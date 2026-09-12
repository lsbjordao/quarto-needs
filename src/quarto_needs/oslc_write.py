"""Reviewed OSLC remote-write plans and their audited application.

The eight contracts this module implements — staleness, conflict,
authored-file placement, atomicity, rollback, optimistic concurrency,
authorization and audit — are stated in `notes/oslc-remote-writes.md`. The
short version: requests are built only from a reconciled binding whose
observation is trusted and carries an ETag, every request is sent one at a
time with `If-Match`, the first provider refusal stops the run, and the audit
is written before any failure propagates because a remote write cannot be
rolled back.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .export import _write_atomic_text
from .oslc_reconcile import ExternalRequirementObservation
from .oslc_rm import DCTERMS_NS, OSLC_REQUIREMENT, QN_OSLC_NS, is_requirement_type
from .oslc_write_http import (
    OslcWriteTransportError,
    WritePolicy,
    send_write_request,
)
from .snapshot import AnalysisSnapshot, thaw_json


class OslcWriteError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _canonical_json(payload: Mapping[str, object]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def project_write_payload(
    snapshot: AnalysisSnapshot, canonical_id: str
) -> dict[str, object]:
    """A conservative update payload for one requirement.

    Deliberately excludes `@id`, `@type`, `serviceProvider` and relation
    triples: the target URI is the observed one, the provider owns its own
    resource typing and service linkage, and relation reconciliation is not
    part of this slice.
    """
    record = snapshot.objects_by_id.get(canonical_id)
    if record is None:
        raise OslcWriteError(
            "unknown-canonical-id", f"{canonical_id!r} is not a known object"
        )
    if not is_requirement_type(record.type):
        raise OslcWriteError(
            "not-a-requirement",
            f"{canonical_id!r} is {record.type!r}, which has no OSLC requirement projection",
        )
    return {
        "@type": OSLC_REQUIREMENT,
        f"{DCTERMS_NS}identifier": record.id,
        f"{DCTERMS_NS}title": record.title,
        f"{DCTERMS_NS}description": record.body,
        f"{QN_OSLC_NS}attributes": thaw_json(record.attributes),
        f"{QN_OSLC_NS}canonicalId": record.id,
        f"{QN_OSLC_NS}objectType": record.type,
        f"{QN_OSLC_NS}rationale": record.rationale,
        f"{QN_OSLC_NS}semanticGraphFingerprint": snapshot.semantic_graph_fingerprint,
        f"{QN_OSLC_NS}status": record.status,
    }


@dataclass(frozen=True, slots=True)
class RemoteWriteRequest:
    canonical_id: str
    method: str
    uri: str
    if_match: str
    body: bytes
    body_digest: str
    content_type: str = "application/json"

    @classmethod
    def create(
        cls,
        *,
        canonical_id: str,
        uri: str,
        if_match: str,
        payload: Mapping[str, object],
        method: str = "PUT",
    ) -> "RemoteWriteRequest":
        body = _canonical_json(payload)
        return cls(
            canonical_id=canonical_id,
            method=method,
            uri=uri,
            if_match=if_match,
            body=body,
            body_digest="sha256:" + hashlib.sha256(body).hexdigest(),
        )

    @property
    def headers(self) -> dict[str, str]:
        return {"Content-Type": self.content_type, "If-Match": self.if_match}

    def to_dict(self) -> dict[str, object]:
        return {
            "canonicalId": self.canonical_id,
            "method": self.method,
            "uri": self.uri,
            "ifMatch": self.if_match,
            "contentType": self.content_type,
            "bodyDigest": self.body_digest,
            "bodyLength": len(self.body),
        }


@dataclass(frozen=True, slots=True)
class SkippedWrite:
    uri: str
    canonical_id: str | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "canonicalId": self.canonical_id,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RemoteWritePlan:
    requests: tuple[RemoteWriteRequest, ...]
    skipped: tuple[SkippedWrite, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "oslc-write-plan-v1",
            "requestCount": len(self.requests),
            "requests": [request.to_dict() for request in self.requests],
            "skipped": [item.to_dict() for item in self.skipped],
        }


@dataclass(frozen=True, slots=True)
class WriteAuditEntry:
    uri: str
    canonical_id: str
    if_match: str
    body_digest: str
    status: int | None
    response_etag: str | None
    error: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "canonicalId": self.canonical_id,
            "ifMatch": self.if_match,
            "bodyDigest": self.body_digest,
            "status": self.status,
            "responseEtag": self.response_etag,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class RemoteWriteAudit:
    completed: bool
    entries: tuple[WriteAuditEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "oslc-write-audit-v1",
            "completed": self.completed,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def load_previous_audit(path: Path) -> Mapping[str, object] | None:
    """Read a previous audit document, or None when there is none."""
    source = Path(path)
    if not source.is_file():
        return None
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OslcWriteError(
            "invalid-audit", f"cannot read write audit {source}: {error}"
        ) from error
    if not isinstance(payload, Mapping) or payload.get("schema") != "oslc-write-audit-v1":
        raise OslcWriteError(
            "invalid-audit", f"{source} is not an oslc-write-audit-v1 document"
        )
    return payload


def _recorded_digests(
    previous_audit: Mapping[str, object] | None,
) -> dict[str, str]:
    if previous_audit is None:
        return {}
    recorded: dict[str, str] = {}
    entries = previous_audit.get("entries")
    if not isinstance(entries, Sequence):
        return {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        status = entry.get("status")
        uri = entry.get("uri")
        digest = entry.get("bodyDigest")
        if isinstance(status, int) and 200 <= status < 300 and isinstance(uri, str) and isinstance(digest, str):
            recorded[uri] = digest
    return recorded


def build_write_plan(
    snapshot: AnalysisSnapshot,
    observations: Sequence[ExternalRequirementObservation],
    bindings: Mapping[str, str],
    *,
    previous_audit: Mapping[str, object] | None = None,
) -> RemoteWritePlan:
    """Build the reviewed requests for every trusted, bound, current observation."""
    recorded = _recorded_digests(previous_audit)
    requests: list[RemoteWriteRequest] = []
    skipped: list[SkippedWrite] = []
    seen: set[str] = set()

    for observation in sorted(
        observations, key=lambda item: item.identity.resource_uri
    ):
        uri = observation.identity.resource_uri
        if uri in seen:
            raise OslcWriteError(
                "duplicate-observation", f"{uri} appears more than once"
            )
        seen.add(uri)
        canonical_id = bindings.get(uri)
        if canonical_id is None:
            continue
        if observation.identity.trust_state != "trusted":
            skipped.append(
                SkippedWrite(
                    uri,
                    canonical_id,
                    f"trust state is {observation.identity.trust_state!r}, not 'trusted'",
                )
            )
            continue
        if not observation.identity.etag:
            skipped.append(
                SkippedWrite(
                    uri,
                    canonical_id,
                    "observation has no ETag validator; unconditional writes are outside the contract",
                )
            )
            continue
        payload = project_write_payload(snapshot, canonical_id)
        request = RemoteWriteRequest.create(
            canonical_id=canonical_id,
            uri=uri,
            if_match=observation.identity.etag,
            payload=payload,
        )
        if recorded.get(uri) == request.body_digest:
            skipped.append(
                SkippedWrite(uri, canonical_id, "payload unchanged since the recorded write")
            )
            continue
        requests.append(request)

    return RemoteWritePlan(requests=tuple(requests), skipped=tuple(skipped))


def apply_write_plan(
    plan: RemoteWritePlan,
    *,
    authorization: str,
    audit_path: Path,
    opener=None,  # type: ignore[no-untyped-def]
    policy: WritePolicy | None = None,
) -> RemoteWriteAudit:
    """Send every request in order, stop on the first refusal, audit always."""
    if not plan.requests:
        raise OslcWriteError("no-requests", "write plan has no requests to send")
    if not isinstance(authorization, str) or not authorization.strip():
        raise OslcWriteError(
            "authorization-required",
            "a non-empty authorization credential is required for remote writes",
        )

    entries: list[WriteAuditEntry] = []
    failure: OslcWriteError | None = None
    for request in plan.requests:
        try:
            response = send_write_request(
                method=request.method,
                uri=request.uri,
                body=request.body,
                headers=request.headers,
                authorization=authorization,
                opener=opener,
                policy=policy,
            )
        except OslcWriteTransportError as error:
            entries.append(
                WriteAuditEntry(
                    uri=request.uri,
                    canonical_id=request.canonical_id,
                    if_match=request.if_match,
                    body_digest=request.body_digest,
                    status=None,
                    response_etag=None,
                    error=f"{error.code}: {error}",
                )
            )
            failure = OslcWriteError(error.code, str(error))
            break
        entries.append(
            WriteAuditEntry(
                uri=request.uri,
                canonical_id=request.canonical_id,
                if_match=request.if_match,
                body_digest=request.body_digest,
                status=response.status,
                response_etag=response.etag,
                error=None,
            )
        )

    audit = RemoteWriteAudit(completed=failure is None, entries=tuple(entries))
    _write_atomic_text(
        Path(audit_path),
        json.dumps(audit.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    if failure is not None:
        raise failure
    return audit
