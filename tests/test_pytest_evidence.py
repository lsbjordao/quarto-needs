from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from quarto_needs.analysis import analyze_project
from quarto_needs.cli import main
from quarto_needs.config import load_config
from quarto_needs.evidence import (
    build_pytest_evidence,
    validate_pytest_evidence,
    write_json_atomic,
)
from quarto_needs.pytest_plugin import _combined_outcome


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "quarto-needs"
SCHEMA = json.loads(
    (ROOT / "schemas" / "evidence-pytest-v1.schema.json").read_text(encoding="utf-8")
)

pytest_plugins = ("pytester",)


def test_pytest_evidence_is_deterministic_and_schema_valid() -> None:
    records = [
        {"nodeid": "tests/test_b.py::test_b", "outcome": "failed", "requirements": ["FUN-004", "SYS-006", "FUN-004"], "testCases": ["TC-010"]},
        {"nodeid": "tests/test_a.py::test_a", "outcome": "passed", "requirements": ["FUN-006"], "testCases": ["TC-005"]},
    ]
    first = build_pytest_evidence(records, provider_version="8.0")
    second = build_pytest_evidence(reversed(records), provider_version="8.0")
    assert first == second
    assert [entry["nodeid"] for entry in first["tests"]] == ["tests/test_a.py::test_a", "tests/test_b.py::test_b"]
    assert first["tests"][1]["requirements"] == ["FUN-004", "SYS-006"]
    assert first["summary"] == {"total": 2, "passed": 1, "failed": 1, "skipped": 0}
    Draft202012Validator(SCHEMA).validate(first)


def test_pytest_phase_outcomes_are_combined_conservatively() -> None:
    assert _combined_outcome({"setup": "passed", "call": "passed", "teardown": "passed"}) == "passed"
    assert _combined_outcome({"setup": "passed", "call": "skipped", "teardown": "passed"}) == "skipped"
    assert _combined_outcome({"setup": "failed"}) == "failed"
    assert _combined_outcome({"setup": "passed", "call": "passed", "teardown": "failed"}) == "failed"


