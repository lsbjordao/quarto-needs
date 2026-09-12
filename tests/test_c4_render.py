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
    assert 'UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")' in source
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


def test_code_table_finds_children_authored_via_decomposes_too() -> None:
    """A component that declares its source-modules via `decomposes`
    (parent declares child, source=focus/target=child) must show up in the
    table exactly like a `part-of`-authored one does — mirrors
    `_is_child_edge`'s dual-direction handling, which `c4_code_table_markdown`
    must match via its own `_child_id_if_matches` helper.
    """
    snapshot = _snapshot(
        _obj(
            "COMP-1", type="component", title="Declaration parser",
            # A relation's source is always the id of the declaring object
            # (analysis.py builds RelationToken/RelationRecord from
            # `declaration.id`, ignoring `Relation.source`) — so the
            # `decomposes` edge must be authored here, on the parent, not on
            # SRC-1 below.
            relations=[Relation("decomposes", "COMP-1", "SRC-1")],
        ),
        _obj(
            "SRC-1", type="source-module", title="QMD declaration parser module",
            attributes={"path": "src/quarto_needs/parser.py", "language": "Python"},
        ),
    )
    table = c4_code_table_markdown(snapshot, focus_id="COMP-1")
    assert "src/quarto_needs/parser.py" in table
    assert "Python" in table


