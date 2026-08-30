from __future__ import annotations

from collections.abc import Mapping

from .evidence import EvidenceIssue
from .snapshot import AnalysisSnapshot, thaw_json


def _text_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def _attribute(snapshot: AnalysisSnapshot, object_id: str, name: str) -> object | None:
    item = snapshot.objects_by_id.get(object_id)
    if item is None:
        return None
    attributes = thaw_json(item.attributes)
    return attributes.get(name) if isinstance(attributes, dict) else None


def _verification_connected(snapshot: AnalysisSnapshot, requirement_id: str, test_case_id: str) -> bool:
    return any(
        relation.target == test_case_id and relation.semantic_family == "verification"
        for relation in snapshot.outgoing.get(requirement_id, ())
    ) or any(
        relation.source == test_case_id and relation.semantic_family == "verification"
        for relation in snapshot.incoming.get(requirement_id, ())
    )


def _evidence_connected(snapshot: AnalysisSnapshot, evidence_id: str, test_case_id: str) -> bool:
    return any(
        relation.target == test_case_id and relation.semantic_family == "evidence"
        for relation in snapshot.outgoing.get(evidence_id, ())
    ) or any(
        relation.source == test_case_id and relation.semantic_family == "evidence"
        for relation in snapshot.incoming.get(evidence_id, ())
    ) or any(
        relation.target == evidence_id and relation.semantic_family == "evidence"
        for relation in snapshot.outgoing.get(test_case_id, ())
    ) or any(
        relation.source == evidence_id and relation.semantic_family == "evidence"
        for relation in snapshot.incoming.get(test_case_id, ())
    )


def validate_check_evidence(
    snapshot: AnalysisSnapshot,
    payload: Mapping[str, object],
    *,
    require_evidence_objects: bool = True,
) -> tuple[EvidenceIssue, ...]:
    """Validate generic machine-check evidence against the canonical graph."""
    provider = str(payload.get("provider", ""))
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return (EvidenceIssue("EVD301", "generic evidence has no valid checks array"),)

    issues: list[EvidenceIssue] = []
    for raw in checks:
        if not isinstance(raw, Mapping):
            issues.append(EvidenceIssue("EVD301", "generic evidence contains a non-object check"))
            continue
        check_id = str(raw.get("id", ""))
        outcome = str(raw.get("outcome", ""))
        requirements = tuple(str(value) for value in raw.get("requirements", ()) if isinstance(value, str))
        test_cases = tuple(str(value) for value in raw.get("testCases", ()) if isinstance(value, str))
        evidence_objects = tuple(str(value) for value in raw.get("evidenceObjects", ()) if isinstance(value, str))

        if outcome != "passed":
            issues.append(EvidenceIssue("EVD302", f"machine check {check_id} outcome is {outcome}, not passed", nodeid=check_id))
        if require_evidence_objects and not evidence_objects:
            issues.append(EvidenceIssue("EVD303", f"machine check {check_id} is not bound to a modeled evidence object", nodeid=check_id))

        known_tests: list[str] = []
        for test_case_id in test_cases:
            if test_case_id not in snapshot.objects_by_id:
                issues.append(EvidenceIssue("EVD304", f"machine check {check_id} references unknown test-case {test_case_id}", nodeid=check_id, object_id=test_case_id))
            else:
                known_tests.append(test_case_id)

        for requirement_id in requirements:
            if requirement_id not in snapshot.objects_by_id:
                issues.append(EvidenceIssue("EVD305", f"machine check {check_id} references unknown requirement {requirement_id}", nodeid=check_id, object_id=requirement_id))
                continue
            if known_tests and not any(
                _verification_connected(snapshot, requirement_id, test_case_id)
                for test_case_id in known_tests
            ):
                issues.append(EvidenceIssue("EVD306", f"requirement {requirement_id} is not verification-linked to a test-case claimed by machine check {check_id}", nodeid=check_id, object_id=requirement_id))

        for evidence_id in evidence_objects:
            evidence = snapshot.objects_by_id.get(evidence_id)
            if evidence is None:
                issues.append(EvidenceIssue("EVD307", f"machine check {check_id} references unknown evidence object {evidence_id}", nodeid=check_id, object_id=evidence_id))
                continue
            modeled_provider = _attribute(snapshot, evidence_id, "provider")
            if modeled_provider is not None and provider and str(modeled_provider) != provider:
                issues.append(EvidenceIssue("EVD308", f"modeled evidence {evidence_id} declares provider {modeled_provider}, machine evidence uses {provider}", nodeid=check_id, object_id=evidence_id))
            if known_tests and not any(
                _evidence_connected(snapshot, evidence_id, test_case_id)
                for test_case_id in known_tests
            ):
                issues.append(EvidenceIssue("EVD309", f"modeled evidence {evidence_id} does not evidence a test-case claimed by machine check {check_id}", nodeid=check_id, object_id=evidence_id))

    return tuple(sorted(
        issues,
        key=lambda issue: (
            issue.code,
            _text_key(issue.object_id or ""),
            _text_key(issue.nodeid or ""),
            issue.message,
        ),
    ))
