from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.migrations.sphinx_needs import (
    SphinxNeedsMigrationError,
    build_migration_plan,
    load_needs_json,
    select_version,
    write_migration_plan,
)


def _document() -> dict[str, object]:
    return {
        "project": "Legacy engineering docs",
        "current_version": "2.0",
        "versions": {
            "1.0": {"needs": {}},
            "2.0": {
                "needs_schema": {
                    "properties": {
                        "links": {"field_type": "links"},
                        "tests": {"field_type": "links"},
                        "links_back": {"field_type": "backlinks"},
                    }
                },
                "needs": {
                    "REQ_001": {
                        "id": "REQ_001",
                        "type": "req",
                        "title": "Authenticate users",
                        "content": "The system shall authenticate users.",
                        "status": "open",
                        "tags": ["security", "auth"],
                        "links": ["REQ_002", "EXT_900"],
                        "tests": ["TC_001", "TC_002[status=='passed']"],
                        "links_back": ["REQ_000"],
                        "owner": "platform-team",
                    },
                    "REQ_002": {
                        "type": "req",
                        "title": "Protect sessions",
                        "content": "Protect active sessions.",
                        "status": None,
                        "tags": "security;session",
                        "links": [],
                        "tests": [],
                    },
                    "TC_001": {
                        "type": "test",
                        "title": "Authentication test",
                        "content": "Exercise login.",
                        "status": "passed",
                        "tags": [],
                        "links": [],
                        "tests": [],
                    },
                },
            },
        },
    }


def test_select_version_uses_current_version_then_explicit_override() -> None:
    selected, version = select_version(_document())
    assert selected == "2.0"
    assert "needs" in version

    selected, _ = select_version(_document(), "1.0")
    assert selected == "1.0"


def test_select_version_falls_back_only_when_unambiguous() -> None:
    document = {"versions": {"only": {"needs": {}}}}
    assert select_version(document)[0] == "only"

    ambiguous = {"versions": {"a": {"needs": {}}, "b": {"needs": {}}}}
    with pytest.raises(SphinxNeedsMigrationError, match="ambiguous"):
        select_version(ambiguous)


def test_migration_plan_requires_explicit_type_and_relation_semantics() -> None:
    plan = build_migration_plan(_document())

    assert plan.source_project == "Legacy engineering docs"
    assert plan.source_version == "2.0"
    assert [candidate.source_id for candidate in plan.candidates] == [
        "REQ_001",
        "REQ_002",
        "TC_001",
    ]
    req = plan.candidates[0]
    assert req.target_type is None
    assert req.relations == ()
    assert req.unmapped_links["links"] == ("REQ_002", "EXT_900")
    assert req.unmapped_links["tests"] == ("TC_001", "TC_002[status=='passed']")
    assert req.extras["owner"] == "platform-team"
    assert "links_back" not in req.extras
    assert {issue.code for issue in plan.issues} == {
        "TYPE_UNMAPPED",
        "LINK_FIELD_UNMAPPED",
    }


def test_migration_plan_maps_only_explicit_types_and_link_fields() -> None:
    plan = build_migration_plan(
        _document(),
        type_map={"req": "system-requirement", "test": "test-case"},
        relation_map={"links": "derives-from", "tests": "verified-by"},
    )

    req = plan.candidates[0]
    assert req.target_type == "system-requirement"
    assert [(relation.relation, relation.target) for relation in req.relations] == [
        ("derives-from", "EXT_900"),
        ("derives-from", "REQ_002"),
        ("verified-by", "TC_001"),
    ]
    assert req.unmapped_links == {"tests": ("TC_002[status=='passed']",)}
    issue_codes = [issue.code for issue in plan.issues]
    assert issue_codes == ["EXTERNAL_LINK_TARGET", "CONDITIONAL_LINK"]


def test_object_keyed_need_id_is_recovered_from_dictionary_key() -> None:
    document = {
        "current_version": "1",
        "versions": {
            "1": {
                "needs": {
                    "REQ_001": {
                        "type": "req",
                        "title": "Recovered ID",
                    }
                }
            }
        },
    }
    plan = build_migration_plan(document, type_map={"req": "system-requirement"})
    assert plan.candidates[0].source_id == "REQ_001"


def test_array_wire_shape_is_supported_and_duplicate_ids_fail_closed() -> None:
    document = {
        "current_version": "1",
        "versions": {
            "1": {
                "needs": [
                    {"id": "A", "type": "req", "title": "A"},
                    {"id": "B", "type": "req", "title": "B"},
                ]
            }
        },
    }
    plan = build_migration_plan(document, type_map={"req": "system-requirement"})
    assert [candidate.source_id for candidate in plan.candidates] == ["A", "B"]

    duplicate = {
        "current_version": "1",
        "versions": {
            "1": {
                "needs": [
                    {"id": "A", "type": "req", "title": "A"},
                    {"id": "A", "type": "req", "title": "Again"},
                ]
            }
        },
    }
    with pytest.raises(SphinxNeedsMigrationError, match="duplicate need IDs"):
        build_migration_plan(duplicate)


def test_plan_writes_deterministic_machine_readable_json(tmp_path: Path) -> None:
    plan = build_migration_plan(
        _document(),
        type_map={"req": "system-requirement", "test": "test-case"},
        relation_map={"tests": "verified-by"},
    )
    output = tmp_path / "migration" / "plan.json"
    write_migration_plan(output, plan)
    first = output.read_bytes()
    write_migration_plan(output, plan)
    assert output.read_bytes() == first
    assert first.endswith(b"\n")


def test_load_needs_json_rejects_malformed_input(tmp_path: Path) -> None:
    path = tmp_path / "needs.json"
    path.write_text("[", encoding="utf-8")
    with pytest.raises(SphinxNeedsMigrationError, match="cannot read"):
        load_needs_json(path)
