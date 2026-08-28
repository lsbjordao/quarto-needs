from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_objects, analyze_project
from quarto_needs.config import ConfigurationError, load_config
from quarto_needs.diagnostics import Finding
from quarto_needs.model import EngineeringObject, Relation
from quarto_needs.rules import RULES, run_rules

ROOT = Path(__file__).resolve().parents[1]


def obj(
    id: str,
    *,
    type: str = "functional-requirement",
    status: str = "draft",
    attributes: dict | None = None,
    relations: list[Relation] | None = None,
) -> EngineeringObject:
    return EngineeringObject(
        id, type, id.title(), status=status, attributes=attributes or {}, relations=relations or []
    )


def snapshot_with(*objects: EngineeringObject):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None
    return result.snapshot


# --- fingerprints ------------------------------------------------------------


def test_fingerprint_is_stable_across_severity_changes() -> None:
    base = Finding("REQ002", "warning", "X has no rationale", "X")
    raised = Finding("REQ002", "error", "X has no rationale", "X")
    assert base.fingerprint == raised.fingerprint
    other = Finding("REQ002", "warning", "Y has no rationale", "Y")
    assert base.fingerprint != other.fingerprint
    assert len(base.fingerprint) == 64


# --- registry ----------------------------------------------------------------


def test_registry_covers_legacy_and_governance_codes() -> None:
    assert tuple(sorted(RULES)) == (
        "DEC001", "DEC002", "DEC003", "DEC004", "DEC005",
        "ID001", "OBJ001",
        "REQ002", "REQ004", "REQ005", "REQ006",
        "REQ008", "REQ009", "REQ010", "REQ011",
        "REQ012", "REQ013", "REQ014", "REQ015",
    )
    assert RULES["REQ004"].structural
    assert RULES["REQ005"].structural
    assert RULES["DEC005"].supported_severities == ("error",)


# --- individual governance rules ---------------------------------------------


def make_config(directory: Path, document: str):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / ".quarto-needs.toml").write_text(document, encoding="utf-8")
    return load_config(directory)


def test_required_attribute_rule(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        '[types.functional-requirement]\nrequired-attributes = ["priority"]\n',
    )
    snapshot = snapshot_with(obj("OK", attributes={"priority": "high"}), obj("MISSING"))
    findings = [f for f in run_rules(snapshot, config) if f.code == "REQ008"]
    assert findings[0].object_id == "MISSING"
    assert findings[0].properties["attribute"] == "priority"


def test_endpoint_policy_rule(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        '[relations."verified-by"]\n'
        'allowed-source-types = ["system-requirement"]\n'
        'allowed-target-types = ["test-case"]\n',
    )
    snapshot = snapshot_with(
        obj("GOOD", type="system-requirement", relations=[Relation("verified-by", "GOOD", "TC")]),
        obj("BAD-SOURCE", relations=[Relation("verified-by", "BAD-SOURCE", "TC")]),
        obj("TC", type="test-case"),
        obj("BAD-TARGET", type="system-requirement", relations=[Relation("verified-by", "BAD-TARGET", "RISK")]),
        obj("RISK", type="risk"),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "REQ009"]
    assert [f.object_id for f in findings] == ["BAD-SOURCE", "RISK"]
    assert findings[0].properties == {"side": "source", "expected": ("system-requirement",)}
    assert findings[1].properties == {"side": "target", "expected": ("test-case",)}


def test_cardinality_rule(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        '[relations."verified-by"]\nminimum-per-source = 2\nmaximum-per-source = 3\n',
    )
    many = [Relation("verified-by", "BUSY", f"TC{i}") for i in range(4)]
    snapshot = snapshot_with(
        obj("BUSY", relations=list(many)),
        obj("LONELY", relations=[Relation("verified-by", "LONELY", "T0")]),
        *[obj(f"TC{i}", type="test-case") for i in range(4)],
        obj("T0", type="test-case"),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "REQ010"]
    assert [f.object_id for f in findings] == ["BUSY", "LONELY"]


def test_approved_without_implementation_rule(tmp_path: Path) -> None:
    config = make_config(tmp_path, "[rules.REQ011]\nenabled = true\n")
    snapshot = snapshot_with(
        obj("IMPL", status="approved", relations=[Relation("implemented-by", "IMPL", "CODE")]),
        obj("BARE", status="approved"),
        obj("DRAFTED", status="draft"),
        obj("CODE", type="component"),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "REQ011"]
    assert [(f.object_id, f.severity) for f in findings] == [("BARE", "warning")]


