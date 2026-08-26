diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/src/quarto_needs/export.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/src/quarto_needs/export.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/src/quarto_needs/export.py	2026-08-25 10:11:17.260378180 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/src/quarto_needs/export.py	2026-08-25 10:25:05.662501894 -0300
@@ -1,56 +1,274 @@
 from __future__ import annotations
 
 import json
+import os
+import tempfile
 from pathlib import Path
+from typing import cast
 
-from .graph import RequirementsGraph
+from .analysis import analyze_objects, legacy_coverage
 from .model import EngineeringObject
+from .relations import DEFAULT_RELATION_CATALOG
+from .snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord, thaw_json
 from .validation import Finding
 
 
-def coverage(objects: list[EngineeringObject]) -> dict[str, object]:
-    requirements = [o for o in objects if o.type.endswith("requirement")]
-    implemented = [o for o in requirements if any(r.type in {"implements", "implemented-by"} for r in o.relations)]
-    verified = [o for o in requirements if any(r.type in {"verified-by", "validated-by"} for r in o.relations)]
-    approved = [o for o in requirements if o.status == "approved"]
+_INVALID_GRAPH_ERROR = "Cannot export a structurally invalid requirements graph"
+
+
+def _legacy_coverage_fallback(
+    objects: list[EngineeringObject],
+) -> dict[str, object]:
+    requirements = [item for item in objects if item.type.endswith("requirement")]
+    implemented = [
+        item
+        for item in requirements
+        if any(
+            relation.type in {"implements", "implemented-by"}
+            for relation in item.relations
+        )
+    ]
+    verified = [
+        item
+        for item in requirements
+        if any(
+            relation.type in {"verified-by", "validated-by"}
+            for relation in item.relations
+        )
+    ]
     total = len(requirements)
     return {
         "requirements": total,
-        "approved": len(approved),
+        "approved": sum(item.status == "approved" for item in requirements),
         "implemented": len(implemented),
         "verified": len(verified),
-        "implementation_coverage": round(100 * len(implemented) / total, 1) if total else 100.0,
-        "verification_coverage": round(100 * len(verified) / total, 1) if total else 100.0,
+        "implementation_coverage": (
+            round(100 * len(implemented) / total, 1) if total else 100.0
+        ),
+        "verification_coverage": (
+            round(100 * len(verified) / total, 1) if total else 100.0
+        ),
     }
 
 
