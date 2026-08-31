from __future__ import annotations

import json
from typing import Mapping
from urllib.parse import quote

from .github_http import fetch_github_resource
from .oslc_http import HttpFetchPolicy
from .oslc_reconcile import ExternalRequirementObservation
from .oslc_rm import ExternalResourceIdentity, TrustState, content_digest

_SUPPORTED_STATES = {"open", "closed"}


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


def fetch_external_github_issue(
    owner: str,
    repo: str,
    number: int,
    *,
    fetched_at: str,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
) -> ExternalRequirementObservation:
    """Fetch and normalize one GitHub issue end to end.

    Composes the bounded transport (``fetch_github_resource``) with identity
    construction and normalization; still no caching or conditional
    requests — a fresh network fetch every call, exactly as the transport
    slice alone provides.
    """
    resource_uri = github_issue_resource_uri(owner, repo, number)
    result = fetch_github_resource(
        resource_uri, fetch_policy=fetch_policy, auth_headers=auth_headers, opener=opener
    )
    try:
        payload = json.loads(result.payload)
    except json.JSONDecodeError as error:
        raise GitHubIssueError(f"GitHub response is not valid JSON: {error}") from error
    if not isinstance(payload, Mapping):
        raise GitHubIssueError("GitHub response is not a JSON object")

    identity = build_github_issue_identity(
        owner,
        repo,
        number,
        payload_bytes=result.payload,
        fetched_at=fetched_at,
        etag=result.etag,
        last_modified=result.last_modified,
    )
    return parse_external_github_issue(payload, identity=identity)
