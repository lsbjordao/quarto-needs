from __future__ import annotations

import hashlib
import json

import pytest

from quarto_needs.github_issues import (
    GitHubIssueError,
    build_github_issue_identity,
    fetch_external_github_issue,
    fetch_external_github_issue_list,
    fetch_external_github_issue_list_pages,
    fetch_external_github_issue_search,
    fetch_external_github_issue_search_pages,
    github_issue_list_resource_uri,
    github_issue_resource_uri,
    github_issue_search_resource_uri,
    parse_external_github_issue,
    parse_next_link,
)
from quarto_needs.oslc_rm import CachePolicy, ExternalResourceIdentity


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


@pytest.mark.requirement("SYS-008", "FUN-014", "NFR-007")
@pytest.mark.quarto_need_test_case("TC-020")
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


def test_fetch_external_github_issue_with_cache_root_hits_network_once(tmp_path) -> None:
    body = json.dumps(_real_shaped_payload()).encode("utf-8")
    # Only one response queued: a second network call would raise.
    opener = _Opener(_Response(200, body, **{"Content-Type": "application/json"}))

    first = fetch_external_github_issue(
        "acme",
        "widgets",
        3164,
        fetched_at="2026-08-31T12:00:00Z",
        opener=opener,
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=3600),
    )
    second = fetch_external_github_issue(
        "acme",
        "widgets",
        3164,
        fetched_at="2026-08-31T12:05:00Z",
        opener=opener,
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=3600),
    )

    assert len(opener.requests) == 1
    assert second.title == first.title
    assert second.identity.digest == first.identity.digest


def test_fetch_external_github_issue_refetches_once_cache_is_stale(tmp_path) -> None:
    body = json.dumps(_real_shaped_payload()).encode("utf-8")
    opener = _Opener(
        _Response(200, body, **{"Content-Type": "application/json"}),
        _Response(200, body, **{"Content-Type": "application/json"}),
    )

    fetch_external_github_issue(
        "acme",
        "widgets",
        3164,
        fetched_at="2026-08-31T12:00:00Z",
        opener=opener,
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=60),
    )
    fetch_external_github_issue(
        "acme",
        "widgets",
        3164,
        # Far past the 60s freshness window.
        fetched_at="2026-08-31T13:00:00Z",
        opener=opener,
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=60),
    )

    assert len(opener.requests) == 2


@pytest.mark.requirement("SYS-008", "FUN-015", "NFR-007")
@pytest.mark.quarto_need_test_case("TC-021")
def test_fetch_external_github_issue_sends_conditional_request_when_cache_is_stale(
    tmp_path,
) -> None:
    body = json.dumps(_real_shaped_payload()).encode("utf-8")
    opener = _Opener(
        _Response(200, body, **{"Content-Type": "application/json", "ETag": '"v1"'}),
        _Response(304, b"", **{"ETag": '"v1"'}),
    )

    first = fetch_external_github_issue(
        "acme",
        "widgets",
        3164,
        fetched_at="2026-08-31T12:00:00Z",
        opener=opener,
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=60),
    )
    second = fetch_external_github_issue(
        "acme",
        "widgets",
        3164,
        fetched_at="2026-08-31T13:00:00Z",  # past the 60s freshness window
        opener=opener,
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=60),
    )

    assert len(opener.requests) == 2
    assert opener.requests[1].get_header("If-none-match") == '"v1"'
    # 304 means the body is reused, not re-fetched, but provenance is refreshed.
    assert second.title == first.title
    assert second.identity.digest == first.identity.digest
    assert second.identity.fetched_at == "2026-08-31T13:00:00Z"


def test_fetch_external_github_issue_refetches_fully_when_conditional_request_returns_200(
    tmp_path,
) -> None:
    old_body = json.dumps(_real_shaped_payload(title="Old title")).encode("utf-8")
    new_body = json.dumps(_real_shaped_payload(title="New title")).encode("utf-8")
    opener = _Opener(
        _Response(200, old_body, **{"Content-Type": "application/json", "ETag": '"v1"'}),
        _Response(200, new_body, **{"Content-Type": "application/json", "ETag": '"v2"'}),
    )

    fetch_external_github_issue(
        "acme",
        "widgets",
        3164,
        fetched_at="2026-08-31T12:00:00Z",
        opener=opener,
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=60),
    )
    second = fetch_external_github_issue(
        "acme",
        "widgets",
        3164,
        fetched_at="2026-08-31T13:00:00Z",
        opener=opener,
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=60),
    )

    assert opener.requests[1].get_header("If-none-match") == '"v1"'
    assert second.title == "New title"
    assert second.identity.etag == '"v2"'


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


