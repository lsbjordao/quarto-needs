"""Union-graph impact traversal with explicit, auditable paths.

The traversal runs over the union of the baseline and current graphs so a
removed node or edge remains explainable. There is deliberately no risk score:
the output is the path that produced each result.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Mapping, Sequence

from . import diff as diff_module
from .config import NeedsConfig
from .snapshot import AnalysisSnapshot

SCHEMA_VERSION = "1"
MAX_DISTANCE = 10


class ImpactError(Exception):
    """The two graphs cannot be traversed together."""


@dataclass(frozen=True, slots=True)
class ImpactReport:
    origins: tuple[Mapping[str, object], ...]
    impacted: tuple[Mapping[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "origins": [dict(item) for item in self.origins],
            "impacted": [dict(item) for item in self.impacted],
        }


def _union_edges(
    baseline_relations: Sequence[Mapping[str, object]], snapshot: AnalysisSnapshot
) -> dict[str, list[tuple[str, str]]]:
    """Adjacency keyed by source, following each relation's impact direction.

    `both` yields an edge in each direction; `none` yields none at all.
    """
    adjacency: dict[str, list[tuple[str, str]]] = {}

    def add(source: str, target: str, name: str, direction: str) -> None:
        if direction in {"source_to_target", "both"}:
            adjacency.setdefault(source, []).append((target, name))
        if direction in {"target_to_source", "both"}:
            adjacency.setdefault(target, []).append((source, name))

    for item in baseline_relations:
        add(
            str(item["source"]),
            str(item["target"]),
            str(item["authoredName"]),
            str(item.get("impactDirection", "none")),
        )
    for record in snapshot.relations:
        add(record.source, record.target, record.authored_name, record.impact_direction)

    for key in adjacency:
        adjacency[key] = sorted(set(adjacency[key]))
    return adjacency


def _origins(report: diff_module.DiffReport) -> tuple[dict[str, object], ...]:
    origins: list[dict[str, object]] = []
    for object_id in report.added_objects:
        origins.append({"id": object_id, "change": "added"})
    for object_id in report.removed_objects:
        origins.append({"id": object_id, "change": "removed"})
    for item in report.modified:
        origins.append({"id": str(item["id"]), "change": "modified", "fields": list(item["fields"])})
    for item in report.added_relations:
        origins.append({"id": str(item["source"]), "change": "relation-added"})
    for item in report.removed_relations:
        origins.append({"id": str(item["source"]), "change": "relation-removed"})
    seen: dict[str, dict[str, object]] = {}
    for origin in origins:
        seen.setdefault(str(origin["id"]), origin)
    return tuple(seen[key] for key in sorted(seen, key=lambda item: (item.casefold(), item)))


def _priority(
    object_id: str, snapshot: AnalysisSnapshot, baseline_objects: Mapping[str, Mapping[str, object]]
) -> str | None:
    record = snapshot.objects_by_id.get(object_id)
    if record is not None:
        return record.priority
    stored = baseline_objects.get(object_id)
    if stored is None:
        return None
    attributes = stored.get("attributes") or {}
    value = attributes.get("priority")
    return str(value) if value not in (None, "") else None


def analyze(
    baseline_payload: Mapping[str, object],
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    recompute: bool = False,
) -> ImpactReport:
    if not baseline_payload.get("valid", False):
        raise ImpactError(
            "This baseline is a diagnostic artifact (valid: false) and cannot be traversed"
        )
    if not recompute and str(
        baseline_payload.get("configurationFingerprint", "")
    ) != snapshot.configuration_fingerprint:
        raise ImpactError(
            "The baseline was produced under a different configuration; "
            "pass --recompute-with current so one relation policy governs the traversal"
        )

    report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
    origins = _origins(report)
    adjacency = _union_edges(baseline_payload.get("relations", []), snapshot)
    baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
    origin_ids = {str(item["id"]) for item in origins}

    impacted: dict[tuple[str, str], dict[str, object]] = {}
    for origin in origins:
        start = str(origin["id"])
        queue: deque[tuple[str, tuple[str, ...], tuple[str, ...]]] = deque([(start, (start,), ())])
        visited = {start}
        while queue:
            current, path, relations = queue.popleft()
            distance = len(path) - 1
            if distance >= MAX_DISTANCE:
                continue
            for neighbor, relation_name in adjacency.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                next_path = path + (neighbor,)
                next_relations = relations + (relation_name,)
                key = (start, neighbor)
                if neighbor not in origin_ids and key not in impacted:
                    impacted[key] = {
                        "id": neighbor,
                        "origin": start,
                        "change": origin["change"],
                        "classification": "direct" if len(next_path) == 2 else "transitive",
                        "distance": len(next_path) - 1,
                        "relations": list(next_relations),
                        "path": list(next_path),
                        "priority": _priority(neighbor, snapshot, baseline_objects),
                    }
                queue.append((neighbor, next_path, next_relations))

    ordered = tuple(
        impacted[key]
        for key in sorted(impacted, key=lambda item: (item[0].casefold(), item[0], item[1].casefold(), item[1]))
    )
    return ImpactReport(origins=origins, impacted=ordered)
