from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import MappingProxyType

from quarto_needs.cli_entry import main
from quarto_needs.config import Gates, NeedsConfig
from quarto_needs.migrations.apply_plan import (
    build_migration_update_plan,
    build_sphinx_apply_plan,
)
from quarto_needs.migrations.sphinx_needs import build_migration_plan
from quarto_needs.parser import parse_qmd_text_declarations
from quarto_needs.snapshot import (
    AnalysisSnapshot,
    LocationRecord,
    ObjectRecord,
    RelationRecord,
)


def _config() -> NeedsConfig:
    return NeedsConfig(
        profile="strict",
        required_attributes=MappingProxyType(
            {"system-requirement": (), "test-case": ()}
        ),
        relation_policies=MappingProxyType({}),
        test_types=("test-case",),
        risk_types=("risk",),
        ineffective_endpoint_statuses=(
            "disapproved",
            "rejected",
            "failed",
            "deprecated",
        ),
        successful_test_statuses=("passed",),
        expiry_attribute="expires",
        rule_settings=MappingProxyType({}),
        named_query_sources=MappingProxyType({}),
        gates=Gates(),
        present=True,
        allowed_statuses=MappingProxyType(
            {
                "system-requirement": ("approved", "draft"),
                "test-case": ("passed", "failed"),
            }
        ),
    )


def _migration():
    document = {
        "project": "Legacy engineering docs",
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs_schema": {
                    "properties": {
                        "tests": {"field_type": "links"},
                    }
                },
                "needs": {
                    "REQ_001": {
                        "type": "req",
                        "title": "Authenticate users",
                        "content": "The system shall authenticate users.",
                        "status": "approved",
                        "tags": ["security"],
                        "tests": ["TC_001"],
                    },
                    "TC_001": {
                        "type": "test",
                        "title": "Authentication test",
                        "content": "Exercise authentication.",
                        "status": "passed",
                        "tags": [],
                        "tests": [],
                    },
                },
            }
        },
    }
    return build_migration_plan(
        document,
        type_map={"req": "system-requirement", "test": "test-case"},
        relation_map={"tests": "verified-by"},
    )


def _record(
    identifier: str,
    *,
    type: str,
    title: str,
    status: str,
    body: str,
    tags: tuple[str, ...] = (),
    source_tool: str | None = "sphinx-needs",
    source_id: str | None = None,
    source_project: str | None = "Legacy engineering docs",
    file: str = "requirements.qmd",
    line: int = 1,
) -> ObjectRecord:
    attributes: dict[str, object] = {}
    if tags:
        attributes["tags"] = ";".join(tags)
    if source_tool is not None:
        attributes["source-tool"] = source_tool
    if source_id is not None:
        attributes["source-id"] = source_id
    if source_project is not None:
        attributes["source-project"] = source_project
    return ObjectRecord(
        id=identifier,
        type=type,
        title=title,
        status=status,
        body=body,
        rationale="",
        attributes=attributes,
        locations=(LocationRecord(file=file, line=line),),
    )


def _verified_by_relation() -> RelationRecord:
    return RelationRecord(
        source="REQ_001",
        authored_name="verified-by",
        catalog_name="verified-by",
        v1_name="verified-by",
        target="TC_001",
        semantic_family="verification",
        source_role="requirement",
        target_role="test",
        impact_direction="source_to_target",
        attributes={},
        provenance=(),
    )


def _snapshot(
    *objects: ObjectRecord, relations: tuple[RelationRecord, ...] = ()
) -> AnalysisSnapshot:
    return AnalysisSnapshot(
        objects=tuple(objects),
        relations=relations,
        findings=(),
        metrics={},
        objects_by_id={item.id: item for item in objects},
        outgoing=(
            {"REQ_001": relations} if relations else {}
        ),
        incoming={},
        generator_name="quarto-needs",
        generator_version="0.1.0",
        relation_catalog_version="6",
        semantic_graph_fingerprint="graph-current",
    )


