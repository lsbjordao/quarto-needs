from __future__ import annotations

import json
from pathlib import Path

import pytest

from quarto_needs.oslc_catalog import discover_oslc_catalog, parse_service_provider_catalog
from quarto_needs.oslc_http import HttpFetchPolicy
from quarto_needs.oslc_rdf import OslcRdfError
from quarto_needs.oslc_rm import OSLC_CORE_NS, CachePolicy


class _Headers(dict[str, str]):
    def get(self, key: str, default=None):  # type: ignore[override]
        for name, value in self.items():
            if name.lower() == key.lower():
                return value
        return default


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.status = 200
        self.code = 200
        self._payload = payload
        self.headers = _Headers(
            {
                "Content-Type": "application/ld+json",
                "Content-Length": str(len(payload)),
            }
        )

    def read(self, amount: int = -1) -> bytes:
        return self._payload if amount < 0 else self._payload[:amount]


class _Opener:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.requests = []

    def open(self, request, timeout: float):  # type: ignore[no-untyped-def]
        self.requests.append((request, timeout))
        return self.response


def test_catalog_parser_returns_sorted_unique_providers_and_nested_catalogs() -> None:
    catalog = {
        f"{OSLC_CORE_NS}serviceProvider": [
            {"@id": "https://provider.test/oslc/sp/z"},
            {"@id": "https://provider.test/oslc/sp/a"},
            {"@id": "https://provider.test/oslc/sp/a"},
        ],
        f"{OSLC_CORE_NS}serviceProviderCatalog": [
            {"@id": "https://provider.test/oslc/catalog/nested-b"},
            {"@id": "https://provider.test/oslc/catalog/nested-a"},
        ],
    }

    providers, nested = parse_service_provider_catalog(catalog)

    assert providers == (
        "https://provider.test/oslc/sp/a",
        "https://provider.test/oslc/sp/z",
    )
    assert nested == (
        "https://provider.test/oslc/catalog/nested-a",
        "https://provider.test/oslc/catalog/nested-b",
    )


def test_catalog_parser_enforces_provider_and_nested_catalog_budgets() -> None:
    catalog = {
        f"{OSLC_CORE_NS}serviceProvider": [
            {"@id": f"https://provider.test/oslc/sp/{index}"} for index in range(3)
        ],
        f"{OSLC_CORE_NS}serviceProviderCatalog": [
            {"@id": f"https://provider.test/oslc/catalog/{index}"}
            for index in range(2)
        ],
    }
    with pytest.raises(OslcRdfError, match="3 providers, limit is 2"):
        parse_service_provider_catalog(catalog, max_providers=2)
    with pytest.raises(OslcRdfError, match="2 nested catalogs, limit is 1"):
        parse_service_provider_catalog(catalog, max_nested_catalogs=1)


def test_catalog_discovery_fetches_one_level_without_recursive_crawling(tmp_path: Path) -> None:
    catalog_uri = "https://provider.test/oslc/catalog"
    document = [
        {
            "@id": catalog_uri,
            f"{OSLC_CORE_NS}serviceProvider": [
                {"@id": "https://provider.test/oslc/sp/rm"},
                {"@id": "https://provider.test/oslc/sp/cm"},
            ],
            f"{OSLC_CORE_NS}serviceProviderCatalog": [
                {"@id": "https://provider.test/oslc/catalog/nested"}
            ],
        }
    ]
    payload = json.dumps(document).encode("utf-8")
    opener = _Opener(_Response(payload))

    result = discover_oslc_catalog(
        catalog_uri=catalog_uri,
        cache_root=tmp_path,
        cache_policy=CachePolicy(max_age_seconds=3600),
        now="2026-08-30T21:00:00Z",
        fetch_policy=HttpFetchPolicy(max_bytes=100_000),
        opener=opener,
    )

    assert result.catalog_uri == catalog_uri
    assert result.fetch_source == "live"
    assert result.service_provider_uris == (
        "https://provider.test/oslc/sp/cm",
        "https://provider.test/oslc/sp/rm",
    )
    assert result.nested_catalog_uris == (
        "https://provider.test/oslc/catalog/nested",
    )
    assert len(opener.requests) == 1


def test_catalog_discovery_requires_configured_catalog_identity(tmp_path: Path) -> None:
    payload = json.dumps([{"@id": "https://provider.test/oslc/other"}]).encode("utf-8")
    with pytest.raises(OslcRdfError, match="configured Service Provider Catalog URI"):
        discover_oslc_catalog(
            catalog_uri="https://provider.test/oslc/catalog",
            cache_root=tmp_path,
            cache_policy=CachePolicy(max_age_seconds=3600),
            now="2026-08-30T21:00:00Z",
            opener=_Opener(_Response(payload)),
        )
