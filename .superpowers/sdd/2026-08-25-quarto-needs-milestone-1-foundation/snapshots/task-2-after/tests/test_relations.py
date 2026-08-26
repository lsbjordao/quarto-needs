from pathlib import Path

from quarto_needs.parser import parse_qmd
from quarto_needs.relations import DEFAULT_RELATION_CATALOG


def test_default_catalog_covers_every_legacy_and_inverse_authoring_name() -> None:
    assert DEFAULT_RELATION_CATALOG.names == (
        "conflicts-with", "constrains", "decomposes", "depends-on",
        "derived-from", "derives-from", "evidenced-by", "evidences",
        "implemented-by", "implements", "justified-by", "mitigates",
        "references", "refines", "validated-by", "verified-by", "verifies",
    )


def test_inverse_authoring_forms_share_semantic_families_and_swap_roles() -> None:
    implements = DEFAULT_RELATION_CATALOG.resolve("implements")
    implemented_by = DEFAULT_RELATION_CATALOG.resolve("implemented-by")

    assert implements.semantic_family == implemented_by.semantic_family == "implementation"
    assert (implements.source_role, implements.target_role) == (
        "implementation-artifact",
        "requirement",
    )
    assert (implemented_by.source_role, implemented_by.target_role) == (
        "requirement",
        "implementation-artifact",
    )
    assert implements.inverse_label == implemented_by.direct_label


def test_derived_from_preserves_authored_name_but_keeps_v1_normalization(tmp_path: Path) -> None:
    source = tmp_path / "requirements.qmd"
    source.write_text(
        "::: {.need #REQ-2 type=system-requirement}\n"
        "derived-from: REQ-1\n\n"
        "## Derived requirement\n"
        ":::\n",
        encoding="utf-8",
    )

    relation = parse_qmd(source)[0].relations[0]

    assert relation.authored_name == "derived-from"
    assert relation.type == "derives-from"
