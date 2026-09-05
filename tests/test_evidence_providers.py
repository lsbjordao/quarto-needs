from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from quarto_needs.evidence_providers import (
    build_check_evidence,
    coverage_json_evidence,
    json_schema_evidence,
    junit_xml_evidence,
    lint_evidence,
    quarto_render_evidence,
    type_check_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas" / "evidence-checks-v1.schema.json").read_text(encoding="utf-8")
)


def test_generic_check_evidence_is_deterministic_and_schema_valid() -> None:
    checks = [
        {
            "id": "z-check",
            "outcome": "failed",
            "requirements": ["FUN-002", "FUN-001", "FUN-001"],
            "testCases": ["TC-002"],
        },
        {
            "id": "a-check",
            "outcome": "passed",
            "requirements": [],
            "testCases": [],
        },
    ]
    first = build_check_evidence("example", "1.0", checks)
    second = build_check_evidence("example", "1.0", reversed(checks))
    assert first == second
    assert [item["id"] for item in first["checks"]] == ["a-check", "z-check"]
    assert first["checks"][1]["requirements"] == ["FUN-001", "FUN-002"]
    assert first["summary"] == {"total": 2, "passed": 1, "failed": 1, "skipped": 0}
    Draft202012Validator(SCHEMA).validate(first)


def test_junit_adapter_normalizes_outcomes_and_traceability(tmp_path: Path) -> None:
    report = tmp_path / "junit.xml"
    report.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="suite" tests="3">
  <testcase classname="pkg.test_mod" name="test_ok" time="0.1">
    <properties>
      <property name="quarto-needs.requirement" value="FUN-002; FUN-001"/>
      <property name="quarto-needs.test-case" value="TC-001"/>
    </properties>
  </testcase>
  <testcase classname="pkg.test_mod" name="test_fail"><failure message="boom"/></testcase>
  <testcase classname="pkg.test_mod" name="test_skip"><skipped/></testcase>
</testsuite>
""",
        encoding="utf-8",
    )
    payload = junit_xml_evidence(report, provider_version="1")
    Draft202012Validator(SCHEMA).validate(payload)
    assert payload["summary"] == {"total": 3, "passed": 1, "failed": 1, "skipped": 1}
    by_id = {item["id"]: item for item in payload["checks"]}
    linked = by_id["pkg.test_mod::test_ok"]
    assert linked["requirements"] == ["FUN-001", "FUN-002"]
    assert linked["testCases"] == ["TC-001"]
    assert by_id["pkg.test_mod::test_fail"]["outcome"] == "failed"
    assert by_id["pkg.test_mod::test_skip"]["outcome"] == "skipped"


def test_coverage_adapter_applies_explicit_threshold(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(
        json.dumps(
            {
                "meta": {"version": "7.6.0"},
                "totals": {
                    "percent_covered": 87.5,
                    "covered_lines": 875,
                    "num_statements": 1000,
                },
            }
        ),
        encoding="utf-8",
    )
    passed = coverage_json_evidence(
        report,
        minimum_percent=85,
        requirements=["NFR-001"],
        test_cases=["TC-020"],
    )
    failed = coverage_json_evidence(report, minimum_percent=90)
    Draft202012Validator(SCHEMA).validate(passed)
    assert passed["provider"] == "coverage.py"
    assert passed["providerVersion"] == "7.6.0"
    assert passed["checks"][0]["outcome"] == "passed"
    assert passed["checks"][0]["requirements"] == ["NFR-001"]
    assert failed["checks"][0]["outcome"] == "failed"


def test_quarto_lint_and_type_check_adapters_preserve_tool_identity() -> None:
    quarto = quarto_render_evidence(
        quarto_version="1.8.24",
        target="docs/src",
        exit_code=0,
        requirements=["FUN-001"],
    )
    lint = lint_evidence(tool="ruff", tool_version="0.12", exit_code=1)
    typing = type_check_evidence(tool="mypy", tool_version="1.17", exit_code=0)
    for payload in (quarto, lint, typing):
        Draft202012Validator(SCHEMA).validate(payload)
    assert quarto["provider"] == "quarto-render"
    assert quarto["checks"][0]["outcome"] == "passed"
    assert lint["provider"] == "lint:ruff"
    assert lint["checks"][0]["outcome"] == "failed"
    assert typing["provider"] == "type-check:mypy"
    assert typing["checks"][0]["outcome"] == "passed"


def test_json_schema_adapter_normalizes_precomputed_validation_results() -> None:
    payload = json_schema_evidence(
        [
            {
                "id": "schema:public-graph",
                "title": "Public graph schema",
                "valid": True,
                "schema": "schemas/public-graph-v1.schema.json",
                "instance": ".quarto-needs/graph.json",
                "requirements": ["NFR-004"],
                "testCases": ["TC-006"],
            },
            {
                "id": "schema:broken",
                "valid": False,
                "errors": 2,
            },
        ],
        validator_version="jsonschema-4",
    )
    Draft202012Validator(SCHEMA).validate(payload)
    assert payload["summary"] == {"total": 2, "passed": 1, "failed": 1, "skipped": 0}
    assert payload["checks"][0]["id"] == "schema:broken"
    assert payload["checks"][1]["testCases"] == ["TC-006"]
