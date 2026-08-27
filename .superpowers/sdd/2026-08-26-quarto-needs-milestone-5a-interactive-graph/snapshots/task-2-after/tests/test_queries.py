from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_objects, analyze_project
from quarto_needs.config import ConfigurationError, load_config
from quarto_needs.diagnostics import Finding
from quarto_needs.model import EngineeringObject, Relation
from quarto_needs.queries import (
    DEFAULT_QUERY_NAME,
    compile_query,
    evaluate,
    materialize_queries,
)

ROOT = Path(__file__).resolve().parents[1]


def canonical_snapshot():
    root = ROOT / "tests/fixtures/canonical"
    result = analyze_project(root, files=[root / "a-tests.qmd", root / "z-requirements.qmd"])
    assert result.snapshot is not None
    return result.snapshot


def snapshot_with(*objects: EngineeringObject):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None, [item.to_dict() for item in result.findings]
    return result.snapshot


def req(
    id: str,
    *,
    type: str = "functional-requirement",
    status: str = "draft",
    attributes: dict | None = None,
    relations: list[Relation] | None = None,
) -> EngineeringObject:
    return EngineeringObject(id, type, id.title(), status=status, attributes=attributes or {}, relations=relations or [])


# --- compilation safety ----------------------------------------------------


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="secret"):
        compile_query("q", {"all": [{"field": "secret", "op": "eq", "value": 1}]})


def test_unknown_operator_direction_and_relation_are_rejected() -> None:
    with pytest.raises(ConfigurationError):
        compile_query("q", {"all": [{"field": "status", "op": "regex", "value": ".*"}]})
    with pytest.raises(ConfigurationError):
        compile_query("q", {"all": [{"relation": "verified-by", "direction": "sideways", "op": "exists"}]})
    with pytest.raises(ConfigurationError):
        compile_query("q", {"all": [{"relation": "not-a-relation", "direction": "out", "op": "exists"}]})


def test_depth_limit_is_enforced() -> None:
    clause: dict = {"field": "status", "op": "eq", "value": "approved"}
    for _ in range(10):
        clause = {"not": clause}
    with pytest.raises(ConfigurationError, match="depth"):
        compile_query("q", {"all": [clause]})


def test_clause_count_limit_is_enforced() -> None:
    clauses = [{"field": "status", "op": "eq", "value": "approved"}] * 101
    with pytest.raises(ConfigurationError, match="100"):
        compile_query("q", {"any": clauses})


def test_in_requires_values_and_eq_requires_value() -> None:
    with pytest.raises(ConfigurationError):
        compile_query("q", {"all": [{"field": "status", "op": "in"}]})
    with pytest.raises(ConfigurationError):
        compile_query("q", {"all": [{"field": "status", "op": "eq"}]})
    with pytest.raises(ConfigurationError):
        compile_query("q", {"all": [{"field": "status", "op": "exists", "value": "x"}]})


def test_authored_relation_alias_normalizes_to_v1_name() -> None:
    query = compile_query("q", {"all": [{"relation": "verified-by", "direction": "out", "op": "exists"}]})
    assert query.root.children[0].relation == "verified-by"
    alias = compile_query("q", {"all": [{"relation": "derived-from", "direction": "out", "op": "exists"}]})
    assert alias.root.children[0].relation == "derives-from"


# --- field semantics --------------------------------------------------------


def test_string_comparison_casefolds_but_types_never_coerce() -> None:
    snapshot = snapshot_with(req("A", attributes={"rank": 3}))
    eq = compile_query("q", {"all": [{"field": "attributes.rank", "op": "eq", "value": "3"}]})
    assert tuple(item.id for item in evaluate(eq, snapshot)) == ()
    numeric = compile_query("q", {"all": [{"field": "attributes.rank", "op": "eq", "value": 3}]})
    assert tuple(item.id for item in evaluate(numeric, snapshot)) == ("A",)
    status = compile_query("q", {"all": [{"field": "status", "op": "eq", "value": "DRAFT"}]})
    assert tuple(item.id for item in evaluate(status, snapshot)) == ("A",)


