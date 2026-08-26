from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


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
