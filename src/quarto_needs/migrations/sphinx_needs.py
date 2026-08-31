from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


class SphinxNeedsMigrationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MigrationIssue:
    code: str
    message: str
    need_id: str | None = None
    field: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "needId": self.need_id,
            "field": self.field,
        }


@dataclass(frozen=True, slots=True)
class MigratedRelation:
    source: str
    relation: str
    target: str
    source_field: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "relation": self.relation,
            "target": self.target,
            "sourceField": self.source_field,
        }


@dataclass(frozen=True, slots=True)
class SphinxNeedCandidate:
    source_id: str
    source_type: str
    target_type: str | None
    title: str
    content: str
    status: str | None
    tags: tuple[str, ...]
    relations: tuple[MigratedRelation, ...]
    unmapped_links: Mapping[str, tuple[str, ...]]
    extras: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "sourceId": self.source_id,
            "sourceType": self.source_type,
            "targetType": self.target_type,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "tags": list(self.tags),
            "relations": [relation.to_dict() for relation in self.relations],
            "unmappedLinks": {
                name: list(values) for name, values in sorted(self.unmapped_links.items())
            },
            "extras": {name: self.extras[name] for name in sorted(self.extras)},
        }


@dataclass(frozen=True, slots=True)
class SphinxNeedsMigrationPlan:
    source_project: str | None
    source_version: str
    candidates: tuple[SphinxNeedCandidate, ...]
    issues: tuple[MigrationIssue, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "sphinx-needs-migration-plan-v1",
            "source": {
                "tool": "Sphinx-Needs",
                "project": self.source_project,
                "version": self.source_version,
            },
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "issues": [issue.to_dict() for issue in self.issues],
        }


_CORE_FIELDS = {
    "id",
    "type",
    "title",
    "full_title",
    "content",
    "status",
    "tags",
}


