from __future__ import annotations

import io

from quarto_needs.console import (
    BOLD_GREEN,
    BOLD_RED,
    RESET,
    SemanticColorStream,
    colorize_line,
    should_color,
)


class _TTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class _Pipe(io.StringIO):
    def isatty(self) -> bool:
        return False


def test_colorize_line_highlights_success_and_failure() -> None:
    assert colorize_line("Evidence check passed: 10 linked pytest test(s)\n") == (
        f"{BOLD_GREEN}Evidence check passed: 10 linked pytest test(s){RESET}\n"
    )
    assert colorize_line("Evidence check failed: 3 issue(s)\n") == (
        f"{BOLD_RED}Evidence check failed: 3 issue(s){RESET}\n"
    )


def test_should_color_only_human_interactive_output() -> None:
    tty = _TTY()
    pipe = _Pipe()
    assert should_color(tty, ["evidence", "check"], environ={"TERM": "xterm-256color"})
    assert not should_color(pipe, ["evidence", "check"], environ={"TERM": "xterm-256color"})
    assert not should_color(
        tty,
        ["evidence", "check", "--format", "json"],
        environ={"TERM": "xterm-256color"},
    )
    assert not should_color(
        tty,
        ["evidence", "check"],
        environ={"TERM": "xterm-256color", "NO_COLOR": "1"},
    )
    assert should_color(
        pipe,
        ["evidence", "check"],
        environ={"TERM": "xterm-256color", "FORCE_COLOR": "1"},
    )


def test_semantic_color_stream_preserves_write_contract_and_buffers_partial_lines() -> None:
    raw = _TTY()
    stream = SemanticColorStream(raw)

    assert stream.write("Evidence check ") == len("Evidence check ")
    assert raw.getvalue() == ""
    assert stream.write("passed: 1 linked test\n") == len("passed: 1 linked test\n")
    assert raw.getvalue() == (
        f"{BOLD_GREEN}Evidence check passed: 1 linked test{RESET}\n"
    )

    stream.write("tail without newline")
    stream.flush()
    assert raw.getvalue().endswith("tail without newline")
