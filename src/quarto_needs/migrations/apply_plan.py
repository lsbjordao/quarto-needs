from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Mapping

from ..config import NeedsConfig
from ..relations import DEFAULT_RELATION_CATALOG
from ..snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord
from .render import (
    authorable_extras,
    need_block_problems,
    render_need_block,
    source_tool_slug,
)
from .sphinx_needs import SphinxNeedCandidate, SphinxNeedsMigrationPlan

ApplyStatus = Literal["ready-create", "blocked", "review-required"]


@dataclass(frozen=True, slots=True)
class MigrationApplyItem:
    source_id: str
    canonical_id: str
    destination_file: str | None
    status: ApplyStatus
    target_type: str | None
    target_status: str | None
    title: str
    content: str
    tags: tuple[str, ...]
    relations: tuple[dict[str, str], ...]
    provenance: Mapping[str, object]
    reasons: tuple[str, ...] = ()
    content_preview: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "sourceId": self.source_id,
            "canonicalId": self.canonical_id,
            "destinationFile": self.destination_file,
            "status": self.status,
            "targetType": self.target_type,
            "targetStatus": self.target_status,
            "title": self.title,
            "content": self.content,
            "tags": list(self.tags),
            "relations": [dict(item) for item in self.relations],
            "provenance": dict(self.provenance),
            "reasons": list(self.reasons),
            "contentPreview": self.content_preview,
        }


@dataclass(frozen=True, slots=True)
class MigrationApplyPlan:
    source_tool: str
    source_project: str | None
    source_version: str
    semantic_graph_fingerprint: str
    items: tuple[MigrationApplyItem, ...]

    @property
    def ready(self) -> bool:
        return all(item.status == "ready-create" for item in self.items)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "migration-apply-plan-v1",
            "source": {
                "tool": self.source_tool,
                "project": self.source_project,
                "version": self.source_version,
            },
            "semanticGraphFingerprint": self.semantic_graph_fingerprint,
            "ready": self.ready,
            "items": [item.to_dict() for item in self.items],
        }


