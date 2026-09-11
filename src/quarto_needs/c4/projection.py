"""The canonical graph to C4 IR projection -- the only place C4 meaning lives.

This module reads an `AnalysisSnapshot` and produces an immutable `C4View`.
It does not render, does not position anything, does not know any diagram
syntax, and never emits Mermaid/Structurizr/PlantUML/D2 (Spec 8).

Containment is resolved from the canonical `part-of`/`decomposes` pair in
*both* authored directions: `part-of` runs child->parent, `decomposes` runs
parent->child. Consuming only one direction silently drops every hierarchy
authored the other way.
"""
from __future__ import annotations

from typing import Mapping

from ..relations import DEFAULT_RELATION_CATALOG
from ..snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord
from .model import (
    C4_ROLE_BY_TYPE,
    C4Element,
    C4ElementRole,
    C4Relationship,
    C4View,
    normalize_level,
    relationship_id,
)


class C4ProjectionError(Exception):
    """An unusable level/scope pair. Reported to users as C4008."""

    code = "C4008"

    def __init__(self, message: str, *, scope_id: str | None = None) -> None:
        super().__init__(message)
        self.scope_id = scope_id


SCOPE_TYPE_BY_LEVEL: Mapping[str, str] = {
    "system-context": "system",
    "container": "system",
    "component": "container",
    "code": "component",
    "deployment": "deployment-node",
}

# What a level draws *inside* its boundary. system-context draws nothing
# inside: a context diagram shows the system as an opaque box (Spec 30).
_CHILD_TYPE_BY_LEVEL: Mapping[str, str] = {
    "container": "container",
    "component": "component",
    "code": "source-module",
    "deployment": "deployment-node",
}

_INTERACTION_RELATION = "depends-on"
_CONTAINMENT_RELATIONS = ("part-of", "decomposes")


def _text_attribute(record: ObjectRecord, key: str) -> str | None:
    """A non-empty string attribute, or None.

    `description` deliberately comes from an attribute and never from the
    `.need` block body: a body is multi-paragraph prose and would wreck
    every diagram it reached.
    """
    value = record.attributes.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _child_id(relation: RelationRecord, *, parent_id: str) -> str | None:
    """The child's ID if `relation` declares it a direct child of `parent_id`.

    `v1_name` rather than `authored_name`: it collapses authoring aliases, so
    a future alias for either direction is handled without touching this.
    """
    if relation.v1_name == "part-of" and relation.target == parent_id:
        return relation.source
    if relation.v1_name == "decomposes" and relation.source == parent_id:
        return relation.target
    return None


def _label_for(relation: RelationRecord) -> str:
    authored = relation.attributes.get("label")
    if isinstance(authored, str) and authored.strip():
        return authored.strip()
    try:
        return DEFAULT_RELATION_CATALOG.resolve(relation.authored_name).direct_label
    except ValueError:
        return relation.authored_name


def _technology_for(relation: RelationRecord) -> str | None:
    value = relation.attributes.get("technology")
    return value if isinstance(value, str) and value.strip() else None


def _element(record: ObjectRecord, *, parent_id: str | None) -> C4Element:
    role = C4_ROLE_BY_TYPE[record.type]
    return C4Element(
        id=record.id,
        role=role,
        name=record.title,
        description=_text_attribute(record, "description"),
        technology=_text_attribute(record, "technology"),
        parent_id=parent_id,
        external=role is C4ElementRole.EXTERNAL_SYSTEM,
        tags=record.tags,
    )


def _sort_key(identifier: str) -> tuple[str, str]:
    return (identifier.casefold(), identifier)


def available_scopes(snapshot: AnalysisSnapshot, level: str) -> tuple[str, ...]:
    """Every object that can scope a view at `level`, in deterministic order."""
    canonical = normalize_level(level)
    if canonical is None:
        return ()
    scope_type = SCOPE_TYPE_BY_LEVEL[canonical]
    return tuple(
        sorted(
            (record.id for record in snapshot.objects if record.type == scope_type),
            key=_sort_key,
        )
    )


