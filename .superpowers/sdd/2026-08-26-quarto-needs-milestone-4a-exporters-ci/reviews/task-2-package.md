# Review package

Snapshot range: `task-2-before` -> `task-2-after`

## Files changed (5)

- `CONTRIBUTING.md`
- `README.md`
- `src/quarto_needs/cli.py`
- `tests/test_cli.py`
- `tests/test_example_project.py`

## Summary

149 lines added, 19 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/CONTRIBUTING.md .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/CONTRIBUTING.md
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/CONTRIBUTING.md	2026-08-26 13:14:30.082319314 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/CONTRIBUTING.md	2026-08-26 15:13:55.902196766 -0300
@@ -42,24 +42,28 @@
   It is the single oracle both the Python evaluator and any future non-Python
   consumer must agree with. Add cases to it when adding grammar; never edit an
   existing expectation to make a failing evaluator pass.
 - `tests/fixtures/views/.quarto-needs/needs.json` is authored by hand, not
   generated. It carries the `extensions.quartoNeeds` projections (relation
   catalog, materialized queries, quality report) that the Lua views read, so
   keep it consistent with what `cli.build` would emit for the same project.
 - Tests must never rewrite a golden or fixture as a side effect of
   running. A mismatch is a failure to investigate, not a file to refresh.
 - `examples/book/baselines/quarto-needs.json` is a checked-in baseline of
-  the Aegis showcase. It must always diff clean against the published book;
-  `tests/test_example_project.py` enforces this by running `diff` against it
-  and asserting exit code 0, and `make diff-example` must print
-  `No changes.`. Regenerate it with `make baseline-example` only when a
+  the Aegis showcase. It must always diff clean against the published book.
+  `tests/test_example_project.py` pins `SOURCE_DATE_EPOCH` to the baseline's
+  own stored `referenceDate` and asserts the JSON diff payload has
+  `"empty": true` and `"notices": []` — exit code alone is not enough,
+  because `diff`'s exit code reflects only gate regressions and stays 0
+  even when an object or relation actually changed. The separate,
+  human-run check is `make diff-example`, which must print `No changes.`.
+  Regenerate the baseline with `make baseline-example` only when a
   deliberate change to the showcase has been approved, and inspect the
   resulting `make diff-example` output before committing the new bytes.
   Never regenerate it just to silence a failing test: a non-empty diff
   against an unchanged book means a fingerprint is leaking derived data, not
   that the baseline is stale.
 
 ## Verification commands
 
 Run the full gate before opening a PR:
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/README.md .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/README.md
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/README.md	2026-08-26 14:57:44.151729746 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/README.md	2026-08-26 15:14:32.686146959 -0300
@@ -512,24 +512,24 @@
 - relation constraints;
 - configurable process rules;
 - CI severity policies.
 
 ### 0.4 — Source traceability
 - code/test scanners;
 - `@implements` and `@verifies` annotations;
 - semantic symbols as graph nodes;
 - Tree-sitter backend.
 
-### 0.5 — Change management
-- Git baselines;
-- semantic diff;
-- graph-based impact analysis.
+### 0.5 — Change management (shipped)
+- baselines, semantic diff, and graph-based impact analysis — see
+  "Baseline, diff, and impact" above for `baseline create`/`baseline
+  inspect`, `diff`, and `impact`.
 
 ### Later
 - JSON/CSV/ReqIF;
 - VS Code extension;
 - GitHub/Jira/external artifacts;
 - GUI.
 
 ## Design principles
 
 - Requirements as Code
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/src/quarto_needs/cli.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/src/quarto_needs/cli.py	2026-08-26 14:57:25.411751117 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/src/quarto_needs/cli.py	2026-08-26 15:15:36.766060194 -0300
@@ -352,31 +352,68 @@
         print(f"origin {origin['id']} ({origin['change']})")
     for item in report.impacted:
         print(
             f"  {item['classification']} d={item['distance']} {item['id']}"
             f" via {' -> '.join(item['path'])}"
             f" [{', '.join(item['relations'])}]"
         )
     return 0
 
 
