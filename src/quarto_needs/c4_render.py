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
from .snapshot import AnalysisSnapshot, RelationRecord

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

    depends_on_edges = [edge for edge in projection.edges if edge.relation == "depends-on"]
    if level == "context":
        drawn_edges = depends_on_edges
        visible_others = others
    else:
        # At container/component level the focus is drawn as a boundary
        # macro, not a positioned node — mermaid 11.6.0's C4 layout engine
        # throws mid-render when a Rel targets a boundary's own alias
        # (verified against Quarto's exact bundled mermaid.js in a real
        # browser). The relationship isn't lost: the context diagram one
        # level up already shows it against the system/container as a whole.
        drawn_edges = [
            edge for edge in depends_on_edges if focus_id not in (edge.source, edge.target)
        ]
        # Dropping that edge is not enough on its own: an "other" node left
        # with no remaining edge renders as a disconnected floating box with
        # no indication of why it's on the diagram (confirmed with a real
        # screenshot of the actual rendered SVG) — worse than the crash it
        # replaced. Omit it entirely, matching standard C4 practice: this
        # level only depicts things that interact with something it shows.
        connected_ids = {edge.source for edge in drawn_edges} | {
            edge.target for edge in drawn_edges
        }
        visible_others = [node for node in others if node.id in connected_ids]

    lines = [diagram_type, '  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")']
    if level == "context":
        lines.append(f"  {_macro_call(focus)}")
        for node in visible_others:
            lines.append(f"  {_macro_call(node)}")
    else:
        boundary_macro = _BOUNDARY_MACRO[level]
        lines.append(
            f'  {boundary_macro}({_ref(focus.id)}, "{_escape(focus.title)}") {{'
        )
        for node in children:
            lines.append(f"    {_macro_call(node)}")
        lines.append("  }")
        for node in visible_others:
            lines.append(f"  {_macro_call(node)}")

    for edge in drawn_edges:
        lines.append(f'  Rel({_ref(edge.source)}, {_ref(edge.target)}, "{_escape(edge.label)}")')

    return "\n".join(lines) + "\n"


def _child_id_if_matches(relation: RelationRecord, *, focus_id: str) -> str | None:
    """The child's id if `relation` declares it a direct child of `focus_id`.

    Mirrors `_is_child_edge`'s dual-direction handling above: a `part-of`
    edge runs child→parent (source=child, target=focus), a `decomposes`
    edge runs parent→child (source=focus, target=child). Checking only
    `part-of` would silently drop any component whose source-modules were
    authored from the parent's side via `decomposes` instead — the exact
    failure shape this function's own sibling, `_is_child_edge`, exists to
    avoid.
    """
    if relation.authored_name == "part-of" and relation.target == focus_id:
        return relation.source
    if relation.authored_name == "decomposes" and relation.source == focus_id:
        return relation.target
    return None


def c4_code_table_markdown(snapshot: AnalysisSnapshot, *, focus_id: str) -> str:
    """A plain Markdown table of one component's direct source-module children.

    Code level is not a diagram: Mermaid has no C4-Code diagram type, and
    source-module objects have no interaction arrows to draw (their only
    relation today is `implements`, to a requirement, not to each other).
    """
    child_ids = {
        child_id
        for relation in snapshot.relations
        if (child_id := _child_id_if_matches(relation, focus_id=focus_id)) is not None
        and child_id in snapshot.objects_by_id
        and snapshot.objects_by_id[child_id].type == "source-module"
    }
    children = sorted(
        (snapshot.objects_by_id[child_id] for child_id in child_ids),
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
