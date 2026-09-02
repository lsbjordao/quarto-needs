from __future__ import annotations

from quarto_needs.c4.model import C4Element, C4ElementRole, C4Relationship, C4View
from quarto_needs.c4.validation import C4Diagnostic, validate_c4_view


def _element(identifier: str, role: C4ElementRole, parent_id: str | None = None) -> C4Element:
    return C4Element(id=identifier, role=role, name=identifier.title(), parent_id=parent_id)


def _view(level: str, scope_id: str | None, elements, relationships=()) -> C4View:
    return C4View(
        id=f"{level}-{scope_id}",
        level=level,
        scope_id=scope_id,
        elements=tuple(elements),
        relationships=tuple(relationships),
    )


def _codes(view: C4View) -> list[str]:
    return [diagnostic.code for diagnostic in validate_c4_view(view)]


def test_a_well_formed_container_view_produces_no_diagnostics() -> None:
    view = _view(
        "container",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1"),
            _element("ACTOR-1", C4ElementRole.PERSON),
        ],
    )
    assert validate_c4_view(view) == ()


def test_c4001_flags_a_container_with_no_parent_system() -> None:
    view = _view(
        "container",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("CONTAINER-A", C4ElementRole.CONTAINER),
        ],
    )
    diagnostics = validate_c4_view(view)
    assert [item.code for item in diagnostics] == ["C4001"]
    assert diagnostics[0].object_id == "CONTAINER-A"
    assert "CONTAINER-A" in diagnostics[0].message
    assert diagnostics[0].severity == "error"


def test_c4001_does_not_flag_the_scope_element_itself() -> None:
    # A component view's scope container legitimately has no parent *in the
    # view* -- its system is one level up and deliberately out of scope.
    view = _view(
        "component",
        "CONTAINER-A",
        [
            _element("CONTAINER-A", C4ElementRole.CONTAINER),
            _element("COMP-1", C4ElementRole.COMPONENT, parent_id="CONTAINER-A"),
        ],
    )
    assert validate_c4_view(view) == ()


def test_c4002_flags_a_parent_that_is_not_in_the_view() -> None:
    view = _view(
        "component",
        "CONTAINER-A",
        [
            _element("CONTAINER-A", C4ElementRole.CONTAINER),
            _element("COMP-1", C4ElementRole.COMPONENT, parent_id="CONTAINER-GONE"),
        ],
    )
    diagnostics = validate_c4_view(view)
    assert [item.code for item in diagnostics] == ["C4002"]
    assert "CONTAINER-GONE" in diagnostics[0].message
    assert diagnostics[0].object_id == "COMP-1"


def test_c4003_flags_a_containment_cycle() -> None:
    view = _view(
        "container",
        "SYS-A",
        [
            _element("SYS-A", C4ElementRole.SOFTWARE_SYSTEM, parent_id="CONTAINER-B"),
            _element("CONTAINER-B", C4ElementRole.CONTAINER, parent_id="SYS-A"),
        ],
    )
    codes = _codes(view)
    assert "C4003" in codes
    cycle = next(item for item in validate_c4_view(view) if item.code == "C4003")
    assert "SYS-A" in cycle.message and "CONTAINER-B" in cycle.message


def test_c4006_flags_a_relationship_pointing_outside_the_view() -> None:
    view = _view(
        "system-context",
        "SYS-1",
        [_element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM)],
        [
            C4Relationship(
                id="depends-on:SYS-1:GONE",
                source_id="SYS-1",
                target_id="GONE",
                relation_type="depends-on",
            )
        ],
    )
    diagnostics = validate_c4_view(view)
    assert [item.code for item in diagnostics] == ["C4006"]
    assert "GONE" in diagnostics[0].message


def test_c4007_flags_a_duplicate_element_id() -> None:
    view = _view(
        "container",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1"),
            _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1"),
        ],
    )
    assert "C4007" in _codes(view)


def test_c4009_flags_a_container_leaking_into_a_system_context_view() -> None:
    view = _view(
        "system-context",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1"),
        ],
    )
    codes = _codes(view)
    assert "C4009" in codes


def test_diagnostics_are_sorted_and_serializable() -> None:
    view = _view(
        "container",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("ZZZ-CONTAINER", C4ElementRole.CONTAINER),
            _element("AAA-CONTAINER", C4ElementRole.CONTAINER),
        ],
    )
    diagnostics = validate_c4_view(view)
    assert [item.object_id for item in diagnostics] == ["AAA-CONTAINER", "ZZZ-CONTAINER"]
    assert diagnostics[0].to_dict() == {
        "code": "C4001",
        "severity": "error",
        "message": diagnostics[0].message,
        "objectId": "AAA-CONTAINER",
    }


def test_diagnostic_without_an_object_id_serializes_a_null() -> None:
    assert C4Diagnostic("C4004", "warning", "no renderer").to_dict() == {
        "code": "C4004",
        "severity": "warning",
        "message": "no renderer",
        "objectId": None,
    }
