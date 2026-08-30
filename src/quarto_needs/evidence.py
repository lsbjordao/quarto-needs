from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import quarto_needs

from .snapshot import AnalysisSnapshot, thaw_json


EVIDENCE_SCHEMA_VERSION = "1"
EVIDENCE_ENVELOPE_SCHEMA_VERSION = "1"
EVIDENCE_KIND = "quarto-needs-evidence"
_ENVELOPE_METADATA_KEY = "_quartoNeedsEnvelope"
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


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return the stable byte representation used for evidence digests."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def evidence_digest(payload: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


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
        tests.append({
            "nodeid": nodeid,
            "outcome": outcome,
            "requirements": list(requirements),
            "testCases": list(test_cases),
        })
    tests.sort(key=lambda item: _text_key(str(item["nodeid"])))
    counts = Counter(str(item["outcome"]) for item in tests)
    return {
        "schemaVersion": EVIDENCE_SCHEMA_VERSION,
        "provider": "pytest",
        "providerVersion": provider_version,
        "generator": {"name": "quarto-needs", "version": quarto_needs.__version__},
        "summary": {
            "total": len(tests),
            "passed": counts.get("passed", 0),
            "failed": counts.get("failed", 0),
            "skipped": counts.get("skipped", 0),
        },
        "tests": tests,
    }


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_evidence_envelope(
    payload: Mapping[str, Any],
    *,
    provider_name: str,
    provider_version: str,
    artifact_schema: str,
    snapshot: AnalysisSnapshot,
    generated_at: datetime | None = None,
    expires_at: datetime | None = None,
    source_revision: str | None = None,
) -> dict[str, object]:
    """Bind provider evidence to a concrete engineering state.

    The provider payload remains independently deterministic. Volatile provenance
    belongs to this envelope, so repeated provider execution can still be
    compared byte-for-byte while an attestation records when and against which
    graph/configuration state the evidence was accepted.
    """
    timestamp = generated_at or datetime.now(timezone.utc)
    subject: dict[str, str] = {
        "configurationFingerprint": snapshot.configuration_fingerprint,
        "semanticGraphFingerprint": snapshot.semantic_graph_fingerprint,
        "representationFingerprint": snapshot.representation_fingerprint,
    }
    if source_revision:
        subject["sourceRevision"] = source_revision
    envelope: dict[str, object] = {
        "schemaVersion": EVIDENCE_ENVELOPE_SCHEMA_VERSION,
        "kind": EVIDENCE_KIND,
        "provider": {"name": provider_name, "version": provider_version},
        "generatedAt": _utc_timestamp(timestamp),
        "subject": subject,
        "artifact": {
            "schema": artifact_schema,
            "digest": evidence_digest(payload),
            "payload": dict(payload),
        },
    }
    if expires_at is not None:
        envelope["expiresAt"] = _utc_timestamp(expires_at)
    return envelope


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


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def load_pytest_evidence(path: Path) -> dict[str, object]:
    """Load raw pytest evidence or an attested pytest envelope.

    The envelope is attached under a private in-memory key after its payload
    digest and provider contract are checked. This keeps the existing CLI path
    backward compatible while allowing semantic validation to include
    provenance and freshness checks.
    """
    envelope, payload = load_evidence(path)
    if envelope is None:
        return payload
    provider = envelope.get("provider")
    if not isinstance(provider, Mapping) or provider.get("name") != "pytest":
        raise ValueError(f"{path} is not an attested pytest evidence artifact")
    loaded = dict(payload)
    loaded[_ENVELOPE_METADATA_KEY] = envelope
    return loaded


