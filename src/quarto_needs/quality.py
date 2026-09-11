from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .analysis import analyze_project
from .config import Gates, NeedsConfig, load_config, reference_date, validate_gate_scope
from .rules import risk_mitigation_population, validate_gate_rule_dependencies
from .diagnostics import Finding
from .metrics import COVERAGE_STRENGTHS, CoverageMeasure, ScopeMetrics, compute_report_metrics
from .queries import materialize_queries


STRUCTURAL_CODES = frozenset({"QND001", "QND002", "REQ004", "REQ005", "REQ007"})

GATE_PERCENT_ATTRIBUTES = {
    # Gates field -> coverage strength; gate names render with dashes.
    "min_implementation_trace": "implementation-trace",
    "min_implementation_effective": "implementation-effective",
    "min_verification_trace": "verification-trace",
    "min_verification_successful": "verification-successful",
    "min_evidence": "evidence",
}


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    scope: str
    threshold: float | int | str | None
    actual: float | int | str | None
    denominator: int | None
    passed: bool
    measurement_status: str = "measured"

    @property
    def label(self) -> str:
        if self.measurement_status != "measured":
            return "WAIVED" if self.passed else "UNMEASURED"
        return "PASS" if self.passed else "FAIL"

    @property
    def measurement_message(self) -> str:
        if self.measurement_status == "empty":
            return "scope matched no objects eligible for measurement"
        if self.measurement_status == "unavailable":
            return "measurement is unavailable"
        return ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "scope": self.scope,
            "threshold": self.threshold,
            "actual": self.actual,
            "denominator": self.denominator,
            "passed": self.passed,
            "measurementStatus": self.measurement_status,
        }


@dataclass(frozen=True, slots=True)
class QualityReport:
    profile: str
    reference_date: str
    configuration_present: bool
    scopes: Mapping[str, ScopeMetrics]
    findings_by_severity: Mapping[str, int]
    findings_by_code: Mapping[str, int]
    gates: tuple[GateResult, ...]
    generator_name: str
    generator_version: str
    structural_errors: bool

    def gate_failures(self) -> int:
        return sum(1 for gate in self.gates if not gate.passed)

    def exit_code(self) -> int:
        return profile_exit_code(self.profile, self.structural_errors, self.gate_failures())

    def to_dict(self) -> dict[str, object]:
        by_severity = {
            severity: self.findings_by_severity.get(severity, 0)
            for severity in ("error", "warning", "info")
        }
        return {
            "schemaVersion": "1",
            "generator": {"name": self.generator_name, "version": self.generator_version},
            "profile": self.profile,
            "referenceDate": self.reference_date,
            "configurationPresent": self.configuration_present,
            "scopes": {name: self.scopes[name].to_dict() for name in sorted(self.scopes)},
            "findings": {
                "counts": {"total": sum(by_severity.values()), **by_severity},
                "byCode": {code: self.findings_by_code[code] for code in sorted(self.findings_by_code)},
            },
            "gates": [gate.to_dict() for gate in self.gates],
            "summary": {
                "structuralErrors": self.structural_errors,
                "gateFailures": self.gate_failures(),
                "exitCode": self.exit_code(),
            },
        }


def profile_exit_code(
    profile: str,
    structural_errors: bool,
    gate_failures: int,
) -> int:
    """Map the execution profile and outcomes to a stable CLI exit code."""
    if structural_errors:
        return 1  # every profile stops on structural failure
    if profile == "advisory":
        return 0  # semantic findings and failed gates stay visible but non-fatal
    if profile == "strict":
        return 1 if gate_failures else 0
    return 0  # default profile reports semantic gate failures without failing


def evaluate_gates(
    *,
    scopes: Mapping[str, ScopeMetrics],
    findings,
    gates: Gates,
    risk_population: int | None = None,
) -> tuple[GateResult, ...]:
    # None is unavailable; an empty findings sequence is a completed zero count.
    measured_findings = None if findings is None else tuple(findings)
    error_count = None if measured_findings is None else sum(
        item.severity == "error" for item in measured_findings
    )
    results = [GateResult(
        "max-errors", "project", gates.max_errors, error_count, None,
        error_count is not None and error_count <= gates.max_errors,
        "unavailable" if error_count is None else "measured",
    )]
    scope_entry = scopes.get(gates.scope)
    for attribute, strength in GATE_PERCENT_ATTRIBUTES.items():
        threshold = getattr(gates, attribute)
        if threshold is None:
            continue
        measure = None if scope_entry is None else scope_entry.coverage.get(strength)
        results.append(_population_gate(
            attribute.replace("_", "-"), gates.scope, threshold,
            None if measure is None else measure.percent,
            None if measure is None else measure.total,
            measure is not None and measure.percent >= threshold,
            gates.allow_empty_scopes,
        ))
    if gates.require_risk_mitigation:
        unmitigated = None if measured_findings is None else sum(
            item.code == "REQ013" for item in measured_findings
        )
        results.append(_population_gate(
            "require-risk-mitigation", "project", 0, unmitigated,
            risk_population if measured_findings is not None else None,
            unmitigated == 0, gates.allow_empty_scopes,
        ))
    return tuple(results)


