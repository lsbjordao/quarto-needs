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


def test_engineering_object_to_dict_omits_authored_name() -> None:
    """authored_name is additive internal state and must stay out of v1 output."""
    from quarto_needs.model import EngineeringObject, Relation

    obj = EngineeringObject(id="REQ-1", type="functional-requirement", title="T", status="draft")
    obj.relations.append(Relation("derives-from", "REQ-1", "STK-1", {}))
    obj.relations[0].authored_name = "derived-from"

    payload = obj.to_dict()

    assert payload["relations"][0]["type"] == "derives-from"
    assert "authored_name" not in payload["relations"][0]
