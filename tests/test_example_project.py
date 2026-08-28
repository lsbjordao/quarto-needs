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
    allowed_prefixes = (
        "STK-", "SYS-", "FUN-", "NFR-", "ADR-", "TC-", "RISK-",
        "COMP-", "IF-", "EVD-",
    )
    assert all(obj.id.startswith(allowed_prefixes) for obj in objects)
    assert not any(obj.id.startswith("IAM-") for obj in objects)
    assert {"approved", "in-review", "draft", "disapproved"} <= {
        obj.status for obj in objects
    }
    assert any(obj.attributes.get("priority") == "high" for obj in objects)
    assert all(obj.attributes.get("tags") for obj in objects)
    assert counts["stakeholder-need"] >= 5
    assert counts["system-requirement"] >= 8
    assert counts["functional-requirement"] >= 15
    assert counts["non-functional-requirement"] >= 10
    assert counts["architecture-decision"] >= 3
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
        f"TC-{number:03d}" for number in range(1, 18)
    }
    for test_case in passed_cases:
        evidence_targets = [
            rel.target for rel in test_case.relations if rel.type == "evidenced-by"
        ]
        assert evidence_targets == [test_case.id.replace("TC-", "EVD-")]
        assert by_id[evidence_targets[0]].type == "evidence"

    expected_system_tests = {
        "SYS-001": "TC-001",
        "SYS-002": "TC-004",
        "SYS-003": "TC-007",
        "SYS-004": "TC-010",
        "SYS-005": "TC-012",
        "SYS-006": "TC-017",
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
        "FUN-002": "RISK-001",
        "FUN-005": "RISK-002",
        "NFR-003": "RISK-003",
        "NFR-008": "RISK-004",
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

    decisions = [obj for obj in objects if obj.type == "architecture-decision"]
    assert all(obj.status == "accepted" for obj in decisions)
    assert all(any(rel.type == "addresses" for rel in obj.relations) for obj in decisions)
    assert all(any(rel.type == "applies-to" for rel in obj.relations) for obj in decisions)
    assert all(any(rel.type == "confirmed-by" for rel in obj.relations) for obj in decisions)


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_aegis_book_renders_generated_views():
    """Breaking the installed adapter or a real shortcode must fail the canonical book build."""
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
    functional = (output / "requirements" / "functional.html").read_text(encoding="utf-8")

    assert 'data-need-count="5"' in index
    assert "need-table-container" in index
    assert "need-flow" in traceability
    assert "need-matrix" in matrix
    assert "TC-017" in matrix
    assert "need-status-approved" in functional
    assert "need-priority-high" in functional
    assert "<svg" in diagrams
    assert '<pre class="mermaid' not in diagrams
    assert "<foreignobject" not in diagrams.lower()
    assert '<h2 class="need-heading anchored"' in functional
    assert 'id="FUN-001-rationale"' in functional

    system = (output / "requirements" / "system.html").read_text(encoding="utf-8")
    assert "need-relations" in system
    assert "Verified by" in functional
    assert "Implemented by" in functional
    assert "Need backlinks" in system
    assert "Source for" in system
    assert "FUN-001" in system
    governance = (output / "governance.html").read_text(encoding="utf-8")
    assert "Quality dashboard" in governance
    assert "Whole catalog" in governance
    assert "Approved requirements" in governance
    assert "Needs by type" in governance
    assert "Findings by severity" in governance
    assert "Dashboard report unavailable." not in governance
    assert 'class="need-inspector' in governance
    assert "Inspector: ADR-002" in governance
    assert "Declared in architecture/decisions.qmd" in governance
    assert governance.count("No needs match this query.") == 2

    assert "need-ref-missing" not in "\n".join(
        (index, traceability, matrix, functional, system, governance)
    )


def test_aegis_configuration_passes_its_own_strict_gates():
    from quarto_needs import cli

    assert cli.main(["--root", str(ROOT / "examples/book"), "quality", "--format", "json"]) == 0


def test_aegis_named_queries_resolve():
    from quarto_needs import cli

    assert cli.main(
        ["--root", str(ROOT / "examples/book"), "query", "approved-high-unverified"]
    ) == 0
    assert cli.main(["--root", str(ROOT / "examples/book"), "query", "evidence-gaps"]) == 0
    assert cli.main(["--root", str(ROOT / "examples/book"), "query", "accepted-decisions"]) == 0


def test_aegis_current_baseline_round_trips_to_an_empty_diff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """A baseline built from the current multilingual showcase round-trips cleanly."""
    import json as _json
    from datetime import datetime, timezone

    from quarto_needs import baseline as baseline_module, cli
    from quarto_needs.analysis import analyze_project
    from quarto_needs.config import load_config

    root = ROOT / "examples/book"
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    payload = baseline_module.build_baseline(result.snapshot, config)
    baseline_path = tmp_path / "quarto-needs.json"
    baseline_module.write_baseline(baseline_path, payload)

    reference_date = datetime.strptime(payload["referenceDate"], "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(int(reference_date.timestamp())))

    exit_code = cli.main(
        ["--root", str(root), "diff", str(baseline_path), "--format", "json"]
    )
    diff_payload = _json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert diff_payload["empty"] is True
    assert diff_payload["notices"] == []


def test_checked_in_aegis_baseline_is_a_valid_historical_artifact():
    import json as _json
    from jsonschema import Draft202012Validator

    schema = _json.loads((ROOT / "schemas" / "baseline-v1.schema.json").read_text(encoding="utf-8"))
    payload = _json.loads((ROOT / "examples/book/baselines/quarto-needs.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    assert payload["valid"] is True
    assert payload["schemaVersion"] == "1"
    assert any(item["id"].startswith("IAM-") for item in payload["objects"])


def test_aegis_impact_explains_a_removed_verification(tmp_path: Path, capsys):
    import json as _json
    import shutil as _shutil
    from quarto_needs import cli

    project = tmp_path / "book"
    _shutil.copytree(
        ROOT / "examples/book",
        project,
        ignore=_shutil.ignore_patterns("_book", ".quarto"),
    )

    from quarto_needs import baseline as baseline_module
    from quarto_needs.analysis import analyze_project
    from quarto_needs.config import load_config

    config = load_config(project)
    before = analyze_project(project, config=config)
    assert before.snapshot is not None
    baseline_path = project / "current-baseline.json"
    baseline_module.write_baseline(
        baseline_path,
        baseline_module.build_baseline(before.snapshot, config),
    )

    system = project / "requirements" / "system.qmd"
    system.write_text(
        system.read_text(encoding="utf-8").replace('verified-by="TC-001"', "", 1),
        encoding="utf-8",
    )

    assert cli.main([
        "--root", str(project), "impact", str(baseline_path),
        "--recompute-with", "current", "--format", "json",
    ]) == 0
    payload = _json.loads(capsys.readouterr().out)
    test_case = next(item for item in payload["impacted"] if item["id"] == "TC-001")
    assert test_case["origin"] == "SYS-001"
    assert test_case["path"] == ["SYS-001", "TC-001"]


def test_aegis_quality_report_projects_passing_gates():
    import json as _json
    from quarto_needs.cli import build

    root = ROOT / "examples/book"
    assert build(root, quiet=True) == 0
    graph = _json.loads((root / ".quarto-needs/needs.json").read_text(encoding="utf-8"))
    report = graph["extensions"]["quartoNeeds"]["report"]

    assert report["profile"] == "strict"
    assert report["configurationPresent"] is True
    assert report["summary"]["exitCode"] == 0
    assert report["summary"]["gateFailures"] == 0
    assert report["findings"]["counts"]["error"] == 0
    assert all(gate["passed"] for gate in report["gates"])
    assert {"approved-high-unverified", "evidence-gaps", "accepted-decisions"} <= set(report["scopes"])