def test_missing_null_and_empty_are_distinct() -> None:
    snapshot = snapshot_with(
        req("ABSENT"),
        req("NULL", attributes={"owner": None}),
        req("EMPTY", attributes={"owner": ""}),
        req("SET", attributes={"owner": "alice"}),
    )
    exists = compile_query("q", {"all": [{"field": "attributes.owner", "op": "exists"}]})
    assert tuple(item.id for item in evaluate(exists, snapshot)) == ("EMPTY", "NULL", "SET")
    missing = compile_query("q", {"all": [{"field": "attributes.owner", "op": "missing"}]})
    assert tuple(item.id for item in evaluate(missing, snapshot)) == ("ABSENT",)
    null_eq = compile_query("q", {"all": [{"field": "attributes.owner", "op": "eq", "value": None}]})
    assert tuple(item.id for item in evaluate(null_eq, snapshot)) == ("NULL",)
    empty_eq = compile_query("q", {"all": [{"field": "attributes.owner", "op": "eq", "value": ""}]})
    assert tuple(item.id for item in evaluate(empty_eq, snapshot)) == ("EMPTY",)


def test_contains_matches_collections_and_substrings() -> None:
    snapshot = snapshot_with(
        req("TAGGED", attributes={"tags": ["authentication", "security"]}),
        req("TEXTUAL", attributes={"summary": "Protects private data"}),
    )
    tagged = compile_query("q", {"all": [{"field": "attributes.tags", "op": "contains", "value": "SECURITY"}]})
    assert tuple(item.id for item in evaluate(tagged, snapshot)) == ("TAGGED",)
    textual = compile_query("q", {"all": [{"field": "attributes.summary", "op": "contains", "value": "private data"}]})
    assert tuple(item.id for item in evaluate(textual, snapshot)) == ("TEXTUAL",)


def test_tags_field_matches_declared_tags_casefolded() -> None:
    snapshot = snapshot_with(req("A", attributes={"tags": "security;login"}), req("B"))
    query = compile_query("q", {"all": [{"field": "tags", "op": "contains", "value": "Security"}]})
    assert tuple(item.id for item in evaluate(query, snapshot)) == ("A",)


def test_combinators_combine() -> None:
    snapshot = snapshot_with(
        req("A", status="approved", attributes={"priority": "high"}),
        req("B", status="approved", attributes={"priority": "low"}),
        req("C", status="draft", attributes={"priority": "high"}),
    )
    query = compile_query(
        "q",
        {
            "all": [
                {"field": "status", "op": "eq", "value": "approved"},
                {
                    "any": [
                        {"field": "priority", "op": "eq", "value": "critical"},
                        {"field": "priority", "op": "in", "values": ["high"]},
                    ]
                },
            ]
        },
    )
    assert tuple(item.id for item in evaluate(query, snapshot)) == ("A",)


def test_not_negates() -> None:
    snapshot = snapshot_with(req("A", status="approved"), req("B", status="draft"))
    query = compile_query("q", {"not": {"field": "status", "op": "eq", "value": "approved"}})
    assert tuple(item.id for item in evaluate(query, snapshot)) == ("B",)


# --- relation clauses -------------------------------------------------------


def test_relation_clause_matches_authored_and_semantic_inverse_views() -> None:
    snapshot = snapshot_with(
        req("REQ-DIRECT", status="approved", relations=[Relation("verified-by", "REQ-DIRECT", "TC")]),
        req("REQ-INVERSE", status="approved"),
        req("NONE", status="approved"),
        req("TC", type="test-case", relations=[Relation("verifies", "TC", "REQ-INVERSE")]),
    )
    out_missing = compile_query("q", {"all": [{"relation": "verified-by", "direction": "out", "op": "missing"}]})
    assert tuple(item.id for item in evaluate(out_missing, snapshot)) == ("NONE", "TC")
    out_exists = compile_query("q", {"all": [{"relation": "verified-by", "direction": "out", "op": "exists"}]})
    assert tuple(item.id for item in evaluate(out_exists, snapshot)) == ("REQ-DIRECT", "REQ-INVERSE")
    either = compile_query("q", {"all": [{"relation": "verifies", "direction": "either", "op": "exists"}]})
    # TC authors the edge; REQ-INVERSE receives it; REQ-DIRECT matches through
    # the semantic inverse view of its own verified-by edge.
    assert set(item.id for item in evaluate(either, snapshot)) == {"TC", "REQ-INVERSE", "REQ-DIRECT"}


