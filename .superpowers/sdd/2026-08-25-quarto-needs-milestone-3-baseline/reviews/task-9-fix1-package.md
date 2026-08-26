# Review package

Snapshot range: `task-10-after` -> `task-9-fix1`

## Files changed (3)

- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `src/quarto_needs/impact.py`
- `tests/test_impact.py`

## Summary

54 lines added, 14 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 10:32:49.309293383 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 11:07:25.490393614 -0300
@@ -2721,20 +2721,34 @@
         'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
     )
     snapshot, config = snapshot_of(tmp_path)
 
     with pytest.raises(impact.ImpactError):
         impact.analyze(before, snapshot, config)
 
     assert impact.analyze(before, snapshot, config, recompute=True) is not None
 
 
+def test_impact_rejects_a_reference_date_mismatch_without_recompute(tmp_path: Path) -> None:
+    """The reference date is a comparison axis for impact too (spec: impact
+    rejects the mismatch)."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    before = {**before, "referenceDate": "1999-01-01"}
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(impact.ImpactError):
+        impact.analyze(before, snapshot, config)
+
+    assert impact.analyze(before, snapshot, config, recompute=True) is not None
+
+
 def test_impact_rejects_a_diagnostic_baseline(tmp_path: Path) -> None:
     write(tmp_path)
     snapshot, config = snapshot_of(tmp_path)
 
     with pytest.raises(impact.ImpactError):
         impact.analyze({"schemaVersion": "1", "valid": False}, snapshot, config)
 ```
 
 - [ ] **Step 2: Run them and verify they fail**
 
@@ -2848,27 +2862,33 @@
     baseline_payload: Mapping[str, object],
     snapshot: AnalysisSnapshot,
     config: NeedsConfig,
     *,
     recompute: bool = False,
 ) -> ImpactReport:
     if not baseline_payload.get("valid", False):
         raise ImpactError(
             "This baseline is a diagnostic artifact (valid: false) and cannot be traversed"
         )
-    if not recompute and str(
-        baseline_payload.get("configurationFingerprint", "")
-    ) != snapshot.configuration_fingerprint:
-        raise ImpactError(
-            "The baseline was produced under a different configuration; "
-            "pass --recompute-with current so one relation policy governs the traversal"
-        )
+    if not recompute:
+        if str(
+            baseline_payload.get("configurationFingerprint", "")
+        ) != snapshot.configuration_fingerprint:
+            raise ImpactError(
+                "The baseline was produced under a different configuration; "
+                "pass --recompute-with current so one relation policy governs the traversal"
+            )
+        if str(baseline_payload.get("referenceDate", "")) != snapshot.reference_date:
+            raise ImpactError(
+                "The baseline was produced under a different reference date; "
+                "pass --recompute-with current to traverse under the current date"
+            )
 
     report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
     origins = _origins(report)
     adjacency = _union_edges(baseline_payload.get("relations", []), snapshot)
     baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
     origin_ids = {str(item["id"]) for item in origins}
 
     impacted: dict[tuple[str, str], dict[str, object]] = {}
     for origin in origins:
         start = str(origin["id"])
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/src/quarto_needs/impact.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-fix1/src/quarto_needs/impact.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/src/quarto_needs/impact.py	2026-08-26 10:42:25.512824469 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-fix1/src/quarto_needs/impact.py	2026-08-26 11:09:11.590243064 -0300
@@ -101,27 +101,33 @@
     baseline_payload: Mapping[str, object],
     snapshot: AnalysisSnapshot,
     config: NeedsConfig,
     *,
     recompute: bool = False,
 ) -> ImpactReport:
     if not baseline_payload.get("valid", False):
         raise ImpactError(
             "This baseline is a diagnostic artifact (valid: false) and cannot be traversed"
         )
-    if not recompute and str(
-        baseline_payload.get("configurationFingerprint", "")
-    ) != snapshot.configuration_fingerprint:
-        raise ImpactError(
-            "The baseline was produced under a different configuration; "
-            "pass --recompute-with current so one relation policy governs the traversal"
-        )
+    if not recompute:
+        if str(
+            baseline_payload.get("configurationFingerprint", "")
+        ) != snapshot.configuration_fingerprint:
+            raise ImpactError(
+                "The baseline was produced under a different configuration; "
+                "pass --recompute-with current so one relation policy governs the traversal"
+            )
+        if str(baseline_payload.get("referenceDate", "")) != snapshot.reference_date:
+            raise ImpactError(
+                "The baseline was produced under a different reference date; "
+                "pass --recompute-with current to traverse under the current date"
+            )
 
     report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
     origins = _origins(report)
     adjacency = _union_edges(baseline_payload.get("relations", []), snapshot)
     baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
     origin_ids = {str(item["id"]) for item in origins}
 
     impacted: dict[tuple[str, str], dict[str, object]] = {}
     for origin in origins:
         start = str(origin["id"])
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/tests/test_impact.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-fix1/tests/test_impact.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/tests/test_impact.py	2026-08-26 10:34:05.789206103 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-fix1/tests/test_impact.py	2026-08-26 11:08:49.858273901 -0300
@@ -150,16 +150,30 @@
         'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
     )
     snapshot, config = snapshot_of(tmp_path)
 
     with pytest.raises(impact.ImpactError):
         impact.analyze(before, snapshot, config)
 
     assert impact.analyze(before, snapshot, config, recompute=True) is not None
 
 
+def test_impact_rejects_a_reference_date_mismatch_without_recompute(tmp_path: Path) -> None:
+    """The reference date is a comparison axis for impact too (spec: impact
+    rejects the mismatch)."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    before = {**before, "referenceDate": "1999-01-01"}
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(impact.ImpactError):
+        impact.analyze(before, snapshot, config)
+
+    assert impact.analyze(before, snapshot, config, recompute=True) is not None
+
+
 def test_impact_rejects_a_diagnostic_baseline(tmp_path: Path) -> None:
     write(tmp_path)
     snapshot, config = snapshot_of(tmp_path)
 
     with pytest.raises(impact.ImpactError):
         impact.analyze({"schemaVersion": "1", "valid": False}, snapshot, config)
```
