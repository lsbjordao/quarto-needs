from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .diagnostics import Finding
    from .model import SourceLocation

JsonScalar = str | int | float | bool | None


def text_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def freeze_json(value: object) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("JSON numbers must be finite")
        return value
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("JSON object keys must be strings")
        frozen = {
            key: freeze_json(value[key])
            for key in sorted(value, key=lambda item: (item.casefold(), item))
        }
        return MappingProxyType(frozen)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    frozen = freeze_json(dict(value))
    assert isinstance(frozen, Mapping)
    return frozen


@dataclass(frozen=True, slots=True)
class LocationRecord:
    file: str
    line: int
    anchor: str | None = None


def to_location_record(source: SourceLocation | None) -> LocationRecord | None:
    if source is None:
        return None
    return LocationRecord(source.file, source.line, source.anchor)


@dataclass(frozen=True, slots=True)
class RelationToken:
    authored_name: str
    target: str
    attributes: Mapping[str, object]
    location: LocationRecord | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))


@dataclass(frozen=True, slots=True)
class ObjectDeclaration:
    id: str
    type: str
    title: str
    status: str
    body: str
    rationale: str
    attributes: Mapping[str, object]
    relations: tuple[RelationToken, ...]
    location: LocationRecord | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))
        object.__setattr__(self, "relations", tuple(self.relations))


@dataclass(frozen=True, slots=True)
class DeclarationBatch:
    declarations: tuple[ObjectDeclaration, ...]
    findings: tuple[Finding, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "declarations", tuple(self.declarations))
        object.__setattr__(self, "findings", tuple(self.findings))


@dataclass(frozen=True, slots=True)
class ObjectRecord:
    id: str
    type: str
    title: str
    status: str
    body: str
    rationale: str
    attributes: Mapping[str, object]
    locations: tuple[LocationRecord, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))
        object.__setattr__(self, "locations", tuple(self.locations))

    @property
    def priority(self) -> str | None:
        value = self.attributes.get("priority")
        return str(value) if value is not None and str(value) != "" else None

    @property
    def tags(self) -> tuple[str, ...]:
        value = self.attributes.get("tags")
        if isinstance(value, tuple):
            return tuple(
                str(item).strip() for item in value if str(item).strip()
            )
        if value is None:
            return ()
        return tuple(
            item.strip()
            for item in str(value).replace(";", ",").split(",")
            if item.strip()
        )


@dataclass(frozen=True, slots=True)
class RelationRecord:
    source: str
    authored_name: str
    catalog_name: str
    v1_name: str
    target: str
    semantic_family: str
    source_role: str
    target_role: str
    impact_direction: str
    attributes: Mapping[str, object]
    provenance: tuple[LocationRecord, ...]
    traversal_direction: str = "none"

    def __post_init__(self) -> None:
        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))
        object.__setattr__(self, "provenance", tuple(self.provenance))


@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
    objects: tuple[ObjectRecord, ...]
    relations: tuple[RelationRecord, ...]
    findings: tuple[Finding, ...]
    metrics: Mapping[str, object]
    objects_by_id: Mapping[str, ObjectRecord]
    outgoing: Mapping[str, tuple[RelationRecord, ...]]
    incoming: Mapping[str, tuple[RelationRecord, ...]]
    generator_name: str
    generator_version: str
    relation_catalog_version: str
    reference_date: str = ""
    configuration_fingerprint: str = ""
    semantic_graph_fingerprint: str = ""
    representation_fingerprint: str = ""
    derived: Mapping[str, Mapping[str, object]] = MappingProxyType({})
    variants: Mapping[str, tuple[str, ...]] = MappingProxyType({})
    variant_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "objects", tuple(self.objects))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "metrics", _freeze_mapping(self.metrics))
        object.__setattr__(
            self, "objects_by_id", MappingProxyType(dict(self.objects_by_id))
        )
        object.__setattr__(
            self,
            "outgoing",
            MappingProxyType(
                {key: tuple(value) for key, value in self.outgoing.items()}
            ),
        )
        object.__setattr__(
            self,
            "incoming",
            MappingProxyType(
                {key: tuple(value) for key, value in self.incoming.items()}
            ),
        )
        frozen_derived: dict[str, Mapping[str, object]] = {}
        for object_id, values in self.derived.items():
            frozen = freeze_json(dict(values))
            assert isinstance(frozen, Mapping)
            frozen_derived[object_id] = frozen
        object.__setattr__(self, "derived", MappingProxyType(frozen_derived))
        object.__setattr__(
            self,
            "variants",
            MappingProxyType({key: tuple(value) for key, value in self.variants.items()}),
        )


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    declarations: tuple[ObjectDeclaration, ...]
    findings: tuple[Finding, ...]
    snapshot: AnalysisSnapshot | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "declarations", tuple(self.declarations))
        object.__setattr__(self, "findings", tuple(self.findings))

    @property
    def valid(self) -> bool:
        return self.snapshot is not None
