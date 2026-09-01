from __future__ import annotations

import pytest

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4_projection import C4ViewError, build_c4_view
from quarto_needs.model import EngineeringObject, Relation


def _obj(id: str, *, type: str, relations: list[Relation] | None = None) -> EngineeringObject:
    return EngineeringObject(id, type, id.title(), status="draft", relations=relations or [])


def _snapshot(*objects: EngineeringObject):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None
    return result.snapshot


def test_context_view_shows_the_system_and_its_direct_neighbors_only() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj(
            "CONTAINER-1",
            type="container",
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    node_ids = {node.id for node in projection.nodes}
    assert node_ids == {"SYS-1", "ACTOR-1"}
    assert "CONTAINER-1" not in node_ids


def test_container_view_shows_the_systems_direct_containers() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj(
            "CONTAINER-1",
            type="container",
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
        _obj(
            "COMP-1",
            type="component",
            relations=[Relation("part-of", "COMP-1", "CONTAINER-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    node_ids = {node.id for node in projection.nodes}
    assert node_ids == {"SYS-1", "ACTOR-1", "CONTAINER-1"}
    assert "COMP-1" not in node_ids


def test_component_view_shows_the_containers_direct_components() -> None:
    snapshot = _snapshot(
        _obj("CONTAINER-1", type="container"),
        _obj(
            "COMP-1",
            type="component",
            relations=[Relation("part-of", "COMP-1", "CONTAINER-1")],
        ),
        _obj(
            "SRC-1",
            type="source-module",
            relations=[Relation("part-of", "SRC-1", "COMP-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="CONTAINER-1", level="component")
    node_ids = {node.id for node in projection.nodes}
    assert node_ids == {"CONTAINER-1", "COMP-1"}
    assert "SRC-1" not in node_ids


def test_context_and_container_levels_require_a_system_focus() -> None:
    snapshot = _snapshot(_obj("CONTAINER-1", type="container"))
    with pytest.raises(C4ViewError, match="requires a 'system' focus"):
        build_c4_view(snapshot, focus_id="CONTAINER-1", level="context")
    with pytest.raises(C4ViewError, match="requires a 'system' focus"):
        build_c4_view(snapshot, focus_id="CONTAINER-1", level="container")


def test_component_level_requires_a_container_focus() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"))
    with pytest.raises(C4ViewError, match="requires a 'container' focus"):
        build_c4_view(snapshot, focus_id="SYS-1", level="component")


def test_unknown_focus_id_raises() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"))
    with pytest.raises(C4ViewError, match="MISSING"):
        build_c4_view(snapshot, focus_id="MISSING", level="context")


def test_unsupported_level_raises() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"))
    with pytest.raises(C4ViewError, match="unsupported C4 level"):
        build_c4_view(snapshot, focus_id="SYS-1", level="code")