def _population_gate(name, scope, threshold, actual, denominator, passed, allow_empty):
    status = "unavailable" if denominator is None else "empty" if denominator == 0 else "measured"
    if status != "measured":
        actual = None
        passed = status == "empty" and allow_empty
    return GateResult(name, scope, threshold, actual, denominator, passed, status)


def _counts(findings) -> tuple[dict[str, int], dict[str, int]]:
    by_severity: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for item in findings:
        by_severity[item.severity] = by_severity.get(item.severity, 0) + 1
        by_code[item.code] = by_code.get(item.code, 0) + 1
    return by_severity, by_code


def _invalid_report(result, config: NeedsConfig) -> QualityReport:
    import quarto_needs

    by_severity, by_code = _counts(result.findings)
    return QualityReport(
        profile=config.profile,
        reference_date=reference_date().isoformat(),
        configuration_present=config.present,
        scopes={},
        findings_by_severity=by_severity,
        findings_by_code=by_code,
        gates=(
            GateResult(
                name="structural-analysis",
                scope="project",
                threshold="valid graph",
                actual="invalid graph",
                denominator=None,
                passed=False,
            ),
        ),
        generator_name="quarto-needs",
        generator_version=quarto_needs.__version__,
        structural_errors=True,
    )


def report_from_snapshot(
    snapshot,
    config: NeedsConfig,
    queries: Mapping[str, Sequence[str]] | None = None,
) -> QualityReport:
    """Build the report from an existing snapshot, without re-analyzing.

    Callers that already hold a snapshot (and often its materialized queries)
    use this so one command still means exactly one analysis pass.
    """
    validate_gate_rule_dependencies(config)
    validate_gate_scope(config)
    resolved = dict(queries) if queries is not None else dict(materialize_queries(config, snapshot))
    metrics = compute_report_metrics(snapshot, config, scope_ids=resolved)
    gates_results = evaluate_gates(
        scopes=metrics.scopes, findings=snapshot.findings, gates=config.gates,
        risk_population=len(risk_mitigation_population(snapshot, config))
    )
    by_severity, by_code = _counts(snapshot.findings)
    return QualityReport(
        profile=config.profile,
        reference_date=reference_date().isoformat(),
        configuration_present=config.present,
        scopes=metrics.scopes,
        findings_by_severity=by_severity,
        findings_by_code=by_code,
        gates=gates_results,
        generator_name=snapshot.generator_name,
        generator_version=snapshot.generator_version,
        structural_errors=any(code in STRUCTURAL_CODES for code in by_code),
    )


def build_quality_report(
    root: Path,
    config: NeedsConfig | None = None,
) -> QualityReport:
    effective_config = config if config is not None else load_config(root)
    validate_gate_rule_dependencies(effective_config)
    validate_gate_scope(effective_config)
    result = analyze_project(root, config=effective_config)
    snapshot = result.snapshot
    if snapshot is None:
        return _invalid_report(result, effective_config)

    queries = materialize_queries(effective_config, snapshot)
    metrics = compute_report_metrics(snapshot, effective_config, scope_ids=dict(queries))
    gates_results = evaluate_gates(
        scopes=metrics.scopes, findings=snapshot.findings, gates=effective_config.gates,
        risk_population=len(risk_mitigation_population(snapshot, effective_config))
    )
    by_severity, by_code = _counts(snapshot.findings)
    return QualityReport(
        profile=effective_config.profile,
        reference_date=reference_date().isoformat(),
        configuration_present=effective_config.present,
        scopes=metrics.scopes,
        findings_by_severity=by_severity,
        findings_by_code=by_code,
        gates=gates_results,
        generator_name=snapshot.generator_name,
        generator_version=snapshot.generator_version,
        structural_errors=any(code in STRUCTURAL_CODES for code in by_code),
    )


# Re-exported for consumers building custom reports.
__all__ = [
    "COVERAGE_STRENGTHS",
    "CoverageMeasure",
    "GateResult",
    "QualityReport",
    "build_quality_report",
    "report_from_snapshot",
    "evaluate_gates",
    "profile_exit_code",
]
