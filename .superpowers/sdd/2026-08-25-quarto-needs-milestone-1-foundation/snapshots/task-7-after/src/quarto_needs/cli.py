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
from .diagnostics import Finding
from .export import write_build_outputs, write_v1_graph
from .snapshot import AnalysisSnapshot


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
    result = analyze_project(root)
    if result.snapshot is None:
        if not quiet:
            print_findings(result.findings, stream=sys.stderr)
        return 1
    write_build_outputs(
        root / ".quarto-needs" / "needs.json",
        root / "_extensions" / "quarto-needs" / "generated-index.lua",
        result.snapshot,
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
    args = parser.parse_args(argv)
    root = _root(args.root)

    if args.command == "scan":
        return build(root)
    result = analyze_project(root)
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