def _list_entry(number: int, *, is_pull_request: bool = False) -> dict[str, object]:
    entry = _real_shaped_payload(number=number)
    if is_pull_request:
        entry["pull_request"] = {
            "url": f"https://api.github.com/repos/acme/widgets/pulls/{number}",
        }
    return entry


def test_github_issue_list_resource_uri_is_deterministic() -> None:
    assert github_issue_list_resource_uri("acme", "widgets") == (
        "https://api.github.com/repos/acme/widgets/issues?state=open&per_page=30&page=1"
    )
    assert github_issue_list_resource_uri("acme", "widgets", state="all", page=2, per_page=50) == (
        "https://api.github.com/repos/acme/widgets/issues?state=all&per_page=50&page=2"
    )


def test_github_issue_list_resource_uri_rejects_invalid_parameters() -> None:
    with pytest.raises(GitHubIssueError, match="state"):
        github_issue_list_resource_uri("acme", "widgets", state="draft")
    with pytest.raises(GitHubIssueError, match="per_page"):
        github_issue_list_resource_uri("acme", "widgets", per_page=0)
    with pytest.raises(GitHubIssueError, match="per_page"):
        github_issue_list_resource_uri("acme", "widgets", per_page=101)
    with pytest.raises(GitHubIssueError, match="page"):
        github_issue_list_resource_uri("acme", "widgets", page=0)


def test_fetch_external_github_issue_list_separates_issues_from_pull_requests() -> None:
    body = json.dumps(
        [_list_entry(3166, is_pull_request=True), _list_entry(3164), _list_entry(3157)]
    ).encode("utf-8")
    opener = _Opener(_Response(200, body, **{"Content-Type": "application/json"}))

    result = fetch_external_github_issue_list(
        "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", opener=opener
    )

    assert result.issue_numbers == (3157, 3164)
    assert result.pull_request_numbers == (3166,)
    assert result.resource_uri == github_issue_list_resource_uri("acme", "widgets")
    assert result.response_digest == "sha256:" + hashlib.sha256(body).hexdigest()


def test_fetch_external_github_issue_list_rejects_non_array_response() -> None:
    opener = _Opener(_Response(200, b"{}", **{"Content-Type": "application/json"}))
    with pytest.raises(GitHubIssueError, match="array"):
        fetch_external_github_issue_list(
            "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", opener=opener
        )


def test_fetch_external_github_issue_list_rejects_entry_without_integer_number() -> None:
    body = json.dumps([{**_real_shaped_payload(), "number": "3164"}]).encode("utf-8")
    opener = _Opener(_Response(200, body, **{"Content-Type": "application/json"}))
    with pytest.raises(GitHubIssueError, match="number"):
        fetch_external_github_issue_list(
            "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", opener=opener
        )


def test_fetch_external_github_issue_list_does_not_promote_inline_data_to_an_observation() -> None:
    """List entries carry full issue bodies, but this is discovery only.

    Getting a provenance-bound ExternalRequirementObservation for a
    discovered number is a separate, independently fetched call — mirroring
    OSLC's query/observe split, where a query's inline node data is never
    treated as equivalent to an independently fetched member observation.
    """
    body = json.dumps([_list_entry(3164)]).encode("utf-8")
    opener = _Opener(_Response(200, body, **{"Content-Type": "application/json"}))

    result = fetch_external_github_issue_list(
        "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", opener=opener
    )

    assert not hasattr(result, "observations")
    assert result.issue_numbers == (3164,)


def test_parse_next_link_extracts_next_target_from_a_multi_entry_header() -> None:
    header = (
        '<https://api.github.com/repositories/123/issues?state=open&per_page=5&page=1>; rel="prev", '
        '<https://api.github.com/repositories/123/issues?state=open&per_page=5&page=2>; rel="next", '
        '<https://api.github.com/repositories/123/issues?state=open&per_page=5&page=9>; rel="last"'
    )
    assert parse_next_link(header) == (
        "https://api.github.com/repositories/123/issues?state=open&per_page=5&page=2"
    )


