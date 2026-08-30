from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from quarto_needs.lsp_server import LspSession, _read_message, _write_message, run_stdio


def _project(tmp_path: Path) -> LspSession:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement]
role = "requirement"
allowed-statuses = ["draft", "approved"]

[types.test-case]
role = "verification"
allowed-statuses = ["draft", "passed"]

[relations."verified-by"]
allowed-source-types = ["functional-requirement"]
allowed-target-types = ["test-case"]

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
Narrative TC-001 must not be refactored as prose.
{{< need TC-001 >}}
:::

::: {.need #FUN-002 type="functional-requirement" status="approved"}
## Requirement two
:::
''',
        encoding="utf-8",
    )
    (tmp_path / "requirements.pt-BR.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Requisito um
Narrativa TC-001 também deve continuar como prosa.
{{< need TC-001 >}}
:::

::: {.need #FUN-002 type="functional-requirement" status="approved"}
## Requisito dois
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
    assert capabilities["textDocumentSync"] == {
        "openClose": True,
        "change": 1,
        "save": {"includeText": False},
    }
    assert capabilities["completionProvider"]
    assert capabilities["hoverProvider"] is True
    assert capabilities["definitionProvider"] is True
    assert capabilities["referencesProvider"] is True
    assert capabilities["renameProvider"] == {"prepareProvider": True}
    assert capabilities["documentSymbolProvider"] is True
    assert capabilities["workspaceSymbolProvider"] is True


def test_hover_definition_and_references_resolve_identifier_at_position(tmp_path: Path) -> None:
    session = _project(tmp_path)
    requirements = tmp_path / "requirements.qmd"
    hover = session.handle("textDocument/hover", _params(requirements, 0, 12))
    assert "FUN-001" in hover["contents"]["value"]

    definition = session.handle("textDocument/definition", _params(requirements, 0, 12))
    assert definition["uri"] == requirements.resolve().as_uri()
    assert definition["range"]["start"]["character"] > 0

    verification = tmp_path / "verification.qmd"
    refs = session.handle("textDocument/references", _params(verification, 0, 12))
    assert refs
    assert refs[0]["uri"] == requirements.resolve().as_uri()


def test_type_completion_returns_only_types(tmp_path: Path) -> None:
    session = _project(tmp_path)
    path = tmp_path / "scratch.qmd"
    text = '::: {.need #NEW type="fun'
    uri = path.resolve().as_uri()
    session.open_document(uri, text)
    items = session.handle(
        "textDocument/completion",
        _params(path, 0, len(text)),
    )
    assert [item["label"] for item in items] == ["functional-requirement"]


def test_status_completion_respects_current_type_lifecycle(tmp_path: Path) -> None:
    session = _project(tmp_path)
    path = tmp_path / "scratch.qmd"
    text = '::: {.need #NEW type="functional-requirement" status="a'
    uri = path.resolve().as_uri()
    session.open_document(uri, text)
    items = session.handle(
        "textDocument/completion",
        _params(path, 0, len(text)),
    )
    assert [item["label"] for item in items] == ["approved"]


def test_relation_target_completion_respects_allowed_target_types(tmp_path: Path) -> None:
    session = _project(tmp_path)
    requirements = tmp_path / "requirements.qmd"
    original = requirements.read_text(encoding="utf-8")
    first = original.splitlines()[0]
    edited_first = first.replace('verified-by="TC-001"', 'verified-by="T')
    edited = original.replace(first, edited_first)
    uri = requirements.resolve().as_uri()
    session.open_document(uri, edited)
    items = session.handle(
        "textDocument/completion",
        _params(requirements, 0, edited_first.index('verified-by="T') + len('verified-by="T')),
    )
    assert [item["label"] for item in items] == ["TC-001"]
    assert all(not item["label"].startswith("FUN-") for item in items)


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


def test_unsaved_change_reloads_canonical_graph_from_memory(tmp_path: Path) -> None:
    session = _project(tmp_path)
    requirements = tmp_path / "requirements.qmd"
    uri = requirements.resolve().as_uri()
    disk_text = requirements.read_text(encoding="utf-8")
    edited = disk_text.replace("Requirement two", "Edited unsaved title").replace(
        'status="approved"}\n## Edited unsaved title',
        'status="approved" verified-by="TC-001"}\n## Edited unsaved title',
    )
    session.open_document(uri, disk_text)
    session.change_document(uri, edited)

    hover = session.service.hover("FUN-002")
    assert hover is not None
    assert hover.title == "Edited unsaved title"
    assert not [
        item
        for item in session.service.diagnostics(file="requirements.qmd")
        if item.code == "POLICY:APPROVED_REQUIRES_TEST" and item.object_id == "FUN-002"
    ]
    assert "Requirement two" in requirements.read_text(encoding="utf-8")


def test_close_document_returns_to_saved_graph(tmp_path: Path) -> None:
    session = _project(tmp_path)
    requirements = tmp_path / "requirements.qmd"
    uri = requirements.resolve().as_uri()
    edited = requirements.read_text(encoding="utf-8").replace(
        "Requirement two", "Unsaved title"
    )
    session.open_document(uri, edited)
    assert session.service.hover("FUN-002").title == "Unsaved title"
    session.close_document(uri)
    assert session.service.hover("FUN-002").title == "Requirement two"


def test_prepare_rename_requires_semantic_id_span(tmp_path: Path) -> None:
    session = _project(tmp_path)
    requirements = tmp_path / "requirements.qmd"
    semantic = session.handle(
        "textDocument/prepareRename",
        _params(requirements, 0, requirements.read_text(encoding="utf-8").splitlines()[0].index("TC-001") + 2),
    )
    assert semantic["placeholder"] == "TC-001"

    prose_line = requirements.read_text(encoding="utf-8").splitlines()[2]
    prose = session.handle(
        "textDocument/prepareRename",
        _params(requirements, 2, prose_line.index("TC-001") + 2),
    )
    assert prose is None


def test_rename_edits_canonical_localized_and_semantic_references_only(tmp_path: Path) -> None:
    session = _project(tmp_path)
    verification = tmp_path / "verification.qmd"
    edit = session.handle(
        "textDocument/rename",
        {
            **_params(verification, 0, 12),
            "newName": "TC-RENAMED",
        },
    )
    changes = edit["changes"]
    assert set(changes) == {
        (tmp_path / "requirements.qmd").resolve().as_uri(),
        (tmp_path / "requirements.pt-BR.qmd").resolve().as_uri(),
        verification.resolve().as_uri(),
    }
    assert sum(len(items) for items in changes.values()) == 5
    assert all(item["newText"] == "TC-RENAMED" for items in changes.values() for item in items)


def test_rename_rejects_existing_object_id(tmp_path: Path) -> None:
    session = _project(tmp_path)
    verification = tmp_path / "verification.qmd"
    with pytest.raises(ValueError, match="existing object ID FUN-001"):
        session.handle(
            "textDocument/rename",
            {
                **_params(verification, 0, 12),
                "newName": "FUN-001",
            },
        )


def test_rename_uses_unsaved_overlay_spans(tmp_path: Path) -> None:
    session = _project(tmp_path)
    requirements = tmp_path / "requirements.qmd"
    uri = requirements.resolve().as_uri()
    edited = requirements.read_text(encoding="utf-8").replace("{{< need TC-001 >}}", "{{< need TC-001 title=true >}}")
    session.open_document(uri, edited)
    shortcode_line = edited.splitlines()[3]
    edit = session.handle(
        "textDocument/rename",
        {
            **_params(requirements, 3, shortcode_line.index("TC-001") + 2),
            "newName": "TC-X",
        },
    )
    assert uri in edit["changes"]
    assert any(item["range"]["start"]["line"] == 3 for item in edit["changes"][uri])


def test_json_rpc_content_length_round_trip() -> None:
    stream = io.BytesIO()
    payload = {"jsonrpc": "2.0", "id": 7, "method": "initialize", "params": {}}
    _write_message(stream, payload)
    stream.seek(0)
    assert _read_message(stream) == payload


def test_stdio_initialize_shutdown_exit_lifecycle(tmp_path: Path) -> None:
    _project(tmp_path)
    incoming = io.BytesIO()
    for payload in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "shutdown", "params": {}},
        {"jsonrpc": "2.0", "method": "exit", "params": {}},
    ):
        _write_message(incoming, payload)
    incoming.seek(0)
    outgoing = io.BytesIO()
    assert run_stdio(tmp_path, incoming, outgoing) == 0
    outgoing.seek(0)
    initialize = _read_message(outgoing)
    shutdown = _read_message(outgoing)
    assert initialize["id"] == 1
    assert initialize["result"]["capabilities"]["renameProvider"] == {"prepareProvider": True}
    assert shutdown == {"jsonrpc": "2.0", "id": 2, "result": None}


def test_shutdown_marks_session_for_clean_exit(tmp_path: Path) -> None:
    session = _project(tmp_path)
    assert session.shutdown_requested is False
    assert session.handle("shutdown", {}) is None
    assert session.shutdown_requested is True
