from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .oslc_http import HttpFetchPolicy

# Transport-owned headers a caller-supplied auth adapter must not override.
# Authorization is deliberately not protected: that is exactly how a caller
# supplies GitHub credentials via auth_headers.
_PROTECTED_REQUEST_HEADERS = {"accept", "user-agent"}


class GitHubTransportError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class GitHubRateLimitError(GitHubTransportError):
    """GitHub's rate limiting, distinguished from auth/availability failures.

    Raised for a ``429`` (GitHub uses it for both primary and secondary
    limits) or a ``403`` carrying either ``X-RateLimit-Remaining: 0``
    (GitHub's primary-exhaustion shape) or a ``Retry-After`` header (the
    secondary/abuse-limit shape, which does not necessarily zero the
    primary quota header). A ``403`` with neither signal is *not* a rate
    limit and keeps raising the generic ``authentication-required`` error.
    The transport reports the server's retry facts and never sleeps on its
    own; ``retry_after_seconds`` comes from ``Retry-After`` (integer-seconds
    form, the only form GitHub sends) and ``rate_limit_reset_epoch`` from
    ``X-RateLimit-Reset``, both ``None`` when the server omitted them.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None,
        rate_limit_reset_epoch: int | None,
    ) -> None:
        super().__init__("rate-limited", message)
        self.retry_after_seconds = retry_after_seconds
        self.rate_limit_reset_epoch = rate_limit_reset_epoch


@dataclass(frozen=True, slots=True)
class GitHubFetchResult:
    payload: bytes | None
    etag: str | None
    last_modified: str | None
    # Raw Link header, surfaced for callers (e.g. list pagination) that need
    # response-level navigation facts; the transport itself never follows it.
    link: str | None = None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _require_http_uri(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute http(s) URI")


def _origin(value: str) -> tuple[str, str, int]:
    parsed = urlparse(value)
    scheme = parsed.scheme.lower()
    default_port = 443 if scheme == "https" else 80
    return (scheme, (parsed.hostname or "").lower(), parsed.port or default_port)


def _merge_auth_headers(headers: dict[str, str], auth_headers: Mapping[str, str] | None) -> None:
    if not auth_headers:
        return
    for name, value in auth_headers.items():
        if name.casefold() in _PROTECTED_REQUEST_HEADERS:
            raise ValueError(f"authentication adapter must not override transport header {name}")
        headers[name] = value


def _media_type(value: str | None) -> str:
    if value is None:
        raise GitHubTransportError("unsupported-media-type", "GitHub response omitted Content-Type")
    media_type = value.split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise GitHubTransportError(
            "unsupported-media-type",
            f"unsupported GitHub response media type: {media_type or value!r}",
        )
    return media_type


def _header_int(headers, name: str) -> int | None:  # type: ignore[no-untyped-def]
    value = headers.get(name)
    if value is None:
        return None
    try:
        parsed = int(value.strip())
    except ValueError as error:
        raise GitHubTransportError(
            "invalid-response", f"GitHub sent a non-integer {name} header: {value!r}"
        ) from error
    return parsed


def _rate_limit_error(status: int, headers) -> GitHubRateLimitError:  # type: ignore[no-untyped-def]
    retry_after = _header_int(headers, "Retry-After")
    reset_epoch = _header_int(headers, "X-RateLimit-Reset")
    facts = [f"HTTP {status}"]
    if retry_after is not None:
        facts.append(f"Retry-After={retry_after}s")
    if reset_epoch is not None:
        facts.append(f"X-RateLimit-Reset={reset_epoch}")
    return GitHubRateLimitError(
        "GitHub rate limit exhausted (" + ", ".join(facts) + ")",
        retry_after_seconds=retry_after,
        rate_limit_reset_epoch=reset_epoch,
    )


def _read_bounded(response, max_bytes: int) -> bytes:  # type: ignore[no-untyped-def]
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as error:
            raise GitHubTransportError("invalid-response", "invalid Content-Length header") from error
        if declared < 0:
            raise GitHubTransportError("invalid-response", "negative Content-Length header")
        if declared > max_bytes:
            raise GitHubTransportError(
                "response-too-large",
                f"GitHub response declares {declared} bytes, limit is {max_bytes}",
            )
    payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise GitHubTransportError(
            "response-too-large",
            f"GitHub response exceeds byte limit {max_bytes}",
        )
    return payload


def fetch_github_resource(
    uri: str,
    *,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    if_none_match: str | None = None,
    if_modified_since: str | None = None,
    opener=None,
) -> GitHubFetchResult:
    """Fetch one GitHub REST API resource with bounded, GET-only HTTP semantics.

    Transport only: no caching and no query/listing support — those are
    separate, later contracts, exactly as OSLC federation built cache,
    query, and observation as their own reviewed slices rather than one
    large fetch function. This does send conditional-request headers when
    the caller (typically a cache layer) supplies them, and returns
    ``GitHubFetchResult(payload=None, ...)`` on a ``304 Not Modified``
    rather than attempting to media-type- or byte-limit-check a response
    with no body. Redirects are same-origin only so an Authorization header
    cannot leak to an attacker-controlled host.
    """
    _require_http_uri(uri, "uri")
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "quarto-needs/0.1 GitHub read-only client",
    }
    if if_none_match:
        headers["If-None-Match"] = if_none_match
    if if_modified_since:
        headers["If-Modified-Since"] = if_modified_since
    _merge_auth_headers(headers, auth_headers)

    transport = opener or build_opener(_NoRedirect())
    current_uri = uri
    allowed_origin = _origin(uri)

    for redirect_count in range(fetch_policy.max_redirects + 1):
        request = Request(current_uri, headers=headers, method="GET")
        try:
            response = transport.open(request, timeout=fetch_policy.timeout_seconds)
        except HTTPError as error:
            response = error
        except URLError as error:
            raise GitHubTransportError("unavailable", f"GitHub unavailable: {error.reason}") from error
        except TimeoutError as error:
            raise GitHubTransportError("timeout", "GitHub request timed out") from error

        status = getattr(response, "status", getattr(response, "code", None))

        if status in {301, 302, 303, 307, 308}:
            if redirect_count >= fetch_policy.max_redirects:
                raise GitHubTransportError("redirect-limit", "GitHub redirect limit exceeded")
            location = response.headers.get("Location")
            if not location:
                raise GitHubTransportError("redirect-invalid", "GitHub redirect omitted Location")
            next_uri = urljoin(current_uri, location)
            _require_http_uri(next_uri, "redirect URI")
            if _origin(next_uri) != allowed_origin:
                raise GitHubTransportError(
                    "redirect-origin", "GitHub redirect crossed origin and was rejected"
                )
            current_uri = next_uri
            continue

        if status == 304:
            return GitHubFetchResult(
                payload=None,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                link=response.headers.get("Link"),
            )

        if status == 429 or (
            status == 403
            and (
                (response.headers.get("X-RateLimit-Remaining") or "").strip() == "0"
                or response.headers.get("Retry-After") is not None
            )
        ):
            raise _rate_limit_error(status, response.headers)
        if status in {401, 403}:
            raise GitHubTransportError("authentication-required", f"GitHub returned HTTP {status}")
        if status == 404:
            raise GitHubTransportError("not-found", "GitHub resource not found")
        if status is None or status < 200 or status >= 300:
            raise GitHubTransportError("unavailable", f"GitHub returned HTTP {status}")

        _media_type(response.headers.get("Content-Type"))
        try:
            payload = _read_bounded(response, fetch_policy.max_bytes)
        except TimeoutError as error:
            raise GitHubTransportError("timeout", "GitHub request timed out") from error
        return GitHubFetchResult(
            payload=payload,
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
            link=response.headers.get("Link"),
        )

    raise GitHubTransportError("redirect-limit", "GitHub redirect limit exceeded")
