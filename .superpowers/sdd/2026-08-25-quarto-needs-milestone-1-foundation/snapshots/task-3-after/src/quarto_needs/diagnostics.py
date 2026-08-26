from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .snapshot import LocationRecord, freeze_json, thaw_json


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: str
    message: str
    object_id: str | None = None
    location: LocationRecord | None = None
    properties: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "properties", freeze_json(dict(self.properties)))

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "object_id": self.object_id,
        }
        if self.location is not None:
            result["location"] = {
                "file": self.location.file,
                "line": self.location.line,
                "anchor": self.location.anchor,
            }
        if self.properties:
            result["properties"] = thaw_json(self.properties)
        return result
