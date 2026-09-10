"""Exact source spans for authored Quarto-Needs object identifiers.

The index recognizes only syntactic positions where object IDs are meaningful:
need declarations, configured relation targets in .need attributes/metadata,
and ``need`` shortcodes. It deliberately does not replace arbitrary body text.

Unlike canonical project analysis, the refactor index intentionally includes
localized ``*.pt-BR.qmd``-style siblings. Localization remains presentation-only,
but an ID rename must update every presentation of that canonical identity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .parser import (
    ATTR_RE,
    LIST_RE,
    LOCALIZED_QMD_RE,
    META_RE,
    OPEN_RE,
    RELATION_KEYS,
)

SHORTCODE_RE = re.compile(
    r"\{\{<\s*need\s+(?P<id>[A-Za-z0-9_.:-]+)(?:\s+[^>]*)?>\}\}"
)
TOKEN_RE = re.compile(r"[A-Za-z0-9_.:-]+")


@dataclass(frozen=True, slots=True)
class SourceSpan:
    file: str
    line: int  # zero-based LSP line
    start: int
    end: int
    kind: str  # declaration | relation | shortcode
    presentation_only: bool = False


def _sources(root: Path, overlays: Mapping[str, str] | None) -> dict[str, str]:
    resolved = root.resolve()
    sources: dict[str, str] = {}
    for path in sorted(resolved.rglob("*.qmd")):
        relative = path.relative_to(resolved)
        if any(part.startswith(".") or part.startswith("_") for part in relative.parts[:-1]):
            continue
        sources[relative.as_posix()] = path.read_text(encoding="utf-8")
    for name, text in (overlays or {}).items():
        path = Path(name)
        absolute = path.resolve() if path.is_absolute() else (resolved / path).resolve()
        if not absolute.is_relative_to(resolved) or absolute.suffix != ".qmd":
            continue
        sources[absolute.relative_to(resolved).as_posix()] = text
    return sources


def _presentation_only(root: Path, file: str) -> bool:
    path = root.resolve() / file
    match = LOCALIZED_QMD_RE.match(path.name)
    if match is None:
        return False
    canonical = path.with_name(f"{match.group('stem')}.qmd")
    return canonical.is_file()


def _value_group(match: re.Match[str]) -> tuple[str, int] | None:
    for group in (2, 3, 4):
        value = match.group(group)
        if value is not None:
            return value, match.start(group)
    return None


def _relation_tokens(value: str, base: int) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    for match in TOKEN_RE.finditer(value):
        tokens.append((match.group(0), base + match.start(), base + match.end()))
    return tokens


def build_source_index(
    root: Path,
    *,
    overlays: Mapping[str, str] | None = None,
) -> Mapping[str, tuple[SourceSpan, ...]]:
    by_id: dict[str, list[SourceSpan]] = {}
    for file, text in sorted(_sources(root, overlays).items()):
        presentation_only = _presentation_only(root, file)
        lines = text.splitlines()
        in_need = False
        active_list_relation: str | None = None
        for line_no, line in enumerate(lines):
            opening = OPEN_RE.match(line)
            if opening is not None:
                in_need = True
                active_list_relation = None
                object_id = opening.group("id")
                start = line.index(f"#{object_id}") + 1
                by_id.setdefault(object_id, []).append(
                    SourceSpan(
                        file,
                        line_no,
                        start,
                        start + len(object_id),
                        "declaration",
                        presentation_only,
                    )
                )
                attrs = opening.group("attrs")
                attrs_start = opening.start("attrs")
                for attr in ATTR_RE.finditer(attrs):
                    key = attr.group(1)
                    if key not in RELATION_KEYS:
                        continue
                    selected = _value_group(attr)
                    if selected is None:
                        continue
                    value, local_base = selected
                    for target, start_rel, end_rel in _relation_tokens(
                        value, attrs_start + local_base
                    ):
                        by_id.setdefault(target, []).append(
                            SourceSpan(
                                file,
                                line_no,
                                start_rel,
                                end_rel,
                                "relation",
                                presentation_only,
                            )
                        )
            elif in_need and line.strip() == ":::":
                in_need = False
                active_list_relation = None
            elif in_need:
                metadata = META_RE.match(line)
                if metadata is not None:
                    key = metadata.group("key")
                    value = metadata.group("value")
                    active_list_relation = key if key in RELATION_KEYS and not value.strip() else None
                    if key in RELATION_KEYS and value.strip():
                        base = metadata.start("value")
                        for target, start, end in _relation_tokens(value, base):
                            by_id.setdefault(target, []).append(
                                SourceSpan(
                                    file,
                                    line_no,
                                    start,
                                    end,
                                    "relation",
                                    presentation_only,
                                )
                            )
                elif active_list_relation is not None:
                    list_item = LIST_RE.match(line)
                    if list_item is not None:
                        value = list_item.group("value")
                        base = list_item.start("value")
                        for target, start, end in _relation_tokens(value, base):
                            by_id.setdefault(target, []).append(
                                SourceSpan(
                                    file,
                                    line_no,
                                    start,
                                    end,
                                    "relation",
                                    presentation_only,
                                )
                            )
                    elif line.strip():
                        active_list_relation = None

            for shortcode in SHORTCODE_RE.finditer(line):
                object_id = shortcode.group("id")
                by_id.setdefault(object_id, []).append(
                    SourceSpan(
                        file,
                        line_no,
                        shortcode.start("id"),
                        shortcode.end("id"),
                        "shortcode",
                        presentation_only,
                    )
                )

    return {
        object_id: tuple(
            sorted(
                spans,
                key=lambda item: (
                    item.presentation_only,
                    item.file.casefold(),
                    item.file,
                    item.line,
                    item.start,
                ),
            )
        )
        for object_id, spans in sorted(by_id.items())
    }
