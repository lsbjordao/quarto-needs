from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs import graph_projection
from quarto_needs.analysis import analyze_project
from quarto_needs.snapshot import AnalysisSnapshot, ObjectRecord

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "graph" / "adversarial.qmd"
SCHEMA = ROOT / "schemas" / "graph-public-v1.schema.json"

CANARIES = (
    "LEAKCANARYATTR7f3a",
    "LEAKCANARYBODY91cd",
    "LEAKCANARYRATIONALE4e77",
    "LEAKCANARYBODY2b80",
)

FIXTURE_FILENAME = "adversarial.qmd"


def _snapshot(*objects: ObjectRecord) -> AnalysisSnapshot:
    """Construct a minimal AnalysisSnapshot for unit testing."""
    return AnalysisSnapshot(
        objects=objects,
        relations=(),
        findings=(),
        metrics={},
        objects_by_id={obj.id: obj for obj in objects},
        outgoing={},
        incoming={},
        generator_name="test",
        generator_version="1.0",
        relation_catalog_version="1.0",
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
    serialized = graph_projection.render_projection(projection_of(tmp_path))
    for canary in CANARIES:
        assert canary not in serialized, f"{canary} reached the public projection"


def test_no_source_location_reaches_the_projection(tmp_path: Path) -> None:
    serialized = graph_projection.render_projection(projection_of(tmp_path))
    assert FIXTURE_FILENAME not in serialized, "a source file name reached the public projection"


def test_projection_validates_against_its_schema(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(graph_projection.render_projection(projection_of(tmp_path))))


def test_only_allowlisted_fields_are_emitted(tmp_path: Path) -> None:
    payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))
    assert payload["nodes"], "fixture produced no nodes; the allowlist check below would be vacuous"
    assert payload["edges"], "fixture produced no edges; the allowlist check below would be vacuous"
    assert set(payload) <= {"schemaVersion", "view", "nodes", "edges", "impact"}, set(payload)
    assert set(payload["view"]) <= {"id", "mode", "limits", "layout", "seed"}, set(payload["view"])
    assert set(payload["view"]["limits"]) <= {"nodes", "edges"}, set(payload["view"]["limits"])
    for node in payload["nodes"]:
        assert set(node) <= set(graph_projection.PUBLIC_NODE_FIELDS), f"unexpected keys: {set(node)}"
    for edge in payload["edges"]:
        assert set(edge) <= set(graph_projection.PUBLIC_EDGE_FIELDS), f"unexpected keys: {set(edge)}"


def test_publishable_content_is_present(tmp_path: Path) -> None:
    payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))

    node = next(item for item in payload["nodes"] if item["id"] == "ADV-1")
    assert node["title"] == "Publishable title"
    assert node["type"] == "functional-requirement"
    assert node["status"] == "approved"
    assert node["priority"] == "high"
    assert node["tags"] == ["public-tag"]
    assert node["href"] == "adversarial.html#ADV-1"

    edge = next(
        item for item in payload["edges"] if item["source"] == "ADV-2" and item["target"] == "ADV-1"
    )
    assert edge["relation"] == "verifies"
    assert edge["label"] == "Verifies"


def test_render_is_byte_stable(tmp_path: Path) -> None:
    first = graph_projection.render_projection(projection_of(tmp_path))
    second = graph_projection.render_projection(projection_of(tmp_path))
    assert first == second
    assert first.startswith('{\n  "edges"'), "top-level keys are not sorted"
    assert first.count("\n") > 4, "output is not indented"
    assert first.endswith("\n")


