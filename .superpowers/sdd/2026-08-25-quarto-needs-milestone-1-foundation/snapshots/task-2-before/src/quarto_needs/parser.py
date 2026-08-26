from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .model import EngineeringObject, Relation, SourceLocation

OPEN_RE = re.compile(r'^\s*:::\s*\{\.need\s+#(?P<id>[A-Za-z0-9_.:-]+)(?P<attrs>[^}]*)\}\s*$')
ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)=(?:"([^"]*)"|\'([^\']*)\'|([^\s]+))')
HEADING_RE = re.compile(r'^##+\s+(?P<title>.+?)\s*$')
META_RE = re.compile(r'^(?P<key>[A-Za-z0-9_-]+):\s*(?P<value>.*)$')
LIST_RE = re.compile(r'^\s*-\s+(?P<value>.+?)\s*$')

RELATION_KEYS = {
    "derives-from", "derived-from", "refines", "decomposes", "depends-on",
    "conflicts-with", "constrains", "implements", "implemented-by",
    "verified-by", "validated-by", "mitigates", "justified-by", "evidenced-by",
    "references",
}
ALIASES = {"derived-from": "derives-from", "implemented-by": "implemented-by", "references": "references"}


def _parse_attrs(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in ATTR_RE.finditer(raw):
        out[m.group(1)] = next(v for v in m.groups()[1:] if v is not None)
    return out


def _collect_metadata(lines: list[str]) -> tuple[dict[str, object], int]:
    """Parse the simple YAML-like preamble used inside a .need block.

    Supports scalar values and lists of scalar values. The parser deliberately
    stays conservative; richer authoring can be added later without making the
    Quarto filter the canonical parser.
    """
    meta: dict[str, object] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if HEADING_RE.match(line):
            break
        m = META_RE.match(line)
        if not m:
            break
        key, value = m.group("key"), m.group("value").strip()
        if value:
            meta[key] = value
            i += 1
            continue
        values: list[str] = []
        j = i + 1
        while j < len(lines):
            lm = LIST_RE.match(lines[j])
            if not lm:
                break
            values.append(lm.group("value"))
            j += 1
        meta[key] = values
        i = j
    return meta, i


def parse_qmd(path: Path, root: Path | None = None) -> list[EngineeringObject]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    objects: list[EngineeringObject] = []
    i = 0
    while i < len(lines):
        m = OPEN_RE.match(lines[i])
        if not m:
            i += 1
            continue
        start_line = i + 1
        need_id = m.group("id")
        attrs = _parse_attrs(m.group("attrs"))
        block: list[str] = []
        i += 1
        while i < len(lines) and lines[i].strip() != ":::":
            block.append(lines[i])
            i += 1
        meta, body_start = _collect_metadata(block)
        merged: dict[str, object] = {**attrs, **meta}

        title = str(merged.pop("title", "")).strip()
        title_index: int | None = None
        if not title:
            for idx, line in enumerate(block[body_start:], start=body_start):
                hm = HEADING_RE.match(line)
                if hm:
                    title = hm.group("title").strip()
                    title_index = idx
                    break
        if not title:
            title = need_id

        rationale = str(merged.pop("rationale", "")).strip()
        body_lines = block[body_start:]
        if title_index is not None:
            body_lines = block[title_index + 1:]
        body = "\n".join(body_lines).strip()

        relations: list[Relation] = []
        attributes: dict[str, object] = {}
        for key, value in merged.items():
            if key in {"type", "status"}:
                continue
            if key in RELATION_KEYS:
                rel_type = ALIASES.get(key, key)
                targets = value if isinstance(value, list) else [value]
                relations.extend(Relation(rel_type, need_id, str(t)) for t in targets if str(t).strip())
            else:
                attributes[key] = value

        relative = path if root is None else path.relative_to(root)
        obj = EngineeringObject(
            id=need_id,
            type=str(merged.get("type", "need")),
            title=title,
            status=str(merged.get("status", "draft")),
            body=body,
            rationale=rationale,
            attributes=attributes,
            relations=relations,
            source=SourceLocation(file=relative.as_posix(), line=start_line, anchor=need_id),
        )
        objects.append(obj)
        i += 1
    return objects


def parse_project(root: Path, files: Iterable[Path] | None = None) -> list[EngineeringObject]:
    if files is None:
        files = (
            p for p in root.rglob("*.qmd")
            if not any(part.startswith(".") or part.startswith("_") for part in p.relative_to(root).parts[:-1])
        )
    objects: list[EngineeringObject] = []
    for path in files:
        objects.extend(parse_qmd(path, root))
    return objects
