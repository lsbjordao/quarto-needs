from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from quarto_needs import baseline, graph_projection, graph_render
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "graph" / "adversarial.qmd"
GOLDEN_CATALOG = ROOT / "tests" / "fixtures" / "graph" / "golden-catalog.mmd"
GOLDEN_DIFF = ROOT / "tests" / "fixtures" / "graph" / "golden-diff.mmd"

NODE_LINE = re.compile(r'^  (need_[0-9a-fA-F]+)\["(.+)"\]$')
EDGE_LINE = re.compile(r'^  (need_[0-9a-fA-F]+) -->\|"(.*)"\| (need_[0-9a-fA-F]+)$')

# --- fixtures ----------------------------------------------------------------


def catalog_projection(tmp_path: Path) -> graph_projection.GraphProjection:
    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = analyze_project(tmp_path)
    assert result.snapshot is not None
    return graph_projection.build_projection(
        result.snapshot, node_ids=("ADV-1", "ADV-2"), view_id="need-graph-1"
    )


V1_A = (
    "::: {.need #REQ-1 type=functional-requirement status=approved priority=high tags=\"core\"}\n"
    "verified-by:\n"
    "  - TC-1\n"
    "  - TC-2\n"
    "\n## Authenticate\nOriginal body.\n:::\n"
    "\n"
    "::: {.need #REQ-2 type=functional-requirement status=draft priority=low tags=\"aux\"}\n"
    "\n## Legacy\nBaseline-only prose.\n:::\n"
    "\n"
    "::: {.need #TC-1 type=test-case status=passed}\n\n## Login test\nSigns a user in.\n:::\n"
)

V1_B = (
    "::: {.need #TC-2 type=test-case status=passed}\n\n## Logout test\nSigns a user out.\n:::\n"
)

V2_A = (
    "::: {.need #REQ-1 type=functional-requirement status=approved priority=high tags=\"core\"}\n"
    "verified-by:\n"
    "  - TC-2\n"
    "\n## Authenticate\nEdited body.\n:::\n"
    "\n"
    "::: {.need #REQ-3 type=functional-requirement status=draft priority=medium tags=\"new\"}\n"
    "verified-by: TC-2\n"
    "\n## Fresh\nA brand-new requirement.\n:::\n"
    "\n"
    "::: {.need #TC-1 type=test-case status=passed}\n\n## Login test\nSigns a user in.\n:::\n"
)


