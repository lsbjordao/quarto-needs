from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.cli_entry import main
from quarto_needs.config import Gates, NeedsConfig
from quarto_needs.migrations import update_write
from quarto_needs.migrations.apply_plan import build_migration_update_plan
from quarto_needs.migrations.sphinx_needs import build_migration_plan
from quarto_needs.migrations.update_write import (
    MigrationUpdateError,
    apply_migration_update_plan,
)


REQUIREMENTS = """Intro prose.

::: {.need #REQ_001 type="system-requirement" status="approved" tags="security" source-tool="sphinx-needs" source-project="Legacy engineering docs" source-id="REQ_001"}
priority: high
verified-by: TC_001

## Authenticate users (old)

An older body.
:::

Closing prose.
"""

VERIFICATION = """::: {.need #TC_001 type="test-case" status="passed" source-tool="sphinx-needs" source-project="Legacy engineering docs" source-id="TC_001"}
## Authentication test

Exercise authentication.
:::
"""


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


def _migration_payload(priority: str = "high") -> dict[str, object]:
    return {
        "project": "Legacy engineering docs",
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs_schema": {
                    "properties": {"tests": {"field_type": "links"}}
                },
                "needs": {
                    "REQ_001": {
                        "type": "req",
                        "title": "Authenticate users",
                        "content": "The system shall authenticate users.",
                        "status": "approved",
                        "tags": ["security"],
                        "priority": priority,
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


def _migration(priority: str = "high"):
    return build_migration_plan(
        _migration_payload(priority),
        type_map={"req": "system-requirement", "test": "test-case"},
        relation_map={"tests": "verified-by"},
    )


def _author(root: Path, *, with_test_case: bool = True) -> None:
    text = REQUIREMENTS
    if not with_test_case:
        # Keep the project valid while leaving TC_001 uncreated, so the
        # plan contains one ready-update and one ready-create.
        text = text.replace("verified-by: TC_001\n\n", "")
    (root / "requirements.qmd").write_text(text, encoding="utf-8")
    if with_test_case:
        (root / "verification.qmd").write_text(VERIFICATION, encoding="utf-8")


def _update_plan(root: Path):
    result = analyze_project(root, config=_config())
    assert result.snapshot is not None
    return build_migration_update_plan(
        _migration(),
        result.snapshot,
        _config(),
        root=root,
        destinations={"REQ_001": "requirements.qmd", "TC_001": "verification.qmd"},
    )


def test_apply_update_replaces_the_block_in_place(tmp_path: Path) -> None:
    _author(tmp_path)
    plan = _update_plan(tmp_path)
    assert {item.source_id: item.status for item in plan.items} == {
        "REQ_001": "ready-update",
        "TC_001": "no-change",
    }

    result = apply_migration_update_plan(tmp_path, plan, _config())

    assert result.to_dict()["schema"] == "migration-update-result-v1"
    assert [entry["sourceId"] for entry in result.to_dict()["updated"]] == ["REQ_001"]
    text = (tmp_path / "requirements.qmd").read_text(encoding="utf-8")
    assert "## Authenticate users (old)" not in text
    assert "## Authenticate users\n" in text
    assert "The system shall authenticate users." in text
    assert "Intro prose." in text and "Closing prose." in text
    assert 'source-id="REQ_001"' in text

    rescanned = analyze_project(tmp_path, config=_config())
    assert rescanned.snapshot is not None
    record = rescanned.snapshot.objects_by_id["REQ_001"]
    assert record.title == "Authenticate users"
    assert record.body == "The system shall authenticate users."


def test_applying_an_outdated_plan_is_refused_without_touching_the_file(
    tmp_path: Path,
) -> None:
    _author(tmp_path)
    plan = _update_plan(tmp_path)
    path = tmp_path / "requirements.qmd"
    path.write_text(REQUIREMENTS.replace("(old)", "(edited locally)"), encoding="utf-8")
    edited = path.read_text(encoding="utf-8")

    with pytest.raises(MigrationUpdateError, match="stale"):
        apply_migration_update_plan(tmp_path, plan, _config())

    assert path.read_text(encoding="utf-8") == edited


def test_changed_extras_classify_an_update_and_are_authored(tmp_path: Path) -> None:
    _author(tmp_path)
    result = analyze_project(tmp_path, config=_config())
    plan = build_migration_update_plan(
        _migration(priority="critical"),
        result.snapshot,
        _config(),
        root=tmp_path,
        destinations={"REQ_001": "requirements.qmd", "TC_001": "verification.qmd"},
    )

    req = next(item for item in plan.items if item.source_id == "REQ_001")
    assert req.status == "ready-update"
    assert "attributes" in req.changes

    apply_migration_update_plan(tmp_path, plan, _config())

    requirements = (tmp_path / "requirements.qmd").read_text(encoding="utf-8")
    assert "priority: critical" in requirements


def test_a_mixed_plan_applies_updates_and_creates_in_one_sync(
    tmp_path: Path,
) -> None:
    """An upstream that changed an item and gained one applies in one run."""
    _author(tmp_path, with_test_case=False)
    plan = _update_plan(tmp_path)
    assert {item.source_id: item.status for item in plan.items} == {
        "REQ_001": "ready-update",
        "TC_001": "ready-create",
    }

    result = apply_migration_update_plan(tmp_path, plan, _config())

    assert [(entry["sourceId"], entry["action"]) for entry in result.to_dict()["updated"]] == [
        ("REQ_001", "ready-update"),
        ("TC_001", "ready-create"),
    ]
    requirements = (tmp_path / "requirements.qmd").read_text(encoding="utf-8")
    assert "## Authenticate users\n" in requirements
    assert "## Authenticate users (old)" not in requirements
    assert "priority: high" in requirements
    verification = (tmp_path / "verification.qmd").read_text(encoding="utf-8")
    assert 'source-id="TC_001"' in verification

    rescanned = analyze_project(tmp_path, config=_config())
    assert rescanned.snapshot is not None
    assert {"REQ_001", "TC_001"} <= set(rescanned.snapshot.objects_by_id)


def test_a_ready_create_stale_plan_is_refused_without_touching_any_file(
    tmp_path: Path,
) -> None:
    _author(tmp_path, with_test_case=False)
    plan = _update_plan(tmp_path)

    # The upstream item was authored locally between plan and apply.
    (tmp_path / "verification.qmd").write_text(VERIFICATION, encoding="utf-8")

    with pytest.raises(MigrationUpdateError, match="already exists"):
        apply_migration_update_plan(tmp_path, plan, _config())

    assert "## Authenticate users (old)" in (
        tmp_path / "requirements.qmd"
    ).read_text(encoding="utf-8")


def test_post_write_failure_removes_a_created_file_and_restores_an_updated_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _author(tmp_path, with_test_case=False)
    plan = _update_plan(tmp_path)

    class _Failed:
        snapshot = None
        findings = ()

    calls = {"count": 0}
    original = update_write.analyze_project

    def flaky(*args, **kwargs):
        calls["count"] += 1
        return _Failed() if calls["count"] > 1 else original(*args, **kwargs)

    monkeypatch.setattr(update_write, "analyze_project", flaky)

    with pytest.raises(MigrationUpdateError, match="rolling back"):
        apply_migration_update_plan(tmp_path, plan, _config())

    assert not (tmp_path / "verification.qmd").exists()
    authored = REQUIREMENTS.replace("verified-by: TC_001\n\n", "")
    assert (tmp_path / "requirements.qmd").read_text(encoding="utf-8") == authored


def test_second_apply_of_a_mixed_plan_is_refused(tmp_path: Path) -> None:
    _author(tmp_path, with_test_case=False)
    plan = _update_plan(tmp_path)

    apply_migration_update_plan(tmp_path, plan, _config())

    with pytest.raises(MigrationUpdateError, match="already exists"):
        apply_migration_update_plan(tmp_path, plan, _config())


def test_a_plan_with_no_updates_is_refused(tmp_path: Path) -> None:
    _author(tmp_path)
    plan = _update_plan(tmp_path)
    no_change = type(plan)(
        source_tool=plan.source_tool,
        source_project=plan.source_project,
        source_version=plan.source_version,
        semantic_graph_fingerprint=plan.semantic_graph_fingerprint,
        items=tuple(
            replace(item, status="no-change") for item in plan.items
        ),
    )

    with pytest.raises(MigrationUpdateError, match="no items to apply"):
        apply_migration_update_plan(tmp_path, no_change, _config())


def test_post_write_verification_failure_rolls_the_file_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _author(tmp_path)
    plan = _update_plan(tmp_path)

    class _Failed:
        snapshot = None
        findings = ()

    calls = {"count": 0}
    original = update_write.analyze_project

    def flaky(*args, **kwargs):
        calls["count"] += 1
        return _Failed() if calls["count"] > 1 else original(*args, **kwargs)

    monkeypatch.setattr(update_write, "analyze_project", flaky)

    with pytest.raises(MigrationUpdateError, match="rolling back"):
        apply_migration_update_plan(tmp_path, plan, _config())

    assert (tmp_path / "requirements.qmd").read_text(encoding="utf-8") == REQUIREMENTS


def test_second_apply_is_refused_by_the_stale_digest(tmp_path: Path) -> None:
    _author(tmp_path)
    plan = _update_plan(tmp_path)

    apply_migration_update_plan(tmp_path, plan, _config())

    with pytest.raises(MigrationUpdateError, match="stale"):
        apply_migration_update_plan(tmp_path, plan, _config())


def test_cli_update_write_applies_and_requires_the_apply_update_flag(
    tmp_path: Path, capsys
) -> None:
    _author(tmp_path)
    (tmp_path / "needs.json").write_text(
        json.dumps(_migration_payload()), encoding="utf-8"
    )

    base = [
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
    ]

    capsys.readouterr()
    refused = main(base + ["--write"])
    assert refused == 2
    assert "--apply-update" in capsys.readouterr().err
    assert "## Authenticate users (old)" in (
        tmp_path / "requirements.qmd"
    ).read_text(encoding="utf-8")

    applied = main(base + ["--apply-update", "--write", "--format", "json"])
    assert applied == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "migration-update-result-v1"
    assert payload["updated"][0]["canonicalId"] == "REQ_001"
    assert "## Authenticate users\n" in (
        tmp_path / "requirements.qmd"
    ).read_text(encoding="utf-8")