-def export_graph(path: Path, objects: list[EngineeringObject], findings: list[Finding]) -> None:
-    graph = RequirementsGraph.build(objects)
-    payload = {
+def coverage(objects: list[EngineeringObject]) -> dict[str, object]:
+    result = analyze_objects(objects)
+    if result.snapshot is None:
+        return _legacy_coverage_fallback(objects)
+    return cast(
+        dict[str, object],
+        thaw_json(legacy_coverage(result.snapshot.objects, result.snapshot.relations)),
+    )
+
+
+def _relation_v1(item: RelationRecord) -> dict[str, object]:
+    return {
+        "type": item.v1_name,
+        "source": item.source,
+        "target": item.target,
+        "attributes": thaw_json(item.attributes),
+    }
+
+
+def _object_v1(
+    item: ObjectRecord,
+    outgoing: tuple[RelationRecord, ...],
+) -> dict[str, object]:
+    source = item.locations[0] if item.locations else None
+    href = (
+        f"{Path(source.file).with_suffix('').as_posix()}.html#"
+        f"{source.anchor or item.id}"
+        if source
+        else f"#{item.id}"
+    )
+    return {
+        "id": item.id,
+        "type": item.type,
+        "title": item.title,
+        "status": item.status,
+        "body": item.body,
+        "rationale": item.rationale,
+        "attributes": thaw_json(item.attributes),
+        "relations": [_relation_v1(relation) for relation in outgoing],
+        "source": (
+            {
+                "file": source.file,
+                "line": source.line,
+                "anchor": source.anchor,
+            }
+            if source
+            else None
+        ),
+        "href": href,
+    }
+
+
+def _relation_metadata(item: RelationRecord) -> dict[str, object]:
+    kind = DEFAULT_RELATION_CATALOG.resolve(item.authored_name)
+    return {
+        "directLabel": kind.direct_label,
+        "inverseLabel": kind.inverse_label,
+        "semanticFamily": kind.semantic_family,
+        "sourceRole": kind.source_role,
+        "targetRole": kind.target_role,
+        "impactDirection": kind.impact_direction,
+        "public": kind.public,
+    }
+
+
+def _project_relation_catalog(
+    relations: tuple[RelationRecord, ...],
+) -> dict[str, object]:
+    metadata_by_name: dict[str, dict[str, object]] = {}
+    for relation in relations:
+        metadata = _relation_metadata(relation)
+        previous = metadata_by_name.get(relation.v1_name)
+        if previous is not None and previous != metadata:
+            raise ValueError(
+                "Conflicting relation aliases for v1 name " f"{relation.v1_name}"
+            )
+        metadata_by_name[relation.v1_name] = metadata
+    return {name: metadata_by_name[name] for name in sorted(metadata_by_name)}
+
+
+def build_v1_payload(snapshot: AnalysisSnapshot) -> dict[str, object]:
+    objects: list[dict[str, object]] = []
+    relations: list[dict[str, object]] = []
+    for item in snapshot.objects:
+        projected = _object_v1(item, snapshot.outgoing[item.id])
+        objects.append(projected)
+        relations.extend(cast(list[dict[str, object]], projected["relations"]))
+
+    backlinks = {
+        item.id: [
+            {"source": relation.source, "type": relation.v1_name}
+            for relation in sorted(
+                snapshot.incoming[item.id],
+                key=lambda relation: (
+                    relation.source.casefold(),
+                    relation.source,
+                    relation.v1_name,
+                ),
+            )
+        ]
+        for item in snapshot.objects
+    }
+    return {
         "schemaVersion": "1",
-        "objects": [o.to_dict() | {"href": o.href} for o in objects],
-        "relations": [r.__dict__ if hasattr(r, "__dict__") else {"type": r.type, "source": r.source, "target": r.target, "attributes": r.attributes}
-                      for o in objects for r in o.relations],
-        "coverage": coverage(objects),
-        "validation": [f.to_dict() for f in findings],
-        "backlinks": {
-            obj_id: [
-                {"source": r.source, "type": r.type}
-                for r in graph.incoming.get(obj_id, [])
-            ]
-            for obj_id in graph.objects
+        "objects": objects,
+        "relations": relations,
+        "coverage": thaw_json(snapshot.metrics),
+        "validation": [finding.to_dict() for finding in snapshot.findings],
+        "backlinks": backlinks,
+        "extensions": {
+            "quartoNeeds": {
+                "generator": {
+                    "name": snapshot.generator_name,
+                    "version": snapshot.generator_version,
+                },
+                "relationCatalogVersion": snapshot.relation_catalog_version,
+                "relationCatalog": _project_relation_catalog(snapshot.relations),
+            }
         },
     }
-    path.parent.mkdir(parents=True, exist_ok=True)
-    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
 
 
-def export_lua_index(path: Path, objects: list[EngineeringObject]) -> None:
-    def esc(s: str) -> str:
-        return s.replace("\\", "\\\\").replace('"', '\\"')
+def render_v1_json(snapshot: AnalysisSnapshot) -> str:
+    return json.dumps(
+        build_v1_payload(snapshot),
+        ensure_ascii=False,
+        indent=2,
+        sort_keys=True,
+    ) + "\n"
+
+
+def _lua_escape(value: str) -> str:
+    return (
+        value.replace("\\", "\\\\")
+        .replace('"', '\\"')
+        .replace("\n", "\\n")
+        .replace("\r", "\\r")
+    )
+
+
+def render_lua_index(snapshot: AnalysisSnapshot) -> str:
     lines = ["return {"]
-    for o in objects:
-        lines.append(f'  ["{esc(o.id)}"] = {{ title = "{esc(o.title)}", href = "{esc(o.href)}", type = "{esc(o.type)}", status = "{esc(o.status)}" }},')
+    for item in snapshot.objects:
+        source = item.locations[0] if item.locations else None
+        href = (
+            f"{Path(source.file).with_suffix('').as_posix()}.html#"
+            f"{source.anchor or item.id}"
+            if source
+            else f"#{item.id}"
+        )
+        lines.append(
+            f'  ["{_lua_escape(item.id)}"] = '
+            f'{{ title = "{_lua_escape(item.title)}", '
+            f'href = "{_lua_escape(href)}", '
+            f'type = "{_lua_escape(item.type)}", '
+            f'status = "{_lua_escape(item.status)}" }},'
+        )
     lines.append("}")
+    return "\n".join(lines) + "\n"
+
+
+def _write_atomic_text(path: Path, contents: str) -> None:
+    path = Path(path)
     path.parent.mkdir(parents=True, exist_ok=True)
-    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
+    descriptor, temporary_name = tempfile.mkstemp(
+        prefix=f".{path.name}.",
+        suffix=".tmp",
+        dir=path.parent,
+    )
+    temporary = Path(temporary_name)
+    try:
+        with os.fdopen(
+            descriptor,
+            "w",
+            encoding="utf-8",
+            newline="\n",
+        ) as stream:
+            stream.write(contents)
+            stream.flush()
+            os.fsync(stream.fileno())
+        os.replace(temporary, path)
+    except BaseException:
+        temporary.unlink(missing_ok=True)
+        raise
+
+
+def write_v1_graph(path: Path, snapshot: AnalysisSnapshot) -> None:
+    _write_atomic_text(path, render_v1_json(snapshot))
+
+
+def write_lua_index(path: Path, snapshot: AnalysisSnapshot) -> None:
+    _write_atomic_text(path, render_lua_index(snapshot))
+
+
+def write_build_outputs(
+    graph_path: Path,
+    index_path: Path,
+    snapshot: AnalysisSnapshot,
+) -> None:
+    graph = render_v1_json(snapshot)
+    index = render_lua_index(snapshot)
+    _write_atomic_text(graph_path, graph)
+    _write_atomic_text(index_path, index)
+
+
+def export_graph(
+    path: Path,
+    objects: list[EngineeringObject],
+    findings: list[Finding],
+) -> None:
+    result = analyze_objects(objects, reported_findings=findings)
+    if result.snapshot is None:
+        raise ValueError(_INVALID_GRAPH_ERROR)
+    write_v1_graph(path, result.snapshot)
+
+
+def export_lua_index(path: Path, objects: list[EngineeringObject]) -> None:
+    result = analyze_objects(objects)
+    if result.snapshot is None:
+        raise ValueError(_INVALID_GRAPH_ERROR)
+    write_lua_index(path, result.snapshot)
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/tests/fixtures/canonical/expected-generated-index.lua .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/tests/fixtures/canonical/expected-generated-index.lua
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/tests/fixtures/canonical/expected-generated-index.lua	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/tests/fixtures/canonical/expected-generated-index.lua	2026-08-25 10:25:05.666501885 -0300
@@ -0,0 +1,5 @@
+return {
+  ["A-REQ-001"] = { title = "Autenticação forte", href = "z-requirements.html#A-REQ-001", type = "functional-requirement", status = "approved" },
+  ["M-NEED-001"] = { title = "Administrators need secure access", href = "z-requirements.html#M-NEED-001", type = "stakeholder-need", status = "approved" },
+  ["Z-TC-001"] = { title = "Verifies autenticação", href = "a-tests.html#Z-TC-001", type = "test-case", status = "passed" },
+}
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/tests/fixtures/canonical/expected-needs-v1.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/tests/fixtures/canonical/expected-needs-v1.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/tests/fixtures/canonical/expected-needs-v1.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/tests/fixtures/canonical/expected-needs-v1.json	2026-08-25 10:25:05.666501885 -0300
@@ -0,0 +1,145 @@
+{
+  "backlinks": {
+    "A-REQ-001": [],
+    "M-NEED-001": [
+      {
+        "source": "A-REQ-001",
+        "type": "derives-from"
+      }
+    ],
+    "Z-TC-001": [
+      {
+        "source": "A-REQ-001",
+        "type": "verified-by"
+      }
+    ]
+  },
+  "coverage": {
+    "approved": 1,
+    "implementation_coverage": 0.0,
+    "implemented": 0,
+    "requirements": 1,
+    "verification_coverage": 100.0,
+    "verified": 1
+  },
+  "extensions": {
+    "quartoNeeds": {
+      "generator": {
+        "name": "quarto-needs",
+        "version": "0.1.0"
+      },
+      "relationCatalog": {
+        "derives-from": {
+          "directLabel": "Derives from",
+          "impactDirection": "target_to_source",
+          "inverseLabel": "Source for",
+          "public": true,
+          "semanticFamily": "derivation",
+          "sourceRole": "derived",
+          "targetRole": "source"
+        },
+        "verified-by": {
+          "directLabel": "Verified by",
+          "impactDirection": "source_to_target",
+          "inverseLabel": "Verifies",
+          "public": true,
+          "semanticFamily": "verification",
+          "sourceRole": "requirement",
+          "targetRole": "test"
+        }
+      },
+      "relationCatalogVersion": "1"
+    }
+  },
+  "objects": [
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": [
+          "authentication",
+          "security"
+        ]
+      },
+      "body": "The service shall authenticate administrators.",
+      "href": "z-requirements.html#A-REQ-001",
+      "id": "A-REQ-001",
+      "rationale": "Prevent unauthorized administrative access.",
+      "relations": [
+        {
+          "attributes": {},
+          "source": "A-REQ-001",
+          "target": "M-NEED-001",
+          "type": "derives-from"
+        },
+        {
+          "attributes": {},
+          "source": "A-REQ-001",
+          "target": "Z-TC-001",
+          "type": "verified-by"
+        }
+      ],
+      "source": {
+        "anchor": "A-REQ-001",
+        "file": "z-requirements.qmd",
+        "line": 10
+      },
+      "status": "approved",
+      "title": "Autenticação forte",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "identity; access"
+      },
+      "body": "Administrative access must be protected.",
+      "href": "z-requirements.html#M-NEED-001",
+      "id": "M-NEED-001",
+      "rationale": "",
+      "relations": [],
+      "source": {
+        "anchor": "M-NEED-001",
+        "file": "z-requirements.qmd",
+        "line": 1
+      },
+      "status": "approved",
+      "title": "Administrators need secure access",
+      "type": "stakeholder-need"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "verification; unicode"
+      },
+      "body": "The test passes for valid credentials.",
+      "href": "a-tests.html#Z-TC-001",
+      "id": "Z-TC-001",
+      "rationale": "",
+      "relations": [],
+      "source": {
+        "anchor": "Z-TC-001",
+        "file": "a-tests.qmd",
+        "line": 1
+      },
+      "status": "passed",
+      "title": "Verifies autenticação",
+      "type": "test-case"
+    }
+  ],
+  "relations": [
+    {
+      "attributes": {},
+      "source": "A-REQ-001",
+      "target": "M-NEED-001",
+      "type": "derives-from"
+    },
+    {
+      "attributes": {},
+      "source": "A-REQ-001",
+      "target": "Z-TC-001",
+      "type": "verified-by"
+    }
+  ],
+  "schemaVersion": "1",
+  "validation": []
+}
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/tests/test_export.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/tests/test_export.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/tests/test_export.py	2026-08-25 10:11:17.264378170 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/tests/test_export.py	2026-08-25 10:25:05.666501885 -0300
@@ -1,10 +1,37 @@
 from __future__ import annotations
 
 import json
