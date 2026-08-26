from __future__ import annotations

from collections import Counter

from .diagnostics import Finding
from .model import EngineeringObject, SourceLocation
from .snapshot import LocationRecord


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _location_record(source: SourceLocation | None) -> LocationRecord | None:
    if source is None:
        return None
    return LocationRecord(source.file, source.line, source.anchor)


def finding_key(item: Finding) -> tuple[object, ...]:
    location = item.location
    return (
        SEVERITY_ORDER.get(item.severity, 99),
        item.code,
        (item.object_id or "").casefold(),
        item.object_id or "",
        location.file.casefold() if location else "",
        location.file if location else "",
        location.line if location else 0,
        item.message,
    )


def validate(objects: list[EngineeringObject], require_rationale_for: set[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    counts = Counter(o.id for o in objects)
    known_ids = set(counts)
    for need_id, count in counts.items():
        if count > 1:
            source = next(obj.source for obj in objects if obj.id == need_id)
            findings.append(Finding(
                "REQ004",
                "error",
                f"Duplicate ID: {need_id}",
                need_id,
                _location_record(source),
            ))

    for obj in objects:
        for rel in obj.relations:
            if rel.target not in known_ids:
                findings.append(Finding(
                    "REQ005", "error",
                    f"{obj.id} references unknown object {rel.target} via {rel.type}",
                    obj.id,
                    _location_record(obj.source),
                ))

    require_rationale_for = require_rationale_for or {"system-requirement", "software-requirement"}
    for obj in objects:
        if obj.type in require_rationale_for and not obj.rationale and "### Rationale" not in obj.body:
            findings.append(Finding("REQ002", "warning", f"{obj.id} has no rationale", obj.id))
        if obj.status == "approved" and obj.type.endswith("requirement"):
            has_verification = any(r.type in {"verified-by", "validated-by"} for r in obj.relations)
            if not has_verification:
                findings.append(Finding("REQ006", "warning", f"{obj.id} is approved but has no verification relation", obj.id))
    return sorted(findings, key=finding_key)
