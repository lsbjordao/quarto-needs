from __future__ import annotations

from types import SimpleNamespace

from quarto_needs import fingerprints
from quarto_needs.config import embedded_defaults
from quarto_needs.snapshot import LocationRecord, ObjectRecord, RelationRecord


def make_object(**overrides: object) -> ObjectRecord:
    base = dict(
        id="REQ-1",
        type="functional-requirement",
        title="Authenticate",
        status="approved",
        body="The service shall authenticate.",
        rationale="Protect data.",
        attributes={"priority": "high", "tags": "security"},
        locations=(LocationRecord("a.qmd", 10, "REQ-1"),),
    )
    base.update(overrides)
    return ObjectRecord(**base)


def make_relation(**overrides: object) -> RelationRecord:
    base = dict(
        source="REQ-1",
        authored_name="verified-by",
        catalog_name="verified-by",
        v1_name="verified-by",
        target="TC-1",
        semantic_family="verification",
        source_role="requirement",
        target_role="test",
        impact_direction="source_to_target",
        attributes={},
        provenance=(LocationRecord("a.qmd", 12, None),),
    )
    base.update(overrides)
    return RelationRecord(**base)


def test_object_fingerprint_ignores_line_numbers_and_file() -> None:
    """Provenance is not authored semantics; moving a need must not modify it."""
    moved = make_object(locations=(LocationRecord("b.qmd", 900, "REQ-1"),))

    assert fingerprints.object_content_fingerprint(make_object()) == \
        fingerprints.object_content_fingerprint(moved)


def test_object_fingerprint_changes_with_every_authored_field() -> None:
    """Each field the spec names must actually participate."""
    original = fingerprints.object_content_fingerprint(make_object())
    for field, value in (
        ("id", "REQ-2"),
        ("type", "system-requirement"),
        ("title", "Other"),
        ("status", "draft"),
        ("body", "Different body."),
        ("rationale", "Different rationale."),
        ("attributes", {"priority": "low", "tags": "security"}),
        ("attributes", {"priority": "high", "tags": "authentication"}),
    ):
        assert fingerprints.object_content_fingerprint(make_object(**{field: value})) != original, field


def test_object_fingerprint_includes_priority_and_tags_as_named_fields() -> None:
    """The derived fields participate even when the attributes payload is equal."""
    record = make_object()
    common = {
        "id": record.id,
        "type": record.type,
        "title": record.title,
        "status": record.status,
        "body": record.body,
        "rationale": record.rationale,
        "attributes": record.attributes,
    }
    original = SimpleNamespace(**common, priority="high", tags=("security",))
    changed_priority = SimpleNamespace(**common, priority="low", tags=("security",))
    changed_tags = SimpleNamespace(**common, priority="high", tags=("authentication",))

    assert fingerprints.object_content_fingerprint(original) != \
        fingerprints.object_content_fingerprint(changed_priority)
    assert fingerprints.object_content_fingerprint(original) != \
        fingerprints.object_content_fingerprint(changed_tags)


def test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation() -> None:
    """REQ -verified-by-> TC and TC -verifies-> REQ are one semantic edge."""
    forward = make_relation()
    inverse = make_relation(
        source="TC-1",
        authored_name="verifies",
        catalog_name="verifies",
        v1_name="verifies",
        target="REQ-1",
        source_role="test",
        target_role="requirement",
        impact_direction="target_to_source",
    )

    assert fingerprints.relation_semantic_fingerprint(forward) == \
        fingerprints.relation_semantic_fingerprint(inverse)
    assert fingerprints.relation_authored_fingerprint(forward) != \
        fingerprints.relation_authored_fingerprint(inverse)


def test_semantic_relation_fingerprint_changes_with_family_and_endpoints() -> None:
    original = fingerprints.relation_semantic_fingerprint(make_relation())

    assert fingerprints.relation_semantic_fingerprint(make_relation(semantic_family="evidence")) != original
    assert fingerprints.relation_semantic_fingerprint(make_relation(target="TC-2")) != original
    assert fingerprints.relation_semantic_fingerprint(make_relation(source="REQ-2")) != original
    assert fingerprints.relation_semantic_fingerprint(make_relation(attributes={"note": "x"})) != original


def test_graph_fingerprint_is_order_independent_and_configuration_sensitive() -> None:
    """Reordering declarations is not a change; changing policy is."""
    objects = [make_object(), make_object(id="REQ-2")]
    relations = [make_relation(), make_relation(target="TC-2")]
    configuration = fingerprints.configuration_fingerprint(
        embedded_defaults(), relation_catalog_version="1"
    )

    forward = fingerprints.semantic_graph_fingerprint(objects, relations, configuration)
    reversed_order = fingerprints.semantic_graph_fingerprint(
        list(reversed(objects)), list(reversed(relations)), configuration
    )
    other_configuration = fingerprints.semantic_graph_fingerprint(
        objects, relations, configuration="different"
    )

    assert forward == reversed_order
    assert forward != other_configuration


def test_configuration_fingerprint_tracks_catalog_and_rule_set_versions() -> None:
    """A catalog-only change must be visible as a configuration change."""
    config = embedded_defaults()

    assert fingerprints.configuration_fingerprint(config, relation_catalog_version="1") != \
        fingerprints.configuration_fingerprint(config, relation_catalog_version="2")
