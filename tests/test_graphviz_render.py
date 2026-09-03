from __future__ import annotations

import subprocess

from quarto_needs.graph_projection import GraphProjection, PublicEdge, PublicNode
from quarto_needs.graphviz_render import dot_source


def _projection() -> GraphProjection:
    return GraphProjection(
        view_id="need-graph-1",
        mode="catalog",
        limits={"nodes": 100, "edges": 300},
        nodes=(
            PublicNode("REQ-1", "A \"quoted\" requirement", "functional-requirement", "approved", None, (), "#REQ-1"),
            PublicNode("SYS-1", "Quarto-Needs", "system", "draft", None, (), "#SYS-1"),
        ),
        edges=(PublicEdge("REQ-1", "SYS-1", "depends-on", "Depends on"),),
    )


def test_dot_source_is_deterministic_and_escaped() -> None:
    source = dot_source(_projection())
    assert source == dot_source(_projection())
    assert 'A \\"quoted\\" requirement' in source
    assert '"REQ-1" -> "SYS-1"' in source
    assert "rankdir=LR" in source


def test_dot_source_keeps_semantic_labels_visible() -> None:
    source = dot_source(_projection())
    assert "REQ-1\\nA \\\"quoted\\\" requirement\\nfunctional-requirement\\napproved" in source
    assert 'label="Depends on"' in source


def test_dot_source_is_accepted_by_graphviz(tmp_path) -> None:
    dot_file = tmp_path / "graph.dot"
    dot_file.write_text(dot_source(_projection()), encoding="utf-8")
    result = subprocess.run(
        ["dot", "-Tsvg", str(dot_file)], capture_output=True, check=True
    )
    assert b"<svg" in result.stdout
