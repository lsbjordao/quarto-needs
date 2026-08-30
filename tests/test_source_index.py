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
    assert all(not span.presentation_only for span in spans)


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


def test_source_index_includes_localized_siblings_for_identity_refactors(tmp_path: Path) -> None:
    canonical = tmp_path / "requirements.qmd"
    localized = tmp_path / "requirements.pt-BR.qmd"
    canonical.write_text(
        '''::: {.need #FUN-001 type="functional-requirement" verified-by="TC-001"}
## Requirement
Narrative TC-001 is intentionally not a semantic reference.
{{< need TC-001 >}}
:::

::: {.need #TC-001 type="test-case"}
## Test
:::
''',
        encoding="utf-8",
    )
    localized.write_text(
        '''::: {.need #FUN-001 type="functional-requirement" verified-by="TC-001"}
## Requisito
Narrativa TC-001 também deve permanecer texto comum.
{{< need TC-001 >}}
:::

::: {.need #TC-001 type="test-case"}
## Teste
:::
''',
        encoding="utf-8",
    )

    index = build_source_index(tmp_path)
    spans = index["TC-001"]
    canonical_spans = [span for span in spans if not span.presentation_only]
    localized_spans = [span for span in spans if span.presentation_only]
    assert len(canonical_spans) == 3
    assert len(localized_spans) == 3
    assert {span.file for span in canonical_spans} == {"requirements.qmd"}
    assert {span.file for span in localized_spans} == {"requirements.pt-BR.qmd"}
    assert all(span.kind in {"relation", "shortcode", "declaration"} for span in spans)
