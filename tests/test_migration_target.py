from __future__ import annotations

from pathlib import Path

from quarto_needs.config import load_config
from quarto_needs.migrations.sphinx_needs import build_migration_plan
from quarto_needs.migrations.target import validate_plan_against_target


def _config(root: Path):
    (root / ".quarto-needs.toml").write_text(
        """
[types.system-requirement]
id-prefix = "SYS-"
allowed-statuses = ["draft", "approved"]
required-attributes = ["owner"]

[types.test-case]
id-prefix = "TC-"
allowed-statuses = ["draft", "passed"]

[relations."verified-by"]
allowed-source-types = ["system-requirement"]
allowed-target-types = ["test-case"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return load_config(root)


def _document():
    return {
        "current_version": "1",
        "versions": {
            "1": {
                "needs_schema": {
                    "properties": {"tests": {"field_type": "links"}}
                },
                "needs": {
                    "REQ_001": {
                        "type": "req",
                        "title": "Authenticate users",
                        "status": "open",
                        "tests": ["TEST_001"],
                        "owner": "platform-team",
                    },
                    "TEST_001": {
                        "type": "test",
                        "title": "Authentication test",
                        "status": "ok",
                        "tests": [],
                    },
                },
            }
        },
    }


def _plan():
    return build_migration_plan(
        _document(),
        type_map={"req": "system-requirement", "test": "test-case"},
        relation_map={"tests": "verified-by"},
    )


def test_target_validation_becomes_ready_only_after_explicit_id_and_status_mapping(tmp_path: Path) -> None:
    result = validate_plan_against_target(
        _plan(),
        _config(tmp_path),
        id_map={"REQ_001": "SYS-001", "TEST_001": "TC-001"},
        status_map={"open": "approved", "ok": "passed"},
    )

    assert result.ready is True
    assert result.issues == ()
    requirement = result.candidates[0]
    assert requirement.target_id == "SYS-001"
    assert requirement.target_type == "system-requirement"
    assert requirement.status == "approved"
    assert requirement.attributes == {"owner": "platform-team"}
    assert [(relation.relation, relation.target) for relation in requirement.relations] == [
        ("verified-by", "TC-001")
    ]


def test_target_validation_reports_prefix_status_and_required_attribute_failures(tmp_path: Path) -> None:
    document = _document()
    document["versions"]["1"]["needs"]["REQ_001"].pop("owner")
    plan = build_migration_plan(
        document,
        type_map={"req": "system-requirement", "test": "test-case"},
        relation_map={"tests": "verified-by"},
    )

    result = validate_plan_against_target(plan, _config(tmp_path))
    codes = {issue.code for issue in result.issues}
    assert codes == {
        "TARGET_ATTRIBUTE_REQUIRED",
        "TARGET_ID_PREFIX",
        "TARGET_STATUS_INVALID",
    }
    assert result.ready is False


def test_target_validation_rejects_unknown_type_relation_and_external_target(tmp_path: Path) -> None:
    config = _config(tmp_path)
    unknown_type = build_migration_plan(
        _document(),
        type_map={"req": "not-configured", "test": "test-case"},
        relation_map={"tests": "not-a-relation"},
    )
    result = validate_plan_against_target(
        unknown_type,
        config,
        id_map={"REQ_001": "SYS-001", "TEST_001": "TC-001"},
        status_map={"open": "approved", "ok": "passed"},
    )
    codes = {issue.code for issue in result.issues}
    assert "TARGET_TYPE_UNKNOWN" in codes

    external_doc = _document()
    external_doc["versions"]["1"]["needs"]["REQ_001"]["tests"] = ["MISSING"]
    external_plan = build_migration_plan(
        external_doc,
        type_map={"req": "system-requirement", "test": "test-case"},
        relation_map={"tests": "verified-by"},
    )
    result = validate_plan_against_target(
        external_plan,
        config,
        id_map={"REQ_001": "SYS-001", "TEST_001": "TC-001"},
        status_map={"open": "approved", "ok": "passed"},
    )
    codes = {issue.code for issue in result.issues}
    assert "EXTERNAL_LINK_TARGET" in codes
    assert "TARGET_RELATION_EXTERNAL" in codes


def test_target_validation_rejects_id_and_attribute_mapping_collisions(tmp_path: Path) -> None:
    document = _document()
    document["versions"]["1"]["needs"]["REQ_001"]["team"] = "other-team"
    plan = build_migration_plan(
        document,
        type_map={"req": "system-requirement", "test": "test-case"},
        relation_map={"tests": "verified-by"},
    )
    result = validate_plan_against_target(
        plan,
        _config(tmp_path),
        id_map={"REQ_001": "SYS-001", "TEST_001": "SYS-001"},
        status_map={"open": "approved", "ok": "passed"},
        attribute_map={"team": "owner"},
    )
    codes = {issue.code for issue in result.issues}
    assert "TARGET_ID_COLLISION" in codes
    assert "TARGET_ATTRIBUTE_COLLISION" in codes


def test_relation_endpoint_policy_is_checked_against_mapped_target_types(tmp_path: Path) -> None:
    plan = build_migration_plan(
        _document(),
        type_map={"req": "test-case", "test": "system-requirement"},
        relation_map={"tests": "verified-by"},
    )
    result = validate_plan_against_target(
        plan,
        _config(tmp_path),
        id_map={"REQ_001": "TC-001", "TEST_001": "SYS-001"},
        status_map={"open": "passed", "ok": "approved"},
    )
    codes = {issue.code for issue in result.issues}
    assert "TARGET_RELATION_SOURCE_TYPE" in codes
    assert "TARGET_RELATION_TARGET_TYPE" in codes
