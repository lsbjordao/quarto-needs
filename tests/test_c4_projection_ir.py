from __future__ import annotations

import pytest

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4.model import C4ElementRole
from quarto_needs.c4.projection import (
    C4ProjectionError,
    available_scopes,
    project_c4,
)
from quarto_needs.model import EngineeringObject, Relation


def _obj(identifier, *, type, title=None, attributes=None, relations=None):
    return EngineeringObject(
        identifier,
        type,
        title or identifier.title(),
        status="draft",
        attributes=attributes or {},
        relations=relations or [],
    )


def _snapshot(*objects):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None
    return result.snapshot


def _ids(view):
    return [element.id for element in view.elements]


def test_system_context_shows_the_system_and_its_interacting_neighbours() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "EXT-1", "SYS-1")]),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    assert view.id == "system-context-SYS-1"
    assert view.level == "system-context"
    assert view.scope_id == "SYS-1"
    assert _ids(view) == ["ACTOR-1", "EXT-1", "SYS-1"]
    assert "CONTAINER-1" not in _ids(view)


def test_roles_and_the_external_flag_come_from_the_object_type() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "EXT-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    roles = {element.id: element.role for element in view.elements}
    assert roles == {
        "SYS-1": C4ElementRole.SOFTWARE_SYSTEM,
        "ACTOR-1": C4ElementRole.PERSON,
        "EXT-1": C4ElementRole.EXTERNAL_SYSTEM,
    }
    external = {element.id: element.external for element in view.elements}
    assert external == {"SYS-1": False, "ACTOR-1": False, "EXT-1": True}


def test_container_level_resolves_children_authored_as_part_of() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj(
            "CONTAINER-1",
            type="container",
            attributes={"technology": "Python 3.12"},
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
    )
    view = project_c4(snapshot, level="container", scope_id="SYS-1")
    assert _ids(view) == ["CONTAINER-1", "SYS-1"]
    container = view.element("CONTAINER-1")
    assert container.parent_id == "SYS-1"
    assert container.technology == "Python 3.12"
    # The scope is the view's root: its own parent is out of scope.
    assert view.scope.parent_id is None
    # Grandchildren stop at one level.
    assert "COMP-1" not in _ids(view)


def test_container_level_resolves_children_authored_as_decomposes() -> None:
    # part-of runs child->parent; decomposes runs parent->child. A consumer
    # that checks only one direction silently drops every hierarchy authored
    # the other way -- the exact defect the previous slice had to fix.
    snapshot = _snapshot(
        _obj("SYS-1", type="system", relations=[Relation("decomposes", "SYS-1", "CONTAINER-1")]),
        _obj("CONTAINER-1", type="container"),
    )
    view = project_c4(snapshot, level="container", scope_id="SYS-1")
    assert _ids(view) == ["CONTAINER-1", "SYS-1"]
    assert view.element("CONTAINER-1").parent_id == "SYS-1"


def test_component_level_does_not_pull_in_the_scopes_own_parent() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
        _obj("SRC-1", type="source-module", relations=[Relation("part-of", "SRC-1", "COMP-1")]),
    )
    view = project_c4(snapshot, level="component", scope_id="CONTAINER-1")
    assert _ids(view) == ["COMP-1", "CONTAINER-1"]
    assert "SYS-1" not in _ids(view)
    assert "SRC-1" not in _ids(view)


def test_code_level_shows_a_components_source_modules() -> None:
    snapshot = _snapshot(
        _obj("COMP-1", type="component"),
        _obj(
            "SRC-1",
            type="source-module",
            attributes={"language": "Python"},
            relations=[Relation("part-of", "SRC-1", "COMP-1")],
        ),
    )
    view = project_c4(snapshot, level="code", scope_id="COMP-1")
    assert _ids(view) == ["COMP-1", "SRC-1"]
    assert view.element("SRC-1").role is C4ElementRole.CODE
    assert view.element("SRC-1").parent_id == "COMP-1"