def test_render_is_byte_stable_across_processes(tmp_path: Path) -> None:
    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    in_process = graph_projection.render_projection(projection_of(tmp_path))

    script = (
        "from pathlib import Path\n"
        "from quarto_needs import graph_projection\n"
        "from quarto_needs.analysis import analyze_project\n"
        f"result = analyze_project(Path({str(tmp_path)!r}))\n"
        "projection = graph_projection.build_projection(\n"
        "    result.snapshot, node_ids=('ADV-1', 'ADV-2'), view_id='need-graph-1'\n"
        ")\n"
        "import sys\n"
        "sys.stdout.write(graph_projection.render_projection(projection))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout == in_process


def test_node_order_is_deterministic_and_independent_of_request_order(tmp_path: Path) -> None:
    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = analyze_project(tmp_path)
    assert result.snapshot is not None

    forward = graph_projection.build_projection(result.snapshot, node_ids=("ADV-1", "ADV-2"), view_id="v")
    reverse = graph_projection.build_projection(result.snapshot, node_ids=("ADV-2", "ADV-1"), view_id="v")

    assert graph_projection.render_projection(forward) == graph_projection.render_projection(reverse)


def test_limits_are_built_from_known_keys_not_copied_wholesale(tmp_path: Path) -> None:
    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = analyze_project(tmp_path)
    assert result.snapshot is not None

    projection = graph_projection.build_projection(
        result.snapshot,
        node_ids=("ADV-1", "ADV-2"),
        view_id="need-graph-1",
        limits={"nodes": 5, "edges": 9, "secret": "LEAKCANARYLIMITq1w2"},
    )
    payload = json.loads(graph_projection.render_projection(projection))

    assert payload["view"]["limits"] == {"nodes": 5, "edges": 9}
    assert "LEAKCANARYLIMITq1w2" not in graph_projection.render_projection(projection)


def test_impact_entries_are_built_from_named_fields(tmp_path: Path) -> None:
    entry = graph_projection.PublicImpactEntry(
        id="ADV-2",
        origin="ADV-1",
        distance=1,
        path=("ADV-1", "ADV-2"),
        classification="direct",
    )
    projection = graph_projection.GraphProjection(
        view_id="v",
        mode="impact",
        limits={"nodes": 1, "edges": 1},
        nodes=(),
        edges=(),
        impact=(entry,),
    )
    payload = json.loads(graph_projection.render_projection(projection))

    assert payload["impact"] == [
        {
            "id": "ADV-2",
            "origin": "ADV-1",
            "distance": 1,
            "path": ["ADV-1", "ADV-2"],
            "classification": "direct",
        }
    ]


def test_impact_cannot_smuggle_undeclared_keys_via_a_raw_mapping() -> None:
    projection = graph_projection.GraphProjection(
        view_id="v",
        mode="impact",
        limits={"nodes": 1, "edges": 1},
        nodes=(),
        edges=(),
        impact=(
            {
                "id": "ADV-2",
                "origin": "ADV-1",
                "distance": 1,
                "path": ["ADV-1", "ADV-2"],
                "secret": "LEAKCANARYIMPACTz9y8",
            },
        ),
    )
    with pytest.raises(AttributeError):
        graph_projection.render_projection(projection)


def test_public_node_surfaces_a_containers_technology_attribute() -> None:
    snapshot = _snapshot(
        ObjectRecord(
            id="CONTAINER-1",
            type="container",
            title="Python package",
            status="implemented",
            body="",
            rationale="",
            attributes={"technology": "Python 3.12"},
            locations=(),
        ),
        ObjectRecord(
            id="SYS-1",
            type="system",
            title="Quarto-Needs",
            status="implemented",
            body="",
            rationale="",
            attributes={},
            locations=(),
        ),
    )
    projection = graph_projection.build_projection(
        snapshot, node_ids=("CONTAINER-1", "SYS-1"), view_id="test-view"
    )
    by_id = {node.id: node for node in projection.nodes}
    assert by_id["CONTAINER-1"].technology == "Python 3.12"
    assert by_id["SYS-1"].technology is None
    assert by_id["CONTAINER-1"].to_dict()["technology"] == "Python 3.12"
    assert "technology" not in by_id["SYS-1"].to_dict()


def test_ghost_node_surfaces_technology_from_baseline() -> None:
    """Test that _ghost_node correctly extracts technology from baseline data."""
    ghost_entry = {
        "id": "CONTAINER-1",
        "title": "Python package",
        "type": "container",
        "status": "implemented",
        "priority": "high",
        "tags": ["backend"],
        "attributes": {"technology": "Python 3.12"},
    }
    ghost = graph_projection._ghost_node(ghost_entry)
    assert ghost.technology == "Python 3.12"
    assert ghost.to_dict()["technology"] == "Python 3.12"

    # Verify technology is None when not in baseline
    ghost_entry_no_tech = dict(ghost_entry)
    ghost_entry_no_tech["attributes"] = {}
    ghost_no_tech = graph_projection._ghost_node(ghost_entry_no_tech)
    assert ghost_no_tech.technology is None
    assert "technology" not in ghost_no_tech.to_dict()
