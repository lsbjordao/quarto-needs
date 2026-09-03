from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4.projection import project_c4
from quarto_needs.c4.serialize import (
    C4_VIEW_SCHEMA_VERSION,
    c4_view_document,
    c4_view_fingerprint,
    render_c4_view,
)
from quarto_needs.c4.validation import validate_c4_view
from quarto_needs.model import EngineeringObject, Relation

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "c4-view-v1.schema.json").read_text(encoding="utf-8"))


def _obj(identifier, *, type, relations=None, attributes=None):
    return EngineeringObject(
        identifier, type, identifier.title(), status="draft",
        attributes=attributes or {}, relations=relations or [],
    )


def _fixture_snapshot():
    result = analyze_objects([
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "EXT-1", "SYS-1")]),
    ])
    assert result.snapshot is not None
    return result.snapshot


def _view():
    return project_c4(_fixture_snapshot(), level="system-context", scope_id="SYS-1")


def test_document_declares_the_versioned_schema_and_the_view_identity() -> None:
    document = c4_view_document(_view())
    assert document["schemaVersion"] == C4_VIEW_SCHEMA_VERSION == "quarto-needs-c4-view-v1"
    assert document["view"] == {
        "id": "system-context-SYS-1",
        "level": "system-context",
        "scopeId": "SYS-1",
    }
    assert [element["id"] for element in document["elements"]] == ["ACTOR-1", "EXT-1", "SYS-1"]
    assert [item["sourceId"] for item in document["relationships"]] == ["ACTOR-1", "EXT-1"]
    assert document["diagnostics"] == []
    assert document["fingerprint"] == c4_view_fingerprint(_view())


def test_document_validates_against_the_published_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    Draft202012Validator(SCHEMA).validate(c4_view_document(_view()))


def test_diagnostics_are_carried_in_the_document() -> None:
    view = _view()
    document = c4_view_document(view, diagnostics=validate_c4_view(view))
    assert document["diagnostics"] == []
    broken = project_c4(_fixture_snapshot(), level="container", scope_id="SYS-1")
    document = c4_view_document(broken, diagnostics=validate_c4_view(broken))
    Draft202012Validator(SCHEMA).validate(document)


def test_rendered_json_is_stable_text_with_a_trailing_newline() -> None:
    text = render_c4_view(_view())
    assert text.endswith("\n")
    assert json.loads(text)["schemaVersion"] == C4_VIEW_SCHEMA_VERSION
    assert render_c4_view(_view()) == text


def test_fingerprint_is_a_sha256_over_the_semantic_content_only() -> None:
    fingerprint = c4_view_fingerprint(_view())
    assert len(fingerprint) == 64
    assert set(fingerprint) <= set("0123456789abcdef")
    # Equivalent snapshots built in a different authoring order must agree.
    reordered = analyze_objects([
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "EXT-1", "SYS-1")]),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("SYS-1", type="system"),
    ])
    assert reordered.snapshot is not None
    assert (
        c4_view_fingerprint(
            project_c4(reordered.snapshot, level="system-context", scope_id="SYS-1")
        )
        == fingerprint
    )


def test_fingerprint_ignores_diagnostics_but_tracks_semantics() -> None:
    view = _view()
    assert c4_view_fingerprint(view) == c4_view_fingerprint(view)
    changed = analyze_objects([
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
    ])
    assert changed.snapshot is not None
    assert c4_view_fingerprint(
        project_c4(changed.snapshot, level="system-context", scope_id="SYS-1")
    ) != c4_view_fingerprint(view)
