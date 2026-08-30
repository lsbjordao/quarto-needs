from pathlib import Path

from quarto_needs.parser import parse_qmd
from quarto_needs.relations import DEFAULT_RELATION_CATALOG


def test_default_catalog_covers_legacy_and_decision_authoring_names() -> None:
    expected = {
        "conflicts-with", "constrains", "decomposes", "depends-on",
        "derived-from", "derives-from", "evidenced-by", "evidences",
        "implemented-by", "implements", "justified-by", "mitigates",
        "references", "refines", "validated-by", "verified-by", "verifies",
        "addresses", "addressed-by", "applies-to", "confirmed-by", "confirms",
        "supersedes", "superseded-by",
    }
    assert set(DEFAULT_RELATION_CATALOG.names) == expected
    assert DEFAULT_RELATION_CATALOG.version == "3"


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


def test_decision_relations_define_roles_and_impact_directions() -> None:
    addresses = DEFAULT_RELATION_CATALOG.resolve("addresses")
    applies_to = DEFAULT_RELATION_CATALOG.resolve("applies-to")
    supersedes = DEFAULT_RELATION_CATALOG.resolve("supersedes")
    confirmed_by = DEFAULT_RELATION_CATALOG.resolve("confirmed-by")

    assert addresses.semantic_family == "decision-addressing"
    assert (addresses.source_role, addresses.target_role) == ("decision", "driver")
    assert addresses.impact_direction == "target_to_source"
    assert addresses.traversal_direction == "target_to_source"

    assert applies_to.semantic_family == "decision-scope"
    assert (applies_to.source_role, applies_to.target_role) == (
        "decision",
        "architecture-element",
    )
    assert applies_to.traversal_direction == "source_to_target"

    assert supersedes.semantic_family == "decision-lineage"
    assert (supersedes.source_role, supersedes.target_role) == (
        "successor",
        "predecessor",
    )
    assert supersedes.traversal_direction == "target_to_source"

    assert confirmed_by.semantic_family == "decision-confirmation"
    assert confirmed_by.impact_direction == "both"
    assert confirmed_by.traversal_direction == "source_to_target"


def test_parser_resolves_inverse_relation_names(tmp_path: Path) -> None:
    source = tmp_path / "needs.qmd"
    source.write_text(
        '''
::: {.need #REQ-1 type="functional-requirement" status="approved" implemented-by="COMP-1"}
## Requirement
:::

::: {.need #COMP-1 type="component" status="approved"}
## Component
:::
'''.strip() + "\n",
        encoding="utf-8",
    )
    batch = parse_qmd(source, tmp_path)
    relation = batch.declarations[0].relations[0]
    assert relation.authored_name == "implemented-by"
    assert relation.target == "COMP-1"
