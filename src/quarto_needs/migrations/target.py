from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..config import NeedsConfig
from ..relations import DEFAULT_RELATION_CATALOG
from .sphinx_needs import MigrationIssue, SphinxNeedCandidate, SphinxNeedsMigrationPlan


@dataclass(frozen=True, slots=True)
class ReadyRelation:
    source: str
    relation: str
    target: str


@dataclass(frozen=True, slots=True)
class ReadyCandidate:
    source_id: str
    target_id: str
    target_type: str
    title: str
    content: str
    status: str | None
    tags: tuple[str, ...]
    attributes: Mapping[str, object]
    relations: tuple[ReadyRelation, ...]


@dataclass(frozen=True, slots=True)
class TargetValidationResult:
    candidates: tuple[ReadyCandidate, ...]
    issues: tuple[MigrationIssue, ...]

    @property
    def ready(self) -> bool:
        return not self.issues


def _known_types(config: NeedsConfig) -> set[str]:
    return (
        set(config.required_attributes)
        | set(config.id_prefixes)
        | set(config.type_roles)
        | set(config.allowed_statuses)
        | set(config.attribute_schemas)
    )


def _mapped_id(source_id: str, id_map: Mapping[str, str]) -> str:
    return id_map.get(source_id, source_id)


def _mapped_status(
    candidate: SphinxNeedCandidate,
    status_map: Mapping[str, str],
) -> str | None:
    if candidate.status is None:
        return None
    return status_map.get(candidate.status, candidate.status)


