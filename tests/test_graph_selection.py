from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs import graph_projection
from quarto_needs.analysis import analyze_project
from quarto_needs.config import GraphSettings, load_config
from quarto_needs.queries import QueryError, query_ids

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "graph-public-v1.schema.json"


def write_project(root: Path, body: str, config: str = "") -> None:
    if config:
        (root / ".quarto-needs.toml").write_text(config, encoding="utf-8")
    (root / "graph.qmd").write_text(body, encoding="utf-8")


def snapshot_of(root: Path):
    result = analyze_project(root)
    assert result.snapshot is not None, [str(f) for f in result.findings]
    return result.snapshot


SPARSE = (
    "::: {.need #REQ-1 type=functional-requirement status=approved priority=high tags=\"auth\"}\n"
    "verified-by: TC-1\n"
    "\n## Authenticate\nBody.\n:::\n"
    "\n"
    "::: {.need #TC-1 type=test-case status=passed}\n\n## Login\nSigns in.\n:::\n"
)

FANOUT = (
    "::: {.need #HUB type=functional-requirement status=approved priority=high tags=\"hub\"}\n"
    "verifies:\n"
    "  - TC-1\n"
    "  - TC-2\n"
    "  - TC-3\n"
    "\n## Hub\nBody.\n:::\n"
    "\n"
    "::: {.need #TC-1 type=test-case status=passed}\nreferences: DOC-1\n\n## T1\n:::\n"
    "\n"
    "::: {.need #TC-2 type=test-case status=passed}\n\n## T2\n:::\n"
    "\n"
    "::: {.need #TC-3 type=test-case status=passed}\n\n## T3\n:::\n"
    "\n"
    "::: {.need #DOC-1 type=risk status=open priority=medium tags=\"hub\"}\n\n## D1\n:::\n"
)

CYCLE = (
    "::: {.need #C-A type=need status=draft}\nreferences: C-B\n\n## A\n:::\n"
    "\n::: {.need #C-B type=need status=draft}\nreferences: C-C\n\n## B\n:::\n"
    "\n::: {.need #C-C type=need status=draft}\nreferences: C-A\n\n## C\n:::\n"
)

DISCONNECTED = (
    "::: {.need #REQ-1 type=functional-requirement status=approved}\n"
    "verified-by: TC-1\n\n## R1\n:::\n"
    "\n::: {.need #TC-1 type=test-case status=passed}\n\n## T1\n:::\n"
    "\n::: {.need #REQ-2 type=functional-requirement status=approved}\n"
    "verified-by: TC-2\n\n## R2\n:::\n"
    "\n::: {.need #TC-2 type=test-case status=passed}\n\n## T2\n:::\n"
)


def test_graph_defaults_apply_without_a_section(tmp_path: Path) -> None:
    write_project(tmp_path, SPARSE)
    assert load_config(tmp_path).graph == GraphSettings()


def test_graph_section_parses_every_key(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        SPARSE,
        config=(
            "[graph]\nmax-nodes = 25\nmax-edges = 50\ndepth = 2\n"
            'mode = "impact"\nlayout = "radial"\nseed = 9\n'
            'relations = ["verified-by", "verifies"]\n'
        ),
    )
    graph = load_config(tmp_path).graph
    assert graph.max_nodes == 25
    assert graph.max_edges == 50
    assert graph.depth == 2
    assert graph.mode == "impact"
    assert graph.layout == "radial"
    assert graph.seed == 9
    assert graph.relations == ("verified-by", "verifies")


def test_graph_rejects_unknown_keys(tmp_path: Path) -> None:
    write_project(tmp_path, SPARSE, config="[graph]\nnodes = 5\n")
    with pytest.raises(Exception, match="unknown keys"):
        load_config(tmp_path)


@pytest.mark.parametrize(
    "config",
    [
        "[graph]\nmax-nodes = 0\n",
        "[graph]\nmax-edges = -1\n",
        "[graph]\ndepth = 0\n",
        "[graph]\ndepth = 11\n",
        '[graph]\nmode = "catalogue"\n',
        '[graph]\nlayout = ""\n',
        "[graph]\nseed = -1\n",
        "[graph]\nrelations = []\n",
        '[graph]\nrelations = ["no-such-relation"]\n',
        '[graph]\nrelations = "verified-by"\n',
    ],
)
def test_graph_rejects_invalid_values(tmp_path: Path, config: str) -> None:
    write_project(tmp_path, SPARSE, config=config)
    with pytest.raises(Exception):
        load_config(tmp_path)


def test_graph_settings_do_not_change_the_configuration_fingerprint(tmp_path: Path) -> None:
    write_project(tmp_path, SPARSE)
    plain = load_config(tmp_path).canonical_document()
    write_project(tmp_path, SPARSE, config="[graph]\nmax-nodes = 5\n")
    limited = load_config(tmp_path).canonical_document()

    assert "graph" not in limited
    assert plain == limited


