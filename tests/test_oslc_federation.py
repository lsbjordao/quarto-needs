from __future__ import annotations

import json
from pathlib import Path

import pytest

from quarto_needs.oslc_federation import discover_oslc_rm
from quarto_needs.oslc_http import HttpFetchPolicy
from quarto_needs.oslc_rdf import OslcRdfError
from quarto_needs.oslc_rm import OSLC_CORE_NS, OSLC_RM_NS, CachePolicy
from quarto_needs.oslc_shape import (
    OSLC_DESCRIBES,
    OSLC_NAME,
    OSLC_OCCURS,
    OSLC_PROPERTY,
    OSLC_PROPERTY_DEFINITION,
)


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
            }
        )

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            return self._payload
        return self._payload[:amount]


class _Opener:
    def __init__(self, *responses: _Response) -> None:
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout: float):  # type: ignore[no-untyped-def]
        self.requests.append((request, timeout))
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        return self.responses.pop(0)


def _provider_document() -> bytes:
    service_provider = "https://provider.test/oslc/sp/1"
    service_uri = "https://provider.test/oslc/service/rm"
    query_uri = "https://provider.test/oslc/query/capability/1"
    shape_uri = "https://provider.test/oslc/shapes/requirement"
    document = [
        {
            "@id": service_provider,
            f"{OSLC_CORE_NS}service": [{"@id": service_uri}],
        },
        {
            "@id": service_uri,
            f"{OSLC_CORE_NS}domain": [{"@id": OSLC_RM_NS}],
            f"{OSLC_CORE_NS}queryCapability": [{"@id": query_uri}],
        },
        {
            "@id": query_uri,
            f"{OSLC_CORE_NS}queryBase": [
                {"@id": "https://provider.test/oslc/rm/requirements"}
            ],
            f"{OSLC_CORE_NS}resourceShape": [{"@id": shape_uri}],
            f"{OSLC_CORE_NS}resourceType": [
                {"@id": f"{OSLC_RM_NS}Requirement"}
            ],
        },
    ]
    return json.dumps(document).encode("utf-8")


def _shape_document(*, identity: str = "https://provider.test/oslc/shapes/requirement") -> bytes:
    property_id = "_:title-property"
    document = [
        {
            "@id": identity,
            OSLC_DESCRIBES: [{"@id": f"{OSLC_RM_NS}Requirement"}],
            OSLC_PROPERTY: [{"@id": property_id}],
        },
        {
            "@id": property_id,
            OSLC_NAME: [{"@value": "title"}],
            OSLC_OCCURS: [{"@id": f"{OSLC_CORE_NS}Exactly-one"}],
            OSLC_PROPERTY_DEFINITION: [
                {"@id": "http://purl.org/dc/terms/title"}
            ],
        },
    ]
    return json.dumps(document).encode("utf-8")


def _discover(tmp_path: Path, opener: _Opener, **overrides):
    values = {
        "service_provider_uri": "https://provider.test/oslc/sp/1",
        "cache_root": tmp_path,
        "cache_policy": CachePolicy(max_age_seconds=3600),
        "now": "2026-08-30T21:00:00Z",
        "fetch_policy": HttpFetchPolicy(max_bytes=100_000),
        "opener": opener,
    }
    values.update(overrides)
    return discover_oslc_rm(**values)


def test_discovery_orchestrates_fetch_normalization_service_and_shape_parsing(tmp_path: Path) -> None:
    opener = _Opener(_Response(_provider_document()), _Response(_shape_document()))

    result = _discover(tmp_path, opener)

    assert result.provider_fetch_source == "live"
    assert len(result.services) == 1
    query = result.services[0].query_capabilities[0]
    assert query.query_base_uri == "https://provider.test/oslc/rm/requirements"
    assert query.resource_shape_uri == "https://provider.test/oslc/shapes/requirement"
    assert len(result.resource_shapes) == 1
    shape = result.resource_shapes[0]
    assert shape.uri == query.resource_shape_uri
    assert shape.shape.describes == (f"{OSLC_RM_NS}Requirement",)
    assert [prop.name for prop in shape.shape.properties] == ["title"]
    assert [request.full_url for request, _ in opener.requests] == [
        "https://provider.test/oslc/sp/1",
        "https://provider.test/oslc/shapes/requirement",
    ]


def test_discovery_can_stop_after_service_capabilities_without_fetching_shapes(tmp_path: Path) -> None:
    opener = _Opener(_Response(_provider_document()))

    result = _discover(tmp_path, opener, fetch_shapes=False)

    assert len(result.services) == 1
    assert result.resource_shapes == ()
    assert len(opener.requests) == 1


def test_discovery_requires_configured_provider_identity_and_rm_service(tmp_path: Path) -> None:
    wrong_provider = json.dumps(
        [{"@id": "https://provider.test/oslc/sp/other"}]
    ).encode("utf-8")
    with pytest.raises(OslcRdfError, match="configured Service Provider URI"):
        _discover(tmp_path, _Opener(_Response(wrong_provider)))

    provider_without_rm = json.dumps(
        [
            {
                "@id": "https://provider.test/oslc/sp/1",
                f"{OSLC_CORE_NS}service": [
                    {
                        f"{OSLC_CORE_NS}domain": [
                            {"@id": "http://open-services.net/ns/cm#"}
                        ]
                    }
                ],
            }
        ]
    ).encode("utf-8")
    with pytest.raises(OslcRdfError, match="exposes no RM service"):
        _discover(tmp_path, _Opener(_Response(provider_without_rm)))


def test_discovery_rejects_resource_shape_identity_mismatch(tmp_path: Path) -> None:
    opener = _Opener(
        _Response(_provider_document()),
        _Response(_shape_document(identity="https://provider.test/oslc/shapes/other")),
    )
    with pytest.raises(OslcRdfError, match="advertised URI"):
        _discover(tmp_path, opener)