def test_pytest_plugin_emits_only_linked_tests(pytester, monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    pytester.makepyfile(test_sample='''
import pytest
@pytest.mark.requirement("FUN-004")
@pytest.mark.quarto_need_test_case("TC-010")
def test_linked():
    assert True
def test_unlinked():
    assert True
''')
    result = pytester.runpytest_subprocess("-p", "quarto_needs.pytest_plugin", "--quarto-needs-evidence=evidence.json", "-q")
    result.assert_outcomes(passed=2)
    payload = json.loads((pytester.path / "evidence.json").read_text(encoding="utf-8"))
    Draft202012Validator(SCHEMA).validate(payload)
    assert payload["summary"] == {"total": 1, "passed": 1, "failed": 0, "skipped": 0}
    assert payload["tests"] == [{"nodeid": "test_sample.py::test_linked", "outcome": "passed", "requirements": ["FUN-004"], "testCases": ["TC-010"]}]


def test_pytest_plugin_normalizes_xfail_and_xpass_conservatively(pytester, monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    pytester.makepyfile(test_sample='''
import pytest

@pytest.mark.requirement("FUN-004")
@pytest.mark.quarto_need_test_case("TC-010")
@pytest.mark.xfail(reason="known defect")
def test_expected_failure():
    assert False

@pytest.mark.requirement("FUN-004")
@pytest.mark.quarto_need_test_case("TC-010")
@pytest.mark.xfail(reason="known defect", strict=False)
def test_unexpected_pass():
    assert True
''')
    pytester.runpytest_subprocess(
        "-p",
        "quarto_needs.pytest_plugin",
        "--quarto-needs-evidence=evidence.json",
        "-q",
    )
    payload = json.loads((pytester.path / "evidence.json").read_text(encoding="utf-8"))
    Draft202012Validator(SCHEMA).validate(payload)
    outcomes = {entry["nodeid"]: entry["outcome"] for entry in payload["tests"]}
    assert outcomes == {
        "test_sample.py::test_expected_failure": "skipped",
        "test_sample.py::test_unexpected_pass": "failed",
    }
    assert payload["summary"] == {"total": 2, "passed": 0, "failed": 1, "skipped": 1}


def test_pytest_plugin_has_no_artifact_side_effect_without_opt_in(pytester, monkeypatch) -> None:
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    pytester.makepyfile(test_sample='''
import pytest
@pytest.mark.requirement("FUN-004")
def test_linked():
    assert True
''')
    result = pytester.runpytest_subprocess("-p", "quarto_needs.pytest_plugin", "-q")
    result.assert_outcomes(passed=1)
    assert not (pytester.path / ".quarto-needs" / "evidence").exists()


def _self_hosted_snapshot():
    config = load_config(EXAMPLE)
    result = analyze_project(EXAMPLE, config=config)
    assert result.snapshot is not None
    return result.snapshot


def _self_hosted_records() -> list[dict[str, object]]:
    return [
        {"nodeid": "tests/test_architecture_decisions.py::test_accepted_decision_passes_decision_governance", "outcome": "passed", "requirements": ["SYS-004"], "testCases": ["TC-004"]},
        {"nodeid": "tests/test_graph_assets.py::test_margin_sidebar_toggle_stays_entirely_outside_page_toc", "outcome": "passed", "requirements": ["FUN-009"], "testCases": ["TC-014"]},
        {"nodeid": "tests/test_graph_semantics.py::test_public_projection_publishes_catalog_semantics", "outcome": "passed", "requirements": ["SYS-006", "FUN-008", "NFR-002", "NFR-004"], "testCases": ["TC-006"]},
        {"nodeid": "tests/test_graph_semantics.py::test_named_query_is_materialized_as_reusable_graph_view", "outcome": "passed", "requirements": ["FUN-003"], "testCases": ["TC-009"]},
        {"nodeid": "tests/test_impact.py::test_editing_a_requirement_impacts_its_verification", "outcome": "passed", "requirements": ["FUN-005"], "testCases": ["TC-011"]},
        {"nodeid": "tests/test_localization.py::test_localized_source_semantic_parity_rejects_model_drift", "outcome": "passed", "requirements": ["FUN-006", "SYS-005"], "testCases": ["TC-005"]},
        {"nodeid": "tests/test_oslc_federation.py::test_discovery_orchestrates_fetch_normalization_service_and_shape_parsing", "outcome": "passed", "requirements": ["SYS-007", "FUN-010", "NFR-006"], "testCases": ["TC-015"]},
        {"nodeid": "tests/test_oslc_reconcile.py::test_matching_external_identifier_never_creates_implicit_identity", "outcome": "passed", "requirements": ["SYS-007", "FUN-011", "NFR-006"], "testCases": ["TC-016"]},
        {"nodeid": "tests/test_oslc_query.py::test_execute_oslc_query_uses_existing_bounded_fetch_and_reports_response_provenance", "outcome": "passed", "requirements": ["SYS-007", "FUN-012", "NFR-006"], "testCases": ["TC-017"]},
        {"nodeid": "tests/test_oslc_observe.py::test_materialization_fetches_each_member_and_preserves_individual_provenance", "outcome": "passed", "requirements": ["SYS-007", "FUN-013", "NFR-006"], "testCases": ["TC-018"]},
        {"nodeid": "tests/test_oslc_import_plan.py::test_unbound_observation_requires_explicit_create_directive", "outcome": "passed", "requirements": ["SYS-007", "FUN-011", "FUN-013", "NFR-006"], "testCases": ["TC-019"]},
        {"nodeid": "tests/test_github_issues.py::test_fetch_external_github_issue_composes_transport_identity_and_parsing", "outcome": "passed", "requirements": ["SYS-008", "FUN-014", "NFR-007"], "testCases": ["TC-020"]},
        {"nodeid": "tests/test_github_issues.py::test_fetch_external_github_issue_sends_conditional_request_when_cache_is_stale", "outcome": "passed", "requirements": ["SYS-008", "FUN-015", "NFR-007"], "testCases": ["TC-021"]},
        {"nodeid": "tests/test_github_issues.py::test_fetch_external_github_issue_list_pages_follows_rel_next_across_pages", "outcome": "passed", "requirements": ["SYS-008", "FUN-016", "NFR-007"], "testCases": ["TC-022"]},
        {"nodeid": "tests/test_github_reconcile.py::test_github_issue_number_stays_data_even_when_it_equals_a_canonical_id", "outcome": "passed", "requirements": ["SYS-008", "FUN-017"], "testCases": ["TC-023"]},
        {"nodeid": "tests/test_github_http.py::test_fetch_github_resource_403_with_exhausted_rate_limit_is_rate_limited", "outcome": "passed", "requirements": ["SYS-008", "NFR-007"], "testCases": ["TC-024"]},
        {"nodeid": "tests/test_extension_first_distribution.py::test_a_clean_consumer_project_needs_no_engine_installation", "outcome": "passed", "requirements": ["SYS-009", "FUN-018", "FUN-019"], "testCases": ["TC-025"]},
        {"nodeid": "tests/test_extension_first_distribution.py::test_a_second_render_succeeds_without_any_engine_source", "outcome": "passed", "requirements": ["SYS-009", "NFR-009"], "testCases": ["TC-026"]},
        {"nodeid": "tests/test_extension_bootstrap.py::test_a_wrong_global_engine_never_wins_over_the_managed_runtime", "outcome": "passed", "requirements": ["FUN-018", "FUN-019"], "testCases": ["TC-027"]},
        {"nodeid": "tests/test_extension_bootstrap.py::test_a_corrupted_runtime_is_reprovisioned", "outcome": "passed", "requirements": ["FUN-018"], "testCases": ["TC-028"]},
        {"nodeid": "tests/test_extension_bootstrap.py::test_two_concurrent_bootstrap_processes_produce_one_installation", "outcome": "passed", "requirements": ["NFR-008"], "testCases": ["TC-029"]},
        {"nodeid": "tests/test_extension_first_distribution.py::test_the_project_path_may_contain_spaces", "outcome": "passed", "requirements": ["FUN-018"], "testCases": ["TC-030"]},
        {"nodeid": "tests/test_extension_distribution_contract.py::test_manifest_declares_the_quarto_floor", "outcome": "passed", "requirements": ["SYS-009"], "testCases": ["TC-031"]},
    ]


def test_machine_evidence_agrees_with_self_hosted_model() -> None:
    payload = build_pytest_evidence(_self_hosted_records(), provider_version="8.0")
    assert validate_pytest_evidence(_self_hosted_snapshot(), payload) == ()


def test_machine_evidence_reports_model_disagreement() -> None:
    records = _self_hosted_records()
    records[3] = {"nodeid": "tests/test_wrong.py::test_wrong", "outcome": "failed", "requirements": ["FUN-003", "UNKNOWN-REQ"], "testCases": ["TC-009", "UNKNOWN-TC"]}
    payload = build_pytest_evidence(records, provider_version="8.0")
    issues = validate_pytest_evidence(_self_hosted_snapshot(), payload)
    codes = {issue.code for issue in issues}
    assert {"EVD101", "EVD103", "EVD105", "EVD106"} <= codes


def test_machine_evidence_reports_missing_modeled_binding() -> None:
    records = [record for record in _self_hosted_records() if record["testCases"] != ["TC-011"]]
    payload = build_pytest_evidence(records, provider_version="8.0")
    issues = validate_pytest_evidence(_self_hosted_snapshot(), payload)
    missing = [issue for issue in issues if issue.code == "EVD108"]
    assert [(issue.object_id, issue.nodeid) for issue in missing] == [
        ("TC-011", "tests/test_impact.py::test_editing_a_requirement_impacts_its_verification")
    ]


def test_machine_evidence_reports_requirement_omitted_from_bound_test_case() -> None:
    records = _self_hosted_records()
    records[2] = {
        **records[2],
        "requirements": ["SYS-006", "FUN-008", "NFR-002"],
    }
    payload = build_pytest_evidence(records, provider_version="8.0")
    issues = validate_pytest_evidence(_self_hosted_snapshot(), payload)
    missing = [issue for issue in issues if issue.code == "EVD109"]
    assert [(issue.object_id, issue.nodeid) for issue in missing] == [
        (
            "NFR-004",
            "tests/test_graph_semantics.py::test_public_projection_publishes_catalog_semantics",
        )
    ]


def test_evidence_check_cli_validates_against_current_graph(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "pytest.json"
    payload = build_pytest_evidence(_self_hosted_records(), provider_version="8.0")
    write_json_atomic(artifact, payload)
    exit_code = main(["--root", str(EXAMPLE), "evidence", "check", str(artifact), "--format", "json"])
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert exit_code == 0
    assert report["valid"] is True
    assert report["issues"] == []
    assert report["tests"] == 23
