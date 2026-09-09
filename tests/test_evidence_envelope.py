from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs.analysis import analyze_project
from quarto_needs.cli import main
from quarto_needs.config import load_config
from quarto_needs.evidence import (
    build_evidence_envelope,
    build_pytest_evidence,
    load_evidence,
    load_pytest_evidence,
    validate_evidence_envelope,
    validate_pytest_evidence,
    write_json_atomic,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "quarto-needs"
SCHEMA = json.loads(
    (ROOT / "schemas" / "evidence-envelope-v1.schema.json").read_text(encoding="utf-8")
)


def _snapshot():
    config = load_config(EXAMPLE)
    result = analyze_project(EXAMPLE, config=config)
    assert result.snapshot is not None
    return result.snapshot


def _provider_payload() -> dict[str, object]:
    return build_pytest_evidence(
        [
            {
                "nodeid": "tests/test_architecture_decisions.py::test_accepted_decision_passes_decision_governance",
                "outcome": "passed",
                "requirements": ["SYS-004"],
                "testCases": ["TC-004"],
            }
        ],
        provider_version="8.0",
    )


def _complete_provider_payload() -> dict[str, object]:
    return build_pytest_evidence(
        [
            {
                "nodeid": "tests/test_architecture_decisions.py::test_accepted_decision_passes_decision_governance",
                "outcome": "passed",
                "requirements": ["SYS-004"],
                "testCases": ["TC-004"],
            },
            {
                "nodeid": "tests/test_graph_assets.py::test_margin_sidebar_toggle_stays_entirely_outside_page_toc",
                "outcome": "passed",
                "requirements": ["FUN-009"],
                "testCases": ["TC-014"],
            },
            {
                "nodeid": "tests/test_localization.py::test_localized_source_semantic_parity_rejects_model_drift",
                "outcome": "passed",
                "requirements": ["FUN-006", "SYS-005"],
                "testCases": ["TC-005"],
            },
            {
                "nodeid": "tests/test_graph_semantics.py::test_public_projection_publishes_catalog_semantics",
                "outcome": "passed",
                "requirements": ["SYS-006", "FUN-008", "NFR-002", "NFR-004"],
                "testCases": ["TC-006"],
            },
            {
                "nodeid": "tests/test_graph_semantics.py::test_named_query_is_materialized_as_reusable_graph_view",
                "outcome": "passed",
                "requirements": ["FUN-003"],
                "testCases": ["TC-009"],
            },
            {
                "nodeid": "tests/test_impact.py::test_editing_a_requirement_impacts_its_verification",
                "outcome": "passed",
                "requirements": ["FUN-005"],
                "testCases": ["TC-011"],
            },
            {
                "nodeid": "tests/test_oslc_federation.py::test_discovery_orchestrates_fetch_normalization_service_and_shape_parsing",
                "outcome": "passed",
                "requirements": ["SYS-007", "FUN-010", "NFR-006"],
                "testCases": ["TC-015"],
            },
            {
                "nodeid": "tests/test_oslc_reconcile.py::test_matching_external_identifier_never_creates_implicit_identity",
                "outcome": "passed",
                "requirements": ["SYS-007", "FUN-011", "NFR-006"],
                "testCases": ["TC-016"],
            },
            {
                "nodeid": "tests/test_oslc_query.py::test_execute_oslc_query_uses_existing_bounded_fetch_and_reports_response_provenance",
                "outcome": "passed",
                "requirements": ["SYS-007", "FUN-012", "NFR-006"],
                "testCases": ["TC-017"],
            },
            {
                "nodeid": "tests/test_oslc_observe.py::test_materialization_fetches_each_member_and_preserves_individual_provenance",
                "outcome": "passed",
                "requirements": ["SYS-007", "FUN-013", "NFR-006"],
                "testCases": ["TC-018"],
            },
            {
                "nodeid": "tests/test_oslc_import_plan.py::test_unbound_observation_requires_explicit_create_directive",
                "outcome": "passed",
                "requirements": ["SYS-007", "FUN-011", "FUN-013", "NFR-006"],
                "testCases": ["TC-019"],
            },
            {
                "nodeid": "tests/test_github_issues.py::test_fetch_external_github_issue_composes_transport_identity_and_parsing",
                "outcome": "passed",
                "requirements": ["SYS-008", "FUN-014", "NFR-007"],
                "testCases": ["TC-020"],
            },
            {
                "nodeid": "tests/test_github_issues.py::test_fetch_external_github_issue_sends_conditional_request_when_cache_is_stale",
                "outcome": "passed",
                "requirements": ["SYS-008", "FUN-015", "NFR-007"],
                "testCases": ["TC-021"],
            },
            {
                "nodeid": "tests/test_github_issues.py::test_fetch_external_github_issue_list_pages_follows_rel_next_across_pages",
                "outcome": "passed",
                "requirements": ["SYS-008", "FUN-016", "NFR-007"],
                "testCases": ["TC-022"],
            },
            {
                "nodeid": "tests/test_github_reconcile.py::test_github_issue_number_stays_data_even_when_it_equals_a_canonical_id",
                "outcome": "passed",
                "requirements": ["SYS-008", "FUN-017"],
                "testCases": ["TC-023"],
            },
            {
                "nodeid": "tests/test_github_http.py::test_fetch_github_resource_403_with_exhausted_rate_limit_is_rate_limited",
                "outcome": "passed",
                "requirements": ["SYS-008", "NFR-007"],
                "testCases": ["TC-024"],
            },
            {
                "nodeid": "tests/test_extension_first_distribution.py::test_a_clean_consumer_project_needs_no_engine_installation",
                "outcome": "passed",
                "requirements": ["SYS-009", "FUN-018", "FUN-019"],
                "testCases": ["TC-025"],
            },
            {
                "nodeid": "tests/test_extension_first_distribution.py::test_a_second_render_succeeds_without_any_engine_source",
                "outcome": "passed",
                "requirements": ["SYS-009", "NFR-009"],
                "testCases": ["TC-026"],
            },
            {
                "nodeid": "tests/test_extension_bootstrap.py::test_a_wrong_global_engine_never_wins_over_the_managed_runtime",
                "outcome": "passed",
                "requirements": ["FUN-018", "FUN-019"],
                "testCases": ["TC-027"],
            },
            {
                "nodeid": "tests/test_extension_bootstrap.py::test_a_corrupted_runtime_is_reprovisioned",
                "outcome": "passed",
                "requirements": ["FUN-018"],
                "testCases": ["TC-028"],
            },
            {
                "nodeid": "tests/test_extension_bootstrap.py::test_two_concurrent_bootstrap_processes_produce_one_installation",
                "outcome": "passed",
                "requirements": ["NFR-008"],
                "testCases": ["TC-029"],
            },
            {
                "nodeid": "tests/test_extension_first_distribution.py::test_the_project_path_may_contain_spaces",
                "outcome": "passed",
                "requirements": ["FUN-018"],
                "testCases": ["TC-030"],
            },
            {
                "nodeid": "tests/test_extension_distribution_contract.py::test_manifest_declares_the_quarto_floor",
                "outcome": "passed",
                "requirements": ["SYS-009"],
                "testCases": ["TC-031"],
            },
            {
                "nodeid": "tests/test_cli_version.py::test_version_works_outside_a_project",
                "outcome": "passed",
                "requirements": ["FUN-020"],
                "testCases": ["TC-032"],
            },
        ],
        provider_version="8.0",
    )


def test_provider_neutral_envelope_is_schema_valid_and_binds_current_graph() -> None:
    snapshot = _snapshot()
    generated_at = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    envelope = build_evidence_envelope(
        _provider_payload(),
        provider_name="pytest",
        provider_version="8.0",
        artifact_schema="evidence-pytest-v1",
        snapshot=snapshot,
        generated_at=generated_at,
        source_revision="abc123",
    )

    Draft202012Validator(SCHEMA).validate(envelope)
    assert envelope["generatedAt"] == "2026-08-30T12:00:00Z"
    assert envelope["subject"] == {
        "configurationFingerprint": snapshot.configuration_fingerprint,
        "semanticGraphFingerprint": snapshot.semantic_graph_fingerprint,
        "representationFingerprint": snapshot.representation_fingerprint,
        "sourceRevision": "abc123",
    }
    assert validate_evidence_envelope(
        snapshot,
        envelope,
        now=generated_at + timedelta(hours=2),
        max_age_hours=4,
        expected_source_revision="abc123",
    ) == ()


def test_envelope_loader_rejects_tampered_provider_payload(tmp_path: Path) -> None:
    envelope = build_evidence_envelope(
        _provider_payload(),
        provider_name="pytest",
        provider_version="8.0",
        artifact_schema="evidence-pytest-v1",
        snapshot=_snapshot(),
        generated_at=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
    )
    envelope["artifact"]["payload"]["summary"]["passed"] = 999  # type: ignore[index]
    artifact = tmp_path / "evidence.json"
    write_json_atomic(artifact, envelope)

    with pytest.raises(ValueError, match="digest does not match"):
        load_evidence(artifact)


def test_envelope_validation_reports_graph_and_revision_drift() -> None:
    snapshot = _snapshot()
    envelope = build_evidence_envelope(
        _provider_payload(),
        provider_name="pytest",
        provider_version="8.0",
        artifact_schema="evidence-pytest-v1",
        snapshot=snapshot,
        generated_at=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
        source_revision="old-revision",
    )
    envelope["subject"]["configurationFingerprint"] = "different-config"  # type: ignore[index]
    envelope["subject"]["semanticGraphFingerprint"] = "different-graph"  # type: ignore[index]
    envelope["subject"]["representationFingerprint"] = "different-representation"  # type: ignore[index]

    issues = validate_evidence_envelope(
        snapshot,
        envelope,
        expected_source_revision="current-revision",
    )
    assert {issue.code for issue in issues} == {"EVD202", "EVD203", "EVD204", "EVD205"}


def test_envelope_freshness_policy_rejects_expired_and_future_evidence() -> None:
    snapshot = _snapshot()
    generated_at = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
    envelope = build_evidence_envelope(
        _provider_payload(),
        provider_name="pytest",
        provider_version="8.0",
        artifact_schema="evidence-pytest-v1",
        snapshot=snapshot,
        generated_at=generated_at,
    )

    expired = validate_evidence_envelope(
        snapshot,
        envelope,
        now=generated_at + timedelta(hours=25),
        max_age_hours=24,
    )
    assert [issue.code for issue in expired] == ["EVD208"]

    future = validate_evidence_envelope(
        snapshot,
        envelope,
        now=generated_at - timedelta(minutes=1),
        max_age_hours=24,
    )
    assert [issue.code for issue in future] == ["EVD207"]


def test_explicit_expiry_is_enforced_without_cli_policy() -> None:
    snapshot = _snapshot()
    generated_at = datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc)
    envelope = build_evidence_envelope(
        _provider_payload(),
        provider_name="pytest",
        provider_version="8.0",
        artifact_schema="evidence-pytest-v1",
        snapshot=snapshot,
        generated_at=generated_at,
        expires_at=generated_at + timedelta(hours=1),
    )
    issues = validate_evidence_envelope(
        snapshot,
        envelope,
        now=generated_at + timedelta(hours=2),
    )
    assert [issue.code for issue in issues] == ["EVD210"]


