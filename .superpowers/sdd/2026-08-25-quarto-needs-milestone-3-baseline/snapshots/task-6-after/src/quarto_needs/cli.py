from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque
from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

from .analysis import analyze_project
from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline
from .config import NeedsConfig, load_config
from .diagnostics import Finding
from .export import _write_atomic_text, write_build_outputs, write_v1_graph
from .metrics import render_measure
from .queries import materialize_queries
from .quality import QualityReport, build_quality_report, report_from_snapshot
from .snapshot import AnalysisSnapshot


class ConfigurationFailure(Exception):
    """Raised when `.quarto-needs.toml` cannot be used."""


def _root(value: str | None) -> Path:
    return Path(value or os.getcwd()).resolve()


def print_findings(findings: Iterable[Finding], stream: TextIO) -> None:
    for finding in findings:
        mark = "ERROR" if finding.severity == "error" else "WARN"
        print(f"[{mark}] {finding.code}: {finding.message}", file=stream)


def _reachable(
    snapshot: AnalysisSnapshot, start: str, direction: str
) -> list[str]:
    seen: set[str] = set()
    queue = deque([start])
    while queue:
        current = queue.popleft()
        relations = (
            snapshot.outgoing.get(current, ())
            if direction == "downstream"
            else snapshot.incoming.get(current, ())
        )
        for relation in relations:
            candidate = (
                relation.target
                if direction == "downstream"
                else relation.source
            )
            if candidate not in seen and candidate != start:
                seen.add(candidate)
                queue.append(candidate)
    return sorted(seen, key=lambda item: (item.casefold(), item))


def build(root: Path, quiet: bool = False) -> int:
    try:
        config = load_config(root)
    except ValueError as error:
        if not quiet:
            print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    result = analyze_project(root, config=config)
    if result.snapshot is None:
        if not quiet:
            print_findings(result.findings, stream=sys.stderr)
        return 1
    queries = materialize_queries(config, result.snapshot)
    # The Lua dashboard reads only what Python projects here, so a configured
    # project ships its materialized queries and its precomputed report.
    extra_extensions = (
        {
            "quartoNeeds": {
                "queries": {name: list(queries[name]) for name in sorted(queries)},
                "report": report_from_snapshot(
                    result.snapshot, config, queries=queries
                ).to_dict(),
            }
        }
        if config.present
        else None
    )
    write_build_outputs(
        root / ".quarto-needs" / "needs.json",
        root / "_extensions" / "quarto-needs" / "generated-index.lua",
        result.snapshot,
        extra_extensions=extra_extensions,
    )
    if not quiet:
        metrics = result.snapshot.metrics
        print(
            f"Quarto-Needs: {len(result.snapshot.objects)} objects, "
            f"{len(result.findings)} findings"
        )
        print(
            f"Requirements: {metrics['requirements']} | "
            f"implemented: {metrics['implementation_coverage']}% | "
            f"verified: {metrics['verification_coverage']}%"
        )
    return 1 if any(f.severity == "error" for f in result.findings) else 0


def _print_quality_text(report: QualityReport) -> None:
    print(
        f"Quarto-Needs quality report (profile={report.profile}, "
        f"reference date={report.reference_date})"
    )
    for name in sorted(report.scopes):
        entry = report.scopes[name]
        print(f"Scope {name}: {entry.denominator} requirements")
        for strength in (
            "implementation-trace",
            "implementation-effective",
            "verification-trace",
            "verification-successful",
            "evidence",
        ):
            measure = entry.coverage[strength]
            print(f"  {strength}: {render_measure(measure)}")
        for gap_name, ids in sorted(entry.gaps.items()):
            if ids:
                print(f"  gaps {gap_name}: {', '.join(ids)}")
    counts = report.findings_by_severity
    print(
        f"Findings: {counts.get('error', 0)} errors, "
        f"{counts.get('warning', 0)} warnings, {counts.get('info', 0)} infos"
    )
    for gate in report.gates:
        mark = "PASS" if gate.passed else "FAIL"
        line = f"[{mark}] {gate.name}"
        details = []
        if gate.actual is not None:
            details.append(f"actual {gate.actual}")
        if gate.threshold is not None:
            details.append(f"threshold {gate.threshold}")
        if gate.denominator is not None:
            details.append(f"denominator {gate.denominator}")
        if gate.scope != "project":
            details.append(f"scope {gate.scope}")
        if details:
            line += " (" + ", ".join(details) + ")"
        print(line)


def _query(root: Path, args: argparse.Namespace, config: NeedsConfig | None) -> int:
    effective = config if config is not None else load_config(root)
    result = analyze_project(root, config=effective)
    if result.snapshot is None:
        print_findings(result.findings, stream=sys.stderr)
        return 1
    queries = materialize_queries(effective, result.snapshot)
    name = args.name
    if name not in queries:
        available = ", ".join(sorted(queries))
        print(f"Unknown query: {name} (available: {available})", file=sys.stderr)
        return 2
    ids = list(queries[name])
    if args.format == "json":
        print(json.dumps({"name": name, "ids": ids}, indent=2))
    else:
        for object_id in ids:
            print(object_id)
    return 0


