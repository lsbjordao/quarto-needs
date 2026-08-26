# Review package

Snapshot range: `task-1-before` -> `task-1-after`

## Files changed (3)

- `README.md`
- `src/quarto_needs/cli.py`
- `tests/test_cli.py`

## Summary

83 lines added, 27 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-before/README.md .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-after/README.md
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-before/README.md	2026-08-26 13:11:57.574904299 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-after/README.md	2026-08-26 14:57:44.151729746 -0300
@@ -372,20 +372,23 @@
 ### Profiles and exit codes
 
 | Profile | Structural failure | Semantic gate failure |
 |---|---|---|
 | `advisory` | 1 | 0 |
 | `default` | 1 | 0 (reported, not enforced) |
 | `strict` | 1 | 1 |
 
 A broken configuration exits 2 from every command.
 
+- `3`: operational failure — an artifact could not be read or written. The
+  message names the artifact; anything already written is left in place.
+
 ### Baseline, diff, and impact
 
 `baseline create` snapshots the current graph — objects, authored relations,
 findings, and the projected report — into `baselines/quarto-needs.json`. It
 refuses to overwrite an existing baseline unless `--force` is given, and it
 refuses to write anything for a structurally invalid project unless
 `--allow-invalid` is given. That flag produces a diagnostic artifact marked
 `valid: false`; only `baseline inspect` accepts it. `diff` and `impact`
 reject it outright, because duplicate IDs make it ambiguous which object a
 comparison would even be comparing.
@@ -421,21 +424,25 @@
 the baseline's authored relations through the *current* relation catalog, so
 semantic comparison is meaningful again after a catalog upgrade — but
 derived deltas stay suppressed until both sides are produced under the same
 configuration and the same reference date.
 
 `impact <baseline>` traverses the union of the baseline and current graphs,
 so a removed node or edge stays explainable instead of disappearing, and
 follows each relation's catalog `impactDirection`. Every result carries an
 explicit path, a distance, a classification (`direct` or `transitive`), and
 a priority; there is deliberately no risk score, since a single number would
