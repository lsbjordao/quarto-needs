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
from .oslc_rm import (
    DCTERMS_NS,
    OSLC_REQUIREMENT,
    QN_OSLC_NS,
    ExternalResourceIdentity,
    is_requirement_type,
)
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
    body: bytes
    body_digest: str
    if_match: str | None = None
    idempotency_key: str | None = None
    content_type: str | None = "application/json"

    @classmethod
    def build(
        cls,
        *,
        canonical_id: str,
        method: str,
        uri: str,
        payload: Mapping[str, object] | None = None,
        if_match: str | None = None,
        idempotency_key: str | None = None,
        idempotent: bool = False,
    ) -> "RemoteWriteRequest":
        body = _canonical_json(payload) if payload is not None else b""
        digest = "sha256:" + hashlib.sha256(body).hexdigest()
        if idempotency_key is None and idempotent:
            idempotency_key = "qn-" + hashlib.sha256(
                f"{canonical_id}\0{digest}".encode("utf-8")
            ).hexdigest()
        return cls(
            canonical_id=canonical_id,
            method=method,
            uri=uri,
            body=body,
            body_digest=digest,
            if_match=if_match,
            idempotency_key=idempotency_key,
            content_type=None if method == "DELETE" else "application/json",
        )

    @property
    def headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.content_type is not None:
            headers["Content-Type"] = self.content_type
        if self.if_match is not None:
            headers["If-Match"] = self.if_match
        if self.idempotency_key is not None:
            headers["Idempotency-Key"] = self.idempotency_key
        return headers

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "canonicalId": self.canonical_id,
            "method": self.method,
            "uri": self.uri,
            "bodyDigest": self.body_digest,
            "bodyLength": len(self.body),
        }
        if self.if_match is not None:
            payload["ifMatch"] = self.if_match
        if self.idempotency_key is not None:
            payload["idempotencyKey"] = self.idempotency_key
        return payload


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
    method: str
    if_match: str | None
    idempotency_key: str | None
    body_digest: str
    status: int | None
    response_etag: str | None
    response_location: str | None
    error: str | None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "uri": self.uri,
            "canonicalId": self.canonical_id,
            "method": self.method,
            "bodyDigest": self.body_digest,
            "status": self.status,
            "responseEtag": self.response_etag,
            "responseLocation": self.response_location,
            "error": self.error,
        }
        if self.if_match is not None:
            payload["ifMatch"] = self.if_match
        if self.idempotency_key is not None:
            payload["idempotencyKey"] = self.idempotency_key
        return payload


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


def observations_from_document(
    payload: object,
) -> tuple[ExternalRequirementObservation, ...]:
    """Rebuild observations from their ``to_dict()`` JSON form."""
    if isinstance(payload, Mapping):
        entries = payload.get("observations")
        if entries is None:
            raise OslcWriteError(
                "invalid-observations",
                "observation document has no 'observations' member",
            )
    else:
        entries = payload
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise OslcWriteError(
            "invalid-observations", "observations must be a JSON array"
        )

    observations: list[ExternalRequirementObservation] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise OslcWriteError(
                "invalid-observations", "each observation must be a JSON object"
            )
        identity_document = entry.get("identity")
        if not isinstance(identity_document, Mapping):
            raise OslcWriteError(
                "invalid-observations", "an observation is missing its identity object"
            )

        def text(value: object) -> str:
            return value if isinstance(value, str) else ""

        try:
            identity = ExternalResourceIdentity(
                resource_uri=text(identity_document.get("resourceUri")),
                service_provider_uri=text(identity_document.get("serviceProviderUri")),
                digest=text(identity_document.get("digest")),
                fetched_at=text(identity_document.get("fetchedAt")),
                trust_state=text(identity_document.get("trustState")) or "unverified",  # type: ignore[arg-type]
                etag=text(identity_document.get("etag")) or None,
                last_modified=text(identity_document.get("lastModified")) or None,
            )
            attributes = entry.get("attributes")
            observations.append(
                ExternalRequirementObservation(
                    identity=identity,
                    title=text(entry.get("title")),
                    description=text(entry.get("description")),
                    external_identifier=text(entry.get("externalIdentifier")) or None,
                    attributes=attributes if isinstance(attributes, Mapping) else {},
                )
            )
        except (TypeError, ValueError) as error:
            raise OslcWriteError(
                "invalid-observations", f"invalid observation: {error}"
            ) from error
    return tuple(observations)