def load_needs_json(path: Path) -> Mapping[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SphinxNeedsMigrationError(f"cannot read Sphinx-Needs JSON: {error}") from error
    if not isinstance(raw, dict):
        raise SphinxNeedsMigrationError("Sphinx-Needs JSON root must be an object")
    return raw


def select_version(document: Mapping[str, object], requested: str | None = None) -> tuple[str, Mapping[str, object]]:
    versions = document.get("versions")
    if not isinstance(versions, dict) or not versions:
        raise SphinxNeedsMigrationError("Sphinx-Needs JSON must contain a non-empty versions object")

    selected = requested
    if selected is None:
        current = document.get("current_version")
        if isinstance(current, str) and current in versions:
            selected = current
        elif len(versions) == 1:
            selected = next(iter(versions))
        else:
            available = ", ".join(sorted(str(key) for key in versions))
            raise SphinxNeedsMigrationError(
                "Sphinx-Needs version is ambiguous; select one explicitly "
                f"(available: {available})"
            )
    if selected not in versions:
        available = ", ".join(sorted(str(key) for key in versions))
        raise SphinxNeedsMigrationError(
            f"Sphinx-Needs version {selected!r} does not exist (available: {available})"
        )
    version = versions[selected]
    if not isinstance(version, dict):
        raise SphinxNeedsMigrationError(f"Sphinx-Needs version {selected!r} must be an object")
    return selected, version


def _normalized_needs(raw: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(raw, dict):
        values: list[Mapping[str, object]] = []
        for key, value in raw.items():
            if not isinstance(value, dict):
                raise SphinxNeedsMigrationError(f"need {key!r} must be an object")
            candidate = dict(value)
            candidate.setdefault("id", key)
            values.append(candidate)
        return tuple(values)
    if isinstance(raw, list):
        if not all(isinstance(value, dict) for value in raw):
            raise SphinxNeedsMigrationError("Sphinx-Needs needs array must contain only objects")
        return tuple(raw)  # type: ignore[return-value]
    raise SphinxNeedsMigrationError("selected Sphinx-Needs version must contain needs as an object or array")


def _field_types(version: Mapping[str, object]) -> dict[str, str]:
    schema = version.get("needs_schema")
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    result: dict[str, str] = {}
    for name, definition in properties.items():
        if not isinstance(name, str) or not isinstance(definition, dict):
            continue
        field_type = definition.get("field_type")
        if isinstance(field_type, str):
            result[name] = field_type
    return result


def _required_string(need: Mapping[str, object], field: str) -> str:
    value = need.get(field)
    if not isinstance(value, str) or not value.strip():
        raise SphinxNeedsMigrationError(f"Sphinx-Needs need requires non-empty {field}")
    return value.strip()


def _tags(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.replace(",", ";").split(";") if part.strip())
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(str(item) for item in value)
    raise SphinxNeedsMigrationError("Sphinx-Needs tags must be a string or array of strings")


def _links(value: object, *, need_id: str, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.replace(",", ";").split(";") if part.strip())
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(str(item) for item in value)
    raise SphinxNeedsMigrationError(
        f"Sphinx-Needs link field {field!r} on {need_id} must be a string or array of strings"
    )


def _conditional_link(value: str) -> bool:
    return "[" in value and value.rstrip().endswith("]")


def build_migration_plan(
    document: Mapping[str, object],
    *,
    version: str | None = None,
    type_map: Mapping[str, str] | None = None,
    relation_map: Mapping[str, str] | None = None,
) -> SphinxNeedsMigrationPlan:
    selected, version_data = select_version(document, version)
    raw_needs = _normalized_needs(version_data.get("needs"))
    field_types = _field_types(version_data)
    link_fields = {name for name, kind in field_types.items() if kind == "links"}
    backlink_fields = {name for name, kind in field_types.items() if kind == "backlinks"}
    types = dict(type_map or {})
    relations = dict(relation_map or {})

    source_ids: list[str] = []
    for raw in raw_needs:
        source_ids.append(_required_string(raw, "id"))
    if len(source_ids) != len(set(source_ids)):
        raise SphinxNeedsMigrationError("Sphinx-Needs JSON contains duplicate need IDs")
    id_set = set(source_ids)

    candidates: list[SphinxNeedCandidate] = []
    issues: list[MigrationIssue] = []
    for raw in sorted(raw_needs, key=lambda item: (_required_string(item, "id").casefold(), _required_string(item, "id"))):
        need_id = _required_string(raw, "id")
        source_type = _required_string(raw, "type")
        title_value = raw.get("title")
        if not isinstance(title_value, str) or not title_value.strip():
            full_title = raw.get("full_title")
            if isinstance(full_title, str) and full_title.strip():
                title_value = full_title
            else:
                raise SphinxNeedsMigrationError(f"Sphinx-Needs need {need_id} requires a title")
        title = title_value.strip()
        content = raw.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise SphinxNeedsMigrationError(f"Sphinx-Needs need {need_id} content must be a string")
        status = raw.get("status")
        if status is not None and not isinstance(status, str):
            raise SphinxNeedsMigrationError(f"Sphinx-Needs need {need_id} status must be a string or null")

        target_type = types.get(source_type)
        if target_type is None:
            issues.append(
                MigrationIssue(
                    code="TYPE_UNMAPPED",
                    message=f"Sphinx-Needs type {source_type!r} has no explicit Quarto-Needs type mapping",
                    need_id=need_id,
                    field="type",
                )
            )

        migrated_relations: list[MigratedRelation] = []
        unmapped_links: dict[str, tuple[str, ...]] = {}
        for field_name in sorted(link_fields):
            values = _links(raw.get(field_name), need_id=need_id, field=field_name)
            if not values:
                continue
            target_relation = relations.get(field_name)
            if target_relation is None:
                unmapped_links[field_name] = values
                issues.append(
                    MigrationIssue(
                        code="LINK_FIELD_UNMAPPED",
                        message=f"Sphinx-Needs link field {field_name!r} has no explicit relation mapping",
                        need_id=need_id,
                        field=field_name,
                    )
                )
                continue
            for target in values:
                if _conditional_link(target):
                    unmapped_links.setdefault(field_name, tuple())
                    unmapped_links[field_name] = (*unmapped_links[field_name], target)
                    issues.append(
                        MigrationIssue(
                            code="CONDITIONAL_LINK",
                            message="conditional Sphinx-Needs link requires explicit migration handling",
                            need_id=need_id,
                            field=field_name,
                        )
                    )
                    continue
                migrated_relations.append(
                    MigratedRelation(
                        source=need_id,
                        relation=target_relation,
                        target=target,
                        source_field=field_name,
                    )
                )
                if target not in id_set:
                    issues.append(
                        MigrationIssue(
                            code="EXTERNAL_LINK_TARGET",
                            message=f"mapped link target {target!r} is not present in the selected Sphinx-Needs version",
                            need_id=need_id,
                            field=field_name,
                        )
                    )

        excluded = _CORE_FIELDS | link_fields | backlink_fields
        extras = {name: value for name, value in raw.items() if name not in excluded}
        candidates.append(
            SphinxNeedCandidate(
                source_id=need_id,
                source_type=source_type,
                target_type=target_type,
                title=title,
                content=content,
                status=status,
                tags=_tags(raw.get("tags")),
                relations=tuple(sorted(migrated_relations, key=lambda item: (item.relation, item.target))),
                unmapped_links=dict(sorted(unmapped_links.items())),
                extras=dict(sorted(extras.items())),
            )
        )

    project = document.get("project")
    if project is not None and not isinstance(project, str):
        project = str(project)
    return SphinxNeedsMigrationPlan(
        source_project=project,
        source_version=selected,
        candidates=tuple(candidates),
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


def write_migration_plan(path: Path, plan: SphinxNeedsMigrationPlan) -> None:
    payload = json.dumps(plan.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
