from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, cast
from urllib.parse import quote, urlencode, urlparse

from .github_http import fetch_github_resource
from .oslc_cache import (
    CachedRepresentation,
    latest_cached_representation,
    read_cached_payload,
    select_cached_representation,
    store_cached_representation,
)
from .oslc_http import HttpFetchPolicy
from .oslc_reconcile import ExternalRequirementObservation
from .oslc_rm import CachePolicy, ExternalResourceIdentity, TrustState, content_digest

_SUPPORTED_STATES = {"open", "closed"}
_SUPPORTED_LIST_STATES = {"open", "closed", "all"}
_SUPPORTED_LIST_SORTS = {"created", "updated", "comments"}
_SUPPORTED_LIST_DIRECTIONS = {"asc", "desc"}
GITHUB_ISSUES_CACHE_SCHEMA = "github-issues-cache-v1"


class GitHubIssueError(ValueError):
    pass


def github_issue_resource_uri(owner: str, repo: str, number: int) -> str:
    """Build the deterministic GitHub REST API URL identifying one issue."""
    if not owner.strip():
        raise GitHubIssueError("owner must be non-empty")
    if not repo.strip():
        raise GitHubIssueError("repo must be non-empty")
    if number <= 0:
        raise GitHubIssueError("issue number must be positive")
    return f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/issues/{number}"


def build_github_issue_identity(
    owner: str,
    repo: str,
    number: int,
    *,
    payload_bytes: bytes,
    fetched_at: str,
    trust_state: TrustState = "unverified",
    etag: str | None = None,
    last_modified: str | None = None,
) -> ExternalResourceIdentity:
    """Build the external identity for one fetched GitHub issue representation.

    ``payload_bytes`` must be the exact bytes actually fetched, so the digest
    reflects the observed representation rather than a re-serialization of
    parsed fields.
    """
    return ExternalResourceIdentity(
        resource_uri=github_issue_resource_uri(owner, repo, number),
        service_provider_uri=f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}",
        digest=content_digest(payload_bytes),
        fetched_at=fetched_at,
        trust_state=trust_state,
        etag=etag,
        last_modified=last_modified,
    )