-hide the path that justifies it.
+hide the path that justifies it. `impact` refuses a baseline whose
+configuration fingerprint or reference date differs from the current run
+unless `--recompute-with current` is supplied, so one policy always governs
+a traversal; under that flag, derived deltas remain suppressed, exactly as
+in `diff`.
 
 Determinism means byte-identical output for a fixed configuration **and** a
 fixed reference date. `SOURCE_DATE_EPOCH` (interpreted in UTC) fixes the
 latter; left unset, the reference date is today, which is why diffing
 against yesterday's baseline the next morning reports
 `reference-date-changed` even when the project itself has not moved.
 
 ## Commands
 
 ```bash
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-before/src/quarto_needs/cli.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-after/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-before/src/quarto_needs/cli.py	2026-08-26 14:41:42.633325987 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-after/src/quarto_needs/cli.py	2026-08-26 14:57:25.411751117 -0300
@@ -60,46 +60,52 @@
     return sorted(seen, key=lambda item: (item.casefold(), item))
 
 
 def build(root: Path, quiet: bool = False) -> int:
     try:
         config = load_config(root)
     except ValueError as error:
         if not quiet:
             print(f"Configuration error: {error}", file=sys.stderr)
         return 2
-    result = analyze_project(root, config=config)
-    if result.snapshot is None:
-        if not quiet:
-            print_findings(result.findings, stream=sys.stderr)
-        return 1
-    queries = materialize_queries(config, result.snapshot)
-    # The Lua dashboard reads only what Python projects here, so a configured
-    # project ships its materialized queries and its precomputed report.
-    extra_extensions = (
-        {
-            "quartoNeeds": {
-                "queries": {name: list(queries[name]) for name in sorted(queries)},
-                "report": report_from_snapshot(
-                    result.snapshot, config, queries=queries
-                ).to_dict(),
+    try:
+        result = analyze_project(root, config=config)
+        if result.snapshot is None:
+            if not quiet:
+                print_findings(result.findings, stream=sys.stderr)
+            return 1
+        queries = materialize_queries(config, result.snapshot)
+        # The Lua dashboard reads only what Python projects here, so a configured
+        # project ships its materialized queries and its precomputed report.
+        extra_extensions = (
+            {
+                "quartoNeeds": {
+                    "queries": {name: list(queries[name]) for name in sorted(queries)},
+                    "report": report_from_snapshot(
+                        result.snapshot, config, queries=queries
+                    ).to_dict(),
+                }
             }
-        }
-        if config.present
-        else None
-    )
-    write_build_outputs(
-        root / ".quarto-needs" / "needs.json",
-        root / "_extensions" / "quarto-needs" / "generated-index.lua",
-        result.snapshot,
-        extra_extensions=extra_extensions,
-    )
+            if config.present
+            else None
+        )
+        write_build_outputs(
+            root / ".quarto-needs" / "needs.json",
+            root / "_extensions" / "quarto-needs" / "generated-index.lua",
+            result.snapshot,
+            extra_extensions=extra_extensions,
+        )
+    except OSError as error:
+        # Reading the project or writing either artifact failed; both are
+        # operational, not validation, failures.
+        print(f"Could not scan {root}: {error}", file=sys.stderr)
+        return 3
     if not quiet:
         metrics = result.snapshot.metrics
         print(
             f"Quarto-Needs: {len(result.snapshot.objects)} objects, "
             f"{len(result.findings)} findings"
         )
         print(
             f"Requirements: {metrics['requirements']} | "
             f"implemented: {metrics['implementation_coverage']}% | "
             f"verified: {metrics['verification_coverage']}%"
@@ -457,17 +463,22 @@
             print(f"Unknown object: {args.id}", file=sys.stderr)
             return 2
         print("Upstream:")
         for item in _reachable(result.snapshot, args.id, "upstream"):
             print(f"  {item}")
         print("Downstream:")
         for item in _reachable(result.snapshot, args.id, "downstream"):
             print(f"  {item}")
         return 0
     if args.command == "export":
-        write_v1_graph(root / args.output, result.snapshot)
+        output = root / args.output
+        try:
+            write_v1_graph(output, result.snapshot)
+        except OSError as error:
+            print(f"Could not write {output}: {error}", file=sys.stderr)
+            return 3
         return 0
     return 2
 
 
 if __name__ == "__main__":
     raise SystemExit(main())
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-before/tests/test_cli.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-after/tests/test_cli.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-before/tests/test_cli.py	2026-08-26 10:49:09.980315875 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-1-after/tests/test_cli.py	2026-08-26 14:56:30.019814287 -0300
@@ -811,10 +811,48 @@
     cli.main(["--root", str(tmp_path), "baseline", "create"])
     (tmp_path / ".quarto-needs.toml").write_text(
         'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
     )
 
     destination = str(tmp_path / "baselines" / "quarto-needs.json")
     assert cli.main(["--root", str(tmp_path), "impact", destination]) == 2
     assert "--recompute-with" in capsys.readouterr().err
 
     assert cli.main(["--root", str(tmp_path), "impact", destination, "--recompute-with", "current"]) == 0
+
+
+def test_scan_on_an_unwritable_root_is_operational_failure(tmp_path: Path, capsys) -> None:
+    """Read-only scan targets are exit 3, not a traceback."""
+    import os
+
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+    target = tmp_path / "locked"
+    target.mkdir()
+    (target / "needs.qmd").write_text(
+        "::: {.need #REQ-2 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+    os.chmod(target, 0o500)
+
+    try:
+        assert cli.main(["--root", str(target), "scan"]) == 3
+        assert "Could not" in capsys.readouterr().err
+    finally:
+        os.chmod(target, 0o700)
+
+
+def test_export_to_an_unwritable_directory_is_operational_failure(tmp_path: Path, capsys) -> None:
+    """A failed artifact write exits 3 and names the artifact."""
+    import os
+
+    write_valid_project(tmp_path)
+    locked = tmp_path / "locked"
+    locked.mkdir()
+    os.chmod(locked, 0o500)
+
+    try:
+        destination = locked / "sub" / "needs.json"
+        assert cli.main(["--root", str(tmp_path), "export", "--output", str(destination)]) == 3
+        assert str(destination) in capsys.readouterr().err
+    finally:
+        os.chmod(locked, 0o700)
```