def _validate_pytest_payload_shape(payload: Mapping[str, object], *, source: str) -> None:
    if payload.get("schemaVersion") != EVIDENCE_SCHEMA_VERSION:
        raise ValueError(f"{source} has unsupported evidence schemaVersion {payload.get('schemaVersion')!r}")
    if payload.get("provider") != "pytest":
        raise ValueError(f"{source} is not a pytest evidence artifact")
    if not isinstance(payload.get("providerVersion"), str) or not payload["providerVersion"]:
        raise ValueError(f"{source} has invalid providerVersion")
    tests = payload.get("tests")
    if not isinstance(tests, list):
        raise ValueError(f"{source} has invalid tests array")
    seen: set[str] = set()
    for index, entry in enumerate(tests):
        if not isinstance(entry, dict):
            raise ValueError(f"{source} tests[{index}] must be an object")
        nodeid = entry.get("nodeid")
        outcome = entry.get("outcome")
        requirements = entry.get("requirements")
        test_cases = entry.get("testCases")
        if not isinstance(nodeid, str) or not nodeid:
            raise ValueError(f"{source} tests[{index}] has invalid nodeid")
        if nodeid in seen:
            raise ValueError(f"{source} contains duplicate pytest nodeid {nodeid}")
        seen.add(nodeid)
        if outcome not in PYTEST_OUTCOMES:
            raise ValueError(f"{source} tests[{index}] has invalid outcome {outcome!r}")
        for key, values in (("requirements", requirements), ("testCases", test_cases)):
            if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
                raise ValueError(f"{source} tests[{index}] has invalid {key}")


def load_evidence(path: Path) -> tuple[dict[str, object] | None, dict[str, object]]:
    """Load either a provider-neutral envelope or a legacy raw pytest artifact."""
    document = _load_json_object(path)
    if document.get("kind") != EVIDENCE_KIND:
        _validate_pytest_payload_shape(document, source=str(path))
        return None, document

    if document.get("schemaVersion") != EVIDENCE_ENVELOPE_SCHEMA_VERSION:
        raise ValueError(
            f"{path} has unsupported evidence envelope schemaVersion {document.get('schemaVersion')!r}"
        )
    provider = document.get("provider")
    subject = document.get("subject")
    artifact = document.get("artifact")
    generated_at = document.get("generatedAt")
    expires_at = document.get("expiresAt")
    if not isinstance(provider, dict) or not isinstance(provider.get("name"), str) or not provider.get("name"):
        raise ValueError(f"{path} has invalid envelope provider")
    if not isinstance(provider.get("version"), str) or not provider.get("version"):
        raise ValueError(f"{path} has invalid envelope provider version")
    if not isinstance(subject, dict):
        raise ValueError(f"{path} has invalid envelope subject")
    if not isinstance(generated_at, str) or parse_evidence_time(generated_at) is None:
        raise ValueError(f"{path} has invalid generatedAt")
    if expires_at is not None and (
        not isinstance(expires_at, str) or parse_evidence_time(expires_at) is None
    ):
        raise ValueError(f"{path} has invalid expiresAt")
    if not isinstance(artifact, dict):
        raise ValueError(f"{path} has invalid envelope artifact")
    raw = artifact.get("payload")
    if not isinstance(raw, dict):
        raise ValueError(f"{path} has invalid envelope artifact payload")
    expected_digest = artifact.get("digest")
    actual_digest = evidence_digest(raw)
    if expected_digest != actual_digest:
        raise ValueError(f"{path} evidence payload digest does not match its envelope")
    if provider.get("name") == "pytest":
        _validate_pytest_payload_shape(raw, source=f"{path} artifact.payload")
    return document, raw


