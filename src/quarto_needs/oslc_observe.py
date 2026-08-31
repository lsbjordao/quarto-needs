from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .oslc_http import HttpFetchPolicy, fetch_oslc_resource_with_offline_fallback
from .oslc_query import OslcQueryResult
from .oslc_rdf import OslcRdfError, index_expanded_nodes, normalize_rdf_representation
from .oslc_reconcile import ExternalRequirementObservation
from .oslc_rm import CachePolicy, ExternalResourceIdentity
from .snapshot import thaw_json

DCTERMS_IDENTIFIER = "http://purl.org/dc/terms/identifier"
DCTERMS_TITLE = "http://purl.org/dc/terms/title"
DCTERMS_DESCRIPTION = "http://purl.org/dc/terms/description"


@dataclass(frozen=True, slots=True)
class OslcObservationBatch:
    query_base_uri: str
    query_response_digest: str
    observations: tuple[ExternalRequirementObservation, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "oslc-observation-batch-v1",
            "queryBaseUri": self.query_base_uri,
            "queryResponseDigest": self.query_response_digest,
            "observations": [observation.to_dict() for observation in self.observations],
        }


def _literal_values(value: object) -> tuple[object, ...]:
    if isinstance(value, Mapping):
        values = (value,)
    elif isinstance(value, list):
        values = tuple(item for item in value if isinstance(item, Mapping))
    else:
        values = ()
    return tuple(item["@value"] for item in values if "@value" in item)


def _one_string(
    node: Mapping[str, object],
    predicate: str,
    *,
    field: str,
    required: bool,
) -> str | None:
    values = _literal_values(node.get(predicate))
    if not values and not required:
        return None
    if len(values) != 1 or not isinstance(values[0], str):
        qualifier = "exactly one" if required else "at most one"
        raise OslcRdfError(
            f"OSLC requirement {field} must contain {qualifier} string literal"
        )
    return values[0]


def parse_external_requirement_observation(
    node: Mapping[str, object],
    *,
    identity: ExternalResourceIdentity,
) -> ExternalRequirementObservation:
    """Normalize one fetched OSLC requirement without creating canonical identity.

    The external resource URI and fetched representation provenance remain the
    authority for the observation. ``dcterms:identifier`` is data only and is
    never promoted into a Quarto-Needs canonical ID by this parser.
    """
    node_id = node.get("@id")
    if node_id != identity.resource_uri:
        raise OslcRdfError(
            "normalized OSLC requirement representation does not contain the requested resource identity"
        )

    title = _one_string(
        node,
        DCTERMS_TITLE,
        field="dcterms:title",
        required=True,
    )
    assert title is not None
    description = _one_string(
        node,
        DCTERMS_DESCRIPTION,
        field="dcterms:description",
        required=False,
    )
    external_identifier = _one_string(
        node,
        DCTERMS_IDENTIFIER,
        field="dcterms:identifier",
        required=False,
    )

    residual = {
        key: thaw_json(value)
        for key, value in node.items()
        if key
        not in {
            "@id",
            DCTERMS_TITLE,
            DCTERMS_DESCRIPTION,
            DCTERMS_IDENTIFIER,
        }
    }
    return ExternalRequirementObservation(
        identity=identity,
        title=title,
        description=description or "",
        external_identifier=external_identifier,
        attributes={"expandedRdf": residual},
    )


def materialize_query_observations(
    query_result: OslcQueryResult,
    *,
    service_provider_uri: str,
    cache_root: Path,
    cache_policy: CachePolicy,
    now: str,
    fetch_policy: HttpFetchPolicy = HttpFetchPolicy(),
    auth_headers: Mapping[str, str] | None = None,
    opener=None,
    max_nodes_per_member: int = 1_000,
    max_members: int = 200,
) -> OslcObservationBatch:
    """Fetch bounded query members into independent external observations.

    Every member is fetched independently even when the query response already
    carried an inline node. This deliberately avoids treating the query
    container digest as the member's representation digest. No relation URI or
    nested Linked Data reference is recursively dereferenced.
    """
    if max_nodes_per_member < 1:
        raise ValueError("max_nodes_per_member must be at least 1")
    if max_members < 1:
        raise ValueError("max_members must be at least 1")
    if len(query_result.members) > max_members:
        raise OslcRdfError(
            f"OSLC observation batch exceeds member fetch limit {max_members}"
        )

    observations: list[ExternalRequirementObservation] = []
    for member in query_result.members:
        fetched = fetch_oslc_resource_with_offline_fallback(
            resource_uri=member.resource_uri,
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
            max_nodes=max_nodes_per_member,
        )
        node = index_expanded_nodes(nodes).get(member.resource_uri)
        if node is None:
            raise OslcRdfError(
                f"normalized OSLC requirement representation does not contain requested URI {member.resource_uri}"
            )

        fetched_identity = fetched.representation.identity
        trust_state = (
            "stale"
            if fetched.source == "cache-stale-allowed"
            else fetched_identity.trust_state
        )
        identity = ExternalResourceIdentity(
            resource_uri=fetched_identity.resource_uri,
            service_provider_uri=fetched_identity.service_provider_uri,
            digest=fetched_identity.digest,
            fetched_at=fetched_identity.fetched_at,
            trust_state=trust_state,
            etag=fetched_identity.etag,
            last_modified=fetched_identity.last_modified,
        )
        observations.append(
            parse_external_requirement_observation(node, identity=identity)
        )

    observations.sort(key=lambda item: item.identity.resource_uri)
    return OslcObservationBatch(
        query_base_uri=query_result.query_base_uri,
        query_response_digest=query_result.response_digest,
        observations=tuple(observations),
    )
