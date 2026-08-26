from __future__ import annotations

import json
from pathlib import Path

from .graph import RequirementsGraph
from .model import EngineeringObject
from .validation import Finding


def coverage(objects: list[EngineeringObject]) -> dict[str, object]:
    requirements = [o for o in objects if o.type.endswith("requirement")]
    implemented = [o for o in requirements if any(r.type in {"implements", "implemented-by"} for r in o.relations)]
    verified = [o for o in requirements if any(r.type in {"verified-by", "validated-by"} for r in o.relations)]
    approved = [o for o in requirements if o.status == "approved"]
    total = len(requirements)
    return {
        "requirements": total,
        "approved": len(approved),
        "implemented": len(implemented),
        "verified": len(verified),
        "implementation_coverage": round(100 * len(implemented) / total, 1) if total else 100.0,
        "verification_coverage": round(100 * len(verified) / total, 1) if total else 100.0,
    }


def export_graph(path: Path, objects: list[EngineeringObject], findings: list[Finding]) -> None:
    graph = RequirementsGraph.build(objects)
    payload = {
        "schemaVersion": "1",
        "objects": [o.to_dict() | {"href": o.href} for o in objects],
        "relations": [r.__dict__ if hasattr(r, "__dict__") else {"type": r.type, "source": r.source, "target": r.target, "attributes": r.attributes}
                      for o in objects for r in o.relations],
        "coverage": coverage(objects),
        "validation": [f.to_dict() for f in findings],
        "backlinks": {
            obj_id: [
                {"source": r.source, "type": r.type}
                for r in graph.incoming.get(obj_id, [])
            ]
            for obj_id in graph.objects
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def export_lua_index(path: Path, objects: list[EngineeringObject]) -> None:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')
    lines = ["return {"]
    for o in objects:
        lines.append(f'  ["{esc(o.id)}"] = {{ title = "{esc(o.title)}", href = "{esc(o.href)}", type = "{esc(o.type)}", status = "{esc(o.status)}" }},')
    lines.append("}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