+import os
+from dataclasses import replace
 from pathlib import Path
 
-from quarto_needs.export import export_graph
+import pytest
+
+from quarto_needs.analysis import analyze_objects, analyze_project
+from quarto_needs.export import (
+    build_v1_payload,
+    coverage,
+    export_graph,
+    export_lua_index,
+    render_lua_index,
+    render_v1_json,
+    write_build_outputs,
+    write_v1_graph,
+)
 from quarto_needs.model import EngineeringObject, Relation
+from quarto_needs.snapshot import AnalysisSnapshot
+
+ROOT = Path(__file__).resolve().parents[1]
+FIXTURE = ROOT / "tests/fixtures/canonical"
+
+
+def canonical_snapshot() -> AnalysisSnapshot:
+    result = analyze_project(
+        FIXTURE,
+        files=[FIXTURE / "a-tests.qmd", FIXTURE / "z-requirements.qmd"],
+    )
+    assert result.snapshot is not None
+    return result.snapshot
 
 
 def test_export_keeps_attributes_relations_and_backlinks(tmp_path: Path):
@@ -26,3 +53,166 @@
     assert payload["objects"][0]["attributes"]["priority"] == "high"
     assert payload["relations"][0]["target"] == "TC-1"
     assert payload["backlinks"]["TC-1"] == [{"source": "REQ-1", "type": "verified-by"}]
