"""CLI projection for deterministic Git-range change intelligence."""
from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from . import diff as diff_module
from . import github_projection as github_projection_module
from . import impact as impact_module
from . import pr_report as pr_report_module
from . import suspect as suspect_module
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
    return value if value in {"text", "json", "markdown", "annotations"} else "text"


def _recompute(argv: Sequence[str]) -> bool:
    value = _option(argv, "--recompute-with")
    return value == "current"


#: The commands this layer claims when they carry `--git`. Named so the
#: stability registry can be checked against the real routing rather than
#: against a second list written beside it.
GIT_RANGE_COMMANDS = ("diff", "impact", "suspect", "pr-report", "github-report")


def git_action(argv: Sequence[str]) -> tuple[str, str] | None:
    """Return a Git-native change command and its two-dot range."""
    values = list(argv)
    command_index = next(
        (
            index
            for index, value in enumerate(values)
            if value in set(GIT_RANGE_COMMANDS)
        ),
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


def _run_suspect(states: GitRangeStates, argv: Sequence[str]) -> int:
    try:
        report = suspect_module.analyze(
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
    if not report.claims:
        print("No suspect traceability claims.")
        return 0
    for claim in report.claims:
        role = f" role={claim['role']}" if claim.get("role") else ""
        print(
            f"suspect {claim['id']}{role} from {claim['origin']} "
            f"d={claim['distance']} via {claim['witness']}"
        )
    return 0


def _run_pr_report(states: GitRangeStates, argv: Sequence[str]) -> int:
    try:
        report = pr_report_module.analyze(
            states.base_baseline,
            states.head_snapshot,
            states.head_config,
            recompute=_recompute(argv),
        )
    except (diff_module.DiffError, impact_module.ImpactError) as error:
        print(str(error), file=sys.stderr)
        return 2
    format_name = _format(argv)
    if format_name == "json":
        print(json.dumps(_json_report(states, report.to_dict()), indent=2, sort_keys=True))
    else:
        if format_name == "text":
            _print_git_header(states)
        print(pr_report_module.render_markdown(report), end="")
    return profile_exit_code(
        states.head_config.profile,
        False,
        len(report.gate_regressions),
    )


def _run_github_report(states: GitRangeStates, argv: Sequence[str]) -> int:
    try:
        report = pr_report_module.analyze(
            states.base_baseline,
            states.head_snapshot,
            states.head_config,
            recompute=_recompute(argv),
        )
    except (diff_module.DiffError, impact_module.ImpactError) as error:
        print(str(error), file=sys.stderr)
        return 2
    projection = github_projection_module.build(
        report,
        states.head_snapshot,
        model_url=_option(argv, "--model-url"),
    )
    format_name = _format(argv)
    if format_name == "json":
        print(json.dumps(_json_report(states, projection.to_dict()), indent=2, sort_keys=True))
    elif format_name == "annotations":
        print(github_projection_module.render_workflow_commands(projection), end="")
    else:
        if format_name == "text":
            _print_git_header(states)
        print(projection.summary_markdown, end="")
    return 1 if projection.check.get("conclusion") == "failure" else 0


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
    if command == "suspect":
        return _run_suspect(states, argv)
    if command == "pr-report":
        return _run_pr_report(states, argv)
    if command == "github-report":
        return _run_github_report(states, argv)
    return 2
