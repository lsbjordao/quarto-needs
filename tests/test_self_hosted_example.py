from __future__ import annotations

from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.parser import parse_qmd_declarations
from quarto_needs.quality import build_quality_report


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "quarto-needs"
CHAPTERS = (
    "index",
    "drivers",
    "requirements",
    "architecture",
    "verification",
    "traceability",
)


def _relation_signature(declaration):
    return tuple(
        sorted((relation.authored_name, relation.target) for relation in declaration.relations)
    )


def _semantic_signature(declaration):
    return (
        declaration.id,
        declaration.type,
        declaration.status,
        declaration.attributes,
        _relation_signature(declaration),
    )


def test_self_hosted_example_is_a_valid_engineering_graph() -> None:
    config = load_config(EXAMPLE)
    result = analyze_project(EXAMPLE, config=config)

    assert result.snapshot is not None
    assert result.findings == ()
    assert len(result.snapshot.objects) == 72

    ids = {item.id for item in result.snapshot.objects}
    assert {
        "STK-001",
        "SYS-001",
        "FUN-004",
        "NFR-005",
        "ADR-001",
        "COMP-GRAPH",
        "IF-003",
        "RISK-001",
        "TC-010",
        "EVD-010",
    } <= ids


def test_self_hosted_example_passes_strict_quality_gates() -> None:
    report = build_quality_report(EXAMPLE)

    assert report.profile == "strict"
    assert report.structural_errors is False
    assert report.gate_failures() == 0
    assert report.exit_code() == 0
    assert all(gate.passed for gate in report.gates)


def test_self_hosted_pt_br_sources_preserve_canonical_semantics() -> None:
    for stem in CHAPTERS:
        canonical = parse_qmd_declarations(EXAMPLE / f"{stem}.qmd", EXAMPLE)
        translated = parse_qmd_declarations(EXAMPLE / f"{stem}.pt-BR.qmd", EXAMPLE)

        canonical_by_id = {item.id: item for item in canonical.declarations}
        translated_by_id = {item.id: item for item in translated.declarations}
        assert set(translated_by_id) == set(canonical_by_id), stem

        for object_id in canonical_by_id:
            assert _semantic_signature(translated_by_id[object_id]) == _semantic_signature(
                canonical_by_id[object_id]
            ), f"semantic drift in {stem}: {object_id}"


def test_self_hosted_model_contains_complete_requirement_to_evidence_chains() -> None:
    result = analyze_project(EXAMPLE, config=load_config(EXAMPLE))
    assert result.snapshot is not None
    snapshot = result.snapshot

    requirements = [
        item for item in snapshot.objects
        if item.type in {
            "system-requirement",
            "functional-requirement",
            "non-functional-requirement",
        }
        and item.status == "approved"
    ]
    for requirement in requirements:
        outgoing = snapshot.outgoing.get(requirement.id, ())
        assert any(edge.semantic_family == "implementation" for edge in outgoing), requirement.id
        verification = [edge for edge in outgoing if edge.semantic_family == "verification"]
        assert verification, requirement.id
        for edge in verification:
            test_outgoing = snapshot.outgoing.get(edge.target, ())
            assert any(item.semantic_family == "evidence" for item in test_outgoing), edge.target
