from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from quarto_needs.analysis import analyze_project
from quarto_needs.baseline import build_baseline
from quarto_needs.config import load_config
from quarto_needs.rules import RULE_SET_VERSION

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "baseline-v1.schema.json"


PROJECT = '''
::: {.need #REQ-1 type="functional-requirement" status="approved" priority="high" tags="security"}
## Authenticate

The service shall authenticate users.

### Rationale

Protect privileged operations.
:::
'''.strip() + "\n"


def write_project(tmp_path: Path) -> None:
    (tmp_path / "needs.qmd").write_text(PROJECT, encoding="utf-8")


def build(tmp_path: Path) -> dict:
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    return build_baseline(result.snapshot, config)


def validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))


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
    assert payload["ruleSetVersion"] == RULE_SET_VERSION


def test_baseline_stores_authored_content_not_only_fingerprints(tmp_path: Path) -> None:
    """Diff reports modifications by field, which needs the field values."""
    write_project(tmp_path)
    payload = build(tmp_path)

    requirement = next(item for item in payload["objects"] if item["id"] == "REQ-1")
    assert requirement["title"] == "Authenticate"
    assert requirement["rationale"].startswith("Protect")
    assert requirement["attributes"]["priority"] == "high"
    assert requirement["location"]["file"] == "needs.qmd"
