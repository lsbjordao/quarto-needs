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

from .cli_dispatch import main as dispatch_main
from .git_range_cli import git_action, run_git_action
from .interchange_cli import interchange_action, run_interchange_export
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


def main(argv: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    git = git_action(values)
    if git is not None:
        command, range_spec = git
        return run_git_action(_root(values), values, command, range_spec)
    variant = variant_action(values)
    if variant is not None:
        action, name = variant
        return run_variant_action(_root(values), values, action, name)
    interchange = interchange_action(values)
    if interchange is not None:
        return run_interchange_export(_root(values), values, interchange)
    oslc = oslc_action(values)
    if oslc is not None:
        return run_oslc_action(_root(values), values, oslc)
    if _top_level_command(values) == "lsp":
        from .lsp_server import run_stdio

        return run_stdio(_root(values))
    return dispatch_main(values)


if __name__ == "__main__":
    raise SystemExit(main())
