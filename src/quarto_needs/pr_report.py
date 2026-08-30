"""Pull-request engineering report composed from canonical change analyses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from . import diff as diff_module
from . import impact as impact_module
from . import suspect as suspect_module
from .config import NeedsConfig
from .snapshot import AnalysisSnapshot

SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class PullRequestReport:
    changed: Mapping[str, tuple[str, ...]]
    affected: Mapping[str, tuple[str, ...]]
    stale_evidence: tuple[str, ...]
    findings_added: tuple[Mapping[str, object], ...]
    findings_removed: tuple[Mapping[str, object], ...]
    gate_regressions: tuple[Mapping[str, object], ...]
    impact_paths: tuple[Mapping[str, object], ...]
    suspect_claims: tuple[Mapping[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "changed": {key: list(value) for key, value in self.changed.items()},
            "affected": {key: list(value) for key, value in self.affected.items()},
            "staleEvidence": list(self.stale_evidence),
            "findings": {
                "added": [dict(item) for item in self.findings_added],
                "removed": [dict(item) for item in self.findings_removed],
            },
            "gates": {"regressed": [dict(item) for item in self.gate_regressions]},
            "impactPaths": [dict(item) for item in self.impact_paths],
            "suspectClaims": [dict(item) for item in self.suspect_claims],
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
) -> tuple[str | None, str | None]:
    record = snapshot.objects_by_id.get(object_id)
    if record is not None:
        return record.type, config.type_roles.get(record.type)
    stored = baseline_objects.get(object_id)
    if stored is None:
        return None, None
    object_type = str(stored.get("type")) if stored.get("type") is not None else None
    return object_type, config.type_roles.get(object_type) if object_type else None


def _ids_by_role(
    object_ids: set[str],
    *,
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    baseline_objects: Mapping[str, Mapping[str, object]],
) -> dict[str, tuple[str, ...]]:
    buckets: dict[str, list[str]] = {
        "requirements": [],
        "decisions": [],
        "architectureElements": [],
        "sourceModules": [],
        "tests": [],
        "evidence": [],
        "other": [],
    }
    role_bucket = {
        "requirement": "requirements",
        "decision": "decisions",
        "architecture-element": "architectureElements",
        "implementation-artifact": "sourceModules",
        "verification": "tests",
        "evidence": "evidence",
    }
    for object_id in sorted(object_ids, key=lambda value: (value.casefold(), value)):
        _, role = _type_and_role(object_id, snapshot, config, baseline_objects)
        buckets[role_bucket.get(role, "other")].append(object_id)
    return {key: tuple(values) for key, values in buckets.items()}


def analyze(
    baseline_payload: Mapping[str, object],
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    recompute: bool = False,
) -> PullRequestReport:
    diff = diff_module.compare(baseline_payload, snapshot, config, recompute=recompute)
    impact = impact_module.analyze(baseline_payload, snapshot, config, recompute=recompute)
    suspect = suspect_module.analyze(baseline_payload, snapshot, config, recompute=recompute)
    baseline_objects = _baseline_objects(baseline_payload)

    changed_ids = set(diff.added_objects) | set(diff.removed_objects)
    changed_ids.update(str(item["id"]) for item in diff.modified)
    changed_ids.update(str(item["id"]) for item in diff.relocated)
    changed_ids.update(str(item["source"]) for item in diff.added_relations)
    changed_ids.update(str(item["source"]) for item in diff.removed_relations)

    affected_ids = {str(item["id"]) for item in impact.impacted}
    stale_evidence = tuple(
        sorted(
            {
                str(claim["id"])
                for claim in suspect.claims
                if claim.get("role") == "evidence"
            },
            key=lambda value: (value.casefold(), value),
        )
    )

    impact_paths = tuple(
        {
            "origin": str(item["origin"]),
            "target": str(item["id"]),
            "classification": str(item["classification"]),
            "distance": int(item["distance"]),
            "relations": list(item.get("relations", [])),
            "path": list(item.get("path", [])),
        }
        for item in impact.impacted
    )
    return PullRequestReport(
        changed=_ids_by_role(
            changed_ids,
            snapshot=snapshot,
            config=config,
            baseline_objects=baseline_objects,
        ),
        affected=_ids_by_role(
            affected_ids,
            snapshot=snapshot,
            config=config,
            baseline_objects=baseline_objects,
        ),
        stale_evidence=stale_evidence,
        findings_added=diff.findings_added,
        findings_removed=diff.findings_removed,
        gate_regressions=diff.gate_regressions,
        impact_paths=impact_paths,
        suspect_claims=suspect.claims,
    )


def render_markdown(report: PullRequestReport) -> str:
    """Render a stable GitHub-step-summary/PR-friendly Markdown projection."""
    lines = ["# Quarto-Needs engineering change report", ""]
    lines.append("## Changed engineering objects")
    for label, ids in report.changed.items():
        if ids:
            lines.append(f"- **{label}**: {', '.join(ids)}")
    if not any(report.changed.values()):
        lines.append("- No engineering objects changed.")

    lines.extend(["", "## Affected engineering objects"])
    for label, ids in report.affected.items():
        if ids:
            lines.append(f"- **{label}**: {', '.join(ids)}")
    if not any(report.affected.values()):
        lines.append("- No downstream engineering objects are affected.")

    lines.extend(["", "## Review attention"])
    lines.append(
        f"- Suspect traceability claims: {len(report.suspect_claims)}"
    )
    lines.append(
        "- Stale/suspect evidence: "
        + (", ".join(report.stale_evidence) if report.stale_evidence else "none")
    )
    lines.append(f"- New findings: {len(report.findings_added)}")
    lines.append(f"- Removed findings: {len(report.findings_removed)}")
    lines.append(f"- Gate regressions: {len(report.gate_regressions)}")

    lines.extend(["", "## Impact paths"])
    if not report.impact_paths:
        lines.append("- No impact paths.")
    for item in report.impact_paths:
        path = " → ".join(str(value) for value in item["path"])
        relations = ", ".join(str(value) for value in item["relations"])
        lines.append(
            f"- `{item['origin']}` → `{item['target']}` "
            f"({item['classification']}, d={item['distance']}): {path} [{relations}]"
        )
    return "\n".join(lines) + "\n"