def test_relation_without_catalog_inverse_has_no_semantic_expansion() -> None:
    with pytest.raises(ConfigurationError):
        compile_query("q", {"all": [{"relation": "referenced-by", "direction": "in", "op": "exists"}]})
    snapshot = snapshot_with(
        req("RISK", type="risk"),
        req("CTRL", type="control", relations=[Relation("mitigates", "CTRL", "RISK")]),
    )
    incoming = compile_query("q", {"all": [{"relation": "mitigates", "direction": "in", "op": "exists"}]})
    # RISK matches through the authored edge; CTRL gets no invented inverse view.
    assert tuple(item.id for item in evaluate(incoming, snapshot)) == ("RISK",)


# --- sorting and materialization --------------------------------------------


def test_sort_uses_priority_rank_then_id_tiebreaker() -> None:
    snapshot = snapshot_with(
        req("B-LOW", status="approved", attributes={"priority": "low"}),
        req("A-HIGH", status="approved", attributes={"priority": "high"}),
        req("C-CRIT", status="approved", attributes={"priority": "critical"}),
        req("D-NONE", status="approved"),
        req("E-HIGH", status="approved", attributes={"priority": "High"}),
    )
    query = compile_query(
        "q",
        {
            "all": [{"field": "status", "op": "eq", "value": "approved"}],
            "sort": ["priority:asc"],
        },
    )
    assert tuple(item.id for item in evaluate(query, snapshot)) == (
        "C-CRIT",
        "A-HIGH",
        "E-HIGH",
        "B-LOW",
        "D-NONE",
    )
    descending = compile_query(
        "q",
        {
            "all": [{"field": "status", "op": "eq", "value": "approved"}],
            "sort": ["id:desc"],
        },
    )
    assert tuple(item.id for item in evaluate(descending, snapshot))[0] == "E-HIGH"


def test_default_named_query_selects_approved_requirements() -> None:
    snapshot = snapshot_with(
        req("REQ-A", status="approved", attributes={"priority": "medium"}),
        req("REQ-B", status="draft"),
        req("TC", type="test-case", status="passed"),
    )
    ids = materialize_queries(type("C", (), {"named_query_sources": {}})(), snapshot)
    assert ids[DEFAULT_QUERY_NAME] == ("REQ-A",)


def test_materialize_queries_compiles_every_configured_query_sorted() -> None:
    snapshot = canonical_snapshot()
    from quarto_needs.config import load_config

    config = load_config(ROOT / "tests/fixtures/query-config")
    ids = materialize_queries(config, snapshot)
    assert list(ids) == sorted(ids)
    assert ids[DEFAULT_QUERY_NAME] == ("A-REQ-001",)
    assert ids["deriving-requirements"] == ("A-REQ-001",)
    assert ids["approved-high-unverified"] == ()


def test_conformance_fixture_vectors_hold() -> None:
    import json

    vectors = json.loads((ROOT / "tests/fixtures/query-conformance.json").read_text(encoding="utf-8"))
    snapshot = canonical_snapshot()
    config = load_config(ROOT / "tests/fixtures/query-config")
    materialized = materialize_queries(config, snapshot)
    for vector in vectors:
        if "query" in vector:
            query = compile_query(vector["name"], vector["query"])
            produced = tuple(item.id for item in evaluate(query, snapshot))
        else:
            produced = materialized[vector["name"]]
        assert produced == tuple(vector["expected"]), vector["name"]
