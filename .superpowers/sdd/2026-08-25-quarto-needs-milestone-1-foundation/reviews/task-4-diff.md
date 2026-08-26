# Task 4 review package (no Git metadata)

## Changed-file inventory
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/src/quarto_needs/graph.py and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/src/quarto_needs/graph.py differ
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/src/quarto_needs/validation.py and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/src/quarto_needs/validation.py differ
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/tests/test_graph.py and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/tests/test_graph.py differ
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/tests: test_validation.py

## Full diff
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/src/quarto_needs/graph.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/src/quarto_needs/graph.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/src/quarto_needs/graph.py	2026-08-24 23:41:30.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/src/quarto_needs/graph.py	2026-08-25 09:43:05.669091477 -0300
@@ -4,6 +4,15 @@
 from dataclasses import dataclass
 
 from .model import EngineeringObject, Relation
+from .model import SourceLocation
+
+
+class DuplicateIdError(ValueError):
+    def __init__(self, duplicate_id: str, locations: tuple[SourceLocation, ...]):
+        self.duplicate_id = duplicate_id
+        self.locations = locations
+        rendered = ", ".join(f"{item.file}:{item.line}" for item in locations) or "unknown locations"
+        super().__init__(f"Duplicate ID {duplicate_id}: {rendered}")
 
 
 @dataclass
@@ -14,6 +23,28 @@
 
     @classmethod
     def build(cls, objects: list[EngineeringObject]) -> "RequirementsGraph":
+        declarations_by_id: dict[str, list[EngineeringObject]] = defaultdict(list)
+        for obj in objects:
+            declarations_by_id[obj.id].append(obj)
+
+        duplicate_ids = [
+            object_id
+            for object_id, declarations in declarations_by_id.items()
+            if len(declarations) > 1
+        ]
+        if duplicate_ids:
+            duplicate_id = min(duplicate_ids, key=lambda item: (item.casefold(), item))
+            locations = tuple(sorted(
+                (obj.source for obj in declarations_by_id[duplicate_id] if obj.source is not None),
+                key=lambda item: (
+                    item.file.casefold(),
+                    item.file,
+                    item.line,
+                    item.anchor or "",
+                ),
+            ))
+            raise DuplicateIdError(duplicate_id, locations)
+
         by_id = {obj.id: obj for obj in objects}
         outgoing: dict[str, list[Relation]] = defaultdict(list)
         incoming: dict[str, list[Relation]] = defaultdict(list)
@@ -21,6 +52,26 @@
             for rel in obj.relations:
                 outgoing[rel.source].append(rel)
                 incoming[rel.target].append(rel)
+        for relations in outgoing.values():
+            relations.sort(
+                key=lambda item: (
+                    item.type,
+                    item.target.casefold(),
+                    item.target,
+                    item.source.casefold(),
+                    item.source,
+                )
+            )
+        for relations in incoming.values():
+            relations.sort(
+                key=lambda item: (
+                    item.type,
+                    item.source.casefold(),
+                    item.source,
+                    item.target.casefold(),
+                    item.target,
+                )
+            )
         return cls(by_id, dict(outgoing), dict(incoming))
 
     def downstream(self, start: str) -> set[str]:
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/src/quarto_needs/validation.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/src/quarto_needs/validation.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/src/quarto_needs/validation.py	2026-08-25 09:32:13.102541926 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/src/quarto_needs/validation.py	2026-08-25 09:43:05.669091477 -0300
@@ -3,20 +3,37 @@
 from collections import Counter
 
 from .diagnostics import Finding
-from .graph import RequirementsGraph
 from .model import EngineeringObject, SourceLocation
 from .snapshot import LocationRecord
 
 
+SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
+
+
 def _location_record(source: SourceLocation | None) -> LocationRecord | None:
     if source is None:
         return None
     return LocationRecord(source.file, source.line, source.anchor)
 
 
+def finding_key(item: Finding) -> tuple[object, ...]:
+    location = item.location
+    return (
+        SEVERITY_ORDER.get(item.severity, 99),
+        item.code,
+        (item.object_id or "").casefold(),
+        item.object_id or "",
+        location.file.casefold() if location else "",
+        location.file if location else "",
+        location.line if location else 0,
+        item.message,
+    )
+
+
 def validate(objects: list[EngineeringObject], require_rationale_for: set[str] | None = None) -> list[Finding]:
     findings: list[Finding] = []
     counts = Counter(o.id for o in objects)
+    known_ids = set(counts)
     for need_id, count in counts.items():
         if count > 1:
             source = next(obj.source for obj in objects if obj.id == need_id)
@@ -28,11 +45,9 @@
                 _location_record(source),
             ))
 
-    graph = RequirementsGraph.build(objects)
-    known = set(graph.objects)
     for obj in objects:
         for rel in obj.relations:
-            if rel.target not in known:
+            if rel.target not in known_ids:
                 findings.append(Finding(
                     "REQ005", "error",
                     f"{obj.id} references unknown object {rel.target} via {rel.type}",
@@ -48,4 +63,4 @@
             has_verification = any(r.type in {"verified-by", "validated-by"} for r in obj.relations)
             if not has_verification:
                 findings.append(Finding("REQ006", "warning", f"{obj.id} is approved but has no verification relation", obj.id))
-    return findings
+    return sorted(findings, key=finding_key)
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/tests/test_graph.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/tests/test_graph.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/tests/test_graph.py	2026-08-24 23:41:30.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/tests/test_graph.py	2026-08-25 09:42:26.181212272 -0300
@@ -1,5 +1,8 @@
+import pytest
+
+from quarto_needs import graph
 from quarto_needs.graph import RequirementsGraph
-from quarto_needs.model import EngineeringObject, Relation
+from quarto_needs.model import EngineeringObject, Relation, SourceLocation
 
 
 def test_traceability():
@@ -9,3 +12,58 @@
     graph = RequirementsGraph.build([a, b, c])
     assert graph.downstream("A") == {"B", "C"}
     assert graph.upstream("C") == {"A", "B"}
+
+
+def test_graph_rejects_duplicate_ids_instead_of_overwriting() -> None:
+    first = EngineeringObject(
+        "REQ-1", "need", "First", source=SourceLocation("a.qmd", 1, "REQ-1")
+    )
+    second = EngineeringObject(
+        "REQ-1", "need", "Second", source=SourceLocation("b.qmd", 7, "REQ-1")
+    )
+
+    with pytest.raises(getattr(graph, "DuplicateIdError", ValueError)) as caught:
+        RequirementsGraph.build([second, first])
+
+    assert caught.value.duplicate_id == "REQ-1"
+    assert [(item.file, item.line) for item in caught.value.locations] == [
+        ("a.qmd", 1),
+        ("b.qmd", 7),
+    ]
+
+
+def test_graph_sorts_adjacency_lists_deterministically() -> None:
+    source = EngineeringObject(
+        "SOURCE",
+        "need",
+        "Source",
+        relations=[
+            Relation("zeta", "SOURCE", "M"),
+            Relation("alpha", "SOURCE", "Z"),
+            Relation("alpha", "SOURCE", "a"),
+        ],
+    )
+    first = EngineeringObject(
+        "FIRST",
+        "need",
+        "First",
+        relations=[Relation("zeta", "Z", "TARGET")],
+    )
+    second = EngineeringObject(
+        "SECOND",
+        "need",
+        "Second",
+        relations=[Relation("alpha", "a", "TARGET")],
+    )
+
+    graph = RequirementsGraph.build([source, first, second])
+
+    assert [(item.type, item.target) for item in graph.outgoing["SOURCE"]] == [
+        ("alpha", "a"),
+        ("alpha", "Z"),
+        ("zeta", "M"),
+    ]
+    assert [(item.type, item.source) for item in graph.incoming["TARGET"]] == [
+        ("alpha", "a"),
+        ("zeta", "Z"),
+    ]
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/tests/test_validation.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/tests/test_validation.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-before/tests/test_validation.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-4-after/tests/test_validation.py	2026-08-25 09:42:26.181212272 -0300
@@ -0,0 +1,43 @@
+from quarto_needs.model import EngineeringObject, Relation, SourceLocation
+from quarto_needs.snapshot import LocationRecord
+from quarto_needs.validation import validate
+
+
+def test_validation_reports_duplicate_and_unknown_target_without_throwing() -> None:
+    first = EngineeringObject(
+        "REQ-1",
+        "need",
+        "First",
+        relations=[Relation("references", "REQ-1", "MISSING")],
+    )
+    second = EngineeringObject("REQ-1", "need", "Second")
+
+    findings = validate([second, first])
+
+    assert [(item.code, item.object_id) for item in findings if item.severity == "error"] == [
+        ("REQ004", "REQ-1"),
+        ("REQ005", "REQ-1"),
+    ]
+
+
+def test_validation_uses_first_duplicate_and_relation_owner_locations() -> None:
+    first = EngineeringObject(
+        "REQ-1",
+        "need",
+        "First",
+        relations=[Relation("references", "REQ-1", "MISSING")],
+        source=SourceLocation("z.qmd", 9, "REQ-1"),
+    )
+    second = EngineeringObject(
+        "REQ-1",
+        "need",
+        "Second",
+        source=SourceLocation("a.qmd", 3, "REQ-1"),
+    )
+
+    findings = validate([first, second])
+
+    assert [(item.code, item.location) for item in findings if item.severity == "error"] == [
+        ("REQ004", LocationRecord("z.qmd", 9, "REQ-1")),
+        ("REQ005", LocationRecord("z.qmd", 9, "REQ-1")),
+    ]
