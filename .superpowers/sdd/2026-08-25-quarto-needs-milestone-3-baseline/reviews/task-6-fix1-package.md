# Review package

Snapshot range: `task-6-after` -> `task-6-fix1`

## Files changed (4)

- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md`
- `src/quarto_needs/diff.py`
- `tests/test_diff.py`

## Summary

90 lines added, 18 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 02:03:22.863211465 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 09:41:24.030092148 -0300
@@ -1639,20 +1639,52 @@
     before = baseline_of(tmp_path)
     before = {**before, "referenceDate": "1999-01-01"}
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config, recompute=True)
 
     assert report.notices == ()
     assert report.recomputed is True
 
 
+def test_recompute_does_not_manufacture_derived_deltas_from_a_config_change(tmp_path: Path) -> None:
+    """The baseline stores its derived results; they cannot be re-derived, so a
+    config-only change must stay silent even under recompute.
+
+    REQ-2 is approved but unverified, so verification coverage is 1 of 2 (50%).
+    The baseline is taken under the default configuration (no verification
+    gate); only then does the configuration grow a 100.0 threshold. Authored
+    content never moves — any derived delta is manufactured by the config edit.
+    """
+    write(tmp_path)
+    (tmp_path / "extra.qmd").write_text(
+        "::: {.need #REQ-2 type=system-requirement status=approved priority=low}\n"
+        "\n## Second\nSecond body.\n"
+        "\n### Rationale\nSecond why.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        "[gates]\nmin-verification-trace = 100.0\n", encoding="utf-8"
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config, recompute=True)
+
+    assert report.notices == ()
+    assert report.modified == ()
+    assert report.gate_regressions == ()
+    assert report.metric_deltas == ()
+    assert report.findings_added == ()
+
+
 def test_configuration_change_still_compares_authored_relations(tmp_path: Path) -> None:
     """Authored comparison keeps running; only the derived deltas stop."""
     write(tmp_path)
     before = baseline_of(tmp_path)
     (tmp_path / ".quarto-needs.toml").write_text('profile = "strict"\n', encoding="utf-8")
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     assert "configuration-changed" in report.notices
@@ -2127,48 +2159,52 @@
         raise DiffError(
             "This baseline is a diagnostic artifact (valid: false) and cannot be compared; "
             "use `baseline inspect` to read it"
         )
 
     current_configuration = snapshot.configuration_fingerprint
     baseline_configuration = str(baseline_payload.get("configurationFingerprint", ""))
     baseline_date = str(baseline_payload.get("referenceDate", ""))
 
     notices: list[str] = []
+    configuration_differs = baseline_configuration != current_configuration
+    date_differs = baseline_date != snapshot.reference_date
     if not recompute:
-        if baseline_configuration != current_configuration:
+        if configuration_differs:
             notices.append("configuration-changed")
-        if baseline_date != snapshot.reference_date:
+        if date_differs:
             notices.append("reference-date-changed")
 
     added, removed, modified, relocated = _classify_objects(
         _baseline_objects(baseline_payload),
         {record.id: _current_object(record) for record in snapshot.objects},
     )
 
     baseline_relations = list(baseline_payload.get("relations", []))
     if recompute:
         baseline_relations = _recomputed_relations(baseline_relations)
     # A catalog change can move families and roles, so semantic fingerprints
     # from the two sides stop being comparable. Fall back to authored tuples,
     # which is exactly what the spec prescribes for this case.
     relation_key = (
         "authoredFingerprint" if "configuration-changed" in notices else "semanticFingerprint"
     )
     added_relations, removed_relations, representation = _classify_relations(
         baseline_relations, _current_relations(snapshot), key=relation_key
     )
 
-    # Derived results were computed under different rules or a different date,
-    # so their deltas describe the inputs, not the project. Suppress them and
-    # say why; `--recompute-with current` is the way to get them back.
-    derived_suppressed = bool(notices)
+    # Derived results are stored in the baseline, never re-derived, so they are
+    # comparable only when both sides were produced under the same rules and
+    # the same reference date. `recompute` re-resolves authored relations
+    # through the current catalog; it cannot make stored findings, metrics, or
+    # gates comparable, so their deltas stay suppressed silently there.
+    derived_suppressed = configuration_differs or date_differs
     if derived_suppressed:
         findings_added: tuple[dict[str, object], ...] = ()
         findings_removed: tuple[dict[str, object], ...] = ()
         metric_deltas: tuple[dict[str, object], ...] = ()
         gate_regressions: tuple[dict[str, object], ...] = ()
     else:
         current_report = report_from_snapshot(snapshot, config).to_dict()
         baseline_report = baseline_payload.get("report", {})
         findings_added, findings_removed = _classify_findings(
             baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
@@ -2194,21 +2230,21 @@
         gate_regressions=gate_regressions,
     )
 ```
 
 Note the deliberate asymmetry: a configuration change still reports **authored** object and relation changes, exactly as the spec requires ("default `diff` compares authored object content and authored relation tuples only"). Only the derived categories are suppressed.
 
 - [ ] **Step 5: Run the diff tests**
 
 Run: `.venv/bin/python -m pytest tests/test_diff.py -q`
 
