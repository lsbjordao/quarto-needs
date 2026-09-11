"""Deterministic, GitHub-friendly CI summary exporter."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .. import diff as diff_module
from .. import impact as impact_module
from ..config import NeedsConfig
from ..export import _write_atomic_text
from ..quality import report_from_snapshot
from ..snapshot import AnalysisSnapshot

_NO_BASELINE = "No baseline was supplied; change classification is unavailable."


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return lines


def _changes(report: diff_module.DiffReport) -> list[str]:
    rows: list[tuple[object, ...]] = []
    rows.extend(("added", object_id, "") for object_id in report.added_objects)
    rows.extend(("removed", object_id, "") for object_id in report.removed_objects)
    rows.extend(
        ("modified", item["id"], ", ".join(item["fields"])) for item in report.modified
    )
    rows.extend(
        (
            "relocated",
            item["id"],
            f"{item['from'].get('file', 'unknown')} → {item['to'].get('file', 'unknown')}",
        )
        for item in report.relocated
    )
    rows.extend(
        ("relation added", item["source"], f"{item['authoredName']} → {item['target']}")
        for item in report.added_relations
    )
    rows.extend(
        ("relation removed", item["source"], f"{item['authoredName']} → {item['target']}")
        for item in report.removed_relations
    )
    return _table(("Change", "ID", "Details"), rows) if rows else ["No authored changes."]


def _coverage(report: diff_module.DiffReport) -> list[str]:
    rows = [
        (item["scope"], item["strength"], item["before"], item["after"])
        for item in report.metric_deltas
    ]
    if rows:
        return _table(("Scope", "Strength", "Before", "After"), rows)
    if "metrics" in report.suppressed:
        return ["Coverage deltas were suppressed because comparison axes differ."]
    return ["No coverage deltas."]


def _failed_gates(snapshot: AnalysisSnapshot, config: NeedsConfig) -> list[str]:
    report = report_from_snapshot(snapshot, config)
    failed = [gate for gate in report.gates if not gate.passed]
    rows = [(gate.name, gate.scope, gate.threshold, gate.actual) for gate in failed]
    lines = _table(("Gate", "Scope", "Threshold", "Actual"), rows) if rows else []
    lines.extend(
        f"[{gate.label}] {gate.name}: {gate.measurement_message}."
        for gate in report.gates if gate.measurement_status != "measured"
    )
    return lines or ["All gates passed."]


def _impact(report: impact_module.ImpactReport) -> list[str]:
    rows = [
        (
            item["id"],
            item["priority"],
            item["distance"],
            " → ".join(item["path"]),
        )
        for item in report.impacted
        if str(item.get("priority") or "").casefold() in {"high", "critical"}
    ]
    return _table(("ID", "Priority", "Distance", "Path"), rows) if rows else [
        "No high or critical impact."
    ]


def render(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    baseline: Mapping[str, object] | None = None,
) -> str:
    quality = report_from_snapshot(snapshot, config)
    diff_report = None
    impact_report = None
    if baseline is not None:
        diff_report = diff_module.compare(baseline, snapshot, config, recompute=True)
        impact_report = impact_module.analyze(baseline, snapshot, config, recompute=True)

    lines = ["# Quarto-Needs CI summary", "", "## Changes", ""]
    lines.extend(_changes(diff_report) if diff_report is not None else [_NO_BASELINE])
    lines.extend(["", "## Coverage deltas", ""])
    lines.extend(_coverage(diff_report) if diff_report is not None else [_NO_BASELINE])
    lines.extend(["", "## Failed gates", ""])
    lines.extend(_failed_gates(snapshot, config))
    lines.extend(["", "## High and critical impact", ""])
    lines.extend(_impact(impact_report) if impact_report is not None else [_NO_BASELINE])
    lines.extend(
        [
            "",
            "## Findings",
            "",
            (
                f"Errors: {quality.findings_by_severity.get('error', 0)}; "
                f"warnings: {quality.findings_by_severity.get('warning', 0)}."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write(
    path: Path,
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    baseline: Mapping[str, object] | None = None,
) -> Path:
    destination = Path(path)
    _write_atomic_text(destination, render(snapshot, config, baseline=baseline))
    return destination
