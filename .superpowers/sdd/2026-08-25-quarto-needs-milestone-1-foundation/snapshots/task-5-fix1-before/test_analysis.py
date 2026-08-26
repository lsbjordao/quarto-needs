from collections import Counter
from pathlib import Path

import pytest
import quarto_needs

from quarto_needs.analysis import analyze_objects, analyze_project
from quarto_needs.diagnostics import Finding
from quarto_needs.model import EngineeringObject, Relation
from quarto_needs.relations import DEFAULT_RELATION_CATALOG


ROOT = Path(__file__).resolve().parents[1]


def test_analysis_snapshot_is_sorted_indexed_and_deeply_immutable() -> None:
    root = ROOT / "tests/fixtures/canonical"
    result = analyze_project(
        root,
        files=[root / "z-requirements.qmd", root / "a-tests.qmd"],
    )

    assert result.valid is True
    assert result.snapshot is not None
    assert [item.id for item in result.snapshot.objects] == [
        "A-REQ-001",
        "M-NEED-001",
        "Z-TC-001",
    ]
    assert [
        (item.source, item.authored_name, item.target)
        for item in result.snapshot.relations
    ] == [
        ("A-REQ-001", "derived-from", "M-NEED-001"),
        ("A-REQ-001", "verified-by", "Z-TC-001"),
    ]
    assert result.snapshot.relations[0].v1_name == "derives-from"
    assert tuple(
        item.target for item in result.snapshot.outgoing["A-REQ-001"]
    ) == ("M-NEED-001", "Z-TC-001")
    assert tuple(
        item.source for item in result.snapshot.incoming["Z-TC-001"]
    ) == ("A-REQ-001",)
    assert result.snapshot.metrics == {
        "requirements": 1,
        "approved": 1,
        "implemented": 0,
        "verified": 1,
        "implementation_coverage": 0.0,
        "verification_coverage": 100.0,
    }
    assert result.snapshot.generator_name == "quarto-needs"
    assert result.snapshot.generator_version == quarto_needs.__version__
    assert (
        result.snapshot.relation_catalog_version
        == DEFAULT_RELATION_CATALOG.version
    )
    with pytest.raises(TypeError):
        result.snapshot.objects_by_id["NEW"] = result.snapshot.objects[0]
    with pytest.raises(TypeError):
        result.snapshot.metrics["requirements"] = 0


def test_structurally_invalid_analysis_has_no_snapshot_and_keeps_all_declarations() -> None:
    source = ROOT / "tests/fixtures/canonical/invalid-duplicates.qmd"

    result = analyze_project(source.parent, files=[source])

    assert result.valid is False
    assert result.snapshot is None
    assert [item.id for item in result.declarations].count("DUP-1") == 2
    assert [
        (item.code, item.object_id)
        for item in result.findings
        if item.severity == "error"
    ] == [
        ("REQ004", "DUP-1"),
        ("REQ005", "DUP-1"),
    ]


def test_analysis_is_independent_of_explicit_file_order() -> None:
    root = ROOT / "tests/fixtures/canonical"

    forward = analyze_project(
        root,
        files=[root / "a-tests.qmd", root / "z-requirements.qmd"],
    )
    reverse = analyze_project(
        root,
        files=[root / "z-requirements.qmd", root / "a-tests.qmd"],
    )

    assert forward.snapshot == reverse.snapshot


def test_analysis_reads_each_selected_source_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = ROOT / "tests/fixtures/canonical"
    selected = {root / "a-tests.qmd", root / "z-requirements.qmd"}
    resolved_selected = {item.resolve() for item in selected}
    reads: Counter[Path] = Counter()
    original = Path.read_text

    def counted(path: Path, *args: object, **kwargs: object) -> str:
        resolved = path.resolve()
        if resolved in resolved_selected:
            reads[resolved] += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)

    result = analyze_project(root, files=selected)

    assert result.snapshot is not None
    assert reads == Counter({item.resolve(): 1 for item in selected})


def test_source_less_legacy_object_keeps_empty_location_and_provenance() -> None:
    legacy = EngineeringObject(
        "REQ-1",
        "functional-requirement",
        "Source-less",
        relations=[Relation("references", "REQ-1", "REQ-1")],
    )

    result = analyze_objects([legacy])

    assert result.snapshot is not None
    assert result.declarations[0].location is None
    assert result.snapshot.objects[0].locations == ()
    assert result.snapshot.relations[0].provenance == ()


@pytest.mark.parametrize(
    ("contents", "expected_code"),
    [
        ("::: {.need #BROKEN}\n## Unclosed\n", "QND001"),
        (
            "::: {.need #EMPTY}\n"
            "verified-by:\n\n"
            "## Empty relation\n"
            ":::\n",
            "QND002",
        ),
    ],
)
def test_parser_structural_findings_suppress_snapshots(
    tmp_path: Path,
    contents: str,
    expected_code: str,
) -> None:
    source = tmp_path / "broken.qmd"
    source.write_text(contents, encoding="utf-8")

    result = analyze_project(tmp_path, files=[source])

    assert result.snapshot is None
    assert [item.code for item in result.findings] == [expected_code]
    assert result.findings[0].location is not None
    assert result.findings[0].location.file == "broken.qmd"


def test_reported_findings_do_not_bypass_structural_validation() -> None:
    first = EngineeringObject(
        "DUP-1",
        "need",
        "First",
        relations=[Relation("references", "DUP-1", "UNKNOWN-1")],
    )
    second = EngineeringObject("DUP-1", "need", "Second")

    result = analyze_objects([first, second], reported_findings=[])

    assert result.snapshot is None
    assert [(item.code, item.object_id) for item in result.findings] == [
        ("REQ004", "DUP-1"),
        ("REQ005", "DUP-1"),
    ]


def test_unknown_legacy_relation_becomes_structural_finding() -> None:
    legacy = EngineeringObject(
        "REQ-1",
        "need",
        "Unsupported relation",
        relations=[Relation("custom-link", "REQ-1", "REQ-1")],
    )

    result = analyze_objects(
        [legacy],
        reported_findings=[Finding("INFO001", "info", "Preserved")],
    )

    assert result.snapshot is None
    assert [(item.code, item.message) for item in result.findings] == [
        ("REQ007", "Unsupported relation type custom-link on REQ-1"),
        ("INFO001", "Preserved"),
    ]
