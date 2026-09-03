"""Deterministic Graphviz/DOT output for public graph projections."""
from __future__ import annotations

from .graph_projection import GraphProjection, PublicEdge, PublicNode


def _quote(value: str, *, preserve_newlines: bool = False) -> str:
    newline_marker = "\x00"
    if preserve_newlines:
        value = value.replace("\\n", newline_marker)
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
    )
    if preserve_newlines:
        escaped = escaped.replace(newline_marker, "\\n")
    return f'"{escaped}"'


def _node_label(node: PublicNode) -> str:
    parts = [node.id, node.title, node.type, node.status]
    if node.priority:
        parts.append(node.priority)
    if node.change not in (None, "unchanged"):
        parts.append(node.change)
    return "\\n".join(parts)


def _edge_label(edge: PublicEdge) -> str:
    suffix = []
    if edge.change not in (None, "unchanged"):
        suffix.append(edge.change)
    if edge.path_member:
        suffix.append("path")
    return edge.label + (f" ({', '.join(suffix)})" if suffix else "")


def _shape(node_type: str) -> str:
    return {
        "actor": "ellipse",
        "external-system": "box3d",
        "system": "box",
        "container": "component",
        "component": "note",
    }.get(node_type, "box")


def dot_source(projection: GraphProjection) -> str:
    """Return stable DOT for the public graph projection."""
    lines = ["digraph quarto_needs {", "  rankdir=LR;", '  graph [fontname="sans"];', '  node [fontname="sans"];', '  edge [fontname="sans"];']
    for node in projection.nodes:
        lines.append(
            f"  {_quote(node.id)} [label={_quote(_node_label(node), preserve_newlines=True)}, shape={_shape(node.type)}];"
        )
    for edge in projection.edges:
        lines.append(
            f"  {_quote(edge.source)} -> {_quote(edge.target)} [label={_quote(_edge_label(edge))}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"