def _destination(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, "destination file requires explicit review"
    text = value.strip().replace("\\", "/")
    if not text:
        return None, "destination file must be non-empty"
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts:
        return None, "destination file must be project-relative"
    if path.suffix.casefold() not in {".qmd", ".md"}:
        return None, "destination file must use .qmd or .md"
    return str(path), None


def _candidate_issue_messages(
    plan: SphinxNeedsMigrationPlan,
) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for issue in plan.issues:
        if issue.need_id is not None:
            result.setdefault(issue.need_id, []).append(f"{issue.code}: {issue.message}")
    return result


def _validate_type_and_status(
    candidate: SphinxNeedCandidate,
    config: NeedsConfig,
) -> list[str]:
    reasons: list[str] = []
    target_type = candidate.target_type
    if target_type is None:
        reasons.append("source type has no explicit Quarto-Needs type mapping")
        return reasons

    configured_types = (
        set(config.required_attributes)
        | set(config.id_prefixes)
        | set(config.type_roles)
        | set(config.allowed_statuses)
        | set(config.attribute_schemas)
    )
    if configured_types and target_type not in configured_types:
        reasons.append(f"target type {target_type!r} is not configured in this project")

    allowed = config.allowed_statuses.get(target_type)
    if allowed and candidate.status is not None and candidate.status not in allowed:
        reasons.append(
            f"status {candidate.status!r} is not allowed for target type {target_type!r}"
        )
    return reasons


def _resolve_relations(
    candidate: SphinxNeedCandidate,
    proposed_ids: Mapping[str, str],
    all_future_ids: set[str],
    reasons: list[str],
) -> tuple[dict[str, str], ...]:
    payload: list[dict[str, str]] = []
    for relation in candidate.relations:
        try:
            canonical_relation = DEFAULT_RELATION_CATALOG.resolve(relation.relation).v1_name
        except ValueError as error:
            reasons.append(str(error))
            continue
        target = proposed_ids.get(relation.target, relation.target)
        if target not in all_future_ids:
            reasons.append(
                f"relation target {relation.target!r} does not resolve to a local or proposed canonical ID"
            )
        payload.append(
            {
                "relation": canonical_relation,
                "target": target,
                "sourceField": relation.source_field,
            }
        )
    return tuple(
        sorted(payload, key=lambda item: (item["relation"], item["target"]))
    )


def _render_candidate(
    canonical_id: str,
    candidate: SphinxNeedCandidate,
    relations: tuple[dict[str, str], ...],
    provenance: Mapping[str, object],
    reasons: list[str],
) -> str | None:
    if candidate.target_type is None:
        return None
    render_problems = need_block_problems(
        canonical_id=canonical_id,
        target_type=candidate.target_type,
        target_status=candidate.status,
        title=candidate.title,
        body=candidate.content,
        tags=candidate.tags,
        relations=relations,
        provenance=provenance,
    )
    reasons.extend(render_problems)
    if render_problems:
        return None
    return render_need_block(
        canonical_id=canonical_id,
        target_type=candidate.target_type,
        target_status=candidate.status,
        title=candidate.title,
        body=candidate.content,
        tags=candidate.tags,
        relations=relations,
        provenance=provenance,
        extras=candidate.extras,
    )


def build_sphinx_apply_plan(
    migration: SphinxNeedsMigrationPlan,
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    destinations: Mapping[str, str],
    id_map: Mapping[str, str] | None = None,
) -> MigrationApplyPlan:
    """Build a reviewed Sphinx-Needs create plan without mutating authored files.

    Source identity is preserved by default: a source ID becomes the proposed
    canonical ID unless an explicit ``id_map`` says otherwise. Existing local
    IDs are conflicts, never implicit updates. This slice is create-only; an
    update/match workflow must have its own reviewed identity contract.
    """
    mapped_ids = dict(id_map or {})
    source_ids = {candidate.source_id for candidate in migration.candidates}
    unknown_destinations = sorted(set(destinations) - source_ids)
    if unknown_destinations:
        raise ValueError(
            "destinations reference unknown source IDs: " + ", ".join(unknown_destinations)
        )
    unknown_mappings = sorted(set(mapped_ids) - source_ids)
    if unknown_mappings:
        raise ValueError(
            "id_map references unknown source IDs: " + ", ".join(unknown_mappings)
        )

    proposed_ids: dict[str, str] = {}
    for candidate in migration.candidates:
        canonical_id = mapped_ids.get(candidate.source_id, candidate.source_id).strip()
        if not canonical_id:
            raise ValueError(f"canonical ID for {candidate.source_id} must be non-empty")
        proposed_ids[candidate.source_id] = canonical_id
    if len(set(proposed_ids.values())) != len(proposed_ids):
        raise ValueError("migration apply plan contains duplicate proposed canonical IDs")

    issue_messages = _candidate_issue_messages(migration)
    all_future_ids = set(snapshot.objects_by_id) | set(proposed_ids.values())
    items: list[MigrationApplyItem] = []

    for candidate in sorted(
        migration.candidates, key=lambda item: (item.source_id.casefold(), item.source_id)
    ):
        canonical_id = proposed_ids[candidate.source_id]
        reasons = list(issue_messages.get(candidate.source_id, ()))
        if canonical_id in snapshot.objects_by_id:
            reasons.append(
                f"canonical ID {canonical_id!r} already exists; migration does not imply update identity"
            )
        reasons.extend(_validate_type_and_status(candidate, config))

        destination_file, destination_problem = _destination(
            destinations.get(candidate.source_id)
        )
        if destination_problem:
            reasons.append(destination_problem)

        sorted_relations = _resolve_relations(
            candidate, proposed_ids, all_future_ids, reasons
        )

        provenance = {
            "tool": migration.tool,
            "project": migration.source_project,
            "version": migration.source_version,
            "sourceId": candidate.source_id,
        }
        content_preview = _render_candidate(
            canonical_id, candidate, sorted_relations, provenance, reasons
        )

        status: ApplyStatus
        if reasons:
            status = "review-required" if all(
                reason == "destination file requires explicit review" for reason in reasons
            ) else "blocked"
        else:
            status = "ready-create"

        items.append(
            MigrationApplyItem(
                source_id=candidate.source_id,
                canonical_id=canonical_id,
                destination_file=destination_file,
                status=status,
                target_type=candidate.target_type,
                target_status=candidate.status,
                title=candidate.title,
                content=candidate.content,
                tags=candidate.tags,
                relations=sorted_relations,
                provenance=provenance,
                reasons=tuple(reasons),
                content_preview=content_preview,
            )
        )

    return MigrationApplyPlan(
        source_tool=migration.tool,
        source_project=migration.source_project,
        source_version=migration.source_version,
        semantic_graph_fingerprint=snapshot.semantic_graph_fingerprint,
        items=tuple(items),
    )


def write_apply_plan(path: Path, plan: MigrationApplyPlan) -> None:
    payload = json.dumps(plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


UpdateStatus = Literal[
    "ready-create", "ready-update", "no-change", "blocked", "review-required"
]


@dataclass(frozen=True, slots=True)
class MigrationUpdateItem:
    source_id: str
    canonical_id: str
    destination_file: str | None
    status: UpdateStatus
    matched_by: str | None
    changes: tuple[str, ...]
    current_file_digest: str | None
    target_type: str | None
    target_status: str | None
    title: str
    content: str
    tags: tuple[str, ...]
    relations: tuple[dict[str, str], ...]
    provenance: Mapping[str, object]
    reasons: tuple[str, ...] = ()
    content_preview: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "sourceId": self.source_id,
            "canonicalId": self.canonical_id,
            "destinationFile": self.destination_file,
            "status": self.status,
            "matchedBy": self.matched_by,
            "changes": list(self.changes),
            "currentFileDigest": self.current_file_digest,
            "targetType": self.target_type,
            "targetStatus": self.target_status,
            "title": self.title,
            "content": self.content,
            "tags": list(self.tags),
            "relations": [dict(item) for item in self.relations],
            "provenance": dict(self.provenance),
            "reasons": list(self.reasons),
            "contentPreview": self.content_preview,
        }


@dataclass(frozen=True, slots=True)
class MigrationUpdatePlan:
    source_tool: str
    source_project: str | None
    source_version: str
    semantic_graph_fingerprint: str
    items: tuple[MigrationUpdateItem, ...]

    @property
    def applicable(self) -> bool:
        """True when nothing needs a decision before an update write."""
        return all(
            item.status in {"ready-create", "ready-update", "no-change"}
            for item in self.items
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "migration-update-plan-v1",
            "source": {
                "tool": self.source_tool,
                "project": self.source_project,
                "version": self.source_version,
            },
            "semanticGraphFingerprint": self.semantic_graph_fingerprint,
            "applicable": self.applicable,
            "items": [item.to_dict() for item in self.items],
        }


def _authored_source_key(
    attributes: Mapping[str, object],
) -> tuple[str, str | None, str] | None:
    """The source identity a migrated block declares, if it declares one."""
    tool = attributes.get("source-tool")
    source_id = attributes.get("source-id")
    if not isinstance(tool, str) or not tool.strip():
        return None
    if not isinstance(source_id, str) or not source_id.strip():
        return None
    project = attributes.get("source-project")
    if project is not None and not isinstance(project, str):
        return None
    normalized_project = project.strip() if isinstance(project, str) and project.strip() else None
    return (tool.strip().casefold(), normalized_project, source_id.strip())


def _candidate_source_key(
    migration: SphinxNeedsMigrationPlan, source_id: str
) -> tuple[str, str | None, str]:
    project = migration.source_project
    normalized_project = project.strip() if isinstance(project, str) and project.strip() else None
    return (source_tool_slug(migration.tool), normalized_project, source_id)


def _candidate_changes(
    candidate: SphinxNeedCandidate,
    record: ObjectRecord,
    outgoing: tuple[RelationRecord, ...],
    desired_relations: tuple[dict[str, str], ...],
) -> tuple[str, ...]:
    """Which source-owned fields differ from the authored object."""
    changes: list[str] = []
    if candidate.target_type is not None and record.type != candidate.target_type:
        changes.append("type")
    if candidate.status is not None and record.status != candidate.status:
        changes.append("status")
    if record.title != candidate.title:
        changes.append("title")
    if record.body.strip() != candidate.content.strip():
        changes.append("body")
    if tuple(record.tags) != tuple(candidate.tags):
        changes.append("tags")
    existing = {(relation.v1_name, relation.target) for relation in outgoing}
    desired = {(item["relation"], item["target"]) for item in desired_relations}
    if existing != desired:
        changes.append("relations")
    for name, value in authorable_extras(candidate.extras):
        if str(record.attributes.get(name)) != value:
            changes.append("attributes")
            break
    return tuple(changes)


def build_migration_update_plan(
    migration: SphinxNeedsMigrationPlan,
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    root: Path,
    destinations: Mapping[str, str],
    id_map: Mapping[str, str] | None = None,
) -> MigrationUpdatePlan:
    """Match a changed upstream source onto already-migrated local objects.

    Matching is by the authored source-identity marker (`source-tool`,
    optional `source-project`, `source-id`), never by an existing canonical
    ID alone: an ID collision without a marker stays blocked and explicit.
    A matched object with no differences is `no-change`; one with
    differences is `ready-update` and carries a digest of its authored file
    so a later write can refuse a stale plan. This plan is read-only.
    """
    mapped_ids = dict(id_map or {})
    source_ids = {candidate.source_id for candidate in migration.candidates}
    unknown_destinations = sorted(set(destinations) - source_ids)
    if unknown_destinations:
        raise ValueError(
            "destinations reference unknown source IDs: " + ", ".join(unknown_destinations)
        )
    unknown_mappings = sorted(set(mapped_ids) - source_ids)
    if unknown_mappings:
        raise ValueError(
            "id_map references unknown source IDs: " + ", ".join(unknown_mappings)
        )

    proposed_ids: dict[str, str] = {}
    for candidate in migration.candidates:
        canonical_id = mapped_ids.get(candidate.source_id, candidate.source_id).strip()
        if not canonical_id:
            raise ValueError(f"canonical ID for {candidate.source_id} must be non-empty")
        proposed_ids[candidate.source_id] = canonical_id
    if len(set(proposed_ids.values())) != len(proposed_ids):
        raise ValueError("migration update plan contains duplicate proposed canonical IDs")

    issue_messages = _candidate_issue_messages(migration)
    authored: dict[tuple[str, str | None, str], list[ObjectRecord]] = {}
    for record in snapshot.objects:
        key = _authored_source_key(record.attributes)
        if key is not None:
            authored.setdefault(key, []).append(record)

    all_future_ids = set(snapshot.objects_by_id) | set(proposed_ids.values())
    resolved_root = Path(root).resolve()
    items: list[MigrationUpdateItem] = []

    for candidate in sorted(
        migration.candidates, key=lambda item: (item.source_id.casefold(), item.source_id)
    ):
        canonical_id = proposed_ids[candidate.source_id]
        reasons = list(issue_messages.get(candidate.source_id, ()))
        matches = authored.get(_candidate_source_key(migration, candidate.source_id), [])
        matched: ObjectRecord | None = None
        matched_by: str | None = None
        changes: tuple[str, ...] = ()
        current_file_digest: str | None = None
        destination_file: str | None = None

        if len(matches) > 1:
            reasons.append(
                "source identity is claimed by multiple local objects: "
                + ", ".join(sorted(record.id for record in matches))
            )
        elif len(matches) == 1:
            matched = matches[0]
            if matched.id != canonical_id:
                reasons.append(
                    f"source identity is already migrated as {matched.id!r}; "
                    f"proposed canonical ID {canonical_id!r} differs "
                    "(renames are explicit, never implicit)"
                )
            else:
                matched_by = "source-marker"
                destination_file = (
                    matched.locations[0].file if matched.locations else None
                )
                if destination_file is None:
                    reasons.append("matched object has no authored source location")
        elif canonical_id in snapshot.objects_by_id:
            reasons.append(
                f"canonical ID {canonical_id!r} already exists without a source marker; "
                "add source-tool/source-id provenance or use --id-map"
            )

        if matched is None and matched_by is None and not reasons:
            destination_file, destination_problem = _destination(
                destinations.get(candidate.source_id)
            )
            if destination_problem:
                reasons.append(destination_problem)

        reasons.extend(_validate_type_and_status(candidate, config))
        sorted_relations = _resolve_relations(
            candidate, proposed_ids, all_future_ids, reasons
        )
        provenance = {
            "tool": migration.tool,
            "project": migration.source_project,
            "version": migration.source_version,
            "sourceId": candidate.source_id,
        }
        content_preview = _render_candidate(
            canonical_id, candidate, sorted_relations, provenance, reasons
        )

        status: UpdateStatus
        if matched is not None and matched_by == "source-marker" and not reasons:
            if destination_file is not None:
                path = (resolved_root / destination_file).resolve()
                if not path.is_file():
                    reasons.append(
                        f"matched object file {destination_file!r} is missing on disk"
                    )
                else:
                    current_file_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if not reasons:
                changes = _candidate_changes(
                    candidate,
                    matched,
                    tuple(snapshot.outgoing.get(matched.id, ())),
                    sorted_relations,
                )
                status = "no-change" if not changes else "ready-update"
            else:
                status = "blocked"
        elif reasons:
            status = "review-required" if all(
                reason == "destination file requires explicit review" for reason in reasons
            ) else "blocked"
        else:
            status = "ready-create"

        items.append(
            MigrationUpdateItem(
                source_id=candidate.source_id,
                canonical_id=canonical_id,
                destination_file=destination_file,
                status=status,
                matched_by=matched_by,
                changes=changes,
                current_file_digest=current_file_digest,
                target_type=candidate.target_type,
                target_status=candidate.status,
                title=candidate.title,
                content=candidate.content,
                tags=candidate.tags,
                relations=sorted_relations,
                provenance=provenance,
                reasons=tuple(reasons),
                content_preview=content_preview,
            )
        )

    return MigrationUpdatePlan(
        source_tool=migration.tool,
        source_project=migration.source_project,
        source_version=migration.source_version,
        semantic_graph_fingerprint=snapshot.semantic_graph_fingerprint,
        items=tuple(items),
    )


def write_update_plan(path: Path, plan: MigrationUpdatePlan) -> None:
    payload = json.dumps(plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
