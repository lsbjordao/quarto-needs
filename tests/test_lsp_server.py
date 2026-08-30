from __future__ import annotations

import io
import json
from pathlib import Path

from quarto_needs.lsp_server import LspSession, _read_message, _write_message


def _project(tmp_path: Path) -> LspSession:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement]
role = "requirement"
allowed-statuses = ["approved"]

[types.test-case]
role = "verification"
allowed-statuses = ["passed"]

[queries.approved]
all = [{ field = "status", op = "eq", value = "approved" }]
sort = ["id:asc"]

[policies.APPROVED_REQUIRES_TEST]
scope = "approved"
assert-relation = "verified-by"
target-role = "verification"
minimum = 1
severity = "error"
''',
        encoding="utf-8",
    )
    (tmp_path / "requirements.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Requirement one
:::

::: {.need #FUN-002 type="functional-requirement" status="approved"}
## Requirement two
:::
''',
        encoding="utf-8",
    )
    (tmp_path / "verification.qmd").write_text(
        '''::: {.need #TC-001 type="test-case" status="passed"}
## Test
:::
''',
        encoding="utf-8",
    )
    return LspSession.load(tmp_path)


def _params(path: Path, line: int, character: int) -> dict[str, object]:
    return {
        "textDocument": {"uri": path.resolve().as_uri()},
        "position": {"line": line, "character": character},
    }


def test_initialize_advertises_shared_semantic_capabilities(tmp_path: Path) -> None:
    session = _project(tmp_path)
    result = session.handle("initialize", {})
    capabilities = result["capabilities"]
    assert capabilities["completionProvider"]
    assert capabilities["hoverProvider"] is True
    assert capabilities["definitionProvider"] is True
    assert capabilities["referencesProvider"] is True
    assert capabilities["documentSymbolProvider"] is True
    assert capabilities["workspaceSymbolProvider"] is True


def test_hover_definition_and_references_resolve_identifier_at_position(tmp_path: Path) -> None:
    session = _project(tmp_path)
    requirements = tmp_path / "requirements.qmd"
    hover = session.handle("textDocument/hover", _params(requirements, 0, 12))
    assert "FUN-001" in hover["contents"]["value"]

    definition = session.handle("textDocument/definition", _params(requirements, 0, 12))
    assert definition["uri"] == requirements.resolve().as_uri()

    verification = tmp_path / "verification.qmd"
    refs = session.handle("textDocument/references", _params(verification, 0, 12))
    assert refs
    assert refs[0]["uri"] == requirements.resolve().as_uri()


def test_publish_diagnostics_projection_uses_lsp_severity(tmp_path: Path) -> None:
    session = _project(tmp_path)
    uri = (tmp_path / "requirements.qmd").resolve().as_uri()
    payload = session.diagnostics_for_uri(uri)
    diagnostic = next(
        item
        for item in payload["diagnostics"]
        if item["code"] == "POLICY:APPROVED_REQUIRES_TEST"
    )
    assert diagnostic["severity"] == 1
    assert diagnostic["source"] == "quarto-needs"


def test_document_and_workspace_symbols(tmp_path: Path) -> None:
    session = _project(tmp_path)
    requirements = tmp_path / "requirements.qmd"
    document = session.handle(
        "textDocument/documentSymbol",
        {"textDocument": {"uri": requirements.resolve().as_uri()}},
    )
    assert [item["name"].split(" — ")[0] for item in document] == ["FUN-001", "FUN-002"]

    workspace = session.handle("workspace/symbol", {"query": "Requirement two"})
    assert len(workspace) == 1
    assert workspace[0]["name"].startswith("FUN-002")


def test_json_rpc_content_length_round_trip() -> None:
    stream = io.BytesIO()
    payload = {"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}}
    _write_message(stream, payload)
    stream.seek(0)
    assert _read_message(stream) == payload


def test_shutdown_marks_session_for_clean_exit(tmp_path: Path) -> None:
    session = _project(tmp_path)
    assert session.shutdown_requested is False
    assert session.handle("shutdown", {}) is None
    assert session.shutdown_requested is True
