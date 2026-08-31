from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from .sphinx_needs import (
    MigratedRelation,
    MigrationIssue,
    SphinxNeedCandidate,
    SphinxNeedsMigrationPlan,
)

_CONSUMED_ITEM_FIELDS = {"header", "text", "links", "reviewed"}
_PRESERVED_EXTRA_FIELDS = {"active", "derived", "normative", "ref", "level"}


class DoorstopMigrationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DoorstopItem:
    uid: str
    header: str
    text: str
    links: tuple[str, ...]
    extras: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class DoorstopDocument:
    prefix: str
    parent: str | None
    path: Path
    items: tuple[DoorstopItem, ...]


def _load_yaml_mapping(path: Path) -> Mapping[str, object]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise DoorstopMigrationError(f"cannot read Doorstop YAML {path}: {error}") from error
    if not isinstance(raw, Mapping):
        raise DoorstopMigrationError(f"Doorstop YAML {path} must contain a mapping")
    return raw


def _link_targets(value: object, *, item_path: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise DoorstopMigrationError(f"Doorstop item {item_path} has a non-list 'links' field")
    targets: list[str] = []
    for entry in value:
        if isinstance(entry, Mapping):
            if len(entry) != 1:
                raise DoorstopMigrationError(
                    f"Doorstop item {item_path} has a malformed link entry: {entry!r}"
                )
            targets.append(str(next(iter(entry))))
        else:
            targets.append(str(entry))
    return tuple(targets)


def _load_item(path: Path) -> DoorstopItem:
    raw = _load_yaml_mapping(path)
    header = raw.get("header") or ""
    if not isinstance(header, str):
        raise DoorstopMigrationError(f"Doorstop item {path} has a non-string 'header'")
    text = raw.get("text") or ""
    if not isinstance(text, str):
        raise DoorstopMigrationError(f"Doorstop item {path} has a non-string 'text'")
    links = _link_targets(raw.get("links"), item_path=path)
    extras = {
        key: value
        for key, value in raw.items()
        if key in _PRESERVED_EXTRA_FIELDS or key not in _CONSUMED_ITEM_FIELDS
    }
    return DoorstopItem(
        uid=path.stem,
        header=header.strip(),
        text=text.strip(),
        links=links,
        extras=extras,
    )


def load_doorstop_documents(root: Path) -> tuple[DoorstopDocument, ...]:
    """Load every Doorstop document (a directory anchored by ``.doorstop.yml``) under ``root``.

    Item identity comes from the filename (its UID), not from a field inside
    the file, matching how Doorstop itself addresses items. This reads only
    the on-disk document tree; it never executes Doorstop or arbitrary Python.
    """
    documents: list[DoorstopDocument] = []
    for config_path in sorted(root.rglob(".doorstop.yml")):
        raw = _load_yaml_mapping(config_path)
        settings = raw.get("settings")
        if not isinstance(settings, Mapping):
            raise DoorstopMigrationError(f"{config_path} is missing a 'settings' mapping")
        prefix = settings.get("prefix")
        if not isinstance(prefix, str) or not prefix.strip():
            raise DoorstopMigrationError(f"{config_path} is missing a non-empty 'settings.prefix'")
        parent = settings.get("parent")
        if parent is not None and not isinstance(parent, str):
            raise DoorstopMigrationError(f"{config_path} has a non-string 'settings.parent'")

        document_dir = config_path.parent
        items = tuple(
            _load_item(item_path)
            for item_path in sorted(document_dir.glob("*.yml"))
            if item_path.name != ".doorstop.yml"
        )
        documents.append(
            DoorstopDocument(prefix=prefix.strip(), parent=parent, path=document_dir, items=items)
        )
    return tuple(documents)


def build_migration_plan(
    documents: Sequence[DoorstopDocument],
    *,
    type_map: Mapping[str, str] | None = None,
    relation_map: Mapping[str, str] | None = None,
) -> SphinxNeedsMigrationPlan:
    """Build a conservative migration plan from a loaded Doorstop document tree.

    A document's ``prefix`` (not a per-item field) is the only source-type
    signal Doorstop items carry, so ``type_map``/``relation_map`` are keyed by
    prefix rather than by an authored field name.
    """
    types = dict(type_map or {})
    relations = dict(relation_map or {})

    all_items: dict[str, tuple[DoorstopDocument, DoorstopItem]] = {}
    for document in documents:
        for item in document.items:
            if item.uid in all_items:
                other_document, _ = all_items[item.uid]
                raise DoorstopMigrationError(
                    f"Doorstop item {item.uid} is defined in both "
                    f"{other_document.path} and {document.path}"
                )
            all_items[item.uid] = (document, item)

    candidates: list[SphinxNeedCandidate] = []
    issues: list[MigrationIssue] = []
    for document, item in sorted(all_items.values(), key=lambda pair: pair[1].uid):
        target_type = types.get(document.prefix)
        if target_type is None:
            issues.append(
                MigrationIssue(
                    code="TYPE_UNMAPPED",
                    message=f"Doorstop document prefix {document.prefix!r} has no explicit type mapping",
                    need_id=item.uid,
                    field=document.prefix,
                )
            )

        title = item.header if item.header else item.uid

        migrated_relations: list[MigratedRelation] = []
        unmapped_targets: list[str] = []
        canonical_relation = relations.get(document.prefix)
        for target in item.links:
            if canonical_relation is None:
                unmapped_targets.append(target)
                continue
            if target not in all_items:
                issues.append(
                    MigrationIssue(
                        code="EXTERNAL_LINK_TARGET",
                        message=(
                            f"Doorstop item {item.uid} links to {target!r}, "
                            "which is not defined in the loaded document tree"
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
                    source_field="links",
                )
            )
        if canonical_relation is None and item.links:
            issues.append(
                MigrationIssue(
                    code="RELATION_UNMAPPED",
                    message=(
                        f"Doorstop document prefix {document.prefix!r} has no explicit "
                        "relation mapping for its 'links' field"
                    ),
                    need_id=item.uid,
                    field=document.prefix,
                )
            )

        candidates.append(
            SphinxNeedCandidate(
                source_id=item.uid,
                source_type=document.prefix,
                target_type=target_type,
                title=title,
                content=item.text,
                status=None,
                tags=(),
                relations=tuple(
                    sorted(migrated_relations, key=lambda relation: (relation.relation, relation.target))
                ),
                unmapped_links=(
                    {document.prefix: tuple(unmapped_targets)} if unmapped_targets else {}
                ),
                extras=dict(sorted(item.extras.items())),
            )
        )

    return SphinxNeedsMigrationPlan(
        source_project=None,
        source_version="n/a",
        candidates=tuple(candidates),
        issues=tuple(
            sorted(
                issues,
                key=lambda issue: (issue.need_id or "", issue.code, issue.field or "", issue.message),
            )
        ),
        tool="Doorstop",
        schema="doorstop-migration-plan-v1",
    )
