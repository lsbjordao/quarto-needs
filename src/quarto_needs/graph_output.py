"""Write public graph projections as files the Lua filter can embed.

At build/scan time the CLI computes one projection per configured graph view and
writes it as versioned JSON under `.quarto-needs/graphs/`. The Lua filter in the
extension reads that file for the requested `need-graph` view, renders the static
figure, accessible edge table, and summary from the *same* projection, and embeds
the projection JSON in the progressive container for the interactive client. The
static and interactive views therefore cannot disagree.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Mapping

from .baseline import BaselineError, load_baseline
from .config import NeedsConfig
from .graph_projection import (
    GraphLimitExceeded,
    GraphProjection,
    build_projection as build_catalog,
    build_diff_overlay,
    build_impact_overlay,
    select_graph,
)
from .queries import DEFAULT_QUERY_NAME, query_ids
from .relations import DEFAULT_RELATION_CATALOG, TRAVERSAL_PROFILES
from .snapshot import AnalysisSnapshot

DEFAULT_VIEW_ID = "need-graph-1"
QUERY_VIEW_PREFIX = "need-graph-query-"
DEFAULT_BASELINE_PATH = Path(".quarto-needs/baseline.json")


def _atomic_text(path: Path, contents: str) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _limits(config: NeedsConfig) -> dict[str, int]:
    return {"nodes": config.graph.max_nodes, "edges": config.graph.max_edges}


def _selection(snapshot: AnalysisSnapshot, config: NeedsConfig, query_name: str = DEFAULT_QUERY_NAME):
    seeds = query_ids(config, snapshot, query_name)
    return select_graph(
        snapshot,
        seeds=seeds,
        relations=config.graph.relations,
        depth=config.graph.depth,
        limits=_limits(config),
    )


def _public_relation_semantics() -> dict[str, dict[str, object]]:
    """Expose presentation-safe relation semantics from the canonical catalog.

    Browser and Lua clients must consume this table rather than re-declaring
    engineering meaning. Aliases sharing a v1 name collapse into one entry.
    """
    result: dict[str, dict[str, object]] = {}
    for kind in DEFAULT_RELATION_CATALOG.entries.values():
        if not kind.public:
            continue
        result.setdefault(
            kind.v1_name,
            {
                "family": kind.semantic_family,
                "directLabel": kind.direct_label,
                "inverseLabel": kind.inverse_label,
                "sourceRole": kind.source_role,
                "targetRole": kind.target_role,
                "impactDirection": kind.impact_direction,
                "traversalDirection": kind.traversal_direction,
            },
        )
    return {name: result[name] for name in sorted(result)}


def _public_traversal_profiles() -> dict[str, list[str]]:
    """Expose canonical named traversal profiles as semantic family allowlists."""
    return {
        name: list(TRAVERSAL_PROFILES[name])
        for name in sorted(TRAVERSAL_PROFILES)
    }


def _safe_public_source(raw: str) -> str | None:
    """Return one normalized project-relative source path or deny publication."""
    value = str(raw).replace("\\", "/").strip()
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:/", value):
        return None
    parts = [part for part in value.split("/") if part not in ("", ".")]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def _public_edge_provenance(snapshot: AnalysisSnapshot) -> dict[tuple[str, str, str], list[dict[str, object]]]:
    """Collect only safe, relative source metadata for authored relations."""
    result: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for relation in snapshot.relations:
        key = (relation.source, relation.target, relation.v1_name)
        bucket = result.setdefault(key, [])
        for location in relation.provenance:
            source = _safe_public_source(location.file)
            if source is None:
                continue
            item: dict[str, object] = {
                "file": source,
                "line": location.line,
            }
            if location.anchor:
                item["anchor"] = location.anchor
            if item not in bucket:
                bucket.append(item)
    return result


def render_public_projection(
    projection: GraphProjection,
    config: NeedsConfig,
    *,
    query_name: str | None = None,
    snapshot: AnalysisSnapshot | None = None,
) -> str:
    """Serialize a graph projection plus canonical, presentation-safe semantics."""
    payload = projection.to_dict()
    payload["relationCatalogVersion"] = DEFAULT_RELATION_CATALOG.version
    payload["relationSemantics"] = _public_relation_semantics()
    payload["traversalProfiles"] = _public_traversal_profiles()
    payload["typeRoles"] = {
        name: config.type_roles[name] for name in sorted(config.type_roles)
    }
    if snapshot is not None:
        provenance = _public_edge_provenance(snapshot)
        for edge in payload.get("edges", []):
            if not isinstance(edge, dict):
                continue
            key = (
                str(edge.get("source", "")),
                str(edge.get("target", "")),
                str(edge.get("relation", "")),
            )
            locations = provenance.get(key)
            if locations:
                edge["provenance"] = locations
    if query_name is not None:
        payload["view"]["query"] = query_name
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _safe_view_token(name: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return token or "query"


def query_view_id(name: str) -> str:
    return QUERY_VIEW_PREFIX + _safe_view_token(name)


def _build_query_projection(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    query_name: str,
) -> GraphProjection:
    selection = _selection(snapshot, config, query_name)
    return build_catalog(
        snapshot,
        node_ids=selection.node_ids,
        view_id=query_view_id(query_name),
        mode="catalog",
        limits=_limits(config),
        relations=config.graph.relations,
        layout=config.graph.layout,
        seed=config.graph.seed,
    )


def build_default_projection(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    mode: str | None = None,
    baseline_path: Path | None = None,
) -> GraphProjection:
    """The projection for a bare `{{< need-graph >}}` invocation.

    Seeds come from the default approved-requirements query; depth, relation
    allowlist, limits, layout, and seed come from the `[graph]` configuration
    block. The mode is honored verbatim (catalog by default); diff and impact
    modes additionally read the supplied baseline.
    """
    effective_mode = mode or config.graph.mode
    selection = _selection(snapshot, config)

    if effective_mode in ("diff", "impact"):
        candidate = baseline_path or DEFAULT_BASELINE_PATH
        try:
            baseline_payload = load_baseline(candidate)
        except BaselineError:
            if effective_mode == "diff":
                from .graph_projection import build_projection as _c

                return _c(
                    snapshot,
                    node_ids=selection.node_ids,
                    view_id=DEFAULT_VIEW_ID,
                    mode="catalog",
                    limits=_limits(config),
                    relations=config.graph.relations,
                    layout=config.graph.layout,
                    seed=config.graph.seed,
                )
            baseline_payload = None
        if baseline_payload is not None and effective_mode == "diff":
            return build_diff_overlay(
                baseline_payload,
                snapshot,
                config,
                node_ids=selection.node_ids,
                view_id=DEFAULT_VIEW_ID,
                recompute=True,
                relations=config.graph.relations,
                limits=_limits(config),
                layout=config.graph.layout,
                seed=config.graph.seed,
            )
        if baseline_payload is not None and effective_mode == "impact":
            return build_impact_overlay(
                baseline_payload,
                snapshot,
                config,
                node_ids=selection.node_ids,
                view_id=DEFAULT_VIEW_ID,
                recompute=True,
                relations=config.graph.relations,
                limits=_limits(config),
                layout=config.graph.layout,
                seed=config.graph.seed,
            )

    return build_catalog(
        snapshot,
        node_ids=selection.node_ids,
        view_id=DEFAULT_VIEW_ID,
        mode="catalog",
        limits=_limits(config),
        relations=config.graph.relations,
        layout=config.graph.layout,
        seed=config.graph.seed,
    )


def write_default_projection(
    root: Path,
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
) -> Path:
    """Write the default graph plus reusable projections for every named query.

    Named query projections deliberately reuse the safe Python query evaluator.
    They are optional presentation artifacts: exceeding the graph budget records
    an unavailable view instead of turning an otherwise valid engineering graph
    into a failed build.
    """
    graph_dir = root / ".quarto-needs" / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    for stale in graph_dir.glob(f"{QUERY_VIEW_PREFIX}*.json"):
        stale.unlink()

    projection = build_default_projection(
        snapshot, config, baseline_path=_baseline_path(root, config)
    )
    target = graph_dir / f"{DEFAULT_VIEW_ID}.json"
    _atomic_text(
        target,
        render_public_projection(projection, config, snapshot=snapshot),
    )
    write_graph_overlays(root, snapshot, config)

    manifest: dict[str, str] = {}
    errors: dict[str, str] = {}
    for query_name in sorted(config.named_query_sources):
        try:
            query_projection = _build_query_projection(snapshot, config, query_name)
        except GraphLimitExceeded as error:
            errors[query_name] = str(error)
            continue
        view_id = query_projection.view_id
        _atomic_text(
            graph_dir / f"{view_id}.json",
            render_public_projection(
                query_projection,
                config,
                query_name=query_name,
                snapshot=snapshot,
            ),
        )
        manifest[query_name] = view_id

    _atomic_text(
        graph_dir / "views.json",
        json.dumps(
            {
                "schemaVersion": "graph-views-v1",
                "queries": manifest,
                "unavailable": errors,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
    )
    return target


def _baseline_path(root: Path, config: NeedsConfig) -> Path:
    if config.graph.baseline:
        return root / config.graph.baseline
    return root / DEFAULT_BASELINE_PATH


OVERLAYS_SCHEMA = "need-graph-overlays-v1"


def build_graph_overlays(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    baseline_payload: Mapping[str, object],
) -> dict[str, object]:
    """The browser-facing annotation artifact, extracted from the *built*
    overlay projections — never re-derived. Whatever the diff/impact builders
    compute is exactly what this artifact carries, so the browser can never
    present annotations that disagree with the overlays themselves.
    """
    selection = _selection(snapshot, config)
    common: dict[str, object] = dict(
        view_id=DEFAULT_VIEW_ID,
        recompute=True,
        relations=config.graph.relations,
        limits=_limits(config),
        layout=config.graph.layout,
        seed=config.graph.seed,
    )
    diff_view = build_diff_overlay(
        baseline_payload, snapshot, config, node_ids=selection.node_ids, **common
    )
    impact_view = build_impact_overlay(
        baseline_payload, snapshot, config, node_ids=selection.node_ids, **common
    )

    return {
        "schemaVersion": OVERLAYS_SCHEMA,
        "view": DEFAULT_VIEW_ID,
        "diff": {
            "nodes": {
                node.id: node.change
                for node in diff_view.nodes
                if node.change not in (None, "unchanged", "removed")
            },
            "edges": [
                [edge.source, edge.relation, edge.target, edge.change]
                for edge in diff_view.edges
                if edge.change not in (None, "unchanged", "removed")
            ],
            "ghostNodes": [
                node.to_dict() for node in diff_view.nodes if node.change == "removed"
            ],
            "ghostEdges": [
                edge.to_dict() for edge in diff_view.edges if edge.change == "removed"
            ],
        },
        "impact": {
            "entries": [entry.to_dict() for entry in impact_view.impact],
            "pathEdges": [
                [edge.source, edge.relation, edge.target]
                for edge in impact_view.edges
                if edge.path_member
            ],
            "ghostNodes": [
                node.to_dict() for node in impact_view.nodes if node.change == "removed"
            ],
            "ghostEdges": [
                edge.to_dict() for edge in impact_view.edges if edge.change == "removed"
            ],
        },
    }


def write_graph_overlays(
    root: Path,
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
) -> Path | None:
    """Write the overlay annotation artifact when a comparison baseline exists.

    Optional presentation artifact with the same contract as the named-query
    projections: no baseline means no artifact and no failed build — the
    browser simply never sees a mode switcher. The same graceful-degradation
    contract applies when the diff/impact traversal itself exceeds the
    configured budget (it is not the same selection as the plain catalog
    view, so it can exceed budget even when the catalog comfortably fits).
    """
    try:
        baseline_payload = load_baseline(_baseline_path(root, config))
    except BaselineError:
        return None
    try:
        overlays = build_graph_overlays(snapshot, config, baseline_payload=baseline_payload)
    except GraphLimitExceeded:
        return None
    graph_dir = root / ".quarto-needs" / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    target = graph_dir / f"{DEFAULT_VIEW_ID}-overlays.json"
    _atomic_text(
        target,
        json.dumps(overlays, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return target


def write_c4_projections(root: Path, snapshot: AnalysisSnapshot) -> None:
    """Pre-render every system's Context/Container view and every
    container's Component view (plus each component's Code-level table).

    Unlike named-query views, C4 views need no project configuration: the
    full set is derived directly from which objects exist as `system`/
    `container`/`component` types, so there is nothing for a project to
    declare and nothing that can drift out of sync with the graph.
    """
    from .c4_projection import C4ViewError, build_c4_view
    from .c4_render import c4_code_table_markdown, c4_mermaid_source

    graph_dir = root / ".quarto-needs" / "graphs"
    for stale in graph_dir.glob("c4-*.json"):
        stale.unlink()

    def _write(view_id: str, kind: str, source: str) -> None:
        graph_dir.mkdir(parents=True, exist_ok=True)
        _atomic_text(
            graph_dir / f"{view_id}.json",
            json.dumps(
                {"schemaVersion": "c4-view-v1", "kind": kind, "source": source},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

    for record in snapshot.objects:
        if record.type == "system":
            for level in ("context", "container"):
                try:
                    projection = build_c4_view(snapshot, focus_id=record.id, level=level)
                except (C4ViewError, GraphLimitExceeded):
                    continue
                source = c4_mermaid_source(projection, focus_id=record.id, level=level)
                _write(f"c4-{level}-{record.id}", "mermaid", source)
        elif record.type == "container":
            try:
                projection = build_c4_view(snapshot, focus_id=record.id, level="component")
            except (C4ViewError, GraphLimitExceeded):
                continue
            source = c4_mermaid_source(projection, focus_id=record.id, level="component")
            _write(f"c4-component-{record.id}", "mermaid", source)
        elif record.type == "component":
            table = c4_code_table_markdown(snapshot, focus_id=record.id)
            _write(f"c4-code-{record.id}", "table", table)