def _non_empty_string(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise GitHubIssueError(f"GitHub issue payload is missing a non-empty {field!r}")
    return value


def parse_external_github_issue(
    payload: Mapping[str, object],
    *,
    identity: ExternalResourceIdentity,
) -> ExternalRequirementObservation:
    """Normalize one fetched GitHub issue without creating canonical identity.

    ``identity.resource_uri`` remains the provenance authority; the issue
    number is data only (``external_identifier``) and is never promoted into
    a Quarto-Needs canonical ID by this parser. Transport/fetch is
    intentionally outside this pure function, matching the OSLC observation
    parser's split between network and normalization.
    """
    if "pull_request" in payload:
        raise GitHubIssueError(
            "GitHub resource is a pull request, not an issue; "
            "pull requests are not supported by this adapter"
        )

    number = payload.get("number")
    if not isinstance(number, int) or isinstance(number, bool):
        raise GitHubIssueError("GitHub issue payload is missing an integer 'number'")

    title = _non_empty_string(payload, "title")
    html_url = _non_empty_string(payload, "html_url")
    updated_at = _non_empty_string(payload, "updated_at")

    state = payload.get("state")
    if state not in _SUPPORTED_STATES:
        raise GitHubIssueError(
            f"GitHub issue payload has an unsupported 'state': {state!r}"
        )

    body = payload.get("body")
    description = body if isinstance(body, str) else ""

    labels: list[str] = []
    raw_labels = payload.get("labels")
    if isinstance(raw_labels, list):
        for entry in raw_labels:
            if isinstance(entry, Mapping) and isinstance(entry.get("name"), str):
                labels.append(entry["name"])

    return ExternalRequirementObservation(
        identity=identity,
        title=title.strip(),
        description=description,
        external_identifier=str(number),
        attributes={
            "state": state,
            "htmlUrl": html_url,
            "updatedAt": updated_at,
            "labels": sorted(labels),
        },
    )


def _observation_from_payload_bytes(
    payload_bytes: bytes, *, identity: ExternalResourceIdentity
) -> ExternalRequirementObservation:
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as error:
        raise GitHubIssueError(f"GitHub response is not valid JSON: {error}") from error
    if not isinstance(payload, Mapping):
        raise GitHubIssueError("GitHub response is not a JSON object")
    return parse_external_github_issue(payload, identity=identity)


def fetch_external_github_issue(
    owner: str,
    repo: str,
    number: int,
    *,
    fetched_at: str,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
    cache_root: Path | None = None,
    cache_policy: CachePolicy = CachePolicy(max_age_seconds=300),
) -> ExternalRequirementObservation:
    """Fetch and normalize one GitHub issue end to end.

    Composes the bounded transport (``fetch_github_resource``) with identity
    construction and normalization. Caching is opt-in: pass ``cache_root``
    to check a fresh cached representation first and skip the network
    entirely, and to persist a live fetch afterward. When the cache exists
    but is stale, the request carries conditional headers (``If-None-Match``/
    ``If-Modified-Since``) built from that stale entry's own validators; a
    ``304`` reuses the cached body under a refreshed identity (new
    ``fetched_at``, same digest) instead of re-downloading it, exactly as
    OSLC's own cache-then-conditional-request flow works.
    """
    resource_uri = github_issue_resource_uri(owner, repo, number)
    latest: CachedRepresentation | None = None

    if cache_root is not None:
        selection = select_cached_representation(
            cache_root,
            resource_uri=resource_uri,
            policy=cache_policy,
            now=fetched_at,
            schema=GITHUB_ISSUES_CACHE_SCHEMA,
        )
        if selection is not None and selection.decision == "fresh":
            return _observation_from_payload_bytes(
                selection.payload, identity=selection.representation.identity
            )
        latest = latest_cached_representation(
            cache_root, resource_uri=resource_uri, schema=GITHUB_ISSUES_CACHE_SCHEMA
        )

    result = fetch_github_resource(
        resource_uri,
        fetch_policy=fetch_policy,
        auth_headers=auth_headers,
        if_none_match=latest.identity.etag if latest is not None else None,
        if_modified_since=latest.identity.last_modified if latest is not None else None,
        opener=opener,
    )

    if result.payload is None:
        # 304: the caller had something to condition against, so latest is
        # guaranteed here — the transport cannot invent a 304 on its own.
        assert latest is not None
        assert cache_root is not None
        payload_bytes = read_cached_payload(cache_root, latest)
        identity = ExternalResourceIdentity(
            resource_uri=latest.identity.resource_uri,
            service_provider_uri=latest.identity.service_provider_uri,
            digest=latest.identity.digest,
            fetched_at=fetched_at,
            trust_state=latest.identity.trust_state,
            etag=result.etag or latest.identity.etag,
            last_modified=result.last_modified or latest.identity.last_modified,
        )
        observation = _observation_from_payload_bytes(payload_bytes, identity=identity)
        store_cached_representation(
            cache_root,
            CachedRepresentation(identity=identity, media_type="application/json"),
            payload_bytes,
            schema=GITHUB_ISSUES_CACHE_SCHEMA,
        )
        return observation

    identity = build_github_issue_identity(
        owner,
        repo,
        number,
        payload_bytes=result.payload,
        fetched_at=fetched_at,
        etag=result.etag,
        last_modified=result.last_modified,
    )
    observation = _observation_from_payload_bytes(result.payload, identity=identity)

    if cache_root is not None:
        store_cached_representation(
            cache_root,
            CachedRepresentation(identity=identity, media_type="application/json"),
            result.payload,
            schema=GITHUB_ISSUES_CACHE_SCHEMA,
        )

    return observation


@dataclass(frozen=True, slots=True)
class GitHubIssueListResult:
    """The outcome of one bounded issue-list query: discovery, not observation.

    List entries carry full issue bodies inline, but that inline data is
    never promoted into an ``ExternalRequirementObservation`` here — the
    same boundary OSLC's query step draws around inline query-container
    data. Fetch each ``issue_numbers`` entry independently with
    ``fetch_external_github_issue`` for a provenance-bound observation.
    """

    resource_uri: str
    fetched_at: str
    response_digest: str
    issue_numbers: tuple[int, ...]
    pull_request_numbers: tuple[int, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "github-issue-list-v1",
            "resourceUri": self.resource_uri,
            "fetchedAt": self.fetched_at,
            "responseDigest": self.response_digest,
            "issueNumbers": list(self.issue_numbers),
            "pullRequestNumbers": list(self.pull_request_numbers),
        }


def github_issue_list_resource_uri(
    owner: str,
    repo: str,
    *,
    state: str = "open",
    per_page: int = 30,
    page: int = 1,
    labels: Sequence[str] | None = None,
    sort: str | None = None,
    direction: str | None = None,
    since: str | None = None,
) -> str:
    """Build the deterministic GitHub REST API URL for one bounded issue-list page.

    ``labels``/``since``/``sort``/``direction`` are the list endpoint's own
    documented filter parameters (never the separate search API); every
    filter is explicit in the resulting URL, so one URI always identifies
    exactly one bounded page.
    """
    if not owner.strip():
        raise GitHubIssueError("owner must be non-empty")
    if not repo.strip():
        raise GitHubIssueError("repo must be non-empty")
    if state not in _SUPPORTED_LIST_STATES:
        raise GitHubIssueError(f"unsupported issue list state: {state!r}")
    if not (1 <= per_page <= 100):
        raise GitHubIssueError("per_page must be between 1 and 100")
    if page < 1:
        raise GitHubIssueError("page must be a positive integer")
    if sort is not None and sort not in _SUPPORTED_LIST_SORTS:
        raise GitHubIssueError(f"unsupported issue list sort: {sort!r}")
    if direction is not None and direction not in _SUPPORTED_LIST_DIRECTIONS:
        raise GitHubIssueError(f"unsupported issue list direction: {direction!r}")
    if since is not None and (not isinstance(since, str) or not since.strip()):
        raise GitHubIssueError("since must be a non-empty timestamp string when present")
    if labels is not None:
        if isinstance(labels, str) or not isinstance(labels, Sequence):
            raise GitHubIssueError("labels must be a sequence of label names, not a string")
        for label in labels:
            if not isinstance(label, str) or not label.strip():
                raise GitHubIssueError("every label must be a non-empty string")

    params: dict[str, object] = {"state": state, "per_page": per_page, "page": page}
    if labels:
        params["labels"] = ",".join(labels)
    if sort is not None:
        params["sort"] = sort
    if direction is not None:
        params["direction"] = direction
    if since is not None:
        params["since"] = since.strip()
    query = urlencode(params)
    return f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/issues?{query}"


def _parse_issue_list_payload(payload: object) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Split one page's entries into issues and pull requests.

    Preserves GitHub's own response order (only dropping exact repeats)
    rather than re-sorting numerically — the list/search endpoints' own
    ``sort``/``direction``/``order`` parameters exist precisely so a caller
    can request an ordering other than ascending issue number, and a
    forced re-sort here would silently discard that ordering.
    """
    if not isinstance(payload, list):
        raise GitHubIssueError("GitHub issue list response is not a JSON array")

    issue_numbers: list[int] = []
    pull_request_numbers: list[int] = []
    seen_issues: set[int] = set()
    seen_pull_requests: set[int] = set()
    for entry in payload:
        if not isinstance(entry, Mapping):
            raise GitHubIssueError("GitHub issue list entry is not a JSON object")
        number = entry.get("number")
        if not isinstance(number, int) or isinstance(number, bool):
            raise GitHubIssueError("GitHub issue list entry is missing an integer 'number'")
        if "pull_request" in entry:
            if number not in seen_pull_requests:
                seen_pull_requests.add(number)
                pull_request_numbers.append(number)
        elif number not in seen_issues:
            seen_issues.add(number)
            issue_numbers.append(number)

    return tuple(issue_numbers), tuple(pull_request_numbers)


def _split_link_header(link_header: str) -> list[str]:
    """Split an RFC 5988 Link header into entries at commas outside ``<...>``."""
    entries: list[str] = []
    current: list[str] = []
    inside_target = False
    for char in link_header:
        if char == "<":
            inside_target = True
        elif char == ">":
            inside_target = False
        if char == "," and not inside_target:
            entries.append("".join(current))
            current = []
            continue
        current.append(char)
    entries.append("".join(current))
    return [entry.strip() for entry in entries if entry.strip()]


def parse_next_link(link_header: str | None) -> str | None:
    """Extract the ``rel="next"`` target from a GitHub ``Link`` header.

    Strict by design: a present-but-malformed header raises rather than
    silently reading as "no next page" — a silent stop would misreport a
    truncated traversal as a complete one.
    """
    if link_header is None:
        return None
    next_uri: str | None = None
    for entry in _split_link_header(link_header):
        if not entry.startswith("<") or ">" not in entry:
            raise GitHubIssueError(f"malformed GitHub Link header entry: {entry!r}")
        target, _, params = entry[1:].partition(">")
        for param in params.split(";"):
            name, _, value = param.strip().partition("=")
            if name.casefold() == "rel" and value.strip().strip('"').casefold() == "next":
                if next_uri is not None:
                    raise GitHubIssueError(
                        'GitHub Link header declares more than one rel="next" target'
                    )
                next_uri = target.strip()
    return next_uri


def _uri_origin(value: str) -> tuple[str, str, int]:
    # Same check as github_http's private redirect-origin guard, duplicated
    # rather than reaching into that module's underscore internals.
    parsed = urlparse(value)
    scheme = parsed.scheme.lower()
    default_port = 443 if scheme == "https" else 80
    return (scheme, (parsed.hostname or "").lower(), parsed.port or default_port)


def _decode_response_json(result) -> object:  # type: ignore[no-untyped-def]
    try:
        return json.loads(result.payload)
    except json.JSONDecodeError as error:
        raise GitHubIssueError(f"GitHub response is not valid JSON: {error}") from error


def _traverse_discovery_pages(
    first_uri: str,
    *,
    max_pages: int,
    fetch_page,  # type: ignore[no-untyped-def]
) -> tuple[tuple[object, ...], bool]:
    """Follow ``Link: rel="next"`` from ``first_uri`` within a page budget.

    Shared by the list and search discovery traversals. Bounded by design:
    a next link that exists when the budget runs out sets ``truncated``
    rather than being silently ignored or unboundedly followed, and a
    server-provided next URL is followed only within the origin of the
    first request — GitHub legitimately rewrites its own Link targets, so
    path equality is deliberately not required, but a cross-origin next is
    rejected rather than followed.
    """
    allowed_origin = _uri_origin(first_uri)

    pages: list[object] = []
    truncated = False
    current_uri = first_uri
    for index in range(max_pages):
        page, next_uri = fetch_page(current_uri)
        pages.append(page)
        if next_uri is None:
            break
        if index + 1 >= max_pages:
            truncated = True
            break
        if _uri_origin(next_uri) != allowed_origin:
            raise GitHubIssueError(
                f'GitHub Link rel="next" crossed origin and was rejected: {next_uri}'
            )
        current_uri = next_uri

    return tuple(pages), truncated


def _fetch_issue_list_page(
    resource_uri: str,
    *,
    fetched_at: str,
    fetch_policy: HttpFetchPolicy,
    auth_headers: Mapping[str, str] | None,
    opener,
) -> tuple[GitHubIssueListResult, str | None]:
    result = fetch_github_resource(
        resource_uri, fetch_policy=fetch_policy, auth_headers=auth_headers, opener=opener
    )
    payload = _decode_response_json(result)
    issue_numbers, pull_request_numbers = _parse_issue_list_payload(payload)
    next_uri = parse_next_link(result.link)
    page = GitHubIssueListResult(
        resource_uri=resource_uri,
        fetched_at=fetched_at,
        response_digest=content_digest(result.payload),
        issue_numbers=issue_numbers,
        pull_request_numbers=pull_request_numbers,
    )
    return page, next_uri


def fetch_external_github_issue_list(
    owner: str,
    repo: str,
    *,
    fetched_at: str,
    state: str = "open",
    per_page: int = 30,
    page: int = 1,
    labels: Sequence[str] | None = None,
    sort: str | None = None,
    direction: str | None = None,
    since: str | None = None,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
) -> GitHubIssueListResult:
    """Discover which issue numbers exist for one bounded list query.

    A single bounded GET (no follow-your-nose pagination here — the caller
    requests one page at a time and decides whether to request the next).
    Pull requests, which GitHub's issues-list endpoint also returns, are
    reported separately rather than silently mixed in or silently dropped.
    """
    resource_uri = github_issue_list_resource_uri(
        owner,
        repo,
        state=state,
        per_page=per_page,
        page=page,
        labels=labels,
        sort=sort,
        direction=direction,
        since=since,
    )
    result, _ = _fetch_issue_list_page(
        resource_uri,
        fetched_at=fetched_at,
        fetch_policy=fetch_policy,
        auth_headers=auth_headers,
        opener=opener,
    )
    return result


@dataclass(frozen=True, slots=True)
class GitHubIssueListPages:
    """The outcome of one bounded multi-page issue-list traversal.

    Still discovery, not observation: like ``GitHubIssueListResult``, this
    carries numbers only. ``truncated`` is an honest report that the
    ``max_pages`` budget ran out while GitHub still offered a next page —
    never conflated with "the list ended".
    """

    pages: tuple[GitHubIssueListResult, ...]
    max_pages: int
    truncated: bool

    def __post_init__(self) -> None:
        if not self.pages:
            raise ValueError("a traversal must contain at least one fetched page")

    @property
    def issue_numbers(self) -> tuple[int, ...]:
        return tuple(sorted({number for page in self.pages for number in page.issue_numbers}))

    @property
    def pull_request_numbers(self) -> tuple[int, ...]:
        return tuple(
            sorted({number for page in self.pages for number in page.pull_request_numbers})
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "github-issue-list-pages-v1",
            "maxPages": self.max_pages,
            "truncated": self.truncated,
            "issueNumbers": list(self.issue_numbers),
            "pullRequestNumbers": list(self.pull_request_numbers),
            "pages": [page.to_dict() for page in self.pages],
        }


def fetch_external_github_issue_list_pages(
    owner: str,
    repo: str,
    *,
    fetched_at: str,
    state: str = "open",
    per_page: int = 30,
    max_pages: int = 1,
    labels: Sequence[str] | None = None,
    sort: str | None = None,
    direction: str | None = None,
    since: str | None = None,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
) -> GitHubIssueListPages:
    """Traverse up to ``max_pages`` list pages, following ``Link: rel="next"``.

    Bounded by design: ``max_pages`` is the hard cap on requests (default 1,
    i.e. no traversal unless the caller asks for one), and a next link that
    exists when the budget runs out sets ``truncated`` rather than being
    silently ignored or unboundedly followed. The next URL is taken from
    GitHub's own Link header and followed only within the origin the caller
    asked for — GitHub legitimately rewrites ``/repos/{owner}/{repo}`` to
    ``/repositories/{id}`` in Link targets, so path equality is deliberately
    not required, but a cross-origin next is rejected rather than followed
    (the same boundary the transport enforces for redirects).
    """
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        raise GitHubIssueError("max_pages must be a positive integer")

    first_uri = github_issue_list_resource_uri(
        owner,
        repo,
        state=state,
        per_page=per_page,
        page=1,
        labels=labels,
        sort=sort,
        direction=direction,
        since=since,
    )

    def fetch_page(resource_uri: str) -> tuple[GitHubIssueListResult, str | None]:
        return _fetch_issue_list_page(
            resource_uri,
            fetched_at=fetched_at,
            fetch_policy=fetch_policy,
            auth_headers=auth_headers,
            opener=opener,
        )

    pages, truncated = _traverse_discovery_pages(
        first_uri, max_pages=max_pages, fetch_page=fetch_page
    )
    return GitHubIssueListPages(
        pages=cast("tuple[GitHubIssueListResult, ...]", pages),
        max_pages=max_pages,
        truncated=truncated,
    )


_SUPPORTED_SEARCH_SORTS = {"comments", "reactions", "interactions", "created", "updated"}


@dataclass(frozen=True, slots=True)
class GitHubIssueSearchResult:
    """The outcome of one bounded search-issues query: discovery, not observation.

    Mirrors ``GitHubIssueListResult`` for the search endpoint's different
    envelope: the response carries ``total_count`` and ``incomplete_results``
    alongside the inline items, and inline item data is never promoted into
    an ``ExternalRequirementObservation`` — the same boundary as the list.
    """

    resource_uri: str
    fetched_at: str
    response_digest: str
    total_count: int
    incomplete_results: bool
    issue_numbers: tuple[int, ...]
    pull_request_numbers: tuple[int, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "github-issue-search-v1",
            "resourceUri": self.resource_uri,
            "fetchedAt": self.fetched_at,
            "responseDigest": self.response_digest,
            "totalCount": self.total_count,
            "incompleteResults": self.incomplete_results,
            "issueNumbers": list(self.issue_numbers),
            "pullRequestNumbers": list(self.pull_request_numbers),
        }


def github_issue_search_resource_uri(
    query: str,
    *,
    per_page: int = 30,
    page: int = 1,
    sort: str | None = None,
    order: str | None = None,
) -> str:
    """Build the deterministic URI for one bounded search-issues query page.

    GitHub scopes search through qualifiers inside the query string itself
    (``repo:owner/name``, ``is:issue``, ``label:...``); the adapter never
    guesses scoping — the caller's query is sent explicitly, so one URI
    always identifies exactly one bounded page of one explicit search.
    """
    if not isinstance(query, str) or not query.strip():
        raise GitHubIssueError("query must be a non-empty string")
    if not (1 <= per_page <= 100):
        raise GitHubIssueError("per_page must be between 1 and 100")
    if page < 1:
        raise GitHubIssueError("page must be a positive integer")
    if sort is not None and sort not in _SUPPORTED_SEARCH_SORTS:
        raise GitHubIssueError(f"unsupported search sort: {sort!r}")
    if order is not None and order not in _SUPPORTED_LIST_DIRECTIONS:
        raise GitHubIssueError(f"unsupported search order: {order!r}")

    params: dict[str, object] = {"q": query.strip(), "per_page": per_page, "page": page}
    if sort is not None:
        params["sort"] = sort
    if order is not None:
        params["order"] = order
    return f"https://api.github.com/search/issues?{urlencode(params)}"


def _parse_search_payload(
    payload: object,
) -> tuple[tuple[int, ...], tuple[int, ...], int, bool]:
    if not isinstance(payload, Mapping):
        raise GitHubIssueError("GitHub search response is not a JSON object")
    total_count = payload.get("total_count")
    if not isinstance(total_count, int) or isinstance(total_count, bool) or total_count < 0:
        raise GitHubIssueError(
            "GitHub search response is missing a non-negative integer 'total_count'"
        )
    incomplete_results = payload.get("incomplete_results")
    if not isinstance(incomplete_results, bool):
        raise GitHubIssueError("GitHub search response is missing a boolean 'incomplete_results'")
    if "items" not in payload:
        raise GitHubIssueError("GitHub search response is missing an 'items' array")
    issue_numbers, pull_request_numbers = _parse_issue_list_payload(payload["items"])
    return issue_numbers, pull_request_numbers, total_count, incomplete_results


def _fetch_issue_search_page(
    resource_uri: str,
    *,
    fetched_at: str,
    fetch_policy: HttpFetchPolicy,
    auth_headers: Mapping[str, str] | None,
    opener,
) -> tuple[GitHubIssueSearchResult, str | None]:
    result = fetch_github_resource(
        resource_uri, fetch_policy=fetch_policy, auth_headers=auth_headers, opener=opener
    )
    payload = _decode_response_json(result)
    issue_numbers, pull_request_numbers, total_count, incomplete_results = (
        _parse_search_payload(payload)
    )
    next_uri = parse_next_link(result.link)
    page = GitHubIssueSearchResult(
        resource_uri=resource_uri,
        fetched_at=fetched_at,
        response_digest=content_digest(result.payload),
        total_count=total_count,
        incomplete_results=incomplete_results,
        issue_numbers=issue_numbers,
        pull_request_numbers=pull_request_numbers,
    )
    return page, next_uri


def fetch_external_github_issue_search(
    query: str,
    *,
    fetched_at: str,
    per_page: int = 30,
    page: int = 1,
    sort: str | None = None,
    order: str | None = None,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
) -> GitHubIssueSearchResult:
    """Discover which issue numbers match one explicit search query.

    A single bounded GET of the search endpoint (no follow-your-nose
    pagination here, exactly like the list call). Pull requests inside the
    items are reported separately, never silently mixed in or dropped, and
    inline item data is never promoted into an observation. The search API
    counts against GitHub's separate search rate-limit class — a 403/429
    there raises the same distinguished rate-limit error as everywhere else.
    """
    resource_uri = github_issue_search_resource_uri(
        query, per_page=per_page, page=page, sort=sort, order=order
    )
    result, _ = _fetch_issue_search_page(
        resource_uri,
        fetched_at=fetched_at,
        fetch_policy=fetch_policy,
        auth_headers=auth_headers,
        opener=opener,
    )
    return result


@dataclass(frozen=True, slots=True)
class GitHubIssueSearchPages:
    """The outcome of one bounded multi-page search traversal.

    Still discovery, not observation. ``total_count`` is GitHub's
    query-level count, read from the first fetched page;
    ``incomplete_results`` is the conservative union — true if any fetched
    page reported it — so a potentially incomplete search is never
    silently presented as complete. ``truncated`` reports an honest stop
    at the ``max_pages`` budget.
    """

    pages: tuple[GitHubIssueSearchResult, ...]
    max_pages: int
    truncated: bool

    def __post_init__(self) -> None:
        if not self.pages:
            raise ValueError("a traversal must contain at least one fetched page")

    @property
    def total_count(self) -> int:
        return self.pages[0].total_count

    @property
    def incomplete_results(self) -> bool:
        return any(page.incomplete_results for page in self.pages)

    @property
    def issue_numbers(self) -> tuple[int, ...]:
        return tuple(sorted({number for page in self.pages for number in page.issue_numbers}))

    @property
    def pull_request_numbers(self) -> tuple[int, ...]:
        return tuple(
            sorted({number for page in self.pages for number in page.pull_request_numbers})
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "github-issue-search-pages-v1",
            "maxPages": self.max_pages,
            "truncated": self.truncated,
            "totalCount": self.total_count,
            "incompleteResults": self.incomplete_results,
            "issueNumbers": list(self.issue_numbers),
            "pullRequestNumbers": list(self.pull_request_numbers),
            "pages": [page.to_dict() for page in self.pages],
        }


def fetch_external_github_issue_search_pages(
    query: str,
    *,
    fetched_at: str,
    per_page: int = 30,
    max_pages: int = 1,
    sort: str | None = None,
    order: str | None = None,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
) -> GitHubIssueSearchPages:
    """Traverse up to ``max_pages`` search pages, following ``Link: rel="next"``.

    Same bounded traversal contract as the list: ``max_pages`` is the hard
    cap on requests (default 1), truncation is reported honestly, next
    targets are followed within the request origin only, and malformed
    Link headers raise rather than silently ending the traversal. Note
    GitHub's own search cap: only the first 1000 results of any query are
    addressable, so a budget large enough to reach that boundary stops on
    a missing next link rather than pretending the query ended.
    """
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages < 1:
        raise GitHubIssueError("max_pages must be a positive integer")

    first_uri = github_issue_search_resource_uri(
        query, per_page=per_page, page=1, sort=sort, order=order
    )

    def fetch_page(resource_uri: str) -> tuple[GitHubIssueSearchResult, str | None]:
        return _fetch_issue_search_page(
            resource_uri,
            fetched_at=fetched_at,
            fetch_policy=fetch_policy,
            auth_headers=auth_headers,
            opener=opener,
        )

    pages, truncated = _traverse_discovery_pages(
        first_uri, max_pages=max_pages, fetch_page=fetch_page
    )
    return GitHubIssueSearchPages(
        pages=cast("tuple[GitHubIssueSearchResult, ...]", pages),
        max_pages=max_pages,
        truncated=truncated,
    )
