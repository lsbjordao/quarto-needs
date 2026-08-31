from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.diagnostics import Finding
from quarto_needs.migrations.apply_plan import build_sphinx_apply_plan
from quarto_needs.migrations.apply_write import MigrationApplyError, apply_migration_plan
from quarto_needs.migrations.sphinx_needs import build_migration_plan


def _plan_for(tmp_path: Path, *, destinations: dict[str, str]):
    document = {
        "project": "Legacy",
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
    migration = build_migration_plan(
        document,
        type_map={"req": "system-requirement", "test": "test-case"},
        relation_map={"tests": "verified-by"},
    )
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    apply_plan = build_sphinx_apply_plan(
        migration, result.snapshot, config, destinations=destinations
    )
    return apply_plan, config


def test_apply_writes_every_ready_item_and_the_project_rescans_clean(tmp_path: Path) -> None:
    plan, config = _plan_for(
        tmp_path,
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )
    assert plan.ready is True

    result = apply_migration_plan(tmp_path, plan, config)

    assert result.written == (
        "requirements/authentication.qmd",
        "verification/authentication.qmd",
    )
    req_path = tmp_path / "requirements" / "authentication.qmd"
    assert req_path.is_file()
    assert "::: {.need #REQ_001" in req_path.read_text(encoding="utf-8")

    rescanned = analyze_project(tmp_path, config=config)
    assert rescanned.snapshot is not None
    assert {"REQ_001", "TC_001"} <= set(rescanned.snapshot.objects_by_id)
    assert not any(f.severity == "error" for f in rescanned.findings)


def test_apply_refuses_when_plan_is_not_fully_ready(tmp_path: Path) -> None:
    plan, config = _plan_for(
        tmp_path, destinations={"TC_001": "verification/authentication.qmd"}
    )
    assert plan.ready is False

    with pytest.raises(MigrationApplyError, match="not fully ready-create"):
        apply_migration_plan(tmp_path, plan, config)

    assert list(tmp_path.rglob("*.qmd")) == []


def test_apply_refuses_to_overwrite_an_existing_destination_file(tmp_path: Path) -> None:
    plan, config = _plan_for(
        tmp_path,
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )
    existing = tmp_path / "requirements" / "authentication.qmd"
    existing.parent.mkdir(parents=True)
    existing.write_text("pre-existing content\n", encoding="utf-8")

    with pytest.raises(MigrationApplyError, match="already exists"):
        apply_migration_plan(tmp_path, plan, config)

    assert existing.read_text(encoding="utf-8") == "pre-existing content\n"
    assert not (tmp_path / "verification" / "authentication.qmd").exists()


def test_apply_rolls_back_earlier_writes_when_a_later_write_fails(tmp_path: Path) -> None:
    plan, config = _plan_for(
        tmp_path,
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )
    # REQ_001 sorts before TC_001, so it is written first. Occupying
    # "verification" with a plain file makes the second write's
    # mkdir(parents=True) fail with a real OS error.
    blocker = tmp_path / "verification"
    blocker.write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(OSError):
        apply_migration_plan(tmp_path, plan, config)

    assert not (tmp_path / "requirements" / "authentication.qmd").exists()
    assert blocker.read_text(encoding="utf-8") == "not a directory\n"


def test_apply_rolls_back_when_post_write_scan_check_finds_a_new_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from quarto_needs.migrations import apply_write

    plan, config = _plan_for(
        tmp_path,
        destinations={
            "REQ_001": "requirements/authentication.qmd",
            "TC_001": "verification/authentication.qmd",
        },
    )

    real_analyze_project = apply_write.analyze_project

    def _poisoned(root, *, config):
        result = real_analyze_project(root, config=config)
        poisoned_findings = (
            *result.findings,
            Finding("REQ004", "error", "synthetic duplicate for the test", "REQ_001", None),
        )
        return result.__class__(result.declarations, poisoned_findings, result.snapshot)

    monkeypatch.setattr(apply_write, "analyze_project", _poisoned)

    with pytest.raises(MigrationApplyError, match="post-write"):
        apply_migration_plan(tmp_path, plan, config)

    assert not (tmp_path / "requirements" / "authentication.qmd").exists()
    assert not (tmp_path / "verification" / "authentication.qmd").exists()


def test_apply_is_idempotent_on_rerun_because_ids_now_exist(tmp_path: Path) -> None:
    destinations = {
        "REQ_001": "requirements/authentication.qmd",
        "TC_001": "verification/authentication.qmd",
    }
    plan, config = _plan_for(tmp_path, destinations=destinations)
    apply_migration_plan(tmp_path, plan, config)

    rerun_plan, rerun_config = _plan_for(tmp_path, destinations=destinations)
    assert rerun_plan.ready is False
    assert all(item.status == "blocked" for item in rerun_plan.items)
    assert all(
        any("already exists" in reason for reason in item.reasons)
        for item in rerun_plan.items
    )

    with pytest.raises(MigrationApplyError, match="not fully ready-create"):
        apply_migration_plan(tmp_path, rerun_plan, rerun_config)
