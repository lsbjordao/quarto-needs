from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping

from .oslc_rm import ExternalResourceIdentity
from .snapshot import AnalysisSnapshot, freeze_json, thaw_json

ReconciliationStatus = Literal[
    "matched",
    "unbound",
    "missing-local",
    "duplicate-local-binding",
    "rejected-external",
    "stale-external",
]


@dataclass(frozen=True, slots=True)
class ExternalRequirementObservation:
    """A normalized remote requirement that remains outside the canonical graph."""

    identity: ExternalResourceIdentity
    title: str
    description: str = ""
    external_identifier: str | None = None
    attributes: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.title, str):
            raise ValueError("title must be a string")
        if not isinstance(self.description, str):
            raise ValueError("description must be a string")
        if self.external_identifier is not None and (
            not isinstance(self.external_identifier, str)
            or not self.external_identifier.strip()
        ):
            raise ValueError("external_identifier must be a non-empty string when present")
        frozen = freeze_json(dict(self.attributes))
        if not isinstance(frozen, Mapping):
            raise TypeError("attributes must be a JSON object")
        object.__setattr__(self, "attributes", frozen)

    def to_dict(self) -> dict[str, object]:
        return {
            "identity": self.identity.to_dict(),
            "title": self.title,
            "description": self.description,
            "externalIdentifier": self.external_identifier,
            "attributes": thaw_json(self.attributes),
        }


@dataclass(frozen=True, slots=True)
class ReconciliationItem:
    external_uri: str
    status: ReconciliationStatus
    canonical_id: str | None
    external_identifier: str | None
    differences: Mapping[str, Mapping[str, object]] = MappingProxyType({})
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "externalUri": self.external_uri,
            "status": self.status,
            "canonicalId": self.canonical_id,
            "externalIdentifier": self.external_identifier,
            "differences": {
                key: dict(value) for key, value in sorted(self.differences.items())
            },
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ReconciliationPlan:
    items: tuple[ReconciliationItem, ...]

    @property
    def has_conflicts(self) -> bool:
        return any(
            item.status
            in {
                "missing-local",
                "duplicate-local-binding",
                "rejected-external",
                "stale-external",
            }
            for item in self.items
        )

    @property
    def unbound_count(self) -> int:
        return sum(item.status == "unbound" for item in self.items)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "oslc-reconciliation-v1",
            "hasConflicts": self.has_conflicts,
            "unboundCount": self.unbound_count,
            "items": [item.to_dict() for item in self.items],
        }


def _field_differences(local, external: ExternalRequirementObservation) -> Mapping[str, Mapping[str, object]]:
    differences: dict[str, Mapping[str, object]] = {}
    if local.title != external.title:
        differences["title"] = MappingProxyType(
            {"local": local.title, "external": external.title}
        )
    if local.body != external.description:
        differences["body"] = MappingProxyType(
            {"local": local.body, "external": external.description}
        )
    if (
        external.external_identifier is not None
        and external.external_identifier != local.id
    ):
        differences["identifier"] = MappingProxyType(
            {"local": local.id, "external": external.external_identifier}
        )
    return MappingProxyType(differences)


def reconcile_external_requirements(
    snapshot: AnalysisSnapshot,
    observations: tuple[ExternalRequirementObservation, ...],
    *,
    bindings: Mapping[str, str],
) -> ReconciliationPlan:
    """Compare remote observations with local objects without mutating either side.

    ``bindings`` is the sole identity bridge. An OSLC ``dcterms:identifier`` or a
    matching title is never treated as authority for automatic identity merge.
    This keeps reconciliation reviewable and prevents accidental aliasing when
    external providers reuse identifiers or expose mutable display fields.
    """

    by_uri: dict[str, ExternalRequirementObservation] = {}
    for observation in observations:
        uri = observation.identity.resource_uri
        if uri in by_uri:
            raise ValueError(f"duplicate external requirement URI: {uri}")
        by_uri[uri] = observation

    unknown_bindings = sorted(set(bindings) - set(by_uri))
    if unknown_bindings:
        raise ValueError(
            "bindings reference unobserved external URIs: "
            + ", ".join(unknown_bindings)
        )

    reverse: dict[str, list[str]] = {}
    for uri, canonical_id in bindings.items():
        if not isinstance(canonical_id, str) or not canonical_id.strip():
            raise ValueError(f"binding for {uri} must target a non-empty canonical ID")
        reverse.setdefault(canonical_id, []).append(uri)
    duplicate_targets = {
        canonical_id
        for canonical_id, uris in reverse.items()
        if len(uris) > 1
    }

    items: list[ReconciliationItem] = []
    for uri in sorted(by_uri):
        observation = by_uri[uri]
        canonical_id = bindings.get(uri)

        if observation.identity.trust_state == "rejected":
            items.append(
                ReconciliationItem(
                    external_uri=uri,
                    status="rejected-external",
                    canonical_id=canonical_id,
                    external_identifier=observation.external_identifier,
                    message="external observation is explicitly rejected and cannot be reconciled",
                )
            )
            continue
        if observation.identity.trust_state == "stale":
            items.append(
                ReconciliationItem(
                    external_uri=uri,
                    status="stale-external",
                    canonical_id=canonical_id,
                    external_identifier=observation.external_identifier,
                    message="external observation is stale; refresh before reconciliation",
                )
            )
            continue
        if canonical_id is None:
            items.append(
                ReconciliationItem(
                    external_uri=uri,
                    status="unbound",
                    canonical_id=None,
                    external_identifier=observation.external_identifier,
                    message="no explicit external-URI to canonical-ID binding exists",
                )
            )
            continue
        if canonical_id in duplicate_targets:
            items.append(
                ReconciliationItem(
                    external_uri=uri,
                    status="duplicate-local-binding",
                    canonical_id=canonical_id,
                    external_identifier=observation.external_identifier,
                    message="multiple external resources are bound to the same canonical object",
                )
            )
            continue

        local = snapshot.objects_by_id.get(canonical_id)
        if local is None:
            items.append(
                ReconciliationItem(
                    external_uri=uri,
                    status="missing-local",
                    canonical_id=canonical_id,
                    external_identifier=observation.external_identifier,
                    message="explicit binding targets a canonical ID that is not present",
                )
            )
            continue

        items.append(
            ReconciliationItem(
                external_uri=uri,
                status="matched",
                canonical_id=canonical_id,
                external_identifier=observation.external_identifier,
                differences=_field_differences(local, observation),
                message="explicit binding resolved; differences are informational only",
            )
        )

    return ReconciliationPlan(items=tuple(items))
