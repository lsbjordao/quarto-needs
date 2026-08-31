from __future__ import annotations

import json
from pathlib import Path

from quarto_needs.cli_entry import main


def _write_needs_json(root: Path) -> Path:
    payload = {
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
    path = root / "needs.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_migration_cli_writes_ready_plan_when_mappings_are_complete(tmp_path: Path, capsys) -> None:
    _write_needs_json(tmp_path)

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
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    output = tmp_path / ".quarto-needs" / "migrations" / "sphinx-needs-plan.json"
    assert output.is_file()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "sphinx-needs-migration-plan-v1"
    assert payload["issues"] == []
    assert json.loads(capsys.readouterr().out) == payload


def test_migration_cli_returns_one_but_keeps_plan_when_semantics_are_unresolved(
    tmp_path: Path, capsys
) -> None:
    _write_needs_json(tmp_path)

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "sphinx-needs",
            "needs.json",
        ]
    )

    assert exit_code == 1
    output = tmp_path / ".quarto-needs" / "migrations" / "sphinx-needs-plan.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert {issue["code"] for issue in payload["issues"]} == {
        "LINK_FIELD_UNMAPPED",
        "TYPE_UNMAPPED",
    }
    stdout = capsys.readouterr().out
    assert "migration plan" in stdout.lower()
    assert "TYPE_UNMAPPED" in stdout


def test_migration_cli_rejects_conflicting_mapping_declarations(tmp_path: Path, capsys) -> None:
    _write_needs_json(tmp_path)

    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "migrate",
                "sphinx-needs",
                "needs.json",
                "--type-map",
                "req=system-requirement",
                "--type-map",
                "req=functional-requirement",
            ]
        )
        == 2
    )
    assert "maps 'req' more than once" in capsys.readouterr().err


def test_migration_cli_rejects_unknown_source(tmp_path: Path, capsys) -> None:
    assert main(["--root", str(tmp_path), "migrate", "other", "input.json"]) == 2
    assert "Unknown migration source: other" in capsys.readouterr().err
