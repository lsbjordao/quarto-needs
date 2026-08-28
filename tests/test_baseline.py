from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs import baseline
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "baseline-v1.schema.json"


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=functional-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "rationale: Protect data.\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n## Login test\nSigns a user in.\n"
        ":::\n",
        encoding="utf-8",
    )


def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def build(root: Path) -> dict[str, object]:
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return baseline.build_baseline(result.snapshot, config)


def test_baseline_validates_against_its_schema(tmp_path: Path) -> None:
    write_project(tmp_path)
    validator().validate(build(tmp_path))


def test_baseline_carries_both_comparison_axes(tmp_path: Path) -> None:
    """Configuration and reference date are what make a round trip stable."""
    write_project(tmp_path)
    payload = build(tmp_path)

    assert payload["valid"] is True
    assert len(payload["configurationFingerprint"]) == 64
    assert payload["referenceDate"]
    assert payload["ruleSetVersion"] == "2"


def test_baseline_stores_authored_content_not_only_fingerprints(tmp_path: Path) -> None:
    """Diff reports modifications by field, which needs the field values."""
    write_project(tmp_path)
    payload = build(tmp_path)

    requirement = next(item for item in payload["objects"] if item["id"] == "REQ-1")
    assert requirement["title"] == "Authenticate"
    assert requirement["rationale"].startswith("Protect")
    assert requirement["attributes"]["priority"] == "high"
    assert requirement["location"]["file"] == "needs.qmd"


def test_baseline_render_is_byte_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    write_project(tmp_path)

    assert baseline.render_baseline(build(tmp_path)) == baseline.render_baseline(build(tmp_path))


def test_write_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    """An overwritten baseline is unrecoverable without version control."""
    write_project(tmp_path)
    payload = build(tmp_path)
    destination = tmp_path / "baselines" / "quarto-needs.json"
    baseline.write_baseline(destination, payload)
    sentinel = destination.read_text(encoding="utf-8")

    with pytest.raises(baseline.BaselineError):
        baseline.write_baseline(destination, payload)

    assert destination.read_text(encoding="utf-8") == sentinel
    baseline.write_baseline(destination, payload, force=True)


def test_load_round_trips_and_rejects_malformed_input(tmp_path: Path) -> None:
    write_project(tmp_path)
    payload = build(tmp_path)
    destination = tmp_path / "b.json"
    baseline.write_baseline(destination, payload)

    assert baseline.load_baseline(destination) == payload

    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(baseline.BaselineError):
        baseline.load_baseline(broken)

    wrong_version = tmp_path / "v2.json"
    wrong_version.write_text(json.dumps({"schemaVersion": "2"}), encoding="utf-8")
    with pytest.raises(baseline.BaselineError):
        baseline.load_baseline(wrong_version)


def test_invalid_baseline_preserves_declarations_and_findings(tmp_path: Path) -> None:
    """The diagnostic artifact exists so `inspect` can explain the failure."""
    (tmp_path / "dup.qmd").write_text(
        "::: {.need #D-1 type=need status=draft}\n\n## A\nA.\n:::\n"
        "\n::: {.need #D-1 type=need status=draft}\n\n## B\nB.\n:::\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is None

    payload = baseline.build_invalid_baseline(result, config)

    validator().validate(payload)
    assert payload["valid"] is False
    assert payload["declarations"]
    assert any(finding["code"] == "REQ004" for finding in payload["findings"])
    assert "objects" not in payload
    assert "semanticGraphFingerprint" not in payload
