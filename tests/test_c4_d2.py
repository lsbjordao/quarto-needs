from __future__ import annotations

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4_d2 import c4_d2_source
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


def test_context_view_declares_the_system_and_a_relationship() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[Relation("depends-on", "ACTOR-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_d2_source(projection, focus_id="SYS-1", level="context")
    assert 'shape: person' in source
    assert 'shape: rectangle' in source
    assert "->" in source
    assert source.endswith("\n")


def test_container_view_nests_children_and_addresses_them_by_dotted_path() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "CONTAINER-1", type="container", title="Python package",
            attributes={"technology": "Python 3.12"},
            relations=[
                Relation("part-of", "CONTAINER-1", "SYS-1"),
                Relation("depends-on", "CONTAINER-1", "SYS-1"),
            ],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    source = c4_d2_source(projection, focus_id="SYS-1", level="container")
    assert "Python 3.12" in source
    focus_line = next(line for line in source.splitlines() if line.startswith("SYS_1:"))
    assert focus_line
    assert "SYS_1.CONTAINER_1 -> SYS_1" in source


def test_external_system_uses_the_hexagon_shape() -> None:
    snapshot = _snapshot(
        _obj(
            "SYS-1", type="system", title="Quarto-Needs",
            relations=[Relation("depends-on", "SYS-1", "EXT-1")],
        ),
        _obj("EXT-1", type="external-system", title="GitHub"),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_d2_source(projection, focus_id="SYS-1", level="context")
    assert "shape: hexagon" in source


def test_labels_are_escaped_against_d2_syntax() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system", title='System "with quotes"'))
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_d2_source(projection, focus_id="SYS-1", level="context")
    line = next(line for line in source.splitlines() if line.startswith("SYS_1:"))
    assert line.count('"') == 2


def test_relationship_technology_is_folded_into_the_d2_edge_label() -> None:
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
    source = c4_d2_source(projection, focus_id="SYS-1", level="context")
    relationship = next(
        line for line in source.splitlines() if " -> " in line and "calls over HTTPS" in line
    )
    assert "HTTPS/JSON" in relationship


def test_deployment_view_nests_deployed_members_under_the_focus_package() -> None:
    snapshot = _snapshot(
        _obj("DEPLOY-1", type="deployment-node", title="Production"),
        _obj(
            "CONTAINER-1", type="container", title="Python package",
            attributes={"technology": "Python 3.12"},
            relations=[Relation("deployed-on", "CONTAINER-1", "DEPLOY-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="DEPLOY-1", level="deployment")
    source = c4_d2_source(projection, focus_id="DEPLOY-1", level="deployment")
    assert "shape: package" in source
    assert "CONTAINER_1" in source
