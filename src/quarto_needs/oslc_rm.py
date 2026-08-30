from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Literal, Mapping
from urllib.parse import quote, urlparse

from .snapshot import AnalysisSnapshot, RelationRecord, thaw_json

OSLC_CORE_NS = "http://open-services.net/ns/core#"
OSLC_RM_NS = "http://open-services.net/ns/rm#"
DCTERMS_NS = "http://purl.org/dc/terms/"
QN_OSLC_NS = "urn:quarto-needs:oslc:v1:"

OSLC_REQUIREMENT = f"{OSLC_RM_NS}Requirement"
OSLC_REQUIREMENT_COLLECTION = f"{OSLC_RM_NS}RequirementCollection"

_OSLC_SERVICE = f"{OSLC_CORE_NS}service"
_OSLC_DOMAIN = f"{OSLC_CORE_NS}domain"
_OSLC_QUERY_CAPABILITY = f"{OSLC_CORE_NS}queryCapability"
_OSLC_QUERY_BASE = f"{OSLC_CORE_NS}queryBase"
_OSLC_RESOURCE_SHAPE = f"{OSLC_CORE_NS}resourceShape"
_OSLC_RESOURCE_TYPE = f"{OSLC_CORE_NS}resourceType"

# Only mappings with a direct, conservative semantic correspondence are
# promoted into the OSLC RM vocabulary. Every other canonical relation remains
# available through Quarto-Needs extension metadata instead of being guessed.
OSLC_RELATION_MAP: Mapping[str, str] = MappingProxyType(
    {
        "implemented-by": f"{OSLC_RM_NS}implementedBy",
        "verified-by": f"{OSLC_RM_NS}validatedBy",
        "validated-by": f"{OSLC_RM_NS}validatedBy",
    }
)

TrustState = Literal["trusted", "unverified", "stale", "rejected"]
CacheDecision = Literal["fresh", "stale-allowed", "stale-rejected"]


