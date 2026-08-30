from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.cli_dispatch import main
from quarto_needs.config import load_config
from quarto_needs.evidence import build_evidence_envelope, build_pytest_evidence, write_json_atomic
from quarto_needs.evidence_providers import build_check_evidence


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "quarto-needs"


def _snapshot():
    config = load_config(EXAMPLE)
    result = analyze_project(EXAMPLE, config=config)
    assert result.snapshot is not None
    return result.snapshot


def _generic_payload() -> dict[str, object]:
    return build_check_evidence(
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


def _complete_pytest_payload() -> dict[str, object]:
    return build_pytest_evidence(
        [
            {
                "nodeid": "tests/test_architecture_decisions.py::test_accepted_decision_passes_decision_governance",
                "outcome": "passed",
                "requirements": ["SYS-004"],
                "testCases": ["TC-004"],
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
        ],
        provider_version="8.0",
    )


def test_dispatch_validates_raw_generic_evidence(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "checks.json"
    write_json_atomic(artifact, _generic_payload())

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
    assert exit_code == 0
    assert report["provider"] == "pytest"
    assert report["checks"] == 1
    assert report["attested"] is False
    assert report["valid"] is True
    assert report["issues"] == []


def test_dispatch_validates_attested_generic_evidence(tmp_path: Path, capsys) -> None:
    now = datetime.now(timezone.utc)
    envelope = build_evidence_envelope(
        _generic_payload(),
        provider_name="pytest",
        provider_version="8.0",
        artifact_schema="evidence-checks-v1",
        snapshot=_snapshot(),
        generated_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(hours=1),
    )
    artifact = tmp_path / "attested-checks.json"
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
    assert exit_code == 0
    assert report["attested"] is True
    assert report["valid"] is True


def test_dispatch_rejects_expired_generic_attestation(tmp_path: Path, capsys) -> None:
    generated_at = datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc)
    envelope = build_evidence_envelope(
        _generic_payload(),
        provider_name="pytest",
        provider_version="8.0",
        artifact_schema="evidence-checks-v1",
        snapshot=_snapshot(),
        generated_at=generated_at,
        expires_at=generated_at + timedelta(hours=1),
    )
    artifact = tmp_path / "expired-checks.json"
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


def test_dispatch_delegates_raw_pytest_evidence_to_legacy_cli(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "pytest.json"
    write_json_atomic(artifact, _complete_pytest_payload())

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
    assert exit_code == 0
    assert report["provider"] == "pytest"
    assert report["tests"] == 4
    assert report["valid"] is True


def test_dispatch_delegates_non_evidence_command(monkeypatch) -> None:
    observed: list[list[str]] = []

    def fake_legacy(argv):
        observed.append(list(argv))
        return 17

    monkeypatch.setattr("quarto_needs.cli_dispatch.legacy_main", fake_legacy)
    assert main(["check", "--root", str(EXAMPLE)]) == 17
    assert observed == [["check", "--root", str(EXAMPLE)]]


def test_dispatch_rejects_malformed_generic_shape(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "malformed.json"
    artifact.write_text(
        json.dumps(
            {
                "schemaVersion": "1",
                "provider": "lint:ruff",
                "providerVersion": "0.12",
                "checks": [
                    {
                        "id": "lint:ruff",
                        "outcome": "passed",
                        "requirements": [],
                        "testCases": []
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    exit_code = main([
        "--root",
        str(EXAMPLE),
        "evidence",
        "check",
        str(artifact),
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "invalid evidenceObjects" in captured.err