def test_parse_next_link_returns_none_when_no_next_page_exists() -> None:
    header = '<https://api.github.com/repositories/123/issues?page=9>; rel="last"'
    assert parse_next_link(header) is None
    assert parse_next_link(None) is None


def test_parse_next_link_rejects_malformed_headers() -> None:
    with pytest.raises(GitHubIssueError, match="malformed"):
        parse_next_link("not-a-link-header")
    with pytest.raises(GitHubIssueError, match='more than one rel="next"'):
        parse_next_link('<https://a.example/2>; rel="next", <https://a.example/3>; rel="next"')


def test_github_issue_list_resource_uri_accepts_the_endpoints_own_filters() -> None:
    assert github_issue_list_resource_uri(
        "acme", "widgets", labels=["bug", "ui"], sort="updated", direction="asc"
    ) == (
        "https://api.github.com/repos/acme/widgets/issues"
        "?state=open&per_page=30&page=1&labels=bug%2Cui&sort=updated&direction=asc"
    )
    assert github_issue_list_resource_uri(
        "acme", "widgets", since="2026-08-01T00:00:00Z"
    ) == (
        "https://api.github.com/repos/acme/widgets/issues"
        "?state=open&per_page=30&page=1&since=2026-08-01T00%3A00%3A00Z"
    )


def test_github_issue_list_resource_uri_rejects_invalid_filter_parameters() -> None:
    with pytest.raises(GitHubIssueError, match="sort"):
        github_issue_list_resource_uri("acme", "widgets", sort="popularity")
    with pytest.raises(GitHubIssueError, match="direction"):
        github_issue_list_resource_uri("acme", "widgets", direction="sideways")
    with pytest.raises(GitHubIssueError, match="since"):
        github_issue_list_resource_uri("acme", "widgets", since="")
    with pytest.raises(GitHubIssueError, match="labels"):
        github_issue_list_resource_uri("acme", "widgets", labels="bug")
    with pytest.raises(GitHubIssueError, match="non-empty string"):
        github_issue_list_resource_uri("acme", "widgets", labels=["bug", ""])


def test_fetch_external_github_issue_list_sends_filters_as_query_parameters() -> None:
    body = json.dumps([]).encode("utf-8")
    opener = _Opener(_Response(200, body, **{"Content-Type": "application/json"}))

    fetch_external_github_issue_list(
        "acme",
        "widgets",
        fetched_at="2026-08-31T12:00:00Z",
        labels=["bug"],
        opener=opener,
    )

    assert opener.requests[0].full_url == github_issue_list_resource_uri(
        "acme", "widgets", labels=["bug"]
    )


def _page_response(entries: list[dict[str, object]], **headers: str) -> "_Response":
    return _Response(
        200, json.dumps(entries).encode("utf-8"), **{"Content-Type": "application/json", **headers}
    )


@pytest.mark.requirement("SYS-008", "FUN-016", "NFR-007")
@pytest.mark.quarto_need_test_case("TC-022")
def test_fetch_external_github_issue_list_pages_follows_rel_next_across_pages() -> None:
    # GitHub rewrites /repos/{owner}/{repo} to /repositories/{id} in its own
    # Link targets, so the next URL deliberately has a different path — the
    # traversal must follow it (same origin) instead of rejecting it.
    next_url = "https://api.github.com/repositories/123/issues?state=open&per_page=30&page=2"
    opener = _Opener(
        _page_response([_list_entry(3164)], Link=f'<{next_url}>; rel="next"'),
        _page_response([_list_entry(3165, is_pull_request=True)]),
    )

    result = fetch_external_github_issue_list_pages(
        "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=3, opener=opener
    )

    assert len(opener.requests) == 2
    assert opener.requests[1].full_url == next_url
    assert [page.resource_uri for page in result.pages] == [
        github_issue_list_resource_uri("acme", "widgets"),
        next_url,
    ]
    assert result.issue_numbers == (3164,)
    assert result.pull_request_numbers == (3165,)
    assert result.truncated is False


def test_fetch_external_github_issue_list_pages_stops_when_github_offers_no_next() -> None:
    opener = _Opener(_page_response([_list_entry(3164)]))

    result = fetch_external_github_issue_list_pages(
        "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=5, opener=opener
    )

    assert len(opener.requests) == 1
    assert result.truncated is False
    assert result.issue_numbers == (3164,)