def bindings_from_document(payload: object) -> dict[str, str]:
    """Validate an explicit external-URI to canonical-ID binding map."""
    if not isinstance(payload, Mapping):
        raise OslcWriteError(
            "invalid-bindings", "bindings must be a JSON object of URI -> canonical ID"
        )
    bindings: dict[str, str] = {}
    for uri, canonical_id in payload.items():
        if not isinstance(uri, str) or not uri.strip():
            raise OslcWriteError("invalid-bindings", f"invalid binding URI: {uri!r}")
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            raise OslcWriteError(
                "invalid-bindings", f"invalid canonical ID for {uri}: {canonical_id!r}"
            )
        bindings[uri] = canonical_id.strip()
    return bindings


def _successful_entries(
    previous_audit: Mapping[str, object] | None,
) -> list[Mapping[str, object]]:
    if previous_audit is None:
        return []
    entries = previous_audit.get("entries")
    if not isinstance(entries, Sequence):
        return []
    return [
        entry
        for entry in entries
        if isinstance(entry, Mapping)
        and isinstance(entry.get("status"), int)
        and 200 <= int(entry["status"]) < 300
    ]


def _recorded_digests(previous_audit: Mapping[str, object] | None) -> dict[str, str]:
    """URI -> payload digest for successful updates (PUT, or legacy audits)."""
    recorded: dict[str, str] = {}
    for entry in _successful_entries(previous_audit):
        method = entry.get("method", "PUT")
        uri = entry.get("uri")
        digest = entry.get("bodyDigest")
        if method == "PUT" and isinstance(uri, str) and isinstance(digest, str):
            recorded[uri] = digest
    return recorded


def _recorded_creates(previous_audit: Mapping[str, object] | None) -> set[str]:
    return {
        str(entry["canonicalId"])
        for entry in _successful_entries(previous_audit)
        if entry.get("method") == "POST" and isinstance(entry.get("canonicalId"), str)
    }


def _recorded_deletes(previous_audit: Mapping[str, object] | None) -> set[str]:
    return {
        str(entry["uri"])
        for entry in _successful_entries(previous_audit)
        if entry.get("method") == "DELETE" and isinstance(entry.get("uri"), str)
    }


