"""Legacy in-memory graph over ``EngineeringObject`` DTOs.

Kept as a compatibility/test surface: tests construct legacy objects and
exercise traversal ordering against it. The canonical analyzer builds its
own indexed immutable graph on ``AnalysisSnapshot`` (see ``snapshot.py``);
this class never participates in project analysis."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .model import EngineeringObject, Relation
from .model import SourceLocation


class DuplicateIdError(ValueError):
    def __init__(self, duplicate_id: str, locations: tuple[SourceLocation, ...]):
        self.duplicate_id = duplicate_id
        self.locations = locations
        rendered = ", ".join(f"{item.file}:{item.line}" for item in locations) or "unknown locations"
        super().__init__(f"Duplicate ID {duplicate_id}: {rendered}")


@dataclass
class RequirementsGraph:
    objects: dict[str, EngineeringObject]
    outgoing: dict[str, list[Relation]]
    incoming: dict[str, list[Relation]]

    @classmethod
    def build(cls, objects: list[EngineeringObject]) -> "RequirementsGraph":
        declarations_by_id: dict[str, list[EngineeringObject]] = defaultdict(list)
        for obj in objects:
            declarations_by_id[obj.id].append(obj)

        duplicate_ids = [
            object_id
            for object_id, declarations in declarations_by_id.items()
            if len(declarations) > 1
        ]
        if duplicate_ids:
            duplicate_id = min(duplicate_ids, key=lambda item: (item.casefold(), item))
            locations = tuple(sorted(
                (obj.source for obj in declarations_by_id[duplicate_id] if obj.source is not None),
                key=lambda item: (
                    item.file.casefold(),
                    item.file,
                    item.line,
                    item.anchor or "",
                ),
            ))
            raise DuplicateIdError(duplicate_id, locations)

        by_id = {obj.id: obj for obj in objects}
        outgoing: dict[str, list[Relation]] = defaultdict(list)
        incoming: dict[str, list[Relation]] = defaultdict(list)
        for obj in objects:
            for rel in obj.relations:
                outgoing[rel.source].append(rel)
                incoming[rel.target].append(rel)
        for relations in outgoing.values():
            relations.sort(
                key=lambda item: (
                    item.type,
                    item.target.casefold(),
                    item.target,
                    item.source.casefold(),
                    item.source,
                )
            )
        for relations in incoming.values():
            relations.sort(
                key=lambda item: (
                    item.type,
                    item.source.casefold(),
                    item.source,
                    item.target.casefold(),
                    item.target,
                )
            )
        return cls(by_id, dict(outgoing), dict(incoming))

    def downstream(self, start: str) -> set[str]:
        seen: set[str] = set()
        q = deque([start])
        while q:
            node = q.popleft()
            for rel in self.outgoing.get(node, []):
                if rel.target not in seen:
                    seen.add(rel.target)
                    q.append(rel.target)
        seen.discard(start)
        return seen

    def upstream(self, start: str) -> set[str]:
        seen: set[str] = set()
        q = deque([start])
        while q:
            node = q.popleft()
            for rel in self.incoming.get(node, []):
                if rel.source not in seen:
                    seen.add(rel.source)
                    q.append(rel.source)
        seen.discard(start)
        return seen