def _quality(root: Path, args: argparse.Namespace, config: NeedsConfig | None) -> int:
    effective = config if config is not None else load_config(root)
    report = build_quality_report(root, config=effective)
    payload = report.to_dict()
    output_path = getattr(args, "output", None)
    if output_path:
        try:
            _write_atomic_text(root / output_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        except OSError as error:
            print(f"Could not write quality report: {error}", file=sys.stderr)
            return 3
    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_quality_text(report)
    return report.exit_code()


def _baseline_destination(root: Path, output: str) -> Path:
    candidate = Path(output)
    return candidate if candidate.is_absolute() else root / candidate


def _baseline_create(root: Path, args, config: NeedsConfig) -> int:
    result = analyze_project(root, config=config)
    if result.snapshot is None:
        print_findings(result.findings, stream=sys.stderr)
        if not args.allow_invalid:
            return 1
        payload = build_invalid_baseline(result, config)
    else:
        payload = build_baseline(
            result.snapshot, config, queries=materialize_queries(config, result.snapshot)
        )
    destination = _baseline_destination(root, args.output)
    try:
        write_baseline(destination, payload, force=args.force)
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Could not write baseline: {error}", file=sys.stderr)
        return 3
    if args.format == "json":
        print(json.dumps({"path": str(destination), "valid": payload["valid"]}, indent=2, sort_keys=True))
    else:
        state = "valid" if payload["valid"] else "diagnostic (valid: false)"
        print(f"Wrote {state} baseline to {destination}")
    return 0


def _baseline_summary(payload: dict[str, object]) -> dict[str, object]:
    return {
        "valid": payload["valid"],
        "referenceDate": payload["referenceDate"],
        "configurationFingerprint": payload["configurationFingerprint"],
        "semanticGraphFingerprint": payload.get("semanticGraphFingerprint"),
        "objects": len(payload.get("objects", payload.get("declarations", []))),
        "relations": len(payload.get("relations", [])),
        "findings": len(payload.get("findings", [])),
    }


def _baseline_inspect(args) -> int:
    try:
        payload = load_baseline(Path(args.baseline))
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    summary = _baseline_summary(payload)
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    print(f"Baseline {args.baseline}")
    print(f"  valid: {summary['valid']}")
    print(f"  reference date: {summary['referenceDate']}")
    print(f"  objects: {summary['objects']}")
    print(f"  relations: {summary['relations']}")
    print(f"  findings: {summary['findings']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quarto-needs", description="Requirements-as-code engine for Quarto")
    parser.add_argument("--root", help="Project root (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="Parse project and write .quarto-needs/needs.json")
    sub.add_parser("check", help="Validate the requirements graph")
    sub.add_parser("coverage", help="Print coverage metrics")
    trace = sub.add_parser("trace", help="Show upstream/downstream traceability")
    trace.add_argument("id")
    export = sub.add_parser("export", help="Export canonical graph JSON")
    export.add_argument("--output", default=".quarto-needs/needs.json")
    quality = sub.add_parser(
        "quality", help="Evaluate scoped metrics, findings, and configured gates"
    )
    quality.add_argument("--format", choices=("text", "json"), default="text")
    quality.add_argument("--output", help="Write the JSON report atomically to this path")
    query = sub.add_parser("query", help="Evaluate a named query and print its ordered IDs")
    query.add_argument("name")
    query.add_argument("--format", choices=("text", "json"), default="text")
    baseline_parser = sub.add_parser("baseline", help="Create or inspect a canonical baseline")
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_command", required=True)
    baseline_create = baseline_sub.add_parser("create", help="Write a baseline for the current graph")
    baseline_create.add_argument("--output", default=str(DEFAULT_BASELINE_PATH))
    baseline_create.add_argument("--force", action="store_true", help="Overwrite an existing baseline")
    baseline_create.add_argument(
        "--allow-invalid",
        action="store_true",
        help="Write a diagnostic artifact for a structurally invalid project",
    )
    baseline_create.add_argument("--format", choices=("text", "json"), default="text")
    baseline_inspect = baseline_sub.add_parser("inspect", help="Summarize an existing baseline")
    baseline_inspect.add_argument("baseline")
    baseline_inspect.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    root = _root(args.root)

    if args.command == "scan":
        return build(root)

    try:
        config: NeedsConfig | None = load_config(root)
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    if args.command == "quality":
        return _quality(root, args, config)
    if args.command == "query":
        return _query(root, args, config)
    if args.command == "baseline":
        if args.baseline_command == "inspect":
            return _baseline_inspect(args)
        return _baseline_create(root, args, config)
    result = analyze_project(root, config=config)
    if args.command == "check":
        print_findings(result.findings, stream=sys.stdout)
        print(
            f"Checked {len(result.declarations)} objects: "
            f"{sum(f.severity == 'error' for f in result.findings)} errors, "
            f"{sum(f.severity == 'warning' for f in result.findings)} warnings"
        )
        return 1 if any(f.severity == "error" for f in result.findings) else 0
    if result.snapshot is None:
        print_findings(result.findings, stream=sys.stderr)
        return 1
    if args.command == "coverage":
        metrics = result.snapshot.metrics
        projection = {
            "requirements": metrics["requirements"],
            "approved": metrics["approved"],
            "implemented": metrics["implemented"],
            "verified": metrics["verified"],
            "implementation_coverage": metrics["implementation_coverage"],
            "verification_coverage": metrics["verification_coverage"],
        }
        print(json.dumps(projection, indent=2))
        return 0
    if args.command == "trace":
        if args.id not in result.snapshot.objects_by_id:
            print(f"Unknown object: {args.id}", file=sys.stderr)
            return 2
        print("Upstream:")
        for item in _reachable(result.snapshot, args.id, "upstream"):
            print(f"  {item}")
        print("Downstream:")
        for item in _reachable(result.snapshot, args.id, "downstream"):
            print(f"  {item}")
        return 0
    if args.command == "export":
        write_v1_graph(root / args.output, result.snapshot)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
