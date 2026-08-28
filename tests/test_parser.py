from pathlib import Path

from quarto_needs.parser import (
    parse_project_declarations,
    parse_qmd,
    parse_qmd_declarations,
)
from quarto_needs.validation import validate


def write_need(
    path: Path,
    need_id: str,
    relation_name: str | None,
    relation_target: str | None,
    *,
    need_type: str = "system-requirement",
) -> None:
    relation = (
        f"{relation_name}: {relation_target}\n"
        if relation_name is not None and relation_target is not None
        else ""
    )
    path.write_text(
        f"::: {{.need #{need_id} type={need_type}}}\n"
        f"{relation}"
        f"\n## {need_id}\n"
        "Body.\n"
        ":::\n",
        encoding="utf-8",
    )


def test_parse_need(tmp_path: Path):
    qmd = tmp_path / "req.qmd"
    qmd.write_text('''::: {.need #SYS-REQ-001 type="system-requirement" status="approved" derived-from="NEED-001"}\n## Login\nText.\n:::\n''', encoding="utf-8")
    objs = parse_qmd(qmd, tmp_path)
    assert len(objs) == 1
    assert objs[0].id == "SYS-REQ-001"
    assert objs[0].title == "Login"
    assert objs[0].relations[0].target == "NEED-001"


def test_unknown_reference(tmp_path: Path):
    qmd = tmp_path / "req.qmd"
    qmd.write_text('''::: {.need #SYS-REQ-001 type="system-requirement" verified-by="TC-404"}\n## Login\nText.\n:::\n''', encoding="utf-8")
    findings = validate(parse_qmd(qmd, tmp_path))
    assert any(f.code == "REQ005" for f in findings)


def test_parser_accepts_catalog_only_relation_names(tmp_path: Path):
    qmd = tmp_path / "req.qmd"
    qmd.write_text(
        '''::: {.need #TC-1 type="test-case"}
verifies: REQ-1
evidences: EVD-1
## Login test
Text.
:::
''',
        encoding="utf-8",
    )

    relations = parse_qmd(qmd, tmp_path)[0].relations

    assert [(relation.type, relation.authored_name, relation.target) for relation in relations] == [
        ("verifies", "verifies", "REQ-1"),
        ("evidences", "evidences", "EVD-1"),
    ]


def test_project_declarations_sort_paths_and_keep_authored_relation(
    tmp_path: Path,
) -> None:
    write_need(tmp_path / "z.qmd", "Z-REQ", "verified-by", "A-TC")
    write_need(tmp_path / "a.qmd", "A-TC", None, None, need_type="test-case")

    batch = parse_project_declarations(
        tmp_path,
        files=[tmp_path / "z.qmd", tmp_path / "a.qmd"],
    )

    assert [item.id for item in batch.declarations] == ["A-TC", "Z-REQ"]
    relation = next(
        item for item in batch.declarations if item.id == "Z-REQ"
    ).relations[0]
    assert relation.authored_name == "verified-by"
    assert relation.location is not None
    assert relation.location.file == "z.qmd"


def test_project_discovery_ignores_localized_sibling(tmp_path: Path) -> None:
    write_need(tmp_path / "requirements.qmd", "REQ-1", None, None)
    write_need(tmp_path / "requirements.pt-BR.qmd", "REQ-1", None, None)

    batch = parse_project_declarations(tmp_path)

    assert [item.id for item in batch.declarations] == ["REQ-1"]
    assert batch.declarations[0].location is not None
    assert batch.declarations[0].location.file == "requirements.qmd"


def test_locale_looking_file_without_canonical_sibling_is_discovered(
    tmp_path: Path,
) -> None:
    write_need(tmp_path / "standalone.pt-BR.qmd", "REQ-PT", None, None)

    batch = parse_project_declarations(tmp_path)

    assert [item.id for item in batch.declarations] == ["REQ-PT"]


def test_localized_file_can_be_parsed_explicitly(tmp_path: Path) -> None:
    write_need(tmp_path / "requirements.qmd", "REQ-EN", None, None)
    localized = tmp_path / "requirements.pt-BR.qmd"
    write_need(localized, "REQ-PT", None, None)

    batch = parse_project_declarations(tmp_path, files=[localized])

    assert [item.id for item in batch.declarations] == ["REQ-PT"]
    assert batch.declarations[0].location is not None
    assert batch.declarations[0].location.file == "requirements.pt-BR.qmd"


def test_unclosed_need_block_is_a_located_structural_finding(tmp_path: Path) -> None:
    source = tmp_path / "broken.qmd"
    source.write_text("::: {.need #REQ-BROKEN}\n## Broken\n", encoding="utf-8")

    batch = parse_qmd_declarations(source, tmp_path)

    assert batch.declarations == ()
    assert [
        (item.code, item.severity, item.location.file, item.location.line)
        for item in batch.findings
    ] == [("QND001", "error", "broken.qmd", 1)]


def test_known_relation_without_targets_is_structurally_invalid(
    tmp_path: Path,
) -> None:
    source = tmp_path / "empty-relation.qmd"
    source.write_text(
        "::: {.need #REQ-EMPTY}\n"
        "verified-by:\n\n"
        "## Empty relation\n"
        ":::\n",
        encoding="utf-8",
    )

    batch = parse_qmd_declarations(source, tmp_path)

    assert [(item.code, item.object_id) for item in batch.findings] == [
        ("QND002", "REQ-EMPTY")
    ]
