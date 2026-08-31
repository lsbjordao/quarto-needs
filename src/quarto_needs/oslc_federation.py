from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .oslc_http import (
    HttpFetchPolicy,
    OslcFetchResult,
    fetch_oslc_resource_with_offline_fallback,
)
from .oslc_rdf import OslcRdfError, index_expanded_nodes, materialize_reference, normalize_rdf_representation
from .oslc_rm import (
    OSLC_CORE_NS,
    CachePolicy,
    OslcRmService,
    discover_rm_services,
)
from .oslc_shape import OSLC_PROPERTY, OslcResourceShape, parse_resource_shape

_OSLC_SERVICE = f"{OSLC_CORE_NS}service"
_OSLC_QUERY_CAPABILITY = f"{OSLC_CORE_NS}queryCapability"


@dataclass(frozen=True, slots=True)
class DiscoveredResourceShape:
    uri: str
    fetch_source: str
    shape: OslcResourceShape


@dataclass(frozen=True, slots=True)
class OslcDiscoveryResult:
    service_provider_uri: str
    provider_fetch_source: str
    services: tuple[OslcRmService, ...]
    resource_shapes: tuple[DiscoveredResourceShape, ...]


def _mapping_values(value: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _materialize_service_provider(
    provider: Mapping[str, object],
    *,
    index: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    result = dict(provider)
    services: list[object] = []
    for service_ref in _mapping_values(provider.get(_OSLC_SERVICE)):
        materialized = materialize_reference(service_ref, index=index)
        if not isinstance(materialized, Mapping):
            continue
        service = dict(materialized)
        queries: list[object] = []
        for query_ref in _mapping_values(service.get(_OSLC_QUERY_CAPABILITY)):
            queries.append(materialize_reference(query_ref, index=index))
        if queries:
            service[_OSLC_QUERY_CAPABILITY] = queries
        services.append(service)
    if services:
        result[_OSLC_SERVICE] = services
    return result


def _materialize_shape(
    shape: Mapping[str, object],
    *,
    index: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    result = dict(shape)
    properties: list[object] = []
    for property_ref in _mapping_values(shape.get(OSLC_PROPERTY)):
        properties.append(materialize_reference(property_ref, index=index))
    if properties:
        result[OSLC_PROPERTY] = properties
    return result


def _normalize_fetch(
    fetched: OslcFetchResult,
    *,
    max_nodes: int,
) -> tuple[Mapping[str, object], ...]:
    return normalize_rdf_representation(
        fetched.payload,
        media_type=fetched.representation.media_type,
        max_nodes=max_nodes,
    )


def discover_oslc_rm(
    *,
    service_provider_uri: str,
    cache_root: Path,
    cache_policy: CachePolicy,
    now: str,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
    max_nodes: int = 5_000,
    fetch_shapes: bool = True,
) -> OslcDiscoveryResult:
    """Discover one configured OSLC RM Service Provider without graph import.

    The orchestration is read-only and bounded: HTTP fetch/cache, RDF
    normalization, RM discovery, and optional Resource Shape fetch/parse. No
    discovered external object is merged into the canonical engineering graph.
    """
    provider_fetch = fetch_oslc_resource_with_offline_fallback(
        resource_uri=service_provider_uri,
        service_provider_uri=service_provider_uri,
        cache_root=cache_root,
        cache_policy=cache_policy,
        now=now,
        fetch_policy=fetch_policy,
        auth_headers=auth_headers,
        opener=opener,
    )
    provider_nodes = _normalize_fetch(provider_fetch, max_nodes=max_nodes)
    provider_index = index_expanded_nodes(provider_nodes)
    provider = provider_index.get(service_provider_uri)
    if provider is None:
        raise OslcRdfError(
            "normalized OSLC representation does not contain the configured Service Provider URI"
        )
    materialized_provider = _materialize_service_provider(provider, index=provider_index)
    services = discover_rm_services(materialized_provider)
    if not services:
        raise OslcRdfError("configured OSLC Service Provider exposes no RM service")

    if not fetch_shapes:
        return OslcDiscoveryResult(
            service_provider_uri=service_provider_uri,
            provider_fetch_source=provider_fetch.source,
            services=services,
            resource_shapes=(),
        )

    shape_uris = sorted(
        {
            query.resource_shape_uri
            for service in services
            for query in service.query_capabilities
            if query.resource_shape_uri is not None
        }
    )
    shapes: list[DiscoveredResourceShape] = []
    for shape_uri in shape_uris:
        assert shape_uri is not None
        shape_fetch = fetch_oslc_resource_with_offline_fallback(
            resource_uri=shape_uri,
            service_provider_uri=service_provider_uri,
            cache_root=cache_root,
            cache_policy=cache_policy,
            now=now,
            fetch_policy=fetch_policy,
            auth_headers=auth_headers,
            opener=opener,
        )
        shape_nodes = _normalize_fetch(shape_fetch, max_nodes=max_nodes)
        shape_index = index_expanded_nodes(shape_nodes)
        shape_node = shape_index.get(shape_uri)
        if shape_node is None:
            raise OslcRdfError(
                f"normalized Resource Shape representation does not contain advertised URI {shape_uri}"
            )
        materialized_shape = _materialize_shape(shape_node, index=shape_index)
        parsed_shape = parse_resource_shape(materialized_shape)
        if parsed_shape.shape_uri != shape_uri:
            raise OslcRdfError(
                f"Resource Shape identity mismatch: advertised {shape_uri}, parsed {parsed_shape.shape_uri}"
            )
        shapes.append(
            DiscoveredResourceShape(
                uri=shape_uri,
                fetch_source=shape_fetch.source,
                shape=parsed_shape,
            )
        )

    return OslcDiscoveryResult(
        service_provider_uri=service_provider_uri,
        provider_fetch_source=provider_fetch.source,
        services=services,
        resource_shapes=tuple(shapes),
    )
