"""The reduced projection the browser is allowed to see.

Deny by default: nodes and edges are constructed field by field from an
allowlist. Nothing is copied wholesale and filtered afterwards, because that
inverts the default — a field added to `ObjectRecord` later would ship to the
browser until someone remembered to exclude it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Mapping

from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord

SCHEMA_VERSION = "graph-public-v1"

PUBLIC_NODE_FIELDS = ("id", "title", "type", "status", "priority", "tags", "href", "change")
PUBLIC_EDGE_FIELDS = ("source", "target", "relation", "label", "change", "pathMember")
PUBLIC_LIMIT_FIELDS = ("nodes", "edges")

DEFAULT_LIMITS = {"nodes": 100, "edges": 300}

# The default relation allowlist: every v1 name the catalog marks publishable.
# Authored aliases collapse onto their v1 name, so the names are deduplicated.
PUBLIC_RELATIONS = tuple(
    sorted({kind.v1_name for kind in DEFAULT_RELATION_CATALOG.entries.values() if kind.public})
)


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
class PublicImpactEntry:
    id: str
    origin: str
    distance: int
    path: tuple[str, ...]
    classification: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "origin": self.origin,
            "distance": self.distance,
            "path": list(self.path),
        }
        if self.classification is not None:
            payload["classification"] = self.classification
        return payload


@dataclass(frozen=True, slots=True)
class GraphProjection:
    view_id: str
    mode: str
    limits: Mapping[str, int]
    nodes: tuple[PublicNode, ...]
    edges: tuple[PublicEdge, ...]
    impact: tuple[PublicImpactEntry, ...] = ()
    layout: str | None = None
    seed: int | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": SCHEMA_VERSION,
            "view": {
                "id": self.view_id,
                "mode": self.mode,
                # Built from the two known keys, never `dict(self.limits)`:
                # a caller-supplied mapping copied wholesale would ship any
                # undeclared key that rode along inside it.
                "limits": {key: self.limits[key] for key in PUBLIC_LIMIT_FIELDS},
            },
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }
        if self.layout is not None:
            payload["view"]["layout"] = self.layout
        if self.seed is not None:
            payload["view"]["seed"] = self.seed
        if self.impact:
            # Each entry must be a `PublicImpactEntry`; `.to_dict()` only
            # emits its declared fields. A raw mapping slipped in here fails
            # loudly (`AttributeError`) instead of being copied wholesale.
            payload["impact"] = [item.to_dict() for item in self.impact]
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


class GraphLimitExceeded(Exception):
    """A selection exceeded the configured budgets.

    Limits never truncate silently: the caller renders this diagnostic as a
    visible narrowing prompt naming actual counts, configured limits, and the
    facets that would narrow the selection.
    """

    def __init__(
        self,
        actual: Mapping[str, int],
        limits: Mapping[str, int],
        suggested_facets: tuple[tuple[str, str, int], ...],
    ) -> None:
        self.actual = dict(actual)
        self.limits = dict(limits)
        self.suggested_facets = suggested_facets
        over = ", ".join(
            f"{count} {key} over {limits[key]}" for key, count in sorted(actual.items())
        )
        hints = ", ".join(f"{field}={value} ({count})" for field, value, count in suggested_facets)
        message = f"graph selection exceeds configured limits: {over}"
        if hints:
            message += f"; narrow with facets such as {hints}"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class Selection:
    """The bounded node and edge set a graph view is allowed to publish."""

    node_ids: tuple[str, ...]
    edges: tuple[tuple[str, str, str], ...]


def _effective_allowlist(relations: Iterable[str]) -> frozenset[str]:
    """Explicit allowlist intersected with the public catalog, deny by default.

    An empty request means every publishable relation; a non-public name is
    always denied, even when someone allowlists it explicitly.
    """
    requested = {str(name) for name in relations}
    return frozenset(requested & set(PUBLIC_RELATIONS)) if requested else frozenset(PUBLIC_RELATIONS)


def _sort_key(identifier: str) -> tuple[str, str]:
    return (identifier.casefold(), identifier)


def _adjacency(snapshot: AnalysisSnapshot, allowed: frozenset[str]) -> dict[str, set[str]]:
    neighbors: dict[str, set[str]] = {record.id: set() for record in snapshot.objects}
    for relation in snapshot.relations:
        if relation.v1_name not in allowed:
            continue
        neighbors.setdefault(relation.source, set()).add(relation.target)
        neighbors.setdefault(relation.target, set()).add(relation.source)
    return neighbors


def _suggest_facets(
    snapshot: AnalysisSnapshot, node_ids: tuple[str, ...]
) -> tuple[tuple[str, str, int], ...]:
    """The most populated values per facet field, deterministically ordered."""
    records = {record.id: record for record in snapshot.objects}
    counters: dict[str, dict[str, int]] = {"type": {}, "status": {}, "priority": {}, "tags": {}}
    for node_id in node_ids:
        record = records.get(node_id)
        if record is None:
            continue
        counters["type"][record.type] = counters["type"].get(record.type, 0) + 1
        counters["status"][record.status] = counters["status"].get(record.status, 0) + 1
        if record.priority is not None:
            counters["priority"][record.priority] = counters["priority"].get(record.priority, 0) + 1
        for tag in record.tags:
            counters["tags"][tag] = counters["tags"].get(tag, 0) + 1
    facets: list[tuple[str, str, int]] = []
    for field, counter in counters.items():
        ranked = sorted(counter.items(), key=lambda item: (-item[1],) + _sort_key(item[0]))
        facets.extend((field, value, count) for value, count in ranked[:2])
    return tuple(facets)


def select_graph(
    snapshot: AnalysisSnapshot,
    *,
    seeds: Iterable[str],
    relations: Iterable[str] = (),
    depth: int = 1,
    limits: Mapping[str, int] | None = None,
) -> Selection:
    """Bounded neighborhood selection over the allowlisted relations.

    Seeds keep their given order (a named query's sort order); each expansion
    frontier is sorted so the selection is deterministic regardless of input
    permutation. A visited set makes cycles terminate. Exceeding a limit
    raises `GraphLimitExceeded` — the selection is never silently truncated.
    """
    allowed = _effective_allowlist(relations)
    neighbors = _adjacency(snapshot, allowed)
    known = {record.id for record in snapshot.objects}

    ordered: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        node = str(seed)
        if node in known and node not in seen:
            seen.add(node)
            ordered.append(node)

    frontier = tuple(ordered)
    for _ in range(max(0, depth)):
        candidates = sorted(
            {node for current in frontier for node in neighbors.get(current, ())} - seen,
            key=_sort_key,
        )
        if not candidates:
            break
        for node in candidates:
            seen.add(node)
            ordered.append(node)
        frontier = tuple(candidates)

    edges = tuple(
        sorted(
            (
                (relation.source, relation.target, relation.v1_name)
                for relation in snapshot.relations
                if relation.v1_name in allowed
                and relation.source in seen
                and relation.target in seen
            ),
            key=lambda edge: _sort_key(edge[0]) + _sort_key(edge[1]) + (_sort_key(edge[2])),
        )
    )

    source_limits = limits if limits is not None else DEFAULT_LIMITS
    budgets = {
        key: int(source_limits.get(key, DEFAULT_LIMITS[key])) for key in PUBLIC_LIMIT_FIELDS
    }
    actual = {"nodes": len(ordered), "edges": len(edges)}
    if actual["nodes"] > budgets["nodes"] or actual["edges"] > budgets["edges"]:
        raise GraphLimitExceeded(
            actual, budgets, _suggest_facets(snapshot, tuple(ordered))
        )
    return Selection(node_ids=tuple(ordered), edges=edges)


def build_projection(
    snapshot: AnalysisSnapshot,
    *,
    node_ids: Iterable[str],
    view_id: str,
    mode: str = "catalog",
    limits: Mapping[str, int] | None = None,
    relations: Iterable[str] = (),
    layout: str | None = None,
    seed: int | None = None,
) -> GraphProjection:
    selected = {str(item) for item in node_ids}
    allowed = _effective_allowlist(relations)
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
        if relation.source in selected
        and relation.target in selected
        and relation.v1_name in allowed
    )
    source_limits = limits if limits is not None else DEFAULT_LIMITS
    return GraphProjection(
        view_id=view_id,
        mode=mode,
        limits={
            key: int(source_limits.get(key, DEFAULT_LIMITS[key]))
            for key in PUBLIC_LIMIT_FIELDS
        },
        nodes=nodes,
        edges=edges,
        layout=layout,
        seed=seed,
    )


def render_projection(projection: GraphProjection) -> str:
    return json.dumps(projection.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