def test_load_evidence_remains_backward_compatible_with_raw_pytest(tmp_path: Path) -> None:
    artifact = tmp_path / "pytest.json"
    payload = _provider_payload()
    write_json_atomic(artifact, payload)

    envelope, loaded = load_evidence(artifact)
    assert envelope is None
    assert loaded == payload


def test_existing_pytest_loader_and_validator_accept_attested_payload(tmp_path: Path) -> None:
    snapshot = _snapshot()
    envelope = build_evidence_envelope(
        _complete_provider_payload(),
        provider_name="pytest",
        provider_version="8.0",
        artifact_schema="evidence-pytest-v1",
        snapshot=snapshot,
        generated_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    artifact = tmp_path / "attested-pytest.json"
    write_json_atomic(artifact, envelope)

    loaded = load_pytest_evidence(artifact)
    assert validate_pytest_evidence(snapshot, loaded) == ()


def test_existing_evidence_check_reports_expired_attestation(tmp_path: Path, capsys) -> None:
    generated_at = datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc)
    envelope = build_evidence_envelope(
        _complete_provider_payload(),
        provider_name="pytest",
        provider_version="8.0",
        artifact_schema="evidence-pytest-v1",
        snapshot=_snapshot(),
        generated_at=generated_at,
        expires_at=generated_at + timedelta(hours=1),
    )
    artifact = tmp_path / "expired.json"
    write_json_atomic(artifact, envelope)

    exit_code = main([
        "--root",
        str(EXAMPLE),
        "evidence",
        "check",
        str(artifact),
        "--format",
        "json",
    ])
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert report["valid"] is False
    assert any(issue["code"] == "EVD210" for issue in report["issues"])
