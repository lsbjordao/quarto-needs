from __future__ import annotations

import hashlib
import json

import pytest

from quarto_needs.github_issues import (
    GitHubIssueError,
    build_github_issue_identity,
    fetch_external_github_issue,
    github_issue_resource_uri,
    parse_external_github_issue,
)
from quarto_needs.oslc_rm import ExternalResourceIdentity


def _identity(uri: str = "https://api.github.com/repos/acme/widgets/issues/3164") -> ExternalResourceIdentity:
    return ExternalResourceIdentity(
        resource_uri=uri,
        service_provider_uri="https://api.github.com/repos/acme/widgets",
        digest="sha256:" + "a" * 64,
        fetched_at="2026-08-31T12:00:00Z",
        trust_state="unverified",
    )


def _real_shaped_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "number": 3164,
        "title": "Feature: Allow custom link text for [LINK: ...]",
        "body": "## Description\n\nAllow an optional link text at the link site.",
        "state": "open",
        "html_url": "https://github.com/acme/widgets/issues/3164",
        "updated_at": "2026-08-30T16:08:59Z",
        "labels": [
            {"id": 1, "name": "enhancement", "color": "a2eeef"},
            {"id": 2, "name": "Bug", "color": "d73a4a"},
        ],
    }
    payload.update(overrides)
    return payload


def test_github_issue_resource_uri_is_deterministic() -> None:
    assert (
        github_issue_resource_uri("acme", "widgets", 3164)
        == "https://api.github.com/repos/acme/widgets/issues/3164"
    )


def test_github_issue_resource_uri_rejects_empty_owner_or_repo() -> None:
    with pytest.raises(GitHubIssueError):
        github_issue_resource_uri("", "widgets", 1)
    with pytest.raises(GitHubIssueError):
        github_issue_resource_uri("acme", "", 1)


def test_github_issue_resource_uri_rejects_non_positive_number() -> None:
    with pytest.raises(GitHubIssueError):
        github_issue_resource_uri("acme", "widgets", 0)


def test_parse_external_github_issue_normalizes_a_real_shaped_payload() -> None:
    observation = parse_external_github_issue(_real_shaped_payload(), identity=_identity())

    assert observation.identity == _identity()
    assert observation.title == "Feature: Allow custom link text for [LINK: ...]"
    assert observation.description.startswith("## Description")
    assert observation.external_identifier == "3164"
    assert observation.attributes["state"] == "open"
    assert observation.attributes["htmlUrl"] == "https://github.com/acme/widgets/issues/3164"
    assert observation.attributes["updatedAt"] == "2026-08-30T16:08:59Z"
    assert observation.attributes["labels"] == ("Bug", "enhancement")


def test_parse_external_github_issue_treats_null_body_as_empty_description() -> None:
    observation = parse_external_github_issue(
        _real_shaped_payload(body=None), identity=_identity()
    )
    assert observation.description == ""


def test_parse_external_github_issue_treats_missing_labels_as_empty() -> None:
    payload = _real_shaped_payload()
    del payload["labels"]
    observation = parse_external_github_issue(payload, identity=_identity())
    assert observation.attributes["labels"] == ()


def test_parse_external_github_issue_rejects_pull_requests() -> None:
    payload = _real_shaped_payload(
        pull_request={
            "url": "https://api.github.com/repos/acme/widgets/pulls/500",
            "html_url": "https://github.com/acme/widgets/pull/500",
        }
    )
    with pytest.raises(GitHubIssueError, match="pull request"):
        parse_external_github_issue(payload, identity=_identity())


def test_parse_external_github_issue_requires_non_empty_title() -> None:
    with pytest.raises(GitHubIssueError, match="title"):
        parse_external_github_issue(_real_shaped_payload(title=""), identity=_identity())


def test_parse_external_github_issue_requires_integer_number() -> None:
    with pytest.raises(GitHubIssueError, match="number"):
        parse_external_github_issue(_real_shaped_payload(number="3164"), identity=_identity())


def test_parse_external_github_issue_rejects_unsupported_state() -> None:
    with pytest.raises(GitHubIssueError, match="state"):
        parse_external_github_issue(_real_shaped_payload(state="draft"), identity=_identity())


def test_parse_external_github_issue_requires_html_url_and_updated_at() -> None:
    with pytest.raises(GitHubIssueError, match="html_url"):
        parse_external_github_issue(_real_shaped_payload(html_url=""), identity=_identity())
    with pytest.raises(GitHubIssueError, match="updated_at"):
        parse_external_github_issue(_real_shaped_payload(updated_at=None), identity=_identity())


def test_build_github_issue_identity_uses_resource_uri_and_content_digest() -> None:
    payload_bytes = b'{"number": 3164}'
    identity = build_github_issue_identity(
        "acme",
        "widgets",
        3164,
        payload_bytes=payload_bytes,
        fetched_at="2026-08-31T12:00:00Z",
    )

    assert identity.resource_uri == "https://api.github.com/repos/acme/widgets/issues/3164"
    assert identity.service_provider_uri == "https://api.github.com/repos/acme/widgets"
    assert identity.trust_state == "unverified"
    assert identity.digest == "sha256:" + hashlib.sha256(payload_bytes).hexdigest()


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


def test_fetch_external_github_issue_composes_transport_identity_and_parsing() -> None:
    body = json.dumps(_real_shaped_payload()).encode("utf-8")
    opener = _Opener(
        _Response(
            200,
            body,
            **{"Content-Type": "application/json", "ETag": '"etag-1"'},
        )
    )

    observation = fetch_external_github_issue(
        "acme", "widgets", 3164, fetched_at="2026-08-31T12:00:00Z", opener=opener
    )

    assert observation.title == "Feature: Allow custom link text for [LINK: ...]"
    assert observation.identity.resource_uri == (
        "https://api.github.com/repos/acme/widgets/issues/3164"
    )
    assert observation.identity.digest == "sha256:" + hashlib.sha256(body).hexdigest()
    assert observation.identity.etag == '"etag-1"'


def test_fetch_external_github_issue_rejects_non_object_json() -> None:
    opener = _Opener(_Response(200, b"[1, 2, 3]", **{"Content-Type": "application/json"}))
    with pytest.raises(GitHubIssueError, match="JSON object"):
        fetch_external_github_issue(
            "acme", "widgets", 1, fetched_at="2026-08-31T12:00:00Z", opener=opener
        )


def test_build_github_issue_identity_accepts_conditional_request_validators() -> None:
    identity = build_github_issue_identity(
        "acme",
        "widgets",
        3164,
        payload_bytes=b"{}",
        fetched_at="2026-08-31T12:00:00Z",
        trust_state="trusted",
        etag='"abc123"',
        last_modified="Mon, 31 Aug 2026 12:00:00 GMT",
    )
    assert identity.etag == '"abc123"'
    assert identity.last_modified == "Mon, 31 Aug 2026 12:00:00 GMT"
    assert identity.trust_state == "trusted"
