"""Applying an accepted import plan to authored files.

This is the one write path. The tests exercise it end to end through the
real pipeline — observation, reconciliation, directives, plan, apply —
and pin the safety contracts inherited from the migration apply:
all-or-nothing preflight against a fresh scan, post-write
self-verification with rollback, and idempotence through refusal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.import_apply import ImportApplyError, apply_import_plan
from quarto_needs.oslc_import_plan import ImportDirective, build_oslc_import_plan
from quarto_needs.oslc_reconcile import (
    ExternalRequirementObservation,
    reconcile_external_requirements,
)
from quarto_needs.oslc_rm import ExternalResourceIdentity

PROJECT = (
    '::: {.need #REQ-1 type="system-requirement" status="approved" priority="high"}\n'
    "verified-by: TC-1\n"
    "\n## Authenticate\n"
    "The service shall authenticate users.\n"
    ":::\n"
    "\n"
    '::: {.need #TC-1 type="test-case" status="passed"}\n'
    "\n## Login test\n"
    "Signs a user in.\n"
    ":::\n"
)

URI = "https://api.github.com/repos/acme/widgets/issues/2067"


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(PROJECT, encoding="utf-8")


def snapshot_of(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None
    return result.snapshot


def observation(title: str = "Documentation train 2025-2026", description: str = "") -> ExternalRequirementObservation:
    return ExternalRequirementObservation(
        identity=ExternalResourceIdentity(
            resource_uri=URI,
            service_provider_uri="https://api.github.com/repos/acme/widgets",
            digest="sha256:" + "a" * 64,
            fetched_at="2026-08-31T12:00:00Z",
        ),
        title=title,
        description=description,
        external_identifier="2067",
    )


def build_plan(root: Path, snapshot, observation, directives, binding=None) -> object:
    reconciliation = reconcile_external_requirements(
        snapshot, (observation,), bindings=binding or {}
    )
    return build_oslc_import_plan(snapshot, (observation,), reconciliation, directives=directives)


def test_ready_create_writes_a_new_block_and_the_graph_gains_the_object(tmp_path: Path) -> None:
    write_project(tmp_path)
    snapshot = snapshot_of(tmp_path)
    obs = observation()
    plan = build_plan(
        tmp_path,
        snapshot,
        obs,
        {URI: ImportDirective(
            action="create",
            canonical_id="REQ-2067",
            canonical_type="documentation-requirement",
            canonical_status="draft",
            target_path="docs/extra.qmd",
        )},
    )

    result = apply_import_plan(tmp_path, plan, snapshot_of(tmp_path), config=load_config(tmp_path))

    assert len(result.applied) == 1
    assert result.applied[0].canonical_id == "REQ-2067"
    assert result.applied[0].file == "docs/extra.qmd"
    assert result.skipped == ()
    text = (tmp_path / "docs" / "extra.qmd").read_text(encoding="utf-8")
    assert '::: {.need #REQ-2067 type="documentation-requirement" status="draft"}' in text
    assert "## Documentation train 2025-2026" in text
    fresh = snapshot_of(tmp_path)
    assert "REQ-2067" in fresh.objects_by_id
    assert fresh.objects_by_id["REQ-2067"].title == "Documentation train 2025-2026"


def test_ready_create_can_append_to_an_existing_authored_file(tmp_path: Path) -> None:
    write_project(tmp_path)
    snapshot = snapshot_of(tmp_path)
    obs = observation()
    plan = build_plan(
        tmp_path,
        snapshot,
        obs,
        {URI: ImportDirective(
            action="create",
            canonical_id="REQ-2067",
            canonical_type="documentation-requirement",
            canonical_status="draft",
            target_path="needs.qmd",
        )},
    )

    apply_import_plan(tmp_path, plan, snapshot_of(tmp_path), config=load_config(tmp_path))

    fresh = snapshot_of(tmp_path)
    assert {"REQ-1", "TC-1", "REQ-2067"} <= set(fresh.objects_by_id)


def test_second_apply_of_the_same_plan_refuses_idempotently(tmp_path: Path) -> None:
    write_project(tmp_path)
    snapshot = snapshot_of(tmp_path)
    obs = observation()
    plan = build_plan(
        tmp_path,
        snapshot,
        obs,
        {URI: ImportDirective(
            action="create",
            canonical_id="REQ-2067",
            canonical_type="documentation-requirement",
            canonical_status="draft",
            target_path="docs/extra.qmd",
        )},
    )
    apply_import_plan(tmp_path, plan, snapshot_of(tmp_path), config=load_config(tmp_path))
    file_after_first = (tmp_path / "docs" / "extra.qmd").read_text(encoding="utf-8")

    with pytest.raises(ImportApplyError, match="already exists"):
        apply_import_plan(tmp_path, plan, snapshot_of(tmp_path), config=load_config(tmp_path))

    assert (tmp_path / "docs" / "extra.qmd").read_text(encoding="utf-8") == file_after_first


def test_ready_update_rewrites_the_block_in_place(tmp_path: Path) -> None:
    write_project(tmp_path)
    snapshot = snapshot_of(tmp_path)
    obs = observation(title="Authenticate users at the perimeter")
    plan = build_plan(
        tmp_path,
        snapshot,
        obs,
        {URI: ImportDirective(action="update", target_path="needs.qmd")},
        binding={URI: "REQ-1"},
    )

    result = apply_import_plan(tmp_path, plan, snapshot_of(tmp_path), config=load_config(tmp_path))

    assert result.applied[0].action == "ready-update"
    text = (tmp_path / "needs.qmd").read_text(encoding="utf-8")
    assert "## Authenticate users at the perimeter" in text
    assert 'priority="high"' in text  # preamble metadata survives the rewrite
    assert "verified-by: TC-1" in text
    assert "## Login test" in text  # the neighbouring block is untouched
    fresh = snapshot_of(tmp_path)
    assert fresh.objects_by_id["REQ-1"].title == "Authenticate users at the perimeter"


def test_stale_plan_from_values_refuse_the_whole_apply(tmp_path: Path) -> None:
    write_project(tmp_path)
    snapshot = snapshot_of(tmp_path)
    obs = observation(title="Authenticate users at the perimeter")
    plan = build_plan(
        tmp_path,
        snapshot,
        obs,
        {URI: ImportDirective(action="update", target_path="needs.qmd")},
        binding={URI: "REQ-1"},
    )
    stale_guard = (tmp_path / "needs.qmd").read_text(encoding="utf-8")
    # Someone edits the authored title after the plan was built.
    (tmp_path / "needs.qmd").write_text(
        stale_guard.replace("## Authenticate", "## Authenticate (edited)"),
        encoding="utf-8",
    )

    with pytest.raises(ImportApplyError, match="changed since the plan was built"):
        apply_import_plan(tmp_path, plan, snapshot_of(tmp_path), config=load_config(tmp_path))

    assert (tmp_path / "needs.qmd").read_text(encoding="utf-8") == stale_guard.replace(
        "## Authenticate", "## Authenticate (edited)"
    )


def test_update_target_path_mismatch_refuses(tmp_path: Path) -> None:
    write_project(tmp_path)
    snapshot = snapshot_of(tmp_path)
    obs = observation(title="Authenticate users at the perimeter")
    plan = build_plan(
        tmp_path,
        snapshot,
        obs,
        {URI: ImportDirective(action="update", target_path="docs/elsewhere.qmd")},
        binding={URI: "REQ-1"},
    )

    with pytest.raises(ImportApplyError, match="authored in"):
        apply_import_plan(tmp_path, plan, snapshot_of(tmp_path), config=load_config(tmp_path))


def test_non_applicable_dispositions_are_skipped_with_their_reason(tmp_path: Path) -> None:
    write_project(tmp_path)
    snapshot = snapshot_of(tmp_path)
    obs = observation()
    reconciliation = reconcile_external_requirements(
        snapshot, (obs,), bindings={URI: "REQ-1"}
    )
    plan = build_oslc_import_plan(
        snapshot,
        (obs,),
        reconciliation,
        directives={URI: ImportDirective(action="ignore")},
    )

    result = apply_import_plan(tmp_path, plan, snapshot_of(tmp_path), config=load_config(tmp_path))

    assert result.applied == ()
    assert len(result.skipped) == 1
    assert result.skipped[0].disposition == "ignored"
    assert result.written_files == ()


def test_empty_plan_refuses(tmp_path: Path) -> None:
    from quarto_needs.oslc_import_plan import OslcImportPlan

    write_project(tmp_path)
    empty = OslcImportPlan(semantic_graph_fingerprint="graph", items=())
    with pytest.raises(ImportApplyError, match="no items"):
        apply_import_plan(tmp_path, empty, snapshot_of(tmp_path), config=load_config(tmp_path))
