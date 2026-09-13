from __future__ import annotations

from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config


ROOT = Path(__file__).resolve().parents[1]
BROKEN = ROOT / "examples" / "broken"


def _analyze(name: str):
    root = BROKEN / name
    return analyze_project(root, config=load_config(root))


def test_probable_relation_typo_warns_without_inventing_an_edge() -> None:
    result = _analyze("probable-relation-typo")

    assert result.snapshot is not None
    warnings = [finding for finding in result.findings if finding.code == "QND005"]
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.severity == "warning"
    assert warning.object_id == "REQ-A"
    assert "verifed-by" in warning.message
    assert "verified-by" in warning.message
    assert "creates no graph edge" in warning.message

    records = {item.id: item for item in result.snapshot.objects}
    assert records["REQ-A"].attributes["verifed-by"] == "TC-B"
    assert not result.snapshot.outgoing.get("REQ-A", ())


def test_relation_looking_custom_attribute_stays_outside_typo_warning_radius() -> None:
    result = _analyze("relation-typo")

    assert result.snapshot is not None
    assert not any(finding.code == "QND005" for finding in result.findings)
    records = {item.id: item for item in result.snapshot.objects}
    assert records["REQ-A"].attributes["linked-to"] == "REQ-B"
    assert not result.snapshot.outgoing.get("REQ-A", ())
