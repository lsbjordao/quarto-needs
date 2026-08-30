from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import quarto_needs

from .snapshot import AnalysisSnapshot, thaw_json


EVIDENCE_SCHEMA_VERSION = "1"
PYTEST_OUTCOMES = frozenset({"passed", "failed", "skipped"})


@dataclass(frozen=True, slots=True)
class EvidenceIssue:
    code: str
    message: str
    nodeid: str | None = None
    object_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.nodeid is not None:
            payload["nodeid"] = self.nodeid
        if self.object_id is not None:
            payload["objectId"] = self.object_id
        return payload


def _text_key(value: str) -> tuple[str, str]:
    return (value.casefold(), value)


def build_pytest_evidence(
    records: Iterable[Mapping[str, Any]], *, provider_version: str
) -> dict[str, object]:
    """Build a deterministic pytest evidence artifact."""
    tests: list[dict[str, object]] = []
    for raw in records:
        nodeid = str(raw["nodeid"])
        outcome = str(raw["outcome"])
        requirements = tuple(sorted({str(v) for v in raw.get("requirements", ())}, key=_text_key))
        test_cases = tuple(sorted({str(v) for v in raw.get("testCases", ())}, key=_text_key))
        tests.append({"nodeid": nodeid, "outcome": outcome, "requirements": list(requirements), "testCases": list(test_cases)})
    tests.sort(key=lambda item: _text_key(str(item["nodeid"])))
    counts = Counter(str(item["outcome"]) for item in tests)
    return {
        "schemaVersion": EVIDENCE_SCHEMA_VERSION,
        "provider": "pytest",
        "providerVersion": provider_version,
        "generator": {"name": "quarto-needs", "version": quarto_needs.__version__},
        "summary": {"total": len(tests), "passed": counts.get("passed", 0), "failed": counts.get("failed", 0), "skipped": counts.get("skipped", 0)},
        "tests": tests,
    }


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def load_pytest_evidence(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    if payload.get("schemaVersion") != EVIDENCE_SCHEMA_VERSION:
        raise ValueError(f"{path} has unsupported evidence schemaVersion {payload.get('schemaVersion')!r}")
    if payload.get("provider") != "pytest":
        raise ValueError(f"{path} is not a pytest evidence artifact")
    if not isinstance(payload.get("providerVersion"), str) or not payload["providerVersion"]:
        raise ValueError(f"{path} has invalid providerVersion")
    tests = payload.get("tests")
    if not isinstance(tests, list):
        raise ValueError(f"{path} has invalid tests array")
    seen: set[str] = set()
    for index, entry in enumerate(tests):
        if not isinstance(entry, dict):
            raise ValueError(f"{path} tests[{index}] must be an object")
        nodeid = entry.get("nodeid")
        outcome = entry.get("outcome")
        requirements = entry.get("requirements")
        test_cases = entry.get("testCases")
        if not isinstance(nodeid, str) or not nodeid:
            raise ValueError(f"{path} tests[{index}] has invalid nodeid")
        if nodeid in seen:
            raise ValueError(f"{path} contains duplicate pytest nodeid {nodeid}")
        seen.add(nodeid)
        if outcome not in PYTEST_OUTCOMES:
            raise ValueError(f"{path} tests[{index}] has invalid outcome {outcome!r}")
        for key, values in (("requirements", requirements), ("testCases", test_cases)):
            if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
                raise ValueError(f"{path} tests[{index}] has invalid {key}")
    return payload


def _attribute(snapshot: AnalysisSnapshot, object_id: str, name: str) -> object | None:
    item = snapshot.objects_by_id.get(object_id)
    if item is None:
        return None
    attributes = thaw_json(item.attributes)
    return attributes.get(name) if isinstance(attributes, dict) else None


def validate_pytest_evidence(
    snapshot: AnalysisSnapshot,
    payload: Mapping[str, object],
    *,
    require_complete: bool = True,
) -> tuple[EvidenceIssue, ...]:
    """Check executable pytest evidence against the current engineering graph."""
    issues: list[EvidenceIssue] = []
    tests = payload.get("tests", [])
    if not isinstance(tests, list):
        return (EvidenceIssue("EVD001", "pytest evidence has no valid tests array"),)

    observed_test_cases: set[str] = set()
    for raw in tests:
        if not isinstance(raw, Mapping):
            continue
        nodeid = str(raw.get("nodeid", ""))
        outcome = str(raw.get("outcome", ""))
        requirements = tuple(str(v) for v in raw.get("requirements", ()) if isinstance(v, str))
        test_cases = tuple(str(v) for v in raw.get("testCases", ()) if isinstance(v, str))
        observed_test_cases.update(test_cases)

        if outcome != "passed":
            issues.append(EvidenceIssue("EVD101", f"executable test {nodeid} outcome is {outcome}, not passed", nodeid=nodeid))
        if not test_cases:
            issues.append(EvidenceIssue("EVD102", f"executable test {nodeid} is not bound to a modeled test-case", nodeid=nodeid))

        for test_case_id in test_cases:
            test_case = snapshot.objects_by_id.get(test_case_id)
            if test_case is None:
                issues.append(EvidenceIssue("EVD103", f"pytest evidence references unknown test-case {test_case_id}", nodeid=nodeid, object_id=test_case_id))
                continue
            modeled_nodeid = _attribute(snapshot, test_case_id, "pytest-nodeid")
            if modeled_nodeid is None:
                issues.append(EvidenceIssue("EVD104", f"modeled test-case {test_case_id} has no pytest-nodeid binding", nodeid=nodeid, object_id=test_case_id))
            elif str(modeled_nodeid) != nodeid:
                issues.append(EvidenceIssue("EVD105", f"modeled test-case {test_case_id} binds to {modeled_nodeid}, evidence reports {nodeid}", nodeid=nodeid, object_id=test_case_id))

        for requirement_id in requirements:
            requirement = snapshot.objects_by_id.get(requirement_id)
            if requirement is None:
                issues.append(EvidenceIssue("EVD106", f"pytest evidence references unknown requirement {requirement_id}", nodeid=nodeid, object_id=requirement_id))
                continue
            modeled_targets = {rel.target for rel in snapshot.outgoing.get(requirement_id, ()) if rel.semantic_family == "verification"}
            if test_cases and not any(tc in modeled_targets for tc in test_cases):
                issues.append(EvidenceIssue("EVD107", f"requirement {requirement_id} is not verified by any test-case bound to {nodeid}", nodeid=nodeid, object_id=requirement_id))

    if require_complete:
        for item in snapshot.objects:
            attributes = thaw_json(item.attributes)
            if not isinstance(attributes, dict) or "pytest-nodeid" not in attributes:
                continue
            if item.id not in observed_test_cases:
                issues.append(EvidenceIssue("EVD108", f"modeled pytest-bound test-case {item.id} is missing from the evidence artifact", nodeid=str(attributes["pytest-nodeid"]), object_id=item.id))

    return tuple(sorted(issues, key=lambda issue: (issue.code, _text_key(issue.object_id or ""), _text_key(issue.nodeid or ""), issue.message)))
