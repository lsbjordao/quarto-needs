from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from .migrations.sphinx_needs import (
    SphinxNeedsMigrationError,
    build_migration_plan,
    load_needs_json,
    write_migration_plan,
)

DEFAULT_SPHINX_PLAN = ".quarto-needs/migrations/sphinx-needs-plan.json"


def migration_action(argv: Sequence[str]) -> str | None:
    values = list(argv)
    index = 0
    while index < len(values):
        value = values[index]
        if value == "--root":
            index += 2
            continue
        if value.startswith("--root="):
            index += 1
            continue
        if value.startswith("-"):
            index += 1
            continue
        if value != "migrate":
            return None
        if index + 1 >= len(values):
            return ""
        return values[index + 1]
    return None


def _root_relative(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _mapping(values: list[str], option: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"{option} values must use SOURCE=TARGET")
        source, target = raw.split("=", 1)
        source = source.strip()
        target = target.strip()
        if not source or not target:
            raise ValueError(f"{option} values must use non-empty SOURCE=TARGET")
        if source in result and result[source] != target:
            raise ValueError(f"{option} maps {source!r} more than once")
        result[source] = target
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quarto-needs migrate sphinx-needs",
        description="Build a conservative migration plan from a Sphinx-Needs needs.json file.",
    )
    parser.add_argument("needs_json")
    parser.add_argument("--root")
    parser.add_argument("--version")
    parser.add_argument("--type-map", action="append", default=[], metavar="SOURCE=TARGET")
    parser.add_argument("--relation-map", action="append", default=[], metavar="FIELD=RELATION")
    parser.add_argument("--output", default=DEFAULT_SPHINX_PLAN)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _strip_dispatch_tokens(argv: Sequence[str]) -> list[str]:
    values = list(argv)
    result: list[str] = []
    skipped = False
    index = 0
    while index < len(values):
        value = values[index]
        if value == "--root":
            result.extend(values[index : index + 2])
            index += 2
            continue
        if value.startswith("--root="):
            result.append(value)
            index += 1
            continue
        if not skipped and value == "migrate":
            skipped = True
            index += 1
            if index < len(values) and values[index] == "sphinx-needs":
                index += 1
            continue
        result.append(value)
        index += 1
    return result


def run_migration_action(root: Path, argv: Sequence[str], source: str) -> int:
    if source != "sphinx-needs":
        if not source:
            print("Migration source required: sphinx-needs", file=sys.stderr)
        else:
            print(f"Unknown migration source: {source}", file=sys.stderr)
        return 2

    parser = _parser()
    try:
        args = parser.parse_args(_strip_dispatch_tokens(argv))
        type_map = _mapping(args.type_map, "--type-map")
        relation_map = _mapping(args.relation_map, "--relation-map")
        document = load_needs_json(_root_relative(root, args.needs_json))
        plan = build_migration_plan(
            document,
            version=args.version,
            type_map=type_map,
            relation_map=relation_map,
        )
        output = _root_relative(root, args.output)
        write_migration_plan(output, plan)
    except (ValueError, SphinxNeedsMigrationError) as error:
        print(f"Migration error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Migration I/O error: {error}", file=sys.stderr)
        return 3

    if args.format == "json":
        print(json.dumps(plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            f"Sphinx-Needs migration plan: {len(plan.candidates)} candidate(s), "
            f"{len(plan.issues)} issue(s)"
        )
        print(f"Source version: {plan.source_version}")
        print(f"Plan: {output}")
        for issue in plan.issues:
            scope = f" {issue.need_id}" if issue.need_id else ""
            field = f" [{issue.field}]" if issue.field else ""
            print(f"[{issue.code}]{scope}{field}: {issue.message}")

    # A plan with unresolved semantics is useful output but not migration-ready.
    return 1 if plan.issues else 0
