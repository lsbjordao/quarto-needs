"""GitHub observations through the source-agnostic reconciliation contracts.

This module pins a discovered fact, not a new implementation: OSLC's
``reconcile_external_requirements`` and ``build_oslc_import_plan`` needed
zero GitHub-specific changes. A GitHub issue observation fetched by
``fetch_external_github_issue`` reconciles and plans through them unchanged
— the same "reuse rather than fork" outcome as the cache and identity
slices, proven here contract by contract.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from quarto_needs.github_issues import (
    build_github_issue_identity,
    fetch_external_github_issue,
    parse_external_github_issue,
)
from quarto_needs.oslc_import_plan import ImportDirective, build_oslc_import_plan
from quarto_needs.oslc_reconcile import reconcile_external_requirements
from quarto_needs.snapshot import AnalysisSnapshot, ObjectRecord


class _Headers(dict[str, str]):
    def get(self, key: str, default=None):  # type: ignore[override]
        for name, value in self.items():
            if name.lower() == key.lower():
                return value
        return default


class _Response:
    def __init__(self, status: int, payload: bytes = b"", **headers: str) -> None:
        self.status = status
        self.code = status
        self._payload = payload
        self.headers = _Headers(headers)

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            return self._payload
        return self._payload[:amount]


class _Opener:
    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.requests: list = []

    def open(self, request, timeout: float):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


ISSUE_URI = "https://api.github.com/repos/acme/widgets/issues/2067"


def _snapshot(local_id: str = "DOC-2067") -> AnalysisSnapshot:
    requirement = ObjectRecord(
        id=local_id,
        type="documentation-requirement",
        title="Document the build pipeline",
        status="draft",
        body="The build pipeline needs authored documentation.",
        rationale="Keep authored content canonical.",
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


def _real_shaped_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "number": 2067,
        "title": "Documentation train 2025-2026",
        "body": "Track the documentation work for the release.",
        "state": "open",
        "html_url": "https://github.com/acme/widgets/issues/2067",
        "updated_at": "2026-08-30T16:08:59Z",
        "labels": [{"id": 1, "name": "documentation"}],
    }
    payload.update(overrides)
    return payload


def _observation(local_id_matching_number: bool = False):
    """A GitHub observation built exactly as the adapter builds it."""
    payload = _real_shaped_payload()
    identity = build_github_issue_identity(
        "acme",
        "widgets",
        2067,
        payload_bytes=json.dumps(payload).encode("utf-8"),
        fetched_at="2026-08-31T12:00:00Z",
    )
    observation = parse_external_github_issue(payload, identity=identity)
    if local_id_matching_number:
        # The canonical ID deliberately equals the issue number: identity
        # must still come only from an explicit binding.
        return observation, _snapshot(local_id="2067")
    return observation, _snapshot()


def test_github_issue_number_stays_data_even_when_it_equals_a_canonical_id() -> None:
    observation, snapshot = _observation(local_id_matching_number=True)

    plan = reconcile_external_requirements(snapshot, (observation,), bindings={})

    assert plan.items[0].status == "unbound"
    assert plan.items[0].canonical_id is None
    assert plan.items[0].external_identifier == "2067"
    assert plan.has_conflicts is False


def test_explicit_api_uri_binding_matches_and_reports_differences_only() -> None:
    observation, snapshot = _observation()
    local_title_before = snapshot.objects_by_id["DOC-2067"].title

    plan = reconcile_external_requirements(
        snapshot, (observation,), bindings={ISSUE_URI: "DOC-2067"}
    )

    assert plan.items[0].status == "matched"
    assert set(plan.items[0].differences) == {"title", "body", "identifier"}
    # Reconciliation is a review artifact: neither side is mutated.
    assert snapshot.objects_by_id["DOC-2067"].title == local_title_before


def test_binding_with_a_non_api_uri_fails_loudly_instead_of_silently_unbinding() -> None:
    observation, snapshot = _observation()

    with pytest.raises(ValueError, match="unobserved external URIs"):
        reconcile_external_requirements(
            snapshot,
            (observation,),
            bindings={"https://github.com/acme/widgets/issues/2067": "DOC-2067"},
        )


def test_full_pipeline_from_fetch_to_reconciliation_uses_exact_bytes_for_provenance() -> None:
    payload = _real_shaped_payload()
    body = json.dumps(payload).encode("utf-8")
    opener = _Opener(_Response(200, body, **{"Content-Type": "application/json"}))
    snapshot = _snapshot()

    observation = fetch_external_github_issue(
        "acme", "widgets", 2067, fetched_at="2026-08-31T12:00:00Z", opener=opener
    )
    plan = reconcile_external_requirements(
        snapshot, (observation,), bindings={observation.identity.resource_uri: "DOC-2067"}
    )

    assert plan.items[0].status == "matched"
    assert observation.identity.digest == "sha256:" + hashlib.sha256(body).hexdigest()
    assert plan.items[0].external_identifier == "2067"


def test_create_directive_on_unbound_observation_plans_a_reviewed_create() -> None:
    observation, snapshot = _observation()
    reconciliation = reconcile_external_requirements(snapshot, (observation,), bindings={})
    directives = {
        ISSUE_URI: ImportDirective(
            action="create",
            canonical_id="DOC-2070",
            canonical_type="documentation-requirement",
            canonical_status="draft",
            target_path="docs/release.qmd",
        )
    }

    plan = build_oslc_import_plan(snapshot, (observation,), reconciliation, directives=directives)

    item = plan.items[0]
    assert item.disposition == "ready-create"
    assert item.canonical_id == "DOC-2070"
    assert item.target_path == "docs/release.qmd"
    assert {key: change["to"] for key, change in dict(item.changes).items()} == {
        "id": "DOC-2070",
        "type": "documentation-requirement",
        "status": "draft",
        "title": "Documentation train 2025-2026",
        "body": "Track the documentation work for the release.",
    }
    assert plan.ready_count == 1


def test_create_directive_targeting_an_existing_canonical_id_is_blocked() -> None:
    observation, snapshot = _observation()
    reconciliation = reconcile_external_requirements(snapshot, (observation,), bindings={})
    directives = {
        ISSUE_URI: ImportDirective(
            action="create",
            canonical_id="DOC-2067",
            canonical_type="documentation-requirement",
            canonical_status="draft",
            target_path="docs/release.qmd",
        )
    }

    plan = build_oslc_import_plan(snapshot, (observation,), reconciliation, directives=directives)

    assert plan.items[0].disposition == "blocked"
    assert plan.has_blocked is True


def test_update_directive_on_matched_observation_plans_only_the_differing_fields() -> None:
    observation, snapshot = _observation()
    reconciliation = reconcile_external_requirements(
        snapshot, (observation,), bindings={ISSUE_URI: "DOC-2067"}
    )
    directives = {ISSUE_URI: ImportDirective(action="update", target_path="docs/release.qmd")}
    objects_before = dict(snapshot.objects_by_id)

    plan = build_oslc_import_plan(snapshot, (observation,), reconciliation, directives=directives)

    item = plan.items[0]
    assert item.disposition == "ready-update"
    assert item.canonical_id == "DOC-2067"
    assert set(dict(item.changes)) == {"title", "body"}
    assert dict(item.changes)["title"] == {
        "from": "Document the build pipeline",
        "to": "Documentation train 2025-2026",
    }
    # The plan is a review artifact; the snapshot is untouched.
    assert snapshot.objects_by_id == objects_before


def test_observation_without_a_directive_stays_review_required() -> None:
    observation, snapshot = _observation()
    reconciliation = reconcile_external_requirements(
        snapshot, (observation,), bindings={ISSUE_URI: "DOC-2067"}
    )

    plan = build_oslc_import_plan(snapshot, (observation,), reconciliation, directives={})

    assert plan.items[0].disposition == "review-required"
    assert plan.requires_review is True


def test_ignore_directive_records_explicit_reviewer_intent() -> None:
    observation, snapshot = _observation()
    reconciliation = reconcile_external_requirements(
        snapshot, (observation,), bindings={ISSUE_URI: "DOC-2067"}
    )
    directives = {ISSUE_URI: ImportDirective(action="ignore")}

    plan = build_oslc_import_plan(snapshot, (observation,), reconciliation, directives=directives)

    assert plan.items[0].disposition == "ignored"


def test_import_plan_items_carry_the_observation_provenance() -> None:
    observation, snapshot = _observation()
    reconciliation = reconcile_external_requirements(snapshot, (observation,), bindings={})

    plan = build_oslc_import_plan(snapshot, (observation,), reconciliation, directives={})

    item = plan.items[0]
    assert item.external_uri == ISSUE_URI
    assert item.source_digest == observation.identity.digest
    assert item.fetched_at == "2026-08-31T12:00:00Z"