+def _export(root: Path, args: argparse.Namespace, config: NeedsConfig | None) -> int:
+    effective = config if config is not None else load_config(root)
+    if args.baseline is not None and args.format != "markdown":
+        # Usage errors are reported before any analysis runs.
+        print(
+            "usage error: --baseline is only valid with --format markdown "
+            f"(got --format {args.format})",
+            file=sys.stderr,
+        )
+        return 2
+    result = analyze_project(root, config=effective)
+    if result.snapshot is None:
+        print_findings(result.findings, stream=sys.stderr)
+        return 1
+    output = root / args.output
+    try:
+        if args.format == "json":
+            # Byte-identity with the pre-task v1 projection holds by
+            # construction: the default format keeps the existing writer.
+            write_v1_graph(output, result.snapshot)
+        else:
+            # TODO(milestone-4a-writers): Tasks 3-6 replace this raise with
+            # the csv/sarif/junit/markdown writers, each routing its writes
+            # through _write_atomic_text like the json path above.
+            raise NotImplementedError(
+                f"--format {args.format} writer lands with the milestone-4a exporter tasks"
+            )
+    except OSError as error:
+        print(f"Could not write {output}: {error}", file=sys.stderr)
+        return 3
+    # The artifact is on disk before the policy verdict leaves the process.
+    report = report_from_snapshot(result.snapshot, effective)
+    return profile_exit_code(effective.profile, False, report.gate_failures())
+
+
 def main(argv: list[str] | None = None) -> int:
     parser = argparse.ArgumentParser(prog="quarto-needs", description="Requirements-as-code engine for Quarto")
     parser.add_argument("--root", help="Project root (default: current directory)")
     sub = parser.add_subparsers(dest="command", required=True)
     sub.add_parser("scan", help="Parse project and write .quarto-needs/needs.json")
     sub.add_parser("check", help="Validate the requirements graph")
     sub.add_parser("coverage", help="Print coverage metrics")
     trace = sub.add_parser("trace", help="Show upstream/downstream traceability")
     trace.add_argument("id")
     export = sub.add_parser("export", help="Export canonical graph JSON")
     export.add_argument("--output", default=".quarto-needs/needs.json")
+    export.add_argument("--format", choices=("json", "csv", "sarif", "junit", "markdown"), default="json")
+    export.add_argument("--baseline", help="Baseline for the Markdown change summary (markdown format only)")
     quality = sub.add_parser(
         "quality", help="Evaluate scoped metrics, findings, and configured gates"
     )
     quality.add_argument("--format", choices=("text", "json"), default="text")
     quality.add_argument("--output", help="Write the JSON report atomically to this path")
     query = sub.add_parser("query", help="Evaluate a named query and print its ordered IDs")
     query.add_argument("name")
     query.add_argument("--format", choices=("text", "json"), default="text")
     baseline_parser = sub.add_parser("baseline", help="Create or inspect a canonical baseline")
     baseline_sub = baseline_parser.add_subparsers(dest="baseline_command", required=True)
@@ -427,20 +464,22 @@
     if args.command == "query":
         return _query(root, args, config)
     if args.command == "baseline":
         if args.baseline_command == "inspect":
             return _baseline_inspect(args)
         return _baseline_create(root, args, config)
     if args.command == "diff":
         return _diff(root, args, config)
     if args.command == "impact":
         return _impact(root, args, config)
+    if args.command == "export":
+        return _export(root, args, config)
     result = analyze_project(root, config=config)
     if args.command == "check":
         print_findings(result.findings, stream=sys.stdout)
         print(
             f"Checked {len(result.declarations)} objects: "
             f"{sum(f.severity == 'error' for f in result.findings)} errors, "
             f"{sum(f.severity == 'warning' for f in result.findings)} warnings"
         )
         return 1 if any(f.severity == "error" for f in result.findings) else 0
     if result.snapshot is None:
@@ -462,23 +501,15 @@
         if args.id not in result.snapshot.objects_by_id:
             print(f"Unknown object: {args.id}", file=sys.stderr)
             return 2
         print("Upstream:")
         for item in _reachable(result.snapshot, args.id, "upstream"):
             print(f"  {item}")
         print("Downstream:")
         for item in _reachable(result.snapshot, args.id, "downstream"):
             print(f"  {item}")
         return 0
-    if args.command == "export":
-        output = root / args.output
-        try:
-            write_v1_graph(output, result.snapshot)
-        except OSError as error:
-            print(f"Could not write {output}: {error}", file=sys.stderr)
-            return 3
-        return 0
     return 2
 
 
 if __name__ == "__main__":
     raise SystemExit(main())
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/tests/test_cli.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/tests/test_cli.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/tests/test_cli.py	2026-08-26 14:56:30.019814287 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/tests/test_cli.py	2026-08-26 15:16:01.302026971 -0300
@@ -849,10 +849,79 @@
     locked = tmp_path / "locked"
     locked.mkdir()
     os.chmod(locked, 0o500)
 
     try:
         destination = locked / "sub" / "needs.json"
         assert cli.main(["--root", str(tmp_path), "export", "--output", str(destination)]) == 3
         assert str(destination) in capsys.readouterr().err
     finally:
         os.chmod(locked, 0o700)
