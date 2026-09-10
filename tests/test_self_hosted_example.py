from __future__ import annotations

import re
from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.parser import parse_qmd_declarations
from quarto_needs.quality import build_quality_report


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "quarto-needs"
CHAPTERS = (
    "index",
    "context",
    "drivers",
    "requirements",
    "architecture",
    "implementation",
    "verification",
    "traceability",
    "change",
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
    assert len(result.snapshot.objects) == 190

    ids = {item.id for item in result.snapshot.objects}
    assert {
        "STK-001",
        "SYS-001",
        "FUN-004",
        "NFR-005",
        "ADR-001",
        "COMP-GRAPH",
        "SYS-QUARTO-NEEDS",
        "ACTOR-ENGINEER",
        "EXT-GITHUB",
        "EXT-OSLC",
        "CONTAINER-PYTHON-PKG",
        "CONTAINER-QUARTO-EXT",
        "IF-003",
        "SRC-GRAPH-OUTPUT",
        "SRC-GRAPH-EXPLORE",
        "SRC-IMPACT",
        "RISK-001",
        "TC-010",
        "EVD-010",
        "STK-007",
        "SYS-008",
        "FUN-014",
        "NFR-007",
        "COMP-GHISSUES",
        "IF-006",
        "SRC-GITHUB-HTTP",
        "SRC-GITHUB-ISSUES",
        "TC-020",
        "EVD-020",
    } <= ids


def test_self_hosted_c4_part_of_ownership_is_complete_and_exact() -> None:
    architecture = parse_qmd_declarations(EXAMPLE / "architecture.qmd", EXAMPLE)
    implementation = parse_qmd_declarations(EXAMPLE / "implementation.qmd", EXAMPLE)
    declarations = {
        item.id: item
        for item in (*architecture.declarations, *implementation.declarations)
    }

    expected_part_of = {
        "COMP-PARSER": ("CONTAINER-PYTHON-PKG",),
        "COMP-ANALYSIS": ("CONTAINER-PYTHON-PKG",),
        "COMP-RULES": ("CONTAINER-PYTHON-PKG",),
        "COMP-CLI": ("CONTAINER-PYTHON-PKG",),
        "COMP-EXTENSION": ("CONTAINER-QUARTO-EXT",),
        "COMP-GRAPH": ("CONTAINER-PYTHON-PKG",),
        "COMP-BASELINE": ("CONTAINER-PYTHON-PKG",),
        "COMP-I18N": ("CONTAINER-PYTHON-PKG",),
        "SRC-PARSER": ("COMP-PARSER",),
        "SRC-RELATIONS": ("COMP-ANALYSIS",),
        "SRC-ANALYSIS": ("COMP-ANALYSIS",),
        "SRC-RULES": ("COMP-RULES",),
        "SRC-QUALITY": ("COMP-RULES",),
        "SRC-QUERIES": ("COMP-ANALYSIS",),
        "SRC-GRAPH-OUTPUT": ("COMP-GRAPH",),
        "SRC-GRAPH-PROJECTION": ("COMP-GRAPH",),
        "SRC-GRAPH-CONTEXT": ("COMP-GRAPH",),
        "SRC-GRAPH-EXPLORE": ("COMP-GRAPH",),
        "SRC-MARGIN-SIDEBAR": ("COMP-EXTENSION",),
        "SRC-BASELINE": ("COMP-BASELINE",),
        "SRC-DIFF": ("COMP-BASELINE",),
        "SRC-IMPACT": ("COMP-BASELINE",),
        "SRC-PRE-RENDER": ("COMP-I18N",),
        "SRC-QUARTO-INTEGRATION": ("COMP-ANALYSIS",),
        "SRC-BOOTSTRAP": ("COMP-EXTENSION",),
    }
    actual_part_of = {
        object_id: tuple(
            relation.target
            for relation in declarations[object_id].relations
            if relation.authored_name == "part-of"
        )
        for object_id in expected_part_of
    }

    assert actual_part_of == expected_part_of


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


def test_self_hosted_source_modules_point_to_real_repository_files() -> None:
    result = analyze_project(EXAMPLE, config=load_config(EXAMPLE))
    assert result.snapshot is not None
    snapshot = result.snapshot

    modules = [item for item in snapshot.objects if item.type == "source-module"]
    assert len(modules) == 28

    for module in modules:
        path = str(module.attributes["path"])
        assert (ROOT / path).is_file(), f"missing source path for {module.id}: {path}"
        outgoing = snapshot.outgoing.get(module.id, ())
        assert any(edge.semantic_family == "implementation" for edge in outgoing), module.id


def test_self_hosted_model_exposes_pedagogical_queries() -> None:
    config = load_config(EXAMPLE)
    assert {
        "graph-exploration",
        "architecture-decisions",
        "verification-assets",
        "implementation-surface",
        "requirement-to-code",
        "localization-path",
        "adr-path",
        "change-analysis",
    } <= set(config.named_query_sources)


def test_self_hosted_pytest_bindings_point_to_real_test_functions() -> None:
    result = analyze_project(EXAMPLE, config=load_config(EXAMPLE))
    assert result.snapshot is not None

    bound = [
        item for item in result.snapshot.objects
        if item.type == "test-case" and "pytest-nodeid" in item.attributes
    ]
    assert {item.id for item in bound} == {
        "TC-004", "TC-005", "TC-006", "TC-009", "TC-011",
        "TC-014", "TC-015", "TC-016", "TC-017", "TC-018", "TC-019",
        "TC-020", "TC-021", "TC-022", "TC-023", "TC-024",
        "TC-025", "TC-026", "TC-027", "TC-028", "TC-029",
        "TC-030", "TC-031", "TC-032", "TC-034",
    }

    for item in bound:
        nodeid = str(item.attributes["pytest-nodeid"])
        path_text, separator, function_name = nodeid.partition("::")
        assert separator == "::", f"invalid pytest-nodeid on {item.id}: {nodeid}"
        path = ROOT / path_text
        assert path.is_file(), f"missing pytest file for {item.id}: {path_text}"
        source = path.read_text(encoding="utf-8")
        assert re.search(rf"^def\s+{re.escape(function_name)}\s*\(", source, re.MULTILINE), (
            f"missing pytest function for {item.id}: {nodeid}"
        )

    evidence = {
        item.id: item for item in result.snapshot.objects
        if item.id in {"EVD-004", "EVD-006", "EVD-009", "EVD-011"}
    }
    assert set(evidence) == {"EVD-004", "EVD-006", "EVD-009", "EVD-011"}
    for item in evidence.values():
        assert item.attributes["provider"] == "pytest"
        assert item.attributes["artifact"] == ".quarto-needs/evidence/pytest.json"


def test_custom_graph_instance_ids_do_not_implicitly_name_projection_files() -> None:
    shortcode = re.compile(r"\{\{<\s*need-graph\s+([^>]*)>\}\}")
    attr = re.compile(r'(id|projection|view)="([^"]+)"')

    for stem in CHAPTERS:
        for suffix in (".qmd", ".pt-BR.qmd"):
            path = EXAMPLE / f"{stem}{suffix}"
            text = path.read_text(encoding="utf-8")
            for match in shortcode.finditer(text):
                attrs = dict(attr.findall(match.group(1)))
                instance_id = attrs.get("id")
                if not instance_id or instance_id == "need-graph-1":
                    continue
                assert attrs.get("projection") or attrs.get("view"), (
                    f"{path.name}: need-graph id={instance_id!r} would be treated as a projection "
                    "filename unless projection= or view= is explicit"
                )


def test_derivation_is_authored_from_derived_requirement_to_source_need() -> None:
    result = analyze_project(EXAMPLE, config=load_config(EXAMPLE))
    assert result.snapshot is not None

    derives = {
        (edge.source, edge.target)
        for edge in result.snapshot.relations
        if edge.v1_name == "derives-from"
    }
    assert ("SYS-001", "STK-001") in derives
    assert ("FUN-004", "SYS-002") in derives
    assert ("STK-001", "SYS-001") not in derives
