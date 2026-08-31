from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .sphinx_needs import (
    MigratedRelation,
    MigrationIssue,
    SphinxNeedCandidate,
    SphinxNeedsMigrationPlan,
)

_BLOCK_OPEN_RE = re.compile(r"^\[(?P<tag>[A-Z_]+)\]$")
_COMPOSITE_OPEN_RE = re.compile(r"^\[\[(?P<tag>[A-Z_]+)\]\]$")
_COMPOSITE_CLOSE_RE = re.compile(r"^\[\[/(?P<tag>[A-Z_]+)\]\]$")
_FIELD_RE = re.compile(r"^(?P<key>[A-Z_]+):\s*(?P<value>.*)$")
_RELATION_TYPE_RE = re.compile(r"^-\s*TYPE:\s*(?P<value>.+)$")
_RELATION_FIELD_RE = re.compile(r"^\s+(?P<key>[A-Z_]+):\s*(?P<value>.+)$")

_CONSUMED_FIELDS = {"UID", "STATUS", "TITLE", "STATEMENT", "RATIONALE", "RELATIONS", "TAGS"}


class StrictDocMigrationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StrictDocItem:
    tag: str
    uid: str
    title: str
    status: str | None
    statement: str
    rationale: str
    tags: tuple[str, ...]
    relations: tuple[tuple[str, str], ...]
    non_uid_relations: tuple[Mapping[str, str], ...]
    extras: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class StrictDocDocument:
    title: str | None
    path: Path
    items: tuple[StrictDocItem, ...]


def _is_block_boundary(line: str) -> bool:
    return bool(
        _BLOCK_OPEN_RE.match(line)
        or _COMPOSITE_OPEN_RE.match(line)
        or _COMPOSITE_CLOSE_RE.match(line)
    )


def _iter_blocks(lines: Sequence[str]) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        open_match = _BLOCK_OPEN_RE.match(line) or _COMPOSITE_OPEN_RE.match(line)
        if not open_match:
            index += 1
            continue
        tag = open_match.group("tag")
        index += 1
        field_lines: list[str] = []
        while index < len(lines) and not _is_block_boundary(lines[index]):
            field_lines.append(lines[index])
            index += 1
        blocks.append((tag, field_lines))
    return blocks


def _parse_fields(field_lines: Sequence[str], *, path: Path) -> dict[str, object]:
    fields: dict[str, object] = {}
    index = 0
    while index < len(field_lines):
        line = field_lines[index]
        if not line.strip():
            index += 1
            continue
        match = _FIELD_RE.match(line)
        if not match:
            # Nested sub-structure of a field this adapter never consumes
            # (e.g. [DOCUMENT]'s OPTIONS, [GRAMMAR]'s ELEMENTS) — StrictDoc's
            # grammar is fully custom per project and this adapter only
            # needs the fixed engineering fields handled below.
            index += 1
            continue
        key, value = match.group("key"), match.group("value")
        index += 1
        if key == "RELATIONS":
            # Each entry is `- TYPE: <type>` followed by zero or more indented
            # sub-fields. A UID-addressed relation (e.g. Parent) carries
            # VALUE; a file-addressed relation (TYPE: File) carries FORMAT/
            # PATH instead and has no UID to resolve — both shapes occur in
            # real StrictDoc projects, so every sub-field is captured and
            # only presence of VALUE decides whether it becomes a candidate
            # relation.
            raw_relations: list[dict[str, str]] = []
            while index < len(field_lines):
                type_match = _RELATION_TYPE_RE.match(field_lines[index])
                if not type_match:
                    break
                entry = {"TYPE": type_match.group("value").strip()}
                index += 1
                while index < len(field_lines):
                    field_match = _RELATION_FIELD_RE.match(field_lines[index])
                    if not field_match:
                        break
                    entry[field_match.group("key")] = field_match.group("value").strip()
                    index += 1
                raw_relations.append(entry)
            fields["RELATIONS"] = tuple(raw_relations)
            continue
        if value == ">>>":
            body_lines: list[str] = []
            while index < len(field_lines) and field_lines[index].strip() != "<<<":
                body_lines.append(field_lines[index])
                index += 1
            if index == len(field_lines):
                raise StrictDocMigrationError(f"{path}: unterminated multi-line field {key!r}")
            index += 1
            fields[key] = "\n".join(body_lines).strip()
            continue
        fields[key] = value.strip()
    return fields


def _load_document(path: Path) -> StrictDocDocument:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks = _iter_blocks(lines)

    document_title: str | None = None
    items: list[StrictDocItem] = []
    for tag, field_lines in blocks:
        if tag == "GRAMMAR":
            # A per-project schema declaration (custom node TAGs, FIELDS,
            # and allowed RELATIONS TYPEs) — never a migration candidate,
            # and its own "- TYPE: Parent" entries have no VALUE, which
            # would otherwise look like a malformed relation instance.
            continue
        fields = _parse_fields(field_lines, path=path)
        if tag == "DOCUMENT":
            title = fields.get("TITLE")
            document_title = str(title) if isinstance(title, str) else None
            continue
        uid = fields.get("UID")
        if not isinstance(uid, str) or not uid.strip():
            continue

        raw_tags = fields.get("TAGS")
        tags = (
            tuple(part.strip() for part in str(raw_tags).split(",") if part.strip())
            if raw_tags
            else ()
        )
        raw_relations = fields.get("RELATIONS") or ()
        relations = tuple(
            (entry["TYPE"], entry["VALUE"]) for entry in raw_relations if "VALUE" in entry
        )
        non_uid_relations = tuple(entry for entry in raw_relations if "VALUE" not in entry)
        status = fields.get("STATUS")
        extras = {
            key: value for key, value in fields.items() if key not in _CONSUMED_FIELDS
        }

        items.append(
            StrictDocItem(
                tag=tag,
                uid=uid.strip(),
                title=str(fields.get("TITLE", "")).strip(),
                status=str(status).strip() if isinstance(status, str) else None,
                statement=str(fields.get("STATEMENT", "")).strip(),
                rationale=str(fields.get("RATIONALE", "")).strip(),
                tags=tags,
                relations=relations,
                non_uid_relations=non_uid_relations,
                extras=extras,
            )
        )

    return StrictDocDocument(title=document_title, path=path, items=tuple(items))