def _parse_instant(value: str, field: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ExternalResourceIdentity:
    resource_uri: str
    service_provider_uri: str
    digest: str
    fetched_at: str
    trust_state: TrustState = "unverified"
    etag: str | None = None
    last_modified: str | None = None

    def __post_init__(self) -> None:
        _require_absolute_http_uri(self.resource_uri, "resource_uri")
        _require_absolute_http_uri(self.service_provider_uri, "service_provider_uri")
        if not self.digest.startswith("sha256:") or len(self.digest) != 71:
            raise ValueError("digest must use sha256:<64 lowercase hexadecimal digits>")
        hex_digest = self.digest.removeprefix("sha256:")
        if any(character not in "0123456789abcdef" for character in hex_digest):
            raise ValueError("digest must use sha256:<64 lowercase hexadecimal digits>")
        _parse_instant(self.fetched_at, "fetched_at")
        if self.trust_state not in {"trusted", "unverified", "stale", "rejected"}:
            raise ValueError(f"unsupported OSLC trust state: {self.trust_state}")

    def to_dict(self) -> dict[str, object]:
        return {
            "resourceUri": self.resource_uri,
            "serviceProviderUri": self.service_provider_uri,
            "digest": self.digest,
            "fetchedAt": self.fetched_at,
            "trustState": self.trust_state,
            "etag": self.etag,
            "lastModified": self.last_modified,
        }


@dataclass(frozen=True, slots=True)
class CachePolicy:
    max_age_seconds: int
    allow_stale: bool = False

    def __post_init__(self) -> None:
        if self.max_age_seconds < 0:
            raise ValueError("max_age_seconds must be non-negative")

    def decide(self, identity: ExternalResourceIdentity, *, now: str) -> CacheDecision:
        fetched = _parse_instant(identity.fetched_at, "fetched_at")
        current = _parse_instant(now, "now")
        age = (current - fetched).total_seconds()
        if age < 0:
            raise ValueError("now must not precede fetched_at")
        if age <= self.max_age_seconds:
            return "fresh"
        return "stale-allowed" if self.allow_stale else "stale-rejected"


@dataclass(frozen=True, slots=True)
class OslcQueryCapability:
    query_base_uri: str
    resource_shape_uri: str | None = None
    resource_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_absolute_http_uri(self.query_base_uri, "query_base_uri")
        if self.resource_shape_uri is not None:
            _require_absolute_http_uri(self.resource_shape_uri, "resource_shape_uri")
        for resource_type in self.resource_types:
            if not urlparse(resource_type).scheme:
                raise ValueError("resource_types entries must be absolute URIs")


@dataclass(frozen=True, slots=True)
class OslcRmService:
    service_id: str | None
    query_capabilities: tuple[OslcQueryCapability, ...]

    def __post_init__(self) -> None:
        if self.service_id is not None:
            if not self.service_id.startswith("_:"):
                _require_absolute_http_uri(self.service_id, "service_id")
        object.__setattr__(self, "query_capabilities", tuple(self.query_capabilities))


def _require_absolute_http_uri(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute http(s) URI")


def _expanded_objects(value: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _expanded_ids(value: object) -> tuple[str, ...]:
    values: list[str] = []
    for item in _expanded_objects(value):
        identifier = item.get("@id")
        if isinstance(identifier, str):
            values.append(identifier)
    return tuple(values)


def discover_rm_services(expanded_service_provider: Mapping[str, object]) -> tuple[OslcRmService, ...]:
    """Extract RM services from an already-expanded JSON-LD ServiceProvider.

    Expansion/transport is intentionally outside this pure function. The live
    adapter can later support JSON-LD, Turtle, or RDF/XML while this discovery
    contract remains stable and independently testable.
    """
    services: list[OslcRmService] = []
    for service in _expanded_objects(expanded_service_provider.get(_OSLC_SERVICE)):
        domains = _expanded_ids(service.get(_OSLC_DOMAIN))
        if len(domains) != 1:
            raise ValueError("OSLC Service must expose exactly one oslc:domain")
        if domains[0] != OSLC_RM_NS:
            continue

        capabilities: list[OslcQueryCapability] = []
        for query in _expanded_objects(service.get(_OSLC_QUERY_CAPABILITY)):
            bases = _expanded_ids(query.get(_OSLC_QUERY_BASE))
            if len(bases) != 1:
                raise ValueError("OSLC RM QueryCapability must expose exactly one oslc:queryBase")
            shapes = _expanded_ids(query.get(_OSLC_RESOURCE_SHAPE))
            if len(shapes) > 1:
                raise ValueError("OSLC RM QueryCapability must expose at most one oslc:resourceShape")
            resource_types = tuple(sorted(set(_expanded_ids(query.get(_OSLC_RESOURCE_TYPE)))))
            capabilities.append(
                OslcQueryCapability(
                    query_base_uri=bases[0],
                    resource_shape_uri=shapes[0] if shapes else None,
                    resource_types=resource_types,
                )
            )

        service_id = service.get("@id")
        if service_id is not None and not isinstance(service_id, str):
            raise ValueError("OSLC service @id must be a string when present")
        services.append(
            OslcRmService(
                service_id=service_id,
                query_capabilities=tuple(
                    sorted(capabilities, key=lambda item: item.query_base_uri)
                ),
            )
        )

    return tuple(
        sorted(
            services,
            key=lambda item: (item.service_id or "", tuple(q.query_base_uri for q in item.query_capabilities)),
        )
    )


def content_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def is_requirement_type(type_name: str) -> bool:
    return type_name == "requirement" or type_name.endswith("-requirement")


def resource_uri(base_uri: str, canonical_id: str) -> str:
    _require_absolute_http_uri(base_uri, "base_uri")
    return base_uri.rstrip("/") + "/resource/" + quote(canonical_id, safe="")


def _relation_projection(
    relation: RelationRecord,
    *,
    base_uri: str,
) -> dict[str, object]:
    projected: dict[str, object] = {
        "canonicalRelation": relation.catalog_name,
        "authoredName": relation.authored_name,
        "semanticFamily": relation.semantic_family,
        "target": {"@id": resource_uri(base_uri, relation.target)},
    }
    oslc_property = OSLC_RELATION_MAP.get(relation.catalog_name)
    if oslc_property is not None:
        projected["oslcProperty"] = oslc_property
    return projected


def build_requirement_resources(
    snapshot: AnalysisSnapshot,
    *,
    base_uri: str,
    service_provider_uri: str,
) -> list[dict[str, object]]:
    """Project canonical requirement nodes into a read-only OSLC RM client model.

    This is deliberately not an OSLC server implementation. It prepares stable
    resources and provenance for later discovery/cache/network adapters while
    keeping all engineering semantics sourced from ``AnalysisSnapshot``.
    """
    _require_absolute_http_uri(base_uri, "base_uri")
    _require_absolute_http_uri(service_provider_uri, "service_provider_uri")

    resources: list[dict[str, object]] = []
    for item in sorted(snapshot.objects, key=lambda value: (value.id.casefold(), value.id)):
        if not is_requirement_type(item.type):
            continue

        outgoing = sorted(
            snapshot.outgoing.get(item.id, ()),
            key=lambda relation: (
                relation.catalog_name.casefold(),
                relation.catalog_name,
                relation.target.casefold(),
                relation.target,
                relation.authored_name.casefold(),
                relation.authored_name,
            ),
        )
        relation_projections = [
            _relation_projection(relation, base_uri=base_uri) for relation in outgoing
        ]

        resource: dict[str, object] = {
            "@id": resource_uri(base_uri, item.id),
            "@type": OSLC_REQUIREMENT,
            f"{DCTERMS_NS}identifier": item.id,
            f"{DCTERMS_NS}title": item.title,
            f"{DCTERMS_NS}description": item.body,
            f"{OSLC_CORE_NS}serviceProvider": {"@id": service_provider_uri},
            f"{QN_OSLC_NS}canonicalId": item.id,
            f"{QN_OSLC_NS}objectType": item.type,
            f"{QN_OSLC_NS}status": item.status,
            f"{QN_OSLC_NS}rationale": item.rationale,
            f"{QN_OSLC_NS}attributes": thaw_json(item.attributes),
            f"{QN_OSLC_NS}relations": relation_projections,
            f"{QN_OSLC_NS}semanticGraphFingerprint": snapshot.semantic_graph_fingerprint,
        }

        for relation, projected in zip(outgoing, relation_projections, strict=True):
            oslc_property = projected.get("oslcProperty")
            if not isinstance(oslc_property, str):
                continue
            target = {"@id": resource_uri(base_uri, relation.target)}
            existing = resource.setdefault(oslc_property, [])
            assert isinstance(existing, list)
            if target not in existing:
                existing.append(target)

        resources.append(resource)
    return resources
