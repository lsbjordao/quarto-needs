from __future__ import annotations

from pathlib import Path

from quarto_needs.language_service import LanguageService


def _project(tmp_path: Path) -> LanguageService:
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement]
role = "requirement"
allowed-statuses = ["approved"]

[types.test-case]
role = "verification"
allowed-statuses = ["passed"]

[queries.approved]
all = [{ field = "status", op = "eq", value = "approved" }]
sort = ["id:asc"]

[derived.verification-count]
scope = "approved"
operation = "relation-count"
relation = "verified-by"
target-role = "verification"

[policies.APPROVED_REQUIRES_TEST]
scope = "approved"
assert-relation = "verified-by"
target-role = "verification"
minimum = 1
severity = "error"
''',
        encoding="utf-8",
    )
    (tmp_path / "requirements.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Requirement one
:::

::: {.need #FUN-002 type="functional-requirement" status="approved"}
## Requirement two
:::
''',
        encoding="utf-8",
    )
    (tmp_path / "verification.qmd").write_text(
        '''::: {.need #TC-001 type="test-case" status="passed"}
## Test
:::
''',
        encoding="utf-8",
    )
    return LanguageService.load(tmp_path)


def test_hover_exposes_authored_and_derived_semantics(tmp_path: Path) -> None:
    service = _project(tmp_path)
    hover = service.hover("FUN-001")
    assert hover is not None
    assert hover.title == "Requirement one"
    assert hover.role == "requirement"
    assert hover.derived["verification-count"] == 1
    assert hover.outgoing == 1


def test_completion_uses_objects_types_statuses_and_relation_catalog(tmp_path: Path) -> None:
    service = _project(tmp_path)
    assert any(item.label == "FUN-001" and item.kind == "object" for item in service.completions("FUN"))
    assert any(item.label == "functional-requirement" and item.kind == "type" for item in service.completions("functional"))
    assert any(item.label == "verified-by" and item.kind == "relation" for item in service.completions("verified"))
    assert any(item.label == "approved" and item.kind == "status" for item in service.completions("app"))


def test_definition_and_references_are_graph_backed(tmp_path: Path) -> None:
    service = _project(tmp_path)
    definition = service.definition("FUN-001")
    assert definition is not None
    assert definition.file == "requirements.qmd"
    refs = service.references("TC-001")
    assert [(item.direction, item.relation, item.peer_id) for item in refs] == [
        ("incoming", "verified-by", "FUN-001")
    ]


def test_diagnostics_and_symbols_filter_by_file(tmp_path: Path) -> None:
    service = _project(tmp_path)
    diagnostics = service.diagnostics(file="requirements.qmd")
    assert any(
        item.code == "POLICY:APPROVED_REQUIRES_TEST" and item.object_id == "FUN-002"
        for item in diagnostics
    )
    symbols = service.symbols(file="verification.qmd")
    assert [(item.object_id, item.type) for item in symbols] == [("TC-001", "test-case")]
