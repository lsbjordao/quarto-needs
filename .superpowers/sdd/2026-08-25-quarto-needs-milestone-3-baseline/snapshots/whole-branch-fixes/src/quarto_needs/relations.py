from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

ImpactDirection = Literal["source_to_target", "target_to_source", "both", "none"]


@dataclass(frozen=True, slots=True)
class RelationKind:
    authored_name: str
    catalog_name: str
    v1_name: str
    semantic_family: str
    direct_label: str
    inverse_label: str
    source_role: str
    target_role: str
    impact_direction: ImpactDirection
    public: bool = True
    allowed_source_types: tuple[str, ...] = ()
    allowed_target_types: tuple[str, ...] = ()
    minimum_per_source: int | None = None
    maximum_per_source: int | None = None


@dataclass(frozen=True, slots=True)
class RelationCatalog:
    version: str
    entries: Mapping[str, RelationKind]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))

    @classmethod
    def create(cls, version: str, entries: tuple[RelationKind, ...]) -> "RelationCatalog":
        by_name = {entry.authored_name: entry for entry in entries}
        if len(by_name) != len(entries):
            raise ValueError("Relation catalog contains duplicate authored names")
        return cls(version=version, entries=MappingProxyType(by_name))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.entries))

    def resolve(self, authored_name: str) -> RelationKind:
        try:
            return self.entries[authored_name]
        except KeyError as error:
            raise ValueError(f"Unknown relation type: {authored_name}") from error


DEFAULT_RELATION_CATALOG = RelationCatalog.create(
    "1",
    (
        RelationKind("derives-from", "derives-from", "derives-from", "derivation", "Derives from", "Source for", "derived", "source", "target_to_source"),
        RelationKind("derived-from", "derives-from", "derives-from", "derivation", "Derives from", "Source for", "derived", "source", "target_to_source"),
        RelationKind("refines", "refines", "refines", "refinement", "Refines", "Refined by", "refinement", "subject", "target_to_source"),
        RelationKind("decomposes", "decomposes", "decomposes", "decomposition", "Decomposes", "Part of", "whole", "part", "none"),
        RelationKind("depends-on", "depends-on", "depends-on", "dependency", "Depends on", "Depended on by", "dependent", "dependency", "target_to_source"),
        RelationKind("conflicts-with", "conflicts-with", "conflicts-with", "conflict", "Conflicts with", "Conflicts with", "subject", "subject", "both"),
        RelationKind("constrains", "constrains", "constrains", "constraint", "Constrains", "Constrained by", "constraint", "subject", "none"),
        RelationKind("implements", "implements", "implements", "implementation", "Implements", "Implemented by", "implementation-artifact", "requirement", "target_to_source"),
        RelationKind("implemented-by", "implemented-by", "implemented-by", "implementation", "Implemented by", "Implements", "requirement", "implementation-artifact", "source_to_target"),
        RelationKind("verifies", "verifies", "verifies", "verification", "Verifies", "Verified by", "test", "requirement", "target_to_source"),
        RelationKind("verified-by", "verified-by", "verified-by", "verification", "Verified by", "Verifies", "requirement", "test", "source_to_target"),
        RelationKind("validated-by", "validated-by", "validated-by", "verification", "Validated by", "Validates", "requirement", "test", "source_to_target"),
        RelationKind("mitigates", "mitigates", "mitigates", "mitigation", "Mitigates", "Mitigated by", "mitigation", "risk", "target_to_source"),
        RelationKind("justified-by", "justified-by", "justified-by", "justification", "Justified by", "Justifies", "subject", "justification", "none"),
        RelationKind("evidences", "evidences", "evidences", "evidence", "Evidences", "Evidenced by", "evidence", "test", "target_to_source"),
        RelationKind("evidenced-by", "evidenced-by", "evidenced-by", "evidence", "Evidenced by", "Evidences", "test", "evidence", "source_to_target"),
        RelationKind("references", "references", "references", "reference", "References", "Referenced by", "source", "target", "none"),
    ),
)
