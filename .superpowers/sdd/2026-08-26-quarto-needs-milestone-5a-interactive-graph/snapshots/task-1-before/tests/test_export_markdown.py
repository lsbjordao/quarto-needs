from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs import baseline as baseline_module
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import markdown_export


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed priority=high}\n"
        "\n## Login\nSigns in.\n"
        ":::\n",
        encoding="utf-8",
    )


def built(root: Path):
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return result.snapshot, config


def test_summary_without_a_baseline_says_so_and_lists_failed_gates(tmp_path: Path) -> None:
    write_project(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[gates]\nmin-evidence = 100.0\n', encoding="utf-8"
    )
    snapshot, config = built(tmp_path)

    text = markdown_export.render(snapshot, config)

    assert "## Changes" in text and "No baseline was supplied" in text
    assert "## Failed gates" in text and "min-evidence" in text
    assert "## High and critical impact" in text


def test_summary_with_a_baseline_reports_changes_and_impact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    write_project(tmp_path)
    snapshot, config = built(tmp_path)
    payload = baseline_module.build_baseline(snapshot, config)

    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nThe service shall authenticate every administrator.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed priority=high}\n"
        "\n## Login\nSigns in.\n"
        ":::\n",
        encoding="utf-8",
    )
    snapshot, config = built(tmp_path)

    text = markdown_export.render(snapshot, config, baseline=payload)

    assert "REQ-1" in text and "body" in text
    assert "TC-1" in text
    assert "## Coverage deltas" in text


def test_summary_escapes_markdown_table_cells(tmp_path: Path) -> None:
    write_project(tmp_path)
    snapshot, config = built(tmp_path)
    payload = baseline_module.build_baseline(snapshot, config)
    (tmp_path / "needs.qmd").write_text(
        (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace(
            "The service shall authenticate.", "Changed | with a table delimiter."
        ),
        encoding="utf-8",
    )
    snapshot, config = built(tmp_path)

    text = markdown_export.render(snapshot, config, baseline=payload)
    assert "REQ-1" in text
    assert "| modified | REQ-1 | body |" in text


def test_summary_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    write_project(tmp_path)
    snapshot, config = built(tmp_path)
    assert markdown_export.render(snapshot, config) == markdown_export.render(snapshot, config)
