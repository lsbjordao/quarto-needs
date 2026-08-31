from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .oslc_cache import (
    CacheSelection,
    CachedRepresentation,
    latest_cached_representation,
    read_cached_payload,
    select_cached_representation,
    store_cached_representation,
)
from .oslc_rm import CachePolicy, ExternalResourceIdentity, content_digest

SUPPORTED_OSLC_MEDIA_TYPES = {
    "application/ld+json",
    "application/json",
    "text/turtle",
    "application/rdf+xml",
}


class OslcTransportError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class HttpFetchPolicy:
    timeout_seconds: float = 10.0
    max_bytes: int = 2_000_000
    max_redirects: int = 3

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        if self.max_redirects < 0:
            raise ValueError("max_redirects must be non-negative")


@dataclass(frozen=True, slots=True)
class OslcFetchResult:
    source: str
    representation: CachedRepresentation
    payload: bytes


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _require_http_uri(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute http(s) URI")


def _media_type(value: str | None) -> str:
    if value is None:
        raise OslcTransportError("unsupported-media-type", "OSLC response omitted Content-Type")
    media_type = value.split(";", 1)[0].strip().lower()
    if media_type not in SUPPORTED_OSLC_MEDIA_TYPES:
        raise OslcTransportError(
            "unsupported-media-type",
            f"unsupported OSLC response media type: {media_type or value!r}",
        )
    return media_type


def _read_bounded(response, max_bytes: int) -> bytes:  # type: ignore[no-untyped-def]
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as error:
            raise OslcTransportError("invalid-response", "invalid Content-Length header") from error
        if declared > max_bytes:
            raise OslcTransportError(
                "response-too-large",
                f"OSLC response declares {declared} bytes, limit is {max_bytes}",
            )
    payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise OslcTransportError(
            "response-too-large",
            f"OSLC response exceeds byte limit {max_bytes}",
        )
    return payload


def _conditional_headers(cached: CachedRepresentation | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if cached is None:
        return headers
    if cached.identity.etag:
        headers["If-None-Match"] = cached.identity.etag
    if cached.identity.last_modified:
        headers["If-Modified-Since"] = cached.identity.last_modified
    return headers


def _request_once(
    opener,
    *,
    uri: str,
    headers: Mapping[str, str],
    policy: HttpFetchPolicy,
):  # type: ignore[no-untyped-def]
    request = Request(uri, headers=dict(headers), method="GET")
    try:
        return opener.open(request, timeout=policy.timeout_seconds)
    except HTTPError as error:
        return error
    except URLError as error:
        raise OslcTransportError("unavailable", f"OSLC provider unavailable: {error.reason}") from error
    except TimeoutError as error:
        raise OslcTransportError("timeout", "OSLC request timed out") from error


def fetch_oslc_resource(
    *,
    resource_uri: str,
    service_provider_uri: str,
    cache_root: Path,
    cache_policy: CachePolicy,
    now: str,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
) -> OslcFetchResult:
    """Fetch one OSLC resource with bounded, read-only HTTP semantics.

    Fresh cache wins without network I/O. Stale observations are used only for
    conditional requests or, when explicitly allowed, as an offline fallback.
    Authentication headers are request-only inputs and are never persisted.
    """
    _require_http_uri(resource_uri, "resource_uri")
    _require_http_uri(service_provider_uri, "service_provider_uri")

    cached = select_cached_representation(
        cache_root,
        resource_uri=resource_uri,
        policy=cache_policy,
        now=now,
    )
    if cached is not None and cached.decision == "fresh":
        return OslcFetchResult(
            source="cache-fresh",
            representation=cached.representation,
            payload=cached.payload,
        )

    latest = latest_cached_representation(cache_root, resource_uri=resource_uri)
    headers = {
        "Accept": ", ".join(sorted(SUPPORTED_OSLC_MEDIA_TYPES)),
        "User-Agent": "quarto-needs/0.1 OSLC read-only client",
        **_conditional_headers(latest),
    }
    if auth_headers:
        headers.update(auth_headers)

    transport = opener or build_opener(_NoRedirect())
    current_uri = resource_uri

    for redirect_count in range(fetch_policy.max_redirects + 1):
        response = _request_once(
            transport,
            uri=current_uri,
            headers=headers,
            policy=fetch_policy,
        )
        status = getattr(response, "status", getattr(response, "code", None))

        if status in {301, 302, 303, 307, 308}:
            if redirect_count >= fetch_policy.max_redirects:
                raise OslcTransportError("redirect-limit", "OSLC redirect limit exceeded")
            location = response.headers.get("Location")
            if not location:
                raise OslcTransportError("redirect-invalid", "OSLC redirect omitted Location")
            next_uri = urljoin(current_uri, location)
            _require_http_uri(next_uri, "redirect URI")
            current_uri = next_uri
            continue

        if status == 304:
            if latest is None:
                raise OslcTransportError(
                    "invalid-response",
                    "OSLC provider returned 304 without a cached representation",
                )
            payload = read_cached_payload(cache_root, latest)
            refreshed = CachedRepresentation(
                identity=ExternalResourceIdentity(
                    resource_uri=resource_uri,
                    service_provider_uri=service_provider_uri,
                    digest=latest.identity.digest,
                    fetched_at=now,
                    trust_state=latest.identity.trust_state,
                    etag=response.headers.get("ETag") or latest.identity.etag,
                    last_modified=response.headers.get("Last-Modified")
                    or latest.identity.last_modified,
                ),
                media_type=latest.media_type,
            )
            store_cached_representation(cache_root, refreshed, payload)
            return OslcFetchResult(
                source="live-not-modified",
                representation=refreshed,
                payload=payload,
            )

        if status in {401, 403}:
            raise OslcTransportError("authentication-required", f"OSLC provider returned HTTP {status}")
        if status is None or status < 200 or status >= 300:
            raise OslcTransportError("unavailable", f"OSLC provider returned HTTP {status}")

        media_type = _media_type(response.headers.get("Content-Type"))
        payload = _read_bounded(response, fetch_policy.max_bytes)
        representation = CachedRepresentation(
            identity=ExternalResourceIdentity(
                resource_uri=resource_uri,
                service_provider_uri=service_provider_uri,
                digest=content_digest(payload),
                fetched_at=now,
                trust_state="unverified",
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            ),
            media_type=media_type,
        )
        store_cached_representation(cache_root, representation, payload)
        return OslcFetchResult(
            source="live",
            representation=representation,
            payload=payload,
        )

    raise AssertionError("redirect loop exhausted without returning")


def fetch_oslc_resource_with_offline_fallback(
    **kwargs,
) -> OslcFetchResult:  # type: ignore[no-untyped-def]
    """Fetch live, falling back only to cache admitted by the configured policy."""
    try:
        return fetch_oslc_resource(**kwargs)
    except OslcTransportError as error:
        cache_root = kwargs["cache_root"]
        resource_uri = kwargs["resource_uri"]
        cache_policy = kwargs["cache_policy"]
        now = kwargs["now"]
        cached: CacheSelection | None = select_cached_representation(
            cache_root,
            resource_uri=resource_uri,
            policy=cache_policy,
            now=now,
        )
        if cached is None:
            raise error
        return OslcFetchResult(
            source=f"cache-{cached.decision}",
            representation=cached.representation,
            payload=cached.payload,
        )
