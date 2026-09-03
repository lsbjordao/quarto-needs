from __future__ import annotations

import json
from pathlib import Path

import pytest

from quarto_needs.cli_entry import main
from quarto_needs.migrations.openfasttrace import (
    OpenFastTraceMigrationError,
    build_migration_plan,
    load_specobjects,
)

_REQUIREMENT = """## Authenticate the user

`req~authenticate-user~2`

Status: approved

The system shall authenticate users before granting access.

Rationale:
Unauthenticated access exposes private data.

Comment:
Carried over verbatim from the legacy tracker.

Depends:
- req~session-management~1
"""

_FEATURE = """### Feature: user management

`feat~user-management~1`

Provides the feature area both requirements live in.

Covers:
* feat~user-management~1
"""

_COVERS_ONE_LINER = """### One-liner coverage

`utest~user-login-test~1`

The login test covers its requirement inline.

Covers: req~authenticate-user~2
"""

_SESSION = """## Session management

`req~session-management~1`

The system shall manage authenticated sessions.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _tree(root: Path) -> None:
    _write(root / "reqs" / "authentication.md", _REQUIREMENT)
    _write(root / "reqs" / "session.md", _SESSION)
    _write(root / "features" / "user-management.md", _FEATURE)
    _write(root / "tests" / "login.md", _COVERS_ONE_LINER)


def test_parser_reads_headings_keywords_and_both_list_styles(tmp_path: Path) -> None:
    _tree(tmp_path)

    items = {item.id: item for item in load_specobjects(tmp_path)}

    assert set(items) == {
        "req~authenticate-user~2",
        "req~session-management~1",
        "feat~user-management~1",
        "utest~user-login-test~1",
    }
    requirement = items["req~authenticate-user~2"]
    assert requirement.doctype == "req"
    assert requirement.revision == "2"
    assert requirement.title == "Authenticate the user"
    assert requirement.status == "approved"
    assert "authenticate users before granting access" in requirement.description
    assert requirement.rationale.startswith("Unauthenticated access")
    assert requirement.extras["comment"].startswith("Carried over verbatim")
    assert requirement.depends == ("req~session-management~1",)

    test_item = items["utest~user-login-test~1"]
    assert test_item.covers == ("req~authenticate-user~2",), (
        "the one-liner Covers form must parse like the bullet form"
    )


def test_plan_maps_doctypes_and_keywords_explicitly(tmp_path: Path) -> None:
    _tree(tmp_path)
    items = load_specobjects(tmp_path)

    plan = build_migration_plan(
        items,
        type_map={"req": "functional-requirement", "feat": "system-requirement"},
        relation_map={"depends": "depends-on"},
    )

    assert plan.tool == "OpenFastTrace"
    assert plan.schema == "openfasttrace-migration-plan-v1"
    by_id = {candidate.source_id: candidate for candidate in plan.candidates}

    requirement = by_id["req~authenticate-user~2"]
    assert requirement.target_type == "functional-requirement"
    assert requirement.status == "approved"
    assert [(relation.relation, relation.target) for relation in requirement.relations] == [
        ("depends-on", "req~session-management~1")
    ]
    content = requirement.content
    assert "authenticate users before granting access" in content
    assert "### Rationale" in content and "Unauthenticated access" in content

    test_item = by_id["utest~user-login-test~1"]
    codes = {(issue.code, issue.need_id) for issue in plan.issues}
    assert ("RELATION_UNMAPPED", "utest~user-login-test~1") in codes
    assert test_item.unmapped_links["covers"] == ("req~authenticate-user~2",), (
        "an unmapped keyword's links are preserved as data, never dropped"
    )


def test_plan_reports_unmapped_doctypes_and_ghost_targets(tmp_path: Path) -> None:
    _tree(tmp_path)
    items = load_specobjects(tmp_path)

    plan = build_migration_plan(
        items,
        type_map={"req": "functional-requirement"},
        relation_map={"covers": "verifies", "depends": "depends-on"},
    )

    codes = {(issue.code, issue.need_id) for issue in plan.issues}
    assert ("TYPE_UNMAPPED", "feat~user-management~1") in codes

    # covers is mapped to verifies here; the *target* is what's missing.
    plan_with_ghost = build_migration_plan(
        [
            item
            for item in items
            if item.id == "utest~user-login-test~1"
        ],
        type_map={"utest": "test-case"},
        relation_map={"covers": "verifies"},
    )
    assert ("EXTERNAL_LINK_TARGET", "utest~user-login-test~1") in {
        (issue.code, issue.need_id) for issue in plan_with_ghost.issues
    }


def test_duplicate_identifiers_across_files_are_refused(tmp_path: Path) -> None:
    _write(tmp_path / "one.md", _REQUIREMENT)
    _write(tmp_path / "two.md", _REQUIREMENT)

    with pytest.raises(OpenFastTraceMigrationError, match="defined in both"):
        load_specobjects(tmp_path)


def test_cli_writes_the_plan_with_default_output_path(tmp_path: Path) -> None:
    _tree(tmp_path / "oft")

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "openfasttrace",
            "oft",
            "--type-map",
            "req=functional-requirement",
            "--type-map",
            "feat=system-requirement",
            "--type-map",
            "utest=test-case",
            "--relation-map",
            "depends=depends-on",
            "--relation-map",
            "covers=verifies",
        ]
    )

    assert exit_code == 0
    plan_path = tmp_path / ".quarto-needs" / "migrations" / "openfasttrace-plan.json"
    assert plan_path.is_file()
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "openfasttrace-migration-plan-v1"
    assert payload["source"]["tool"] == "OpenFastTrace"
