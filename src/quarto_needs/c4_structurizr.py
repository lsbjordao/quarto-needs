"""Structurizr DSL rendering for C4 views.

Mirrors c4_render.py's role for the Structurizr backend: turns an
already-computed C4 projection (graph_projection.py's GraphProjection) into
Structurizr DSL source text. Duplicates c4_render.py's own escaping/
reference helpers rather than importing them, matching this project's
established convention of small renderer modules owning their own private
helpers (see c4_render.py's own module docstring) — no renderer imports
another renderer's internals.

The module only generates DSL. Optional SVG/PNG rendering is handled by the
Quarto Lua extension through the current `structurizr` consolidated tooling.
"""
from __future__ import annotations

import re

from .graph_projection import GraphProjection, PublicEdge, PublicNode

_ELEMENT_KEYWORD = {
    "actor": "person",
    "external-system": "softwareSystem",
    "system": "softwareSystem",
    "container": "container",
    "component": "component",
    "deployment-node": "deploymentNode",
}
_VIEW_KEYWORD = {"context": "systemContext", "container": "container", "component": "component"}
_INVALID = re.compile(r"[^A-Za-z0-9_]")


def _sanitize(identifier: str) -> str:
    sanitized = _INVALID.sub("_", identifier)
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"c4_{sanitized}"
    return sanitized.lower()


def _escape(value: str) -> str:
    replaced = value.replace("\\", "/").replace('"', "'")
    return replaced.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _is_child_edge(edge: PublicEdge, *, focus_id: str, child_id: str) -> bool:
    """True if `edge` declares `child_id` as a direct child of `focus_id`.

    Mirrors c4_render.py's `_is_child_edge`: a `part-of` edge runs
    child->parent, a `decomposes` edge runs parent->child.
    """
    if edge.relation == "part-of":
        return edge.source == child_id and edge.target == focus_id
    if edge.relation == "decomposes":
        return edge.source == focus_id and edge.target == child_id
    if edge.relation == "deployed-on":
        return edge.source == child_id and edge.target == focus_id
    if edge.relation == "deploys":
        return edge.source == focus_id and edge.target == child_id
    return False


def _element_line(node: PublicNode, *, indent: str) -> str:
    keyword = _ELEMENT_KEYWORD[node.type]
    variable = _sanitize(node.id)
    parts = [f'"{_escape(node.title)}"']
    if node.technology:
        parts.append(f'"{_escape(node.technology)}"')
    tags = ' tags "External"' if node.type == "external-system" else ""
    return f'{indent}{variable} = {keyword} {" ".join(parts)}{tags}'


def _deployment_element_line(node: PublicNode, *, indent: str) -> str:
    """A deployed artifact as a deployment node.

    Structurizr's `containerInstance` needs the referenced container defined
    elsewhere in the same workspace, and a deployment view's projection does
    not carry the container's owning system. The runtime a container occupies
    is itself a deployment node in Structurizr's vocabulary, so the deployed
    artifact is emitted that way, with its technology.
    """
    parts = [f'"{_escape(node.title)}"']
    if node.technology:
        parts.append(f'"{_escape(node.technology)}"')
    return f'{indent}{_sanitize(node.id)} = deploymentNode {" ".join(parts)}'


def _deployment_source(
    *,
    focus: PublicNode,
    focus_variable: str,
    children: list[PublicNode],
    depends_on_edges: list[PublicEdge],
) -> str:
    environment = _escape(focus.title)
    focus_parts = [f'"{environment}"']
    if focus.technology:
        focus_parts.append(f'"{_escape(focus.technology)}"')
    child_ids = {node.id for node in children}
    lines = [
        "workspace {",
        "  model {",
        f'    deploymentEnvironment "{environment}" {{',
        f'      {focus_variable} = deploymentNode {" ".join(focus_parts)} {{',
    ]
    for node in children:
        lines.append(_deployment_element_line(node, indent="        "))
    for edge in depends_on_edges:
        if edge.source not in child_ids or edge.target not in child_ids:
            continue
        technology = f' "{_escape(edge.technology)}"' if edge.technology else ""
        lines.append(
            f'        {_sanitize(edge.source)} -> {_sanitize(edge.target)} '
            f'"{_escape(edge.label)}"{technology}'
        )
    lines.extend([
        "      }",
        "    }",
        "  }",
        "  views {",
        f'    deployment * "{environment}" {{',
        "      include *",
        "      autoLayout",
        "    }",
        "  }",
        "}",
    ])
    return "\n".join(lines) + "\n"


def c4_structurizr_source(projection: GraphProjection, *, focus_id: str, level: str) -> str:
    """Deterministic Structurizr DSL source for one focus node's view.

    Node/edge order follows the projection's own canonical order, so two
    renders of an equivalent projection are byte-identical (same guarantee
    c4_mermaid_source makes).
    """
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

    focus_variable = _sanitize(focus.id)
    if level == "deployment":
        return _deployment_source(
            focus=focus,
            focus_variable=focus_variable,
            children=children,
            depends_on_edges=depends_on_edges,
        )
    view_keyword = _VIEW_KEYWORD[level]
    lines = ["workspace {", "  model {"]
    for node in others:
        lines.append(_element_line(node, indent="    "))
    if level == "context":
        lines.append(_element_line(focus, indent="    "))
    else:
        keyword = _ELEMENT_KEYWORD[focus.type]
        lines.append(f'    {focus_variable} = {keyword} "{_escape(focus.title)}" {{')
        for node in children:
            lines.append(_element_line(node, indent="      "))
        lines.append("    }")

    for edge in depends_on_edges:
        source_variable = _sanitize(edge.source)
        target_variable = _sanitize(edge.target)
        technology = f' "{_escape(edge.technology)}"' if edge.technology else ""
        lines.append(
            f'    {source_variable} -> {target_variable} '
            f'"{_escape(edge.label)}"{technology}'
        )

    lines.extend([
        "  }",
        "  views {",
        f"    {view_keyword} {focus_variable} {{",
        "      include *",
        "      autoLayout",
        "    }",
        "  }",
        "}",
    ])
    return "\n".join(lines) + "\n"
