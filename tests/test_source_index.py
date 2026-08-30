from __future__ import annotations

from pathlib import Path

from quarto_needs.source_index import build_source_index


def test_source_index_tracks_only_semantic_id_positions(tmp_path: Path) -> None:
    (tmp_path / "model.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement" verified-by="TC-001; TC-002"}
## Requirement
Narrative TC-001 should not be renamed blindly.
{{< need TC-001 >}}
:::

::: {.need #TC-001 type="test-case"}
## Test one
:::

::: {.need #TC-002 type="test-case"}
## Test two
:::
''',
        encoding="utf-8",
    )
    index = build_source_index(tmp_path)
    spans = index["TC-001"]
    assert [span.kind for span in spans] == ["relation", "shortcode", "declaration"]
    assert len(spans) == 3


def test_source_index_tracks_metadata_relation_lists(tmp_path: Path) -> None:
    (tmp_path / "model.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement"}
verified-by:
  - TC-001
  - TC-002
## Requirement
:::

::: {.need #TC-001 type="test-case"}
## Test
:::
''',
        encoding="utf-8",
    )
    index = build_source_index(tmp_path)
    relation = next(span for span in index["TC-001"] if span.kind == "relation")
    assert relation.line == 2
    line = (tmp_path / "model.qmd").read_text(encoding="utf-8").splitlines()[relation.line]
    assert line[relation.start:relation.end] == "TC-001"


def test_source_index_uses_unsaved_overlay_text(tmp_path: Path) -> None:
    source = tmp_path / "model.qmd"
    source.write_text(
        '''::: {.need #FUN-OLD type="functional-requirement"}
## Old
:::
''',
        encoding="utf-8",
    )
    overlay = source.read_text(encoding="utf-8").replace("FUN-OLD", "FUN-NEW")
    index = build_source_index(tmp_path, overlays={"model.qmd": overlay})
    assert "FUN-NEW" in index
    assert "FUN-OLD" not in index
