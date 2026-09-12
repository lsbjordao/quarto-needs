"""The reduced projection the browser is allowed to see.

Deny by default: nodes and edges are constructed field by field from an
allowlist. Nothing is copied wholesale and filtered afterwards, because that
inverts the default — a field added to `ObjectRecord` later would ship to the
browser until someone remembered to exclude it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path as _Path
from typing import Iterable, Mapping

from . import diff as diff_module
from . import impact as impact_module
from .config import NeedsConfig
from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord

SCHEMA_VERSION = "graph-public-v1"

PUBLIC_NODE_FIELDS = ("id", "title", "type", "status", "priority", "tags", "href", "change", "technology")
PUBLIC_EDGE_FIELDS = ("source", "target", "relation", "label", "change", "pathMember", "technology", "order")
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
    technology: str | None = None

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
        if self.technology is not None:
            payload["technology"] = self.technology
        return payload


@dataclass(frozen=True, slots=True)
class PublicEdge:
    source: str
    target: str
    relation: str
    label: str
    change: str | None = None
    path_member: bool | None = None
    technology: str | None = None
    order: int | None = None

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
        if self.technology is not None:
            payload["technology"] = self.technology
        if self.order is not None:
            payload["order"] = self.order
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
    """Site-relative href to the need's defining page, falling back to an anchor.

    Built only from public source metadata (source ``file`` + ``anchor``), never
    from an absolute filesystem path, so it is safe to publish and keeps the
    interactive tooltip's "Open need" link working. Matches the href emitted for
    objects in the exported needs index (``export._object_v1``). When a record
    has no location we fall back to an anchor-only target on the current page.
    """
    import pathlib

    if record.locations:
        source = record.locations[0]
        stem = _Path(source.file).with_suffix("").as_posix()
        return f"{stem}.html#{source.anchor or record.id}"
    return "#" + record.id


def _label_for(relation: RelationRecord) -> str:
    authored = relation.attributes.get("label")
    if isinstance(authored, str) and authored.strip():
        return authored.strip()
    try:
        return DEFAULT_RELATION_CATALOG.resolve(relation.authored_name).direct_label
    except ValueError:
        return relation.authored_name


def _relation_technology(relation: RelationRecord) -> str | None:
    value = relation.attributes.get("technology")
    return value if isinstance(value, str) and value.strip() else None


def _relation_order(relation: RelationRecord) -> int | None:
    """The authored sequence number of an interaction, when one is usable."""
    value = relation.attributes.get("order")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _technology_of(record: ObjectRecord) -> str | None:
    value = record.attributes.get("technology")
    return value if isinstance(value, str) and value.strip() else None


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
            technology=_technology_of(record),
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
            technology=_relation_technology(relation),
            order=_relation_order(relation),
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


# --- overlays ----------------------------------------------------------------


def _node_changes(report: diff_module.DiffReport) -> dict[str, str]:
    """Diff classifications for current nodes, strongest signal first.

    An object can be both modified and relocated; content change is the
    stronger marker, so it wins. Added objects cannot be either.
    """
    changes: dict[str, str] = {}
    for item in report.relocated:
        changes[str(item["id"])] = "relocated"
    for item in report.modified:
        changes[str(item["id"])] = "modified"
    for object_id in report.added_objects:
        changes[str(object_id)] = "added"
    return changes


def _ghost_node(entry: Mapping[str, object]) -> PublicNode:
    """A removed object, rebuilt from baseline public fields only.

    The normalization mirrors `ObjectRecord.priority`/`.tags` so a ghost is
    indistinguishable from a live node of the same authoring. Bodies,
    rationales, locations, and undeclared attributes have no path back in:
    the ghost is constructed field by field like every other public node.
    """
    attributes = entry.get("attributes") or {}
    priority = attributes.get("priority") if isinstance(attributes, Mapping) else None
    tags_value = attributes.get("tags") if isinstance(attributes, Mapping) else None
    if isinstance(tags_value, (list, tuple)):
        tags = tuple(str(item).strip() for item in tags_value if str(item).strip())
    elif tags_value is None:
        tags = ()
    else:
        tags = tuple(
            item.strip()
            for item in str(tags_value).replace(";", ",").split(",")
            if item.strip()
        )
    technology_value = attributes.get("technology") if isinstance(attributes, Mapping) else None
    technology = technology_value if isinstance(technology_value, str) and technology_value.strip() else None
    identifier = str(entry["id"])
    return PublicNode(
        id=identifier,
        title=str(entry.get("title", "")),
        type=str(entry.get("type", "")),
        status=str(entry.get("status", "")),
        priority=str(priority) if priority not in (None, "") else None,
        tags=tags,
        href="#" + identifier,
        change="removed",
        technology=technology,
    )


def _ghost_edge(item: Mapping[str, object]) -> PublicEdge:
    """A removed relation, resolved through the *current* catalog.

    The catalog decides the v1 name and the label, exactly as for live edges;
    an authored name the current catalog no longer knows is kept verbatim
    rather than dropped.
    """
    authored = str(item["authoredName"])
    try:
        kind = DEFAULT_RELATION_CATALOG.resolve(authored)
        relation, label = kind.v1_name, kind.direct_label
    except ValueError:
        relation, label = authored, authored
    return PublicEdge(
        source=str(item["source"]),
        target=str(item["target"]),
        relation=relation,
        label=label,
        change="removed",
    )


def _enforce_overlay_limits(
    snapshot: AnalysisSnapshot,
    node_ids: tuple[str, ...],
    node_count: int,
    edge_count: int,
    limits: Mapping[str, int] | None,
) -> dict[str, int]:
    budgets = {
        key: int((limits or DEFAULT_LIMITS).get(key, DEFAULT_LIMITS[key]))
        for key in PUBLIC_LIMIT_FIELDS
    }
    if node_count > budgets["nodes"] or edge_count > budgets["edges"]:
        raise GraphLimitExceeded(
            {"nodes": node_count, "edges": edge_count},
            budgets,
            _suggest_facets(snapshot, node_ids),
        )
    return budgets


def build_diff_overlay(
    baseline_payload: Mapping[str, object],
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    node_ids: Iterable[str],
    view_id: str,
    recompute: bool = False,
    relations: Iterable[str] = (),
    limits: Mapping[str, int] | None = None,
    layout: str | None = None,
    seed: int | None = None,
) -> GraphProjection:
    """The diff view: current nodes with change markers plus baseline ghosts.

    Every classification comes from `diff.compare` — this function never
    re-derives one. Removed objects and relations stay visible as ghosts so
    the delta remains explainable; ghosts count toward the limits like any
    other node, because a silent budget cut is a truncated graph.
    """
    report = diff_module.compare(baseline_payload, snapshot, config, recompute=recompute)
    allowed = _effective_allowlist(relations)
    selected = {str(item) for item in node_ids}
    changes = _node_changes(report)

    nodes = tuple(
        PublicNode(
            id=record.id,
            title=record.title,
            type=record.type,
            status=record.status,
            priority=record.priority,
            tags=record.tags,
            href=_public_href(record),
            change=changes.get(record.id, "unchanged"),
            technology=_technology_of(record),
        )
        for record in snapshot.objects
        if record.id in selected
    )
    added_keys = {
        (str(item["source"]), str(item["authoredName"]), str(item["target"]))
        for item in report.added_relations
    }
    edges = tuple(
        PublicEdge(
            source=relation.source,
            target=relation.target,
            relation=relation.v1_name,
            label=_label_for(relation),
            change=(
                "added"
                if (relation.source, relation.authored_name, relation.target) in added_keys
                else "unchanged"
            ),
        )
        for relation in snapshot.relations
        if relation.source in selected
        and relation.target in selected
        and relation.v1_name in allowed
    )

    baseline_objects = {
        str(item["id"]): item
        for item in baseline_payload.get("objects", [])
    }
    ghost_ids = sorted({str(item) for item in report.removed_objects}, key=_sort_key)
    ghosts = tuple(
        _ghost_node(baseline_objects[ghost_id])
        for ghost_id in ghost_ids
        if ghost_id in baseline_objects
    )
    node_universe = selected | set(ghost_ids)
    ghost_edges = tuple(
        sorted(
            (
                _ghost_edge(item)
                for item in report.removed_relations
                if str(item["source"]) in node_universe
                and str(item["target"]) in node_universe
            ),
            key=lambda edge: _sort_key(edge.source) + _sort_key(edge.target) + _sort_key(edge.relation),
        )
    )

    budgets = _enforce_overlay_limits(
        snapshot,
        tuple(selected),
        len(nodes) + len(ghosts),
        len(edges) + len(ghost_edges),
        limits,
    )
    return GraphProjection(
        view_id=view_id,
        mode="diff",
        limits=budgets,
        nodes=nodes + ghosts,
        edges=edges + ghost_edges,
        layout=layout,
        seed=seed,
    )


def build_impact_overlay(
    baseline_payload: Mapping[str, object],
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    node_ids: Iterable[str],
    view_id: str,
    recompute: bool = False,
    relations: Iterable[str] = (),
    limits: Mapping[str, int] | None = None,
    layout: str | None = None,
    seed: int | None = None,
) -> GraphProjection:
    """The impact view: the propagation subgraph with explicit paths.

    `impact.analyze` owns the traversal and the guards; this function maps
    its report and never recomputes a path. Nodes reachable only through the
    baseline (removed but still explainable) appear as ghosts, exactly as in
    diff mode.
    """
    report = impact_module.analyze(
        baseline_payload, snapshot, config, recompute=recompute
    )
    allowed = _effective_allowlist(relations)
    selected = {str(item) for item in node_ids}

    entries = tuple(
        PublicImpactEntry(
            id=str(item["id"]),
            origin=str(item["origin"]),
            distance=int(item["distance"]),
            path=tuple(str(step) for step in item["path"]),
            classification=(
                str(item["classification"]) if item.get("classification") is not None else None
            ),
        )
        for item in report.impacted
    )

    path_ids = set(selected)
    path_pairs: set[tuple[str, str]] = set()
    for entry in entries:
        path_ids.update(entry.path)
        for left, right in zip(entry.path, entry.path[1:]):
            path_pairs.add((left, right))

    nodes = tuple(
        PublicNode(
            id=record.id,
            title=record.title,
            type=record.type,
            status=record.status,
            priority=record.priority,
            tags=record.tags,
            href=_public_href(record),
            technology=_technology_of(record),
        )
        for record in snapshot.objects
        if record.id in path_ids
    )
    edges = tuple(
        PublicEdge(
            source=relation.source,
            target=relation.target,
            relation=relation.v1_name,
            label=_label_for(relation),
            path_member=(
                (relation.source, relation.target) in path_pairs
                or (relation.target, relation.source) in path_pairs
            ),
        )
        for relation in snapshot.relations
        if relation.source in path_ids
        and relation.target in path_ids
        and relation.v1_name in allowed
    )

    baseline_objects = {
        str(item["id"]): item
        for item in baseline_payload.get("objects", [])
    }
    ghost_ids = sorted(path_ids - {record.id for record in snapshot.objects}, key=_sort_key)
    ghosts = tuple(
        _ghost_node(baseline_objects[ghost_id])
        for ghost_id in ghost_ids
        if ghost_id in baseline_objects
    )

    budgets = _enforce_overlay_limits(
        snapshot,
        tuple(path_ids),
        len(nodes) + len(ghosts),
        len(edges),
        limits,
    )
    return GraphProjection(
        view_id=view_id,
        mode="impact",
        limits=budgets,
        nodes=nodes + ghosts,
        edges=edges,
        impact=entries,
        layout=layout,
        seed=seed,
    )
