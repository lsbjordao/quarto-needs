from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_objects
from quarto_needs.config import load_config
from quarto_needs.metrics import compute_report_metrics
from quarto_needs.model import EngineeringObject, Relation

ROOT = Path(__file__).resolve().parents[1]


def snapshot_with(*objects: EngineeringObject):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None, [f.to_dict() for f in result.findings]
    return result.snapshot


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


def config_from(tmp_path: Path, document: str):
    (tmp_path / ".quarto-needs.toml").write_text(document, encoding="utf-8")
    return load_config(tmp_path)


def default_config():
    return load_config(Path("/nonexistent-quarto-needs-root"))


def scope(metrics, name):
    return metrics.scopes[name]


# --- strength separation ------------------------------------------------------


def test_trace_and_effective_implementation_differ_on_endpoint_status(tmp_path: Path) -> None:
    config = config_from(tmp_path, "")
    snapshot = snapshot_with(
        obj("R-OK", status="approved", relations=[Relation("implemented-by", "R-OK", "GOOD")]),
        obj("R-BAD", status="approved", relations=[Relation("implemented-by", "R-BAD", "REJ")]),
        obj("R-NONE", status="approved"),
        obj("GOOD", type="component", status="implemented"),
        obj("REJ", type="component", status="rejected"),
    )
    entry = scope(compute_report_metrics(snapshot, config), "catalog")
    coverage = {name: (m.covered, m.total) for name, m in entry.coverage.items()}
    assert coverage["implementation-trace"] == (2, 3)
    assert coverage["implementation-effective"] == (1, 3)
    assert entry.gaps["implementation-effective"] == ("R-BAD", "R-NONE")


def test_verification_strengths_require_successful_status(tmp_path: Path) -> None:
    config = config_from(tmp_path, "")
    snapshot = snapshot_with(
        obj("R-PASS", status="approved", relations=[Relation("verified-by", "R-PASS", "T-PASS")]),
        obj("R-FAIL", status="approved", relations=[Relation("verified-by", "R-FAIL", "T-FAIL")]),
        obj("T-PASS", type="test-case", status="passed"),
        obj("T-FAIL", type="test-case", status="failed"),
    )
    entry = scope(compute_report_metrics(snapshot, config), "catalog")
    coverage = {name: (m.covered, m.total) for name, m in entry.coverage.items()}
    assert coverage["verification-trace"] == (2, 2)
    assert coverage["verification-successful"] == (1, 2)


def test_evidence_requires_valid_non_expired_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")  # 2025-01-01 UTC
    config = config_from(tmp_path, "")
    snapshot = snapshot_with(
        obj("R-GOOD", status="approved", relations=[Relation("verified-by", "R-GOOD", "T1")]),
        obj("R-STALE", status="approved", relations=[Relation("verified-by", "R-STALE", "T2")]),
        obj("R-NONE", status="approved", relations=[Relation("verified-by", "R-NONE", "T3")]),
        obj("T1", type="test-case", status="passed", relations=[Relation("evidenced-by", "T1", "E1")]),
        obj("T2", type="test-case", status="passed", relations=[Relation("evidenced-by", "T2", "E2")]),
        obj("T3", type="test-case", status="passed"),
        obj("E1", type="evidence", status="approved"),
        obj("E2", type="evidence", attributes={"expires": "2024-12-31"}),
    )
    entry = scope(compute_report_metrics(snapshot, config), "catalog")
    evidence = entry.coverage["evidence"]
    assert (evidence.covered, evidence.total) == (1, 3)
    assert entry.gaps["evidence"] == ("R-NONE", "R-STALE")


def test_custom_successful_statuses_and_expiry_attribute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    config = config_from(
        tmp_path,
        '[governance]\nsuccessful-test-statuses = ["passed", "approved"]\nexpiry-attribute = ""\n',
    )
    snapshot = snapshot_with(
        obj("R-A", status="approved", relations=[Relation("validated-by", "R-A", "T1")]),
        obj("T1", type="test-case", status="approved", relations=[Relation("evidenced-by", "T1", "E1")]),
        obj("E1", type="evidence", attributes={"expires": "2020-01-01"}),
    )
    entry = scope(compute_report_metrics(snapshot, config), "catalog")
    assert entry.coverage["verification-successful"].covered == 1
    # expiry checks disabled via empty attribute: stale date still counts
    assert entry.coverage["evidence"].covered == 1


# --- scopes and denominators ---------------------------------------------------


def test_approved_scope_uses_default_named_query_ids() -> None:
    config = default_config()
    snapshot = snapshot_with(
        obj("R-APP", status="approved"),
        obj("R-DRAFT"),
        obj("N-APP", type="stakeholder-need", status="approved"),
    )
    metrics = compute_report_metrics(
        snapshot,
        config,
        scope_ids={"approved-requirements": ("R-APP",)},
    )
    catalog = scope(metrics, "catalog")
    approved = scope(metrics, "approved-requirements")
    assert catalog.denominator == 2
    assert approved.denominator == 1
    assert approved.breakdowns["status"] == {"approved": 1}
    assert "stakeholder-need" not in approved.breakdowns["type"]


def test_empty_denominator_reports_full_percent() -> None:
    config = default_config()
    snapshot = snapshot_with(obj("TC", type="test-case", status="passed"))
    entry = scope(compute_report_metrics(snapshot, config), "catalog")
    assert entry.denominator == 0
    assert entry.coverage["implementation-trace"].percent == 100.0


def test_breakdowns_are_complete_and_deterministic() -> None:
    config = default_config()
    snapshot = snapshot_with(
        obj("R-B", attributes={"priority": "high"}),
        obj("R-A", status="approved", attributes={"priority": "HIGH"}),
        obj("R-C"),
    )
    entry = scope(compute_report_metrics(snapshot, config), "catalog")
    assert list(entry.breakdowns["type"]) == sorted(entry.breakdowns["type"])
    assert entry.breakdowns["priority"]["high"] == 2
    assert entry.breakdowns["priority"]["unspecified"] == 1
    assert entry.breakdowns["status"]["draft"] == 2
    assert entry.breakdowns["status"]["approved"] == 1


def test_gap_ids_are_sorted_casefolded() -> None:
    config = default_config()
    snapshot = snapshot_with(
        obj("r-low", status="approved"),
        obj("R-UP", status="approved"),
    )
    entry = scope(compute_report_metrics(snapshot, config), "catalog")
    assert entry.gaps["implementation-effective"] == ("r-low", "R-UP")


def test_to_dict_is_plain_and_json_serializable() -> None:
    import json

    config = default_config()
    snapshot = snapshot_with(obj("R-1", status="approved"))
    payload = compute_report_metrics(snapshot, config).to_dict()
    encoded = json.dumps(payload, sort_keys=True)
    assert json.loads(encoded)["scopes"]["catalog"]["denominator"] == 1
    measure = payload["scopes"]["catalog"]["coverage"]["verification-trace"]
    assert set(measure) == {"covered", "total", "percent"}
