"""Static rendering of the public graph projection.

Renderer decision (made during implementation, as the milestone directs):
Mermaid.js as bundled with Quarto, rendered locally by Quarto's built-in
mermaid support — this project adds no network call. Mermaid is MIT-licensed;
the version is whatever the local Quarto release pins (verified against
1.8.26 here), and the emitted source is plain `flowchart LR` text. This
module emits text only; it never invokes a browser or a JavaScript runtime.

Everything a reader needs is text: change markers, path membership, and
relation labels are words, never colors, so the diagram survives monochrome
PDF and any color vision as-is.
"""
from __future__ import annotations

from dataclasses import dataclass

from .graph_projection import GraphProjection, PublicEdge, PublicNode

NODE_PREFIX = "need_"


def _ref(identifier: str) -> str:
    """Mermaid node id: hex of the public id, collision-free and deterministic."""
    return NODE_PREFIX + identifier.encode("utf-8").hex()


def _escape(value: str) -> str:
    """Neutralize Mermaid syntax inside quoted labels.

    Mirrors `views.escape_mermaid` in the Lua extension (`"`→`'`, `\\`→`/`,
    newlines→space) and additionally defuses `|` and arrow/link runs, which
    would otherwise break out of a label or forge an edge.
    """
    replaced = (
        value.replace("\\", "/")
        .replace('"', "'")
        .replace("|", "/")
        .replace("-->", "→")
        .replace("---", "—")
    )
    return replaced.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _node_label(node: PublicNode) -> str:
    heading = " · ".join(part for part in (node.id, node.title) if part)
    facets = " · ".join(
        part for part in (node.type, node.status, node.priority or "") if part
    )
    if node.change not in (None, "unchanged"):
        facets += f" — {node.change}"
    return _escape(heading) + "<br/>" + _escape(facets)


def _edge_label(edge: PublicEdge) -> str:
    suffix = ""
    if edge.change not in (None, "unchanged"):
        suffix = f" ({edge.change})"
    if edge.path_member:
        suffix += " (path)"
    return _escape(edge.label + suffix)


def mermaid_source(projection: GraphProjection) -> str:
    """Deterministic `flowchart LR` source for a projection.

    Lines follow the projection's canonical node and edge order, so two
    renders of equivalent input are byte-identical — that is what the golden
    tests pin.
    """
    lines = ["flowchart LR"]
    for node in projection.nodes:
        lines.append(f'  {_ref(node.id)}["{_node_label(node)}"]')
    for edge in projection.edges:
        lines.append(f'  {_ref(edge.source)} -->|"{_edge_label(edge)}"| {_ref(edge.target)}')
    return "\n".join(lines) + "\n"


@dataclass(frozen=True, slots=True)
class EdgeRow:
    """One accessible-table row: source, relation, target, change, impact."""

    source: str
    relation: str
    target: str
    change: str
    impact: str


def _impact_texts(projection: GraphProjection) -> dict[tuple[str, str], list[str]]:
    explanations: dict[tuple[str, str], list[str]] = {}
    for entry in projection.impact:
        hops = "hop" if entry.distance == 1 else "hops"
        classification = entry.classification or "impact"
        text = " → ".join(entry.path) + f" ({classification}, {entry.distance} {hops})"
        for left, right in zip(entry.path, entry.path[1:]):
            explanations.setdefault((left, right), []).append(text)
    return explanations


def edge_table_rows(projection: GraphProjection) -> tuple[EdgeRow, ...]:
    """Table data carrying every edge's change state and impact explanation.

    The explanation names the full path, classification, and distance of each
    impacted entry that travels through the edge — the table, not the canvas,
    is where propagation is explained.
    """
    explanations = _impact_texts(projection)
    rows: list[EdgeRow] = []
    for edge in projection.edges:
        hits = (explanations.get((edge.source, edge.target)) or []) + (
            explanations.get((edge.target, edge.source)) or []
        )
        rows.append(
            EdgeRow(
                source=edge.source,
                relation=edge.label,
                target=edge.target,
                change=edge.change or "",
                impact="; ".join(hit for hit in hits if hit),
            )
        )
    return tuple(rows)


def summary_entries(projection: GraphProjection) -> tuple[tuple[str, str], ...]:
    """Display pairs summarizing a graph instance with counts.

    Counts are shown against the configured limits so a narrowed selection
    is visible as numbers, not discovered by scrolling.
    """
    entries: list[tuple[str, str]] = [
        ("mode", projection.mode),
        ("nodes", f"{len(projection.nodes)} / {projection.limits['nodes']}"),
        ("edges", f"{len(projection.edges)} / {projection.limits['edges']}"),
    ]
    if projection.mode == "diff":
        counts: dict[str, int] = {}
        for node in projection.nodes:
            if node.change:
                counts[node.change] = counts.get(node.change, 0) + 1
        for key in ("added", "removed", "modified", "relocated"):
            entries.append((f"nodes {key}", str(counts.get(key, 0))))
    if projection.mode == "impact":
        total = len(projection.impact)
        direct = sum(1 for entry in projection.impact if entry.classification == "direct")
        entries.append(("impacted", str(total)))
        entries.append(("direct", str(direct)))
        entries.append(("transitive", str(total - direct)))
    return tuple(entries)