def validate_plan_against_target(
    plan: SphinxNeedsMigrationPlan,
    config: NeedsConfig,
    *,
    id_map: Mapping[str, str] | None = None,
    status_map: Mapping[str, str] | None = None,
    attribute_map: Mapping[str, str] | None = None,
) -> TargetValidationResult:
    """Validate a migration plan against the target Quarto-Needs configuration.

    This function performs no mutation and no QMD generation. It exists as the
    semantic gate between source-specific migration planning and materialization.
    """
    ids = dict(id_map or {})
    statuses = dict(status_map or {})
    attributes = dict(attribute_map or {})
    issues = list(plan.issues)
    known_types = _known_types(config)

    source_candidates = {candidate.source_id: candidate for candidate in plan.candidates}
    target_ids: dict[str, str] = {
        source_id: _mapped_id(source_id, ids) for source_id in source_candidates
    }
    if len(set(target_ids.values())) != len(target_ids):
        collisions: dict[str, list[str]] = {}
        for source_id, target_id in target_ids.items():
            collisions.setdefault(target_id, []).append(source_id)
        for target_id, sources in sorted(collisions.items()):
            if len(sources) > 1:
                issues.append(
                    MigrationIssue(
                        code="TARGET_ID_COLLISION",
                        message=f"multiple source objects map to target ID {target_id!r}: {', '.join(sorted(sources))}",
                    )
                )

    ready: list[ReadyCandidate] = []
    for candidate in plan.candidates:
        target_type = candidate.target_type
        target_id = target_ids[candidate.source_id]
        if target_type is None:
            # Source planner already emits TYPE_UNMAPPED; avoid duplicate noise.
            continue
        if target_type not in known_types:
            issues.append(
                MigrationIssue(
                    code="TARGET_TYPE_UNKNOWN",
                    message=f"target type {target_type!r} is not configured in the target project",
                    need_id=candidate.source_id,
                    field="type",
                )
            )
            continue

        prefix = config.id_prefixes.get(target_type)
        if prefix and not target_id.startswith(prefix):
            issues.append(
                MigrationIssue(
                    code="TARGET_ID_PREFIX",
                    message=f"target ID {target_id!r} must start with configured prefix {prefix!r} for type {target_type!r}",
                    need_id=candidate.source_id,
                    field="id",
                )
            )

        target_status = _mapped_status(candidate, statuses)
        allowed_statuses = config.allowed_statuses.get(target_type, ())
        if target_status is not None and allowed_statuses and target_status not in allowed_statuses:
            issues.append(
                MigrationIssue(
                    code="TARGET_STATUS_INVALID",
                    message=f"status {target_status!r} is not allowed for target type {target_type!r}",
                    need_id=candidate.source_id,
                    field="status",
                )
            )

        mapped_attributes: dict[str, object] = {}
        for source_name, value in candidate.extras.items():
            target_name = attributes.get(source_name, source_name)
            if target_name in mapped_attributes and mapped_attributes[target_name] != value:
                issues.append(
                    MigrationIssue(
                        code="TARGET_ATTRIBUTE_COLLISION",
                        message=f"multiple source attributes map to target attribute {target_name!r}",
                        need_id=candidate.source_id,
                        field=source_name,
                    )
                )
            else:
                mapped_attributes[target_name] = value

        for required in config.required_attributes.get(target_type, ()):
            if required not in mapped_attributes:
                issues.append(
                    MigrationIssue(
                        code="TARGET_ATTRIBUTE_REQUIRED",
                        message=f"target type {target_type!r} requires attribute {required!r}",
                        need_id=candidate.source_id,
                        field=required,
                    )
                )

        ready_relations: list[ReadyRelation] = []
        for relation in candidate.relations:
            try:
                canonical = DEFAULT_RELATION_CATALOG.resolve(relation.relation).v1_name
            except ValueError:
                issues.append(
                    MigrationIssue(
                        code="TARGET_RELATION_UNKNOWN",
                        message=f"relation {relation.relation!r} is not in the canonical Quarto-Needs relation catalog",
                        need_id=candidate.source_id,
                        field=relation.source_field,
                    )
                )
                continue

            target_candidate = source_candidates.get(relation.target)
            if target_candidate is None:
                issues.append(
                    MigrationIssue(
                        code="TARGET_RELATION_EXTERNAL",
                        message=f"relation target {relation.target!r} is not mapped inside this migration plan",
                        need_id=candidate.source_id,
                        field=relation.source_field,
                    )
                )
                continue
            if target_candidate.target_type is None:
                issues.append(
                    MigrationIssue(
                        code="TARGET_RELATION_TYPE_UNRESOLVED",
                        message=f"relation target {relation.target!r} has no resolved target type",
                        need_id=candidate.source_id,
                        field=relation.source_field,
                    )
                )
                continue

            policy = config.relation_policies.get(canonical)
            if policy is not None:
                if policy.allowed_source_types and target_type not in policy.allowed_source_types:
                    issues.append(
                        MigrationIssue(
                            code="TARGET_RELATION_SOURCE_TYPE",
                            message=f"relation {canonical!r} does not allow source type {target_type!r}",
                            need_id=candidate.source_id,
                            field=relation.source_field,
                        )
                    )
                if policy.allowed_target_types and target_candidate.target_type not in policy.allowed_target_types:
                    issues.append(
                        MigrationIssue(
                            code="TARGET_RELATION_TARGET_TYPE",
                            message=f"relation {canonical!r} does not allow target type {target_candidate.target_type!r}",
                            need_id=candidate.source_id,
                            field=relation.source_field,
                        )
                    )
            ready_relations.append(
                ReadyRelation(
                    source=target_id,
                    relation=canonical,
                    target=target_ids[relation.target],
                )
            )

        ready.append(
            ReadyCandidate(
                source_id=candidate.source_id,
                target_id=target_id,
                target_type=target_type,
                title=candidate.title,
                content=candidate.content,
                status=target_status,
                tags=candidate.tags,
                attributes=dict(sorted(mapped_attributes.items())),
                relations=tuple(
                    sorted(ready_relations, key=lambda item: (item.relation, item.target))
                ),
            )
        )

    return TargetValidationResult(
        candidates=tuple(sorted(ready, key=lambda item: (item.target_id.casefold(), item.target_id))),
        issues=tuple(
            sorted(
                issues,
                key=lambda item: (
                    item.need_id or "",
                    item.code,
                    item.field or "",
                    item.message,
                ),
            )
        ),
    )