-Expected: PASS, all fifteen.
+Expected: PASS, all sixteen.
 
 - [ ] **Step 6: Run the full suite**
 
 Run: `.venv/bin/python -m pytest -q`
 
 Expected: PASS, no warnings.
 
 - [ ] **Step 7: Record the checkpoint conditionally**
 
 ```bash
@@ -2414,21 +2450,21 @@
 
 Add `from . import diff as diff_module` to the imports.
 
 - [ ] **Step 5: Implement the handler**
 
 Add above `main`:
 
 ```python
 def _print_diff_text(report) -> None:
     for notice in report.notices:
-        print(f"[notice] {notice}: derived deltas suppressed; pass --recompute-with current to compare them")
+        print(f"[notice] {notice}: derived deltas suppressed; both sides must share configuration and reference date to compare them")
     if report.is_empty():
         print("No changes.")
         return
     for object_id in report.added_objects:
         print(f"+ object {object_id}")
     for object_id in report.removed_objects:
         print(f"- object {object_id}")
     for item in report.modified:
         print(f"~ object {item['id']} ({', '.join(item['fields'])})")
     for item in report.relocated:
@@ -3219,21 +3255,21 @@
 
 - [ ] **Step 6: Document the commands in the README**
 
 Extend the `## Commands` block with the three new entries and add a `### Baseline, diff, and impact` section after the configuration reference. It must state:
 
 - `baseline create` writes `baselines/quarto-needs.json`, refuses to overwrite without `--force`, and refuses a structurally invalid project unless `--allow-invalid` is given;
 - `--allow-invalid` produces a diagnostic artifact marked `valid: false` that only `baseline inspect` accepts — `diff` and `impact` reject it, because duplicate IDs make comparison ambiguous;
 - `diff` classifies added/removed objects, modifications by field, added/removed relations, relocation, and findings/metrics/gate regressions; a changed ID is reported as a removal plus an addition because rename detection is heuristic and deliberately excluded;
 - **relocation is keyed on the declaring file** — a line-only shift produces no record;
 - an authored alias flip (`verified-by` to `verifies`) that preserves endpoint roles is a representation change, never a relation addition or removal;
