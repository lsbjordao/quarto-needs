from __future__ import annotations

from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.evidence_providers import build_check_evidence
from quarto_needs.evidence_validation import validate_check_evidence


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "quarto-needs"


def _snapshot():
    config = load_config(EXAMPLE)
    result = analyze_project(EXAMPLE, config=config)
    assert result.snapshot is not None
    return result.snapshot


def test_generic_machine_check_agrees_with_modeled_verification_and_evidence() -> None:
    payload = build_check_evidence(
        "pytest",
        "8.0",
        [
            {
                "id": "adr-governance",
                "outcome": "passed",
                "requirements": ["SYS-004"],
                "testCases": ["TC-004"],
                "evidenceObjects": ["EVD-004"],
            }
        ],
    )
    assert validate_check_evidence(_snapshot(), payload) == ()


def test_generic_machine_check_reports_provider_and_graph_disagreement() -> None:
    payload = build_check_evidence(
        "coverage.py",
        "7.6",
        [
            {
                "id": "wrong-provider",
                "outcome": "failed",
                "requirements": ["SYS-004", "UNKNOWN-REQ"],
                "testCases": ["TC-004", "UNKNOWN-TC"],
                "evidenceObjects": ["EVD-004", "UNKNOWN-EVD"],
            }
        ],
    )
    issues = validate_check_evidence(_snapshot(), payload)
    codes = {issue.code for issue in issues}
    assert {"EVD302", "EVD304", "EVD305", "EVD307", "EVD308"} <= codes


def test_generic_machine_check_requires_modeled_evidence_by_default() -> None:
    payload = build_check_evidence(
        "json-schema",
        "4",
        [
            {
                "id": "public-graph-schema",
                "outcome": "passed",
                "requirements": ["NFR-004"],
                "testCases": ["TC-006"],
            }
        ],
    )
    issues = validate_check_evidence(_snapshot(), payload)
    assert [issue.code for issue in issues] == ["EVD303"]
    assert validate_check_evidence(
        _snapshot(), payload, require_evidence_objects=False
    ) == ()


def test_generic_machine_check_detects_unrelated_evidence_object() -> None:
    payload = build_check_evidence(
        "pytest",
        "8.0",
        [
            {
                "id": "mismatched-evidence",
                "outcome": "passed",
                "requirements": ["SYS-004"],
                "testCases": ["TC-004"],
                "evidenceObjects": ["EVD-006"],
            }
        ],
    )
    issues = validate_check_evidence(_snapshot(), payload)
    assert any(issue.code == "EVD309" for issue in issues)
