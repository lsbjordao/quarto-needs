# Review package

Snapshot range: `task-1-after` -> `task-1-fix1`

## Files changed (4)

- `schemas/graph-public-v1.schema.json`
- `src/quarto_needs/graph_projection.py`
- `tests/fixtures/graph/adversarial.qmd`
- `tests/test_graph_projection.py`

## Summary

198 lines added, 13 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/schemas/graph-public-v1.schema.json .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-fix1/schemas/graph-public-v1.schema.json
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/schemas/graph-public-v1.schema.json	2026-08-27 01:17:12.597802638 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-fix1/schemas/graph-public-v1.schema.json	2026-08-27 10:20:57.200847495 -0300
@@ -22,21 +22,21 @@
           "required": ["nodes", "edges"],
           "properties": {"nodes": {"type": "integer"}, "edges": {"type": "integer"}}
         }
       }
     },
     "nodes": {
       "type": "array",
       "items": {
         "type": "object",
         "additionalProperties": false,
-        "required": ["id", "title", "type", "status"],
+        "required": ["id", "title", "type", "status", "href"],
         "properties": {
           "id": {"type": "string"},
           "title": {"type": "string"},
           "type": {"type": "string"},
           "status": {"type": "string"},
           "priority": {"type": ["string", "null"]},
           "tags": {"type": "array", "items": {"type": "string"}},
           "href": {"type": "string"},
           "change": {"enum": ["added", "removed", "modified", "relocated", "unchanged"]}
         }
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/src/quarto_needs/graph_projection.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-fix1/src/quarto_needs/graph_projection.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/src/quarto_needs/graph_projection.py	2026-08-27 01:22:33.000879081 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-fix1/src/quarto_needs/graph_projection.py	2026-08-27 10:23:58.228150918 -0300
@@ -2,29 +2,30 @@
 
 Deny by default: nodes and edges are constructed field by field from an
 allowlist. Nothing is copied wholesale and filtered afterwards, because that
 inverts the default — a field added to `ObjectRecord` later would ship to the
 browser until someone remembered to exclude it.
 """
 from __future__ import annotations
 
 import json
 from dataclasses import dataclass
-from typing import Iterable, Mapping, Sequence
+from typing import Iterable, Mapping
 
 from .relations import DEFAULT_RELATION_CATALOG
 from .snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord
 
 SCHEMA_VERSION = "graph-public-v1"
 
 PUBLIC_NODE_FIELDS = ("id", "title", "type", "status", "priority", "tags", "href", "change")
 PUBLIC_EDGE_FIELDS = ("source", "target", "relation", "label", "change", "pathMember")
+PUBLIC_LIMIT_FIELDS = ("nodes", "edges")
 
 DEFAULT_LIMITS = {"nodes": 100, "edges": 300}
 
 
 @dataclass(frozen=True, slots=True)
 class PublicNode:
     id: str
     title: str
     type: str
     status: str
@@ -65,41 +66,67 @@
             "label": self.label,
         }
         if self.change is not None:
             payload["change"] = self.change
         if self.path_member is not None:
             payload["pathMember"] = self.path_member
         return payload
 
 
 @dataclass(frozen=True, slots=True)
+class PublicImpactEntry:
+    id: str
+    origin: str
+    distance: int
+    path: tuple[str, ...]
+    classification: str | None = None
+
+    def to_dict(self) -> dict[str, object]:
+        payload: dict[str, object] = {
+            "id": self.id,
+            "origin": self.origin,
+            "distance": self.distance,
+            "path": list(self.path),
+        }
+        if self.classification is not None:
+            payload["classification"] = self.classification
+        return payload
+
+
+@dataclass(frozen=True, slots=True)
 class GraphProjection:
     view_id: str
     mode: str
     limits: Mapping[str, int]
     nodes: tuple[PublicNode, ...]
     edges: tuple[PublicEdge, ...]
-    impact: tuple[Mapping[str, object], ...] = ()
+    impact: tuple[PublicImpactEntry, ...] = ()
 
     def to_dict(self) -> dict[str, object]:
         payload: dict[str, object] = {
             "schemaVersion": SCHEMA_VERSION,
             "view": {
                 "id": self.view_id,
                 "mode": self.mode,
-                "limits": dict(self.limits),
+                # Built from the two known keys, never `dict(self.limits)`:
+                # a caller-supplied mapping copied wholesale would ship any
+                # undeclared key that rode along inside it.
+                "limits": {key: self.limits[key] for key in PUBLIC_LIMIT_FIELDS},
             },
             "nodes": [node.to_dict() for node in self.nodes],
             "edges": [edge.to_dict() for edge in self.edges],
         }
         if self.impact:
-            payload["impact"] = [dict(item) for item in self.impact]
+            # Each entry must be a `PublicImpactEntry`; `.to_dict()` only
+            # emits its declared fields. A raw mapping slipped in here fails
+            # loudly (`AttributeError`) instead of being copied wholesale.
+            payload["impact"] = [item.to_dict() for item in self.impact]
         return payload
 
 
 def _public_href(record: ObjectRecord) -> str:
     """Anchor-only by default.
 
     A resolved cross-page href is safe to publish, but it is built by the Lua
     link resolver at render time, where the output format and current page are
     known. Emitting a filesystem-derived path here would leak project layout.
     """
@@ -138,21 +165,25 @@
     edges = tuple(
         PublicEdge(
             source=relation.source,
             target=relation.target,
             relation=relation.v1_name,
             label=_label_for(relation),
         )
         for relation in snapshot.relations
         if relation.source in selected and relation.target in selected
     )
+    source_limits = limits if limits is not None else DEFAULT_LIMITS
     return GraphProjection(
         view_id=view_id,
         mode=mode,
-        limits=dict(limits or DEFAULT_LIMITS),
+        limits={
+            key: int(source_limits.get(key, DEFAULT_LIMITS[key]))
+            for key in PUBLIC_LIMIT_FIELDS
+        },
         nodes=nodes,
         edges=edges,
     )
 
 
 def render_projection(projection: GraphProjection) -> str:
     return json.dumps(projection.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/tests/fixtures/graph/adversarial.qmd .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-fix1/tests/fixtures/graph/adversarial.qmd
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/tests/fixtures/graph/adversarial.qmd	2026-08-27 01:16:37.121904898 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-fix1/tests/fixtures/graph/adversarial.qmd	2026-08-27 10:20:06.581051038 -0300
@@ -1,14 +1,13 @@
 ::: {.need #ADV-1 type=functional-requirement status=approved priority=high tags="public-tag" secret-attribute="LEAKCANARYATTR7f3a"}
+rationale: LEAKCANARYRATIONALE4e77 explains why and is equally private.
+
 ## Publishable title
 
 LEAKCANARYBODY91cd is body prose and must never reach the browser.
-
-### Rationale
-LEAKCANARYRATIONALE4e77 explains why and is equally private.
 :::
 
-::: {.need #ADV-2 type=test-case status=passed tags="public-tag"}
+::: {.need #ADV-2 type=test-case status=passed tags="public-tag" verifies="ADV-1"}
 ## Second publishable title
 
 LEAKCANARYBODY2b80 is more private prose.
 :::
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/tests/test_graph_projection.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-fix1/tests/test_graph_projection.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-after/tests/test_graph_projection.py	2026-08-27 01:16:50.473866410 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-5a-interactive-graph/snapshots/task-1-fix1/tests/test_graph_projection.py	2026-08-27 10:20:50.032875175 -0300
@@ -1,32 +1,40 @@
 from __future__ import annotations
 
 import json
+import subprocess
+import sys
 from pathlib import Path
 
 import pytest
 from jsonschema import Draft202012Validator
 
 from quarto_needs import graph_projection
 from quarto_needs.analysis import analyze_project
 
 ROOT = Path(__file__).resolve().parents[1]
 FIXTURE = ROOT / "tests" / "fixtures" / "graph" / "adversarial.qmd"
 SCHEMA = ROOT / "schemas" / "graph-public-v1.schema.json"
 
 CANARIES = (
     "LEAKCANARYATTR7f3a",
     "LEAKCANARYBODY91cd",
     "LEAKCANARYRATIONALE4e77",
     "LEAKCANARYBODY2b80",
 )
 
+# The fixture is always written to a file literally named this. If it ever
+# reaches the serialized output, something leaked a filesystem path (a
+# resolved href, an edge label built from relation provenance, or similar) —
+# not one of the four content canaries, but just as private.
+FIXTURE_FILENAME = "adversarial.qmd"
+
 
 def projection_of(tmp_path: Path):
     (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
     result = analyze_project(tmp_path)
     assert result.snapshot is not None
     return graph_projection.build_projection(
         result.snapshot,
         node_ids=("ADV-1", "ADV-2"),
         view_id="need-graph-1",
     )
@@ -38,51 +46,198 @@
     Enumerating fields only catches leaks through paths someone anticipated. A
     canary search catches a leak through any path at all, including a future
     field added without thinking about publication policy.
     """
     serialized = graph_projection.render_projection(projection_of(tmp_path))
 
     for canary in CANARIES:
         assert canary not in serialized, f"{canary} reached the public projection"
 
 
+def test_no_source_location_reaches_the_projection(tmp_path: Path) -> None:
+    """Filesystem paths and line numbers are as private as body text.
+
+    The fixture declares a relation (ADV-2 verifies ADV-1), so an edge label
+    built from `relation.provenance` instead of the relation catalog would
+    smuggle the source file name and line number into the public output. The
+    node href is also at risk of the same leak via `record.locations`.
+    """
+    serialized = graph_projection.render_projection(projection_of(tmp_path))
+
+    assert FIXTURE_FILENAME not in serialized, "a source file name reached the public projection"
+
+
 def test_projection_validates_against_its_schema(tmp_path: Path) -> None:
     schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
     Draft202012Validator.check_schema(schema)
     Draft202012Validator(schema).validate(json.loads(graph_projection.render_projection(projection_of(tmp_path))))
 
 
 def test_only_allowlisted_fields_are_emitted(tmp_path: Path) -> None:
     payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))
 