def test_fetch_external_github_issue_list_pages_reports_truncation_at_the_budget() -> None:
    next_url = "https://api.github.com/repositories/123/issues?page=2"
    opener = _Opener(_page_response([_list_entry(3164)], Link=f'<{next_url}>; rel="next"'))

    result = fetch_external_github_issue_list_pages(
        "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=1, opener=opener
    )

    # The budget, not the end of the list, stopped the traversal — and the
    # result says so instead of implying completeness.
    assert len(opener.requests) == 1
    assert result.truncated is True
    assert result.max_pages == 1
    assert result.pages[-1].resource_uri == github_issue_list_resource_uri("acme", "widgets")


def test_fetch_external_github_issue_list_pages_rejects_cross_origin_next() -> None:
    opener = _Opener(
        _page_response(
            [_list_entry(3164)],
            Link='<https://evil.example/issues?page=2>; rel="next"',
        )
    )

    with pytest.raises(GitHubIssueError, match="crossed origin"):
        fetch_external_github_issue_list_pages(
            "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=2, opener=opener
        )


def test_fetch_external_github_issue_list_pages_rejects_a_malformed_link_header() -> None:
    # A malformed Link header must fail loudly even mid-traversal: reading it
    # as "no next page" would misreport a truncated list as complete.
    opener = _Opener(_page_response([_list_entry(3164)], Link="garbage"))

    with pytest.raises(GitHubIssueError, match="malformed"):
        fetch_external_github_issue_list_pages(
            "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=1, opener=opener
        )


def test_fetch_external_github_issue_list_pages_rejects_invalid_max_pages() -> None:
    opener = _Opener()
    with pytest.raises(GitHubIssueError, match="max_pages"):
        fetch_external_github_issue_list_pages(
            "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=0, opener=opener
        )
    with pytest.raises(GitHubIssueError, match="max_pages"):
        fetch_external_github_issue_list_pages(
            "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=True, opener=opener
        )
    assert opener.requests == []


def test_fetch_external_github_issue_list_pages_dedupes_aggregates_keeps_per_page_truth() -> None:
    next_url = "https://api.github.com/repositories/123/issues?page=2"
    opener = _Opener(
        _page_response([_list_entry(3164)], Link=f'<{next_url}>; rel="next"'),
        _page_response([_list_entry(3164), _list_entry(3165)]),
    )

    result = fetch_external_github_issue_list_pages(
        "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=2, opener=opener
    )

    assert result.issue_numbers == (3164, 3165)
    assert [page.issue_numbers for page in result.pages] == [(3164,), (3164, 3165)]


def test_fetch_external_github_issue_list_pages_remains_discovery_only() -> None:
    opener = _Opener(_page_response([_list_entry(3164)]))

    result = fetch_external_github_issue_list_pages(
        "acme", "widgets", fetched_at="2026-08-31T12:00:00Z", opener=opener
    )

    assert not hasattr(result, "observations")
    assert result.to_dict()["schema"] == "github-issue-list-pages-v1"
    assert result.to_dict()["pages"][0]["resourceUri"] == (
        github_issue_list_resource_uri("acme", "widgets")
    )


def _search_entry(number: int, *, is_pull_request: bool = False) -> dict[str, object]:
    return _list_entry(number, is_pull_request=is_pull_request)


def _search_response(
    total: int,
    entries: list[dict[str, object]],
    *,
    incomplete: bool = False,
    **headers: str,
) -> "_Response":
    body = json.dumps(
        {"total_count": total, "incomplete_results": incomplete, "items": entries}
    ).encode("utf-8")
    return _Response(200, body, **{"Content-Type": "application/json", **headers})


def test_github_issue_search_resource_uri_is_deterministic() -> None:
    assert github_issue_search_resource_uri("repo:acme/widgets is:issue") == (
        "https://api.github.com/search/issues"
        "?q=repo%3Aacme%2Fwidgets+is%3Aissue&per_page=30&page=1"
    )
    assert github_issue_search_resource_uri(
        "repo:acme/widgets", per_page=50, page=2, sort="updated", order="desc"
    ) == (
        "https://api.github.com/search/issues"
        "?q=repo%3Aacme%2Fwidgets&per_page=50&page=2&sort=updated&order=desc"
    )


