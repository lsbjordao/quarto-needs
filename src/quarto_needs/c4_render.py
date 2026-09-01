"""Mermaid C4 diagram and Code-level table rendering.

Mirrors graph_render.py's role (static text rendering of an
already-computed projection) for the C4-specific diagram types. `_ref`/
`_escape` duplicate graph_render.py's private helpers rather than
importing them — the same choice already made for github_issues.py's
_origin duplicating oslc_http.py's rather than reaching into another
module's underscore-prefixed internals.
"""
from __future__ import annotations

from .graph_projection import GraphProjection, PublicEdge, PublicNode
from .snapshot import AnalysisSnapshot

NODE_PREFIX = "c4_"

_MACRO_BY_TYPE = {
    "actor": "Person",
    "external-system": "System_Ext",
    "system": "System",
    "container": "Container",
    "component": "Component",
}
_DIAGRAM_TYPE = {
    "context": "C4Context",
    "container": "C4Container",
    "component": "C4Component",
}
_BOUNDARY_MACRO = {"container": "System_Boundary", "component": "Container_Boundary"}


def _ref(identifier: str) -> str:
    return NODE_PREFIX + identifier.encode("utf-8").hex()


def _escape(value: str) -> str:
    replaced = value.replace("\\", "/").replace('"', "'")
    return replaced.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _macro_call(node: PublicNode) -> str:
    macro = _MACRO_BY_TYPE[node.type]
    args = [_ref(node.id), f'"{_escape(node.title)}"']
    if node.technology:
        args.append(f'"{_escape(node.technology)}"')
    return f"{macro}({', '.join(args)})"


def _is_child_edge(edge: PublicEdge, *, focus_id: str, child_id: str) -> bool:
    """True if `edge` declares `child_id` as a direct child of `focus_id`.

    Handles both authored directions: a `part-of` edge runs child→parent
    (source=child, target=focus — this project's own retrofit authors
    exclusively this direction), a `decomposes` edge runs parent→child
    (source=focus, target=child). Checking only one direction would miss
    every part-of-authored edge, which is exactly what this project's own
    content uses.
    """
    if edge.relation == "part-of":
        return edge.source == child_id and edge.target == focus_id
    if edge.relation == "decomposes":
        return edge.source == focus_id and edge.target == child_id
    return False


def c4_mermaid_source(projection: GraphProjection, *, focus_id: str, level: str) -> str:
    """Deterministic Mermaid C4 source for one focus node's view.

    Node and edge order follows the projection's own canonical order (the
    same determinism guarantee graph_render.py's mermaid_source makes), so
    two renders of an equivalent projection are byte-identical.
    """
    diagram_type = _DIAGRAM_TYPE[level]
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
    others = [
        node
        for node in projection.nodes
        if node.id != focus_id and node not in children
    ]

    lines = [diagram_type]
    if level == "context":
        lines.append(f"  {_macro_call(focus)}")
        for node in others:
            lines.append(f"  {_macro_call(node)}")
    else:
        boundary_macro = _BOUNDARY_MACRO[level]
        lines.append(
            f'  {boundary_macro}({_ref(focus.id)}, "{_escape(focus.title)}") {{'
        )
        for node in children:
            lines.append(f"    {_macro_call(node)}")
        lines.append("  }")
        for node in others:
            lines.append(f"  {_macro_call(node)}")

    for edge in projection.edges:
        if edge.relation != "depends-on":
            continue
        lines.append(f'  Rel({_ref(edge.source)}, {_ref(edge.target)}, "{_escape(edge.label)}")')

    return "\n".join(lines) + "\n"


def c4_code_table_markdown(snapshot: AnalysisSnapshot, *, focus_id: str) -> str:
    """A plain Markdown table of one component's direct source-module children.

    Code level is not a diagram: Mermaid has no C4-Code diagram type, and
    source-module objects have no interaction arrows to draw (their only
    relation today is `implements`, to a requirement, not to each other).
    """
    children = sorted(
        (
            snapshot.objects_by_id[relation.source]
            for relation in snapshot.relations
            if relation.authored_name == "part-of"
            and relation.target == focus_id
            and relation.source in snapshot.objects_by_id
            and snapshot.objects_by_id[relation.source].type == "source-module"
        ),
        key=lambda record: record.id,
    )
    lines = ["| ID | Path | Language | Implements |", "| --- | --- | --- | --- |"]
    for record in children:
        implements = ", ".join(
            sorted(
                relation.target
                for relation in snapshot.relations
                if relation.v1_name == "implements" and relation.source == record.id
            )
        )
        path = str(record.attributes.get("path", ""))
        language = str(record.attributes.get("language", ""))
        lines.append(f"| {record.id} | {path} | {language} | {implements} |")
    return "\n".join(lines) + "\n"