-- the two guards: a changed configuration fingerprint or reference date emits `configuration-changed` / `reference-date-changed` and suppresses derived deltas, and `--recompute-with current` re-evaluates both sides;
+- the two guards: a changed configuration fingerprint or reference date emits `configuration-changed` / `reference-date-changed` and suppresses derived deltas; `--recompute-with current` re-resolves the baseline's authored relations through the current catalog so semantic comparison is valid again, while derived deltas stay suppressed until both sides are produced under the same configuration and reference date;
 - `impact` traverses the union of both graphs so removed nodes stay explainable, follows each relation's catalog `impactDirection`, and gives every result an explicit path, distance, classification, and priority — there is no risk score;
 - determinism means byte-identical output for a fixed configuration **and** a fixed reference date; `SOURCE_DATE_EPOCH` fixes the latter.
 
 - [ ] **Step 7: Update the pipeline diagram**
 
 In `ARCHITECTURE.md`, extend the canonical pipeline block:
 
 ```text
 AnalysisSnapshot -> fingerprints -> baselines/quarto-needs.json
                                           |
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-fix1/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md	2026-08-25 16:24:03.641108789 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-fix1/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md	2026-08-26 02:28:58.028504270 -0300
@@ -163,27 +163,27 @@
 - added and removed objects;
 - semantic modifications by field;
 - added and removed relations;
 - source relocation without semantic change;
 - findings, metrics, and gate regressions.
 
 Automatic rename detection is excluded from the initial release because it is inherently heuristic. A changed ID is reported as removal plus addition.
 
 Impact analysis traverses the union of the before and after graphs so removed nodes and edges remain explainable. Every impacted result includes the originating change, direct or transitive classification, distance, traversed relations, path, and configured priority. The first implementation does not invent an opaque risk score; paths and policy decisions remain auditable.
 
-Snapshots store a configuration fingerprint: SHA-256 over the canonical merged configuration, embedded defaults, relation-catalog version, and rule-set version, excluding the configuration file's path. When fingerprints differ, default `diff` compares authored object content and authored relation tuples only, emits `configuration-changed`, and suppresses semantic-relation, finding, metric, and gate deltas. This prevents a catalog-only family/role change from appearing as a project edge removal/addition. `diff --recompute-with current` re-evaluates both snapshots under the current configuration before comparing semantic and derived results. `impact` rejects mismatched configuration fingerprints unless the same recomputation option is supplied, ensuring one relation policy governs the entire traversal.
+Snapshots store a configuration fingerprint: SHA-256 over the canonical merged configuration, embedded defaults, relation-catalog version, and rule-set version, excluding the configuration file's path. When fingerprints differ, default `diff` compares authored object content and authored relation tuples only, emits `configuration-changed`, and suppresses semantic-relation, finding, metric, and gate deltas. This prevents a catalog-only family/role change from appearing as a project edge removal/addition. `diff --recompute-with current` re-evaluates the baseline's authored relations through the current catalog so semantic comparison is valid again; the baseline's stored derived results (findings, metrics, gates) are never re-derived, so those deltas stay suppressed until both sides are produced under the same configuration and reference date. `impact` rejects mismatched configuration fingerprints unless the same recomputation option is supplied, ensuring one relation policy governs the entire traversal.
 
 ### Milestone 3 design decisions
 
 The following three decisions refine the contract above without altering it. Each was open because this specification did not address it.
 
-**The reference date is a first-class comparison axis.** `reference_date()` is a semantic input, not formatting metadata: evidence expiry (REQ015) and evidence coverage both depend on it, so an unchanged project legitimately reports different coverage on different days. A baseline therefore records the reference date it was computed under, alongside its configuration fingerprint. When the two differ, `diff` emits `reference-date-changed` and suppresses the date-derived deltas — evidence coverage and REQ015 findings — exactly as it does for a changed configuration fingerprint, and `impact` rejects the mismatch. `diff --recompute-with current` re-evaluates both snapshots under the current reference date. Determinism is consequently defined as byte-identical output for a fixed configuration and a fixed reference date; `SOURCE_DATE_EPOCH` remains the way to fix the latter. Fingerprints continue to exclude the reference date, which is an input to derived data rather than authored content.
+**The reference date is a first-class comparison axis.** `reference_date()` is a semantic input, not formatting metadata: evidence expiry (REQ015) and evidence coverage both depend on it, so an unchanged project legitimately reports different coverage on different days. A baseline therefore records the reference date it was computed under, alongside its configuration fingerprint. When the two differ, `diff` emits `reference-date-changed` and suppresses the date-derived deltas — evidence coverage and REQ015 findings — exactly as it does for a changed configuration fingerprint, and `impact` rejects the mismatch. As with a configuration change, `--recompute-with current` re-resolves the baseline's authored relations but cannot re-derive its stored date-derived results, so those deltas stay suppressed until both sides share a reference date. Determinism is consequently defined as byte-identical output for a fixed configuration and a fixed reference date; `SOURCE_DATE_EPOCH` remains the way to fix the latter. Fingerprints continue to exclude the reference date, which is an input to derived data rather than authored content.
 
 This is distinct from the exporter rule on wall-clock timestamps. That rule governs formatting metadata, which is omitted or pinned to `SOURCE_DATE_EPOCH` with a `1970-01-01T00:00:00Z` fallback. The reference date is an analysis input whose value changes results, so it is recorded and compared rather than omitted; a 1970 fallback would make every expiry check meaningless.
 
 **Relocation is keyed on the declaring file.** A relocation record is emitted when an object's declaring file changes, and it carries the file and line before and after. A line-only shift within the same file produces no record: fingerprints already exclude line numbers, and emitting a record for every object below an inserted paragraph would make relocation the loudest and least informative category in the diff. Moving a need between pages is an authored fact; being pushed down three lines is not.
 
 **Baseline creation refuses to overwrite.** `baseline create` fails with exit code 2 when its destination already exists, unless `--force` is supplied. An accidentally overwritten baseline is unrecoverable without version control, which this project does not assume.
 
 ## Quarto experience
 
 Python writes the precomputed projection. Lua loads and caches it per Pandoc process, resolves links according to the output format, and creates semantic Pandoc AST. Local JavaScript progressively enhances only HTML.
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/src/quarto_needs/diff.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-fix1/src/quarto_needs/diff.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/src/quarto_needs/diff.py	2026-08-26 02:06:00.838941317 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-fix1/src/quarto_needs/diff.py	2026-08-26 09:45:41.582023649 -0300
@@ -1,20 +1,20 @@
 """Classified comparison between a baseline and the current snapshot.
 
 Two guards run before any comparison. A changed configuration or a changed
 reference date means the derived numbers were produced under different rules,
 so reporting their deltas as project changes would be a lie; the diff says so
 and suppresses them instead.
 """
 from __future__ import annotations
 
-from dataclasses import dataclass, field
+from dataclasses import dataclass
 from typing import Mapping, Sequence
 
 from . import fingerprints
 from .config import NeedsConfig
 from .quality import report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
 SCHEMA_VERSION = "1"
 
 OBJECT_FIELDS = ("type", "title", "status", "body", "rationale", "attributes")
@@ -310,48 +310,52 @@
         raise DiffError(
             "This baseline is a diagnostic artifact (valid: false) and cannot be compared; "
             "use `baseline inspect` to read it"
         )
 
     current_configuration = snapshot.configuration_fingerprint
     baseline_configuration = str(baseline_payload.get("configurationFingerprint", ""))
     baseline_date = str(baseline_payload.get("referenceDate", ""))
 
     notices: list[str] = []
+    configuration_differs = baseline_configuration != current_configuration
+    date_differs = baseline_date != snapshot.reference_date
     if not recompute:
-        if baseline_configuration != current_configuration:
+        if configuration_differs:
             notices.append("configuration-changed")
-        if baseline_date != snapshot.reference_date:
+        if date_differs:
             notices.append("reference-date-changed")
 
     added, removed, modified, relocated = _classify_objects(
         _baseline_objects(baseline_payload),
         {record.id: _current_object(record) for record in snapshot.objects},
     )
 
     baseline_relations = list(baseline_payload.get("relations", []))
     if recompute:
         baseline_relations = _recomputed_relations(baseline_relations)
     # A catalog change can move families and roles, so semantic fingerprints
     # from the two sides stop being comparable. Fall back to authored tuples,
     # which is exactly what the spec prescribes for this case.
     relation_key = (
         "authoredFingerprint" if "configuration-changed" in notices else "semanticFingerprint"
     )
     added_relations, removed_relations, representation = _classify_relations(
         baseline_relations, _current_relations(snapshot), key=relation_key
     )
 
-    # Derived results were computed under different rules or a different date,
-    # so their deltas describe the inputs, not the project. Suppress them and
-    # say why; `--recompute-with current` is the way to get them back.
-    derived_suppressed = bool(notices)
+    # Derived results are stored in the baseline, never re-derived, so they are
+    # comparable only when both sides were produced under the same rules and
+    # the same reference date. `recompute` re-resolves authored relations
+    # through the current catalog; it cannot make stored findings, metrics, or
+    # gates comparable, so their deltas stay suppressed silently there.
+    derived_suppressed = configuration_differs or date_differs
     if derived_suppressed:
         findings_added: tuple[dict[str, object], ...] = ()
         findings_removed: tuple[dict[str, object], ...] = ()
         metric_deltas: tuple[dict[str, object], ...] = ()
         gate_regressions: tuple[dict[str, object], ...] = ()
     else:
         current_report = report_from_snapshot(snapshot, config).to_dict()
         baseline_report = baseline_payload.get("report", {})
         findings_added, findings_removed = _classify_findings(
             baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/tests/test_diff.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-fix1/tests/test_diff.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/tests/test_diff.py	2026-08-26 02:05:08.719030445 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-fix1/tests/test_diff.py	2026-08-26 09:40:42.266829023 -0300
@@ -166,20 +166,52 @@
     before = baseline_of(tmp_path)
     before = {**before, "referenceDate": "1999-01-01"}
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config, recompute=True)
 
     assert report.notices == ()
     assert report.recomputed is True
 
 
+def test_recompute_does_not_manufacture_derived_deltas_from_a_config_change(tmp_path: Path) -> None:
+    """The baseline stores its derived results; they cannot be re-derived, so a
+    config-only change must stay silent even under recompute.
+
+    REQ-2 is approved but unverified, so verification coverage is 1 of 2 (50%).
+    The baseline is taken under the default configuration (no verification
+    gate); only then does the configuration grow a 100.0 threshold. Authored
+    content never moves — any derived delta is manufactured by the config edit.
+    """
+    write(tmp_path)
+    (tmp_path / "extra.qmd").write_text(
+        "::: {.need #REQ-2 type=system-requirement status=approved priority=low}\n"
+        "\n## Second\nSecond body.\n"
+        "\n### Rationale\nSecond why.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        "[gates]\nmin-verification-trace = 100.0\n", encoding="utf-8"
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config, recompute=True)
+
+    assert report.notices == ()
+    assert report.modified == ()
+    assert report.gate_regressions == ()
+    assert report.metric_deltas == ()
+    assert report.findings_added == ()
+
+
 def test_configuration_change_still_compares_authored_relations(tmp_path: Path) -> None:
     """Authored comparison keeps running; only the derived deltas stop."""
     write(tmp_path)
     before = baseline_of(tmp_path)
     (tmp_path / ".quarto-needs.toml").write_text('profile = "strict"\n', encoding="utf-8")
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     assert "configuration-changed" in report.notices
```
