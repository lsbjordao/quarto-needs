"""One C4 view: a focus object plus one level of its part-of/depends-on
neighborhood.

Reuses graph_projection.py's existing bounded selection (select_graph) and
projection builder (build_projection) unchanged — Context, Container, and
Component views are all the same operation (focus + depth 1 over
decomposes/depends-on), differing only in which relations are allowed and
what type the focus must be. No new selection algorithm.
"""
from __future__ import annotations

from typing import Mapping

from .graph_projection import GraphProjection, build_projection, select_graph
from .snapshot import AnalysisSnapshot


class C4ViewError(Exception):
    """Raised when a C4 view is requested for an invalid focus/level pair."""


_LEVEL_FOCUS_TYPE: Mapping[str, str] = {
    "context": "system",
    "container": "system",
    "component": "container",
    "deployment": "deployment-node",
    "dynamic": "system",
}

_LEVEL_RELATIONS: Mapping[str, tuple[str, ...]] = {
    "context": ("depends-on",),
    "container": ("part-of", "decomposes", "depends-on"),
    "component": ("part-of", "decomposes", "depends-on"),
    "deployment": ("part-of", "decomposes", "deployed-on", "deploys", "depends-on"),
}

# Every object type the C4 model gives a role to. Interaction partners that
# are not architecture elements (a requirement, say) are simply not drawn.
_C4_TYPES = frozenset(
    {
        "actor",
        "external-system",
        "system",
        "container",
        "component",
        "source-module",
        "deployment-node",
    }
)

_INTERACTION_RELATION = "interacts-with"


def _dynamic_node_ids(snapshot: AnalysisSnapshot, focus_id: str) -> tuple[str, ...]:
    """The participants of one dynamic view, in deterministic order.

    The focus, its direct containment children, and every architecture
    element connected to that set by an interaction are participants. The
    interaction expansion runs after the containment expansion so an
    interaction between two children (neither touching the focus) is still
    drawn, which the generic depth-1 selection would miss.
    """
    selected = {focus_id}

    def is_transformable(identifier: str) -> bool:
        record = snapshot.objects_by_id.get(identifier)
        return record is not None and record.type in _C4_TYPES

    for relation in snapshot.relations:
        if relation.v1_name == "part-of" and relation.target == focus_id:
            candidate = relation.source
        elif relation.v1_name == "decomposes" and relation.source == focus_id:
            candidate = relation.target
        else:
            continue
        if is_transformable(candidate):
            selected.add(candidate)

    for relation in snapshot.relations:
        if relation.v1_name != _INTERACTION_RELATION:
            continue
        if relation.source in selected and is_transformable(relation.target):
            selected.add(relation.target)
        elif relation.target in selected and is_transformable(relation.source):
            selected.add(relation.source)

    return tuple(
        sorted(selected, key=lambda identifier: (identifier.casefold(), identifier))
    )


def build_c4_view(
    snapshot: AnalysisSnapshot,
    *,
    focus_id: str,
    level: str,
    limits: Mapping[str, int] | None = None,
) -> GraphProjection:
    if level not in _LEVEL_FOCUS_TYPE:
        raise C4ViewError(
            f"unsupported C4 level: {level!r} (expected one of "
            f"{', '.join(sorted(_LEVEL_FOCUS_TYPE))})"
        )
    focus = snapshot.objects_by_id.get(focus_id)
    if focus is None:
        raise C4ViewError(f"{focus_id!r} is not a known object")
    expected_type = _LEVEL_FOCUS_TYPE[level]
    if focus.type != expected_type:
        raise C4ViewError(
            f"level={level!r} requires a {expected_type!r} focus, "
            f"but {focus_id!r} is {focus.type!r}"
        )
    if level == "dynamic":
        return build_projection(
            snapshot,
            node_ids=_dynamic_node_ids(snapshot, focus_id),
            view_id=f"c4-{level}-{focus_id}",
            mode="c4",
            relations=("part-of", "decomposes", _INTERACTION_RELATION),
            limits=limits,
        )
    relations = _LEVEL_RELATIONS[level]
    selection = select_graph(
        snapshot, seeds=(focus_id,), relations=relations, depth=1, limits=limits
    )
    return build_projection(
        snapshot,
        node_ids=selection.node_ids,
        view_id=f"c4-{level}-{focus_id}",
        mode="c4",
        relations=relations,
        limits=limits,
    )
