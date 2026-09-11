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


def test_scalar_relation_targets_split_on_semicolons_and_commas(tmp_path: Path) -> None:
    qmd = tmp_path / "decision.qmd"
    qmd.write_text(
        '''::: {.need #ADR-1 type="architecture-decision" addresses="REQ-1; REQ-2,REQ-3"}
## Decision
Text.
:::
''',
        encoding="utf-8",
    )

    relations = parse_qmd(qmd, tmp_path)[0].relations

    assert [(relation.type, relation.target) for relation in relations] == [
        ("addresses", "REQ-1"),
        ("addresses", "REQ-2"),
        ("addresses", "REQ-3"),
    ]


def test_relation_attributes_are_authored_inline(tmp_path: Path) -> None:
    qmd = tmp_path / "arch.qmd"
    qmd.write_text(
        "::: {.need #COMP-A type=\"component\" "
        "depends-on='CONTAINER-API technology=\"HTTPS/JSON\" label=\"calls over HTTPS\"'}\n"
        "## A\nText.\n:::\n",
        encoding="utf-8",
    )

    relations = parse_qmd(qmd, tmp_path)[0].relations

    assert [(relation.target, relation.attributes) for relation in relations] == [
        (
            "CONTAINER-API",
            {"technology": "HTTPS/JSON", "label": "calls over HTTPS"},
        )
    ]


def test_relation_attributes_apply_to_every_target_without_splitting_quoted_commas(
    tmp_path: Path,
) -> None:
    qmd = tmp_path / "arch.qmd"
    qmd.write_text(
        "::: {.need #COMP-A type=\"component\" "
        "depends-on='SYS-A, SYS-B technology=\"HTTP, JSON\"'}\n"
        "## A\nText.\n:::\n",
        encoding="utf-8",
    )

    relations = parse_qmd(qmd, tmp_path)[0].relations

    assert [(relation.target, relation.attributes) for relation in relations] == [
        ("SYS-A", {"technology": "HTTP, JSON"}),
        ("SYS-B", {"technology": "HTTP, JSON"}),
    ]


def test_relation_attribute_list_form_carries_attributes_per_item(
    tmp_path: Path,
) -> None:
    source = tmp_path / "arch.qmd"
    source.write_text(
        "::: {.need #COMP-A type=\"component\"}\n"
        "depends-on:\n"
        "  - CONTAINER-A technology=\"gRPC\"\n"
        "  - CONTAINER-B\n"
        "\n## A\nText.\n:::\n",
        encoding="utf-8",
    )

    relations = parse_qmd_declarations(source, tmp_path).declarations[0].relations

    assert [(relation.target, relation.attributes) for relation in relations] == [
        ("CONTAINER-A", {"technology": "gRPC"}),
        ("CONTAINER-B", {}),
    ]


def test_relation_attribute_bare_and_single_quoted_values(tmp_path: Path) -> None:
    qmd = tmp_path / "arch.qmd"
    qmd.write_text(
        "::: {.need #COMP-A type=\"component\"}\n"
        "depends-on: CONTAINER-A technology=gRPC label='calls'\n"
        "\n## A\nText.\n:::\n",
        encoding="utf-8",
    )

    relations = parse_qmd(qmd, tmp_path)[0].relations

    assert [(relation.target, relation.attributes) for relation in relations] == [
        ("CONTAINER-A", {"technology": "gRPC", "label": "calls"})
    ]


def test_relation_targets_without_attributes_keep_the_legacy_spelling(
    tmp_path: Path,
) -> None:
    qmd = tmp_path / "arch.qmd"
    qmd.write_text(
        "::: {.need #COMP-A type=\"component\" depends-on='SYS-A SYS-B'}\n"
        "## A\nText.\n:::\n",
        encoding="utf-8",
    )

    relations = parse_qmd(qmd, tmp_path)[0].relations

    assert [(relation.target, relation.attributes) for relation in relations] == [
        ("SYS-A SYS-B", {})
    ]


def test_malformed_relation_attribute_is_a_located_finding_and_keeps_the_target(
    tmp_path: Path,
) -> None:
    source = tmp_path / "arch.qmd"
    source.write_text(
        "::: {.need #COMP-A type=\"component\" "
        "depends-on='CONTAINER-A technology=\"unterminated'}\n"
        "## A\nText.\n:::\n",
        encoding="utf-8",
    )

    batch = parse_qmd_declarations(source, tmp_path)

    assert [
        (item.code, item.severity, item.object_id) for item in batch.findings
    ] == [("QND004", "error", "COMP-A")]
    relation = batch.declarations[0].relations[0]
    assert relation.target == "CONTAINER-A"
    assert relation.attributes == {}


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


def test_rationale_heading_is_indexed_and_body_stays_verbatim(tmp_path: Path) -> None:
    """The authoring manual keeps explanations in Markdown; this indexes them."""
    source = tmp_path / "rationale.qmd"
    source.write_text(
        "::: {.need #REQ-R type=\"system-requirement\" status=\"approved\"}\n"
        "\n## Authenticate\n"
        "The service shall authenticate users.\n"
        "\n### Rationale\n"
        "Protect privileged operations.\n"
        ":::\n",
        encoding="utf-8",
    )

    declaration = parse_qmd_declarations(source, tmp_path).declarations[0]

    assert declaration.rationale == "Protect privileged operations."
    # The body stays the authored text verbatim — extraction never rewrites it.
    assert "### Rationale" in declaration.body
    assert "Protect privileged operations." in declaration.body


