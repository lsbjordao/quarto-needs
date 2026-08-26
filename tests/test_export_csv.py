from __future__ import annotations

import csv
from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import csv_export


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "rationale: Protect data.\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n## Login\n=SUM(A1:A9) starts a formula when pasted into a spreadsheet\n"
        ":::\n",
        encoding="utf-8",
    )


def build(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None
    return result.snapshot


def test_csv_writes_three_files_with_expected_headers(tmp_path: Path) -> None:
    write_project(tmp_path)
    written = csv_export.write_all(tmp_path / "csv", build(tmp_path))

    assert [path.name for path in written] == ["findings.csv", "objects.csv", "relations.csv"]
    rows = list(csv.DictReader((tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8").splitlines()))
    assert rows[0]["id"] == "REQ-1"
    assert rows[0]["type"] == "system-requirement"


def test_csv_neutralizes_formula_injection(tmp_path: Path) -> None:
    write_project(tmp_path)
    csv_export.write_all(tmp_path / "csv", build(tmp_path))

    text = (tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8")
    cells = {value: None for row in csv.DictReader(text.splitlines()) for value in row.values()}
    dangerous = [value for value in cells if value.startswith(("=", "+", "-", "@", "\t", "\r"))]
    assert not dangerous
    assert any(value.startswith("'=") for value in cells), "the neutralized cell must carry the apostrophe prefix"


def test_csv_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    write_project(tmp_path)
    first = csv_export.render_objects(build(tmp_path))
    second = csv_export.render_objects(build(tmp_path))
    assert first == second
