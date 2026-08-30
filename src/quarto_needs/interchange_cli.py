from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .analysis import analyze_project
from .config import load_config
from .exporters import reqif_export


def interchange_action(argv: Sequence[str]) -> str | None:
    """Return an interchange format handled outside the legacy export parser."""
    values = list(argv)
    try:
        export_index = values.index("export")
    except ValueError:
        return None

    tail = values[export_index + 1 :]
    try:
        format_index = tail.index("--format")
    except ValueError:
        return None
    if format_index + 1 >= len(tail):
        return None
    value = tail[format_index + 1]
    return value if value in {"reqif"} else None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quarto-needs export")
    parser.add_argument("--format", choices=("reqif",), required=True)
    parser.add_argument("--output")
    return parser


def _export_tail(argv: Sequence[str]) -> list[str]:
    values = list(argv)
    index = values.index("export")
    return values[index + 1 :]


def run_interchange_export(root: Path, argv: Sequence[str], format_name: str) -> int:
    try:
        args = _parser().parse_args(_export_tail(argv))
    except SystemExit as error:
        return int(error.code)

    try:
        config = load_config(root)
    except ValueError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    try:
        result = analyze_project(root, config=config)
    except OSError as error:
        print(f"Could not scan {root}: {error}", file=sys.stderr)
        return 3
    if result.snapshot is None:
        from .cli import print_findings

        print_findings(result.findings, stream=sys.stderr)
        return 1

    if format_name != "reqif":
        print(f"Unsupported interchange format: {format_name}", file=sys.stderr)
        return 2

    output_arg = Path(args.output) if args.output else Path(".quarto-needs/requirements.reqif")
    output = output_arg if output_arg.is_absolute() else root / output_arg
    try:
        reqif_export.write(output, result.snapshot)
    except OSError as error:
        print(f"Could not write ReqIF export {output}: {error}", file=sys.stderr)
        return 3

    print(
        f"Wrote ReqIF {reqif_export.REQIF_SPECIFICATION_VERSION} export to {output} "
        f"({len(result.snapshot.objects)} objects, {len(result.snapshot.relations)} relations)"
    )
    return 0