def parse_evidence_time(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def validate_evidence_envelope(
    snapshot: AnalysisSnapshot,
    envelope: Mapping[str, object],
    *,
    now: datetime | None = None,
    max_age_hours: float | None = None,
    expected_source_revision: str | None = None,
) -> tuple[EvidenceIssue, ...]:
    issues: list[EvidenceIssue] = []
    subject = envelope.get("subject")
    if not isinstance(subject, Mapping):
        return (EvidenceIssue("EVD201", "evidence envelope has no valid subject"),)

    fingerprint_checks = (
        ("configurationFingerprint", snapshot.configuration_fingerprint, "EVD202", "configuration"),
        ("semanticGraphFingerprint", snapshot.semantic_graph_fingerprint, "EVD203", "semantic graph"),
        ("representationFingerprint", snapshot.representation_fingerprint, "EVD204", "representation"),
    )
    for key, expected, code, label in fingerprint_checks:
        observed = subject.get(key)
        if observed != expected:
            issues.append(EvidenceIssue(code, f"evidence {label} fingerprint does not match the current project"))

    if expected_source_revision is not None:
        observed_revision = subject.get("sourceRevision")
        if observed_revision is not None and observed_revision != expected_source_revision:
            issues.append(EvidenceIssue(
                "EVD205",
                f"evidence source revision {observed_revision} does not match current revision {expected_source_revision}",
            ))

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    reference = reference.astimezone(timezone.utc)

    generated = envelope.get("generatedAt")
    parsed_generated = parse_evidence_time(str(generated)) if isinstance(generated, str) else None
    if parsed_generated is None:
        issues.append(EvidenceIssue("EVD206", "evidence generatedAt is not a valid timezone-aware timestamp"))
    elif parsed_generated > reference:
        issues.append(EvidenceIssue("EVD207", "evidence generatedAt is in the future"))
    elif max_age_hours is not None:
        age_seconds = (reference - parsed_generated).total_seconds()
        if age_seconds > max_age_hours * 3600:
            issues.append(EvidenceIssue(
                "EVD208",
                f"evidence is older than the allowed {max_age_hours:g} hour(s)",
            ))

    expires = envelope.get("expiresAt")
    if expires is not None:
        parsed_expiry = parse_evidence_time(str(expires)) if isinstance(expires, str) else None
        if parsed_expiry is None:
            issues.append(EvidenceIssue("EVD209", "evidence expiresAt is not a valid timezone-aware timestamp"))
        elif reference > parsed_expiry:
            issues.append(EvidenceIssue("EVD210", f"evidence expired at {_utc_timestamp(parsed_expiry)}"))
        elif parsed_generated is not None and parsed_expiry < parsed_generated:
            issues.append(EvidenceIssue("EVD211", "evidence expiresAt precedes generatedAt"))

    return tuple(issues)


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
    envelope = payload.get(_ENVELOPE_METADATA_KEY)
    if isinstance(envelope, Mapping):
        issues.extend(validate_evidence_envelope(snapshot, envelope))

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

        known_test_cases: list[str] = []
        for test_case_id in test_cases:
            test_case = snapshot.objects_by_id.get(test_case_id)
            if test_case is None:
                issues.append(EvidenceIssue("EVD103", f"pytest evidence references unknown test-case {test_case_id}", nodeid=nodeid, object_id=test_case_id))
                continue
            known_test_cases.append(test_case_id)
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
            modeled_targets = {
                rel.target
                for rel in snapshot.outgoing.get(requirement_id, ())
                if rel.semantic_family == "verification"
            }
            if test_cases and not any(tc in modeled_targets for tc in test_cases):
                issues.append(EvidenceIssue("EVD107", f"requirement {requirement_id} is not verified by any test-case bound to {nodeid}", nodeid=nodeid, object_id=requirement_id))

        claimed_requirements = set(requirements)
        modeled_by_requirement: dict[str, set[str]] = {}
        for test_case_id in known_test_cases:
            for relation in snapshot.incoming.get(test_case_id, ()):
                if relation.semantic_family != "verification":
                    continue
                modeled_by_requirement.setdefault(relation.source, set()).add(test_case_id)
        for requirement_id in sorted(modeled_by_requirement.keys() - claimed_requirements, key=_text_key):
            modeled_test_cases = ", ".join(sorted(modeled_by_requirement[requirement_id], key=_text_key))
            issues.append(EvidenceIssue(
                "EVD109",
                f"modeled test-case(s) {modeled_test_cases} verify requirement {requirement_id}, but executable test {nodeid} does not claim that requirement",
                nodeid=nodeid,
                object_id=requirement_id,
            ))

    if require_complete:
        for item in snapshot.objects:
            attributes = thaw_json(item.attributes)
            if not isinstance(attributes, dict) or "pytest-nodeid" not in attributes:
                continue
            if item.id not in observed_test_cases:
                issues.append(EvidenceIssue(
                    "EVD108",
                    f"modeled pytest-bound test-case {item.id} is missing from the evidence artifact",
                    nodeid=str(attributes["pytest-nodeid"]),
                    object_id=item.id,
                ))

    return tuple(sorted(
        issues,
        key=lambda issue: (
            issue.code,
            _text_key(issue.object_id or ""),
            _text_key(issue.nodeid or ""),
            issue.message,
        ),
    ))
