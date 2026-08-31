from __future__ import annotations

from urllib.error import URLError

import pytest

from quarto_needs.github_http import GitHubTransportError, fetch_github_resource
from quarto_needs.oslc_http import HttpFetchPolicy


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
        self.requests: list = []

    def open(self, request, timeout: float):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


URI = "https://api.github.com/repos/acme/widgets/issues/1"


def test_fetch_github_resource_returns_payload_and_validators() -> None:
    opener = _Opener(
        _Response(
            200,
            b'{"number": 1}',
            **{
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": "13",
                "ETag": '"abc123"',
                "Last-Modified": "Mon, 31 Aug 2026 12:00:00 GMT",
            },
        )
    )

    result = fetch_github_resource(URI, opener=opener)

    assert result.payload == b'{"number": 1}'
    assert result.etag == '"abc123"'
    assert result.last_modified == "Mon, 31 Aug 2026 12:00:00 GMT"
    request = opener.requests[0]
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert request.get_header("User-agent")


def test_fetch_github_resource_merges_authorization_header() -> None:
    opener = _Opener(_Response(200, b"{}", **{"Content-Type": "application/json"}))

    fetch_github_resource(URI, opener=opener, auth_headers={"Authorization": "Bearer tok"})

    assert opener.requests[0].get_header("Authorization") == "Bearer tok"


def test_fetch_github_resource_rejects_auth_header_overriding_transport_headers() -> None:
    opener = _Opener()
    with pytest.raises(ValueError, match="Accept"):
        fetch_github_resource(URI, opener=opener, auth_headers={"Accept": "text/plain"})


def test_fetch_github_resource_enforces_declared_byte_limit() -> None:
    opener = _Opener(
        _Response(200, b"{}", **{"Content-Type": "application/json", "Content-Length": "999999999"})
    )
    with pytest.raises(GitHubTransportError) as excinfo:
        fetch_github_resource(URI, opener=opener, fetch_policy=HttpFetchPolicy(max_bytes=100))
    assert excinfo.value.code == "response-too-large"


def test_fetch_github_resource_enforces_actual_byte_limit_without_content_length() -> None:
    opener = _Opener(_Response(200, b"x" * 200, **{"Content-Type": "application/json"}))
    with pytest.raises(GitHubTransportError) as excinfo:
        fetch_github_resource(URI, opener=opener, fetch_policy=HttpFetchPolicy(max_bytes=100))
    assert excinfo.value.code == "response-too-large"


def test_fetch_github_resource_follows_same_origin_redirect() -> None:
    opener = _Opener(
        _Response(302, b"", Location="https://api.github.com/repos/acme/widgets/issues/2"),
        _Response(200, b'{"number": 2}', **{"Content-Type": "application/json"}),
    )
    result = fetch_github_resource(URI, opener=opener)
    assert result.payload == b'{"number": 2}'
    assert len(opener.requests) == 2


def test_fetch_github_resource_rejects_cross_origin_redirect() -> None:
    opener = _Opener(_Response(302, b"", Location="https://evil.example/steal"))
    with pytest.raises(GitHubTransportError) as excinfo:
        fetch_github_resource(URI, opener=opener)
    assert excinfo.value.code == "redirect-origin"


def test_fetch_github_resource_enforces_redirect_limit() -> None:
    opener = _Opener(
        _Response(302, b"", Location=URI),
        _Response(302, b"", Location=URI),
    )
    with pytest.raises(GitHubTransportError) as excinfo:
        fetch_github_resource(URI, opener=opener, fetch_policy=HttpFetchPolicy(max_redirects=1))
    assert excinfo.value.code == "redirect-limit"


def test_fetch_github_resource_reports_authentication_required() -> None:
    opener = _Opener(_Response(401, b""))
    with pytest.raises(GitHubTransportError) as excinfo:
        fetch_github_resource(URI, opener=opener)
    assert excinfo.value.code == "authentication-required"


def test_fetch_github_resource_reports_not_found() -> None:
    opener = _Opener(_Response(404, b""))
    with pytest.raises(GitHubTransportError) as excinfo:
        fetch_github_resource(URI, opener=opener)
    assert excinfo.value.code == "not-found"


def test_fetch_github_resource_rejects_unsupported_media_type() -> None:
    opener = _Opener(_Response(200, b"<html></html>", **{"Content-Type": "text/html"}))
    with pytest.raises(GitHubTransportError) as excinfo:
        fetch_github_resource(URI, opener=opener)
    assert excinfo.value.code == "unsupported-media-type"


def test_fetch_github_resource_reports_network_unavailable() -> None:
    opener = _Opener(URLError("no route to host"))
    with pytest.raises(GitHubTransportError) as excinfo:
        fetch_github_resource(URI, opener=opener)
    assert excinfo.value.code == "unavailable"


def test_fetch_github_resource_rejects_non_http_uri() -> None:
    with pytest.raises(ValueError):
        fetch_github_resource("ftp://api.github.com/x", opener=_Opener())


def test_fetch_github_resource_sends_conditional_headers_when_provided() -> None:
    opener = _Opener(_Response(200, b"{}", **{"Content-Type": "application/json"}))

    fetch_github_resource(
        URI,
        opener=opener,
        if_none_match='"cached-etag"',
        if_modified_since="Mon, 31 Aug 2026 12:00:00 GMT",
    )

    request = opener.requests[0]
    assert request.get_header("If-none-match") == '"cached-etag"'
    assert request.get_header("If-modified-since") == "Mon, 31 Aug 2026 12:00:00 GMT"


def test_fetch_github_resource_omits_conditional_headers_when_not_provided() -> None:
    opener = _Opener(_Response(200, b"{}", **{"Content-Type": "application/json"}))

    fetch_github_resource(URI, opener=opener)

    request = opener.requests[0]
    assert request.get_header("If-none-match") is None
    assert request.get_header("If-modified-since") is None


def test_fetch_github_resource_returns_not_modified_result_on_304() -> None:
    opener = _Opener(
        _Response(304, b"", **{"ETag": '"same-etag"', "Last-Modified": "Mon, 31 Aug 2026 12:00:00 GMT"})
    )

    result = fetch_github_resource(URI, opener=opener, if_none_match='"same-etag"')

    assert result.payload is None
    assert result.etag == '"same-etag"'
    assert result.last_modified == "Mon, 31 Aug 2026 12:00:00 GMT"


def test_fetch_github_resource_304_response_is_not_media_type_or_byte_checked() -> None:
    # A 304 carries no body and often no Content-Type at all; it must not be
    # run through the application/json media-type check or the byte-limit
    # reader that a 200 response is.
    opener = _Opener(_Response(304, b""))

    result = fetch_github_resource(URI, opener=opener, if_none_match='"etag"')

    assert result.payload is None