def test_test_without_evidence_rule(tmp_path: Path) -> None:
    config = make_config(tmp_path, "[rules.REQ012]\nenabled = true\n")
    snapshot = snapshot_with(
        obj("TC-PASSED", type="test-case", status="passed"),
        obj("TC-EVIDENCED", type="test-case", status="passed", relations=[Relation("evidenced-by", "TC-EVIDENCED", "EV")]),
        obj("TC-DRAFT", type="test-case", status="draft"),
        obj("EV", type="evidence"),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "REQ012"]
    assert [f.object_id for f in findings] == ["TC-PASSED"]


def test_high_risk_without_mitigation_rule(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        '[rules.REQ013]\nenabled = true\nseverity = "error"\n',
    )
    snapshot = snapshot_with(
        obj("RISK-HIGH", type="risk", attributes={"priority": "High"}),
        obj("RISK-CRIT", type="risk", attributes={"priority": "critical"}),
        obj("RISK-MITIGATED", type="risk", attributes={"priority": "high"}),
        obj("RISK-LOW", type="risk", attributes={"priority": "low"}),
        obj("CTRL", type="control", relations=[Relation("mitigates", "CTRL", "RISK-MITIGATED")]),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "REQ013"]
    assert [(f.object_id, f.severity) for f in findings] == [
        ("RISK-CRIT", "error"),
        ("RISK-HIGH", "error"),
    ]


def test_orphaned_object_rule(tmp_path: Path) -> None:
    config = make_config(tmp_path, "[rules.REQ014]\nenabled = true\n")
    snapshot = snapshot_with(
        obj("ISLAND"),
        obj("CONNECTED", relations=[Relation("references", "CONNECTED", "PEER")]),
        obj("PEER"),
    )
    findings = run_rules(snapshot, config)
    assert [(f.code, f.object_id, f.severity) for f in findings] == [("REQ014", "ISLAND", "info")]


def test_expired_evidence_rule(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    config = make_config(tmp_path, "[rules.REQ015]\nenabled = true\n")
    snapshot = snapshot_with(
        obj("TC", type="test-case", status="passed", relations=[
            Relation("evidenced-by", "TC", "EV-OLD"),
            Relation("evidenced-by", "TC", "EV-FRESH"),
        ]),
        obj("EV-OLD", type="evidence", attributes={"expires": "2024-06-30"}),
        obj("EV-FRESH", type="evidence", attributes={"expires": "2030-01-01"}),
        obj("EV-BAD", type="evidence", attributes={"expires": "not-a-date"}),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "REQ015"]
    assert [f.object_id for f in findings] == ["EV-BAD", "EV-OLD"]
    assert findings[0].properties["reason"] == "unparseable"
    assert findings[1].properties["referenceDate"] == "2025-01-01"


# --- configuration interaction ------------------------------------------------


def test_disabled_and_remapped_legacy_rules(tmp_path: Path) -> None:
    config = make_config(
        tmp_path,
        '[rules.REQ002]\nenabled = false\n'
        '[rules.REQ006]\nseverity = "error"\n',
    )
    result = analyze_objects([obj("A", status="approved")], config=config)
    assert result.snapshot is not None
    codes = {(f.code, f.severity) for f in result.findings}
    assert ("REQ002", "warning") not in codes
    assert ("REQ006", "error") in codes


def test_structural_rules_cannot_be_disabled_or_remapped(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        make_config(tmp_path / "a", '[rules.REQ004]\nenabled = false\n')
    with pytest.raises(ConfigurationError):
        make_config(tmp_path / "b", '[rules.REQ005]\nseverity = "info"\n')


def test_embedded_defaults_keep_canonical_output_identical() -> None:
    root = ROOT / "tests/fixtures/canonical"
    baseline = analyze_project(root, files=[root / "a-tests.qmd", root / "z-requirements.qmd"])
    assert baseline.snapshot is not None
    assert all(f.code in {"REQ002", "REQ004", "REQ005", "REQ006"} for f in baseline.snapshot.findings)


def test_enabled_rules_do_not_invalidate_snapshots(tmp_path: Path) -> None:
    document = (
        "[rules.REQ011]\nenabled = true\n"
        "[rules.REQ012]\nenabled = true\n"
        "[rules.REQ013]\nenabled = true\n"
        "[rules.REQ014]\nenabled = true\n"
    )
    (tmp_path / ".quarto-needs.toml").write_text(document, encoding="utf-8")
    source = tmp_path / "page.qmd"
    source.write_text(
        "::: {.need #RISK-1 type=risk status=draft priority=high}\n"
        "## High risk\n"
        ":::\n"
        "\n"
        "::: {.need #REQ-1 type=functional-requirement status=approved}\n"
        "## Approved requirement\n"
        ":::\n",
        encoding="utf-8",
    )
    result = analyze_project(tmp_path)
    assert result.snapshot is not None
    codes = {finding.code for finding in result.snapshot.findings}
    assert {"REQ011", "REQ013"} <= codes
