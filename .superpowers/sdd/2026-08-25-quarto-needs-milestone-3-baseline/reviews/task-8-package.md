# Review package

Snapshot range: `task-8-before` -> `task-8-after`

## Files changed (4)

- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `schemas/diff-v1.schema.json`
- `src/quarto_needs/cli.py`
- `tests/test_cli.py`

## Summary

222 lines added, 1 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 09:41:24.030092148 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 09:59:33.683251291 -0300
@@ -2347,34 +2347,36 @@
 - [ ] **Step 2: Write the failing CLI tests**
 
 Add to `tests/test_cli.py`:
 
 ```python
 def test_diff_against_an_unchanged_project_is_empty_and_exits_zero(
     tmp_path: Path, capsys
 ) -> None:
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     destination = str(tmp_path / "baselines" / "quarto-needs.json")
 
     assert cli.main(["--root", str(tmp_path), "diff", destination, "--format", "json"]) == 0
 
     payload = json.loads(capsys.readouterr().out)
     assert payload["empty"] is True
     assert payload["notices"] == []
 
 
 def test_diff_validates_against_the_diff_schema(tmp_path: Path, capsys) -> None:
     from jsonschema import Draft202012Validator
 
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json"])
     payload = json.loads(capsys.readouterr().out)
 
     schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "diff-v1.schema.json").read_text(encoding="utf-8"))
     Draft202012Validator.check_schema(schema)
     Draft202012Validator(schema).validate(payload)
 
 
 def test_diff_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
     write_valid_project(tmp_path)
@@ -2404,20 +2406,21 @@
 
 
 def test_diff_reports_a_missing_baseline_as_usage_error(tmp_path: Path) -> None:
     write_valid_project(tmp_path)
     assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "absent.json")]) == 2
 
 
 def test_diff_recompute_with_current_clears_notices(tmp_path: Path, capsys) -> None:
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     destination = tmp_path / "baselines" / "quarto-needs.json"
     payload = json.loads(destination.read_text(encoding="utf-8"))
     payload["referenceDate"] = "1999-01-01"
     destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
 
     cli.main(["--root", str(tmp_path), "diff", str(destination), "--format", "json"])
     assert "reference-date-changed" in json.loads(capsys.readouterr().out)["notices"]
 
     cli.main([
         "--root", str(tmp_path), "diff", str(destination),
@@ -2993,20 +2996,21 @@
 - [ ] **Step 2: Write the failing CLI tests**
 
 Add to `tests/test_cli.py`:
 
 ```python
 def test_impact_validates_against_the_impact_schema(tmp_path: Path, capsys) -> None:
     from jsonschema import Draft202012Validator
 
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     (tmp_path / "needs.qmd").write_text(
         (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace("First body.", "Changed body."),
         encoding="utf-8",
     )
 
     assert cli.main([
         "--root", str(tmp_path), "impact",
         str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json",
     ]) == 0
     payload = json.loads(capsys.readouterr().out)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-before/schemas/diff-v1.schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-after/schemas/diff-v1.schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-before/schemas/diff-v1.schema.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-after/schemas/diff-v1.schema.json	2026-08-26 10:00:03.963170253 -0300
@@ -0,0 +1,68 @@
+{
+  "$schema": "https://json-schema.org/draft/2020-12/schema",
+  "$id": "https://quarto-needs.dev/schema/diff-v1.schema.json",
+  "title": "Quarto-Needs diff v1",
+  "type": "object",
+  "additionalProperties": false,
+  "required": ["schemaVersion", "referenceDate", "recomputed", "notices", "objects", "relations", "findings", "metrics", "gates", "empty"],
+  "properties": {
+    "schemaVersion": {"const": "1"},
+    "referenceDate": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["baseline", "current"],
+      "properties": {"baseline": {"type": "string"}, "current": {"type": "string"}}
+    },
+    "recomputed": {"type": "boolean"},
+    "notices": {
+      "type": "array",
+      "items": {"enum": ["configuration-changed", "reference-date-changed"]}
+    },
+    "objects": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["added", "removed", "modified", "relocated"],
+      "properties": {
+        "added": {"type": "array", "items": {"type": "string"}},
+        "removed": {"type": "array", "items": {"type": "string"}},
+        "modified": {
+          "type": "array",
+          "items": {
+            "type": "object",
+            "additionalProperties": false,
+            "required": ["id", "fields"],
+            "properties": {"id": {"type": "string"}, "fields": {"type": "array", "items": {"type": "string"}}}
+          }
+        },
+        "relocated": {"type": "array", "items": {"type": "object"}}
+      }
+    },
+    "relations": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["added", "removed", "representationChanged"],
+      "properties": {
+        "added": {"type": "array", "items": {"type": "object"}},
+        "removed": {"type": "array", "items": {"type": "object"}},
+        "representationChanged": {"type": "array", "items": {"type": "object"}}
+      }
+    },
+    "findings": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["added", "removed"],
+      "properties": {
+        "added": {"type": "array", "items": {"type": "object"}},
+        "removed": {"type": "array", "items": {"type": "object"}}
+      }
+    },
+    "metrics": {"type": "array", "items": {"type": "object"}},
+    "gates": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["regressed"],
+      "properties": {"regressed": {"type": "array", "items": {"type": "object"}}}
+    },
+    "empty": {"type": "boolean"}
+  }
+}
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-before/src/quarto_needs/cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-after/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-before/src/quarto_needs/cli.py	2026-08-26 01:36:30.732530153 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-after/src/quarto_needs/cli.py	2026-08-26 10:00:39.211082073 -0300
@@ -2,28 +2,29 @@
 
 import argparse
 import json
 import os
 import sys
 from collections import deque
 from collections.abc import Iterable
 from pathlib import Path
 from typing import TextIO
 
