from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

from .model import EngineeringObject, Relation


@dataclass
class RequirementsGraph:
    objects: dict[str, EngineeringObject]
    outgoing: dict[str, list[Relation]]
    incoming: dict[str, list[Relation]]

    @classmethod
    def build(cls, objects: list[EngineeringObject]) -> "RequirementsGraph":
        by_id = {obj.id: obj for obj in objects}
        outgoing: dict[str, list[Relation]] = defaultdict(list)
        incoming: dict[str, list[Relation]] = defaultdict(list)
        for obj in objects:
            for rel in obj.relations:
                outgoing[rel.source].append(rel)
                incoming[rel.target].append(rel)
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
