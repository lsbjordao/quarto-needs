from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

from quarto_needs.analysis import analyze_objects
from quarto_needs.model import EngineeringObject
from quarto_needs.oslc_reconcile import ExternalRequirementObservation
from quarto_needs.oslc_rm import ExternalResourceIdentity, content_digest
from quarto_needs.oslc_write import (
    OslcWriteError,
    apply_write_plan,
    build_write_plan,
    load_previous_audit,
    project_write_payload,
)
from quarto_needs.oslc_write_http import OslcWriteTransportError, send_write_request


class _Headers(dict[str, str]):
    def get(self, key: str, default=None):  # type: ignore[override]
        for name, value in self.items():
            if name.lower() == key.lower():
                return value
        return default


class _Response:
    def __init__(self, status: int, payload: bytes = b"", **headers: str) -> None:
        self.status = status
        self.code = status
        self._payload = payload
        self.headers = _Headers(headers)

    def read(self, amount: int = -1) -> bytes:
        return self._payload if amount < 0 else self._payload[:amount]

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc_info) -> None:
        return None


class _Opener:
    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout: float):  # type: ignore[no-untyped-def]
        self.requests.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _snapshot():
    result = analyze_objects(
        [
            EngineeringObject(
                "REQ-1",
                "system-requirement",
                "Authenticate users",
                status="approved",
                body="The system shall authenticate users.",
                rationale="Protect data.",
                attributes={"tags": "security"},
            ),
            EngineeringObject("COMP-1", "component", "Component"),
        ]
    )
    assert result.snapshot is not None
    return result.snapshot


def _observation(
    uri: str = "https://provider.test/oslc/req/1",
    *,
    etag: str | None = '"etag-1"',
    trust_state: str = "trusted",
    fetched_at: str = "2026-09-10T12:00:00Z",
) -> ExternalRequirementObservation:
    return ExternalRequirementObservation(
        identity=ExternalResourceIdentity(
            resource_uri=uri,
            service_provider_uri="https://provider.test/oslc/sp",
            digest=content_digest(b"remote-bytes"),
            fetched_at=fetched_at,
            trust_state=trust_state,
            etag=etag,
        ),
        title="Authenticate users",
        description="The system shall authenticate users.",
    )


def test_payload_is_conservative_and_deterministic() -> None:
    snapshot = _snapshot()
    first = project_write_payload(snapshot, "REQ-1")
    second = project_write_payload(snapshot, "REQ-1")

    assert first == second
    assert "@id" not in first
    assert "@type" in first
    assert "serviceProvider" not in json.dumps(first)
    assert first["http://purl.org/dc/terms/title"] == "Authenticate users"
    assert first["urn:quarto-needs:oslc:v1:canonicalId"] == "REQ-1"

    with pytest.raises(OslcWriteError, match="no OSLC requirement projection"):
        project_write_payload(snapshot, "COMP-1")


def test_plan_requires_a_binding_trust_and_an_etag() -> None:
    snapshot = _snapshot()
    bound = _observation()
    untrusted = _observation("https://provider.test/oslc/req/2", trust_state="unverified")
    no_etag = _observation("https://provider.test/oslc/req/3", etag=None)
    unbound = _observation("https://provider.test/oslc/req/4")

    plan = build_write_plan(
        snapshot,
        [unbound, no_etag, untrusted, bound],
        {
            bound.identity.resource_uri: "REQ-1",
            untrusted.identity.resource_uri: "REQ-1",
            no_etag.identity.resource_uri: "REQ-1",
        },
    )

    assert len(plan.requests) == 1
    request = plan.requests[0]
    assert request.method == "PUT"
    assert request.uri == bound.identity.resource_uri
    assert request.if_match == '"etag-1"'
    assert request.body_digest.startswith("sha256:")
    assert request.headers["If-Match"] == '"etag-1"'
    reasons = {item.uri: item.reason for item in plan.skipped}
    assert "not 'trusted'" in reasons[untrusted.identity.resource_uri]
    assert "no ETag" in reasons[no_etag.identity.resource_uri]
    # An unbound observation is not a write target at all, not a skip.
    assert unbound.identity.resource_uri not in reasons
    assert plan.to_dict()["schema"] == "oslc-write-plan-v1"


def test_unknown_binding_target_is_refused() -> None:
    with pytest.raises(OslcWriteError, match="not a known object"):
        build_write_plan(
            _snapshot(),
            [_observation()],
            {"https://provider.test/oslc/req/1": "MISSING"},
        )


