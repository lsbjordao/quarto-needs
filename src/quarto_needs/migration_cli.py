from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .analysis import analyze_project
from .config import load_config
from .migrations.apply_plan import build_sphinx_apply_plan, write_apply_plan
from .migrations.apply_write import MigrationApplyError, apply_migration_plan
from .migrations.doorstop import DoorstopMigrationError, load_doorstop_documents
from .migrations.doorstop import build_migration_plan as build_doorstop_plan
from .migrations.sphinx_needs import (
    SphinxNeedsMigrationError,
    SphinxNeedsMigrationPlan,
    build_migration_plan as build_sphinx_plan,
    load_needs_json,
    write_migration_plan,
)

SOURCES = ("sphinx-needs", "doorstop")

DEFAULT_PLAN_PATHS = {
    "sphinx-needs": ".quarto-needs/migrations/sphinx-needs-plan.json",
    "doorstop": ".quarto-needs/migrations/doorstop-plan.json",
}
DEFAULT_APPLY_PLAN_PATHS = {
    "sphinx-needs": ".quarto-needs/migrations/sphinx-needs-apply-plan.json",
    "doorstop": ".quarto-needs/migrations/doorstop-apply-plan.json",
}


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


def _add_apply_flags(parser: argparse.ArgumentParser, source: str) -> None:
    parser.add_argument("--output", default=DEFAULT_PLAN_PATHS[source])
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--apply-plan", action="store_true")
    parser.add_argument("--destination", action="append", default=[], metavar="SOURCE=PATH")
    parser.add_argument("--id-map", action="append", default=[], metavar="SOURCE=CANONICAL")
    parser.add_argument("--apply-output", default=DEFAULT_APPLY_PLAN_PATHS[source])
    parser.add_argument("--show-content", action="store_true")
    parser.add_argument("--write", action="store_true")


def _sphinx_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quarto-needs migrate sphinx-needs",
        description="Build a conservative migration plan from a Sphinx-Needs needs.json file.",
    )
    parser.add_argument("needs_json")
    parser.add_argument("--root")
    parser.add_argument("--version")
    parser.add_argument("--type-map", action="append", default=[], metavar="SOURCE=TARGET")
    parser.add_argument("--relation-map", action="append", default=[], metavar="FIELD=RELATION")
    _add_apply_flags(parser, "sphinx-needs")
    return parser


def _doorstop_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quarto-needs migrate doorstop",
        description="Build a conservative migration plan from a Doorstop document tree.",
    )
    parser.add_argument("doorstop_root")
    parser.add_argument("--root")
    parser.add_argument(
        "--type-map", action="append", default=[], metavar="PREFIX=TARGET",
        help="Doorstop document prefix (e.g. REQ) to Quarto-Needs type",
    )
    parser.add_argument(
        "--relation-map", action="append", default=[], metavar="PREFIX=RELATION",
        help="Doorstop child-document prefix to the canonical relation its links express",
    )
    _add_apply_flags(parser, "doorstop")
    return parser


def _strip_dispatch_tokens(argv: Sequence[str], source: str) -> list[str]:
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
            if index < len(values) and values[index] == source:
                index += 1
            continue
        result.append(value)
        index += 1
    return result


def _build_plan(
    root: Path, source: str, argv: Sequence[str]
) -> tuple[SphinxNeedsMigrationPlan, argparse.Namespace]:
    if source == "sphinx-needs":
        parser = _sphinx_parser()
        args = parser.parse_args(_strip_dispatch_tokens(argv, source))
        if args.write and not args.apply_plan:
            raise ValueError("--write requires --apply-plan")
        type_map = _mapping(args.type_map, "--type-map")
        relation_map = _mapping(args.relation_map, "--relation-map")
        document = load_needs_json(_root_relative(root, args.needs_json))
        plan = build_sphinx_plan(
            document, version=args.version, type_map=type_map, relation_map=relation_map
        )
        return plan, args

    parser = _doorstop_parser()
    args = parser.parse_args(_strip_dispatch_tokens(argv, source))
    if args.write and not args.apply_plan:
        raise ValueError("--write requires --apply-plan")
    type_map = _mapping(args.type_map, "--type-map")
    relation_map = _mapping(args.relation_map, "--relation-map")
    documents = load_doorstop_documents(_root_relative(root, args.doorstop_root))
    plan = build_doorstop_plan(documents, type_map=type_map, relation_map=relation_map)
    return plan, args


