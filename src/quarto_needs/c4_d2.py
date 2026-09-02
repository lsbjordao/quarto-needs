"""D2 rendering for C4 views.

Mirrors c4_render.py's role for the D2 backend. D2 has no dedicated C4
macro vocabulary, so containment is expressed through D2's own nested-map
syntax (a child element declared inside its parent's `{ }` block) and
relationships to a nested child are addressed by dotted path
(`parent.child`), matching D2's own key-addressing rules. Duplicates
c4_render.py's helpers rather than importing them, per this project's
established renderer-module convention.

Source generation only: nothing here shells out to the `d2` binary. The
`.d2` text is the deliverable.
"""
from __future__ import annotations

import re

from .graph_projection import GraphProjection, PublicEdge, PublicNode

_SHAPE_BY_TYPE = {
    "actor": "person",
    "external-system": "hexagon",
    "system": "rectangle",
    "container": "rectangle",
    "component": "rectangle",
}
_INVALID = re.compile(r"[^A-Za-z0-9_]")


def _sanitize(identifier: str) -> str:
    sanitized = _INVALID.sub("_", identifier)
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"c4_{sanitized}"
    return sanitized


def _escape(value: str) -> str:
    replaced = value.replace("\\", "/").replace('"', "'")
    return replaced.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _label(node: PublicNode) -> str:
    label = node.title if not node.technology else f"{node.title} ({node.technology})"
    return _escape(label)


def _is_child_edge(edge: PublicEdge, *, focus_id: str, child_id: str) -> bool:
    if edge.relation == "part-of":
        return edge.source == child_id and edge.target == focus_id
    if edge.relation == "decomposes":
        return edge.source == focus_id and edge.target == child_id
    return False


def c4_d2_source(projection: GraphProjection, *, focus_id: str, level: str) -> str:
    """Deterministic D2 source for one focus node's view."""
    focus = next(node for node in projection.nodes if node.id == focus_id)
    children = [
        node
        for node in projection.nodes
        if node.id != focus_id
        and any(
            _is_child_edge(edge, focus_id=focus_id, child_id=node.id)
            for edge in projection.edges
        )
    ]
    others = [node for node in projection.nodes if node.id != focus_id and node not in children]
    child_ids = {node.id for node in children}
    depends_on_edges = [edge for edge in projection.edges if edge.relation == "depends-on"]

    lines: list[str] = []
    for node in others:
        variable = _sanitize(node.id)
        lines.extend(
            [
                f'{variable}: "{_label(node)}" {{',
                f"  shape: {_SHAPE_BY_TYPE[node.type]}",
                "}",
            ]
        )

    focus_variable = _sanitize(focus.id)
    lines.append(f'{focus_variable}: "{_label(focus)}" {{')
    lines.append(f"  shape: {_SHAPE_BY_TYPE[focus.type]}")
    for node in children:
        child_variable = _sanitize(node.id)
        lines.extend(
            [
                f'  {child_variable}: "{_label(node)}" {{',
                f"    shape: {_SHAPE_BY_TYPE[node.type]}",
                "  }",
            ]
        )
    lines.append("}")

    for edge in depends_on_edges:
        source_variable = _sanitize(edge.source)
        target_variable = _sanitize(edge.target)
        if edge.source in child_ids:
            source_variable = f"{focus_variable}.{source_variable}"
        if edge.target in child_ids:
            target_variable = f"{focus_variable}.{target_variable}"
        lines.append(f'{source_variable} -> {target_variable}: "{_escape(edge.label)}"')

    return "\n".join(lines) + "\n"
