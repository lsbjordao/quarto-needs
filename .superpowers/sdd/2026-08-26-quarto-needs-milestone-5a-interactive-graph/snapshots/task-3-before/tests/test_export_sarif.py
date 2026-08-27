from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import sarif_export


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "vendor" / "sarif-2.1.0" / "sarif-schema.json"

# Locked in schemas/vendor/sarif-2.1.0/VENDORED.md so an offline build cannot
# drift from the reviewed vendor copy.
VENDORED_SHA256 = "7c9688f0a1c4a4e1649ecc78521087e664729c1dff56ee8212ff195c7b16132a"


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nBody.\n"
        ":::\n"
        "\n"
        "::: {.need #DUP type=need status=draft}\n\n## A\nA.\n:::\n"
        "\n::: {.need #DUP type=need status=draft}\n\n## B\nB.\n:::\n",
        encoding="utf-8",
    )


def snapshot_with_findings(root: Path):
    result = analyze_project(root, config=load_config(root))
    return result.declarations and result.findings and result or None


def test_sarif_validates_against_the_vendored_schema(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)

    (tmp_path / "ok.qmd").write_text(
        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
    )
    result = analyze_project(tmp_path, config=load_config(tmp_path))
    assert result.snapshot is not None

    payload = json.loads(sarif_export.render(result.snapshot))
    Draft7Validator(schema).validate(payload)


def test_sarif_maps_findings_with_locations_and_fingerprints(tmp_path: Path) -> None:
    write_project(tmp_path)
    result = analyze_project(tmp_path, config=load_config(tmp_path))
    assert any(f.code == "REQ004" for f in result.findings)

    payload = json.loads(sarif_export.render_from_findings(result.findings))
    result_entry = next(r for r in payload["runs"][0]["results"] if r["ruleId"] == "REQ004")

    assert result_entry["fingerprints"]["primaryLocationLineHash"]
    assert result_entry["locations"][0]["physicalLocation"]["region"]["startLine"] > 0
    assert payload["runs"][0]["tool"]["driver"]["rules"], "rule metadata must be present"


def test_sarif_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    write_project(tmp_path)
    result = analyze_project(tmp_path, config=load_config(tmp_path))
    assert sarif_export.render_from_findings(result.findings) == sarif_export.render_from_findings(result.findings)


def test_vendored_sarif_schema_checksum_is_locked() -> None:
    """The vendored SARIF schema must match the SHA-256 recorded in VENDORED.md."""
    assert hashlib.sha256(SCHEMA.read_bytes()).hexdigest() == VENDORED_SHA256