def test_children_are_filtered_to_the_levels_expected_child_type() -> None:
    # ARC001 already rejects a layer skip as a graph error; the projection
    # additionally refuses to draw one, so a project running under an
    # advisory profile still gets a coherent diagram.
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="container", scope_id="SYS-1")
    assert _ids(view) == ["SYS-1"]


def test_a_non_architecture_neighbour_is_not_a_c4_element() -> None:
    # Before this projection existed, a depends-on edge from a requirement
    # reached the Mermaid renderer and raised KeyError inside
    # `quarto-needs scan`. Only types in C4_ROLE_BY_TYPE are elements.
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("REQ-1", type="system-requirement", relations=[Relation("depends-on", "REQ-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    assert _ids(view) == ["SYS-1"]
    assert view.relationships == ()


def test_relationships_keep_semantic_direction_and_carry_the_catalog_label() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    assert len(view.relationships) == 1
    relationship = view.relationships[0]
    assert relationship.source_id == "ACTOR-1"
    assert relationship.target_id == "SYS-1"
    assert relationship.relation_type == "depends-on"
    assert relationship.description == "Depends on"
    # Known limitation: the parser has no relation-attribute grammar.
    assert relationship.technology is None


def test_interaction_edges_survive_at_container_level() -> None:
    # The IR keeps them; whether a given renderer can draw an arrow into a
    # boundary is that renderer's problem, not the model's.
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="container", scope_id="SYS-1")
    assert _ids(view) == ["ACTOR-1", "CONTAINER-1", "SYS-1"]
    assert [item.id for item in view.relationships] == ["depends-on:ACTOR-1:SYS-1"]


def test_ordering_is_stable_regardless_of_authoring_order() -> None:
    objects = [
        _obj("SYS-1", type="system"),
        _obj("ZED", type="external-system", relations=[Relation("depends-on", "ZED", "SYS-1")]),
        _obj("ABLE", type="actor", relations=[Relation("depends-on", "ABLE", "SYS-1")]),
    ]
    forward = project_c4(_snapshot(*objects), level="system-context", scope_id="SYS-1")
    backward = project_c4(_snapshot(*reversed(objects)), level="system-context", scope_id="SYS-1")
    assert _ids(forward) == ["ABLE", "SYS-1", "ZED"]
    assert _ids(forward) == _ids(backward)
    assert forward.relationships == backward.relationships


def test_the_legacy_context_level_name_is_accepted() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"))
    view = project_c4(snapshot, level="context", scope_id="SYS-1")
    assert view.level == "system-context"
    assert view.id == "system-context-SYS-1"


def test_invalid_scope_and_level_raise_c4008() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"), _obj("CONTAINER-1", type="container"))
    with pytest.raises(C4ProjectionError, match="unsupported C4 level") as unsupported:
        project_c4(snapshot, level="deployment", scope_id="SYS-1")
    assert unsupported.value.code == "C4008"
    with pytest.raises(C4ProjectionError, match="MISSING"):
        project_c4(snapshot, level="system-context", scope_id="MISSING")
    with pytest.raises(C4ProjectionError, match="requires a 'system' scope"):
        project_c4(snapshot, level="container", scope_id="CONTAINER-1")
    with pytest.raises(C4ProjectionError, match="requires a 'container' scope"):
        project_c4(snapshot, level="component", scope_id="SYS-1")
    with pytest.raises(C4ProjectionError, match="requires a 'component' scope"):
        project_c4(snapshot, level="code", scope_id="SYS-1")


def test_available_scopes_enumerates_the_levels_scope_type() -> None:
    snapshot = _snapshot(
        _obj("SYS-B", type="system"),
        _obj("SYS-A", type="system"),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-A")]),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
    )
    assert available_scopes(snapshot, "system-context") == ("SYS-A", "SYS-B")
    assert available_scopes(snapshot, "container") == ("SYS-A", "SYS-B")
    assert available_scopes(snapshot, "component") == ("CONTAINER-1",)
    assert available_scopes(snapshot, "code") == ("COMP-1",)
    assert available_scopes(snapshot, "deployment") == ()
