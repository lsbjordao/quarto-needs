from __future__ import annotations

import json
from pathlib import Path

from quarto_needs.cli_entry import main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_tree(root: Path) -> None:
    _write(
        root / "reqs" / ".doorstop.yml",
        "settings:\n  digits: 3\n  prefix: REQ\n  sep: ''\n",
    )
    _write(
        root / "reqs" / "REQ001.yml",
        (
            "active: true\n"
            "derived: false\n"
            "header: 'Assets'\n"
            "level: 1.0\n"
            "links: []\n"
            "normative: true\n"
            "ref: ''\n"
            "reviewed: abc\n"
            "text: |\n"
            "  Doorstop shall support the storage of external requirements assets.\n"
        ),
    )
    _write(
        root / "reqs" / "tutorial" / ".doorstop.yml",
        "settings:\n  digits: 3\n  parent: REQ\n  prefix: TUT\n  sep: ''\n",
    )
    _write(
        root / "reqs" / "tutorial" / "TUT008.yml",
        (
            "active: true\n"
            "derived: false\n"
            "header: ''\n"
            "level: 1.4\n"
            "links:\n"
            "- REQ001: 9TcFUzsQWUHhoh5wsqnhL7VRtSqMaIhrCXg7mfIkxKM=\n"
            "normative: true\n"
            "ref: ''\n"
            "reviewed: abc\n"
            "text: |\n"
            "  Validating the tree.\n"
        ),
    )


def test_doorstop_cli_writes_ready_plan_when_mappings_are_complete(tmp_path: Path, capsys) -> None:
    _write_tree(tmp_path)

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "doorstop",
            "reqs",
            "--type-map",
            "REQ=system-requirement",
            "--type-map",
            "TUT=test-case",
            "--relation-map",
            "TUT=derives-from",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    output = tmp_path / ".quarto-needs" / "migrations" / "doorstop-plan.json"
    assert output.is_file()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "doorstop-migration-plan-v1"
    assert payload["source"]["tool"] == "Doorstop"
    assert payload["issues"] == []
    assert json.loads(capsys.readouterr().out) == payload


def test_doorstop_cli_apply_plan_and_write_produce_authored_files(tmp_path: Path) -> None:
    _write_tree(tmp_path)

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "doorstop",
            "reqs",
            "--type-map",
            "REQ=system-requirement",
            "--type-map",
            "TUT=test-case",
            "--relation-map",
            "TUT=derives-from",
            "--apply-plan",
            "--write",
            "--destination",
            "REQ001=requirements/assets.qmd",
            "--destination",
            "TUT008=verification/tree.qmd",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    req_path = tmp_path / "requirements" / "assets.qmd"
    tut_path = tmp_path / "verification" / "tree.qmd"
    assert req_path.is_file()
    assert tut_path.is_file()
    assert "::: {.need #TUT008" in tut_path.read_text(encoding="utf-8")


def test_doorstop_cli_returns_one_but_keeps_plan_when_semantics_are_unresolved(
    tmp_path: Path,
) -> None:
    _write_tree(tmp_path)

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "doorstop",
            "reqs",
        ]
    )

    assert exit_code == 1
    output = tmp_path / ".quarto-needs" / "migrations" / "doorstop-plan.json"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert {issue["code"] for issue in payload["issues"]} == {"TYPE_UNMAPPED", "RELATION_UNMAPPED"}


def test_sphinx_and_doorstop_plans_use_independent_default_output_paths(
    tmp_path: Path,
) -> None:
    _write_tree(tmp_path)
    needs_json = tmp_path / "needs.json"
    needs_json.write_text(
        json.dumps(
            {
                "project": "Legacy",
                "current_version": "1.0",
                "versions": {"1.0": {"needs_schema": {"properties": {}}, "needs": {}}},
            }
        ),
        encoding="utf-8",
    )

    main(["--root", str(tmp_path), "migrate", "sphinx-needs", "needs.json"])
    main(["--root", str(tmp_path), "migrate", "doorstop", "reqs"])

    assert (tmp_path / ".quarto-needs" / "migrations" / "sphinx-needs-plan.json").is_file()
    assert (tmp_path / ".quarto-needs" / "migrations" / "doorstop-plan.json").is_file()
