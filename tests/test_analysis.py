from collections import Counter
from pathlib import Path

import pytest
import quarto_needs

from quarto_needs.analysis import analyze_objects, analyze_project
from quarto_needs.diagnostics import Finding
from quarto_needs.model import EngineeringObject, Relation
from quarto_needs.relations import DEFAULT_RELATION_CATALOG
from quarto_needs.snapshot import LocationRecord, thaw_json


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


def test_analysis_deduplicates_repeated_selected_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = ROOT / "tests/fixtures/canonical"
    source = root / "a-tests.qmd"
    reads: Counter[Path] = Counter()
    original = Path.read_text

    def counted(path: Path, *args: object, **kwargs: object) -> str:
        if path.resolve() == source.resolve():
            reads[path.resolve()] += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)

    result = analyze_project(root, files=[source, source])

    assert result.snapshot is not None
    assert [item.id for item in result.declarations] == ["Z-TC-001"]
    assert reads == Counter({source.resolve(): 1})


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


def _approved_requirement_qmd(need_id: str) -> str:
    return (
        f'::: {{.need #{need_id} type="system-requirement" status="approved"}}\n'
        f"\n## {need_id}\n"
        "Body.\n"
        ":::\n"
    )


def test_validation_warnings_do_not_prevent_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "req.qmd"
    source.write_text(_approved_requirement_qmd("REQ-1"), encoding="utf-8")

    result = analyze_project(tmp_path, files=[source])

    assert result.valid is True
    assert result.snapshot is not None
    # Characterization: REQ002/REQ006 carry no location and sort by code.
    assert [
        (item.code, item.severity, item.object_id, item.message, item.location)
        for item in result.findings
    ] == [
        ("REQ002", "warning", "REQ-1", "REQ-1 has no rationale", None),
        (
            "REQ006",
            "warning",
            "REQ-1",
            "REQ-1 is approved but has no verification relation",
            None,
        ),
    ]


def test_warnings_are_still_reported_when_the_snapshot_is_blocked(
    tmp_path: Path,
) -> None:
    # Characterization: REQ002/REQ006 are computed pre-snapshot, so they stay
    # observable even when a structural error blocks construction. Identical
    # warnings on duplicate IDs deduplicate into one finding each.
    first = tmp_path / "a.qmd"
    second = tmp_path / "z.qmd"
    for path in (first, second):
        path.write_text(_approved_requirement_qmd("REQ-DUP"), encoding="utf-8")

    result = analyze_project(tmp_path, files=[first, second])

    assert result.snapshot is None
    assert [
        (item.code, item.severity, item.object_id, item.location)
        for item in result.findings
    ] == [
        ("REQ004", "error", "REQ-DUP", LocationRecord("a.qmd", 1, "REQ-DUP")),
        ("REQ002", "warning", "REQ-DUP", None),
        ("REQ006", "warning", "REQ-DUP", None),
    ]


def test_unknown_target_blocks_snapshot_with_resolved_relation_and_owner_location(
    tmp_path: Path,
) -> None:
    # Characterization: the REQ005 message names the resolved v1 relation and
    # the finding carries the owning object's location, not the token's.
    source = tmp_path / "req.qmd"
    source.write_text(
        '::: {.need #REQ-1 type="need" verified-by="TC-404"}\n\n## REQ-1\nBody.\n:::\n',
        encoding="utf-8",
    )

    result = analyze_project(tmp_path, files=[source])

    assert result.snapshot is None
    assert [
        (item.code, item.severity, item.object_id, item.message, item.location)
        for item in result.findings
    ] == [
        (
            "REQ005",
            "error",
            "REQ-1",
            "REQ-1 references unknown object TC-404 via verified-by",
            LocationRecord("req.qmd", 1, "REQ-1"),
        ),
    ]


def test_verified_relation_satisfies_req006_even_when_its_target_is_unknown(
    tmp_path: Path,
) -> None:
    # Characterization: REQ006 inspects relation presence only; target
    # existence is REQ005's concern.
    source = tmp_path / "req.qmd"
    source.write_text(
        "::: {.need #REQ-1 type=\"system-requirement\" status=\"approved\"}\n"
        "verified-by: TC-GHOST\n"
        "\n## REQ-1\nBody.\n:::\n",
        encoding="utf-8",
    )

    result = analyze_project(tmp_path, files=[source])

    assert result.snapshot is None
    # REQ006 stays silent (relation presence is enough); the approved,
    # rationale-less requirement still earns REQ002.
    assert [item.code for item in result.findings] == ["REQ005", "REQ002"]


def test_findings_and_snapshot_are_equivalent_under_file_order_permutation(
    tmp_path: Path,
) -> None:
    governed = tmp_path / "a.qmd"
    governed.write_text(
        "::: {.need #REQ-B type=\"system-requirement\" status=\"approved\"}\n"
        "verified-by: GHOST-TC\n"
        "\n## REQ-B\nBody.\n:::\n",
        encoding="utf-8",
    )
    plain = tmp_path / "z.qmd"
    plain.write_text(
        '::: {.need #REQ-A type="system-requirement"}\n\n## REQ-A\nBody.\n:::\n',
        encoding="utf-8",
    )

    forward = analyze_project(tmp_path, files=[governed, plain])
    reverse = analyze_project(tmp_path, files=[plain, governed])

    assert forward == reverse
    assert [(item.code, item.object_id) for item in forward.findings] == [
        ("REQ005", "REQ-B"),
        ("REQ002", "REQ-A"),
        ("REQ002", "REQ-B"),
    ]


