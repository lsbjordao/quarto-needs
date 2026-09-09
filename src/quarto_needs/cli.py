from __future__ import annotations

import argparse
import json
import os
import sys
from collections import deque
from pathlib import Path

from . import __version__

from . import diff as diff_module
from . import evidence as evidence_module
from . import impact as impact_module
from .analysis import analyze_project
from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline
from .config import NeedsConfig, load_config
from .diagnostics import print_findings
from .export import _write_atomic_text, write_build_outputs, write_v1_graph
from .exporters import csv_export, junit_export, markdown_export, sarif_export
from .metrics import render_measure
from .queries import materialize_queries
from .quality import QualityReport, build_quality_report, profile_exit_code, report_from_snapshot
from .snapshot import AnalysisSnapshot


class ConfigurationFailure(Exception):
    """Raised when `.quarto-needs.toml` cannot be used."""


def _root(value: str | None) -> Path:
    return Path(value or os.getcwd()).resolve()


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
    """Run the canonical Quarto pre-render build.

    The implementation lives in `quarto_integration` because the extension
    bootstrap calls it too; `scan` and the extension must be the same
    operation, not two that agree today. This wrapper stays because it is
    the established name for callers inside and outside the repository.
    """
    from .quarto_integration import run_quarto_pre_render

    return run_quarto_pre_render(root, quiet=quiet)


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


def _evidence_check(root: Path, args: argparse.Namespace, config: NeedsConfig) -> int:
    artifact = Path(args.artifact)
    if not artifact.is_absolute():
        artifact = root / artifact
    try:
        payload = evidence_module.load_pytest_evidence(artifact)
    except ValueError as error:
        print(f"Evidence error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Could not read evidence artifact {artifact}: {error}", file=sys.stderr)
        return 3

    result = analyze_project(root, config=config)
    if result.snapshot is None:
        print_findings(result.findings, stream=sys.stderr)
        return 1

    issues = evidence_module.validate_pytest_evidence(result.snapshot, payload)
    projection = {
        "artifact": str(artifact),
        "provider": payload["provider"],
        "tests": len(payload["tests"]),
        "valid": not issues,
        "issues": [issue.to_dict() for issue in issues],
    }
    if args.format == "json":
        print(json.dumps(projection, indent=2, sort_keys=True))
    else:
        if issues:
            print(f"Evidence check failed: {len(issues)} issue(s)")
            for issue in issues:
                scope = ""
                if issue.object_id:
                    scope += f" {issue.object_id}"
                if issue.nodeid:
                    scope += f" [{issue.nodeid}]"
                print(f"[{issue.code}]{scope}: {issue.message}")
        else:
            print(
                f"Evidence check passed: {len(payload['tests'])} linked pytest test(s) "
                f"from {artifact} agree with the current engineering graph"
            )
    return 1 if issues else 0


def _baseline_destination(root: Path, output: str) -> Path:
    candidate = Path(output)
    return candidate if candidate.is_absolute() else root / candidate


def _baseline_create(root: Path, args, config: NeedsConfig) -> int:
    try:
        result = analyze_project(root, config=config)
    except OSError as error:
        # Reading the project failed; operational, not validation, failure.
        print(f"Could not scan {root}: {error}", file=sys.stderr)
        return 3
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
    try:
        summary = _baseline_summary(payload)
    except KeyError as error:
        # A tampered artifact can declare schemaVersion "1" yet omit required
        # keys; load_baseline does not schema-validate, so this is the last
        # line of defense before a raw traceback.
        print(f"{args.baseline} is missing required key {error}; it is not a trustworthy baseline", file=sys.stderr)
        return 2
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


def _print_diff_text(report) -> None:
    for notice in report.notices:
        print(f"[notice] {notice}: derived deltas suppressed; both sides must share configuration and reference date to compare them")
    if report.is_empty():
        if report.suppressed:
            # Plain "No changes." would claim every category matched,
            # including the ones this run never compared at all.
            print(
                "No changes in the compared categories "
                f"({', '.join(report.suppressed)} not compared)."
            )
        else:
            print("No changes.")
        return
    for object_id in report.added_objects:
        print(f"+ object {object_id}")
    for object_id in report.removed_objects:
        print(f"- object {object_id}")
    for item in report.modified:
        print(f"~ object {item['id']} ({', '.join(item['fields'])})")
    for item in report.relocated:
        print(f"> object {item['id']} moved {item['from'].get('file')} -> {item['to'].get('file')}")
    for item in report.added_relations:
        print(f"+ relation {item['source']} {item['authoredName']} {item['target']}")
    for item in report.removed_relations:
        print(f"- relation {item['source']} {item['authoredName']} {item['target']}")
    for item in report.representation_changes:
        print(f"= relation {item['source']} -> {item['target']} respelled {item['from']} -> {item['to']}")
    for item in report.findings_added:
        print(f"+ finding {item['code']} {item['object_id'] or ''}".rstrip())
    for item in report.findings_removed:
        print(f"- finding {item['code']} {item['object_id'] or ''}".rstrip())
    for item in report.metric_deltas:
        print(f"~ metric {item['scope']}/{item['strength']} {item['before']} -> {item['after']}")
    for item in report.gate_regressions:
        print(f"! gate {item['name']} failed (threshold {item['threshold']}, actual {item['actual']})")