def test_query_ids_evaluates_a_named_query(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        FANOUT,
        config=(
            '[queries.hub]\nall = [{ field = "id", op = "eq", value = "HUB" }]\n'
            'sort = ["id:asc"]\n'
        ),
    )
    assert query_ids(load_config(tmp_path), snapshot_of(tmp_path), "hub") == ("HUB",)


def test_query_ids_serves_the_default_query_without_configuration(tmp_path: Path) -> None:
    write_project(tmp_path, SPARSE)
    assert query_ids(load_config(tmp_path), snapshot_of(tmp_path), "approved-requirements") == ("REQ-1",)


def test_query_ids_rejects_an_unknown_name(tmp_path: Path) -> None:
    write_project(tmp_path, SPARSE)
    with pytest.raises(QueryError, match="no-such-query"):
        query_ids(load_config(tmp_path), snapshot_of(tmp_path), "no-such-query")


def test_sparse_selection_reaches_one_hop_neighbors(tmp_path: Path) -> None:
    write_project(tmp_path, SPARSE)
    selection = graph_projection.select_graph(
        snapshot_of(tmp_path), seeds=("REQ-1",), depth=1
    )
    assert selection.node_ids == ("REQ-1", "TC-1")
    assert selection.edges == (("REQ-1", "TC-1", "verified-by"),)


def test_depth_bounds_the_expansion(tmp_path: Path) -> None:
    write_project(tmp_path, FANOUT)
    snapshot = snapshot_of(tmp_path)
    one = graph_projection.select_graph(snapshot, seeds=("HUB",), depth=1)
    two = graph_projection.select_graph(snapshot, seeds=("HUB",), depth=2)

    assert one.node_ids == ("HUB", "TC-1", "TC-2", "TC-3")
    assert "DOC-1" not in one.node_ids
    assert set(two.node_ids) == {"HUB", "TC-1", "TC-2", "TC-3", "DOC-1"}
    assert ("TC-1", "DOC-1", "references") in two.edges


def test_relation_allowlist_bounds_expansion_and_edges(tmp_path: Path) -> None:
    write_project(tmp_path, FANOUT)
    selection = graph_projection.select_graph(
        snapshot_of(tmp_path), seeds=("HUB",), relations=("references",), depth=2
    )
    assert selection.node_ids == ("HUB",)
    assert selection.edges == ()
    from_doc = graph_projection.select_graph(
        snapshot_of(tmp_path), seeds=("DOC-1",), relations=("references",), depth=2
    )
    assert from_doc.node_ids == ("DOC-1", "TC-1")
    assert from_doc.edges == (("TC-1", "DOC-1", "references"),)


def test_cyclic_selection_terminates(tmp_path: Path) -> None:
    write_project(tmp_path, CYCLE)
    selection = graph_projection.select_graph(
        snapshot_of(tmp_path), seeds=("C-A",), depth=5
    )
    assert selection.node_ids == ("C-A", "C-B", "C-C")


def test_disconnected_components_stay_disconnected(tmp_path: Path) -> None:
    write_project(tmp_path, DISCONNECTED)
    selection = graph_projection.select_graph(
        snapshot_of(tmp_path), seeds=("REQ-1",), depth=3
    )
    assert set(selection.node_ids) == {"REQ-1", "TC-1"}
    assert selection.edges == (("REQ-1", "TC-1", "verified-by"),)


def test_high_fanout_selects_direct_neighbors_only_at_depth_one(tmp_path: Path) -> None:
    write_project(tmp_path, FANOUT)
    selection = graph_projection.select_graph(
        snapshot_of(tmp_path), seeds=("HUB",), depth=1
    )
    assert selection.node_ids == ("HUB", "TC-1", "TC-2", "TC-3")
    assert len(selection.edges) == 3


def test_empty_selection_is_valid_not_an_error(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        SPARSE,
        config='[queries.none]\nall = [{ field = "status", op = "eq", value = "blocked" }]\n',
    )
    snapshot = snapshot_of(tmp_path)
    assert query_ids(load_config(tmp_path), snapshot, "none") == ()
    selection = graph_projection.select_graph(snapshot, seeds=())
    assert selection.node_ids == ()
    assert selection.edges == ()


def test_seed_order_directs_the_selection_but_not_its_content(tmp_path: Path) -> None:
    write_project(tmp_path, DISCONNECTED)
    snapshot = snapshot_of(tmp_path)
    forward = graph_projection.select_graph(snapshot, seeds=("REQ-1", "REQ-2"))
    reverse = graph_projection.select_graph(snapshot, seeds=("REQ-2", "REQ-1"))

    assert forward.node_ids != reverse.node_ids
    assert set(forward.node_ids) == set(reverse.node_ids)
    assert forward.edges == reverse.edges


