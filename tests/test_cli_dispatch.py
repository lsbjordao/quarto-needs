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
            {
                "nodeid": "tests/test_localization.py::test_localized_source_semantic_parity_rejects_model_drift",
                "outcome": "passed",
                "requirements": ["FUN-006"],
                "testCases": ["TC-005"],
            },
        ],
        provider_version="8.0",
    )


def test_dispatch_validates_raw_generic_evidence(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "checks.json"
    write_json_atomic(artifact, _generic_payload())

    exit_code = main([
        "--root", str(EXAMPLE), "evidence", "check", str(artifact), "--format", "json"
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
        "--root", str(EXAMPLE), "evidence", "check", str(artifact), "--format", "json"
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
        "--root", str(EXAMPLE), "evidence", "check", str(artifact), "--format", "json"
    ])
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert report["valid"] is False
    assert any(issue["code"] == "EVD210" for issue in report["issues"])


def test_dispatch_delegates_raw_pytest_evidence_to_legacy_cli(tmp_path: Path, capsys) -> None:
    artifact = tmp_path / "pytest.json"
    write_json_atomic(artifact, _complete_pytest_payload())

    exit_code = main([
        "--root", str(EXAMPLE), "evidence", "check", str(artifact), "--format", "json"
    ])
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["provider"] == "pytest"
    assert report["tests"] == 5
    assert report["valid"] is True


def test_attest_wraps_pytest_payload_and_result_is_checkable(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "pytest-provider.json"
    output = tmp_path / "pytest.json"
    write_json_atomic(source, _complete_pytest_payload())
    monkeypatch.setenv("GITHUB_SHA", "abc123")

    exit_code = main([
        "--root",
        str(EXAMPLE),
        "evidence",
        "attest",
        str(source),
        "--output",
        str(output),
        "--expires-hours",
        "24",
        "--source-revision",
        "abc123",
        "--format",
        "json",
    ])
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["artifactSchema"] == "evidence-pytest-v1"
    assert report["provider"] == "pytest"
    assert report["sourceRevision"] == "abc123"

    envelope = json.loads(output.read_text(encoding="utf-8"))
    assert envelope["kind"] == "quarto-needs-evidence"
    assert envelope["artifact"]["schema"] == "evidence-pytest-v1"
    assert envelope["subject"]["sourceRevision"] == "abc123"
    assert envelope["expiresAt"]

    exit_code = main([
        "--root", str(EXAMPLE), "evidence", "check", str(output), "--format", "json"
    ])
    checked = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert checked["valid"] is True
    assert checked["attested"] is True
    assert checked["tests"] == 5


def test_attest_wraps_generic_check_payload(tmp_path: Path, capsys) -> None:
    source = tmp_path / "checks-provider.json"
    output = tmp_path / "checks.json"
    write_json_atomic(source, _generic_payload())

    exit_code = main([
        "--root",
        str(EXAMPLE),
        "evidence",
        "attest",
        str(source),
        "--output",
        str(output),
        "--expires-hours",
        "1",
        "--format",
        "json",
    ])
    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["artifactSchema"] == "evidence-checks-v1"

    envelope = json.loads(output.read_text(encoding="utf-8"))
    assert envelope["artifact"]["schema"] == "evidence-checks-v1"
    assert envelope["artifact"]["payload"]["checks"][0]["evidenceObjects"] == ["EVD-004"]

    exit_code = main([
        "--root", str(EXAMPLE), "evidence", "check", str(output), "--format", "json"
    ])
    checked = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert checked["valid"] is True
    assert checked["attested"] is True


def test_attest_uses_github_sha_when_revision_is_not_explicit(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    source = tmp_path / "checks-provider.json"
    output = tmp_path / "checks.json"
    write_json_atomic(source, _generic_payload())
    monkeypatch.setenv("GITHUB_SHA", "github-sha")

    assert main([
        "--root",
        str(EXAMPLE),
        "evidence",
        "attest",
        str(source),
        "--output",
        str(output),
    ]) == 0
    capsys.readouterr()
    envelope = json.loads(output.read_text(encoding="utf-8"))
    assert envelope["subject"]["sourceRevision"] == "github-sha"


def test_attested_revision_mismatch_is_reported_for_pytest_and_generic(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    monkeypatch.setenv("GITHUB_SHA", "current-revision")
    now = datetime.now(timezone.utc)
    cases = (
        ("pytest", _complete_pytest_payload(), "evidence-pytest-v1"),
        ("generic", _generic_payload(), "evidence-checks-v1"),
    )
    for name, payload, artifact_schema in cases:
        artifact = tmp_path / f"{name}.json"
        envelope = build_evidence_envelope(
            payload,
            provider_name="pytest",
            provider_version="8.0",
            artifact_schema=artifact_schema,
            snapshot=_snapshot(),
            generated_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(hours=1),
            source_revision="old-revision",
        )
        write_json_atomic(artifact, envelope)
        exit_code = main([
            "--root", str(EXAMPLE), "evidence", "check", str(artifact), "--format", "json"
        ])
        report = json.loads(capsys.readouterr().out)
        assert exit_code == 1
        assert any(issue["code"] == "EVD205" for issue in report["issues"])


def test_attest_rejects_nonpositive_expiry(tmp_path: Path, capsys) -> None:
    source = tmp_path / "checks-provider.json"
    output = tmp_path / "checks.json"
    write_json_atomic(source, _generic_payload())

    exit_code = main([
        "--root",
        str(EXAMPLE),
        "evidence",
        "attest",
        str(source),
        "--output",
        str(output),
        "--expires-hours",
        "0",
    ])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "greater than zero" in captured.err
    assert not output.exists()


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
