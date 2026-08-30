from __future__ import annotations

from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.language_service import LanguageService
from quarto_needs.parser import parse_project_declarations


def test_project_parser_uses_overlay_without_mutating_disk(tmp_path: Path) -> None:
    source = tmp_path / "requirements.qmd"
    source.write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="draft"}
## Disk title
:::
''',
        encoding="utf-8",
    )
    overlay = source.read_text(encoding="utf-8").replace("Disk title", "Unsaved title")
    batch = parse_project_declarations(
        tmp_path, overlays={"requirements.qmd": overlay}
    )
    assert batch.declarations[0].title == "Unsaved title"
    assert "Disk title" in source.read_text(encoding="utf-8")


def test_overlay_can_introduce_unsaved_new_qmd_file(tmp_path: Path) -> None:
    overlay = '''::: {.need #FUN-NEW type="functional-requirement" status="draft"}
## New unsaved object
:::
'''
    result = analyze_project(tmp_path, overlays={"new.qmd": overlay})
    assert result.snapshot is not None
    assert "FUN-NEW" in result.snapshot.objects_by_id
    assert not (tmp_path / "new.qmd").exists()


def test_language_service_reads_unsaved_overlay_semantics(tmp_path: Path) -> None:
    (tmp_path / "requirements.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="draft"}
## Original
:::
''',
        encoding="utf-8",
    )
    overlay = '''::: {.need #FUN-001 type="functional-requirement" status="draft"}
## Edited in memory
:::
'''
    service = LanguageService.load(
        tmp_path, overlays={"requirements.qmd": overlay}
    )
    hover = service.hover("FUN-001")
    assert hover is not None
    assert hover.title == "Edited in memory"