def test_a_previous_audit_skips_an_unchanged_payload() -> None:
    snapshot = _snapshot()
    observation = _observation()
    plan = build_write_plan(snapshot, [observation], {observation.identity.resource_uri: "REQ-1"})
    request = plan.requests[0]

    repeat = build_write_plan(
        snapshot,
        [observation],
        {observation.identity.resource_uri: "REQ-1"},
        previous_audit={
            "schema": "oslc-write-audit-v1",
            "completed": True,
            "entries": [
                {
                    "uri": request.uri,
                    "status": 200,
                    "bodyDigest": request.body_digest,
                }
            ],
        },
    )

    assert repeat.requests == ()
    assert "unchanged" in repeat.skipped[0].reason


def test_apply_sends_precondition_and_authorization_and_audits(tmp_path: Path) -> None:
    snapshot = _snapshot()
    observation = _observation()
    plan = build_write_plan(snapshot, [observation], {observation.identity.resource_uri: "REQ-1"})
    opener = _Opener(_Response(200, b"{}", ETag='"etag-2"'))
    audit_path = tmp_path / "audit.json"
    secret = "Bearer super-secret-token"

    audit = apply_write_plan(
        plan, authorization=secret, audit_path=audit_path, opener=opener
    )

    assert audit.completed is True
    request, timeout = opener.requests[0]
    assert request.method == "PUT"
    assert request.get_header("If-match") == '"etag-1"'
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("Authorization") == secret
    assert timeout == 30.0

    document = json.loads(audit_path.read_text(encoding="utf-8"))
    assert document["schema"] == "oslc-write-audit-v1"
    assert document["completed"] is True
    assert document["entries"][0]["status"] == 200
    assert document["entries"][0]["responseEtag"] == '"etag-2"'
    assert secret not in audit_path.read_text(encoding="utf-8")
    assert load_previous_audit(audit_path) is not None


def test_conflict_stops_the_run_and_is_audited_before_raising(tmp_path: Path) -> None:
    snapshot = _snapshot()
    first = _observation("https://provider.test/oslc/req/1")
    second = _observation("https://provider.test/oslc/req/2")
    plan = build_write_plan(
        snapshot,
        [first, second],
        {
            first.identity.resource_uri: "REQ-1",
            second.identity.resource_uri: "REQ-1",
        },
    )
    assert len(plan.requests) == 2
    opener = _Opener(
        _Response(200, b"{}", ETag='"etag-2"'),
        HTTPError(
            second.identity.resource_uri,
            412,
            "Precondition Failed",
            _Headers(),
            io.BytesIO(b"stale"),
        ),
    )
    audit_path = tmp_path / "audit.json"

    with pytest.raises(OslcWriteError) as failure:
        apply_write_plan(
            plan,
            authorization="Bearer token",
            audit_path=audit_path,
            opener=opener,
        )

    assert failure.value.code == "precondition-failed"
    assert len(opener.requests) == 2, "no request may be sent after the conflict"
    document = json.loads(audit_path.read_text(encoding="utf-8"))
    assert document["completed"] is False
    assert document["entries"][0]["status"] == 200
    assert document["entries"][1]["status"] is None
    assert "precondition-failed" in document["entries"][1]["error"]


def test_authorization_is_required_before_anything_is_sent(tmp_path: Path) -> None:
    snapshot = _snapshot()
    observation = _observation()
    plan = build_write_plan(snapshot, [observation], {observation.identity.resource_uri: "REQ-1"})
    opener = _Opener()

    with pytest.raises(OslcWriteError, match="authorization credential"):
        apply_write_plan(
            plan, authorization="  ", audit_path=tmp_path / "audit.json", opener=opener
        )

    assert opener.requests == []
    assert not (tmp_path / "audit.json").exists()


def test_transport_refuses_insecure_targets_redirects_and_methods() -> None:
    with pytest.raises(OslcWriteTransportError, match="https"):
        send_write_request(
            method="PUT",
            uri="http://provider.test/oslc/req/1",
            body=b"{}",
            headers={},
            authorization="Bearer token",
            opener=_Opener(),
        )

    with pytest.raises(OslcWriteTransportError, match="unsupported write method"):
        send_write_request(
            method="DELETE",
            uri="https://provider.test/oslc/req/1",
            body=b"",
            headers={},
            authorization="Bearer token",
            opener=_Opener(),
        )

    opener = _Opener(
        HTTPError(
            "https://provider.test/oslc/req/1",
            307,
            "Temporary Redirect",
            _Headers(Location="https://elsewhere.test/"),
            io.BytesIO(b""),
        )
    )
    with pytest.raises(OslcWriteTransportError) as failure:
        send_write_request(
            method="PUT",
            uri="https://provider.test/oslc/req/1",
            body=b"{}",
            headers={},
            authorization="Bearer token",
            opener=opener,
        )
    assert failure.value.code == "redirect-refused"


def test_invalid_previous_audit_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "audit.json"
    path.write_text('{"schema": "something-else"}', encoding="utf-8")
    with pytest.raises(OslcWriteError, match="oslc-write-audit-v1"):
        load_previous_audit(path)