+
+
+def test_export_default_format_is_byte_identical_to_the_v1_projection(tmp_path: Path) -> None:
+    """No --format must mean today's json output, byte for byte."""
+    import hashlib
+
+    write_valid_project(tmp_path)
+    first = tmp_path / "a.json"
+    second = tmp_path / "b.json"
+    assert cli.main(["--root", str(tmp_path), "export", "--output", str(first)]) == 0
+    assert cli.main(["--root", str(tmp_path), "export", "--format", "json", "--output", str(second)]) == 0
+
+    assert first.read_bytes() == second.read_bytes()
+    assert len(hashlib.sha256(first.read_bytes()).hexdigest()) == 64
+
+
+# TODO(milestone-4a-writers): remove this xfail when Tasks 3-6 land the writers.
+@pytest.mark.xfail(strict=True, reason="csv/sarif/junit writers land in Tasks 3-6")
+def test_export_runs_exactly_one_analysis_per_format(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    write_valid_project(tmp_path)
+    calls = 0
+    real_analyze = cli.analyze_project
+
+    def counted(root: Path, **kwargs: object):
+        nonlocal calls
+        calls += 1
+        return real_analyze(root, **kwargs)
+
+    monkeypatch.setattr(cli, "analyze_project", counted)
+
+    for name in ("json", "csv", "sarif", "junit", "markdown"):
+        destination = tmp_path / "out" / name
+        assert cli.main([
+            "--root", str(tmp_path), "export", "--format", name,
+            "--output", str(destination / "artifact"),
+        ]) in (0, 1), name
+    assert calls == 5
+
+
+def test_export_rejects_baseline_for_non_markdown_formats(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    assert cli.main([
+        "--root", str(tmp_path), "export", "--format", "sarif",
+        "--output", str(tmp_path / "out.sarif"), "--baseline", str(tmp_path / "none.json"),
+    ]) == 2
+    assert "markdown" in capsys.readouterr().err
+
+
+# TODO(milestone-4a-writers): remove this xfail when Task 6 lands the markdown writer.
+@pytest.mark.xfail(strict=True, reason="markdown writer lands in Task 6")
+def test_export_preserves_artifacts_on_policy_failure(tmp_path: Path) -> None:
+    """A failing strict gate still writes the artifact, then exits 1."""
+    # An approved requirement with no verification makes the verification gate
+    # fail with a non-zero denominator (an empty scope passes vacuously).
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
+        "\n## Authenticate\nBody.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n', encoding="utf-8"
+    )
+    destination = tmp_path / "artifacts" / "report.md"
+
+    assert cli.main(["--root", str(tmp_path), "export", "--format", "markdown", "--output", str(destination)]) == 1
+    assert destination.is_file()
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/tests/test_example_project.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/tests/test_example_project.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-before/tests/test_example_project.py	2026-08-26 14:41:49.133308008 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-2-after/tests/test_example_project.py	2026-08-26 15:11:45.458373391 -0300
@@ -207,34 +207,60 @@
 
     assert (
         cli.main(
             ["--root", str(ROOT / "examples/book"), "query", "approved-high-unverified"]
         )
         == 0
     )
     assert cli.main(["--root", str(ROOT / "examples/book"), "query", "evidence-gaps"]) == 0
 
 
-def test_aegis_baseline_round_trips_to_an_empty_diff():
-    """The gate: a checked-in baseline must still describe the published book."""
+def test_aegis_baseline_round_trips_to_an_empty_diff(
+    monkeypatch: pytest.MonkeyPatch,
+    capsys: pytest.CaptureFixture[str],
+):
+    """The gate: a checked-in baseline must still describe the published book.
+
+    Exit code alone is not the gate: `diff`'s exit code reflects only gate
+    regressions, so a modified object or an added/removed relation can leave
+    it at 0. The reference date is also pinned to the baseline's own stored
+    date, derived from the artifact rather than hard-coded, so this test
+    cannot decay into a tautological pass on any day after the baseline was
+    created — a differing reference date would otherwise emit
+    `reference-date-changed` and silently suppress every derived delta.
+    """
     import json as _json
+    from datetime import datetime, timezone
+
     from quarto_needs import cli
 
     root = ROOT / "examples/book"
     baseline_path = root / "baselines" / "quarto-needs.json"
     assert baseline_path.is_file(), "run `make baseline-example` to create it"
 
     payload = _json.loads(baseline_path.read_text(encoding="utf-8"))
     assert payload["valid"] is True
     assert payload["schemaVersion"] == "1"
 
-    assert cli.main(["--root", str(root), "diff", str(baseline_path)]) == 0
+    reference_date = datetime.strptime(payload["referenceDate"], "%Y-%m-%d").replace(
+        tzinfo=timezone.utc
+    )
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(int(reference_date.timestamp())))
+
+    exit_code = cli.main(
+        ["--root", str(root), "diff", str(baseline_path), "--format", "json"]
+    )
+    diff_payload = _json.loads(capsys.readouterr().out)
+
+    assert exit_code == 0
+    assert diff_payload["empty"] is True
+    assert diff_payload["notices"] == []
 
 
 def test_aegis_baseline_validates_against_the_baseline_schema():
     import json as _json
     from jsonschema import Draft202012Validator
 
     schema = _json.loads((ROOT / "schemas" / "baseline-v1.schema.json").read_text(encoding="utf-8"))
     payload = _json.loads((ROOT / "examples/book/baselines/quarto-needs.json").read_text(encoding="utf-8"))
     Draft202012Validator.check_schema(schema)
     Draft202012Validator(schema).validate(payload)
```
