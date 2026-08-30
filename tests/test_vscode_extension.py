from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "editors" / "vscode"


def test_vscode_extension_is_lsp_client_not_semantic_engine() -> None:
    source = (EXTENSION / "src" / "extension.ts").read_text(encoding="utf-8")
    assert "vscode-languageclient/node" in source
    assert '"--root"' in source
    assert '"lsp"' in source
    assert ".quarto-needs.toml" in source

    forbidden = (
        "verified-by",
        "implemented-by",
        "semantic_family",
        "POLICY:",
        "CONSTRAINT:",
        "REQ005",
        "jsonschema",
    )
    assert all(token not in source for token in forbidden)


def test_vscode_manifest_declares_configurable_server_and_qmd_activation() -> None:
    manifest = json.loads((EXTENSION / "package.json").read_text(encoding="utf-8"))
    assert manifest["main"] == "./dist/extension.js"
    assert "vscode-languageclient" in manifest["dependencies"]
    assert "workspaceContains:.quarto-needs.toml" in manifest["activationEvents"]
    properties = manifest["contributes"]["configuration"]["properties"]
    assert properties["quartoNeeds.server.command"]["default"] == "quarto-needs"
    assert properties["quartoNeeds.server.extraArgs"]["default"] == []


def test_vscode_client_supports_multi_root_and_does_not_embed_environment_paths() -> None:
    source = (EXTENSION / "src" / "extension.ts").read_text(encoding="utf-8")
    assert "new Map<string, LanguageClient>()" in source
    assert "workspaceFolders" in source
    assert "folder.uri.fsPath" in source
    assert "folder.index" not in source
    assert "clientId(folder)" in source
    assert ".venv" not in source
    assert "/usr/bin" not in source


def test_vscode_client_tracks_project_marker_creation_and_removal() -> None:
    source = (EXTENSION / "src" / "extension.ts").read_text(encoding="utf-8")
    assert 'createFileSystemWatcher(\n    "**/.quarto-needs.toml"' in source
    assert "markerWatcher.onDidCreate(syncWorkspaceClients)" in source
    assert "markerWatcher.onDidDelete(syncWorkspaceClients)" in source
    assert "desiredProjectFolders" in source
    assert "activeKeys" in source


def test_vscode_client_keeps_language_intelligence_on_server_side() -> None:
    source = (EXTENSION / "src" / "extension.ts").read_text(encoding="utf-8")
    forbidden_implementations = (
        "registerCompletionItemProvider",
        "createDiagnosticCollection",
        "registerDefinitionProvider",
        "registerReferenceProvider",
        "registerRenameProvider",
        "registerHoverProvider",
    )
    assert all(token not in source for token in forbidden_implementations)


def test_vscode_manifest_supports_repeatable_vsix_packaging_contract() -> None:
    manifest = json.loads((EXTENSION / "package.json").read_text(encoding="utf-8"))
    assert manifest["repository"]["directory"] == "editors/vscode"
    assert "@vscode/vsce" in manifest["devDependencies"]
    assert manifest["scripts"]["package"] == "vsce package --out quarto-needs-vscode.vsix"
    assert manifest["scripts"]["vscode:prepublish"] == "npm run compile"

    ignore = (EXTENSION / ".vscodeignore").read_text(encoding="utf-8")
    assert "src/**" in ignore
    assert "tsconfig.json" in ignore
    assert "dist/**" not in ignore
    assert "README.md" not in ignore


def test_vscode_package_version_matches_current_core_release_line() -> None:
    manifest = json.loads((EXTENSION / "package.json").read_text(encoding="utf-8"))
    init_source = (ROOT / "src" / "quarto_needs" / "__init__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{manifest["version"]}"' in init_source
