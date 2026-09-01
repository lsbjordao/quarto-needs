from __future__ import annotations

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4_projection import build_c4_view
from quarto_needs.c4_render import c4_code_table_markdown, c4_mermaid_source
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


def test_context_diagram_shows_the_system_as_an_opaque_box() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[Relation("depends-on", "ACTOR-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="context")
    assert source.splitlines()[0] == "C4Context"
    assert 'System(' in source
    assert 'Person(' in source
    assert 'Rel(' in source
    assert source.endswith("\n")


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
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="container")
    assert source.splitlines()[0] == "C4Container"
    assert "System_Boundary(" in source
    assert 'Container(' in source
    assert "Python 3.12" in source
    assert source.rstrip("\n").endswith("}")


def test_component_diagram_wraps_components_in_a_container_boundary() -> None:
    snapshot = _snapshot(
        _obj("CONTAINER-1", type="container", title="Python package"),
        _obj(
            "COMP-1", type="component", title="Declaration parser",
            relations=[Relation("part-of", "COMP-1", "CONTAINER-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="CONTAINER-1", level="component")
    source = c4_mermaid_source(projection, focus_id="CONTAINER-1", level="component")
    assert source.splitlines()[0] == "C4Component"
    assert "Container_Boundary(" in source
    assert "Component(" in source


def test_labels_are_escaped_against_mermaid_syntax() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system", title='System "with quotes"'))
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="context")
    call = source.split("System(", 1)[1].split(")", 1)[0]
    # Exactly the label's two syntactic wrapping quotes should survive; the
    # title's own embedded quote must have been escaped to a single quote,
    # not left as a third/fourth raw `"` that would break the macro call.
    assert call.count('"') == 2


def test_code_level_renders_a_plain_markdown_table_not_mermaid() -> None:
    snapshot = _snapshot(
        _obj("COMP-1", type="component", title="Declaration parser"),
        _obj(
            "SRC-1", type="source-module", title="QMD declaration parser module",
            attributes={"path": "src/quarto_needs/parser.py", "language": "Python"},
            relations=[Relation("part-of", "SRC-1", "COMP-1")],
        ),
    )
    # Code level does not go through build_c4_view (its focus is a component,
    # not a container) — it reads the component's own direct children
    # directly from the snapshot instead. See Step 3's implementation.
    table = c4_code_table_markdown(snapshot, focus_id="COMP-1")
    assert table.splitlines()[0].startswith("|")
    assert "C4Component" not in table
    assert "src/quarto_needs/parser.py" in table
    assert "Python" in table
