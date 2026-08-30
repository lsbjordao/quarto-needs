from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import quarto_needs


CHECKS_SCHEMA_VERSION = "1"
CHECK_OUTCOMES = frozenset({"passed", "failed", "skipped"})


def _text_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def _ids(values: Iterable[object]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()}, key=_text_key)


def _split_ids(value: str | None) -> list[str]:
    if not value:
        return []
    return _ids(value.replace(";", ",").split(","))


def build_check_evidence(
    provider: str,
    provider_version: str,
    checks: Iterable[Mapping[str, Any]],
) -> dict[str, object]:
    """Build a deterministic provider-neutral machine-check payload."""
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in checks:
        check_id = str(raw["id"]).strip()
        if not check_id:
            raise ValueError("evidence check id must not be empty")
        if check_id in seen:
            raise ValueError(f"duplicate evidence check id: {check_id}")
        seen.add(check_id)
        outcome = str(raw["outcome"])
        if outcome not in CHECK_OUTCOMES:
            raise ValueError(f"invalid evidence check outcome {outcome!r}")
        entry: dict[str, object] = {
            "id": check_id,
            "outcome": outcome,
            "requirements": _ids(raw.get("requirements", ())),
            "testCases": _ids(raw.get("testCases", ())),
        }
        title = raw.get("title")
        if title is not None and str(title).strip():
            entry["title"] = str(title).strip()
        details = raw.get("details")
        if details is not None:
            if not isinstance(details, Mapping):
                raise ValueError(f"evidence check {check_id} details must be an object")
            entry["details"] = dict(details)
        normalized.append(entry)
    normalized.sort(key=lambda item: _text_key(str(item["id"])))
    counts = Counter(str(item["outcome"]) for item in normalized)
    return {
        "schemaVersion": CHECKS_SCHEMA_VERSION,
        "provider": provider,
        "providerVersion": provider_version,
        "generator": {"name": "quarto-needs", "version": quarto_needs.__version__},
        "summary": {
            "total": len(normalized),
            "passed": counts.get("passed", 0),
            "failed": counts.get("failed", 0),
            "skipped": counts.get("skipped", 0),
        },
        "checks": normalized,
    }