+    # A subset check (`set(x) <= allowlist`) is vacuously true on an empty
+    # collection. Assert non-emptiness first so the checks below actually
+    # exercise something instead of passing by having nothing to inspect.
+    assert payload["nodes"], "fixture produced no nodes; the allowlist check below would be vacuous"
+    assert payload["edges"], "fixture produced no edges; the allowlist check below would be vacuous"
+
+    assert set(payload) <= {"schemaVersion", "view", "nodes", "edges", "impact"}, set(payload)
+    assert set(payload["view"]) <= {"id", "mode", "limits", "layout", "seed"}, set(payload["view"])
+    assert set(payload["view"]["limits"]) <= {"nodes", "edges"}, set(payload["view"]["limits"])
+
     for node in payload["nodes"]:
         assert set(node) <= set(graph_projection.PUBLIC_NODE_FIELDS), f"unexpected keys: {set(node)}"
     for edge in payload["edges"]:
-        assert set(edge) <= set(graph_projection.PUBLIC_EDGE_FIELDS)
+        assert set(edge) <= set(graph_projection.PUBLIC_EDGE_FIELDS), f"unexpected keys: {set(edge)}"
 
 
 def test_publishable_content_is_present(tmp_path: Path) -> None:
     """Deny-by-default must not degrade into deny-everything."""
     payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))
 
     node = next(item for item in payload["nodes"] if item["id"] == "ADV-1")
     assert node["title"] == "Publishable title"
     assert node["type"] == "functional-requirement"
     assert node["status"] == "approved"
     assert node["priority"] == "high"
     assert node["tags"] == ["public-tag"]
