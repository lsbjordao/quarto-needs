# Review package

Snapshot range: `task-5-before` -> `task-5-after`

## Files changed (3)

- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `src/quarto_needs/cli.py`
- `tests/test_cli.py`

## Summary

161 lines added, 1 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 01:15:55.479325417 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 01:38:10.668359063 -0300
@@ -1288,20 +1288,21 @@
     assert cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"]) == 0
 
     payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
     assert payload["valid"] is False
     assert payload["declarations"]
 
 
 def test_baseline_inspect_reports_both_variants(tmp_path: Path, capsys) -> None:
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     destination = str(tmp_path / "baselines" / "quarto-needs.json")
 
     assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination, "--format", "json"]) == 0
     summary = json.loads(capsys.readouterr().out)
     assert summary["valid"] is True
     assert summary["objects"] == 3
     assert summary["referenceDate"]
 
     assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination]) == 0
     assert "objects" in capsys.readouterr().out
@@ -3158,21 +3159,21 @@
     import json as _json
     import shutil as _shutil
     from quarto_needs import cli
 
     project = tmp_path / "book"
     _shutil.copytree(ROOT / "examples/book", project, ignore=_shutil.ignore_patterns("_book", ".quarto"))
     baseline_path = project / "baselines" / "quarto-needs.json"
 
     system = project / "requirements" / "system.qmd"
     system.write_text(
-        system.read_text(encoding="utf-8").replace("verified-by: IAM-TC-001", "", 1),
+        system.read_text(encoding="utf-8").replace('verified-by="IAM-TC-001"', "", 1),
         encoding="utf-8",
     )
 
     assert cli.main(["--root", str(project), "impact", str(baseline_path), "--format", "json"]) == 0
 ```
 
 Note: this last test reads the JSON only to prove the command exits 0 on a real project; asserting exact reachability is already covered by `tests/test_impact.py`.
 
 - [ ] **Step 2: Run them and verify they fail**
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-before/src/quarto_needs/cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-after/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-before/src/quarto_needs/cli.py	2026-08-25 20:46:51.752450384 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-after/src/quarto_needs/cli.py	2026-08-26 01:36:30.732530153 -0300
@@ -3,20 +3,21 @@
 import argparse
 import json
 import os
 import sys
 from collections import deque
 from collections.abc import Iterable
 from pathlib import Path
 from typing import TextIO
 
 from .analysis import analyze_project
+from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline
 from .config import NeedsConfig, load_config
 from .diagnostics import Finding
 from .export import _write_atomic_text, write_build_outputs, write_v1_graph
 from .metrics import render_measure
 from .queries import materialize_queries
 from .quality import QualityReport, build_quality_report, report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
 
 class ConfigurationFailure(Exception):
@@ -178,55 +179,137 @@
         except OSError as error:
             print(f"Could not write quality report: {error}", file=sys.stderr)
             return 3
     if args.format == "json":
         print(json.dumps(payload, indent=2, sort_keys=True))
     else:
         _print_quality_text(report)
     return report.exit_code()
 
 
+def _baseline_destination(root: Path, output: str) -> Path:
+    candidate = Path(output)
+    return candidate if candidate.is_absolute() else root / candidate
+
+
+def _baseline_create(root: Path, args, config: NeedsConfig) -> int:
+    result = analyze_project(root, config=config)
+    if result.snapshot is None:
+        print_findings(result.findings, stream=sys.stderr)
+        if not args.allow_invalid:
+            return 1
+        payload = build_invalid_baseline(result, config)
+    else:
+        payload = build_baseline(
+            result.snapshot, config, queries=materialize_queries(config, result.snapshot)
+        )
+    destination = _baseline_destination(root, args.output)
+    try:
+        write_baseline(destination, payload, force=args.force)
+    except BaselineError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    except OSError as error:
+        print(f"Could not write baseline: {error}", file=sys.stderr)
+        return 3
+    if args.format == "json":
+        print(json.dumps({"path": str(destination), "valid": payload["valid"]}, indent=2, sort_keys=True))
+    else:
+        state = "valid" if payload["valid"] else "diagnostic (valid: false)"
+        print(f"Wrote {state} baseline to {destination}")
+    return 0
+
+
+def _baseline_summary(payload: dict[str, object]) -> dict[str, object]:
+    return {
+        "valid": payload["valid"],
+        "referenceDate": payload["referenceDate"],
+        "configurationFingerprint": payload["configurationFingerprint"],
+        "semanticGraphFingerprint": payload.get("semanticGraphFingerprint"),
+        "objects": len(payload.get("objects", payload.get("declarations", []))),
+        "relations": len(payload.get("relations", [])),
+        "findings": len(payload.get("findings", [])),
+    }
+
+
+def _baseline_inspect(args) -> int:
+    try:
+        payload = load_baseline(Path(args.baseline))
+    except BaselineError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    summary = _baseline_summary(payload)
+    if args.format == "json":
+        print(json.dumps(summary, indent=2, sort_keys=True))
+        return 0
+    print(f"Baseline {args.baseline}")
+    print(f"  valid: {summary['valid']}")
+    print(f"  reference date: {summary['referenceDate']}")
+    print(f"  objects: {summary['objects']}")
+    print(f"  relations: {summary['relations']}")
+    print(f"  findings: {summary['findings']}")
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
     export.add_argument("--output", default=".quarto-needs/needs.json")
     quality = sub.add_parser(
         "quality", help="Evaluate scoped metrics, findings, and configured gates"
     )
     quality.add_argument("--format", choices=("text", "json"), default="text")
     quality.add_argument("--output", help="Write the JSON report atomically to this path")
     query = sub.add_parser("query", help="Evaluate a named query and print its ordered IDs")
     query.add_argument("name")
     query.add_argument("--format", choices=("text", "json"), default="text")
+    baseline_parser = sub.add_parser("baseline", help="Create or inspect a canonical baseline")
+    baseline_sub = baseline_parser.add_subparsers(dest="baseline_command", required=True)
+    baseline_create = baseline_sub.add_parser("create", help="Write a baseline for the current graph")
+    baseline_create.add_argument("--output", default=str(DEFAULT_BASELINE_PATH))
+    baseline_create.add_argument("--force", action="store_true", help="Overwrite an existing baseline")
+    baseline_create.add_argument(
+        "--allow-invalid",
+        action="store_true",
+        help="Write a diagnostic artifact for a structurally invalid project",
+    )
+    baseline_create.add_argument("--format", choices=("text", "json"), default="text")
+    baseline_inspect = baseline_sub.add_parser("inspect", help="Summarize an existing baseline")
+    baseline_inspect.add_argument("baseline")
+    baseline_inspect.add_argument("--format", choices=("text", "json"), default="text")
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
+    if args.command == "baseline":
+        if args.baseline_command == "inspect":
+            return _baseline_inspect(args)
+        return _baseline_create(root, args, config)
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
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-before/tests/test_cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-after/tests/test_cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-before/tests/test_cli.py	2026-08-25 20:46:10.864585396 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-5-after/tests/test_cli.py	2026-08-26 01:36:06.448571727 -0300
@@ -601,10 +601,86 @@
 
     assert cli.main(["--root", str(tmp_path), "trace", "REQ-A"]) == 0
 
     output = capsys.readouterr().out
     assert output == (
         "Upstream:\n"
         "Downstream:\n"
         "  sub-b\n"
         "  SUB-C\n"
     )
+
+
+def test_baseline_create_writes_the_default_path_with_one_analysis(
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
+    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
+    assert calls == 1
+
+    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
+    assert payload["valid"] is True
+    assert payload["schemaVersion"] == "1"
+
+
+def test_baseline_create_refuses_to_clobber(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
+    destination = tmp_path / "baselines" / "quarto-needs.json"
+    sentinel = destination.read_text(encoding="utf-8")
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 2
+    assert destination.read_text(encoding="utf-8") == sentinel
+    assert "--force" in capsys.readouterr().err
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--force"]) == 0
+
+
+def test_baseline_create_refuses_invalid_input_without_the_flag(
+    tmp_path: Path, capsys
+) -> None:
+    """Structural failure must not silently become a comparison baseline."""
+    write_duplicate_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 1
+    assert not (tmp_path / "baselines" / "quarto-needs.json").exists()
+    assert "REQ004" in capsys.readouterr().err
+
+
+def test_baseline_create_allow_invalid_writes_a_diagnostic_artifact(tmp_path: Path) -> None:
+    write_duplicate_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"]) == 0
+
+    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
+    assert payload["valid"] is False
+    assert payload["declarations"]
+
+
+def test_baseline_inspect_reports_both_variants(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    destination = str(tmp_path / "baselines" / "quarto-needs.json")
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination, "--format", "json"]) == 0
+    summary = json.loads(capsys.readouterr().out)
+    assert summary["valid"] is True
+    assert summary["objects"] == 3
+    assert summary["referenceDate"]
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination]) == 0
+    assert "objects" in capsys.readouterr().out
+
+
+def test_baseline_inspect_reports_a_missing_file_as_usage_error(tmp_path: Path) -> None:
+    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", str(tmp_path / "nope.json")]) == 2
```
