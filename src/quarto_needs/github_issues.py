from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import quote, urlencode

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
) -> str:
    """Build the deterministic GitHub REST API URL for one bounded issue-list page."""
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
    query = urlencode({"state": state, "per_page": per_page, "page": page})
    return f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/issues?{query}"


def _parse_issue_list_payload(payload: object) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if not isinstance(payload, list):
        raise GitHubIssueError("GitHub issue list response is not a JSON array")

    issue_numbers: list[int] = []
    pull_request_numbers: list[int] = []
    for entry in payload:
        if not isinstance(entry, Mapping):
            raise GitHubIssueError("GitHub issue list entry is not a JSON object")
        number = entry.get("number")
        if not isinstance(number, int) or isinstance(number, bool):
            raise GitHubIssueError("GitHub issue list entry is missing an integer 'number'")
        if "pull_request" in entry:
            pull_request_numbers.append(number)
        else:
            issue_numbers.append(number)

    return tuple(sorted(set(issue_numbers))), tuple(sorted(set(pull_request_numbers)))


def fetch_external_github_issue_list(
    owner: str,
    repo: str,
    *,
    fetched_at: str,
    state: str = "open",
    per_page: int = 30,
    page: int = 1,
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
        owner, repo, state=state, per_page=per_page, page=page
    )
    result = fetch_github_resource(
        resource_uri, fetch_policy=fetch_policy, auth_headers=auth_headers, opener=opener
    )
    try:
        payload = json.loads(result.payload)
    except json.JSONDecodeError as error:
        raise GitHubIssueError(f"GitHub response is not valid JSON: {error}") from error
    issue_numbers, pull_request_numbers = _parse_issue_list_payload(payload)

    return GitHubIssueListResult(
        resource_uri=resource_uri,
        fetched_at=fetched_at,
        response_digest=content_digest(result.payload),
        issue_numbers=issue_numbers,
        pull_request_numbers=pull_request_numbers,
    )
