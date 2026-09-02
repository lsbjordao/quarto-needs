from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .snapshot import ObjectDeclaration, RelationToken, to_location_record


@dataclass(slots=True)
class SourceLocation:
    file: str
    line: int
    anchor: str | None = None


@dataclass(slots=True)
class Relation:
    type: str
    source: str
    target: str
    attributes: dict[str, Any] = field(default_factory=dict)
    authored_name: str | None = None


def relation_to_v1_dict(relation: Relation) -> dict[str, Any]:
    return {
        "type": relation.type,
        "source": relation.source,
        "target": relation.target,
        "attributes": relation.attributes,
    }


@dataclass(slots=True)
class EngineeringObject:
    id: str
    type: str
    title: str
    status: str = "draft"
    body: str = ""
    rationale: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    source: SourceLocation | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "body": self.body,
            "rationale": self.rationale,
            "attributes": self.attributes,
            "relations": [relation_to_v1_dict(relation) for relation in self.relations],
            "source": asdict(self.source) if self.source else None,
        }

    @property
    def href(self) -> str:
        if not self.source:
            return f"#{self.id}"
        file = Path(self.source.file)
        stem = file.with_suffix("").as_posix()
        return f"{stem}.html#{self.id}"


def to_declaration(item: EngineeringObject) -> ObjectDeclaration:
    """Adapt a legacy object into the canonical declaration model.

    This adapter lives in the legacy module on purpose: compatibility types
    may depend on the canonical model, never the reverse. It is the single
    entry point used by the convenience APIs (``analyze_objects``, the
    legacy ``validate`` wrapper) to reach the canonical analyzer.
    """
    location = to_location_record(item.source)
    return ObjectDeclaration(
        id=item.id,
        type=item.type,
        title=item.title,
        status=item.status,
        body=item.body,
        rationale=item.rationale,
        attributes=item.attributes,
        relations=tuple(
            RelationToken(
                relation.authored_name or relation.type,
                relation.target,
                relation.attributes,
                location,
            )
            for relation in item.relations
        ),
        location=location,
    )