+from . import diff as diff_module
 from .analysis import analyze_project
 from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline
 from .config import NeedsConfig, load_config
 from .diagnostics import Finding
 from .export import _write_atomic_text, write_build_outputs, write_v1_graph
 from .metrics import render_measure
 from .queries import materialize_queries
-from .quality import QualityReport, build_quality_report, report_from_snapshot
+from .quality import QualityReport, build_quality_report, profile_exit_code, report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
 
 class ConfigurationFailure(Exception):
     """Raised when `.quarto-needs.toml` cannot be used."""
 
 
 def _root(value: str | None) -> Path:
     return Path(value or os.getcwd()).resolve()
 
@@ -243,20 +244,77 @@
         return 0
     print(f"Baseline {args.baseline}")
     print(f"  valid: {summary['valid']}")
     print(f"  reference date: {summary['referenceDate']}")
     print(f"  objects: {summary['objects']}")
     print(f"  relations: {summary['relations']}")
     print(f"  findings: {summary['findings']}")
     return 0
 
 
+def _print_diff_text(report) -> None:
+    for notice in report.notices:
+        print(f"[notice] {notice}: derived deltas suppressed; both sides must share configuration and reference date to compare them")
+    if report.is_empty():
+        print("No changes.")
+        return
+    for object_id in report.added_objects:
+        print(f"+ object {object_id}")
+    for object_id in report.removed_objects:
+        print(f"- object {object_id}")
+    for item in report.modified:
+        print(f"~ object {item['id']} ({', '.join(item['fields'])})")
+    for item in report.relocated:
+        print(f"> object {item['id']} moved {item['from'].get('file')} -> {item['to'].get('file')}")
+    for item in report.added_relations:
+        print(f"+ relation {item['source']} {item['authoredName']} {item['target']}")
+    for item in report.removed_relations:
+        print(f"- relation {item['source']} {item['authoredName']} {item['target']}")
+    for item in report.representation_changes:
+        print(f"= relation {item['source']} -> {item['target']} respelled {item['from']} -> {item['to']}")
+    for item in report.findings_added:
+        print(f"+ finding {item['code']} {item['object_id'] or ''}".rstrip())
+    for item in report.findings_removed:
+        print(f"- finding {item['code']} {item['object_id'] or ''}".rstrip())
+    for item in report.metric_deltas:
+        print(f"~ metric {item['scope']}/{item['strength']} {item['before']} -> {item['after']}")
+    for item in report.gate_regressions:
+        print(f"! gate {item['name']} failed (threshold {item['threshold']}, actual {item['actual']})")
+
+
+def _diff(root: Path, args, config: NeedsConfig) -> int:
+    try:
+        baseline_payload = load_baseline(Path(args.baseline))
+    except BaselineError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    result = analyze_project(root, config=config)
+    if result.snapshot is None:
+        print_findings(result.findings, stream=sys.stderr)
+        return 1
+    try:
+        report = diff_module.compare(
+            baseline_payload,
+            result.snapshot,
+            config,
+            recompute=args.recompute_with == "current",
+        )
+    except diff_module.DiffError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    if args.format == "json":
+        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
+    else:
+        _print_diff_text(report)
+    return profile_exit_code(config.profile, False, len(report.gate_regressions))
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
@@ -276,40 +334,51 @@
     baseline_create.add_argument("--force", action="store_true", help="Overwrite an existing baseline")
     baseline_create.add_argument(
         "--allow-invalid",
         action="store_true",
         help="Write a diagnostic artifact for a structurally invalid project",
     )
     baseline_create.add_argument("--format", choices=("text", "json"), default="text")
     baseline_inspect = baseline_sub.add_parser("inspect", help="Summarize an existing baseline")
     baseline_inspect.add_argument("baseline")
     baseline_inspect.add_argument("--format", choices=("text", "json"), default="text")
