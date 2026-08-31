from __future__ import annotations

from pathlib import Path
from urllib.error import URLError

import pytest

from quarto_needs.oslc_cache import CachedRepresentation, store_cached_representation
from quarto_needs.oslc_http import (
    HttpFetchPolicy,
    OslcTransportError,
    fetch_oslc_resource,
    fetch_oslc_resource_with_offline_fallback,
)
from quarto_needs.oslc_rm import CachePolicy, ExternalResourceIdentity, content_digest


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
        if amount < 0:
            return self._payload
        return self._payload[:amount]


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


def _cached(
    root: Path,
    *,
    payload: bytes = b"cached",
    fetched_at: str = "2026-08-30T18:00:00Z",
) -> CachedRepresentation:
    representation = CachedRepresentation(
        identity=ExternalResourceIdentity(
            resource_uri="https://provider.test/oslc/sp/1",
            service_provider_uri="https://provider.test/oslc/sp/1",
            digest=content_digest(payload),
            fetched_at=fetched_at,
            etag='"etag-1"',
            last_modified="Sun, 30 Aug 2026 18:00:00 GMT",
        ),
        media_type="application/ld+json",
    )
    store_cached_representation(root, representation, payload)
    return representation


def _kwargs(tmp_path: Path) -> dict[str, object]:
    return {
        "resource_uri": "https://provider.test/oslc/sp/1",
        "service_provider_uri": "https://provider.test/oslc/sp/1",
        "cache_root": tmp_path,
        "cache_policy": CachePolicy(max_age_seconds=3600),
        "now": "2026-08-30T21:00:00Z",
    }


def test_fresh_cache_avoids_network_io(tmp_path: Path) -> None:
    _cached(tmp_path, fetched_at="2026-08-30T20:30:00Z")
    opener = _Opener()

    result = fetch_oslc_resource(**_kwargs(tmp_path), opener=opener)

    assert result.source == "cache-fresh"
    assert result.payload == b"cached"
    assert opener.requests == []


def test_live_get_is_bounded_cached_and_does_not_persist_auth_headers(tmp_path: Path) -> None:
    payload = b'{"@id":"https://provider.test/oslc/sp/1"}'
    opener = _Opener(
        _Response(
            200,
            payload,
            **{
                "Content-Type": "application/ld+json; charset=utf-8",
                "Content-Length": str(len(payload)),
                "ETag": '"etag-2"',
            },
        )
    )

    result = fetch_oslc_resource(
        **_kwargs(tmp_path),
        opener=opener,
        auth_headers={"Authorization": "Bearer top-secret"},
        fetch_policy=HttpFetchPolicy(max_bytes=1024),
    )

    assert result.source == "live"
    assert result.payload == payload
    request, timeout = opener.requests[0]
    assert request.get_method() == "GET"
    assert request.get_header("Authorization") == "Bearer top-secret"
    assert timeout == 10.0
    manifest = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert "top-secret" not in manifest
    assert "Authorization" not in manifest


def test_stale_cache_drives_conditional_get_and_304_refresh(tmp_path: Path) -> None:
    old = _cached(tmp_path)
    opener = _Opener(_Response(304, ETag='"etag-1"'))

    result = fetch_oslc_resource(**_kwargs(tmp_path), opener=opener)

    assert result.source == "live-not-modified"
    assert result.payload == b"cached"
    assert result.representation.identity.digest == old.identity.digest
    assert result.representation.identity.fetched_at == "2026-08-30T21:00:00Z"
    request, _ = opener.requests[0]
    assert request.get_header("If-none-match") == '"etag-1"'
    assert request.get_header("If-modified-since") == "Sun, 30 Aug 2026 18:00:00 GMT"


def test_transport_rejects_unsupported_media_type_and_oversized_payload(tmp_path: Path) -> None:
    opener = _Opener(_Response(200, b"html", **{"Content-Type": "text/html"}))
    with pytest.raises(OslcTransportError) as unsupported:
        fetch_oslc_resource(**_kwargs(tmp_path), opener=opener)
    assert unsupported.value.code == "unsupported-media-type"

    opener = _Opener(
        _Response(
            200,
            b"0123456789",
            **{"Content-Type": "application/ld+json", "Content-Length": "10"},
        )
    )
    with pytest.raises(OslcTransportError) as too_large:
        fetch_oslc_resource(
            **_kwargs(tmp_path),
            opener=opener,
            fetch_policy=HttpFetchPolicy(max_bytes=5),
        )
    assert too_large.value.code == "response-too-large"


def test_redirects_are_same_origin_and_bounded(tmp_path: Path) -> None:
    same_origin_root = tmp_path / "same-origin"
    opener = _Opener(
        _Response(302, Location="/oslc/sp/final"),
        _Response(200, b"{}", **{"Content-Type": "application/ld+json"}),
    )
    result = fetch_oslc_resource(**_kwargs(same_origin_root), opener=opener)
    assert result.source == "live"
    assert opener.requests[1][0].full_url == "https://provider.test/oslc/sp/final"

    cross_origin_root = tmp_path / "cross-origin"
    opener = _Opener(_Response(302, Location="https://evil.test/steal"))
    with pytest.raises(OslcTransportError) as cross_origin:
        fetch_oslc_resource(
            **_kwargs(cross_origin_root),
            opener=opener,
            auth_headers={"Authorization": "Bearer secret"},
        )
    assert cross_origin.value.code == "redirect-origin"
    assert len(opener.requests) == 1

    redirect_limit_root = tmp_path / "redirect-limit"
    opener = _Opener(_Response(302, Location="/again"))
    with pytest.raises(OslcTransportError) as redirect_limit:
        fetch_oslc_resource(
            **_kwargs(redirect_limit_root),
            opener=opener,
            fetch_policy=HttpFetchPolicy(max_redirects=0),
        )
    assert redirect_limit.value.code == "redirect-limit"


def test_offline_fallback_requires_explicit_stale_permission(tmp_path: Path) -> None:
    _cached(tmp_path)
    unavailable = _Opener(URLError("offline"))

    with pytest.raises(OslcTransportError) as strict:
        fetch_oslc_resource_with_offline_fallback(
            **_kwargs(tmp_path),
            opener=unavailable,
        )
    assert strict.value.code == "unavailable"

    permissive = dict(_kwargs(tmp_path))
    permissive["cache_policy"] = CachePolicy(max_age_seconds=3600, allow_stale=True)
    result = fetch_oslc_resource_with_offline_fallback(
        **permissive,
        opener=_Opener(URLError("offline")),
    )
    assert result.source == "cache-stale-allowed"
    assert result.payload == b"cached"


def test_authentication_failure_is_not_hidden_by_stale_cache(tmp_path: Path) -> None:
    _cached(tmp_path)
    permissive = dict(_kwargs(tmp_path))
    permissive["cache_policy"] = CachePolicy(max_age_seconds=3600, allow_stale=True)

    with pytest.raises(OslcTransportError) as denied:
        fetch_oslc_resource_with_offline_fallback(
            **permissive,
            opener=_Opener(_Response(401)),
        )
    assert denied.value.code == "authentication-required"
