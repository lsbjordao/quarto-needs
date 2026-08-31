from __future__ import annotations

import json
from pathlib import Path

import pytest

from quarto_needs.oslc_http import HttpFetchPolicy
from quarto_needs.oslc_observe import (
    DCTERMS_DESCRIPTION,
    DCTERMS_IDENTIFIER,
    DCTERMS_TITLE,
    materialize_query_observations,
)
from quarto_needs.oslc_query import OslcQueryMember, OslcQueryResult
from quarto_needs.oslc_rdf import OslcRdfError
from quarto_needs.oslc_rm import CachePolicy, content_digest


class _Headers(dict[str, str]):
    def get(self, key: str, default=None):  # type: ignore[override]
        for name, value in self.items():
            if name.lower() == key.lower():
                return value
        return default


class _Response:
    def __init__(self, payload: bytes, *, status: int = 200) -> None:
        self.status = status
        self.code = status
        self._payload = payload
        self.headers = _Headers(
            {
                "Content-Type": "application/ld+json",
                "Content-Length": str(len(payload)),
                "ETag": '"member-etag"',
            }
        )

    def read(self, amount: int = -1) -> bytes:
        return self._payload if amount < 0 else self._payload[:amount]


class _Opener:
    def __init__(self, *responses: _Response) -> None:
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout: float):  # type: ignore[no-untyped-def]
        self.requests.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        return self.responses.pop(0)


def _query(*uris: str) -> OslcQueryResult:
    return OslcQueryResult(
        query_base_uri="https://provider.test/oslc/query/requirements",
        fetch_source="live",
        response_digest="sha256:query",
        fetched_at="2026-08-30T21:00:00Z",
        member_property_uri="http://www.w3.org/2000/01/rdf-schema#member",
        members=tuple(OslcQueryMember(uri) for uri in uris),
    )


def _requirement(uri: str, *, title: str = "Remote requirement") -> bytes:
    return json.dumps(
        {
            "@id": uri,
            DCTERMS_TITLE: [{"@value": title}],
            DCTERMS_DESCRIPTION: [{"@value": "Remote body"}],
            DCTERMS_IDENTIFIER: [{"@value": "EXT-42"}],
            "https://example.test/priority": [{"@value": "high"}],
        }
    ).encode("utf-8")


@pytest.mark.requirement("SYS-007", "FUN-011", "FUN-012", "NFR-006")
@pytest.mark.quarto_need_test_case("TC-018")
def test_materialization_fetches_each_member_and_preserves_individual_provenance(tmp_path: Path) -> None:
    first_uri = "https://provider.test/oslc/rm/1"
    second_uri = "https://provider.test/oslc/rm/2"
    first = _requirement(first_uri, title="First")
    second = _requirement(second_uri, title="Second")
    # The query asks for /2 before /1, so fake transport responses must follow
    # that request order. Identity validation intentionally rejects mismatches.
    opener = _Opener(_Response(second), _Response(first))

    result = materialize_query_observations(
        _query(second_uri, first_uri),
        service_provider_uri="https://provider.test/oslc/sp/1",
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=3600),
        now="2026-08-30T21:10:00Z",
        fetch_policy=HttpFetchPolicy(max_bytes=100_000),
        opener=opener,
    )

    assert [item.identity.resource_uri for item in result.observations] == [first_uri, second_uri]
    by_uri = {item.identity.resource_uri: item for item in result.observations}
    assert by_uri[first_uri].identity.digest == content_digest(first)
    assert by_uri[second_uri].identity.digest == content_digest(second)
    assert by_uri[first_uri].identity.digest != result.query_response_digest
    assert by_uri[first_uri].external_identifier == "EXT-42"
    assert by_uri[first_uri].attributes["expandedRdf"]["https://example.test/priority"] == (
        {"@value": "high"},
    )
    assert [request.full_url for request, _ in opener.requests] == [second_uri, first_uri]


def test_materialization_rejects_fanout_above_explicit_member_limit(tmp_path: Path) -> None:
    query = _query(
        "https://provider.test/oslc/rm/1",
        "https://provider.test/oslc/rm/2",
    )
    opener = _Opener()
    with pytest.raises(OslcRdfError, match="member fetch limit 1"):
        materialize_query_observations(
            query,
            service_provider_uri="https://provider.test/oslc/sp/1",
            cache_root=tmp_path,
            cache_policy=CachePolicy(max_age_seconds=3600),
            now="2026-08-30T21:10:00Z",
            max_members=1,
            opener=opener,
        )
    assert opener.requests == []


def test_materialization_requires_requested_identity_and_title(tmp_path: Path) -> None:
    uri = "https://provider.test/oslc/rm/1"
    wrong = json.dumps(
        {
            "@id": "https://provider.test/oslc/rm/other",
            DCTERMS_TITLE: [{"@value": "Wrong"}],
        }
    ).encode("utf-8")
    with pytest.raises(OslcRdfError, match="does not contain requested URI"):
        materialize_query_observations(
            _query(uri),
            service_provider_uri="https://provider.test/oslc/sp/1",
            cache_root=tmp_path / "wrong",
            cache_policy=CachePolicy(max_age_seconds=3600),
            now="2026-08-30T21:10:00Z",
            opener=_Opener(_Response(wrong)),
        )

    no_title = json.dumps(
        {
            "@id": uri,
            DCTERMS_DESCRIPTION: [{"@value": "Body without title"}],
        }
    ).encode("utf-8")
    with pytest.raises(OslcRdfError, match="dcterms:title"):
        materialize_query_observations(
            _query(uri),
            service_provider_uri="https://provider.test/oslc/sp/1",
            cache_root=tmp_path / "no-title",
            cache_policy=CachePolicy(max_age_seconds=3600),
            now="2026-08-30T21:10:00Z",
            opener=_Opener(_Response(no_title)),
        )