def build_write_plan(
    snapshot: AnalysisSnapshot,
    observations: Sequence[ExternalRequirementObservation],
    bindings: Mapping[str, str],
    *,
    creates: Sequence[str] = (),
    deletes: Sequence[str] = (),
    collection_uri: str | None = None,
    previous_audit: Mapping[str, object] | None = None,
) -> RemoteWritePlan:
    """Build the reviewed requests for every explicit, contract-satisfying write.

    Updates are derived from the trusted, bound observations that carry an
    ETag. Creates are only the canonical IDs the caller names, target the
    explicit collection URI, and refuse an ID that is already bound. Deletes
    are only the canonical IDs the caller names, need a single trusted bound
    observation with an ETag, and never happen automatically.
    """
    recorded_updates = _recorded_digests(previous_audit)
    recorded_creates = _recorded_creates(previous_audit)
    recorded_deletes = _recorded_deletes(previous_audit)

    create_ids = tuple(dict.fromkeys(creates))
    delete_ids = tuple(dict.fromkeys(deletes))
    overlap = sorted(set(create_ids) & set(delete_ids))
    if overlap:
        raise OslcWriteError(
            "create-delete-overlap",
            "a canonical ID cannot be created and deleted in the same plan: "
            + ", ".join(overlap),
        )
    if create_ids and not collection_uri:
        raise OslcWriteError(
            "collection-required", "creating remote resources requires a collection URI"
        )

    reverse: dict[str, list[str]] = {}
    for uri, canonical_id in bindings.items():
        reverse.setdefault(canonical_id, []).append(uri)

    requests: list[RemoteWriteRequest] = []
    skipped: list[SkippedWrite] = []
    seen_uris: set[str] = set()

    for observation in sorted(
        observations, key=lambda item: item.identity.resource_uri
    ):
        uri = observation.identity.resource_uri
        if uri in seen_uris:
            raise OslcWriteError(
                "duplicate-observation", f"{uri} appears more than once"
            )
        seen_uris.add(uri)
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
        request = RemoteWriteRequest.build(
            canonical_id=canonical_id,
            method="PUT",
            uri=uri,
            payload=payload,
            if_match=observation.identity.etag,
        )
        if recorded_updates.get(uri) == request.body_digest:
            skipped.append(
                SkippedWrite(uri, canonical_id, "payload unchanged since the recorded write")
            )
            continue
        requests.append(request)

    bound_targets = set(bindings.values())
    for canonical_id in sorted(create_ids, key=lambda value: (value.casefold(), value)):
        if canonical_id in bound_targets:
            raise OslcWriteError(
                "already-bound",
                f"{canonical_id!r} is already bound to a remote resource; update it instead",
            )
        if canonical_id in recorded_creates:
            skipped.append(
                SkippedWrite(
                    collection_uri or "",
                    canonical_id,
                    "already created in the recorded audit",
                )
            )
            continue
        requests.append(
            RemoteWriteRequest.build(
                canonical_id=canonical_id,
                method="POST",
                uri=collection_uri or "",
                payload=project_write_payload(snapshot, canonical_id),
                idempotent=True,
            )
        )

    observed_by_uri = {
        observation.identity.resource_uri: observation for observation in observations
    }
    for canonical_id in sorted(delete_ids, key=lambda value: (value.casefold(), value)):
        uris = sorted(reverse.get(canonical_id, ()))
        if not uris:
            raise OslcWriteError(
                "unbound-delete",
                f"{canonical_id!r} has no bound remote resource to delete",
            )
        if len(uris) > 1:
            raise OslcWriteError(
                "ambiguous-delete",
                f"{canonical_id!r} is bound to more than one remote resource: "
                + ", ".join(uris),
            )
        uri = uris[0]
        observation = observed_by_uri.get(uri)
        if observation is None:
            raise OslcWriteError(
                "missing-observation",
                f"{canonical_id!r} is bound to {uri}, which is not in this observation set",
            )
        if observation.identity.trust_state != "trusted":
            raise OslcWriteError(
                "untrusted-delete",
                f"refusing to delete {uri}: trust state is "
                f"{observation.identity.trust_state!r}, not 'trusted'",
            )
        if not observation.identity.etag:
            raise OslcWriteError(
                "delete-without-etag",
                f"refusing to delete {uri}: the observation has no ETag validator",
            )
        if uri in recorded_deletes:
            skipped.append(
                SkippedWrite(uri, canonical_id, "already deleted in the recorded audit")
            )
            continue
        requests.append(
            RemoteWriteRequest.build(
                canonical_id=canonical_id,
                method="DELETE",
                uri=uri,
                if_match=observation.identity.etag,
            )
        )

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
                    method=request.method,
                    if_match=request.if_match,
                    idempotency_key=request.idempotency_key,
                    body_digest=request.body_digest,
                    status=None,
                    response_etag=None,
                    response_location=None,
                    error=f"{error.code}: {error}",
                )
            )
            failure = OslcWriteError(error.code, str(error))
            break
        entries.append(
            WriteAuditEntry(
                uri=request.uri,
                canonical_id=request.canonical_id,
                method=request.method,
                if_match=request.if_match,
                idempotency_key=request.idempotency_key,
                body_digest=request.body_digest,
                status=response.status,
                response_etag=response.etag,
                response_location=response.location,
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
