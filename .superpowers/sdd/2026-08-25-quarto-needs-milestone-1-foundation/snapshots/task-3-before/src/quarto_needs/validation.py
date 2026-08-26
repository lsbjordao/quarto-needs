from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

from .graph import RequirementsGraph
from .model import EngineeringObject


@dataclass(slots=True)
class Finding:
    code: str
    severity: str
    message: str
    object_id: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "object_id": self.object_id,
        }


def validate(objects: list[EngineeringObject], require_rationale_for: set[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    counts = Counter(o.id for o in objects)
    for need_id, count in counts.items():
        if count > 1:
            findings.append(Finding("REQ004", "error", f"Duplicate ID: {need_id}", need_id))

    graph = RequirementsGraph.build(objects)
    known = set(graph.objects)
    for obj in objects:
        for rel in obj.relations:
            if rel.target not in known:
                findings.append(Finding(
                    "REQ005", "error",
                    f"{obj.id} references unknown object {rel.target} via {rel.type}",
                    obj.id,
                ))

    require_rationale_for = require_rationale_for or {"system-requirement", "software-requirement"}
    for obj in objects:
        if obj.type in require_rationale_for and not obj.rationale and "### Rationale" not in obj.body:
            findings.append(Finding("REQ002", "warning", f"{obj.id} has no rationale", obj.id))
        if obj.status == "approved" and obj.type.endswith("requirement"):
            has_verification = any(r.type in {"verified-by", "validated-by"} for r in obj.relations)
            if not has_verification:
                findings.append(Finding("REQ006", "warning", f"{obj.id} is approved but has no verification relation", obj.id))
    return findings