def test_snapshot_indexes_cover_every_object_with_canonical_relations(
    tmp_path: Path,
) -> None:
    source = tmp_path / "req.qmd"
    source.write_text(
        '::: {.need #REQ-1 type="need" verified-by="TC-1"}\n\n## REQ-1\nBody.\n:::\n'
        '::: {.need #TC-1 type="need"}\n\n## TC-1\nBody.\n:::\n'
        '::: {.need #REQ-2 type="need"}\n\n## REQ-2\nBody.\n:::\n',
        encoding="utf-8",
    )

    result = analyze_project(tmp_path, files=[source])

    assert result.snapshot is not None
    snapshot = result.snapshot
    assert set(snapshot.outgoing) == {"REQ-1", "TC-1", "REQ-2"}
    assert set(snapshot.incoming) == {"REQ-1", "TC-1", "REQ-2"}
    assert snapshot.outgoing["REQ-2"] == ()
    assert snapshot.outgoing["TC-1"] == ()
    assert snapshot.incoming["REQ-1"] == ()
    assert snapshot.incoming["REQ-2"] == ()
    edge = snapshot.relations[0]
    assert snapshot.outgoing["REQ-1"] == (edge,)
    assert snapshot.incoming["TC-1"] == (edge,)
    assert all(
        relation in snapshot.relations
        for group in (*snapshot.outgoing.values(), *snapshot.incoming.values())
        for relation in group
    )


def test_snapshot_index_construction_is_linear(tmp_path: Path) -> None:
    """Regression guard against the removed O(V*E) construction pattern.

    4,000 objects with 16,000 relations must analyze in a few seconds at
    most; the replaced pattern (one full relation scan per object) costs
    four scans worth of comparisons per object and takes tens of seconds at
    this size. The bound is deliberately generous — the AST contract in
    ``test_semantic_kernel_contract.py`` guards the pattern deterministically,
    this only proves the construction stays practical at scale.
    """
    import time

    blocks = []
    for index in range(4_000):
        targets = "; ".join(
            f"OBJ-{(index + offset) % 4_000:05d}" for offset in range(1, 5)
        )
        blocks.append(
            f'::: {{.need #OBJ-{index:05d} type="need"}}\n'
            f"derives-from: {targets}\n"
            f"\n## OBJ-{index:05d}\n"
            "Body.\n"
            ":::\n"
        )
    source = tmp_path / "scale.qmd"
    source.write_text("\n".join(blocks), encoding="utf-8")

    started = time.monotonic()
    result = analyze_project(tmp_path, files=[source])
    elapsed = time.monotonic() - started

    assert result.snapshot is not None
    assert len(result.snapshot.objects) == 4_000
    assert len(result.snapshot.relations) == 16_000
    assert elapsed < 3.0, f"analysis took {elapsed:.2f}s"


def test_finding_order_includes_anchor_and_canonical_properties() -> None:
    legacy = EngineeringObject("REQ-1", "need", "Canonical findings")
    findings = [
        Finding(
            "CUSTOM001",
            "warning",
            "Same message",
            "REQ-1",
            LocationRecord("source.qmd", 4, "z-anchor"),
            {"nested": {"rank": 1}},
        ),
        Finding(
            "CUSTOM001",
            "warning",
            "Same message",
            "REQ-1",
            LocationRecord("source.qmd", 4, "a-anchor"),
            {"nested": {"rank": 2}},
        ),
        Finding(
            "CUSTOM001",
            "warning",
            "Same message",
            "REQ-1",
            LocationRecord("source.qmd", 4, "a-anchor"),
            {"nested": {"rank": 1}},
        ),
        Finding(
            "CUSTOM001",
            "warning",
            "Same message",
            "REQ-1",
            LocationRecord("source.qmd", 4, "m-anchor"),
            {"kind": True},
        ),
        Finding(
            "CUSTOM001",
            "warning",
            "Same message",
            "REQ-1",
            LocationRecord("source.qmd", 4, "m-anchor"),
            {"kind": 1},
        ),
    ]

    forward = analyze_objects([legacy], reported_findings=findings)
    reverse = analyze_objects([legacy], reported_findings=reversed(findings))

    assert forward.snapshot == reverse.snapshot
    assert forward.snapshot is not None
    assert [
        (
            item.location.anchor if item.location else None,
            thaw_json(item.properties),
        )
        for item in forward.findings
    ] == [
        ("a-anchor", {"nested": {"rank": 1}}),
        ("a-anchor", {"nested": {"rank": 2}}),
        ("m-anchor", {"kind": 1}),
        ("m-anchor", {"kind": True}),
        ("z-anchor", {"nested": {"rank": 1}}),
    ]