def _authored_pair() -> tuple[ObjectRecord, ObjectRecord]:
    return (
        _record(
            "REQ_001",
            type="system-requirement",
            title="Authenticate users",
            status="approved",
            body="The system shall authenticate users.",
            tags=("security",),
            source_id="REQ_001",
        ),
        _record(
            "TC_001",
            type="test-case",
            title="Authentication test",
            status="passed",
            body="Exercise authentication.",
            source_id="TC_001",
        ),
    )


def test_create_previews_carry_the_source_marker() -> None:
    plan = build_sphinx_apply_plan(
        _migration(),
        _snapshot(),
        _config(),
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )

    preview = plan.items[0].content_preview
    assert preview is not None
    assert 'source-tool="sphinx-needs"' in preview
    assert 'source-project="Legacy engineering docs"' in preview
    assert 'source-id="REQ_001"' in preview

    declaration = parse_qmd_text_declarations(preview, "generated.qmd").declarations[0]
    assert declaration.attributes["source-tool"] == "sphinx-needs"
    assert declaration.attributes["source-project"] == "Legacy engineering docs"
    assert declaration.attributes["source-id"] == "REQ_001"


def test_marker_matching_reports_unchanged_objects(tmp_path: Path) -> None:
    (tmp_path / "requirements.qmd").write_text(":::\n:::\n", encoding="utf-8")

    plan = build_migration_update_plan(
        _migration(),
        _snapshot(*_authored_pair(), relations=(_verified_by_relation(),)),
        _config(),
        root=tmp_path,
        destinations={},
    )

    assert plan.applicable is True
    assert [item.status for item in plan.items] == ["no-change", "no-change"]
    req = plan.items[0]
    assert req.matched_by == "source-marker"
    assert req.changes == ()
    assert req.destination_file == "requirements.qmd"
    assert req.current_file_digest == hashlib.sha256(
        (tmp_path / "requirements.qmd").read_bytes()
    ).hexdigest()
    assert plan.to_dict()["schema"] == "migration-update-plan-v1"


def test_changed_source_classifies_a_ready_update_with_its_changes(
    tmp_path: Path,
) -> None:
    (tmp_path / "requirements.qmd").write_text(":::\n:::\n", encoding="utf-8")
    outdated = _record(
        "REQ_001",
        type="system-requirement",
        title="Authenticate users (old)",
        status="approved",
        body="An older body.",
        tags=("security",),
        source_id="REQ_001",
    )
    _, test_case = _authored_pair()

    plan = build_migration_update_plan(
        _migration(),
        _snapshot(outdated, test_case, relations=(_verified_by_relation(),)),
        _config(),
        root=tmp_path,
        destinations={},
    )

    req = plan.items[0]
    assert req.status == "ready-update"
    assert req.matched_by == "source-marker"
    assert req.changes == ("title", "body")
    assert plan.applicable is True


def test_canonical_id_without_a_marker_is_blocked_never_an_implicit_update(
    tmp_path: Path,
) -> None:
    legacy = _record(
        "REQ_001",
        type="system-requirement",
        title="Authenticate users",
        status="approved",
        body="The system shall authenticate users.",
        tags=("security",),
        source_tool=None,
        source_id=None,
        source_project=None,
    )

    plan = build_migration_update_plan(
        _migration(),
        _snapshot(legacy),
        _config(),
        root=tmp_path,
        destinations={},
    )

    req = next(item for item in plan.items if item.source_id == "REQ_001")
    assert req.status == "blocked"
    assert req.matched_by is None
    assert any("without a source marker" in reason for reason in req.reasons)
    assert plan.applicable is False


def test_marker_identity_under_a_different_canonical_id_is_blocked(
    tmp_path: Path,
) -> None:
    renamed = _record(
        "RENAMED",
        type="system-requirement",
        title="Authenticate users",
        status="approved",
        body="The system shall authenticate users.",
        tags=("security",),
        source_id="REQ_001",
    )

    plan = build_migration_update_plan(
        _migration(),
        _snapshot(renamed),
        _config(),
        root=tmp_path,
        destinations={},
    )

    req = next(item for item in plan.items if item.source_id == "REQ_001")
    assert req.status == "blocked"
    assert any("renames are explicit" in reason for reason in req.reasons)


