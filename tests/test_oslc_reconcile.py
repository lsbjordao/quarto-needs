from __future__ import annotations

from quarto_needs.oslc_reconcile import (
    ExternalRequirementObservation,
    reconcile_external_requirements,
)
from quarto_needs.oslc_rm import ExternalResourceIdentity
from quarto_needs.snapshot import AnalysisSnapshot, ObjectRecord


def _snapshot() -> AnalysisSnapshot:
    requirement = ObjectRecord(
        id="SYS-007",
        type="system-requirement",
        title="Federate OSLC requirements",
        status="approved",
        body="Use a bounded read-only adapter.",
        rationale="Preserve trust boundaries.",
        attributes={},
        locations=(),
    )
    return AnalysisSnapshot(
        objects=(requirement,),
        relations=(),
        findings=(),
        metrics={},
        objects_by_id={requirement.id: requirement},
        outgoing={},
        incoming={},
        generator_name="quarto-needs",
        generator_version="0.1.0",
        relation_catalog_version="1",
        semantic_graph_fingerprint="graph-test",
    )


def _observation(
    uri: str,
    *,
    trust_state: str = "unverified",
    identifier: str | None = "SYS-007",
    title: str = "Federate OSLC requirements",
    description: str = "Use a bounded read-only adapter.",
) -> ExternalRequirementObservation:
    return ExternalRequirementObservation(
        identity=ExternalResourceIdentity(
            resource_uri=uri,
            service_provider_uri="https://provider.test/oslc/sp/1",
            digest="sha256:" + "0" * 64,
            fetched_at="2026-08-30T21:00:00Z",
            trust_state=trust_state,  # type: ignore[arg-type]
        ),
        title=title,
        description=description,
        external_identifier=identifier,
    )


def test_matching_external_identifier_never_creates_implicit_identity() -> None:
    observation = _observation("https://provider.test/oslc/rm/requirements/7")

    plan = reconcile_external_requirements(_snapshot(), (observation,), bindings={})

    assert plan.unbound_count == 1
    assert plan.items[0].status == "unbound"
    assert plan.items[0].canonical_id is None
    assert plan.has_conflicts is False


def test_explicit_binding_matches_and_reports_differences_without_mutation() -> None:
    uri = "https://provider.test/oslc/rm/requirements/7"
    observation = _observation(
        uri,
        identifier="REMOTE-7",
        title="Remote title",
        description="Remote description",
    )
    snapshot = _snapshot()

    plan = reconcile_external_requirements(
        snapshot,
        (observation,),
        bindings={uri: "SYS-007"},
    )

    item = plan.items[0]
    assert item.status == "matched"
    assert item.canonical_id == "SYS-007"
    assert set(item.differences) == {"title", "body", "identifier"}
    assert item.differences["title"] == {
        "local": "Federate OSLC requirements",
        "external": "Remote title",
    }
    assert snapshot.objects_by_id["SYS-007"].title == "Federate OSLC requirements"
    assert plan.has_conflicts is False


def test_stale_and_rejected_observations_block_reconciliation() -> None:
    stale_uri = "https://provider.test/oslc/rm/requirements/stale"
    rejected_uri = "https://provider.test/oslc/rm/requirements/rejected"
    plan = reconcile_external_requirements(
        _snapshot(),
        (
            _observation(stale_uri, trust_state="stale"),
            _observation(rejected_uri, trust_state="rejected"),
        ),
        bindings={stale_uri: "SYS-007", rejected_uri: "SYS-007"},
    )

    assert [item.status for item in plan.items] == [
        "rejected-external",
        "stale-external",
    ]
    assert plan.has_conflicts is True


def test_duplicate_local_bindings_are_explicit_conflicts() -> None:
    first = "https://provider.test/oslc/rm/requirements/1"
    second = "https://provider.test/oslc/rm/requirements/2"

    plan = reconcile_external_requirements(
        _snapshot(),
        (_observation(second), _observation(first)),
        bindings={first: "SYS-007", second: "SYS-007"},
    )

    assert [item.external_uri for item in plan.items] == [first, second]
    assert {item.status for item in plan.items} == {"duplicate-local-binding"}
    assert plan.has_conflicts is True


def test_binding_to_missing_local_object_is_not_treated_as_create() -> None:
    uri = "https://provider.test/oslc/rm/requirements/404"
    plan = reconcile_external_requirements(
        _snapshot(),
        (_observation(uri),),
        bindings={uri: "SYS-404"},
    )

    assert plan.items[0].status == "missing-local"
    assert plan.items[0].canonical_id == "SYS-404"
    assert plan.has_conflicts is True


def test_bindings_cannot_reference_unobserved_resources() -> None:
    import pytest

    with pytest.raises(ValueError, match="unobserved external URIs"):
        reconcile_external_requirements(
            _snapshot(),
            (),
            bindings={"https://provider.test/oslc/rm/requirements/ghost": "SYS-007"},
        )


def test_reconciliation_projection_is_deterministic_and_machine_readable() -> None:
    uri = "https://provider.test/oslc/rm/requirements/7"
    plan = reconcile_external_requirements(
        _snapshot(),
        (_observation(uri),),
        bindings={uri: "SYS-007"},
    )

    assert plan.to_dict() == {
        "schema": "oslc-reconciliation-v1",
        "hasConflicts": False,
        "unboundCount": 0,
        "items": [
            {
                "externalUri": uri,
                "status": "matched",
                "canonicalId": "SYS-007",
                "externalIdentifier": "SYS-007",
                "differences": {},
                "message": "explicit binding resolved; differences are informational only",
            }
        ],
    }