def snapshot_of(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None, [str(f) for f in result.findings]
    return result.snapshot


def diff_projection(tmp_path: Path) -> graph_projection.GraphProjection:
    for existing in tmp_path.glob("*.qmd"):
        existing.unlink()
    (tmp_path / "a.qmd").write_text(V1_A, encoding="utf-8")
    (tmp_path / "b.qmd").write_text(V1_B, encoding="utf-8")
    payload = baseline.build_baseline(snapshot_of(tmp_path), load_config(tmp_path))
    (tmp_path / "b.qmd").unlink()
    (tmp_path / "a.qmd").write_text(V2_A, encoding="utf-8")
    (tmp_path / "c.qmd").write_text(V1_B, encoding="utf-8")
    return graph_projection.build_diff_overlay(
        payload,
        snapshot_of(tmp_path),
        load_config(tmp_path),
        node_ids=("REQ-1", "REQ-3", "TC-1", "TC-2"),
        view_id="need-graph-diff",
    )


CHAIN_V1 = (
    "::: {.need #STK-1 type=need status=approved priority=high}\n"
    "\n## Stake\nStakeholder concern.\n:::\n"
    "\n"
    "::: {.need #SYS-1 type=system-requirement status=approved priority=high "
    'derives-from="STK-1" verified-by="TC-9"}\n'
    "\n## System\nThe system shall do it.\n:::\n"
    "\n"
    "::: {.need #TC-9 type=test-case status=passed}\n\n## Verify\nChecks the system.\n:::\n"
)


def impact_projection(tmp_path: Path) -> graph_projection.GraphProjection:
    (tmp_path / "chain.qmd").write_text(CHAIN_V1, encoding="utf-8")
    payload = baseline.build_baseline(snapshot_of(tmp_path), load_config(tmp_path))
    (tmp_path / "chain.qmd").write_text(
        CHAIN_V1.replace("Stakeholder concern.", "Stakeholder concern, revised."), encoding="utf-8"
    )
    return graph_projection.build_impact_overlay(
        payload,
        snapshot_of(tmp_path),
        load_config(tmp_path),
        node_ids=("STK-1",),
        view_id="need-graph-impact",
    )


def parse_diagram(source: str):
    nodes: dict[str, str] = {}
    edges: list[tuple[str, str]] = []
    for line in source.splitlines():
        node_match = NODE_LINE.match(line)
        if node_match:
            ref, label = node_match.groups()
            identifier = bytes.fromhex(ref[len("need_"):]).decode("utf-8")
            assert identifier not in nodes
            nodes[identifier] = label
            continue
        edge_match = EDGE_LINE.match(line)
        if edge_match:
            source_ref, _, target_ref = edge_match.groups()
            edges.append(
                (
                    bytes.fromhex(source_ref[len("need_"):]).decode("utf-8"),
                    bytes.fromhex(target_ref[len("need_"):]).decode("utf-8"),
                )
            )
            continue
        assert line == "flowchart LR" or line == "", f"unparsable mermaid line: {line!r}"
    return nodes, edges


# --- mermaid source -----------------------------------------------------------


def test_mermaid_source_matches_the_catalog_golden(tmp_path: Path) -> None:
    assert graph_render.mermaid_source(catalog_projection(tmp_path)) == GOLDEN_CATALOG.read_text(encoding="utf-8")


def test_mermaid_source_matches_the_diff_golden(tmp_path: Path) -> None:
    assert graph_render.mermaid_source(diff_projection(tmp_path)) == GOLDEN_DIFF.read_text(encoding="utf-8")


def test_two_renders_of_independent_analyses_are_byte_identical(tmp_path: Path) -> None:
    first = graph_render.mermaid_source(catalog_projection(tmp_path))
    (tmp_path / "adversarial.qmd").unlink()
    second = graph_render.mermaid_source(catalog_projection(tmp_path))
    assert first == second


def test_diagram_table_and_projection_agree(tmp_path: Path) -> None:
    """The static-equivalence gate in miniature: same nodes, same edges."""
    for projection in (
        catalog_projection(tmp_path),
        diff_projection(tmp_path),
        impact_projection(tmp_path),
    ):
        nodes, edges = parse_diagram(graph_render.mermaid_source(projection))
        rows = graph_render.edge_table_rows(projection)

        assert set(nodes) == {node.id for node in projection.nodes}
        assert sorted(edges) == sorted((edge.source, edge.target) for edge in projection.edges)
        assert sorted((row.source, row.target) for row in rows) == sorted(edges)
        assert len(rows) == len(projection.edges)


def test_change_markers_and_labels_are_visible_as_text(tmp_path: Path) -> None:
    source = graph_render.mermaid_source(diff_projection(tmp_path))
    nodes, _ = parse_diagram(source)

    assert "Authenticate" in nodes["REQ-1"] and "— modified" in nodes["REQ-1"]
    assert "— added" in nodes["REQ-3"]
    assert "— relocated" in nodes["TC-2"]
    assert "— removed" in nodes["REQ-2"]  # the ghost
    assert "— added" not in nodes["TC-1"]
    assert '"Verified by (added)"' in source
    assert '"Verified by (removed)"' in source

    rows = graph_render.edge_table_rows(diff_projection(tmp_path))
    by_change = {row.change for row in rows}
    assert by_change == {"added", "removed", "unchanged"}


def test_hostile_labels_are_escaped(tmp_path: Path) -> None:
    hostile = graph_projection.GraphProjection(
        view_id="g",
        mode="catalog",
        limits={"nodes": 10, "edges": 10},
        nodes=(
            graph_projection.PublicNode(
                id="EVIL-1",
                title='Evil "quote" \\ slash --> arrow | pipe',
                type="functional-requirement",
                status="approved",
                priority=None,
                tags=(),
                href="#EVIL-1",
            ),
            graph_projection.PublicNode(
                id="EVIL-2", title="Calm", type="test-case", status="passed",
                priority=None, tags=(), href="#EVIL-2",
            ),
        ),
        edges=(
            graph_projection.PublicEdge(
                source="EVIL-1", target="EVIL-2", relation="verifies", label='Bad "label" | pipe'
            ),
        ),
    )
    source = graph_render.mermaid_source(hostile)
    nodes, edges = parse_diagram(source)

    # The hostile node still parses as exactly one node line with no embedded
    # quote, arrow, or pipe syntax.
    assert "Evil 'quote' / slash → arrow / pipe" in nodes["EVIL-1"]
    assert "Bad 'label' / pipe" in source
    assert "| pipe" not in source and "slash -->" not in source
    assert edges == [("EVIL-1", "EVIL-2")]


def test_impact_path_members_are_marked(tmp_path: Path) -> None:
    source = graph_render.mermaid_source(impact_projection(tmp_path))
    assert '"Derives from (path)"' in source
    assert '"Verified by (path)"' in source


# --- edge table ---------------------------------------------------------------


def test_edge_table_carries_impact_explanations(tmp_path: Path) -> None:
    rows = graph_render.edge_table_rows(impact_projection(tmp_path))
    by_pair = {(row.source, row.target): row for row in rows}

    derives = by_pair[("SYS-1", "STK-1")]
    assert "STK-1 → SYS-1 (direct, 1 hop)" in derives.impact
    assert "STK-1 → SYS-1 → TC-9 (transitive, 2 hops)" in derives.impact

    verifies = by_pair[("SYS-1", "TC-9")]
    assert "STK-1 → SYS-1 → TC-9 (transitive, 2 hops)" in verifies.impact

    # Catalog rows carry no impact text.
    calm = graph_render.edge_table_rows(catalog_projection(tmp_path))
    assert all(row.impact == "" for row in calm)


def test_edge_table_relation_column_uses_labels_not_codes(tmp_path: Path) -> None:
    rows = graph_render.edge_table_rows(catalog_projection(tmp_path))
    assert [(row.source, row.relation, row.target) for row in rows] == [
        ("ADV-2", "Verifies", "ADV-1")
    ]


def test_node_table_carries_type_status_priority_and_tags(tmp_path: Path) -> None:
    """The static accessible fallback is edge-only today — a node's own
    type/status/priority/tags are otherwise only visible on the
    (deliberately aria-hidden) interactive canvas. Closes that gap."""
    rows = graph_render.node_table_rows(catalog_projection(tmp_path))
    by_id = {row.id: row for row in rows}

    assert set(by_id) == {"ADV-1", "ADV-2"}
    adv1 = by_id["ADV-1"]
    assert adv1.title
    assert adv1.type
    assert adv1.status
    # tags stays the node's own per-tag sequence — the table cell wraps each
    # one as its own badge span, it is never comma-joined.
    assert adv1.tags == ("public-tag",)


def test_node_table_change_column_matches_the_projection_catalog_is_blank(
    tmp_path: Path,
) -> None:
    diff_rows = graph_render.node_table_rows(diff_projection(tmp_path))
    by_id = {row.id: row for row in diff_rows}
    assert by_id["REQ-1"].change == "modified"
    assert by_id["REQ-3"].change == "added"

    catalog_rows = graph_render.node_table_rows(catalog_projection(tmp_path))
    assert all(row.change == "" for row in catalog_rows)


# --- summary ------------------------------------------------------------------


def test_summary_counts_catalog(tmp_path: Path) -> None:
    entries = dict(graph_render.summary_entries(catalog_projection(tmp_path)))
    assert entries["mode"] == "catalog"
    assert entries["nodes"] == "2 / 100"
    assert entries["edges"] == "1 / 300"


def test_summary_counts_diff_changes(tmp_path: Path) -> None:
    entries = dict(graph_render.summary_entries(diff_projection(tmp_path)))
    assert entries["mode"] == "diff"
    assert entries["nodes added"] == "1"
    assert entries["nodes removed"] == "1"
    assert entries["nodes modified"] == "1"
    assert entries["nodes relocated"] == "1"


def test_summary_counts_impact(tmp_path: Path) -> None:
    entries = dict(graph_render.summary_entries(impact_projection(tmp_path)))
    assert entries["mode"] == "impact"
    assert entries["impacted"] == "2"
    assert entries["direct"] == "1"
    assert entries["transitive"] == "1"
