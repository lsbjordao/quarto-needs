"""Minimal dependency-free LSP stdio transport over :mod:`language_service`.

The transport translates Language Server Protocol JSON-RPC messages only. All
engineering semantics remain in ``LanguageService`` and the canonical analyzer.
Open editor buffers are passed to that same analyzer as in-memory source
overlays; the server never writes unsaved client text to the project tree.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Mapping
from urllib.parse import unquote, urlparse

from .analysis import analyze_project
from .config import load_config
from .diagnostics import Finding
from .language_service import LanguageService, LanguageServiceError
from .parser import ATTR_RE, RELATION_KEYS
from .snapshot import LocationRecord
from .source_index import SourceSpan, build_source_index

IDENTIFIER_RE = re.compile(r"[A-Za-z0-9_.:-]+")
VALUE_CONTEXT_RE = re.compile(
    r"(?P<key>[A-Za-z0-9_-]+)\s*=\s*[\"']?(?P<prefix>[A-Za-z0-9_.:-]*)$"
)
META_CONTEXT_RE = re.compile(
    r"^\s*(?P<key>[A-Za-z0-9_-]+)\s*:\s*(?P<prefix>[A-Za-z0-9_.:-]*)$"
)


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


def _span_range(span: SourceSpan) -> dict[str, object]:
    return {
        "start": {"line": span.line, "character": span.start},
        "end": {"line": span.line, "character": span.end},
    }


def _span_location(root: Path, span: SourceSpan) -> dict[str, object]:
    return {"uri": _uri(root / span.file), "range": _span_range(span)}


def _location(root: Path, location: LocationRecord) -> dict[str, object]:
    return {
        "uri": _uri(root / location.file),
        "range": _range(location.line),
    }


def _severity(value: str) -> int:
    return {"error": 1, "warning": 2, "info": 3}.get(value, 3)


def _identifier_in_text(text: str, line: int, character: int) -> str | None:
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return None
    source = lines[line]
    cursor = min(max(character, 0), len(source))
    for match in IDENTIFIER_RE.finditer(source):
        if match.start() <= cursor <= match.end():
            return match.group(0)
    return None


def _identifier_at(path: Path, line: int, character: int) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return _identifier_in_text(text, line, character)


def _type_on_need_line(source: str) -> str | None:
    for match in ATTR_RE.finditer(source):
        if match.group(1) != "type":
            continue
        return next(value for value in match.groups()[1:] if value is not None)
    return None


def _completion_context(
    text: str,
    line: int,
    character: int,
) -> tuple[str, set[str] | None, str | None, str | None]:
    """Return prefix, completion kinds, object type, and relation context."""
    lines = text.splitlines()
    if line < 0 or line >= len(lines):
        return "", None, None, None
    source = lines[line]
    cursor = min(max(character, 0), len(source))
    before = source[:cursor]
    value = VALUE_CONTEXT_RE.search(before)
    if value is not None:
        key = value.group("key")
        prefix = value.group("prefix")
        object_type = _type_on_need_line(source)
        if key == "type":
            return prefix, {"type"}, None, None
        if key == "status":
            return prefix, {"status"}, object_type, None
        if key in RELATION_KEYS:
            return prefix, {"object"}, object_type, key
        return prefix, set(), object_type, None

    meta = META_CONTEXT_RE.match(before)
    if meta is not None and meta.group("key") in RELATION_KEYS:
        return meta.group("prefix"), {"object"}, None, meta.group("key")

    identifier = _identifier_in_text(text, line, character)
    return identifier or "", None, _type_on_need_line(source), None


@dataclass
class LspSession:
    root: Path
    service: LanguageService
    shutdown_requested: bool = False
    documents: dict[str, str] = field(default_factory=dict)
    transient_findings: tuple[Finding, ...] = ()

    @classmethod
    def load(cls, root: Path) -> "LspSession":
        resolved = Path(root).resolve()
        return cls(resolved, LanguageService.load(resolved))

    def _overlays(self) -> dict[str, str]:
        overlays: dict[str, str] = {}
        for uri, text in self.documents.items():
            path = _path_from_uri(uri)
            try:
                relative = path.relative_to(self.root).as_posix()
            except ValueError:
                continue
            overlays[relative] = text
        return overlays

    def _index(self) -> Mapping[str, tuple[SourceSpan, ...]]:
        return build_source_index(self.root, overlays=self._overlays())

    def reload(self) -> bool:
        config = load_config(self.root)
        result = analyze_project(
            self.root,
            config=config,
            overlays=self._overlays(),
        )
        if result.snapshot is None:
            self.transient_findings = result.findings
            return False
        self.service = LanguageService(self.root, config, result.snapshot)
        self.transient_findings = ()
        return True

    def open_document(self, uri: str, text: str) -> bool:
        self.documents[uri] = text
        return self.reload()

    def change_document(self, uri: str, text: str) -> bool:
        self.documents[uri] = text
        return self.reload()

    def close_document(self, uri: str) -> bool:
        self.documents.pop(uri, None)
        return self.reload()

    def _document(self, params: Mapping[str, object]) -> tuple[str, Path]:
        document = params.get("textDocument")
        if not isinstance(document, Mapping) or not isinstance(document.get("uri"), str):
            raise ValueError("textDocument.uri is required")
        uri = str(document["uri"])
        return uri, _path_from_uri(uri)

    def _text(self, uri: str, path: Path) -> str:
        if uri in self.documents:
            return self.documents[uri]
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _identifier(self, uri: str, path: Path, line: int, character: int) -> str | None:
        text = self.documents.get(uri)
        if text is not None:
            return _identifier_in_text(text, line, character)
        return _identifier_at(path, line, character)

    def _semantic_span(
        self, uri: str, object_id: str, line: int, character: int
    ) -> SourceSpan | None:
        path = _path_from_uri(uri)
        try:
            relative = path.relative_to(self.root).as_posix()
        except ValueError:
            return None
        for span in self._index().get(object_id, ()):
            if span.file == relative and span.line == line and span.start <= character <= span.end:
                return span
        return None

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
        for finding in self.transient_findings:
            if finding.location is None or finding.location.file != relative:
                continue
            diagnostics.append(
                {
                    "range": _range(finding.location.line),
                    "severity": _severity(finding.severity),
                    "code": finding.code,
                    "source": "quarto-needs",
                    "message": finding.message,
                }
            )
        seen: set[tuple[object, ...]] = set()
        unique = []
        for diagnostic in diagnostics:
            key = (
                diagnostic["code"],
                diagnostic["message"],
                json.dumps(diagnostic["range"], sort_keys=True),
            )
            if key not in seen:
                seen.add(key)
                unique.append(diagnostic)
        return {"uri": uri, "diagnostics": unique}

    def handle(self, method: str, params: Mapping[str, object] | None) -> object:
        values: Mapping[str, object] = params or {}
        if method == "initialize":
            return {
                "capabilities": {
                    "textDocumentSync": {
                        "openClose": True,
                        "change": 1,
                        "save": {"includeText": False},
                    },
                    "completionProvider": {"triggerCharacters": ["#", "=", ":"]},
                    "hoverProvider": True,
                    "definitionProvider": True,
                    "referencesProvider": True,
                    "renameProvider": {"prepareProvider": True},
                    "documentSymbolProvider": True,
                    "workspaceSymbolProvider": True,
                },
                "serverInfo": {"name": "quarto-needs", "version": "0.1"},
            }
        if method == "shutdown":
            self.shutdown_requested = True
            return None
        if method == "textDocument/completion":
            uri, path = self._document(values)
            position = values.get("position")
            prefix = ""
            kinds: set[str] | None = None
            object_type = None
            relation = None
            if isinstance(position, Mapping):
                prefix, kinds, object_type, relation = _completion_context(
                    self._text(uri, path),
                    int(position.get("line", 0)),
                    int(position.get("character", 0)),
                )
            kind_map = {"object": 6, "type": 7, "relation": 10, "status": 12}
            return [
                {
                    "label": item.label,
                    "kind": kind_map.get(item.kind, 1),
                    "detail": item.detail,
                }
                for item in self.service.completions(
                    prefix,
                    kinds=kinds,
                    object_type=object_type,
                    relation=relation,
                )
            ]
        if method in {
            "textDocument/hover",
            "textDocument/definition",
            "textDocument/references",
            "textDocument/prepareRename",
            "textDocument/rename",
        }:
            uri, path = self._document(values)
            position = values.get("position")
            if not isinstance(position, Mapping):
                return None if method != "textDocument/references" else []
            line = int(position.get("line", 0))
            character = int(position.get("character", 0))
            object_id = self._identifier(uri, path, line, character)
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
                lines.append(
                    f"Relations: {hover.outgoing} outgoing, {hover.incoming} incoming"
                )
                return {"contents": {"kind": "markdown", "value": "\n".join(lines)}}

            spans = self._index().get(object_id, ())
            if method == "textDocument/definition":
                declaration = next(
                    (
                        span
                        for span in spans
                        if span.kind == "declaration" and not span.presentation_only
                    ),
                    None,
                )
                if declaration is not None:
                    return _span_location(self.root, declaration)
                definition = self.service.definition(object_id)
                return _location(self.root, definition) if definition else None

            if method == "textDocument/references":
                context = values.get("context")
                include_declaration = bool(
                    isinstance(context, Mapping) and context.get("includeDeclaration")
                )
                return [
                    _span_location(self.root, span)
                    for span in spans
                    if include_declaration or span.kind != "declaration"
                ]

            semantic_span = self._semantic_span(uri, object_id, line, character)
            if semantic_span is None or object_id not in self.service.snapshot.objects_by_id:
                return None
            if method == "textDocument/prepareRename":
                return {
                    "range": _span_range(semantic_span),
                    "placeholder": object_id,
                }

            new_name = values.get("newName")
            if not isinstance(new_name, str) or IDENTIFIER_RE.fullmatch(new_name) is None:
                raise ValueError("newName must be a valid Quarto-Needs identifier")
            if new_name != object_id and new_name in self.service.snapshot.objects_by_id:
                raise ValueError(f"Cannot rename {object_id} to existing object ID {new_name}")
            changes: dict[str, list[dict[str, object]]] = {}
            for span in spans:
                target_uri = _uri(self.root / span.file)
                changes.setdefault(target_uri, []).append(
                    {"range": _span_range(span), "newText": new_name}
                )
            return {"changes": changes}

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
                if (
                    needle
                    and needle not in symbol.object_id.casefold()
                    and needle not in symbol.title.casefold()
                ):
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


def _document_uri(params: object) -> str | None:
    if not isinstance(params, Mapping):
        return None
    document = params.get("textDocument")
    if not isinstance(document, Mapping) or not isinstance(document.get("uri"), str):
        return None
    return str(document["uri"])


def run_stdio(
    root: Path,
    instream: BinaryIO | None = None,
    outstream: BinaryIO | None = None,
) -> int:
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
        if method in {
            "textDocument/didOpen",
            "textDocument/didChange",
            "textDocument/didSave",
            "textDocument/didClose",
        }:
            uri = _document_uri(params)
            if uri is None:
                continue
            try:
                if method == "textDocument/didOpen":
                    document = params.get("textDocument") if isinstance(params, Mapping) else None
                    if isinstance(document, Mapping) and isinstance(document.get("text"), str):
                        session.open_document(uri, str(document["text"]))
                    else:
                        session.reload()
                elif method == "textDocument/didChange":
                    changes = params.get("contentChanges") if isinstance(params, Mapping) else None
                    if (
                        isinstance(changes, list)
                        and changes
                        and isinstance(changes[-1], Mapping)
                        and isinstance(changes[-1].get("text"), str)
                    ):
                        session.change_document(uri, str(changes[-1]["text"]))
                    else:
                        continue
                elif method == "textDocument/didClose":
                    session.close_document(uri)
                else:
                    session.reload()
                diagnostic_payload = (
                    {"uri": uri, "diagnostics": []}
                    if method == "textDocument/didClose"
                    else session.diagnostics_for_uri(uri)
                )
                _write_message(
                    output_stream,
                    {
                        "jsonrpc": "2.0",
                        "method": "textDocument/publishDiagnostics",
                        "params": diagnostic_payload,
                    },
                )
            except ValueError:
                continue
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
