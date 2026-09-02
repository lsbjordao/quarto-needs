from __future__ import annotations

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4_plantuml import c4_plantuml_source
from quarto_needs.c4_projection import build_c4_view
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


def test_context_diagram_includes_the_c4_context_stdlib() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[Relation("depends-on", "ACTOR-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_plantuml_source(projection, focus_id="SYS-1", level="context")
    assert source.splitlines()[0] == "@startuml"
    assert "!include <C4/C4_Context>" in source
    assert "System(" in source
    assert "Person(" in source
    assert "Rel(" in source
    assert source.rstrip("\n").endswith("@enduml")


def test_container_diagram_wraps_containers_in_a_system_boundary() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "CONTAINER-1", type="container", title="Python package",
            attributes={"technology": "Python 3.12"},
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    source = c4_plantuml_source(projection, focus_id="SYS-1", level="container")
    assert "!include <C4/C4_Container>" in source
    assert "System_Boundary(" in source
    assert "Container(" in source
    assert "Python 3.12" in source


def test_component_diagram_wraps_components_in_a_container_boundary() -> None:
    snapshot = _snapshot(
        _obj("CONTAINER-1", type="container", title="Python package"),
        _obj(
            "COMP-1", type="component", title="Declaration parser",
            relations=[Relation("part-of", "COMP-1", "CONTAINER-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="CONTAINER-1", level="component")
    source = c4_plantuml_source(projection, focus_id="CONTAINER-1", level="component")
    assert "!include <C4/C4_Component>" in source
    assert "Container_Boundary(" in source
    assert "Component(" in source


def test_labels_are_escaped_against_plantuml_syntax() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system", title='System "with quotes"'))
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_plantuml_source(projection, focus_id="SYS-1", level="context")
    call = source.split("System(", 1)[1].split(")", 1)[0]
    assert call.count('"') == 2
