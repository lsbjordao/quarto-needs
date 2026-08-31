from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.oslc_cache import CachedRepresentation
from quarto_needs.oslc_http import OslcFetchResult
from quarto_needs.oslc_query import RDFS_MEMBER, execute_oslc_query, parse_query_result
from quarto_needs.oslc_rdf import OslcRdfError
from quarto_needs.oslc_rm import CachePolicy, ExternalResourceIdentity


QUERY_BASE = "https://provider.test/oslc/rm/requirements"
MEMBER_A = "https://provider.test/oslc/rm/requirements/a"
MEMBER_B = "https://provider.test/oslc/rm/requirements/b"


def _expanded_nodes():
    return (
        {
            "@id": QUERY_BASE,
            RDFS_MEMBER: [
                {"@id": MEMBER_B},
                {"@id": MEMBER_A},
            ],
        },
        {
            "@id": MEMBER_A,
            "http://purl.org/dc/terms/title": [{"@value": "Requirement A"}],
        },
    )


def test_parse_query_result_is_deterministic_and_does_not_dereference_members() -> None:
    members = parse_query_result(_expanded_nodes(), query_base_uri=QUERY_BASE)

    assert [member.resource_uri for member in members] == [MEMBER_A, MEMBER_B]
    assert members[0].is_inline is True
    assert members[1].is_inline is False
    assert members[0].inline_node["@id"] == MEMBER_A


def test_parse_query_result_rejects_duplicate_members_and_limits() -> None:
    duplicate = (
        {
            "@id": QUERY_BASE,
            RDFS_MEMBER: [{"@id": MEMBER_A}, {"@id": MEMBER_A}],
        },
        {"@id": MEMBER_A},
    )
    with pytest.raises(OslcRdfError, match="duplicate member identities"):
        parse_query_result(duplicate, query_base_uri=QUERY_BASE)

    with pytest.raises(OslcRdfError, match="exceeds member limit 1"):
        parse_query_result(_expanded_nodes(), query_base_uri=QUERY_BASE, max_members=1)


def test_parse_query_result_requires_the_query_base_container() -> None:
    with pytest.raises(OslcRdfError, match="does not contain the queryBase URI"):
        parse_query_result(({"@id": MEMBER_A},), query_base_uri=QUERY_BASE)


@pytest.mark.requirement("SYS-007")
@pytest.mark.requirement("FUN-012")
@pytest.mark.requirement("NFR-006")
@pytest.mark.quarto_need_test_case("TC-017")
def test_execute_oslc_query_uses_existing_bounded_fetch_and_reports_response_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    payload = b"query-response"
    identity = ExternalResourceIdentity(
        resource_uri=QUERY_BASE,
        service_provider_uri="https://provider.test/oslc/sp/1",
        digest="sha256:" + "1" * 64,
        fetched_at="2026-08-30T21:00:00Z",
    )
    fetched = OslcFetchResult(
        source="live",
        representation=CachedRepresentation(identity=identity, media_type="text/turtle"),
        payload=payload,
    )
    captured = {}

    def fake_fetch(**kwargs):
        captured.update(kwargs)
        return fetched

    def fake_normalize(raw, *, media_type, max_nodes):
        assert raw == payload
        assert media_type == "text/turtle"
        assert max_nodes == 250
        return _expanded_nodes()

    monkeypatch.setattr("quarto_needs.oslc_query.fetch_oslc_resource_with_offline_fallback", fake_fetch)
    monkeypatch.setattr("quarto_needs.oslc_query.normalize_rdf_representation", fake_normalize)

    result = execute_oslc_query(
        query_base_uri=QUERY_BASE,
        service_provider_uri="https://provider.test/oslc/sp/1",
        cache_root=tmp_path / "cache",
        cache_policy=CachePolicy(max_age_seconds=3600),
        now="2026-08-30T21:01:00Z",
        max_nodes=250,
        max_members=10,
    )

    assert captured["resource_uri"] == QUERY_BASE
    assert captured["service_provider_uri"] == "https://provider.test/oslc/sp/1"
    assert result.fetch_source == "live"
    assert result.response_digest == "sha256:" + "1" * 64
    assert result.fetched_at == "2026-08-30T21:00:00Z"
    assert [member.resource_uri for member in result.members] == [MEMBER_A, MEMBER_B]
    assert result.to_dict()["schema"] == "oslc-query-result-v1"