def test_duplicate_source_markers_are_blocked(tmp_path: Path) -> None:
    first, second = _authored_pair()
    duplicate = _record(
        "REQ_001-B",
        type="system-requirement",
        title="Authenticate users",
        status="approved",
        body="The system shall authenticate users.",
        tags=("security",),
        source_id="REQ_001",
    )

    plan = build_migration_update_plan(
        _migration(),
        _snapshot(first, duplicate, second, relations=(_verified_by_relation(),)),
        _config(),
        root=tmp_path,
        destinations={},
    )

    req = next(item for item in plan.items if item.source_id == "REQ_001")
    assert req.status == "blocked"
    assert any("multiple local objects" in reason for reason in req.reasons)


def test_new_candidates_are_ready_create_with_the_marker_preview(
    tmp_path: Path,
) -> None:
    plan = build_migration_update_plan(
        _migration(),
        _snapshot(),
        _config(),
        root=tmp_path,
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )

    assert [item.status for item in plan.items] == ["ready-create", "ready-create"]
    assert plan.applicable is True
    preview = plan.items[0].content_preview
    assert preview is not None and 'source-id="REQ_001"' in preview


def test_unrenderable_provenance_blocks_the_item(tmp_path: Path) -> None:
    plan = build_migration_update_plan(
        _migration(),
        _snapshot(),
        _config(),
        root=tmp_path,
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )
    assert plan.applicable is True

    hostile = build_migration_plan(
        {
            "project": 'Legacy "quoted" project',
            "current_version": "1.0",
            "versions": {
                "1.0": {
                    "needs_schema": {"properties": {"tests": {"field_type": "links"}}},
                    "needs": {
                        "REQ_001": {
                            "type": "req",
                            "title": "Authenticate users",
                            "content": "The system shall authenticate users.",
                            "status": "approved",
                            "tags": [],
                            "tests": [],
                        }
                    },
                }
            },
        },
        type_map={"req": "system-requirement"},
        relation_map={"tests": "verified-by"},
    )
    hostile_plan = build_migration_update_plan(
        hostile,
        _snapshot(),
        _config(),
        root=tmp_path,
        destinations={"REQ_001": "requirements/authentication.qmd"},
    )

    assert hostile_plan.items[0].status == "blocked"
    assert hostile_plan.items[0].content_preview is None


def test_cli_update_plan_writes_the_artifact_and_refuses_write(
    tmp_path: Path, capsys
) -> None:
    payload = _migration_payload()
    (tmp_path / "needs.json").write_text(json.dumps(payload), encoding="utf-8")

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "sphinx-needs",
            "needs.json",
            "--type-map",
            "req=system-requirement",
            "--type-map",
            "test=test-case",
            "--relation-map",
            "tests=verified-by",
            "--update-plan",
            "--format",
            "json",
        ]
    )

    assert exit_code == 1  # no destinations: creates are not applicable yet
    plan_path = tmp_path / ".quarto-needs" / "migrations" / "sphinx-needs-update-plan.json"
    assert plan_path.is_file()
    document = json.loads(plan_path.read_text(encoding="utf-8"))
    assert document["schema"] == "migration-update-plan-v1"
    assert {item["status"] for item in document["items"]} == {"review-required"}

    capsys.readouterr()
    refused = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "sphinx-needs",
            "needs.json",
            "--type-map",
            "req=system-requirement",
            "--type-map",
            "test=test-case",
            "--relation-map",
            "tests=verified-by",
            "--update-plan",
            "--apply-plan",
            "--write",
        ]
    )
    assert refused == 2
    assert "--apply-update" in capsys.readouterr().err


def _migration_payload() -> dict[str, object]:
    return {
        "project": "Legacy",
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs_schema": {
                    "properties": {
                        "tests": {"field_type": "links"},
                        "tests_back": {"field_type": "backlinks"},
                    }
                },
                "needs": {
                    "REQ_001": {
                        "type": "req",
                        "title": "Authenticate users",
                        "content": "The system shall authenticate users.",
                        "status": "approved",
                        "tags": ["security"],
                        "tests": ["TC_001"],
                    },
                    "TC_001": {
                        "type": "test",
                        "title": "Authentication test",
                        "content": "Exercise authentication.",
                        "status": "passed",
                        "tags": [],
                        "tests": [],
                    },
                },
            }
        },
    }