+    assert node["href"] == "#ADV-1"
+
+    edge = next(
+        item for item in payload["edges"] if item["source"] == "ADV-2" and item["target"] == "ADV-1"
+    )
+    assert edge["relation"] == "verifies"
+    assert edge["label"] == "Verifies"
 
 
 def test_render_is_byte_stable(tmp_path: Path) -> None:
-    assert graph_projection.render_projection(projection_of(tmp_path)) == \
-        graph_projection.render_projection(projection_of(tmp_path))
+    first = graph_projection.render_projection(projection_of(tmp_path))
+    second = graph_projection.render_projection(projection_of(tmp_path))
+    assert first == second
+
+    # Pin the canonical form itself, not just self-agreement within one
+    # process. Without `sort_keys=True` the top-level key order would follow
+    # dict-construction order ("schemaVersion" first); without `indent=2` the
+    # whole document would collapse onto (almost) one line. Either regression
+    # left `first == second` true, since both calls run the same buggy code.
+    assert first.startswith('{\n  "edges"'), "top-level keys are not sorted"
+    assert first.count("\n") > 4, "output is not indented"
+    assert first.endswith("\n")
+
+
+def test_render_is_byte_stable_across_processes(tmp_path: Path) -> None:
+    """A second call in the same process can't see hash-seed or process-local
+    ordering effects. Render the same fixture in a fresh interpreter and
+    compare bytes exactly."""
+    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
+    in_process = graph_projection.render_projection(projection_of(tmp_path))
+
+    script = (
+        "from pathlib import Path\n"
+        "from quarto_needs import graph_projection\n"
+        "from quarto_needs.analysis import analyze_project\n"
+        f"result = analyze_project(Path({str(tmp_path)!r}))\n"
+        "projection = graph_projection.build_projection(\n"
+        "    result.snapshot, node_ids=('ADV-1', 'ADV-2'), view_id='need-graph-1'\n"
+        ")\n"
+        "import sys\n"
+        "sys.stdout.write(graph_projection.render_projection(projection))\n"
+    )
+    completed = subprocess.run(
+        [sys.executable, "-c", script],
+        capture_output=True,
+        text=True,
+        check=True,
+    )
+    assert completed.stdout == in_process
 
 
 def test_node_order_is_deterministic_and_independent_of_request_order(tmp_path: Path) -> None:
     (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
     result = analyze_project(tmp_path)
     assert result.snapshot is not None
 
     forward = graph_projection.build_projection(result.snapshot, node_ids=("ADV-1", "ADV-2"), view_id="v")
     reverse = graph_projection.build_projection(result.snapshot, node_ids=("ADV-2", "ADV-1"), view_id="v")
 
     assert graph_projection.render_projection(forward) == graph_projection.render_projection(reverse)
+
+
+def test_limits_are_built_from_known_keys_not_copied_wholesale(tmp_path: Path) -> None:
+    """`view.limits` must be constructed field by field, like nodes and edges.
+
+    A caller-supplied (or otherwise smuggled-in) mapping with an undeclared
+    key must not reach the serialized output just because it rode along in
+    the same dict.
+    """
+    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
+    result = analyze_project(tmp_path)
+    assert result.snapshot is not None
+
+    projection = graph_projection.build_projection(
+        result.snapshot,
+        node_ids=("ADV-1", "ADV-2"),
+        view_id="need-graph-1",
+        limits={"nodes": 5, "edges": 9, "secret": "LEAKCANARYLIMITq1w2"},
+    )
+    payload = json.loads(graph_projection.render_projection(projection))
+
+    assert payload["view"]["limits"] == {"nodes": 5, "edges": 9}
+    assert "LEAKCANARYLIMITq1w2" not in graph_projection.render_projection(projection)
+
+
+def test_impact_entries_are_built_from_named_fields(tmp_path: Path) -> None:
+    """`impact` must be a dataclass with named fields, not a raw mapping.
+
+    A raw `dict` payload copied wholesale would ship any key a caller put in
+    it. `PublicImpactEntry.to_dict()` only ever emits the fields it declares.
+    """
+    entry = graph_projection.PublicImpactEntry(
+        id="ADV-2",
+        origin="ADV-1",
+        distance=1,
+        path=("ADV-1", "ADV-2"),
+        classification="direct",
+    )
+    projection = graph_projection.GraphProjection(
+        view_id="v",
+        mode="impact",
+        limits={"nodes": 1, "edges": 1},
+        nodes=(),
+        edges=(),
+        impact=(entry,),
+    )
+    payload = json.loads(graph_projection.render_projection(projection))
+
+    assert payload["impact"] == [
+        {
+            "id": "ADV-2",
+            "origin": "ADV-1",
+            "distance": 1,
+            "path": ["ADV-1", "ADV-2"],
+            "classification": "direct",
+        }
+    ]
+
+
+def test_impact_cannot_smuggle_undeclared_keys_via_a_raw_mapping() -> None:
+    """A raw dict slipped into `impact` instead of a `PublicImpactEntry` must
+    not be silently accepted and copied through — it must fail loudly."""
+    projection = graph_projection.GraphProjection(
+        view_id="v",
+        mode="impact",
+        limits={"nodes": 1, "edges": 1},
+        nodes=(),
+        edges=(),
+        impact=(
+            {
+                "id": "ADV-2",
+                "origin": "ADV-1",
+                "distance": 1,
+                "path": ["ADV-1", "ADV-2"],
+                "secret": "LEAKCANARYIMPACTz9y8",
+            },
+        ),
+    )
+    with pytest.raises(AttributeError):
+        graph_projection.render_projection(projection)
```
