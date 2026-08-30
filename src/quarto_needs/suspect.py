"""Explainable suspect traceability derived from semantic change impact.

Suspect state is deliberately not persisted into authored engineering objects.
It is recomputed from two engineering states, and every claim carries the path
that makes re-review necessary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from . import impact as impact_module
from .config import NeedsConfig
from .snapshot import AnalysisSnapshot

SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class SuspectReport:
    origins: tuple[Mapping[str, object], ...]
    claims: tuple[Mapping[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "origins": [dict(item) for item in self.origins],
            "claims": [dict(item) for item in self.claims],
        }


def _baseline_objects(payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    return {
        str(item["id"]): item
        for item in payload.get("objects", [])
        if isinstance(item, Mapping) and "id" in item
    }


def _type_and_role(
    object_id: str,
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    baseline_objects: Mapping[str, Mapping[str, object]],
) -> tuple[str | None, str | None, str]:
    current = snapshot.objects_by_id.get(object_id)
    if current is not None:
        object_type = current.type
        role = config.type_roles.get(object_type)
        return object_type, role, "current"
    stored = baseline_objects.get(object_id)
    if stored is None:
        return None, None, "unknown"
    object_type = str(stored.get("type")) if stored.get("type") is not None else None
    role = config.type_roles.get(object_type) if object_type is not None else None
    return object_type, role, "baseline"


def _witness(path: list[str], relations: list[str]) -> str:
    if not path:
        return ""
    pieces = [path[0]]
    for relation, target in zip(relations, path[1:]):
        pieces.append(f"--{relation}--> {target}")
    return " ".join(pieces)


def analyze(
    baseline_payload: Mapping[str, object],
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    recompute: bool = False,
) -> SuspectReport:
    """Derive re-review claims from the canonical union-graph impact report."""
    impact = impact_module.analyze(
        baseline_payload,
        snapshot,
        config,
        recompute=recompute,
    )
    baseline_objects = _baseline_objects(baseline_payload)
    claims: list[dict[str, object]] = []
    for item in impact.impacted:
        target_id = str(item["id"])
        object_type, role, source_state = _type_and_role(
            target_id,
            snapshot,
            config,
            baseline_objects,
        )
        path = [str(value) for value in item.get("path", [])]
        relations = [str(value) for value in item.get("relations", [])]
        claims.append(
            {
                "id": target_id,
                "state": "suspect",
                "origin": str(item["origin"]),
                "originChange": str(item["change"]),
                "classification": str(item["classification"]),
                "distance": int(item["distance"]),
                "type": object_type,
                "role": role,
                "sourceState": source_state,
                "relations": relations,
                "path": path,
                "witness": _witness(path, relations),
                "reason": "reachable-from-changed-engineering-object",
            }
        )
    ordered = tuple(
        sorted(
            claims,
            key=lambda item: (
                str(item["origin"]).casefold(),
                str(item["origin"]),
                int(item["distance"]),
                str(item["id"]).casefold(),
                str(item["id"]),
            ),
        )
    )
    return SuspectReport(origins=impact.origins, claims=ordered)
