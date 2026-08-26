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
        data = asdict(self)
        return data

    @property
    def href(self) -> str:
        if not self.source:
            return f"#{self.id}"
        file = Path(self.source.file)
        stem = file.with_suffix("").as_posix()
        return f"{stem}.html#{self.id}"