def test_container_diagram_omits_rel_lines_targeting_the_boundary_itself() -> None:
    """A `depends-on` edge whose target is the focus node itself becomes,
    at container/component level, a `Rel()` pointing at the System_Boundary/
    Container_Boundary macro's own alias — not a real positioned node.

    Confirmed by direct reproduction against the exact mermaid.js Quarto
    ships (11.6.0) in a real headless Chrome: mermaid's C4 layout engine
    throws mid-render ("Cannot read properties of undefined (reading 'x')")
    when asked to draw a Rel to a boundary alias, even though the grammar
    parses it fine — a real upstream limitation, not a syntax mistake here.
    Dropping the Rel is not the whole fix on its own — see the next test
    for why the actor's box is also omitted, not merely left disconnected;
    the relationship is not lost information either way, since the context
    diagram one level up already shows it against the system as a whole.
    """
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "CONTAINER-1", type="container", title="Python package",
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[Relation("depends-on", "ACTOR-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="container")

    # No Rel() line references the boundary's own alias as an endpoint.
    boundary_alias = source.split("System_Boundary(", 1)[1].split(",", 1)[0].strip()
    for line in source.splitlines():
        if line.strip().startswith("Rel("):
            assert boundary_alias not in line


def test_container_diagram_omits_an_actor_left_with_no_surviving_relation() -> None:
    """Dropping the boundary-targeted Rel (previous test) is not enough on
    its own: a box left with no remaining edge renders as a disconnected
    floating shape with no indication of why it's on the diagram at all —
    confirmed by a real screenshot of the actual rendered SVG, which is
    what surfaced this as a real defect, not just a style nit. An actor/
    external system whose only relation was to the focus itself must be
    omitted from the container/component view entirely, matching standard
    C4 practice: that diagram level only depicts things that interact with
    something it actually shows.
    """
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "CONTAINER-1", type="container", title="Python package",
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[Relation("depends-on", "ACTOR-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="container")

    assert "Person(" not in source
    assert "Container(" in source


def test_container_diagram_keeps_two_others_joined_by_their_own_relation() -> None:
    """The omission above is scoped to nodes left with zero surviving
    edges — two 'other' nodes each reachable via the (now-dropped) edge to
    the focus, but also joined to *each other* by a depends-on edge the
    boundary filter does not touch, must both still appear with that Rel
    line intact."""
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "CONTAINER-1", type="container", title="Python package",
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[
                Relation("depends-on", "ACTOR-1", "SYS-1"),
                Relation("depends-on", "ACTOR-1", "EXT-1"),
            ],
        ),
        _obj(
            "EXT-1", type="external-system", title="Issue tracker",
            relations=[Relation("depends-on", "EXT-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="container")

    assert "Person(" in source
    assert "System_Ext(" in source
    assert "Rel(" in source


def test_context_diagram_keeps_rel_lines_to_the_system_itself() -> None:
    """At context level the focus is drawn as a plain System() node, not a
    boundary — the same depends-on edge is a normal, safely-renderable Rel
    there, and must not be dropped by the container/component-only guard."""
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[Relation("depends-on", "ACTOR-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="context")
    assert "Rel(" in source


def test_container_diagram_finds_children_authored_via_decomposes_too() -> None:
    """`_is_child_edge`'s `decomposes` branch (parent declares child,
    source=focus/target=child), exercised end to end through
    `c4_mermaid_source` — every other diagram test in this file uses
    `part-of` only.
    """
    snapshot = _snapshot(
        _obj(
            "SYS-1", type="system", title="Quarto-Needs",
            # See the analogous comment in the code-table test above: the
            # relation's source is the declaring object's id, so this must
            # be authored on SYS-1 (the parent), not on CONTAINER-1.
            relations=[Relation("decomposes", "SYS-1", "CONTAINER-1")],
        ),
        _obj("CONTAINER-1", type="container", title="Python package"),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="container")
    assert "System_Boundary(" in source
    assert "Container(" in source
    # The child renders inside the boundary block, not as a top-level box
    # alongside it.
    boundary_block = source.split("System_Boundary(", 1)[1].split("}", 1)[0]
    assert "Container(" in boundary_block


def test_relationship_attributes_reach_the_mermaid_relationship() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[
                Relation(
                    "depends-on", "ACTOR-1", "SYS-1",
                    attributes={"label": "calls over HTTPS", "technology": "HTTPS/JSON"},
                )
            ],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="context")
    relationship = next(
        line for line in source.splitlines() if line.strip().startswith("Rel(")
    )
    assert "calls over HTTPS" in relationship
    assert "HTTPS/JSON" in relationship


def test_deployment_diagram_wraps_deployed_members_in_a_deployment_node() -> None:
    snapshot = _snapshot(
        _obj("DEPLOY-1", type="deployment-node", title="Production"),
        _obj(
            "CONTAINER-1", type="container", title="Python package",
            attributes={"technology": "Python 3.12"},
            relations=[Relation("deployed-on", "CONTAINER-1", "DEPLOY-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="DEPLOY-1", level="deployment")
    source = c4_mermaid_source(projection, focus_id="DEPLOY-1", level="deployment")
    assert source.splitlines()[0] == "C4Deployment"
    assert "Deployment_Node(" in source
    boundary_block = source.split("Deployment_Node(", 1)[1].split("}", 1)[0]
    assert "Container(" in boundary_block
    assert "Python 3.12" in boundary_block


def test_dynamic_diagram_numbers_interactions_in_authored_order() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "CONTAINER-A", type="container", title="Python package",
            relations=[
                Relation("part-of", "CONTAINER-A", "SYS-1"),
                Relation(
                    "interacts-with", "CONTAINER-A", "CONTAINER-B",
                    attributes={"order": "2", "label": "writes the graph"},
                ),
            ],
        ),
        _obj(
            "CONTAINER-B", type="container", title="Extension",
            relations=[Relation("part-of", "CONTAINER-B", "SYS-1")],
        ),
        _obj(
            "ACTOR-1", type="actor", title="Engineer",
            relations=[
                Relation(
                    "interacts-with", "ACTOR-1", "CONTAINER-A",
                    attributes={"order": "1", "label": "runs quarto render"},
                )
            ],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="dynamic")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="dynamic")

    assert source.splitlines()[0] == "C4Dynamic"
    first = next(line for line in source.splitlines() if "RelIndex(1," in line)
    second = next(line for line in source.splitlines() if "RelIndex(2," in line)
    assert "runs quarto render" in first
    assert "writes the graph" in second
    assert "Engineer" in source
