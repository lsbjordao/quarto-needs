from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .oslc_http import (
    HttpFetchPolicy,
    OslcFetchResult,
    fetch_oslc_resource_with_offline_fallback,
)
from .oslc_rdf import OslcRdfError, index_expanded_nodes, normalize_rdf_representation
from .oslc_rm import CachePolicy

RDFS_MEMBER = "http://www.w3.org/2000/01/rdf-schema#member"


@dataclass(frozen=True, slots=True)
class OslcQueryMember:
    resource_uri: str
    inline_node: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not self.resource_uri.startswith(("http://", "https://")):
            raise ValueError("OSLC query member URI must be absolute HTTP(S)")
        if self.inline_node is not None:
            object.__setattr__(self, "inline_node", MappingProxyType(dict(self.inline_node)))

    @property
    def is_inline(self) -> bool:
        return self.inline_node is not None

    def to_dict(self) -> dict[str, object]:
        return {
            "resourceUri": self.resource_uri,
            "inline": self.is_inline,
            "node": dict(self.inline_node) if self.inline_node is not None else None,
        }


@dataclass(frozen=True, slots=True)
class OslcQueryResult:
    query_base_uri: str
    fetch_source: str
    response_digest: str
    fetched_at: str
    member_property_uri: str
    members: tuple[OslcQueryMember, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "oslc-query-result-v1",
            "queryBaseUri": self.query_base_uri,
            "fetchSource": self.fetch_source,
            "responseDigest": self.response_digest,
            "fetchedAt": self.fetched_at,
            "memberPropertyUri": self.member_property_uri,
            "members": [member.to_dict() for member in self.members],
        }


def _mapping_values(value: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def parse_query_result(
    expanded_nodes: tuple[Mapping[str, object], ...],
    *,
    query_base_uri: str,
    member_property_uri: str = RDFS_MEMBER,
    max_members: int = 1_000,
) -> tuple[OslcQueryMember, ...]:
    """Parse one already-expanded OSLC query result container.

    The parser never dereferences member URIs. A member receives ``inline_node``
    only when that same RDF representation already contains a node with the
    referenced identity.
    """
    if max_members < 1:
        raise ValueError("max_members must be at least 1")
    if not member_property_uri:
        raise ValueError("member_property_uri must be non-empty")

    index = index_expanded_nodes(expanded_nodes)
    container = index.get(query_base_uri)
    if container is None:
        raise OslcRdfError(
            "normalized OSLC query representation does not contain the queryBase URI"
        )

    member_uris: list[str] = []
    for item in _mapping_values(container.get(member_property_uri)):
        identifier = item.get("@id")
        if not isinstance(identifier, str):
            raise OslcRdfError("OSLC query member reference must contain an @id")
        if not identifier.startswith(("http://", "https://")):
            raise OslcRdfError("OSLC query member identity must be absolute HTTP(S)")
        member_uris.append(identifier)
        if len(member_uris) > max_members:
            raise OslcRdfError(
                f"OSLC query result exceeds member limit {max_members}"
            )

    if len(set(member_uris)) != len(member_uris):
        raise OslcRdfError("OSLC query result contains duplicate member identities")

    return tuple(
        OslcQueryMember(resource_uri=uri, inline_node=index.get(uri))
        for uri in sorted(member_uris)
    )


def execute_oslc_query(
    *,
    query_base_uri: str,
    service_provider_uri: str,
    cache_root: Path,
    cache_policy: CachePolicy,
    now: str,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
    max_nodes: int = 5_000,
    max_members: int = 1_000,
    member_property_uri: str = RDFS_MEMBER,
) -> OslcQueryResult:
    """Execute a bounded GET against one discovered OSLC Query Capability.

    No ``oslc.where`` or ``oslc.searchTerms`` is added in this first slice. The
    query therefore requests the resources described by the discovered query
    capability while preserving the existing GET-only transport boundary.
    Member URIs are reported but never recursively fetched here.
    """
    fetched: OslcFetchResult = fetch_oslc_resource_with_offline_fallback(
        resource_uri=query_base_uri,
        service_provider_uri=service_provider_uri,
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
    members = parse_query_result(
        nodes,
        query_base_uri=query_base_uri,
        member_property_uri=member_property_uri,
        max_members=max_members,
    )
    identity = fetched.representation.identity
    return OslcQueryResult(
        query_base_uri=query_base_uri,
        fetch_source=fetched.source,
        response_digest=identity.digest,
        fetched_at=identity.fetched_at,
        member_property_uri=member_property_uri,
        members=members,
    )
