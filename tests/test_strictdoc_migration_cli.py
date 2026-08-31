from __future__ import annotations

import json
from pathlib import Path

from quarto_needs.cli_entry import main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_project(root: Path) -> None:
    _write(
        root / "srs.sdoc",
        """[DOCUMENT]
TITLE: System Requirements

[REQUIREMENT]
UID: SRS-1
STATUS: Active
TITLE: Persist configuration
STATEMENT: >>>
The system shall persist configuration between runs.
<<<
""",
    )
    _write(
        root / "llr.sdoc",
        """[DOCUMENT]
TITLE: Low-Level Requirements

[REQUIREMENT]
UID: LLR-1
STATUS: Active
TITLE: Write config atomically
STATEMENT: >>>
The config writer shall use a temp-file-plus-rename write.
<<<
RELATIONS:
- TYPE: Parent
  VALUE: SRS-1
""",
    )


def test_strictdoc_cli_writes_ready_plan_when_mappings_are_complete(
    tmp_path: Path, capsys
) -> None:
    _write_project(tmp_path)

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "strictdoc",
            ".",
            "--type-map",
            "REQUIREMENT=system-requirement",
            "--relation-map",
            "Parent=derives-from",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    output = tmp_path / ".quarto-needs" / "migrations" / "strictdoc-plan.json"
    assert output.is_file()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "strictdoc-migration-plan-v1"
    assert payload["source"]["tool"] == "StrictDoc"
    assert payload["issues"] == []
    assert json.loads(capsys.readouterr().out) == payload


def test_strictdoc_cli_apply_plan_and_write_produce_authored_files(tmp_path: Path) -> None:
    _write_project(tmp_path)

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "strictdoc",
            ".",
            "--type-map",
            "REQUIREMENT=system-requirement",
            "--relation-map",
            "Parent=derives-from",
            "--apply-plan",
            "--write",
            "--destination",
            "SRS-1=requirements/config.qmd",
            "--destination",
            "LLR-1=implementation/config-writer.qmd",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    srs_path = tmp_path / "requirements" / "config.qmd"
    llr_path = tmp_path / "implementation" / "config-writer.qmd"
    assert srs_path.is_file()
    assert llr_path.is_file()
    llr_text = llr_path.read_text(encoding="utf-8")
    assert "::: {.need #LLR-1" in llr_text
    assert "derives-from: SRS-1" in llr_text


def test_strictdoc_cli_returns_one_but_keeps_plan_when_semantics_are_unresolved(
    tmp_path: Path,
) -> None:
    _write_project(tmp_path)

    exit_code = main(["--root", str(tmp_path), "migrate", "strictdoc", "."])

    assert exit_code == 1
    output = tmp_path / ".quarto-needs" / "migrations" / "strictdoc-plan.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert {issue["code"] for issue in payload["issues"]} == {"TYPE_UNMAPPED", "RELATION_UNMAPPED"}


def test_three_migration_sources_use_independent_default_output_paths(tmp_path: Path) -> None:
    _write_project(tmp_path)

    main(["--root", str(tmp_path), "migrate", "strictdoc", "."])

    assert (tmp_path / ".quarto-needs" / "migrations" / "strictdoc-plan.json").is_file()
    assert (tmp_path / ".quarto-needs" / "migrations" / "sphinx-needs-plan.json").exists() is False
    assert (tmp_path / ".quarto-needs" / "migrations" / "doorstop-plan.json").exists() is False
