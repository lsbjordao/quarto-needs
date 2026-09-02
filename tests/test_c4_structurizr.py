from __future__ import annotations

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4_projection import build_c4_view
from quarto_needs.c4_structurizr import c4_structurizr_source
from quarto_needs.model import EngineeringObject, Relation


def _obj(id: str, *, type: str, title: str | None = None, attributes=None, relations=None):
    return EngineeringObject(
        id, type, title or id.title(), status="draft",
        attributes=attributes or {}, relations=relations or [],
    )


def _snapshot(*objects):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None
    return result.snapshot


def test_context_view_declares_the_system_and_a_relationship() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[Relation("depends-on", "ACTOR-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_structurizr_source(projection, focus_id="SYS-1", level="context")
    assert source.splitlines()[0] == "workspace {"
    assert "= softwareSystem " in source
    assert "= person " in source
    assert "->" in source
    assert "systemContext " in source
    assert source.endswith("\n")


def test_container_view_nests_containers_inside_the_system_block() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "CONTAINER-1", type="container", title="Python package",
            attributes={"technology": "Python 3.12"},
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    source = c4_structurizr_source(projection, focus_id="SYS-1", level="container")
    assert "= softwareSystem \"Quarto-Needs\" {" in source
    assert "= container " in source
    assert "Python 3.12" in source
    assert "container " in source.split("views {", 1)[1]


def test_component_view_nests_components_inside_the_container_block() -> None:
    snapshot = _snapshot(
        _obj("CONTAINER-1", type="container", title="Python package"),
        _obj(
            "COMP-1", type="component", title="Declaration parser",
            relations=[Relation("part-of", "COMP-1", "CONTAINER-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="CONTAINER-1", level="component")
    source = c4_structurizr_source(projection, focus_id="CONTAINER-1", level="component")
    assert "= container \"Python package\" {" in source
    assert "= component " in source


def test_labels_are_escaped_against_structurizr_syntax() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system", title='System "with quotes"'))
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_structurizr_source(projection, focus_id="SYS-1", level="context")
    line = next(line for line in source.splitlines() if "= softwareSystem" in line)
    assert line.count('"') == 2


def test_source_is_byte_stable_across_calls() -> None:
    snapshot = _snapshot(
        _obj(
            "SYS-1", type="system", title="Quarto-Needs",
            relations=[Relation("depends-on", "SYS-1", "EXT-1")],
        ),
        _obj("EXT-1", type="external-system", title="GitHub"),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    first = c4_structurizr_source(projection, focus_id="SYS-1", level="context")
    second = c4_structurizr_source(projection, focus_id="SYS-1", level="context")
    assert first == second
    assert 'tags "External"' in first