def _diff(root: Path, args, config: NeedsConfig) -> int:
    try:
        baseline_payload = load_baseline(Path(args.baseline))
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    try:
        result = analyze_project(root, config=config)
    except OSError as error:
        # Reading the project failed; operational, not validation, failure.
        print(f"Could not scan {root}: {error}", file=sys.stderr)
        return 3
    if result.snapshot is None:
        print_findings(result.findings, stream=sys.stderr)
        return 1
    try:
        report = diff_module.compare(
            baseline_payload,
            result.snapshot,
            config,
            recompute=args.recompute_with == "current",
        )
    except diff_module.DiffError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        _print_diff_text(report)
    return profile_exit_code(config.profile, False, len(report.gate_regressions))


def _impact(root: Path, args, config: NeedsConfig) -> int:
    try:
        baseline_payload = load_baseline(Path(args.baseline))
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    try:
        result = analyze_project(root, config=config)
    except OSError as error:
        # Reading the project failed; operational, not validation, failure.
        print(f"Could not scan {root}: {error}", file=sys.stderr)
        return 3
    if result.snapshot is None:
        print_findings(result.findings, stream=sys.stderr)
        return 1
    try:
        report = impact_module.analyze(
            baseline_payload,
            result.snapshot,
            config,
            recompute=args.recompute_with == "current",
        )
    except impact_module.ImpactError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0
    if not report.origins:
        print("No changes to propagate.")
        return 0
    for origin in report.origins:
        print(f"origin {origin['id']} ({origin['change']})")
    for item in report.impacted:
        print(
            f"  {item['classification']} d={item['distance']} {item['id']}"
            f" via {' -> '.join(item['path'])}"
            f" [{', '.join(item['relations'])}]"
        )
    return 0


