from __future__ import annotations

import pytest

from quarto_needs.oslc_import_plan import (
    ImportDirective,
    build_oslc_import_plan,
)
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
    title: str = "Remote title",
    description: str = "Remote description",
    identifier: str | None = "REMOTE-7",
) -> ExternalRequirementObservation:
    return ExternalRequirementObservation(
        identity=ExternalResourceIdentity(
            resource_uri=uri,
            service_provider_uri="https://provider.test/oslc/sp/1",
            digest="sha256:" + "a" * 64,
            fetched_at="2026-08-30T21:10:00Z",
            trust_state=trust_state,  # type: ignore[arg-type]
        ),
        title=title,
        description=description,
        external_identifier=identifier,
    )


@pytest.mark.requirement("SYS-007", "FUN-011", "FUN-013", "NFR-006")
@pytest.mark.quarto_need_test_case("TC-019")
def test_unbound_observation_requires_explicit_create_directive() -> None:
    uri = "https://provider.test/oslc/rm/requirements/7"
    observation = _observation(uri)
    snapshot = _snapshot()
    reconciliation = reconcile_external_requirements(snapshot, (observation,), bindings={})

    plan = build_oslc_import_plan(
        snapshot,
        (observation,),
        reconciliation,
        directives={},
    )

    assert plan.requires_review is True
    assert plan.ready_count == 0
    assert plan.items[0].disposition == "review-required"
    assert snapshot.objects_by_id["SYS-007"].title == "Federate OSLC requirements"


def test_explicit_create_plan_requires_new_identity_type_status_and_target_path() -> None:
    uri = "https://provider.test/oslc/rm/requirements/7"
    observation = _observation(uri)
    snapshot = _snapshot()
    reconciliation = reconcile_external_requirements(snapshot, (observation,), bindings={})

    directive = ImportDirective(
        action="create",
        canonical_id="SYS-008",
        canonical_type="system-requirement",
        canonical_status="draft",
        target_path="requirements/imported-oslc.qmd",
    )
    plan = build_oslc_import_plan(
        snapshot,
        (observation,),
        reconciliation,
        directives={uri: directive},
    )

    item = plan.items[0]
    assert item.disposition == "ready-create"
    assert item.canonical_id == "SYS-008"
    assert item.target_path == "requirements/imported-oslc.qmd"
    assert item.changes["title"] == {"from": None, "to": "Remote title"}
    assert plan.ready_count == 1
    assert "SYS-008" not in snapshot.objects_by_id

    existing = ImportDirective(
        action="create",
        canonical_id="SYS-007",
        canonical_type="system-requirement",
        canonical_status="draft",
        target_path="requirements/imported-oslc.qmd",
    )
    blocked = build_oslc_import_plan(
        snapshot,
        (observation,),
        reconciliation,
        directives={uri: existing},
    )
    assert blocked.items[0].disposition == "blocked"


def test_explicit_update_uses_reconciled_identity_and_only_title_body_differences() -> None:
    uri = "https://provider.test/oslc/rm/requirements/7"
    observation = _observation(uri)
    snapshot = _snapshot()
    reconciliation = reconcile_external_requirements(
        snapshot,
        (observation,),
        bindings={uri: "SYS-007"},
    )

    plan = build_oslc_import_plan(
        snapshot,
        (observation,),
        reconciliation,
        directives={
            uri: ImportDirective(
                action="update",
                target_path="requirements/system.qmd",
            )
        },
    )

    item = plan.items[0]
    assert item.disposition == "ready-update"
    assert item.canonical_id == "SYS-007"
    assert item.canonical_type == "system-requirement"
    assert item.canonical_status == "approved"
    assert set(item.changes) == {"title", "body"}
    assert "identifier" not in item.changes
    assert snapshot.objects_by_id["SYS-007"].body == "Use a bounded read-only adapter."


def test_stale_or_conflicting_reconciliation_blocks_import_directives() -> None:
    stale_uri = "https://provider.test/oslc/rm/requirements/stale"
    stale = _observation(stale_uri, trust_state="stale")
    snapshot = _snapshot()
    reconciliation = reconcile_external_requirements(
        snapshot,
        (stale,),
        bindings={stale_uri: "SYS-007"},
    )

    plan = build_oslc_import_plan(
        snapshot,
        (stale,),
        reconciliation,
        directives={
            stale_uri: ImportDirective(
                action="update",
                target_path="requirements/system.qmd",
            )
        },
    )

    assert plan.has_blocked is True
    assert plan.items[0].disposition == "blocked"
    assert "stale-external" in plan.items[0].message


def test_import_directive_rejects_unsafe_or_incomplete_target_metadata() -> None:
    with pytest.raises(ValueError, match="canonical_type"):
        ImportDirective(
            action="create",
            canonical_id="SYS-008",
            canonical_status="draft",
            target_path="requirements/new.qmd",
        )

    with pytest.raises(ValueError, match="project-relative"):
        ImportDirective(action="update", target_path="../outside.qmd")

    with pytest.raises(ValueError, match=".qmd or .md"):
        ImportDirective(action="update", target_path="requirements/system.txt")


def test_import_plan_projection_is_deterministic_and_provenance_bound() -> None:
    uri = "https://provider.test/oslc/rm/requirements/7"
    observation = _observation(uri)
    snapshot = _snapshot()
    reconciliation = reconcile_external_requirements(snapshot, (observation,), bindings={})
    plan = build_oslc_import_plan(
        snapshot,
        (observation,),
        reconciliation,
        directives={
            uri: ImportDirective(
                action="create",
                canonical_id="SYS-008",
                canonical_type="system-requirement",
                canonical_status="draft",
                target_path="requirements/imported-oslc.qmd",
            )
        },
    )

    document = plan.to_dict()
    assert document["schema"] == "oslc-import-plan-v1"
    assert document["semanticGraphFingerprint"] == "graph-test"
    assert document["readyCount"] == 1
    item = document["items"][0]
    assert item["sourceDigest"] == observation.identity.digest
    assert item["fetchedAt"] == observation.identity.fetched_at
