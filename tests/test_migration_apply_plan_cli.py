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


def _run(tmp_path: Path, *extra_args: str) -> int:
    _write_needs_json(tmp_path)
    return main(
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
            *extra_args,
        ]
    )


def test_apply_plan_cli_writes_ready_plan_when_destinations_are_explicit(
    tmp_path: Path, capsys
) -> None:
    exit_code = _run(
        tmp_path,
        "--apply-plan",
        "--destination",
        "REQ_001=requirements/authentication.qmd",
        "--destination",
        "TC_001=verification/authentication.qmd",
        "--format",
        "json",
    )

    assert exit_code == 0
    output = tmp_path / ".quarto-needs" / "migrations" / "sphinx-needs-apply-plan.json"
    assert output.is_file()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "migration-apply-plan-v1"
    assert payload["ready"] is True
    assert [item["status"] for item in payload["items"]] == [
        "ready-create",
        "ready-create",
    ]
    assert json.loads(capsys.readouterr().out) == payload


def test_apply_plan_cli_reports_review_required_without_destination(
    tmp_path: Path, capsys
) -> None:
    exit_code = _run(
        tmp_path,
        "--apply-plan",
        "--destination",
        "TC_001=verification/authentication.qmd",
        "--format",
        "text",
    )

    assert exit_code == 1
    stdout = capsys.readouterr().out
    assert "review-required" in stdout
    assert "no destination" in stdout
    output = tmp_path / ".quarto-needs" / "migrations" / "sphinx-needs-apply-plan.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ready"] is False


def test_apply_plan_cli_show_content_prints_the_rendered_need_block(
    tmp_path: Path, capsys
) -> None:
    exit_code = _run(
        tmp_path,
        "--apply-plan",
        "--destination",
        "REQ_001=requirements/authentication.qmd",
        "--destination",
        "TC_001=verification/authentication.qmd",
        "--format",
        "text",
        "--show-content",
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "::: {.need #REQ_001" in stdout
    assert "## Authenticate users" in stdout


def test_apply_plan_cli_hides_content_by_default(tmp_path: Path, capsys) -> None:
    exit_code = _run(
        tmp_path,
        "--apply-plan",
        "--destination",
        "REQ_001=requirements/authentication.qmd",
        "--destination",
        "TC_001=verification/authentication.qmd",
        "--format",
        "text",
    )

    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "::: {.need" not in stdout


def test_plan_only_invocation_is_unaffected_by_apply_plan_support(
    tmp_path: Path, capsys
) -> None:
    exit_code = _run(tmp_path, "--format", "json")

    assert exit_code == 0
    output = tmp_path / ".quarto-needs" / "migrations" / "sphinx-needs-plan.json"
    assert output.is_file()
    apply_output = tmp_path / ".quarto-needs" / "migrations" / "sphinx-needs-apply-plan.json"
    assert not apply_output.exists()