def _export(root: Path, args: argparse.Namespace, config: NeedsConfig | None) -> int:
    effective = config if config is not None else load_config(root)
    if args.baseline is not None and args.format != "markdown":
        # Usage errors are reported before any analysis runs.
        print(
            "usage error: --baseline is only valid with --format markdown "
            f"(got --format {args.format})",
            file=sys.stderr,
        )
        return 2
    baseline_payload = None
    if args.baseline is not None:
        try:
            baseline_payload = load_baseline(Path(args.baseline))
        except BaselineError as error:
            print(str(error), file=sys.stderr)
            return 2
    result = analyze_project(root, config=effective)
    # SARIF is findings-driven: it exports even when a structural failure
    # left the snapshot None; json/csv still require the snapshot itself.
    if result.snapshot is None and args.format != "sarif":
        print_findings(result.findings, stream=sys.stderr)
        return 1
    report = (
        report_from_snapshot(result.snapshot, effective)
        if result.snapshot is not None
        else None
    )
    output = root / args.output
    try:
        if args.format == "json":
            # Byte-identity with the pre-task v1 projection holds by
            # construction: the default format keeps the existing writer.
            write_v1_graph(output, result.snapshot)
        elif args.format == "csv":
            # The csv format's --output names a directory (created on
            # demand) receiving objects/relations/findings.csv, each
            # written atomically through export._write_atomic_text.
            csv_export.write_all(output, result.snapshot)
        elif args.format == "sarif":
            # Single-file findings export written atomically; a structurally
            # invalid project still produces its artifact, then fails policy.
            sarif_export.write(output, result.findings)
        elif args.format == "junit":
            if report is None:
                print("JUnit export requires a valid snapshot.", file=sys.stderr)
                return 1
            junit_export.write(output, report)
        else:
            if args.format != "markdown" or result.snapshot is None:
                print("Markdown export requires a valid snapshot.", file=sys.stderr)
                return 1
            markdown_export.write(
                output,
                result.snapshot,
                effective,
                baseline=baseline_payload,
            )
    except (diff_module.DiffError, impact_module.ImpactError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Could not write {output}: {error}", file=sys.stderr)
        return 3
    if result.snapshot is None:
        # The SARIF artifact is on disk; the structural findings still fail.
        print_findings(result.findings, stream=sys.stderr)
        return 1
    # The artifact is on disk before the policy verdict leaves the process.
    assert report is not None
    return profile_exit_code(effective.profile, False, report.gate_failures())


# Commands intercepted by cli_entry before argparse ever runs. They are not
# subparsers here, so `--help` would otherwise present this argparse group as
# the whole CLI and hide half of it. Listing them keeps the entry point's help
# honest without moving dispatch into argparse.
DISPATCHED_COMMAND_HELP = """
commands handled by the outer dispatch layer:
  suspect --git BASE..HEAD
                        Traceability claims needing review after a change
  pr-report --git BASE..HEAD
                        Combined change/impact/suspect review report
  github-report --git BASE..HEAD
                        Summary, annotations, and check projection for GitHub
  diff|impact --git BASE..HEAD
                        Compare two committed Git states instead of a baseline
  variant list|show NAME
                        Inspect configured build variants
  export --format reqif|jsonld
                        ReqIF 1.2 and JSON-LD interchange projections
  migrate SOURCE        Migration plans for sphinx-needs, doorstop, strictdoc,
                        openfasttrace
  oslc discover|catalog|query
                        Bounded read-only OSLC RM federation
  lsp                   Run the language server over stdio

`oslc` and `migrate` subcommands accept their own --help. The complete
reference for every command above is the CLI reference chapter of the manual.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quarto-needs",
        description="Requirements-as-code engine for Quarto",
        epilog=DISPATCHED_COMMAND_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", help="Project root (default: current directory)")
    parser.add_argument("--version", action="version", version=f"quarto-needs {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan", help="Parse project and write .quarto-needs/needs.json")
    sub.add_parser("check", help="Validate the requirements graph")
    sub.add_parser("coverage", help="Print coverage metrics")
    trace = sub.add_parser("trace", help="Show upstream/downstream traceability")
    trace.add_argument("id")
    export = sub.add_parser("export", help="Export canonical graph JSON")
    export.add_argument("--output", default=".quarto-needs/needs.json")
    export.add_argument("--format", choices=("json", "csv", "sarif", "junit", "markdown"), default="json")
    export.add_argument("--baseline", help="Baseline for the Markdown change summary (markdown format only)")
    quality = sub.add_parser(
        "quality", help="Evaluate scoped metrics, findings, and configured gates"
    )
    quality.add_argument("--format", choices=("text", "json"), default="text")
    quality.add_argument("--output", help="Write the JSON report atomically to this path")
    query = sub.add_parser("query", help="Evaluate a named query and print its ordered IDs")
    query.add_argument("name")
    query.add_argument("--format", choices=("text", "json"), default="text")
    evidence = sub.add_parser("evidence", help="Validate machine evidence against the engineering graph")
    evidence_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_check = evidence_sub.add_parser("check", help="Check a pytest evidence artifact against the current graph")
    evidence_check.add_argument("artifact")
    evidence_check.add_argument("--format", choices=("text", "json"), default="text")
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
    diff_parser = sub.add_parser("diff", help="Compare a baseline against the current graph")
    diff_parser.add_argument("baseline")
    diff_parser.add_argument("--format", choices=("text", "json"), default="text")
    diff_parser.add_argument(
        "--recompute-with",
        choices=("current",),
        dest="recompute_with",
        help="Re-resolve the baseline's relations under the current configuration and reference date",
    )
    impact_parser = sub.add_parser("impact", help="Explain what a baseline's changes reach")
    impact_parser.add_argument("baseline")
    impact_parser.add_argument("--format", choices=("text", "json"), default="text")
    impact_parser.add_argument(
        "--recompute-with",
        choices=("current",),
        dest="recompute_with",
        help="Re-resolve the baseline's relations under the current configuration and reference date",
    )
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
    if args.command == "evidence":
        return _evidence_check(root, args, config)
    if args.command == "baseline":
        if args.baseline_command == "inspect":
            return _baseline_inspect(args)
        return _baseline_create(root, args, config)
    if args.command == "diff":
        return _diff(root, args, config)
    if args.command == "impact":
        return _impact(root, args, config)
    if args.command == "export":
        return _export(root, args, config)
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
