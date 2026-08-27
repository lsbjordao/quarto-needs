# Review package

Snapshot range: `task-1-before` -> `task-1-after`

## Files changed (5)

- `examples/book/.quarto-needs/needs.json`
- `schemas/graph-public-v1.schema.json`
- `src/quarto_needs/graph_projection.py`
- `tests/fixtures/graph/adversarial.qmd`
- `tests/test_graph_projection.py`

## Summary

338 lines added, 1 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/examples/book/.quarto-needs/needs.json .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/examples/book/.quarto-needs/needs.json
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/examples/book/.quarto-needs/needs.json	2026-08-26 23:43:19.137391247 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/examples/book/.quarto-needs/needs.json	2026-08-27 10:06:14.400499164 -0300
@@ -736,21 +736,21 @@
             "passed": true,
             "scope": "project",
             "threshold": 0
           }
         ],
         "generator": {
           "name": "quarto-needs",
           "version": "0.1.0"
         },
         "profile": "strict",
-        "referenceDate": "2026-08-26",
+        "referenceDate": "2026-08-27",
         "schemaVersion": "1",
         "scopes": {
           "approved-high-unverified": {
             "breakdowns": {
               "priority": {},
               "status": {},
               "type": {}
             },
             "coverage": {
               "evidence": {
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/schemas/graph-public-v1.schema.json .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/schemas/graph-public-v1.schema.json
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/schemas/graph-public-v1.schema.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/schemas/graph-public-v1.schema.json	2026-08-27 01:17:12.597802638 -0300
@@ -0,0 +1,77 @@
+{
+  "$schema": "https://json-schema.org/draft/2020-12/schema",
+  "$id": "https://quarto-needs.dev/schema/graph-public-v1.schema.json",
+  "title": "Quarto-Needs public graph projection v1",
+  "type": "object",
+  "additionalProperties": false,
+  "required": ["schemaVersion", "view", "nodes", "edges"],
+  "properties": {
+    "schemaVersion": {"const": "graph-public-v1"},
+    "view": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["id", "mode", "limits"],
+      "properties": {
+        "id": {"type": "string"},
+        "layout": {"type": "string"},
+        "mode": {"enum": ["catalog", "diff", "impact"]},
+        "seed": {"type": "integer"},
+        "limits": {
+          "type": "object",
+          "additionalProperties": false,
+          "required": ["nodes", "edges"],
+          "properties": {"nodes": {"type": "integer"}, "edges": {"type": "integer"}}
+        }
+      }
+    },
+    "nodes": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["id", "title", "type", "status"],
+        "properties": {
+          "id": {"type": "string"},
+          "title": {"type": "string"},
+          "type": {"type": "string"},
+          "status": {"type": "string"},
+          "priority": {"type": ["string", "null"]},
+          "tags": {"type": "array", "items": {"type": "string"}},
+          "href": {"type": "string"},
+          "change": {"enum": ["added", "removed", "modified", "relocated", "unchanged"]}
+        }
+      }
+    },
+    "edges": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["source", "target", "relation", "label"],
+        "properties": {
+          "source": {"type": "string"},
+          "target": {"type": "string"},
+          "relation": {"type": "string"},
+          "label": {"type": "string"},
+          "change": {"enum": ["added", "removed", "unchanged"]},
+          "pathMember": {"type": "boolean"}
+        }
+      }
+    },
+    "impact": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["id", "origin", "distance", "path"],
+        "properties": {
+          "id": {"type": "string"},
+          "origin": {"type": "string"},
+          "classification": {"enum": ["direct", "transitive"]},
+          "distance": {"type": "integer", "minimum": 1},
+          "path": {"type": "array", "items": {"type": "string"}, "minItems": 2}
+        }
+      }
+    }
+  }
+}
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/src/quarto_needs/graph_projection.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/src/quarto_needs/graph_projection.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/src/quarto_needs/graph_projection.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/src/quarto_needs/graph_projection.py	2026-08-27 01:22:33.000879081 -0300
@@ -0,0 +1,158 @@
+"""The reduced projection the browser is allowed to see.
+
+Deny by default: nodes and edges are constructed field by field from an
+allowlist. Nothing is copied wholesale and filtered afterwards, because that
+inverts the default — a field added to `ObjectRecord` later would ship to the
+browser until someone remembered to exclude it.
+"""
+from __future__ import annotations
+
+import json
+from dataclasses import dataclass
+from typing import Iterable, Mapping, Sequence
+
+from .relations import DEFAULT_RELATION_CATALOG
+from .snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord
+
+SCHEMA_VERSION = "graph-public-v1"
+
+PUBLIC_NODE_FIELDS = ("id", "title", "type", "status", "priority", "tags", "href", "change")
+PUBLIC_EDGE_FIELDS = ("source", "target", "relation", "label", "change", "pathMember")
+
+DEFAULT_LIMITS = {"nodes": 100, "edges": 300}
+
+
+@dataclass(frozen=True, slots=True)
+class PublicNode:
+    id: str
+    title: str
+    type: str
+    status: str
+    priority: str | None
+    tags: tuple[str, ...]
+    href: str
+    change: str | None = None
+
+    def to_dict(self) -> dict[str, object]:
+        payload: dict[str, object] = {
+            "id": self.id,
+            "title": self.title,
+            "type": self.type,
+            "status": self.status,
+            "priority": self.priority,
+            "tags": list(self.tags),
+            "href": self.href,
+        }
+        if self.change is not None:
+            payload["change"] = self.change
+        return payload
+
+
+@dataclass(frozen=True, slots=True)
+class PublicEdge:
+    source: str
+    target: str
+    relation: str
+    label: str
+    change: str | None = None
+    path_member: bool | None = None
+
+    def to_dict(self) -> dict[str, object]:
+        payload: dict[str, object] = {
+            "source": self.source,
+            "target": self.target,
+            "relation": self.relation,
+            "label": self.label,
+        }
+        if self.change is not None:
+            payload["change"] = self.change
+        if self.path_member is not None:
+            payload["pathMember"] = self.path_member
+        return payload
+
+
+@dataclass(frozen=True, slots=True)
+class GraphProjection:
+    view_id: str
+    mode: str
+    limits: Mapping[str, int]
+    nodes: tuple[PublicNode, ...]
+    edges: tuple[PublicEdge, ...]
+    impact: tuple[Mapping[str, object], ...] = ()
+
+    def to_dict(self) -> dict[str, object]:
+        payload: dict[str, object] = {
+            "schemaVersion": SCHEMA_VERSION,
+            "view": {
+                "id": self.view_id,
+                "mode": self.mode,
+                "limits": dict(self.limits),
+            },
+            "nodes": [node.to_dict() for node in self.nodes],
+            "edges": [edge.to_dict() for edge in self.edges],
+        }
+        if self.impact:
+            payload["impact"] = [dict(item) for item in self.impact]
+        return payload
+
+
+def _public_href(record: ObjectRecord) -> str:
+    """Anchor-only by default.
+
+    A resolved cross-page href is safe to publish, but it is built by the Lua
+    link resolver at render time, where the output format and current page are
+    known. Emitting a filesystem-derived path here would leak project layout.
+    """
+    return "#" + record.id
+
+
+def _label_for(relation: RelationRecord) -> str:
+    try:
+        return DEFAULT_RELATION_CATALOG.resolve(relation.authored_name).direct_label
+    except ValueError:
+        return relation.authored_name
+
+
+def build_projection(
+    snapshot: AnalysisSnapshot,
+    *,
+    node_ids: Iterable[str],
+    view_id: str,
+    mode: str = "catalog",
+    limits: Mapping[str, int] | None = None,
+) -> GraphProjection:
+    selected = {str(item) for item in node_ids}
+    nodes = tuple(
+        PublicNode(
+            id=record.id,
+            title=record.title,
+            type=record.type,
+            status=record.status,
+            priority=record.priority,
+            tags=record.tags,
+            href=_public_href(record),
+        )
+        for record in snapshot.objects
+        if record.id in selected
+    )
+    edges = tuple(
+        PublicEdge(
+            source=relation.source,
+            target=relation.target,
+            relation=relation.v1_name,
+            label=_label_for(relation),
+        )
+        for relation in snapshot.relations
+        if relation.source in selected and relation.target in selected
+    )
+    return GraphProjection(
+        view_id=view_id,
+        mode=mode,
+        limits=dict(limits or DEFAULT_LIMITS),
+        nodes=nodes,
+        edges=edges,
+    )
+
+
+def render_projection(projection: GraphProjection) -> str:
+    return json.dumps(projection.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/tests/fixtures/graph/adversarial.qmd .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/tests/fixtures/graph/adversarial.qmd
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/tests/fixtures/graph/adversarial.qmd	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/tests/fixtures/graph/adversarial.qmd	2026-08-27 01:16:37.121904898 -0300
@@ -0,0 +1,14 @@
+::: {.need #ADV-1 type=functional-requirement status=approved priority=high tags="public-tag" secret-attribute="LEAKCANARYATTR7f3a"}
+## Publishable title
+
+LEAKCANARYBODY91cd is body prose and must never reach the browser.
+
+### Rationale
+LEAKCANARYRATIONALE4e77 explains why and is equally private.
+:::
+
+::: {.need #ADV-2 type=test-case status=passed tags="public-tag"}
+## Second publishable title
+
+LEAKCANARYBODY2b80 is more private prose.
+:::
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/tests/test_graph_projection.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/tests/test_graph_projection.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-before/tests/test_graph_projection.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/tests/test_graph_projection.py	2026-08-27 01:16:50.473866410 -0300
@@ -0,0 +1,88 @@
+from __future__ import annotations
+
+import json
+from pathlib import Path
+
+import pytest
+from jsonschema import Draft202012Validator
+
+from quarto_needs import graph_projection
+from quarto_needs.analysis import analyze_project
+
+ROOT = Path(__file__).resolve().parents[1]
+FIXTURE = ROOT / "tests" / "fixtures" / "graph" / "adversarial.qmd"
+SCHEMA = ROOT / "schemas" / "graph-public-v1.schema.json"
+
+CANARIES = (
+    "LEAKCANARYATTR7f3a",
+    "LEAKCANARYBODY91cd",
+    "LEAKCANARYRATIONALE4e77",
+    "LEAKCANARYBODY2b80",
+)
+
+
+def projection_of(tmp_path: Path):
+    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
+    result = analyze_project(tmp_path)
+    assert result.snapshot is not None
+    return graph_projection.build_projection(
+        result.snapshot,
+        node_ids=("ADV-1", "ADV-2"),
+        view_id="need-graph-1",
+    )
+
+
+def test_no_denied_value_reaches_the_projection(tmp_path: Path) -> None:
+    """Search the serialized output for denied values, not for field names.
+
+    Enumerating fields only catches leaks through paths someone anticipated. A
+    canary search catches a leak through any path at all, including a future
+    field added without thinking about publication policy.
+    """
+    serialized = graph_projection.render_projection(projection_of(tmp_path))
+
+    for canary in CANARIES:
+        assert canary not in serialized, f"{canary} reached the public projection"
+
+
+def test_projection_validates_against_its_schema(tmp_path: Path) -> None:
+    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
+    Draft202012Validator.check_schema(schema)
+    Draft202012Validator(schema).validate(json.loads(graph_projection.render_projection(projection_of(tmp_path))))
+
+
+def test_only_allowlisted_fields_are_emitted(tmp_path: Path) -> None:
+    payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))
+
+    for node in payload["nodes"]:
+        assert set(node) <= set(graph_projection.PUBLIC_NODE_FIELDS), f"unexpected keys: {set(node)}"
+    for edge in payload["edges"]:
+        assert set(edge) <= set(graph_projection.PUBLIC_EDGE_FIELDS)
+
+
+def test_publishable_content_is_present(tmp_path: Path) -> None:
+    """Deny-by-default must not degrade into deny-everything."""
+    payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))
+
+    node = next(item for item in payload["nodes"] if item["id"] == "ADV-1")
+    assert node["title"] == "Publishable title"
+    assert node["type"] == "functional-requirement"
+    assert node["status"] == "approved"
+    assert node["priority"] == "high"
+    assert node["tags"] == ["public-tag"]
+
+
+def test_render_is_byte_stable(tmp_path: Path) -> None:
+    assert graph_projection.render_projection(projection_of(tmp_path)) == \
+        graph_projection.render_projection(projection_of(tmp_path))
+
+
+def test_node_order_is_deterministic_and_independent_of_request_order(tmp_path: Path) -> None:
+    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
+    result = analyze_project(tmp_path)
+    assert result.snapshot is not None
+
+    forward = graph_projection.build_projection(result.snapshot, node_ids=("ADV-1", "ADV-2"), view_id="v")
+    reverse = graph_projection.build_projection(result.snapshot, node_ids=("ADV-2", "ADV-1"), view_id="v")
+
+    assert graph_projection.render_projection(forward) == graph_projection.render_projection(reverse)
```