def _junit_outcome(case: ET.Element) -> str:
    if case.find("failure") is not None or case.find("error") is not None:
        return "failed"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def _junit_properties(case: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    properties = case.find("properties")
    if properties is None:
        return values
    for prop in properties.findall("property"):
        name = prop.get("name")
        value = prop.get("value")
        if name and value is not None:
            values[name] = value
    return values


def junit_xml_evidence(path: Path, *, provider_version: str = "junit-xml") -> dict[str, object]:
    """Normalize JUnit XML test cases into generic machine checks.

    Optional testcase properties `quarto-needs.requirement` and
    `quarto-needs.test-case` carry comma/semicolon-separated model IDs.
    """
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as error:
        raise ValueError(f"{path} is not valid JUnit XML: {error}") from error

    cases = root.findall(".//testcase")
    if root.tag == "testcase":
        cases = [root]
    checks: list[dict[str, object]] = []
    duplicate_counts: Counter[str] = Counter()
    for case in cases:
        classname = (case.get("classname") or "").strip()
        name = (case.get("name") or "").strip()
        base_id = f"{classname}::{name}" if classname else name
        if not base_id:
            raise ValueError(f"{path} contains a testcase without name")
        duplicate_counts[base_id] += 1
        check_id = base_id if duplicate_counts[base_id] == 1 else f"{base_id}#{duplicate_counts[base_id]}"
        props = _junit_properties(case)
        checks.append({
            "id": check_id,
            "title": name or check_id,
            "outcome": _junit_outcome(case),
            "requirements": _split_ids(props.get("quarto-needs.requirement")),
            "testCases": _split_ids(props.get("quarto-needs.test-case")),
            "details": {
                "classname": classname,
                "time": case.get("time") or "",
            },
        })
    return build_check_evidence("junit", provider_version, checks)


def coverage_json_evidence(
    path: Path,
    *,
    minimum_percent: float,
    requirements: Sequence[str] = (),
    test_cases: Sequence[str] = (),
) -> dict[str, object]:
    """Normalize coverage.py JSON total coverage into one threshold check."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} must contain a coverage.py JSON object")
    meta = document.get("meta")
    totals = document.get("totals")
    if not isinstance(meta, dict) or not isinstance(totals, dict):
        raise ValueError(f"{path} is missing coverage.py meta/totals")
    version = str(meta.get("version") or "unknown")
    raw_percent = totals.get("percent_covered")
    if isinstance(raw_percent, bool) or not isinstance(raw_percent, (int, float)):
        raise ValueError(f"{path} has no numeric totals.percent_covered")
    percent = float(raw_percent)
    outcome = "passed" if percent >= minimum_percent else "failed"
    return build_check_evidence(
        "coverage.py",
        version,
        [{
            "id": "coverage:total",
            "title": "Total code coverage",
            "outcome": outcome,
            "requirements": requirements,
            "testCases": test_cases,
            "details": {
                "percentCovered": percent,
                "minimumPercent": float(minimum_percent),
                "coveredLines": totals.get("covered_lines"),
                "numStatements": totals.get("num_statements"),
            },
        }],
    )


def process_evidence(
    *,
    provider: str,
    provider_version: str,
    check_id: str,
    exit_code: int,
    title: str | None = None,
    requirements: Sequence[str] = (),
    test_cases: Sequence[str] = (),
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Normalize a bounded process result such as Quarto, lint, or type-check."""
    merged_details = {"exitCode": int(exit_code)}
    if details:
        merged_details.update(details)
    return build_check_evidence(
        provider,
        provider_version,
        [{
            "id": check_id,
            "title": title or check_id,
            "outcome": "passed" if exit_code == 0 else "failed",
            "requirements": requirements,
            "testCases": test_cases,
            "details": merged_details,
        }],
    )


def quarto_render_evidence(
    *,
    quarto_version: str,
    target: str,
    exit_code: int,
    requirements: Sequence[str] = (),
    test_cases: Sequence[str] = (),
) -> dict[str, object]:
    return process_evidence(
        provider="quarto-render",
        provider_version=quarto_version,
        check_id=f"quarto-render:{target}",
        title=f"Quarto render: {target}",
        exit_code=exit_code,
        requirements=requirements,
        test_cases=test_cases,
        details={"target": target},
    )


def json_schema_evidence(
    validations: Iterable[Mapping[str, object]],
    *,
    validator_version: str,
) -> dict[str, object]:
    """Normalize already-performed JSON Schema validations.

    Each validation must provide `id` and `valid`; it may also provide title,
    requirements, testCases, schema, and instance metadata. Validation itself
    stays with the caller so this adapter cannot execute arbitrary schemas or
    external references behind the user's back.
    """
    checks: list[dict[str, object]] = []
    for validation in validations:
        check_id = str(validation["id"])
        valid = validation.get("valid")
        if not isinstance(valid, bool):
            raise ValueError(f"JSON Schema validation {check_id} valid must be boolean")
        details: dict[str, object] = {}
        for key in ("schema", "instance", "errors"):
            if key in validation:
                details[key] = validation[key]
        checks.append({
            "id": check_id,
            "title": validation.get("title", check_id),
            "outcome": "passed" if valid else "failed",
            "requirements": validation.get("requirements", ()),
            "testCases": validation.get("testCases", ()),
            "details": details,
        })
    return build_check_evidence("json-schema", validator_version, checks)


def lint_evidence(
    *,
    tool: str,
    tool_version: str,
    exit_code: int,
    requirements: Sequence[str] = (),
    test_cases: Sequence[str] = (),
) -> dict[str, object]:
    return process_evidence(
        provider=f"lint:{tool}",
        provider_version=tool_version,
        check_id=f"lint:{tool}",
        title=f"Lint: {tool}",
        exit_code=exit_code,
        requirements=requirements,
        test_cases=test_cases,
    )


def type_check_evidence(
    *,
    tool: str,
    tool_version: str,
    exit_code: int,
    requirements: Sequence[str] = (),
    test_cases: Sequence[str] = (),
) -> dict[str, object]:
    return process_evidence(
        provider=f"type-check:{tool}",
        provider_version=tool_version,
        check_id=f"type-check:{tool}",
        title=f"Type check: {tool}",
        exit_code=exit_code,
        requirements=requirements,
        test_cases=test_cases,
    )
