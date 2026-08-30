from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping
from urllib.parse import quote, urlparse

from .snapshot import AnalysisSnapshot, ResolvedRelation, thaw_json

OSLC_CORE_NS = "http://open-services.net/ns/core#"
OSLC_RM_NS = "http://open-services.net/ns/rm#"
DCTERMS_NS = "http://purl.org/dc/terms/"
QN_OSLC_NS = "urn:quarto-needs:oslc:v1:"

OSLC_REQUIREMENT = f"{OSLC_RM_NS}Requirement"
OSLC_REQUIREMENT_COLLECTION = f"{OSLC_RM_NS}RequirementCollection"

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
        if self.trust_state not in {"trusted", "unverified", "stale", "rejected"}:
            raise ValueError(f"unsupported OSLC trust state: {self.trust_state}")


def _require_absolute_http_uri(value: str, field: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{field} must be an absolute http(s) URI")


def content_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def is_requirement_type(type_name: str) -> bool:
    return type_name == "requirement" or type_name.endswith("-requirement")


def resource_uri(base_uri: str, canonical_id: str) -> str:
    _require_absolute_http_uri(base_uri, "base_uri")
    return base_uri.rstrip("/") + "/resource/" + quote(canonical_id, safe="")


def _relation_projection(
    relation: ResolvedRelation,
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
