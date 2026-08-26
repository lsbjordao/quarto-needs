from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .export import coverage, export_graph, export_lua_index
from .graph import RequirementsGraph
from .parser import parse_project
from .validation import validate


def _root(value: str | None) -> Path:
    return Path(value or os.getcwd()).resolve()


def build(root: Path, quiet: bool = False) -> int:
    objects = parse_project(root)
    findings = validate(objects)
    export_graph(root / ".quarto-needs" / "needs.json", objects, findings)
    export_lua_index(root / "_extensions" / "quarto-needs" / "generated-index.lua", objects)
    if not quiet:
        c = coverage(objects)
        print(f"Quarto-Needs: {len(objects)} objects, {len(findings)} findings")
        print(f"Requirements: {c['requirements']} | implemented: {c['implementation_coverage']}% | verified: {c['verification_coverage']}%")
    return 1 if any(f.severity == "error" for f in findings) else 0


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
    objects = parse_project(root)
    findings = validate(objects)

    if args.command == "scan":
        return build(root)
    if args.command == "check":
        for f in findings:
            mark = "ERROR" if f.severity == "error" else "WARN"
            print(f"[{mark}] {f.code}: {f.message}")
        print(f"Checked {len(objects)} objects: {sum(f.severity == 'error' for f in findings)} errors, {sum(f.severity == 'warning' for f in findings)} warnings")
        return 1 if any(f.severity == "error" for f in findings) else 0
    if args.command == "coverage":
        print(json.dumps(coverage(objects), indent=2))
        return 0
    if args.command == "trace":
        graph = RequirementsGraph.build(objects)
        if args.id not in graph.objects:
            print(f"Unknown object: {args.id}", file=sys.stderr)
            return 2
        print("Upstream:")
        for item in sorted(graph.upstream(args.id)):
            print(f"  {item}")
        print("Downstream:")
        for item in sorted(graph.downstream(args.id)):
            print(f"  {item}")
        return 0
    if args.command == "export":
        export_graph(root / args.output, objects, findings)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
