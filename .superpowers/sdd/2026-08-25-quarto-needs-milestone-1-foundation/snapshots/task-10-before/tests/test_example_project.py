from collections import Counter
from pathlib import Path
import shutil
import subprocess

import pytest

from quarto_needs.parser import parse_project
from quarto_needs.validation import validate


ROOT = Path(__file__).resolve().parents[1]


def test_aegis_example_is_large_and_traceable():
    """The Aegis IAM book is a complete, internally valid showcase graph."""
    objects = parse_project(ROOT / "examples/book")
    findings = validate(objects)
    counts = Counter(obj.type for obj in objects)

    assert len(objects) >= 60
    assert all(obj.id.startswith("IAM-") for obj in objects)
    assert {"approved", "in-review", "draft", "disapproved"} <= {
        obj.status for obj in objects
    }
    assert any(obj.attributes.get("priority") == "high" for obj in objects)
    assert all(obj.attributes.get("tags") for obj in objects)
    assert counts["stakeholder-need"] >= 5
    assert counts["system-requirement"] >= 8
    assert counts["functional-requirement"] >= 15
    assert counts["non-functional-requirement"] >= 10
    assert counts["test-case"] >= 15
    assert counts["risk"] >= 3
    assert counts["component"] >= 5
    assert counts["interface"] >= 3
    assert counts["evidence"] >= 5
    assert not [finding for finding in findings if finding.severity == "error"]

    approved = [
        obj
        for obj in objects
        if obj.status == "approved" and obj.type.endswith("requirement")
    ]
    assert approved
    assert all(
        any(rel.type in {"verified-by", "validated-by"} for rel in obj.relations)
        for obj in approved
    )
    assert all(
        any(rel.type == "implemented-by" for rel in obj.relations)
        for obj in approved
    )

    by_id = {obj.id: obj for obj in objects}
    assert all(
        obj.rationale or "### Rationale" in obj.body
        for obj in approved
        if obj.type in {"functional-requirement", "non-functional-requirement"}
    )
    assert all(
        by_id[rel.target].type == "test-case"
        for obj in approved
        for rel in obj.relations
        if rel.type in {"verified-by", "validated-by"}
    )
    assert all(
        by_id[rel.target].type in {"component", "interface"}
        for obj in approved
        for rel in obj.relations
        if rel.type == "implemented-by"
    )
    assert all(
        by_id[rel.target].status == "approved"
        for obj in approved
        for rel in obj.relations
        if rel.type == "derives-from"
    )

    passed_cases = [
        obj for obj in objects if obj.type == "test-case" and obj.status == "passed"
    ]
    assert {obj.id for obj in passed_cases} == {
        f"IAM-TC-{number:03d}" for number in range(1, 18)
    }
    for test_case in passed_cases:
        evidence_targets = [
            rel.target for rel in test_case.relations if rel.type == "evidenced-by"
        ]
        assert evidence_targets == [
            test_case.id.replace("IAM-TC-", "IAM-EVD-")
        ]
        assert by_id[evidence_targets[0]].type == "evidence"

    expected_system_tests = {
        "IAM-SYS-001": "IAM-TC-001",
        "IAM-SYS-002": "IAM-TC-004",
        "IAM-SYS-003": "IAM-TC-007",
        "IAM-SYS-004": "IAM-TC-010",
        "IAM-SYS-005": "IAM-TC-012",
        "IAM-SYS-006": "IAM-TC-017",
    }
    assert {
        system_id: next(
            rel.target
            for rel in by_id[system_id].relations
            if rel.type == "verified-by"
        )
        for system_id in expected_system_tests
    } == expected_system_tests

    expected_mitigations = {
        "IAM-FUN-002": "IAM-RISK-001",
        "IAM-FUN-005": "IAM-RISK-002",
        "IAM-NFR-003": "IAM-RISK-003",
        "IAM-NFR-008": "IAM-RISK-004",
    }
    assert {
        requirement_id: next(
            rel.target
            for rel in by_id[requirement_id].relations
            if rel.type == "mitigates"
        )
        for requirement_id in expected_mitigations
    } == expected_mitigations
    assert all(
        not any(rel.type == "mitigates" for rel in obj.relations)
        for obj in objects
        if obj.type == "risk"
    )
    assert all(
        by_id[rel.target].type == "risk"
        for obj in objects
        if obj.type.endswith("requirement")
        for rel in obj.relations
        if rel.type == "mitigates"
    )


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_aegis_book_renders_generated_views():
    """Breaking the installed adapter or a real shortcode must fail the showcase build."""
    subprocess.run(
        ["quarto", "render", "examples/book"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    output = ROOT / "examples" / "book" / "_book"
    index = (output / "index.html").read_text(encoding="utf-8")
    traceability = (output / "traceability.html").read_text(encoding="utf-8")
    matrix = (output / "matrices.html").read_text(encoding="utf-8")
    diagrams = (output / "diagrams.html").read_text(encoding="utf-8")
    functional = (output / "requirements" / "functional.html").read_text(
        encoding="utf-8"
    )

    assert 'data-need-count="5"' in index
    assert "need-table-container" in index
    assert "need-flow" in traceability
    assert "need-matrix" in matrix
    assert "IAM-TC-017" in matrix
    assert "need-status-approved" in functional
    assert "need-priority-high" in functional
    assert "<svg" in diagrams
    assert '<pre class="mermaid' not in diagrams
    assert "<foreignobject" not in diagrams.lower()
    assert '<h2 class="need-heading anchored"' in functional
    assert 'id="IAM-FUN-001-rationale"' in functional

    system = (output / "requirements" / "system.html").read_text(encoding="utf-8")
    assert "need-relations" in system
    assert "Verified by" in functional
    assert "Implemented by" in functional
    assert "Need backlinks" in system
    assert "Source for" in system
    assert "IAM-FUN-001" in system
    assert "need-ref-missing" not in "\n".join(
        (index, traceability, matrix, functional, system)
    )
