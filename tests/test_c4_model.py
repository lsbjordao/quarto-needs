from __future__ import annotations

from quarto_needs.c4.model import (
    CONTAINMENT_ROLES,
    C4_ROLE_BY_TYPE,
    C4Element,
    C4ElementRole,
    C4Relationship,
    C4View,
    LEVEL_ALIASES,
    LEVELS,
    LayoutDirection,
    identifier_map,
    normalize_level,
    relationship_id,
    sanitize_identifier,
)


def _element(identifier: str, role: C4ElementRole, **kwargs) -> C4Element:
    return C4Element(id=identifier, role=role, name=identifier.title(), **kwargs)


def test_every_architecture_object_type_maps_to_exactly_one_role() -> None:
    # The mapping is explicit and canonical -- never inferred from titles,
    # tags or colours (Spec 45). These types are the architecture types the
    # graph already has; nothing else is a C4 element.
    assert C4_ROLE_BY_TYPE == {
        "actor": C4ElementRole.PERSON,
        "external-system": C4ElementRole.EXTERNAL_SYSTEM,
        "system": C4ElementRole.SOFTWARE_SYSTEM,
        "container": C4ElementRole.CONTAINER,
        "component": C4ElementRole.COMPONENT,
        "source-module": C4ElementRole.CODE,
        "deployment-node": C4ElementRole.DEPLOYMENT_NODE,
    }


def test_containment_roles_are_the_layers_below_the_root() -> None:
    assert CONTAINMENT_ROLES == (
        C4ElementRole.CONTAINER,
        C4ElementRole.COMPONENT,
        C4ElementRole.CODE,
    )
    assert C4ElementRole.SOFTWARE_SYSTEM not in CONTAINMENT_ROLES
    assert C4ElementRole.PERSON not in CONTAINMENT_ROLES


def test_levels_and_the_legacy_context_alias() -> None:
    assert LEVELS == (
        "system-context",
        "container",
        "component",
        "code",
        "deployment",
        "dynamic",
    )
    # Published, not private: the artifact manifest hands this table to Lua
    # so the shortcode resolves an alias by lookup instead of by a rule of
    # its own (Task 8's index.json, Task 10's reader).
    assert LEVEL_ALIASES == {"context": "system-context"}
    assert normalize_level("system-context") == "system-context"
    assert normalize_level("context") == "system-context"
    assert normalize_level("container") == "container"
    assert normalize_level("code") == "code"
    assert normalize_level("deployment") == "deployment"
    assert normalize_level("dynamic") == "dynamic"
    assert normalize_level("") is None
    assert normalize_level("codex") is None


def test_layout_direction_is_renderer_neutral() -> None:
    assert {member.value for member in LayoutDirection} == {
        "top-bottom", "bottom-top", "left-right", "right-left",
    }


def test_element_to_dict_always_emits_every_declared_key() -> None:
    # Unlike PublicNode's conditional inclusion, the IR emits nulls: this
    # payload is a versioned boundary consumed by four adapters and pinned
    # by goldens, so a stable key set matters more than payload size.
    element = _element("CONTAINER-CORE", C4ElementRole.CONTAINER, technology="Python")
    assert element.to_dict() == {
        "id": "CONTAINER-CORE",
        "role": "container",
        "name": "Container-Core",
        "description": None,
        "technology": "Python",
        "parentId": None,
        "external": False,
        "tags": [],
    }


def test_relationship_to_dict_and_deterministic_id() -> None:
    assert relationship_id("A", "B", "depends-on") == "depends-on:A:B"
    relationship = C4Relationship(
        id=relationship_id("A", "B", "depends-on"),
        source_id="A",
        target_id="B",
        relation_type="depends-on",
        description="Depends on",
    )
    assert relationship.to_dict() == {
        "id": "depends-on:A:B",
        "sourceId": "A",
        "targetId": "B",
        "relationType": "depends-on",
        "description": "Depends on",
        "technology": None,
        "order": None,
        "tags": [],
    }


def test_view_lookup_helpers() -> None:
    system = _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM)
    first = _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1")
    second = _element("CONTAINER-B", C4ElementRole.CONTAINER, parent_id="SYS-1")
    outside = _element("ACTOR-1", C4ElementRole.PERSON)
    view = C4View(
        id="container-SYS-1",
        level="container",
        scope_id="SYS-1",
        elements=(first, second, outside, system),
        relationships=(),
    )
    assert view.scope is system
    assert view.element("CONTAINER-B") is second
    assert view.element("NOPE") is None
    assert view.children_of("SYS-1") == (first, second)
    assert view.children_of("CONTAINER-A") == ()


def test_view_scope_is_none_when_the_scope_element_is_absent() -> None:
    view = C4View(id="v", level="container", scope_id="MISSING", elements=(), relationships=())
    assert view.scope is None


def test_sanitize_identifier_is_readable_and_syntactically_safe() -> None:
    assert sanitize_identifier("SYS-QUARTO-NEEDS") == "SYS_QUARTO_NEEDS"
    assert sanitize_identifier("COMP.parser") == "COMP_parser"
    assert sanitize_identifier("already_safe") == "already_safe"
    # A leading digit is invalid in every target DSL's identifier grammar.
    assert sanitize_identifier("1ST") == "c4_1ST"
    assert sanitize_identifier("") == "c4_"


def test_identifier_map_suffixes_every_member_of_a_collision_group() -> None:
    # "A-B" and "A.B" both sanitize to "A_B". Suffixing only the second one
    # seen would make the output depend on element order; both must be
    # suffixed, and the result must be permutation-independent.
    dashed = _element("A-B", C4ElementRole.COMPONENT)
    dotted = _element("A.B", C4ElementRole.COMPONENT)
    lonely = _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM)
    forward = C4View(
        id="v", level="component", scope_id="SYS-1",
        elements=(dashed, dotted, lonely), relationships=(),
    )
    backward = C4View(
        id="v", level="component", scope_id="SYS-1",
        elements=(lonely, dotted, dashed), relationships=(),
    )
    mapping = identifier_map(forward)
    assert identifier_map(backward) == mapping
    assert mapping["SYS-1"] == "SYS_1"
    assert mapping["A-B"].startswith("A_B_")
    assert mapping["A.B"].startswith("A_B_")
    assert mapping["A-B"] != mapping["A.B"]
    assert len(set(mapping.values())) == 3