def test_rationale_section_ends_at_the_next_heading(tmp_path: Path) -> None:
    source = tmp_path / "rationale-boundary.qmd"
    source.write_text(
        "::: {.need #REQ-R type=\"system-requirement\" status=\"approved\"}\n"
        "\n## Authenticate\n"
        "Body.\n"
        "\n### Rationale\n"
        "Protect privileged operations.\n"
        "\n### Confirmation\n"
        "Verified by login tests.\n"
        ":::\n",
        encoding="utf-8",
    )

    declaration = parse_qmd_declarations(source, tmp_path).declarations[0]

    assert declaration.rationale == "Protect privileged operations."
    assert "### Confirmation" in declaration.body
    assert "Verified by login tests." in declaration.body
    assert "Verified by login tests." not in declaration.rationale


def test_rationale_metadata_takes_precedence_over_body_heading(tmp_path: Path) -> None:
    source = tmp_path / "rationale-precedence.qmd"
    source.write_text(
        "::: {.need #REQ-R type=\"system-requirement\" status=\"approved\""
        " rationale=\"Protect the perimeter.\"}\n"
        "\n## Authenticate\n"
        "Body.\n"
        "\n### Rationale\n"
        "Protect privileged operations.\n"
        ":::\n",
        encoding="utf-8",
    )

    declaration = parse_qmd_declarations(source, tmp_path).declarations[0]

    assert declaration.rationale == "Protect the perimeter."


def test_bodies_without_a_rationale_heading_keep_an_empty_rationale(
    tmp_path: Path,
) -> None:
    source = tmp_path / "no-rationale.qmd"
    source.write_text(
        "::: {.need #REQ-PLAIN type=\"system-requirement\" status=\"approved\"}\n"
        "\n## Authenticate\n"
        "Body.\n"
        ":::\n",
        encoding="utf-8",
    )

    declaration = parse_qmd_declarations(source, tmp_path).declarations[0]

    assert declaration.rationale == ""
    assert declaration.body == "Body."


def test_rationale_heading_recognizes_the_established_portuguese_heading(
    tmp_path: Path,
) -> None:
    """``### Justificativa`` is this project's own pre-existing pt-BR heading.

    ``requirements.pt-BR.qmd`` and ``drivers.pt-BR.qmd`` already use
    "Justificativa" throughout (predating rationale-heading indexing);
    recognizing only the English word would silently leave the entire
    pt-BR corpus's rationale sections unindexed.
    """
    source = tmp_path / "rationale-pt-br.qmd"
    source.write_text(
        "::: {.need #REQ-R type=\"system-requirement\" status=\"approved\"}\n"
        "\n## Autenticar\n"
        "O serviço deve autenticar usuários.\n"
        "\n### Justificativa\n"
        "Proteger operações privilegiadas.\n"
        ":::\n",
        encoding="utf-8",
    )

    declaration = parse_qmd_declarations(source, tmp_path).declarations[0]

    assert declaration.rationale == "Proteger operações privilegiadas."
    assert "### Justificativa" in declaration.body


def test_rationale_heading_is_not_mistaken_for_the_title_when_no_title_heading_exists(
    tmp_path: Path,
) -> None:
    """A ``### Rationale`` heading must never be consumed as the block's title.

    Title detection scans for the first ``##+`` heading with no level
    restriction; without an exclusion, a block whose only heading is
    ``### Rationale`` had that heading stripped from the body as the
    "title" before rationale extraction ran, leaving rationale empty.
    """
    source = tmp_path / "rationale-only-heading.qmd"
    source.write_text(
        "::: {.need #REQ-R type=\"system-requirement\" status=\"approved\"}\n"
        "The service shall authenticate users.\n"
        "\n### Rationale\n"
        "Protect privileged operations.\n"
        ":::\n",
        encoding="utf-8",
    )

    declaration = parse_qmd_declarations(source, tmp_path).declarations[0]

    assert declaration.title == "REQ-R"
    assert declaration.rationale == "Protect privileged operations."


def test_repeated_preamble_key_reports_the_dropped_value(tmp_path: Path) -> None:
    """A repeated key keeps only its last value, so the loss must be visible.

    The preamble is a mapping. Without QND003 an author who writes two
    `verified-by:` lines loses the first target with no diagnostic, and the
    project still validates as fully traced.
    """
    source = tmp_path / "duplicate.qmd"
    source.write_text(
        "::: {.need #REQ-DUP}\n"
        "verified-by: TC-001\n"
        "verified-by: TC-002\n\n"
        "## Duplicate relation key\n"
        ":::\n",
        encoding="utf-8",
    )

    batch = parse_qmd_declarations(source, tmp_path)

    assert [
        (item.code, item.severity, item.object_id, item.location.line)
        for item in batch.findings
    ] == [("QND003", "error", "REQ-DUP", 3)]
    # The surviving value is still the last one; the finding reports the loss
    # rather than changing the merge semantics.
    assert [item.target for item in batch.declarations[0].relations] == ["TC-002"]


def test_distinct_preamble_keys_are_not_reported_as_duplicates(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clean.qmd"
    source.write_text(
        "::: {.need #REQ-CLEAN}\n"
        "verified-by: TC-001, TC-002\n"
        "implemented-by:\n"
        "  - COMP-001\n"
        "  - COMP-002\n\n"
        "## Multiple targets without repeating a key\n"
        ":::\n",
        encoding="utf-8",
    )

    batch = parse_qmd_declarations(source, tmp_path)

    assert batch.findings == ()
    assert [item.target for item in batch.declarations[0].relations] == [
        "TC-001",
        "TC-002",
        "COMP-001",
        "COMP-002",
    ]
