from __future__ import annotations

from pathlib import Path

import quarto_needs

from quarto_needs.lsp_server import LspSession


def _session(tmp_path: Path) -> LspSession:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.test-case]
role = "verification"
allowed-statuses = ["passed"]
''',
        encoding="utf-8",
    )
    (tmp_path / "verification.qmd").write_text(
        '''::: {.need #TC-001 type="test-case" status="passed"}
## Canonical test
:::
''',
        encoding="utf-8",
    )
    (tmp_path / "verification.pt-BR.qmd").write_text(
        '''::: {.need #TC-001 type="test-case" status="passed"}
## Teste localizado
:::
''',
        encoding="utf-8",
    )
    return LspSession.load(tmp_path)


def test_definition_from_localized_declaration_targets_canonical_source(tmp_path: Path) -> None:
    session = _session(tmp_path)
    localized = tmp_path / "verification.pt-BR.qmd"
    definition = session.handle(
        "textDocument/definition",
        {
            "textDocument": {"uri": localized.resolve().as_uri()},
            "position": {"line": 0, "character": 14},
        },
    )
    assert definition["uri"] == (tmp_path / "verification.qmd").resolve().as_uri()


def test_initialize_reports_installed_package_version(tmp_path: Path) -> None:
    session = _session(tmp_path)
    initialize = session.handle("initialize", {})
    assert initialize["serverInfo"] == {
        "name": "quarto-needs",
        "version": quarto_needs.__version__,
    }
