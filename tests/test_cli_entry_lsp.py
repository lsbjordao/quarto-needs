from __future__ import annotations

from pathlib import Path

import quarto_needs.cli_entry as cli_entry
import quarto_needs.lsp_server as lsp_server


def test_lsp_top_level_command_dispatches_to_stdio(tmp_path: Path, monkeypatch) -> None:
    called: dict[str, Path] = {}

    def fake_run_stdio(root: Path) -> int:
        called["root"] = root
        return 17

    monkeypatch.setattr(lsp_server, "run_stdio", fake_run_stdio)
    assert cli_entry.main(["--root", str(tmp_path), "lsp"]) == 17
    assert called["root"] == tmp_path.resolve()


def test_lsp_word_as_non_command_does_not_hijack_legacy_dispatch(monkeypatch) -> None:
    called: dict[str, list[str]] = {}

    def fake_dispatch(values) -> int:
        called["values"] = list(values)
        return 23

    monkeypatch.setattr(cli_entry, "dispatch_main", fake_dispatch)
    assert cli_entry.main(["trace", "lsp"]) == 23
    assert called["values"] == ["trace", "lsp"]


def test_root_equals_form_still_resolves_lsp_command(tmp_path: Path, monkeypatch) -> None:
    called: dict[str, Path] = {}

    def fake_run_stdio(root: Path) -> int:
        called["root"] = root
        return 0

    monkeypatch.setattr(lsp_server, "run_stdio", fake_run_stdio)
    assert cli_entry.main([f"--root={tmp_path}", "lsp"]) == 0
    assert called["root"] == tmp_path.resolve()
