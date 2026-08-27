from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs import graph_projection
from quarto_needs.analysis import analyze_project

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "graph" / "adversarial.qmd"
SCHEMA = ROOT / "schemas" / "graph-public-v1.schema.json"

CANARIES = (
    "LEAKCANARYATTR7f3a",
    "LEAKCANARYBODY91cd",
    "LEAKCANARYRATIONALE4e77",
    "LEAKCANARYBODY2b80",
)


def projection_of(tmp_path: Path):
    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = analyze_project(tmp_path)
    assert result.snapshot is not None
    return graph_projection.build_projection(
        result.snapshot,
        node_ids=("ADV-1", "ADV-2"),
        view_id="need-graph-1",
    )


def test_no_denied_value_reaches_the_projection(tmp_path: Path) -> None:
    """Search the serialized output for denied values, not for field names.

    Enumerating fields only catches leaks through paths someone anticipated. A
    canary search catches a leak through any path at all, including a future
    field added without thinking about publication policy.
    """
    serialized = graph_projection.render_projection(projection_of(tmp_path))

    for canary in CANARIES:
        assert canary not in serialized, f"{canary} reached the public projection"


def test_projection_validates_against_its_schema(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(graph_projection.render_projection(projection_of(tmp_path))))


def test_only_allowlisted_fields_are_emitted(tmp_path: Path) -> None:
    payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))

    for node in payload["nodes"]:
        assert set(node) <= set(graph_projection.PUBLIC_NODE_FIELDS), f"unexpected keys: {set(node)}"
    for edge in payload["edges"]:
        assert set(edge) <= set(graph_projection.PUBLIC_EDGE_FIELDS)


def test_publishable_content_is_present(tmp_path: Path) -> None:
    """Deny-by-default must not degrade into deny-everything."""
    payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))

    node = next(item for item in payload["nodes"] if item["id"] == "ADV-1")
    assert node["title"] == "Publishable title"
    assert node["type"] == "functional-requirement"
    assert node["status"] == "approved"
    assert node["priority"] == "high"
    assert node["tags"] == ["public-tag"]


def test_render_is_byte_stable(tmp_path: Path) -> None:
    assert graph_projection.render_projection(projection_of(tmp_path)) == \
        graph_projection.render_projection(projection_of(tmp_path))


def test_node_order_is_deterministic_and_independent_of_request_order(tmp_path: Path) -> None:
    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = analyze_project(tmp_path)
    assert result.snapshot is not None

    forward = graph_projection.build_projection(result.snapshot, node_ids=("ADV-1", "ADV-2"), view_id="v")
    reverse = graph_projection.build_projection(result.snapshot, node_ids=("ADV-2", "ADV-1"), view_id="v")

    assert graph_projection.render_projection(forward) == graph_projection.render_projection(reverse)