def run_migration_action(root: Path, argv: Sequence[str], source: str) -> int:
    if source not in SOURCES:
        if not source:
            print(f"Migration source required: {', '.join(SOURCES)}", file=sys.stderr)
        else:
            print(f"Unknown migration source: {source}", file=sys.stderr)
        return 2

    apply_plan = None
    apply_output = None
    apply_result = None
    try:
        plan, args = _build_plan(root, source, argv)
        output = _root_relative(root, args.output)
        write_migration_plan(output, plan)

        if args.apply_plan:
            destinations = _mapping(args.destination, "--destination")
            id_map = _mapping(args.id_map, "--id-map")
            config = load_config(root)
            result = analyze_project(root, config=config)
            if result.snapshot is None:
                for finding in result.findings:
                    print(f"[ERROR] {finding.code}: {finding.message}", file=sys.stderr)
                return 2
            apply_plan = build_sphinx_apply_plan(
                plan,
                result.snapshot,
                config,
                destinations=destinations,
                id_map=id_map,
            )
            apply_output = _root_relative(root, args.apply_output)
            write_apply_plan(apply_output, apply_plan)

            if args.write:
                apply_result = apply_migration_plan(root, apply_plan, config)
    except (ValueError, SphinxNeedsMigrationError, DoorstopMigrationError, MigrationApplyError) as error:
        print(f"Migration error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Migration I/O error: {error}", file=sys.stderr)
        return 3

    if args.format == "json":
        if apply_result is not None:
            payload = apply_result.to_dict()
        elif apply_plan is not None:
            payload = apply_plan.to_dict()
        else:
            payload = plan.to_dict()
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            f"{plan.tool} migration plan: {len(plan.candidates)} candidate(s), "
            f"{len(plan.issues)} issue(s)"
        )
        print(f"Source version: {plan.source_version}")
        print(f"Plan: {output}")
        for issue in plan.issues:
            scope = f" {issue.need_id}" if issue.need_id else ""
            field = f" [{issue.field}]" if issue.field else ""
            print(f"[{issue.code}]{scope}{field}: {issue.message}")

        if apply_plan is not None:
            print()
            print(
                f"{plan.tool} apply plan: {len(apply_plan.items)} item(s), "
                f"ready={apply_plan.ready}"
            )
            print(f"Apply plan: {apply_output}")
            for item in apply_plan.items:
                destination = item.destination_file or "no destination"
                print(f"[{item.status}] {item.source_id} -> {item.canonical_id} ({destination})")
                if item.target_type or item.target_status:
                    print(f"  type={item.target_type} status={item.target_status}")
                if item.relations:
                    rendered = ", ".join(
                        f"{relation['relation']} -> {relation['target']}"
                        for relation in item.relations
                    )
                    print(f"  relations: {rendered}")
                if item.reasons:
                    print(f"  reasons: {'; '.join(item.reasons)}")
                if args.show_content and item.content_preview is not None:
                    print("  content preview:")
                    for line in item.content_preview.splitlines():
                        print(f"    {line}")

            if apply_result is not None:
                print()
                print(f"Wrote {len(apply_result.written)} file(s):")
                for destination_file in apply_result.written:
                    print(f"  {destination_file}")

    # A plan with unresolved semantics or an apply plan that is not fully
    # ready-to-create is useful output but not migration-ready.
    if plan.issues:
        return 1
    if apply_plan is not None and not apply_plan.ready:
        return 1
    return 0