def test_missing_seed_ids_are_ignored(tmp_path: Path) -> None:
    write_project(tmp_path, SPARSE)
    selection = graph_projection.select_graph(
        snapshot_of(tmp_path), seeds=("REQ-1", "GHOST"), depth=1
    )
    assert selection.node_ids == ("REQ-1", "TC-1")


def test_node_limit_exceeded_raises_a_structured_diagnostic(tmp_path: Path) -> None:
    write_project(tmp_path, FANOUT)
    with pytest.raises(graph_projection.GraphLimitExceeded) as raised:
        graph_projection.select_graph(
            snapshot_of(tmp_path),
            seeds=("HUB",),
            depth=2,
            limits={"nodes": 3, "edges": 300},
        )
    error = raised.value
    assert error.actual["nodes"] == 5
    assert error.limits == {"nodes": 3, "edges": 300}
    assert error.suggested_facets
    assert "5" in str(error) and "3" in str(error)


def test_edge_limit_exceeded_raises(tmp_path: Path) -> None:
    write_project(tmp_path, FANOUT)
    with pytest.raises(graph_projection.GraphLimitExceeded) as raised:
        graph_projection.select_graph(
            snapshot_of(tmp_path),
            seeds=("HUB",),
            depth=2,
            limits={"nodes": 100, "edges": 3},
        )
    assert raised.value.actual == {"nodes": 5, "edges": 4}


def test_selection_at_the_boundary_passes(tmp_path: Path) -> None:
    write_project(tmp_path, FANOUT)
    selection = graph_projection.select_graph(
        snapshot_of(tmp_path),
        seeds=("HUB",),
        depth=2,
        limits={"nodes": 5, "edges": 4},
    )
    assert len(selection.node_ids) == 5
    assert len(selection.edges) == 4


def test_suggested_facets_name_real_values_with_counts(tmp_path: Path) -> None:
    write_project(tmp_path, FANOUT)
    with pytest.raises(graph_projection.GraphLimitExceeded) as raised:
        graph_projection.select_graph(
            snapshot_of(tmp_path), seeds=("HUB",), depth=2, limits={"nodes": 2, "edges": 300}
        )
    facets = raised.value.suggested_facets
    as_dict = {(field, value): count for field, value, count in facets}
    assert as_dict[("type", "functional-requirement")] == 1
    assert as_dict[("type", "test-case")] == 3
    assert as_dict[("status", "passed")] == 3
    assert as_dict[("priority", "high")] == 1
    assert as_dict[("tags", "hub")] == 2
    fields = [field for field, _, _ in facets]
    assert fields == sorted(fields, key=["type", "status", "priority", "tags"].index)


def test_default_allowlist_is_the_catalogs_public_relations() -> None:
    assert graph_projection.PUBLIC_RELATIONS == (
        "addressed-by",
        "addresses",
        "applies-to",
        "confirmed-by",
        "confirms",
        "conflicts-with",
        "constrains",
        "decomposes",
        "depends-on",
        "derives-from",
        "evidenced-by",
        "evidences",
        "implemented-by",
        "implements",
        "justified-by",
        "mitigates",
        "part-of",
        "references",
        "refines",
        "superseded-by",
        "supersedes",
        "validated-by",
        "verified-by",
        "verifies",
    )


def test_build_projection_consumes_a_selection_and_its_allowlist(tmp_path: Path) -> None:
    write_project(tmp_path, FANOUT)
    snapshot = snapshot_of(tmp_path)
    selection = graph_projection.select_graph(snapshot, seeds=("HUB",), depth=2)

    projection = graph_projection.build_projection(
        snapshot,
        node_ids=selection.node_ids,
        view_id="need-graph-1",
        relations=("verifies",),
    )
    payload = json.loads(graph_projection.render_projection(projection))

    assert {node["id"] for node in payload["nodes"]} == set(selection.node_ids)
    assert {edge["relation"] for edge in payload["edges"]} == {"verifies"}
    assert len(payload["edges"]) == 3


def test_build_projection_serializes_layout_and_seed(tmp_path: Path) -> None:
    write_project(tmp_path, SPARSE)
    projection = graph_projection.build_projection(
        snapshot_of(tmp_path),
        node_ids=("REQ-1", "TC-1"),
        view_id="need-graph-2",
        layout="radial",
        seed=7,
    )
    payload = json.loads(graph_projection.render_projection(projection))
    assert payload["view"]["layout"] == "radial"
    assert payload["view"]["seed"] == 7

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
