"""Minimal dependency-free LSP stdio transport over :mod:`language_service`.

The transport translates Language Server Protocol JSON-RPC messages only. All
engineering semantics remain in ``LanguageService`` and the canonical analyzer.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Mapping
from urllib.parse import unquote, urlparse

from .language_service import LanguageService, LanguageServiceError
from .snapshot import LocationRecord

IDENTIFIER_RE = re.compile(r"[A-Za-z0-9_.:-]+")


def _path_from_uri(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Unsupported document URI scheme: {parsed.scheme}")
    return Path(unquote(parsed.path)).resolve()


def _uri(path: Path) -> str:
    return path.resolve().as_uri()


def _range(line: int, *, width: int = 1) -> dict[str, object]:
    zero = max(0, line - 1)
    return {
        "start": {"line": zero, "character": 0},
        "end": {"line": zero, "character": max(1, width)},
    }


def _location(root: Path, location: LocationRecord) -> dict[str, object]:
    return {
        "uri": _uri(root / location.file),
        "range": _range(location.line),
    }


def _severity(value: str) -> int:
    return {"error": 1, "warning": 2, "info": 3}.get(value, 3)


def _identifier_at(path: Path, line: int, character: int) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if line < 0 or line >= len(lines):
        return None
    text = lines[line]
    cursor = min(max(character, 0), len(text))
    for match in IDENTIFIER_RE.finditer(text):
        if match.start() <= cursor <= match.end():
            return match.group(0)
    return None


@dataclass
class LspSession:
    root: Path
    service: LanguageService
    shutdown_requested: bool = False

    @classmethod
    def load(cls, root: Path) -> "LspSession":
        resolved = Path(root).resolve()
        return cls(resolved, LanguageService.load(resolved))

    def reload(self) -> None:
        self.service = LanguageService.load(self.root)

    def _document(self, params: Mapping[str, object]) -> tuple[str, Path]:
        document = params.get("textDocument")
        if not isinstance(document, Mapping) or not isinstance(document.get("uri"), str):
            raise ValueError("textDocument.uri is required")
        uri = str(document["uri"])
        return uri, _path_from_uri(uri)

    def diagnostics_for_uri(self, uri: str) -> dict[str, object]:
        path = _path_from_uri(uri)
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError:
            return {"uri": uri, "diagnostics": []}
        diagnostics = []
        for item in self.service.diagnostics(file=relative):
            if item.location is None:
                continue
            diagnostics.append(
                {
                    "range": _range(item.location.line),
                    "severity": _severity(item.severity),
                    "code": item.code,
                    "source": "quarto-needs",
                    "message": item.message,
                }
            )
        return {"uri": uri, "diagnostics": diagnostics}

    def handle(self, method: str, params: Mapping[str, object] | None) -> object:
        values: Mapping[str, object] = params or {}
        if method == "initialize":
            return {
                "capabilities": {
                    "textDocumentSync": 1,
                    "completionProvider": {"triggerCharacters": ["#", "=", ":"]},
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    "documentSymbolProvider": True,
                    "workspaceSymbolProvider": True,
                },
                "serverInfo": {"name": "quarto-needs", "version": "0.1"},
            }
        if method == "shutdown":
            self.shutdown_requested = True
            return None
        if method == "textDocument/completion":
            _, path = self._document(values)
            position = values.get("position")
            prefix = ""
            if isinstance(position, Mapping):
                identifier = _identifier_at(
                    path,
                    int(position.get("line", 0)),
                    int(position.get("character", 0)),
                )
                prefix = identifier or ""
            kind_map = {"object": 6, "type": 7, "relation": 10, "status": 12}
            return [
                {
                    "label": item.label,
                    "kind": kind_map.get(item.kind, 1),
                    "detail": item.detail,
                }
                for item in self.service.completions(prefix)
            ]
        if method in {"textDocument/hover", "textDocument/definition", "textDocument/references"}:
            _, path = self._document(values)
            position = values.get("position")
            if not isinstance(position, Mapping):
                return None if method != "textDocument/references" else []
            object_id = _identifier_at(
                path,
                int(position.get("line", 0)),
                int(position.get("character", 0)),
            )
            if not object_id:
                return None if method != "textDocument/references" else []
            if method == "textDocument/hover":
                hover = self.service.hover(object_id)
                if hover is None:
                    return None
                lines = [
                    f"**{hover.object_id} — {hover.title}**",
                    "",
                    f"Type: `{hover.type}` · Status: `{hover.status}`",
                ]
                if hover.role:
                    lines.append(f"Role: `{hover.role}`")
                if hover.priority:
                    lines.append(f"Priority: `{hover.priority}`")
                if hover.derived:
                    lines.append("")
                    lines.append("Derived:")
                    for name, value in hover.derived.items():
                        lines.append(f"- `{name}`: `{value}`")
                lines.append("")
                lines.append(f"Relations: {hover.outgoing} outgoing, {hover.incoming} incoming")
                return {"contents": {"kind": "markdown", "value": "\n".join(lines)}}
            if method == "textDocument/definition":
                definition = self.service.definition(object_id)
                return _location(self.root, definition) if definition else None
            return [
                _location(self.root, ref.location)
                for ref in self.service.references(object_id)
                if ref.location is not None
            ]
        if method == "textDocument/documentSymbol":
            _, path = self._document(values)
            try:
                relative = path.relative_to(self.root).as_posix()
            except ValueError:
                return []
            return [
                {
                    "name": f"{symbol.object_id} — {symbol.title}",
                    "kind": 13,
                    "range": _range(symbol.location.line if symbol.location else 1),
                    "selectionRange": _range(symbol.location.line if symbol.location else 1),
                    "detail": f"{symbol.type} · {symbol.status}",
                }
                for symbol in self.service.symbols(file=relative)
            ]
        if method == "workspace/symbol":
            query = values.get("query")
            needle = str(query).casefold() if query is not None else ""
            result = []
            for symbol in self.service.symbols():
                if needle and needle not in symbol.object_id.casefold() and needle not in symbol.title.casefold():
                    continue
                if symbol.location is None:
                    continue
                result.append(
                    {
                        "name": f"{symbol.object_id} — {symbol.title}",
                        "kind": 13,
                        "location": _location(self.root, symbol.location),
                    }
                )
            return result
        return None


def _read_message(stream: BinaryIO) -> dict[str, object] | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        text = line.decode("ascii").strip()
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.casefold()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    payload = json.loads(stream.read(length).decode("utf-8"))
    return payload if isinstance(payload, dict) else None


def _write_message(stream: BinaryIO, payload: Mapping[str, object]) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    stream.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    stream.write(data)
    stream.flush()


def run_stdio(root: Path, instream: BinaryIO | None = None, outstream: BinaryIO | None = None) -> int:
    input_stream = instream or sys.stdin.buffer
    output_stream = outstream or sys.stdout.buffer
    try:
        session = LspSession.load(root)
    except (LanguageServiceError, ValueError) as error:
        print(f"LSP startup error: {error}", file=sys.stderr)
        return 2

    while True:
        message = _read_message(input_stream)
        if message is None:
            return 0
        method = message.get("method")
        params = message.get("params")
        if method == "exit":
            return 0 if session.shutdown_requested else 1
        if method in {"textDocument/didOpen", "textDocument/didSave"}:
            try:
                session.reload()
                if isinstance(params, Mapping):
                    document = params.get("textDocument")
                    if isinstance(document, Mapping) and isinstance(document.get("uri"), str):
                        _write_message(
                            output_stream,
                            {
                                "jsonrpc": "2.0",
                                "method": "textDocument/publishDiagnostics",
                                "params": session.diagnostics_for_uri(str(document["uri"])),
                            },
                        )
            except (LanguageServiceError, ValueError):
                pass
            continue
        if not isinstance(method, str) or "id" not in message:
            continue
        try:
            result = session.handle(
                method, params if isinstance(params, Mapping) else None
            )
            response = {"jsonrpc": "2.0", "id": message["id"], "result": result}
        except Exception as error:  # protocol boundary: return an LSP error, do not crash stdio
            response = {
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {"code": -32603, "message": str(error)},
            }
        _write_message(output_stream, response)
