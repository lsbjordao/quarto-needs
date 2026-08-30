from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def test_self_hosted_evidence_flow_attests_before_validation_and_render() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "--quarto-needs-evidence=examples/quarto-needs/.quarto-needs/evidence/pytest-provider.json" in text
    assert "-m quarto_needs.cli_entry --root examples/quarto-needs evidence attest" in text
    assert ".quarto-needs/evidence/pytest-provider.json" in text
    assert "--output .quarto-needs/evidence/pytest.json --expires-hours 24" in text
    assert "-m quarto_needs.cli_entry --root examples/quarto-needs evidence check" in text
    assert ".quarto-needs/evidence/pytest.json" in text
    assert "render-self-example: evidence-self-example" in text


def test_self_hosted_evidence_flow_executes_all_modeled_pytest_bindings() -> None:
    text = MAKEFILE.read_text(encoding="utf-8")
    expected = (
        "tests/test_architecture_decisions.py::test_accepted_decision_passes_decision_governance",
        "tests/test_localization.py::test_localized_source_semantic_parity_rejects_model_drift",
        "tests/test_graph_semantics.py::test_public_projection_publishes_catalog_semantics",
        "tests/test_graph_semantics.py::test_named_query_is_materialized_as_reusable_graph_view",
        "tests/test_impact.py::test_editing_a_requirement_impacts_its_verification",
        "tests/test_graph_assets.py::test_margin_sidebar_toggle_stays_entirely_outside_page_toc",
    )
    for nodeid in expected:
        assert nodeid in text