def test_github_issue_search_resource_uri_rejects_invalid_parameters() -> None:
    with pytest.raises(GitHubIssueError, match="query"):
        github_issue_search_resource_uri("   ")
    with pytest.raises(GitHubIssueError, match="per_page"):
        github_issue_search_resource_uri("x", per_page=101)
    with pytest.raises(GitHubIssueError, match="page"):
        github_issue_search_resource_uri("x", page=0)
    with pytest.raises(GitHubIssueError, match="sort"):
        github_issue_search_resource_uri("x", sort="popularity")
    with pytest.raises(GitHubIssueError, match="order"):
        github_issue_search_resource_uri("x", order="sideways")


def test_fetch_external_github_issue_search_separates_items_and_surfaces_envelope() -> None:
    opener = _Opener(
        _search_response(
            12,
            [_search_entry(3164), _search_entry(3166, is_pull_request=True)],
            incomplete=True,
        )
    )

    result = fetch_external_github_issue_search(
        "repo:acme/widgets is:issue", fetched_at="2026-08-31T12:00:00Z", opener=opener
    )

    assert result.issue_numbers == (3164,)
    assert result.pull_request_numbers == (3166,)
    assert result.total_count == 12
    assert result.incomplete_results is True
    assert result.resource_uri == github_issue_search_resource_uri("repo:acme/widgets is:issue")
    assert not hasattr(result, "observations")


def test_fetch_external_github_issue_search_rejects_malformed_envelopes() -> None:
    for body in (
        b"[]",
        b'{"total_count": 1}',
        b'{"total_count": "12", "incomplete_results": false, "items": []}',
        b'{"total_count": 12, "incomplete_results": "no", "items": []}',
        b'{"total_count": 12, "incomplete_results": false}',
        b'{"total_count": 12, "incomplete_results": false, "items": {"number": 1}}',
    ):
        opener = _Opener(_Response(200, body, **{"Content-Type": "application/json"}))
        with pytest.raises(GitHubIssueError):
            fetch_external_github_issue_search(
                "repo:acme/widgets", fetched_at="2026-08-31T12:00:00Z", opener=opener
            )


def test_fetch_external_github_issue_search_pages_follows_rel_next_across_pages() -> None:
    next_url = "https://api.github.com/search/issues?q=repo%3Aacme%2Fwidgets&page=2"
    opener = _Opener(
        _search_response(
            12, [_search_entry(3164)], Link=f'<{next_url}>; rel="next"'
        ),
        _search_response(
            12, [_search_entry(3165, is_pull_request=True)], incomplete=True
        ),
    )

    result = fetch_external_github_issue_search_pages(
        "repo:acme/widgets is:issue", fetched_at="2026-08-31T12:00:00Z", max_pages=3, opener=opener
    )

    assert len(opener.requests) == 2
    assert opener.requests[1].full_url == next_url
    assert result.total_count == 12
    assert result.incomplete_results is True  # conservative union across pages
    assert result.issue_numbers == (3164,)
    assert result.pull_request_numbers == (3165,)
    assert result.truncated is False


def test_fetch_external_github_issue_search_pages_reports_truncation_at_the_budget() -> None:
    next_url = "https://api.github.com/search/issues?q=repo%3Aacme%2Fwidgets&page=2"
    opener = _Opener(_search_response(12, [_search_entry(3164)], Link=f'<{next_url}>; rel="next"'))

    result = fetch_external_github_issue_search_pages(
        "repo:acme/widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=1, opener=opener
    )

    assert len(opener.requests) == 1
    assert result.truncated is True


def test_fetch_external_github_issue_search_pages_rejects_cross_origin_next() -> None:
    opener = _Opener(
        _search_response(1, [_search_entry(3164)], Link='<https://evil.example/search?page=2>; rel="next"')
    )

    with pytest.raises(GitHubIssueError, match="crossed origin"):
        fetch_external_github_issue_search_pages(
            "repo:acme/widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=2, opener=opener
        )


def test_fetch_external_github_issue_search_pages_rejects_invalid_max_pages() -> None:
    opener = _Opener()
    with pytest.raises(GitHubIssueError, match="max_pages"):
        fetch_external_github_issue_search_pages(
            "repo:acme/widgets", fetched_at="2026-08-31T12:00:00Z", max_pages=0, opener=opener
        )
    assert opener.requests == []
