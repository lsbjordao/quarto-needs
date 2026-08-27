"""The reduced projection the browser is allowed to see.

Deny by default: nodes and edges are constructed field by field from an
allowlist. Nothing is copied wholesale and filtered afterwards, because that
inverts the default — a field added to `ObjectRecord` later would ship to the
browser until someone remembered to exclude it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord

SCHEMA_VERSION = "graph-public-v1"

PUBLIC_NODE_FIELDS = ("id", "title", "type", "status", "priority", "tags", "href", "change")
PUBLIC_EDGE_FIELDS = ("source", "target", "relation", "label", "change", "pathMember")

DEFAULT_LIMITS = {"nodes": 100, "edges": 300}


@dataclass(frozen=True, slots=True)
class PublicNode:
    id: str
    title: str
    type: str
    status: str
    priority: str | None
    tags: tuple[str, ...]
    href: str
    change: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "priority": self.priority,
            "tags": list(self.tags),
            "href": self.href,
        }
        if self.change is not None:
            payload["change"] = self.change
        return payload


@dataclass(frozen=True, slots=True)
class PublicEdge:
    source: str
    target: str
    relation: str
    label: str
    change: str | None = None
    path_member: bool | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "label": self.label,
        }
        if self.change is not None:
            payload["change"] = self.change
        if self.path_member is not None:
            payload["pathMember"] = self.path_member
        return payload


@dataclass(frozen=True, slots=True)
class GraphProjection:
    view_id: str
    mode: str
    limits: Mapping[str, int]
    nodes: tuple[PublicNode, ...]
    edges: tuple[PublicEdge, ...]
    impact: tuple[Mapping[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": SCHEMA_VERSION,
            "view": {
                "id": self.view_id,
                "mode": self.mode,
                "limits": dict(self.limits),
            },
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }
        if self.impact:
            payload["impact"] = [dict(item) for item in self.impact]
        return payload


def _public_href(record: ObjectRecord) -> str:
    """Anchor-only by default.

    A resolved cross-page href is safe to publish, but it is built by the Lua
    link resolver at render time, where the output format and current page are
    known. Emitting a filesystem-derived path here would leak project layout.
    """
    return "#" + record.id


def _label_for(relation: RelationRecord) -> str:
    try:
        return DEFAULT_RELATION_CATALOG.resolve(relation.authored_name).direct_label
    except ValueError:
        return relation.authored_name


def build_projection(
    snapshot: AnalysisSnapshot,
    *,
    node_ids: Iterable[str],
    view_id: str,
    mode: str = "catalog",
    limits: Mapping[str, int] | None = None,
) -> GraphProjection:
    selected = {str(item) for item in node_ids}
    nodes = tuple(
        PublicNode(
            id=record.id,
            title=record.title,
            type=record.type,
            status=record.status,
            priority=record.priority,
            tags=record.tags,
            href=_public_href(record),
        )
        for record in snapshot.objects
        if record.id in selected
    )
    edges = tuple(
        PublicEdge(
            source=relation.source,
            target=relation.target,
            relation=relation.v1_name,
            label=_label_for(relation),
        )
        for relation in snapshot.relations
        if relation.source in selected and relation.target in selected
    )
    return GraphProjection(
        view_id=view_id,
        mode=mode,
        limits=dict(limits or DEFAULT_LIMITS),
        nodes=nodes,
        edges=edges,
    )


def render_projection(projection: GraphProjection) -> str:
    return json.dumps(projection.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
