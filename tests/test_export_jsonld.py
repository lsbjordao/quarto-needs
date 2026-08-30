from __future__ import annotations

import json
from pathlib import Path

from pyld import jsonld

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import jsonld_export


def _write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #SYS-001 type=system-requirement status=approved verified-by=TC-001 priority=high}\n"
        "## Authenticate users\n"
        "The system shall authenticate users.\n"
        ":::\n\n"
        "::: {.need #TC-001 type=test-case status=passed}\n"
        "## Authentication test\n"
        "Verify login.\n"
        ":::\n",
        encoding="utf-8",
    )


def _snapshot(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None
    return result.snapshot


def _expanded_nodes(document: object) -> list[dict[str, object]]:
    nodes: list[dict[str, object]] = []

    def visit(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return
        if "@id" in value or "@type" in value:
            nodes.append(value)
        graph = value.get("@graph")
        if graph is not None:
            visit(graph)

    visit(document)
    return nodes


def test_jsonld_projects_graph_objects_and_relations(tmp_path: Path) -> None:
    _write_project(tmp_path)
    document = jsonld_export.build_document(_snapshot(tmp_path))

    assert document["@context"]["@version"] == 1.1
    graph = document["@graph"]
    assert graph[0]["@type"] == "qn:EngineeringGraph"
    objects = [node for node in graph if node.get("@type") == "qn:EngineeringObject"]
    relations = [node for node in graph if node.get("@type") == "qn:Relation"]
    assert {node["canonicalId"] for node in objects} == {"SYS-001", "TC-001"}
    assert len(relations) == 1
    assert relations[0]["relationType"] == "verified-by"
    assert relations[0]["semanticFamily"] == "verification"
    assert relations[0]["source"].endswith("SYS-001")
    assert relations[0]["target"].endswith("TC-001")


def test_jsonld_preserves_authored_attributes_as_json(tmp_path: Path) -> None:
    _write_project(tmp_path)
    document = jsonld_export.build_document(_snapshot(tmp_path))
    requirement = next(
        node
        for node in document["@graph"]
        if node.get("canonicalId") == "SYS-001"
    )
    assert requirement["attributes"]["priority"] == "high"


def test_jsonld_is_byte_deterministic(tmp_path: Path) -> None:
    _write_project(tmp_path)
    snapshot = _snapshot(tmp_path)
    assert jsonld_export.render(snapshot) == jsonld_export.render(snapshot)
    assert jsonld_export.render(snapshot).endswith("\n")


def test_jsonld_write_is_parseable_json(tmp_path: Path) -> None:
    _write_project(tmp_path)
    destination = tmp_path / "exchange" / "graph.jsonld"
    jsonld_export.write(destination, _snapshot(tmp_path))
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["quartoNeedsJsonLdVersion"] == "1"


def test_jsonld_expands_with_independent_processor(tmp_path: Path) -> None:
    _write_project(tmp_path)
    document = jsonld_export.build_document(_snapshot(tmp_path))

    expanded = jsonld.expand(document)
    nodes = _expanded_nodes(expanded)
    ids = {node.get("@id") for node in nodes}
    assert f"{jsonld_export.QN_NAMESPACE}object:SYS-001" in ids
    assert f"{jsonld_export.QN_NAMESPACE}object:TC-001" in ids
    assert any(
        f"{jsonld_export.QN_NAMESPACE}Relation" in node.get("@type", [])
        for node in nodes
    )


def test_jsonld_rdf_projection_preserves_relation_endpoints(tmp_path: Path) -> None:
    _write_project(tmp_path)
    document = jsonld_export.build_document(_snapshot(tmp_path))

    nquads = jsonld.to_rdf(document, {"format": "application/n-quads"})
    source_predicate = f"<{jsonld_export.QN_NAMESPACE}source>"
    target_predicate = f"<{jsonld_export.QN_NAMESPACE}target>"
    source_object = f"<{jsonld_export.QN_NAMESPACE}object:SYS-001>"
    target_object = f"<{jsonld_export.QN_NAMESPACE}object:TC-001>"

    assert source_predicate in nquads and source_object in nquads
    assert target_predicate in nquads and target_object in nquads
