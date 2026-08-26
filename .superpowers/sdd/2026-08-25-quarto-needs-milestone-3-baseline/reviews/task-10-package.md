# Review package

Snapshot range: `task-10-before` -> `task-10-after`

## Files changed (3)

- `schemas/impact-v1.schema.json`
- `src/quarto_needs/cli.py`
- `tests/test_cli.py`

## Summary

146 lines added, 1 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-before/schemas/impact-v1.schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/schemas/impact-v1.schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-before/schemas/impact-v1.schema.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/schemas/impact-v1.schema.json	2026-08-26 10:48:50.384341729 -0300
@@ -0,0 +1,42 @@
+{
+  "$schema": "https://json-schema.org/draft/2020-12/schema",
+  "$id": "https://quarto-needs.dev/schema/impact-v1.schema.json",
+  "title": "Quarto-Needs impact v1",
+  "type": "object",
+  "additionalProperties": false,
+  "required": ["schemaVersion", "origins", "impacted"],
+  "properties": {
+    "schemaVersion": {"const": "1"},
+    "origins": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["id", "change"],
+        "properties": {
+          "id": {"type": "string"},
+          "change": {"enum": ["added", "removed", "modified", "relation-added", "relation-removed"]},
+          "fields": {"type": "array", "items": {"type": "string"}}
+        }
+      }
+    },
+    "impacted": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["id", "origin", "change", "classification", "distance", "relations", "path", "priority"],
+        "properties": {
+          "id": {"type": "string"},
+          "origin": {"type": "string"},
+          "change": {"type": "string"},
+          "classification": {"enum": ["direct", "transitive"]},
+          "distance": {"type": "integer", "minimum": 1},
+          "relations": {"type": "array", "items": {"type": "string"}, "minItems": 1},
+          "path": {"type": "array", "items": {"type": "string"}, "minItems": 2},
+          "priority": {"type": ["string", "null"]}
+        }
+      }
+    }
+  }
+}
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-before/src/quarto_needs/cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-before/src/quarto_needs/cli.py	2026-08-26 10:00:39.211082073 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/src/quarto_needs/cli.py	2026-08-26 10:50:07.764239637 -0300
@@ -3,20 +3,21 @@
 import argparse
 import json
 import os
 import sys
 from collections import deque
 from collections.abc import Iterable
 from pathlib import Path
 from typing import TextIO
 
 from . import diff as diff_module
+from . import impact as impact_module
 from .analysis import analyze_project
 from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline
 from .config import NeedsConfig, load_config
 from .diagnostics import Finding
 from .export import _write_atomic_text, write_build_outputs, write_v1_graph
 from .metrics import render_measure
 from .queries import materialize_queries
 from .quality import QualityReport, build_quality_report, profile_exit_code, report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
@@ -301,20 +302,57 @@
     except diff_module.DiffError as error:
         print(str(error), file=sys.stderr)
         return 2
     if args.format == "json":
         print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
     else:
         _print_diff_text(report)
     return profile_exit_code(config.profile, False, len(report.gate_regressions))
 
 
+def _impact(root: Path, args, config: NeedsConfig) -> int:
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
+        report = impact_module.analyze(
+            baseline_payload,
+            result.snapshot,
+            config,
+            recompute=args.recompute_with == "current",
+        )
+    except impact_module.ImpactError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    if args.format == "json":
+        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
+        return 0
+    if not report.origins:
+        print("No changes to propagate.")
+        return 0
+    for origin in report.origins:
+        print(f"origin {origin['id']} ({origin['change']})")
+    for item in report.impacted:
+        print(
+            f"  {item['classification']} d={item['distance']} {item['id']}"
+            f" via {' -> '.join(item['path'])}"
+            f" [{', '.join(item['relations'])}]"
+        )
+    return 0
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
@@ -341,21 +379,30 @@
     baseline_inspect = baseline_sub.add_parser("inspect", help="Summarize an existing baseline")
     baseline_inspect.add_argument("baseline")
     baseline_inspect.add_argument("--format", choices=("text", "json"), default="text")
     diff_parser = sub.add_parser("diff", help="Compare a baseline against the current graph")
     diff_parser.add_argument("baseline")
     diff_parser.add_argument("--format", choices=("text", "json"), default="text")
     diff_parser.add_argument(
         "--recompute-with",
         choices=("current",),
         dest="recompute_with",
-        help="Re-evaluate both sides under the current configuration and reference date",
+        help="Re-resolve the baseline's relations under the current configuration and reference date",
+    )
+    impact_parser = sub.add_parser("impact", help="Explain what a baseline's changes reach")
+    impact_parser.add_argument("baseline")
+    impact_parser.add_argument("--format", choices=("text", "json"), default="text")
+    impact_parser.add_argument(
+        "--recompute-with",
+        choices=("current",),
+        dest="recompute_with",
+        help="Re-resolve the baseline's relations under the current configuration and reference date",
     )
     args = parser.parse_args(argv)
     root = _root(args.root)
 
     if args.command == "scan":
         return build(root)
 
     try:
         config: NeedsConfig | None = load_config(root)
     except ValueError as error:
@@ -365,20 +412,22 @@
     if args.command == "quality":
         return _quality(root, args, config)
     if args.command == "query":
         return _query(root, args, config)
     if args.command == "baseline":
         if args.baseline_command == "inspect":
             return _baseline_inspect(args)
         return _baseline_create(root, args, config)
     if args.command == "diff":
         return _diff(root, args, config)
+    if args.command == "impact":
+        return _impact(root, args, config)
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
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-before/tests/test_cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/tests/test_cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-before/tests/test_cli.py	2026-08-26 10:00:14.743143284 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-10-after/tests/test_cli.py	2026-08-26 10:49:09.980315875 -0300
@@ -757,10 +757,64 @@
     destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
 
     cli.main(["--root", str(tmp_path), "diff", str(destination), "--format", "json"])
     assert "reference-date-changed" in json.loads(capsys.readouterr().out)["notices"]
 
     cli.main([
         "--root", str(tmp_path), "diff", str(destination),
         "--recompute-with", "current", "--format", "json",
     ])
     assert json.loads(capsys.readouterr().out)["notices"] == []
+
+
+def test_impact_validates_against_the_impact_schema(tmp_path: Path, capsys) -> None:
+    from jsonschema import Draft202012Validator
+
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    (tmp_path / "needs.qmd").write_text(
+        (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace("First body.", "Changed body."),
+        encoding="utf-8",
+    )
+
+    assert cli.main([
+        "--root", str(tmp_path), "impact",
+        str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json",
+    ]) == 0
+    payload = json.loads(capsys.readouterr().out)
+
+    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "impact-v1.schema.json").read_text(encoding="utf-8"))
+    Draft202012Validator.check_schema(schema)
+    Draft202012Validator(schema).validate(payload)
+    assert payload["origins"]
+
+
+def test_impact_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
+    cli.main(["--root", str(tmp_path), "impact", str(tmp_path / "baselines" / "quarto-needs.json")])
+    assert calls == 1
+
+
+def test_impact_rejects_a_configuration_mismatch(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
+    )
+
+    destination = str(tmp_path / "baselines" / "quarto-needs.json")
+    assert cli.main(["--root", str(tmp_path), "impact", destination]) == 2
+    assert "--recompute-with" in capsys.readouterr().err
+
+    assert cli.main(["--root", str(tmp_path), "impact", destination, "--recompute-with", "current"]) == 0
```
