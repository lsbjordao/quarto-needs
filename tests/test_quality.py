from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from quarto_needs.config import load_config
from quarto_needs.diagnostics import Finding
from quarto_needs.metrics import CoverageMeasure, ScopeMetrics
from quarto_needs.quality import evaluate_gates, profile_exit_code


def make_config(document: str):
    directory = Path(tempfile.mkdtemp())
    (directory / ".quarto-needs.toml").write_text(document, encoding="utf-8")
    return load_config(directory)


def scope_with(denominator: int, coverage: dict[str, tuple[int, int]]) -> ScopeMetrics:
    return ScopeMetrics(
        name="catalog",
        denominator=denominator,
        breakdowns={},
        coverage={
            name: CoverageMeasure(covered, total)
            for name, (covered, total) in coverage.items()
        },
        gaps={},
    )


# --- gate evaluation -------------------------------------------------------------


def test_default_configuration_evaluates_only_max_errors() -> None:
    gates = load_config(Path("/nonexistent")).gates
    results = evaluate_gates(scopes={}, findings=(), gates=gates)
    assert [(gate.name, gate.passed) for gate in results] == [("max-errors", True)]


def test_error_count_gate_fails_on_structural_errors() -> None:
    gates = make_config("[gates]\nmax-errors = 0\n").gates
    results = evaluate_gates(
        scopes={},
        findings=(Finding("REQ004", "error", "duplicate id", "X"),),
        gates=gates,
    )
    assert [(gate.name, gate.passed) for gate in results] == [("max-errors", False)]


def test_error_count_gate_counts_only_errors() -> None:
    gates = make_config("[gates]\nmax-errors = 0\n").gates
    results = evaluate_gates(
        scopes={},
        findings=(
            Finding("REQ002", "warning", "no rationale", "X"),
            Finding("REQ014", "info", "orphan", "Y"),
        ),
        gates=gates,
    )
    assert [(gate.name, gate.passed) for gate in results] == [("max-errors", True)]


def test_percentage_gates_use_scope_and_denominators() -> None:
    config = make_config(
        '[gates]\nmin-implementation-effective = 90\nmin-verification-successful = 50\nscope = "catalog"\n'
    )
    scopes = {
        "catalog": scope_with(
            denominator=2,
            coverage={
                "implementation-effective": (1, 2),
                "verification-successful": (2, 2),
            },
        )
    }
    results = {
        gate.name: gate for gate in evaluate_gates(scopes=scopes, findings=(), gates=config.gates)
    }
    assert results["min-implementation-effective"].passed is False
    assert results["min-implementation-effective"].actual == 50.0
    assert results["min-implementation-effective"].threshold == 90.0
    assert results["min-verification-successful"].passed is True
    assert results["min-verification-successful"].denominator == 2


def test_missing_scope_gate_reports_unavailable() -> None:
    config = make_config('[gates]\nmin-evidence = 80\nscope = "approved-requirements"\n')
    results = evaluate_gates(scopes={}, findings=(), gates=config.gates)
    by_name = {gate.name: gate for gate in results}
    # A missing measurement is never a satisfied gate.
    assert (by_name["min-evidence"].passed, by_name["min-evidence"].actual) == (False, None)
    assert ("max-errors", True) == (by_name["max-errors"].name, by_name["max-errors"].passed)


def test_risk_mitigation_gate_uses_findings(tmp_path: Path) -> None:
    config = make_config(
        "[rules.REQ013]\nenabled = true\n[gates]\nrequire-risk-mitigation = true\n"
    )
    def gate_map(findings):
        return {
            gate.name: gate
            for gate in evaluate_gates(scopes={}, findings=findings, gates=config.gates, risk_population=1)
        }

    failing = gate_map((Finding("REQ013", "warning", "risk unmitigated", "R1"),))
    passing = gate_map(())
    assert failing["require-risk-mitigation"].passed is False
    assert passing["require-risk-mitigation"].passed is True


# --- profiles ---------------------------------------------------------------------


def test_profile_exit_codes() -> None:
    assert profile_exit_code("advisory", structural_errors=False, gate_failures=3) == 0
    assert profile_exit_code("default", structural_errors=True, gate_failures=0) == 1
    assert profile_exit_code("default", structural_errors=False, gate_failures=5) == 0
    assert profile_exit_code("strict", structural_errors=False, gate_failures=1) == 1
    assert profile_exit_code("strict", structural_errors=True, gate_failures=0) == 1


def test_invalid_profile_is_rejected_at_load(tmp_path: Path) -> None:
    from quarto_needs.config import ConfigurationError

    (tmp_path / ".quarto-needs.toml").write_text('profile = "yolo"\n', encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(tmp_path)


def test_quality_report_to_dict_shape(tmp_path: Path) -> None:
    """Smoke for the report builder on a tiny valid project."""
    from quarto_needs.quality import build_quality_report

    project = tmp_path / "proj"
    project.mkdir()
    (project / "page.qmd").write_text(
        "::: {.need #REQ-1 type=functional-requirement status=draft}\n## Req\n:::\n",
        encoding="utf-8",
    )
    report = build_quality_report(project)
    payload = report.to_dict()
    assert payload["profile"] == "default"
    assert payload["scopes"]["catalog"]["denominator"] == 1
    assert payload["findings"]["counts"]["total"] >= 0
    assert json.dumps(payload)
