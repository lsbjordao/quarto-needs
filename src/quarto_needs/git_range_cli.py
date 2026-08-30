"""CLI projection for deterministic Git-range diff and impact analysis."""
from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from . import diff as diff_module
from . import impact as impact_module
from .git_range import GitRangeError, GitRangeStates, materialize_git_range
from .quality import profile_exit_code


def _option(argv: Sequence[str], name: str) -> str | None:
    values = list(argv)
    try:
        index = values.index(name)
    except ValueError:
        return None
    if index + 1 >= len(values):
        return None
    return values[index + 1]


def _format(argv: Sequence[str]) -> str:
    value = _option(argv, "--format")
    return value if value in {"text", "json"} else "text"


def _recompute(argv: Sequence[str]) -> bool:
    value = _option(argv, "--recompute-with")
    return value == "current"


def git_action(argv: Sequence[str]) -> tuple[str, str] | None:
    """Return (diff|impact, range) only for the new ``--git`` form."""
    values = list(argv)
    command_index = next(
        (index for index, value in enumerate(values) if value in {"diff", "impact"}),
        None,
    )
    if command_index is None:
        return None
    git_range = _option(values[command_index + 1 :], "--git")
    if git_range is None:
        return None
    return values[command_index], git_range


def _git_metadata(states: GitRangeStates) -> dict[str, object]:
    return {
        "range": states.range_spec,
        "baseRef": states.base_ref,
        "baseSha": states.base_sha,
        "headRef": states.head_ref,
        "headSha": states.head_sha,
        "referenceEpoch": states.reference_epoch,
    }


def _json_report(states: GitRangeStates, report: Mapping[str, object]) -> dict[str, object]:
    payload = dict(report)
    payload["git"] = _git_metadata(states)
    return payload


def _print_git_header(states: GitRangeStates) -> None:
    print(
        f"Git range {states.base_ref}..{states.head_ref} "
        f"({states.base_sha[:12]}..{states.head_sha[:12]})"
    )


def _print_diff_text(report) -> None:
    # Kept in this projection rather than reaching into cli.py's private helper;
    # both functions present the same canonical DiffReport.
    for notice in report.notices:
        print(
            f"[notice] {notice}: derived deltas suppressed; both sides must share "
            "configuration and reference date to compare them"
        )
    if report.is_empty():
        if report.suppressed:
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


def _run_diff(states: GitRangeStates, argv: Sequence[str]) -> int:
    try:
        report = diff_module.compare(
            states.base_baseline,
            states.head_snapshot,
            states.head_config,
            recompute=_recompute(argv),
        )
    except diff_module.DiffError as error:
        print(str(error), file=sys.stderr)
        return 2
    if _format(argv) == "json":
        print(json.dumps(_json_report(states, report.to_dict()), indent=2, sort_keys=True))
    else:
        _print_git_header(states)
        _print_diff_text(report)
    return profile_exit_code(states.head_config.profile, False, len(report.gate_regressions))


def _run_impact(states: GitRangeStates, argv: Sequence[str]) -> int:
    try:
        report = impact_module.analyze(
            states.base_baseline,
            states.head_snapshot,
            states.head_config,
            recompute=_recompute(argv),
        )
    except impact_module.ImpactError as error:
        print(str(error), file=sys.stderr)
        return 2
    if _format(argv) == "json":
        print(json.dumps(_json_report(states, report.to_dict()), indent=2, sort_keys=True))
        return 0
    _print_git_header(states)
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


def run_git_action(project_root: Path, argv: Sequence[str], command: str, range_spec: str) -> int:
    try:
        states = materialize_git_range(project_root, range_spec)
    except GitRangeError as error:
        print(f"Git range error: {error}", file=sys.stderr)
        return 2
    if command == "diff":
        return _run_diff(states, argv)
    if command == "impact":
        return _run_impact(states, argv)
    return 2
