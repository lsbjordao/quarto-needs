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


def _root(argv: Sequence[str]) -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--root")
    args, _ = parser.parse_known_args(list(argv))
    return Path(args.root or os.getcwd()).resolve()


def main(argv: Sequence[str] | None = None) -> int:
    values = list(sys.argv[1:] if argv is None else argv)
    action = git_action(values)
    if action is not None:
        command, range_spec = action
        return run_git_action(_root(values), values, command, range_spec)
    return dispatch_main(values)


if __name__ == "__main__":
    raise SystemExit(main())