def project_c4(
    snapshot: AnalysisSnapshot, *, level: str, scope_id: str
) -> C4View:
    canonical = normalize_level(level)
    if canonical is None:
        raise C4ProjectionError(
            f"unsupported C4 level: {level!r} (expected one of "
            f"{', '.join(SCOPE_TYPE_BY_LEVEL)})"
        )
    record = snapshot.objects_by_id.get(scope_id)
    if record is None:
        raise C4ProjectionError(
            f"{scope_id!r} is not a known object", scope_id=scope_id
        )
    expected_type = SCOPE_TYPE_BY_LEVEL[canonical]
    if record.type != expected_type:
        raise C4ProjectionError(
            f"level={canonical!r} requires a {expected_type!r} scope, "
            f"but {scope_id!r} is {record.type!r}",
            scope_id=scope_id,
        )

    # id -> parent id within this view. The scope is always the view's root.
    parents: dict[str, str | None] = {scope_id: None}

    child_type = _CHILD_TYPE_BY_LEVEL.get(canonical)
    if child_type is not None:
        for relation in snapshot.relations:
            child_id = _child_id(relation, parent_id=scope_id)
            if child_id is None or child_id in parents:
                continue
            child = snapshot.objects_by_id.get(child_id)
            # Filtering by the level's expected child type keeps a layer
            # skip (already an ARC001 graph error) from producing an
            # incoherent diagram under an advisory profile.
            if child is not None and child.type == child_type:
                parents[child_id] = scope_id

    if canonical == "deployment":
        # Deployed artifacts are members of the node's boundary through
        # deployed-on (artifact -> node) or its inverse authoring, deploys.
        for relation in snapshot.relations:
            if relation.v1_name == "deployed-on" and relation.target == scope_id:
                artifact_id = relation.source
            elif relation.v1_name == "deploys" and relation.source == scope_id:
                artifact_id = relation.target
            else:
                continue
            artifact = snapshot.objects_by_id.get(artifact_id)
            if artifact is not None and artifact.type in C4_ROLE_BY_TYPE:
                parents.setdefault(artifact_id, scope_id)

    for relation in snapshot.relations:
        if relation.v1_name != _INTERACTION_RELATION:
            continue
        if relation.source == scope_id:
            other = relation.target
        elif relation.target == scope_id:
            other = relation.source
        else:
            continue
        if other not in parents and other in snapshot.objects_by_id:
            parents[other] = None

    # Only architecture objects are C4 elements. A `depends-on` neighbour of
    # any other type (a requirement, say) is a perfectly valid graph edge
    # that simply has no C4 role, and is not drawn.
    elements = tuple(
        _element(snapshot.objects_by_id[identifier], parent_id=parents[identifier])
        for identifier in sorted(parents, key=_sort_key)
        if snapshot.objects_by_id[identifier].type in C4_ROLE_BY_TYPE
    )
    element_ids = {element.id for element in elements}

    relationships = tuple(
        sorted(
            (
                C4Relationship(
                    id=relationship_id(
                        relation.source, relation.target, relation.v1_name
                    ),
                    source_id=relation.source,
                    target_id=relation.target,
                    relation_type=relation.v1_name,
                    description=_label_for(relation),
                    technology=_technology_for(relation),
                )
                for relation in snapshot.relations
                if relation.v1_name == _INTERACTION_RELATION
                and relation.source in element_ids
                and relation.target in element_ids
            ),
            key=lambda item: _sort_key(item.source_id)
            + _sort_key(item.target_id)
            + _sort_key(item.relation_type),
        )
    )

    return C4View(
        id=f"{canonical}-{scope_id}",
        level=canonical,
        scope_id=scope_id,
        elements=elements,
        relationships=relationships,
    )
