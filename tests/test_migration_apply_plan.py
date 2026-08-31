from __future__ import annotations

from types import MappingProxyType

from quarto_needs.config import Gates, NeedsConfig
from quarto_needs.migrations.apply_plan import build_sphinx_apply_plan
from quarto_needs.migrations.sphinx_needs import build_migration_plan
from quarto_needs.parser import parse_qmd_text_declarations
from quarto_needs.snapshot import AnalysisSnapshot, ObjectRecord


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


def _snapshot(*objects: ObjectRecord) -> AnalysisSnapshot:
    by_id = {item.id: item for item in objects}
    return AnalysisSnapshot(
        objects=tuple(objects),
        relations=(),
        findings=(),
        metrics={},
        objects_by_id=by_id,
        outgoing={},
        incoming={},
        generator_name="quarto-needs",
        generator_version="0.1.0",
        relation_catalog_version="1",
        semantic_graph_fingerprint="graph-current",
    )


def _migration(
    *, status: str = "approved", target: str = "TC_001", content: str = "The system shall authenticate users."
):
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
                        "content": content,
                        "status": status,
                        "tags": ["security"],
                        "tests": [target],
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


def test_apply_plan_is_ready_only_with_explicit_destinations_and_valid_semantics() -> None:
    snapshot = _snapshot()
    plan = build_sphinx_apply_plan(
        _migration(),
        snapshot,
        _config(),
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )

    assert plan.ready is True
    assert [item.status for item in plan.items] == ["ready-create", "ready-create"]
    req = plan.items[0]
    assert req.canonical_id == "REQ_001"
    assert req.destination_file == "requirements/authentication.qmd"
    assert req.relations == (
        {
            "relation": "verified-by",
            "target": "TC_001",
            "sourceField": "tests",
        },
    )
    assert req.provenance == {
        "tool": "Sphinx-Needs",
        "project": "Legacy engineering docs",
        "version": "1.0",
        "sourceId": "REQ_001",
    }
    assert plan.semantic_graph_fingerprint == "graph-current"
    assert snapshot.objects == ()


def test_missing_destination_requires_review_but_does_not_guess_file_placement() -> None:
    plan = build_sphinx_apply_plan(
        _migration(),
        _snapshot(),
        _config(),
        destinations={"TC_001": "verification/authentication.qmd"},
    )

    req = plan.items[0]
    assert req.status == "review-required"
    assert req.destination_file is None
    assert req.reasons == ("destination file requires explicit review",)
    assert plan.ready is False


def test_existing_canonical_id_blocks_create_instead_of_becoming_implicit_update() -> None:
    local = ObjectRecord(
        id="REQ_001",
        type="system-requirement",
        title="Existing requirement",
        status="approved",
        body="Existing body",
        rationale="",
        attributes={},
        locations=(),
    )
    plan = build_sphinx_apply_plan(
        _migration(),
        _snapshot(local),
        _config(),
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )

    req = plan.items[0]
    assert req.status == "blocked"
    assert any("already exists" in reason for reason in req.reasons)


def test_status_not_allowed_by_project_configuration_blocks_candidate() -> None:
    plan = build_sphinx_apply_plan(
        _migration(status="open"),
        _snapshot(),
        _config(),
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )

    req = plan.items[0]
    assert req.status == "blocked"
    assert any("is not allowed" in reason for reason in req.reasons)


def test_unresolved_external_relation_target_blocks_apply_plan() -> None:
    migration = _migration(target="EXT_900")
    plan = build_sphinx_apply_plan(
        migration,
        _snapshot(),
        _config(),
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )

    req = plan.items[0]
    assert req.status == "blocked"
    assert any("EXTERNAL_LINK_TARGET" in reason for reason in req.reasons)
    assert any("does not resolve" in reason for reason in req.reasons)


def test_ready_item_carries_a_content_preview_that_round_trips_through_the_parser() -> None:
    plan = build_sphinx_apply_plan(
        _migration(),
        _snapshot(),
        _config(),
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )

    req = plan.items[0]
    assert req.status == "ready-create"
    assert req.content_preview is not None

    batch = parse_qmd_text_declarations(req.content_preview, "generated.qmd")
    assert batch.findings == ()
    declaration = batch.declarations[0]
    assert declaration.id == "REQ_001"
    assert declaration.type == "system-requirement"
    assert declaration.status == "approved"
    assert declaration.title == "Authenticate users"
    assert declaration.body == "The system shall authenticate users."
    assert [(r.authored_name, r.target) for r in declaration.relations] == [
        ("verified-by", "TC_001"),
    ]


def test_unrenderable_source_content_blocks_the_item_and_omits_content_preview() -> None:
    plan = build_sphinx_apply_plan(
        _migration(content="line one\n:::\nline three"),
        _snapshot(),
        _config(),
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )

    req = plan.items[0]
    assert req.status == "blocked"
    assert req.content_preview is None
    assert any("prematurely close" in reason for reason in req.reasons)