def load_strictdoc_documents(root: Path) -> tuple[StrictDocDocument, ...]:
    """Load every ``.sdoc`` file under ``root`` as a StrictDoc document.

    Only blocks that carry an explicit, non-empty ``UID`` become migration
    candidates; ``[TEXT]``/``[[SECTION]]`` prose blocks without one are
    structural presentation and are not migrated. This reads only the on-disk
    SDoc text; it never executes StrictDoc.
    """
    return tuple(_load_document(path) for path in sorted(root.rglob("*.sdoc")))


def build_migration_plan(
    documents: Sequence[StrictDocDocument],
    *,
    type_map: Mapping[str, str] | None = None,
    relation_map: Mapping[str, str] | None = None,
) -> SphinxNeedsMigrationPlan:
    """Build a conservative migration plan from a loaded StrictDoc document set.

    A StrictDoc item's ``[TAG]`` (e.g. ``REQUIREMENT``) is its source type,
    and each relation's authored ``TYPE`` (e.g. ``Parent``) is the field
    ``relation_map`` is keyed by — UIDs are authored explicitly and globally
    unique across the whole project, not derived from file structure.
    """
    types = dict(type_map or {})
    relations_config = dict(relation_map or {})

    all_items: dict[str, tuple[StrictDocDocument, StrictDocItem]] = {}
    for document in documents:
        for item in document.items:
            if item.uid in all_items:
                other_document, _ = all_items[item.uid]
                raise StrictDocMigrationError(
                    f"StrictDoc item {item.uid} is defined in both "
                    f"{other_document.path} and {document.path}"
                )
            all_items[item.uid] = (document, item)

    candidates: list[SphinxNeedCandidate] = []
    issues: list[MigrationIssue] = []
    for document, item in sorted(all_items.values(), key=lambda pair: pair[1].uid):
        target_type = types.get(item.tag)
        if target_type is None:
            issues.append(
                MigrationIssue(
                    code="TYPE_UNMAPPED",
                    message=f"StrictDoc tag {item.tag!r} has no explicit type mapping",
                    need_id=item.uid,
                    field=item.tag,
                )
            )

        content = item.statement
        if item.rationale:
            content = f"{content}\n\n### Rationale\n\n{item.rationale}" if content else (
                f"### Rationale\n\n{item.rationale}"
            )

        migrated_relations: list[MigratedRelation] = []
        unmapped: dict[str, list[str]] = {}
        for relation_type, target in item.relations:
            canonical_relation = relations_config.get(relation_type)
            if canonical_relation is None:
                unmapped.setdefault(relation_type, []).append(target)
                issues.append(
                    MigrationIssue(
                        code="RELATION_UNMAPPED",
                        message=(
                            f"StrictDoc relation TYPE {relation_type!r} has no "
                            "explicit relation mapping"
                        ),
                        need_id=item.uid,
                        field=relation_type,
                    )
                )
                continue
            if target not in all_items:
                issues.append(
                    MigrationIssue(
                        code="EXTERNAL_LINK_TARGET",
                        message=(
                            f"StrictDoc item {item.uid} links to {target!r}, "
                            "which is not defined anywhere in the loaded project"
                        ),
                        need_id=item.uid,
                        field=target,
                    )
                )
                continue
            migrated_relations.append(
                MigratedRelation(
                    source=item.uid,
                    relation=canonical_relation,
                    target=target,
                    source_field=relation_type,
                )
            )

        extras = dict(sorted(item.extras.items()))
        if item.non_uid_relations:
            # Relations addressed by something other than a UID (e.g.
            # TYPE: File, addressed by PATH) cannot resolve against the
            # canonical graph's ID space; preserve them rather than drop
            # them silently.
            extras["nonUidRelations"] = [dict(sorted(entry.items())) for entry in item.non_uid_relations]

        candidates.append(
            SphinxNeedCandidate(
                source_id=item.uid,
                source_type=item.tag,
                target_type=target_type,
                title=item.title or item.uid,
                content=content,
                status=item.status,
                tags=item.tags,
                relations=tuple(
                    sorted(migrated_relations, key=lambda relation: (relation.relation, relation.target))
                ),
                unmapped_links={key: tuple(values) for key, values in sorted(unmapped.items())},
                extras=extras,
            )
        )

    return SphinxNeedsMigrationPlan(
        source_project=documents[0].title if documents else None,
        source_version="n/a",
        candidates=tuple(candidates),
        issues=tuple(
            sorted(
                issues,
                key=lambda issue: (issue.need_id or "", issue.code, issue.field or "", issue.message),
            )
        ),
        tool="StrictDoc",
        schema="strictdoc-migration-plan-v1",
    )