+    diff_parser = sub.add_parser("diff", help="Compare a baseline against the current graph")
+    diff_parser.add_argument("baseline")
+    diff_parser.add_argument("--format", choices=("text", "json"), default="text")
+    diff_parser.add_argument(
+        "--recompute-with",
+        choices=("current",),
+        dest="recompute_with",
+        help="Re-evaluate both sides under the current configuration and reference date",
+    )
     args = parser.parse_args(argv)
     root = _root(args.root)
 
     if args.command == "scan":
         return build(root)
 
     try:
         config: NeedsConfig | None = load_config(root)
     except ValueError as error:
         print(f"Configuration error: {error}", file=sys.stderr)
         return 2
 
     if args.command == "quality":
         return _quality(root, args, config)
     if args.command == "query":
         return _query(root, args, config)
     if args.command == "baseline":
         if args.baseline_command == "inspect":
             return _baseline_inspect(args)
         return _baseline_create(root, args, config)
+    if args.command == "diff":
+        return _diff(root, args, config)
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
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-before/tests/test_cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-after/tests/test_cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-before/tests/test_cli.py	2026-08-26 01:36:06.448571727 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-8-after/tests/test_cli.py	2026-08-26 10:00:14.743143284 -0300
@@ -677,10 +677,90 @@
     assert summary["valid"] is True
     assert summary["objects"] == 3
     assert summary["referenceDate"]
 
     assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination]) == 0
     assert "objects" in capsys.readouterr().out
 
 
 def test_baseline_inspect_reports_a_missing_file_as_usage_error(tmp_path: Path) -> None:
     assert cli.main(["--root", str(tmp_path), "baseline", "inspect", str(tmp_path / "nope.json")]) == 2
+
+
+def test_diff_against_an_unchanged_project_is_empty_and_exits_zero(
+    tmp_path: Path, capsys
+) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    destination = str(tmp_path / "baselines" / "quarto-needs.json")
+
+    assert cli.main(["--root", str(tmp_path), "diff", destination, "--format", "json"]) == 0
+
+    payload = json.loads(capsys.readouterr().out)
+    assert payload["empty"] is True
+    assert payload["notices"] == []
+
+
+def test_diff_validates_against_the_diff_schema(tmp_path: Path, capsys) -> None:
+    from jsonschema import Draft202012Validator
+
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json"])
+    payload = json.loads(capsys.readouterr().out)
+
+    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "diff-v1.schema.json").read_text(encoding="utf-8"))
+    Draft202012Validator.check_schema(schema)
+    Draft202012Validator(schema).validate(payload)
+
+
+def test_diff_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
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
+    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")])
+    assert calls == 1
+
+
+def test_diff_rejects_a_diagnostic_baseline(tmp_path: Path, capsys) -> None:
+    write_duplicate_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"])
+    (tmp_path / "duplicates.qmd").unlink()
+    write_valid_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")]) == 2
+    assert "diagnostic artifact" in capsys.readouterr().err
+
+
+def test_diff_reports_a_missing_baseline_as_usage_error(tmp_path: Path) -> None:
+    write_valid_project(tmp_path)
+    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "absent.json")]) == 2
+
+
+def test_diff_recompute_with_current_clears_notices(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    destination = tmp_path / "baselines" / "quarto-needs.json"
+    payload = json.loads(destination.read_text(encoding="utf-8"))
+    payload["referenceDate"] = "1999-01-01"
+    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
+
+    cli.main(["--root", str(tmp_path), "diff", str(destination), "--format", "json"])
+    assert "reference-date-changed" in json.loads(capsys.readouterr().out)["notices"]
+
+    cli.main([
+        "--root", str(tmp_path), "diff", str(destination),
+        "--recompute-with", "current", "--format", "json",
+    ])
+    assert json.loads(capsys.readouterr().out)["notices"] == []
```
