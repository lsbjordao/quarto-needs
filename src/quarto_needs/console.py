from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from typing import TextIO

RESET = "\x1b[0m"
BOLD_RED = "\x1b[1;31m"
RED = "\x1b[31m"
BOLD_GREEN = "\x1b[1;32m"
GREEN = "\x1b[32m"
BOLD_YELLOW = "\x1b[1;33m"
YELLOW = "\x1b[33m"
BOLD_CYAN = "\x1b[1;36m"
CYAN = "\x1b[36m"
DIM = "\x1b[2m"

_ISSUE_CODE = re.compile(r"^\[(?:EVD|REQ|ADR|CFG|OSLC|INT|GIT|VAR|MIG)\d+\]")
_ERROR_PREFIX = re.compile(
    r"^(?:\[ERROR\]|ERROR\b|Error\b|Configuration error:|Evidence error:|"
    r"Evidence check failed:|Could not\b|Unknown\b|Invalid\b)"
)
_WARNING_PREFIX = re.compile(r"^(?:\[WARN\]|WARN\b|Warning\b|\[notice\]|notice\b)", re.I)
_SUCCESS_PREFIX = re.compile(
    r"^(?:\[PASS\]|PASS\b|Evidence check passed:|Wrote\b|Created\b|Updated\b|"
    r"No changes\.|Successfully\b)"
)
_INFO_PREFIX = re.compile(
    r"^(?:Quarto-Needs\b|Requirements:|Baseline\b|Scope\b|Findings:|OSLC\b)"
)


def colorize_line(line: str) -> str:
    """Apply one semantic terminal style to a complete human-readable line."""
    plain = line.rstrip("\n")
    newline = "\n" if line.endswith("\n") else ""
    if not plain:
        return line

    if _ERROR_PREFIX.search(plain) or plain.startswith("! gate "):
        return f"{BOLD_RED}{plain}{RESET}{newline}"
    if _ISSUE_CODE.search(plain):
        # Validation/diagnostic codes printed as top-level issue lines are
        # attention items even when their category is more specific than ERROR.
        return f"{RED}{plain}{RESET}{newline}"
    if _WARNING_PREFIX.search(plain):
        return f"{BOLD_YELLOW}{plain}{RESET}{newline}"
    if _SUCCESS_PREFIX.search(plain):
        return f"{BOLD_GREEN}{plain}{RESET}{newline}"

    # Diff notation is intentionally visually stable and mirrors familiar VCS
    # conventions without changing the underlying text contract.
    if plain.startswith("+ "):
        return f"{GREEN}{plain}{RESET}{newline}"
    if plain.startswith("- "):
        return f"{RED}{plain}{RESET}{newline}"
    if plain.startswith(("~ ", "[notice]")):
        return f"{YELLOW}{plain}{RESET}{newline}"
    if plain.startswith(("> ", "= ")):
        return f"{CYAN}{plain}{RESET}{newline}"
    if _INFO_PREFIX.search(plain):
        return f"{BOLD_CYAN}{plain}{RESET}{newline}"
    if plain.startswith("  "):
        return f"{DIM}{plain}{RESET}{newline}"
    return line


def should_color(
    stream: TextIO,
    argv: Sequence[str],
    *,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return whether human CLI output should contain ANSI color escapes."""
    env = os.environ if environ is None else environ
    if "NO_COLOR" in env:
        return False
    if "--format" in argv:
        try:
            if argv[argv.index("--format") + 1].casefold() == "json":
                return False
        except IndexError:
            pass
    if any(value.casefold() == "--format=json" for value in argv):
        return False
    if "lsp" in argv:
        return False
    if "FORCE_COLOR" in env and env.get("FORCE_COLOR", "") != "0":
        return True
    if env.get("TERM", "").casefold() == "dumb":
        return False
    try:
        return bool(stream.isatty())
    except (AttributeError, OSError):
        return False


class SemanticColorStream:
    """Line-buffering TextIO proxy that colors only complete terminal lines."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream
        self._pending = ""

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            raise TypeError("console stream accepts text only")
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self._stream.write(colorize_line(line + "\n"))
        # Match TextIO.write: report how much caller input was accepted, not
        # how many ANSI-decorated characters reached the underlying stream.
        return len(text)

    def flush(self) -> None:
        if self._pending:
            self._stream.write(colorize_line(self._pending))
            self._pending = ""
        self._stream.flush()

    def isatty(self) -> bool:
        return self._stream.isatty()

    @property
    def encoding(self):  # type: ignore[no-untyped-def]
        return getattr(self._stream, "encoding", None)

    def fileno(self) -> int:
        return self._stream.fileno()

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(self._stream, name)


def install_semantic_color(argv: Sequence[str]) -> tuple[TextIO, TextIO] | None:
    """Wrap stdout/stderr for human terminal output and return originals."""
    stdout = os.sys.stdout
    stderr = os.sys.stderr
    color_stdout = should_color(stdout, argv)
    color_stderr = should_color(stderr, argv)
    if not color_stdout and not color_stderr:
        return None
    if color_stdout:
        os.sys.stdout = SemanticColorStream(stdout)  # type: ignore[assignment]
    if color_stderr:
        os.sys.stderr = SemanticColorStream(stderr)  # type: ignore[assignment]
    return stdout, stderr


def restore_streams(originals: tuple[TextIO, TextIO] | None) -> None:
    if originals is None:
        return
    # Flush wrappers before restoring so a final line without newline is not lost.
    os.sys.stdout.flush()
    os.sys.stderr.flush()
    os.sys.stdout, os.sys.stderr = originals
