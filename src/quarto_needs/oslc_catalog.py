from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .oslc_http import HttpFetchPolicy, fetch_oslc_resource_with_offline_fallback
from .oslc_rdf import OslcRdfError, index_expanded_nodes, normalize_rdf_representation
from .oslc_rm import OSLC_CORE_NS, CachePolicy

OSLC_SERVICE_PROVIDER = f"{OSLC_CORE_NS}serviceProvider"
OSLC_SERVICE_PROVIDER_CATALOG = f"{OSLC_CORE_NS}serviceProviderCatalog"


@dataclass(frozen=True, slots=True)
class OslcCatalogResult:
    catalog_uri: str
    fetch_source: str
    service_provider_uris: tuple[str, ...]
    nested_catalog_uris: tuple[str, ...]


def _ids(value: object) -> tuple[str, ...]:
    values: list[str] = []
    candidates = value if isinstance(value, list) else [value]
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        identifier = candidate.get("@id")
        if isinstance(identifier, str):
            values.append(identifier)
    return tuple(values)


def parse_service_provider_catalog(
    expanded_catalog: Mapping[str, object],
    *,
    max_providers: int = 200,
    max_nested_catalogs: int = 50,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if max_providers <= 0:
        raise ValueError("max_providers must be positive")
    if max_nested_catalogs < 0:
        raise ValueError("max_nested_catalogs must be non-negative")

    providers = tuple(sorted(set(_ids(expanded_catalog.get(OSLC_SERVICE_PROVIDER)))))
    nested = tuple(
        sorted(set(_ids(expanded_catalog.get(OSLC_SERVICE_PROVIDER_CATALOG))))
    )
    if len(providers) > max_providers:
        raise OslcRdfError(
            f"OSLC Service Provider Catalog exposes {len(providers)} providers, "
            f"limit is {max_providers}"
        )
    if len(nested) > max_nested_catalogs:
        raise OslcRdfError(
            f"OSLC Service Provider Catalog exposes {len(nested)} nested catalogs, "
            f"limit is {max_nested_catalogs}"
        )
    return providers, nested


def discover_oslc_catalog(
    *,
    catalog_uri: str,
    cache_root: Path,
    cache_policy: CachePolicy,
    now: str,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
    max_nodes: int = 5_000,
    max_providers: int = 200,
    max_nested_catalogs: int = 50,
) -> OslcCatalogResult:
    fetched = fetch_oslc_resource_with_offline_fallback(
        resource_uri=catalog_uri,
        service_provider_uri=catalog_uri,
        cache_root=cache_root,
        cache_policy=cache_policy,
        now=now,
        fetch_policy=fetch_policy,
        auth_headers=auth_headers,
        opener=opener,
    )
    nodes = normalize_rdf_representation(
        fetched.payload,
        media_type=fetched.representation.media_type,
        max_nodes=max_nodes,
    )
    index = index_expanded_nodes(nodes)
    catalog = index.get(catalog_uri)
    if catalog is None:
        raise OslcRdfError(
            "normalized OSLC representation does not contain the configured Service Provider Catalog URI"
        )
    providers, nested = parse_service_provider_catalog(
        catalog,
        max_providers=max_providers,
        max_nested_catalogs=max_nested_catalogs,
    )
    return OslcCatalogResult(
        catalog_uri=catalog_uri,
        fetch_source=fetched.source,
        service_provider_uris=providers,
        nested_catalog_uris=nested,
    )
