diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-fix1-before/analysis.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-fix1-after/analysis.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-fix1-before/analysis.py	2026-08-25 10:04:35.917453236 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-fix1-after/analysis.py	2026-08-25 10:09:48.668610617 -0300
@@ -60,6 +60,28 @@
     )
 
 
+def _analysis_finding_key(item: Finding) -> tuple[object, ...]:
+    location = item.location
+    anchor = location.anchor if location is not None else None
+    properties = json.dumps(
+        thaw_json(item.properties),
+        ensure_ascii=False,
+        sort_keys=True,
+        separators=(",", ":"),
+    )
+    return (
+        *finding_key(item),
+        item.severity.casefold(),
+        item.severity,
+        item.object_id is not None,
+        location is not None,
+        anchor is not None,
+        (anchor or "").casefold(),
+        anchor or "",
+        properties,
+    )
+
+
 def legacy_coverage(
     objects: tuple[ObjectRecord, ...],
     relations: tuple[RelationRecord, ...],
@@ -190,11 +212,14 @@
 
 def _merge_findings(*groups: Iterable[Finding]) -> tuple[Finding, ...]:
     merged: list[Finding] = []
+    seen: set[tuple[object, ...]] = set()
     for group in groups:
         for finding in group:
-            if finding not in merged:
+            key = _analysis_finding_key(finding)
+            if key not in seen:
+                seen.add(key)
                 merged.append(finding)
-    return tuple(sorted(merged, key=finding_key))
+    return tuple(sorted(merged, key=_analysis_finding_key))
 
 
 def _records(
@@ -298,7 +323,26 @@
     root: Path,
     files: Iterable[Path] | None = None,
 ) -> AnalysisResult:
-    return _analyze_batch(parse_project_declarations(root, files))
+    if files is None:
+        selected = None
+    else:
+        resolved_root = root.resolve()
+        unique: set[Path] = set()
+        for path in files:
+            if path.is_absolute():
+                resolved = path.resolve()
+            else:
+                resolved = path.resolve()
+                if not resolved.is_relative_to(resolved_root):
+                    resolved = (resolved_root / path).resolve()
+            unique.add(resolved)
+        selected = tuple(
+            sorted(
+                unique,
+                key=lambda path: (path.as_posix().casefold(), path.as_posix()),
+            )
+        )
+    return _analyze_batch(parse_project_declarations(root, selected))
 
 
 def analyze_objects(
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-fix1-before/test_analysis.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-fix1-after/test_analysis.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-fix1-before/test_analysis.py	2026-08-25 10:04:35.917453236 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-fix1-after/test_analysis.py	2026-08-25 10:09:48.668610617 -0300
@@ -8,6 +8,7 @@
 from quarto_needs.diagnostics import Finding
 from quarto_needs.model import EngineeringObject, Relation
 from quarto_needs.relations import DEFAULT_RELATION_CATALOG
+from quarto_needs.snapshot import LocationRecord, thaw_json
 
 
 ROOT = Path(__file__).resolve().parents[1]
@@ -117,6 +118,28 @@
     assert reads == Counter({item.resolve(): 1 for item in selected})
 
 
+def test_analysis_deduplicates_repeated_selected_source(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    root = ROOT / "tests/fixtures/canonical"
+    source = root / "a-tests.qmd"
+    reads: Counter[Path] = Counter()
+    original = Path.read_text
+
+    def counted(path: Path, *args: object, **kwargs: object) -> str:
+        if path.resolve() == source.resolve():
+            reads[path.resolve()] += 1
+        return original(path, *args, **kwargs)
+
+    monkeypatch.setattr(Path, "read_text", counted)
+
+    result = analyze_project(root, files=[source, source])
+
+    assert result.snapshot is not None
+    assert [item.id for item in result.declarations] == ["Z-TC-001"]
+    assert reads == Counter({source.resolve(): 1})
+
+
 def test_source_less_legacy_object_keeps_empty_location_and_provenance() -> None:
     legacy = EngineeringObject(
         "REQ-1",
@@ -198,3 +221,68 @@
         ("REQ007", "Unsupported relation type custom-link on REQ-1"),
         ("INFO001", "Preserved"),
     ]
+
+
+def test_finding_order_includes_anchor_and_canonical_properties() -> None:
+    legacy = EngineeringObject("REQ-1", "need", "Canonical findings")
+    findings = [
+        Finding(
+            "CUSTOM001",
+            "warning",
+            "Same message",
+            "REQ-1",
+            LocationRecord("source.qmd", 4, "z-anchor"),
+            {"nested": {"rank": 1}},
+        ),
+        Finding(
+            "CUSTOM001",
+            "warning",
+            "Same message",
+            "REQ-1",
+            LocationRecord("source.qmd", 4, "a-anchor"),
+            {"nested": {"rank": 2}},
+        ),
+        Finding(
+            "CUSTOM001",
+            "warning",
+            "Same message",
+            "REQ-1",
+            LocationRecord("source.qmd", 4, "a-anchor"),
+            {"nested": {"rank": 1}},
+        ),
+        Finding(
+            "CUSTOM001",
+            "warning",
+            "Same message",
+            "REQ-1",
+            LocationRecord("source.qmd", 4, "m-anchor"),
+            {"kind": True},
+        ),
+        Finding(
+            "CUSTOM001",
+            "warning",
+            "Same message",
+            "REQ-1",
+            LocationRecord("source.qmd", 4, "m-anchor"),
+            {"kind": 1},
+        ),
+    ]
+
+    forward = analyze_objects([legacy], reported_findings=findings)
+    reverse = analyze_objects([legacy], reported_findings=reversed(findings))
+
+    assert forward.snapshot == reverse.snapshot
+    assert forward.snapshot is not None
+    assert [
+        (
+            item.location.anchor if item.location else None,
+            thaw_json(item.properties),
+        )
+        for item in forward.findings
+    ] == [
+        ("a-anchor", {"nested": {"rank": 1}}),
+        ("a-anchor", {"nested": {"rank": 2}}),
+        ("m-anchor", {"kind": 1}),
+        ("m-anchor", {"kind": True}),
+        ("z-anchor", {"nested": {"rank": 1}}),
+    ]
