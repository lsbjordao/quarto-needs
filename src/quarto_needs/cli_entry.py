"""Installed Quarto-Needs CLI entry point.

New command forms are intercepted in narrow dispatch layers; all established
commands ultimately delegate to the legacy argparse implementation unchanged.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from . import surface
from .cli_dispatch import main as dispatch_main
from .console import install_semantic_color, restore_streams
from .git_range_cli import git_action, run_git_action
from .interchange_cli import interchange_action, run_interchange_export
from .migration_cli import migration_action, run_migration_action
from .oslc_cli import oslc_action, run_oslc_action
from .variant_cli import run_variant_action, variant_action


def _root(argv: Sequence[str]) -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root")
    args, _ = parser.parse_known_args(list(argv))
    return Path(args.root or os.getcwd()).resolve()


def _top_level_command(argv: Sequence[str]) -> str | None:
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
        return value
    return None


def _warn_if_experimental(token: str | None, argv: Sequence[str]) -> None:
    """One stderr line before an experimental command runs.

    The tier is read from the registry rather than decided here, so a command
    promoted out of experimental stops warning without this file changing --
    and the warning cannot disagree with the tier that `--help` and the manual
    show.

    stdout stays untouched: it is consumed by machines, and a banner there
    would break pipelines. There is no command-line flag on purpose -- a flag
    would have to be added to every subparser, including the ones that never
    reach argparse, which is the duplication this registry exists to remove.
    """
    if token is None or surface.tier_of(token) != surface.EXPERIMENTAL:
        return
    if os.environ.get(surface.SUPPRESS_WARNING_ENVIRONMENT) == "1":
        return
    if "-h" in argv or "--help" in argv:
        return  # Reading about a command is not using it.
    print(
        f"quarto-needs: '{token}' is experimental and outside the stability "
        "contract: it may change or be removed at any time. Set "
        f"{surface.SUPPRESS_WARNING_ENVIRONMENT}=1 to silence this.",
        file=sys.stderr,
    )


def _dispatch(values: list[str]) -> int:
    git = git_action(values)
    if git is not None:
        command, range_spec = git
        _warn_if_experimental(command, values)
        return run_git_action(_root(values), values, command, range_spec)
    variant = variant_action(values)
    if variant is not None:
        action, name = variant
        _warn_if_experimental("variant", values)
        return run_variant_action(_root(values), values, action, name)
    interchange = interchange_action(values)
    if interchange is not None:
        _warn_if_experimental("export", values)
        return run_interchange_export(_root(values), values, interchange)
    migration = migration_action(values)
    if migration is not None:
        _warn_if_experimental("migrate", values)
        return run_migration_action(_root(values), values, migration)
    oslc = oslc_action(values)
    if oslc is not None:
        _warn_if_experimental("oslc", values)
        return run_oslc_action(_root(values), values, oslc)
    token = _top_level_command(values)
    if token == "lsp":
        from .lsp_server import run_stdio

        _warn_if_experimental("lsp", values)
        return run_stdio(_root(values))
    # Everything argparse handles, plus `evidence attest`, warns from here on
    # the same registry lookup, so no layer is exempt by construction.
    _warn_if_experimental(token, values)
    return dispatch_main(values)


def main(argv: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    originals = install_semantic_color(values)
    try:
        return _dispatch(values)
    finally:
        restore_streams(originals)


if __name__ == "__main__":
    raise SystemExit(main())
