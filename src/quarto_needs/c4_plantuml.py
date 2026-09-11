"""C4-PlantUML rendering for C4 views.

Mirrors c4_render.py's role for the C4-PlantUML backend. C4-PlantUML's own
macro vocabulary (Person, System, System_Ext, Container, Component,
System_Boundary, Container_Boundary, Rel) is the same one Mermaid's C4
diagrams borrow from, so the shape of this module tracks c4_render.py
closely -- but it duplicates every helper rather than importing them, per
this project's established renderer-module convention (see c4_render.py's
own module docstring): no renderer imports another renderer's internals.

Source generation only: nothing here shells out to `plantuml`. The `.puml`
text is the deliverable.
"""
from __future__ import annotations

from .graph_projection import GraphProjection, PublicEdge, PublicNode

_MACRO_BY_TYPE = {
    "actor": "Person",
    "external-system": "System_Ext",
    "system": "System",
    "container": "Container",
    "component": "Component",
    "deployment-node": "Deployment_Node",
}
_INCLUDE_BY_LEVEL = {
    "context": "C4_Context",
    "container": "C4_Container",
    "component": "C4_Component",
    "deployment": "C4_Deployment",
}
_BOUNDARY_MACRO = {
    "container": "System_Boundary",
    "component": "Container_Boundary",
    "deployment": "Deployment_Node",
}


def _ref(identifier: str) -> str:
    sanitized = "".join(character if character.isalnum() else "_" for character in identifier)
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"c4_{sanitized}"
    return sanitized


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
    if edge.relation == "part-of":
        return edge.source == child_id and edge.target == focus_id
    if edge.relation == "decomposes":
        return edge.source == focus_id and edge.target == child_id
    if edge.relation == "deployed-on":
        return edge.source == child_id and edge.target == focus_id
    if edge.relation == "deploys":
        return edge.source == focus_id and edge.target == child_id
    return False


def c4_plantuml_source(projection: GraphProjection, *, focus_id: str, level: str) -> str:
    """Deterministic C4-PlantUML source for one focus node's view."""
    include = _INCLUDE_BY_LEVEL[level]
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
    depends_on_edges = [edge for edge in projection.edges if edge.relation == "depends-on"]

    lines = ["@startuml", f"!include <C4/{include}>", ""]
    if level == "context":
        lines.append(_macro_call(focus))
        for node in others:
            lines.append(_macro_call(node))
    else:
        boundary_macro = _BOUNDARY_MACRO[level]
        lines.append(f'{boundary_macro}({_ref(focus.id)}, "{_escape(focus.title)}") {{')
        for node in children:
            lines.append(f"  {_macro_call(node)}")
        lines.append("}")
        for node in others:
            lines.append(_macro_call(node))

    lines.append("")
    for edge in depends_on_edges:
        technology = f', "{_escape(edge.technology)}"' if edge.technology else ""
        lines.append(
            f'Rel({_ref(edge.source)}, {_ref(edge.target)}, '
            f'"{_escape(edge.label)}"{technology})'
        )
    lines.extend(["", "@enduml"])
    return "\n".join(lines) + "\n"
