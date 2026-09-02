from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Mapping, cast

from .diagnostics import Finding
from .model import EngineeringObject, Relation, SourceLocation
from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import (
    DeclarationBatch,
    LocationRecord,
    ObjectDeclaration,
    RelationToken,
    thaw_json,
)

OPEN_RE = re.compile(
    r'^\s*:::\s*\{\.need\s+#(?P<id>[A-Za-z0-9_.:-]+)(?P<attrs>[^}]*)\}\s*$'
)
ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)=(?:"([^"]*)"|\'([^\']*)\'|([^\s]+))')
HEADING_RE = re.compile(r'^##+\s+(?P<title>.+?)\s*$')
META_RE = re.compile(r'^(?P<key>[A-Za-z0-9_-]+):\s*(?P<value>.*)$')
LIST_RE = re.compile(r'^\s*-\s+(?P<value>.+?)\s*$')
LOCALIZED_QMD_RE = re.compile(
    r'^(?P<stem>.+)\.(?P<locale>[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)\.qmd$'
)

RELATION_KEYS = set(DEFAULT_RELATION_CATALOG.names)
RATIONALE_HEADING_RE = re.compile(r'^###\s+(?:Rationale|Justificativa)\s*$')


def _parse_attrs(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in ATTR_RE.finditer(raw):
        out[match.group(1)] = next(
            value for value in match.groups()[1:] if value is not None
        )
    return out


def _collect_metadata(
    lines: list[str],
) -> tuple[dict[str, object], dict[str, int], int]:
    """Parse the simple YAML-like preamble used inside a .need block."""
    meta: dict[str, object] = {}
    offsets: dict[str, int] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if HEADING_RE.match(line):
            break
        match = META_RE.match(line)
        if not match:
            break
        key, value = match.group("key"), match.group("value").strip()
        offsets[key] = i
        if value:
            meta[key] = value
            i += 1
            continue
        values: list[str] = []
        j = i + 1
        while j < len(lines):
            list_match = LIST_RE.match(lines[j])
            if not list_match:
                break
            values.append(list_match.group("value"))
            j += 1
        meta[key] = values
        i = j
    return meta, offsets, i


def _source_file(path: Path, root: Path | None) -> str:
    relative = path if root is None else path.relative_to(root)
    return relative.as_posix()


def _relation_targets(value: object) -> list[str]:
    """Normalize scalar/list relation syntax into individual graph endpoints."""
    values = value if isinstance(value, list) else [value]
    targets: list[str] = []
    for item in values:
        for target in re.split(r"[;,]", str(item)):
            normalized = target.strip()
            if normalized:
                targets.append(normalized)
    return targets


def _extract_rationale(body: str) -> str:
    """Return the text under a ``### Rationale`` body heading, if any.

    The authoring manual keeps human explanations in Markdown while
    machine-queryable metadata lives in the preamble, and validation
    accepts this heading as a requirement's rationale. This indexes that
    prose into the ``rationale`` field so diff, baseline, and export see
    it; the body is never modified — it stays the authored text verbatim.
    Only the first heading counts, and the section ends at the next
    heading of any level.
    """
    lines = body.split("\n")
    for index, line in enumerate(lines):
        if not RATIONALE_HEADING_RE.match(line):
            continue
        collected: list[str] = []
        for candidate in lines[index + 1:]:
            if HEADING_RE.match(candidate):
                break
            collected.append(candidate)
        return "\n".join(collected).strip()
    return ""


def parse_qmd_text_declarations(text: str, source_file: str) -> DeclarationBatch:
    """Parse one QMD source buffer using the canonical .need grammar."""
    lines = text.splitlines()
    declarations: list[ObjectDeclaration] = []
    findings: list[Finding] = []
    i = 0
    while i < len(lines):
        match = OPEN_RE.match(lines[i])
        if not match:
            i += 1
            continue
        start_line = i + 1
        need_id = match.group("id")
        attrs = _parse_attrs(match.group("attrs"))
        block: list[str] = []
        i += 1
        while i < len(lines) and lines[i].strip() != ":::":
            block.append(lines[i])
            i += 1
        location = LocationRecord(source_file, start_line, need_id)
        if i == len(lines):
            findings.append(Finding(
                "QND001",
                "error",
                f"Unclosed .need block: {need_id}",
                need_id,
                location,
            ))
            break

        meta, meta_offsets, body_start = _collect_metadata(block)
        merged: dict[str, object] = {**attrs, **meta}

        title = str(merged.pop("title", "")).strip()
        title_index: int | None = None
        if not title:
            for index, line in enumerate(block[body_start:], start=body_start):
                if RATIONALE_HEADING_RE.match(line):
                    continue
                heading_match = HEADING_RE.match(line)
                if heading_match:
                    title = heading_match.group("title").strip()
                    title_index = index
                    break
        if not title:
            title = need_id

        rationale = str(merged.pop("rationale", "")).strip()
        body_lines = block[body_start:]
        if title_index is not None:
            body_lines = block[title_index + 1:]
        body = "\n".join(body_lines).strip()
        if not rationale:
            rationale = _extract_rationale(body)

        relations: list[RelationToken] = []
        attributes: dict[str, object] = {}
        for key, value in merged.items():
            if key in {"type", "status"}:
                continue
            if key in RELATION_KEYS:
                targets = _relation_targets(value)
                if not targets:
                    findings.append(Finding(
                        "QND002",
                        "error",
                        f"Relation {key} on {need_id} has no targets",
                        need_id,
                        location,
                    ))
                    continue
                relation_line = (
                    start_line + 1 + meta_offsets[key]
                    if key in meta_offsets
                    else start_line
                )
                relation_location = LocationRecord(
                    source_file,
                    relation_line,
                    need_id,
                )
                relations.extend(
                    RelationToken(key, target, {}, relation_location)
                    for target in targets
                )
            else:
                attributes[key] = value

        declarations.append(ObjectDeclaration(
            id=need_id,
            type=str(merged.get("type", "need")),
            title=title,
            status=str(merged.get("status", "draft")),
            body=body,
            rationale=rationale,
            attributes=attributes,
            relations=tuple(relations),
            location=location,
        ))
        i += 1
    return DeclarationBatch(tuple(declarations), tuple(findings))


def parse_qmd_declarations(
    path: Path,
    root: Path | None = None,
) -> DeclarationBatch:
    return parse_qmd_text_declarations(
        path.read_text(encoding="utf-8"), _source_file(path, root)
    )


def _resolved_project_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    resolved = path.resolve()
    if resolved.is_relative_to(root):
        return resolved
    return (root / path).resolve()


def _is_localized_qmd(path: Path) -> bool:
    """Return whether *path* is a BabelQuarto-style localized sibling."""
    match = LOCALIZED_QMD_RE.match(path.name)
    if match is None:
        return False
    canonical = path.with_name(f"{match.group('stem')}.qmd")
    return canonical.is_file()


def _overlay_paths(
    root: Path, overlays: Mapping[str, str] | None
) -> dict[Path, str]:
    resolved: dict[Path, str] = {}
    for name, text in (overlays or {}).items():
        path = Path(name)
        absolute = path.resolve() if path.is_absolute() else (root / path).resolve()
        if not absolute.is_relative_to(root):
            raise ValueError(f"overlay path escapes project root: {name}")
        if absolute.suffix == ".qmd":
            resolved[absolute] = text
    return resolved


def parse_project_declarations(
    root: Path,
    files: Iterable[Path] | None = None,
    *,
    overlays: Mapping[str, str] | None = None,
) -> DeclarationBatch:
    resolved_root = root.resolve()
    overlay_by_path = _overlay_paths(resolved_root, overlays)
    if files is None:
        discovered = {
            path
            for path in resolved_root.rglob("*.qmd")
            if not any(
                part.startswith(".") or part.startswith("_")
                for part in path.relative_to(resolved_root).parts[:-1]
            )
            and not _is_localized_qmd(path)
        }
        discovered.update(overlay_by_path)
        files = discovered
    paths = [_resolved_project_path(resolved_root, Path(path)) for path in files]
    paths = list(dict.fromkeys(paths))
    paths.sort(
        key=lambda path: (
            path.relative_to(resolved_root).as_posix().casefold(),
            path.relative_to(resolved_root).as_posix(),
        )
    )

    declarations: list[ObjectDeclaration] = []
    findings: list[Finding] = []
    for path in paths:
        if path in overlay_by_path:
            batch = parse_qmd_text_declarations(
                overlay_by_path[path], path.relative_to(resolved_root).as_posix()
            )
        else:
            batch = parse_qmd_declarations(path, resolved_root)
        declarations.extend(batch.declarations)
        findings.extend(batch.findings)
    declarations.sort(key=lambda item: (
        item.location.file.casefold() if item.location else "",
        item.location.file if item.location else "",
        item.location.line if item.location else 0,
        item.id.casefold(),
        item.id,
    ))
    return DeclarationBatch(tuple(declarations), tuple(findings))


def _legacy_object(declaration: ObjectDeclaration) -> EngineeringObject:
    """Compatibility adapter: canonical declaration -> legacy DTO.

    Exists only for the legacy constructors below; the canonical analyzer
    never converts declarations back into legacy objects.
    """
    relations: list[Relation] = []
    for token in declaration.relations:
        kind = DEFAULT_RELATION_CATALOG.resolve(token.authored_name)
        relations.append(Relation(
            type=kind.v1_name,
            source=declaration.id,
            target=token.target,
            attributes=cast(dict[str, object], thaw_json(token.attributes)),
            authored_name=token.authored_name,
        ))
    source = (
        SourceLocation(
            declaration.location.file,
            declaration.location.line,
            declaration.location.anchor,
        )
        if declaration.location is not None
        else None
    )
    return EngineeringObject(
        id=declaration.id,
        type=declaration.type,
        title=declaration.title,
        status=declaration.status,
        body=declaration.body,
        rationale=declaration.rationale,
        attributes=cast(dict[str, object], thaw_json(declaration.attributes)),
        relations=relations,
        source=source,
    )


def parse_qmd(path: Path, root: Path | None = None) -> list[EngineeringObject]:
    """Compatibility constructor over the canonical declaration parser.

    Parses through the canonical pipeline and adapts the result into legacy
    DTOs for external convenience; no canonical analysis path uses it.
    """
    return [
        _legacy_object(declaration)
        for declaration in parse_qmd_declarations(path, root).declarations
    ]


def parse_project(
    root: Path,
    files: Iterable[Path] | None = None,
    *,
    overlays: Mapping[str, str] | None = None,
) -> list[EngineeringObject]:
    """Compatibility constructor over the canonical declaration parser.

    Legacy counterpart of :func:`parse_project_declarations`; tests and
    external convenience callers consume the legacy DTOs, while canonical
    analysis consumes the declarations directly.
    """
    objects = [
        _legacy_object(declaration)
        for declaration in parse_project_declarations(
            root, files, overlays=overlays
        ).declarations
    ]
    objects.sort(key=lambda item: (
        item.id.casefold(),
        item.id,
        item.source.file if item.source else "",
        item.source.line if item.source else 0,
    ))
    return objects
