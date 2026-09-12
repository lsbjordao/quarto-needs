"""Bounded single-shot OSLC write transport.

GET has its own bounded transport in `oslc_http.py`; this module is the
write-side counterpart and shares only the policy shape, not the code — the
established convention (see `github_http.py`). One call sends one request and
returns one outcome; retries, merges and transactions are caller policy, and
none of them live here.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


@dataclass(frozen=True, slots=True)
class WritePolicy:
    timeout_seconds: float = 30.0
    max_request_bytes: int = 1_048_576
    max_response_bytes: int = 65_536

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_request_bytes <= 0 or self.max_response_bytes <= 0:
            raise ValueError("byte limits must be positive")


class OslcWriteTransportError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


@dataclass(frozen=True, slots=True)
class WriteResponse:
    status: int
    etag: str | None
    body: bytes


def _require_write_uri(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise OslcWriteTransportError(
            "invalid-uri", f"write target must be an absolute http(s) URI: {value!r}"
        )
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" and host not in {"localhost", "127.0.0.1", "::1"}:
        raise OslcWriteTransportError(
            "insecure-uri",
            "remote writes require https (localhost fixtures excepted)",
        )


def _read_bounded(response, max_bytes: int) -> bytes:  # type: ignore[no-untyped-def]
    chunks: list[bytes] = []
    remaining = max_bytes
    while remaining > 0:
        chunk = response.read(min(remaining, 65_536))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _classify(status: int) -> str:
    if status in {301, 302, 303, 307, 308}:
        return "redirect-refused"
    if status == 412:
        return "precondition-failed"
    if status == 409:
        return "conflict"
    if status in {401, 403}:
        return "authorization-failed"
    if status >= 500:
        return "server-error"
    return "client-error"


def send_write_request(
    *,
    method: str,
    uri: str,
    body: bytes,
    headers: dict[str, str],
    authorization: str,
    opener=None,  # type: ignore[no-untyped-def]
    policy: WritePolicy | None = None,
) -> WriteResponse:
    """Send exactly one bounded write. Redirects are never followed."""
    resolved = policy if policy is not None else WritePolicy()
    if method != "PUT":
        raise OslcWriteTransportError(
            "unsupported-method", f"unsupported write method: {method!r}"
        )
    _require_write_uri(uri)
    if not isinstance(authorization, str) or not authorization.strip():
        raise OslcWriteTransportError(
            "authorization-required",
            "a non-empty authorization credential is required for remote writes",
        )
    if len(body) > resolved.max_request_bytes:
        raise OslcWriteTransportError(
            "request-too-large",
            f"write body is {len(body)} bytes, above the {resolved.max_request_bytes} limit",
        )

    request_headers = dict(headers)
    request_headers["Authorization"] = authorization
    request = Request(uri, data=body, headers=request_headers, method=method)
    active_opener = opener if opener is not None else build_opener(_NoRedirect())
    try:
        with active_opener.open(request, timeout=resolved.timeout_seconds) as response:
            status = int(getattr(response, "status", None) or response.getcode())
            etag = response.headers.get("ETag")
            payload = _read_bounded(response, resolved.max_response_bytes)
    except HTTPError as error:
        code = _classify(error.code)
        detail = ""
        if error.fp is not None:
            raw = error.read(resolved.max_response_bytes)
            detail = raw.decode("utf-8", "replace")[:500]
        raise OslcWriteTransportError(
            code,
            f"provider refused the write with HTTP {error.code}"
            + (f": {detail}" if detail else ""),
        ) from error
    except URLError as error:
        raise OslcWriteTransportError(
            "transport-error", f"write transport failed: {error.reason}"
        ) from error

    if not 200 <= status < 300:
        raise OslcWriteTransportError(
            _classify(status), f"provider returned HTTP {status} for the write"
        )
    return WriteResponse(status=status, etag=etag, body=payload)