+
+
+def test_v1_render_is_byte_identical_for_reversed_file_order() -> None:
+    first = analyze_project(
+        FIXTURE,
+        files=[FIXTURE / "a-tests.qmd", FIXTURE / "z-requirements.qmd"],
+    )
+    second = analyze_project(
+        FIXTURE,
+        files=[FIXTURE / "z-requirements.qmd", FIXTURE / "a-tests.qmd"],
+    )
+    assert first.snapshot is not None and second.snapshot is not None
+    assert render_v1_json(first.snapshot) == render_v1_json(second.snapshot)
+    assert render_v1_json(first.snapshot).endswith("\n")
+    assert render_lua_index(first.snapshot).endswith("\n")
+
+
+def test_v1_nested_relations_exactly_equal_top_level_relations() -> None:
+    payload = json.loads(render_v1_json(canonical_snapshot()))
+    nested = [relation for item in payload["objects"] for relation in item["relations"]]
+    assert nested == payload["relations"]
+    assert payload["relations"][0]["type"] == "derives-from"
+    assert "authored_name" not in json.dumps(payload)
+
+
+def test_v1_relation_catalog_contains_only_sorted_present_names() -> None:
+    payload = build_v1_payload(canonical_snapshot())
+    catalog = payload["extensions"]["quartoNeeds"]["relationCatalog"]
+    assert list(catalog) == ["derives-from", "verified-by"]
+    assert catalog["derives-from"] == {
+        "directLabel": "Derives from",
+        "inverseLabel": "Source for",
+        "semanticFamily": "derivation",
+        "sourceRole": "derived",
+        "targetRole": "source",
+        "impactDirection": "target_to_source",
+        "public": True,
+    }
+
+
+def test_v1_relation_catalog_rejects_conflicting_alias_metadata() -> None:
+    snapshot = canonical_snapshot()
+    original = snapshot.outgoing["A-REQ-001"][0]
+    conflicting = replace(
+        original,
+        authored_name="verified-by",
+        catalog_name="verified-by",
+        semantic_family="verification",
+        source_role="requirement",
+        target_role="test",
+        impact_direction="source_to_target",
+    )
+    outgoing = dict(snapshot.outgoing)
+    outgoing["A-REQ-001"] = (original, conflicting)
+    malformed = replace(
+        snapshot,
+        relations=(original, conflicting),
+        outgoing=outgoing,
+    )
+
+    with pytest.raises(ValueError, match="Conflicting relation aliases for v1 name derives-from"):
+        build_v1_payload(malformed)
+
+
+def test_v1_writer_replaces_destination_atomically(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    destination = tmp_path / "needs.json"
+    destination.write_text("sentinel", encoding="utf-8")
+    replacements: list[tuple[Path, Path]] = []
+    real_replace = os.replace
+
+    def recording_replace(source: str | Path, target: str | Path) -> None:
+        replacements.append((Path(source), Path(target)))
+        real_replace(source, target)
+
+    monkeypatch.setattr(os, "replace", recording_replace)
+    write_v1_graph(destination, canonical_snapshot())
+    assert replacements and replacements[-1][1] == destination
+    assert json.loads(destination.read_text(encoding="utf-8"))["schemaVersion"] == "1"
+    assert not list(tmp_path.glob(".needs.json.*.tmp"))
+
+
+def test_build_outputs_render_both_before_replacing_either_file(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    graph_path = tmp_path / "needs.json"
+    index_path = tmp_path / "generated-index.lua"
+    graph_path.write_text("old graph\n", encoding="utf-8")
+    index_path.write_text("old index\n", encoding="utf-8")
+
+    def fail_lua_render(snapshot: AnalysisSnapshot) -> str:
+        raise TypeError("unsupported Lua index value")
+
+    monkeypatch.setattr("quarto_needs.export.render_lua_index", fail_lua_render)
+    with pytest.raises(TypeError, match="unsupported Lua index value"):
+        write_build_outputs(graph_path, index_path, canonical_snapshot())
+    assert graph_path.read_text(encoding="utf-8") == "old graph\n"
+    assert index_path.read_text(encoding="utf-8") == "old index\n"
+
+
+def test_lua_index_escapes_control_characters() -> None:
+    result = analyze_objects(
+        [
+            EngineeringObject(
+                'ID"\\',
+                "test-case",
+                "line one\nline two\rline three",
+                status='pa"ssed',
+            )
+        ]
+    )
+    assert result.snapshot is not None
+    rendered = render_lua_index(result.snapshot)
+    assert '["ID\\"\\\\"]' in rendered
+    assert 'title = "line one\\nline two\\rline three"' in rendered
+    assert 'status = "pa\\"ssed"' in rendered
+
+
+def test_coverage_keeps_exact_legacy_six_key_projection() -> None:
+    result = coverage(
+        [EngineeringObject("REQ-1", "functional-requirement", "Login")]
+    )
+    assert set(result) == {
+        "requirements",
+        "approved",
+        "implemented",
+        "verified",
+        "implementation_coverage",
+        "verification_coverage",
+    }
+
+
+@pytest.mark.parametrize("writer", [export_graph, export_lua_index])
+def test_compatibility_writers_do_not_touch_invalid_destination(
+    tmp_path: Path, writer: object
+) -> None:
+    destination = tmp_path / "existing-output"
+    destination.write_text("sentinel\n", encoding="utf-8")
+    duplicates = [
+        EngineeringObject("DUP-1", "functional-requirement", "First"),
+        EngineeringObject("DUP-1", "functional-requirement", "Second"),
+    ]
+
+    with pytest.raises(
+        ValueError,
+        match="^Cannot export a structurally invalid requirements graph$",
+    ):
+        if writer is export_graph:
+            export_graph(destination, duplicates, [])
+        else:
+            export_lua_index(destination, duplicates)
+    assert destination.read_text(encoding="utf-8") == "sentinel\n"
+
+
+def test_canonical_fixture_matches_checked_in_bytes() -> None:
+    snapshot = canonical_snapshot()
+    assert render_v1_json(snapshot) == (
+        FIXTURE / "expected-needs-v1.json"
+    ).read_text(encoding="utf-8")
+    assert render_lua_index(snapshot) == (
+        FIXTURE / "expected-generated-index.lua"
+    ).read_text(encoding="utf-8")
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/tests/test_v1_contract.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/tests/test_v1_contract.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-before/tests/test_v1_contract.py	2026-08-25 10:11:17.264378170 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-6-after/tests/test_v1_contract.py	2026-08-25 10:25:05.666501885 -0300
@@ -5,6 +5,9 @@
 
 from jsonschema import Draft202012Validator, RefResolver
 
+from quarto_needs.analysis import analyze_project
+from quarto_needs.export import render_v1_json
+
 ROOT = Path(__file__).resolve().parents[1]
 SCHEMAS = ROOT / "schemas"
 GOLDEN = ROOT / "tests/fixtures/v1/aegis-needs-v1.json"
@@ -64,3 +67,11 @@
     nested = [relation for item in payload["objects"] for relation in item.get("relations", [])]
     key = lambda relation: json.dumps(relation, ensure_ascii=False, sort_keys=True)
     assert sorted(nested, key=key) == sorted(payload["relations"], key=key)
+
+
+def test_refactored_aegis_export_preserves_v1_semantics() -> None:
+    frozen = load_json(GOLDEN)
+    result = analyze_project(ROOT / "examples/book")
+    assert result.snapshot is not None
+    current = json.loads(render_v1_json(result.snapshot))
+    assert legacy_projection(current) == legacy_projection(frozen)
