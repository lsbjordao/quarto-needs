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
from .relations import DEFAULT_RELATION_CATALOG
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


def render_public_projection(
    projection: GraphProjection,
    config: NeedsConfig,
    *,
    query_name: str | None = None,
) -> str:
    """Serialize a graph projection plus canonical, presentation-safe semantics."""
    payload = projection.to_dict()
    payload["relationCatalogVersion"] = DEFAULT_RELATION_CATALOG.version
    payload["relationSemantics"] = _public_relation_semantics()
    payload["typeRoles"] = {
        name: config.type_roles[name] for name in sorted(config.type_roles)
    }
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
        snapshot, config, baseline_path=root / DEFAULT_BASELINE_PATH
    )
    target = graph_dir / f"{DEFAULT_VIEW_ID}.json"
    _atomic_text(target, render_public_projection(projection, config))

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
            render_public_projection(query_projection, config, query_name=query_name),
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
