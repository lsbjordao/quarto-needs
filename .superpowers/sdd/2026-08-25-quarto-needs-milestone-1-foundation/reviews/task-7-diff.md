diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-before/src/quarto_needs/cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-after/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-before/src/quarto_needs/cli.py	2026-08-25 10:32:11.673592737 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-after/src/quarto_needs/cli.py	2026-08-25 10:41:00.072684461 -0300
@@ -4,28 +4,74 @@
 import json
 import os
 import sys
+from collections import deque
+from collections.abc import Iterable
 from pathlib import Path
+from typing import TextIO
 
-from .export import coverage, export_graph, export_lua_index
-from .graph import RequirementsGraph
-from .parser import parse_project
-from .validation import validate
+from .analysis import analyze_project
+from .diagnostics import Finding
+from .export import write_build_outputs, write_v1_graph
+from .snapshot import AnalysisSnapshot
 
 
 def _root(value: str | None) -> Path:
     return Path(value or os.getcwd()).resolve()
 
 
+def print_findings(findings: Iterable[Finding], stream: TextIO) -> None:
+    for finding in findings:
+        mark = "ERROR" if finding.severity == "error" else "WARN"
+        print(f"[{mark}] {finding.code}: {finding.message}", file=stream)
+
+
+def _reachable(
+    snapshot: AnalysisSnapshot, start: str, direction: str
+) -> list[str]:
+    seen: set[str] = set()
+    queue = deque([start])
+    while queue:
+        current = queue.popleft()
+        relations = (
+            snapshot.outgoing.get(current, ())
+            if direction == "downstream"
+            else snapshot.incoming.get(current, ())
+        )
+        for relation in relations:
+            candidate = (
+                relation.target
+                if direction == "downstream"
+                else relation.source
+            )
+            if candidate not in seen and candidate != start:
+                seen.add(candidate)
+                queue.append(candidate)
+    return sorted(seen, key=lambda item: (item.casefold(), item))
+
+
 def build(root: Path, quiet: bool = False) -> int:
-    objects = parse_project(root)
-    findings = validate(objects)
-    export_graph(root / ".quarto-needs" / "needs.json", objects, findings)
-    export_lua_index(root / "_extensions" / "quarto-needs" / "generated-index.lua", objects)
+    result = analyze_project(root)
+    if result.snapshot is None:
+        if not quiet:
+            print_findings(result.findings, stream=sys.stderr)
+        return 1
+    write_build_outputs(
+        root / ".quarto-needs" / "needs.json",
+        root / "_extensions" / "quarto-needs" / "generated-index.lua",
+        result.snapshot,
+    )
     if not quiet:
-        c = coverage(objects)
-        print(f"Quarto-Needs: {len(objects)} objects, {len(findings)} findings")
-        print(f"Requirements: {c['requirements']} | implemented: {c['implementation_coverage']}% | verified: {c['verification_coverage']}%")
-    return 1 if any(f.severity == "error" for f in findings) else 0
+        metrics = result.snapshot.metrics
+        print(
+            f"Quarto-Needs: {len(result.snapshot.objects)} objects, "
+            f"{len(result.findings)} findings"
+        )
+        print(
+            f"Requirements: {metrics['requirements']} | "
+            f"implemented: {metrics['implementation_coverage']}% | "
+            f"verified: {metrics['verification_coverage']}%"
+        )
+    return 1 if any(f.severity == "error" for f in result.findings) else 0
 
 
 def main(argv: list[str] | None = None) -> int:
@@ -41,34 +87,46 @@
     export.add_argument("--output", default=".quarto-needs/needs.json")
     args = parser.parse_args(argv)
     root = _root(args.root)
-    objects = parse_project(root)
-    findings = validate(objects)
 
     if args.command == "scan":
         return build(root)
+    result = analyze_project(root)
     if args.command == "check":
-        for f in findings:
-            mark = "ERROR" if f.severity == "error" else "WARN"
-            print(f"[{mark}] {f.code}: {f.message}")
-        print(f"Checked {len(objects)} objects: {sum(f.severity == 'error' for f in findings)} errors, {sum(f.severity == 'warning' for f in findings)} warnings")
-        return 1 if any(f.severity == "error" for f in findings) else 0
+        print_findings(result.findings, stream=sys.stdout)
+        print(
+            f"Checked {len(result.declarations)} objects: "
+            f"{sum(f.severity == 'error' for f in result.findings)} errors, "
+            f"{sum(f.severity == 'warning' for f in result.findings)} warnings"
+        )
+        return 1 if any(f.severity == "error" for f in result.findings) else 0
+    if result.snapshot is None:
+        print_findings(result.findings, stream=sys.stderr)
+        return 1
     if args.command == "coverage":
-        print(json.dumps(coverage(objects), indent=2))
+        metrics = result.snapshot.metrics
+        projection = {
+            "requirements": metrics["requirements"],
+            "approved": metrics["approved"],
+            "implemented": metrics["implemented"],
+            "verified": metrics["verified"],
+            "implementation_coverage": metrics["implementation_coverage"],
+            "verification_coverage": metrics["verification_coverage"],
+        }
+        print(json.dumps(projection, indent=2))
         return 0
     if args.command == "trace":
-        graph = RequirementsGraph.build(objects)
-        if args.id not in graph.objects:
+        if args.id not in result.snapshot.objects_by_id:
             print(f"Unknown object: {args.id}", file=sys.stderr)
             return 2
         print("Upstream:")
-        for item in sorted(graph.upstream(args.id)):
+        for item in _reachable(result.snapshot, args.id, "upstream"):
             print(f"  {item}")
         print("Downstream:")
-        for item in sorted(graph.downstream(args.id)):
+        for item in _reachable(result.snapshot, args.id, "downstream"):
             print(f"  {item}")
         return 0
     if args.command == "export":
-        export_graph(root / args.output, objects, findings)
+        write_v1_graph(root / args.output, result.snapshot)
         return 0
     return 2
 
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-before/tests/test_cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-after/tests/test_cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-before/tests/test_cli.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-after/tests/test_cli.py	2026-08-25 10:41:00.076684456 -0300
@@ -0,0 +1,312 @@
+from __future__ import annotations
+
+import json
+from pathlib import Path
+
+import pytest
+
+from quarto_needs import cli
+
+
+def write_valid_project(root: Path) -> None:
+    (root / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=need status=draft}\n"
+        "references: REQ-2\n"
+        "\n"
+        "## First\n"
+        "First body.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #REQ-2 type=need status=draft}\n"
+        "references: TC-1\n"
+        "\n"
+        "## Second\n"
+        "Second body.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #TC-1 type=test-case status=passed}\n"
+        "\n"
+        "## Test\n"
+        "Test body.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+
+def write_duplicate_project(root: Path) -> None:
+    (root / "duplicates.qmd").write_text(
+        "::: {.need #DUP-1 type=need status=draft}\n"
+        "\n"
+        "## First\n"
+        "First body.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #DUP-1 type=need status=draft}\n"
+        "\n"
+        "## Second\n"
+        "Second body.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+
+@pytest.mark.parametrize(
+    "arguments",
+    [
+        ["scan"],
+        ["check"],
+        ["coverage"],
+        ["trace", "REQ-1"],
+        ["export", "--output", "exported.json"],
+    ],
+    ids=["scan", "check", "coverage", "trace", "export"],
+)
+def test_each_command_analyzes_project_once(
+    tmp_path: Path,
+    monkeypatch: pytest.MonkeyPatch,
+    arguments: list[str],
+) -> None:
+    """Calling analysis twice would rescan files and split command state."""
+    write_valid_project(tmp_path)
+    calls = 0
+    real_analyze = cli.analyze_project
+
+    def counted(root: Path):
+        nonlocal calls
+        calls += 1
+        return real_analyze(root)
+
+    monkeypatch.setattr(cli, "analyze_project", counted)
+
+    assert cli.main(["--root", str(tmp_path), *arguments]) == 0
+    assert calls == 1
+
+
+def test_scan_delegates_to_build_without_preanalysis(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    """The scan branch must reach build before any analysis in main."""
+    build_calls: list[tuple[Path, bool]] = []
+
+    def fail_preanalysis(root: Path):
+        raise AssertionError(f"main pre-analyzed {root}")
+
+    def recorded_build(root: Path, quiet: bool = False) -> int:
+        build_calls.append((root, quiet))
+        return 7
+
+    monkeypatch.setattr(cli, "analyze_project", fail_preanalysis)
+    monkeypatch.setattr(cli, "build", recorded_build)
+
+    assert cli.main(["--root", str(tmp_path), "scan"]) == 7
+    assert build_calls == [(tmp_path.resolve(), False)]
+
+
+def test_scan_writes_both_outputs_and_keeps_legacy_stdout(
+    tmp_path: Path,
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    """A valid scan must retain its two generated artifacts and summary."""
+    write_valid_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "scan"]) == 0
+
+    captured = capsys.readouterr()
+    assert captured.out == (
+        "Quarto-Needs: 3 objects, 0 findings\n"
+        "Requirements: 0 | implemented: 100.0% | verified: 100.0%\n"
+    )
+    assert captured.err == ""
+    assert json.loads(
+        (tmp_path / ".quarto-needs/needs.json").read_text(encoding="utf-8")
+    )["schemaVersion"] == "1"
+    assert (
+        tmp_path / "_extensions/quarto-needs/generated-index.lua"
+    ).read_text(encoding="utf-8").startswith("return {\n")
+
+
+def test_invalid_scan_reports_error_without_replacing_outputs(
+    tmp_path: Path,
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    """Structural invalidity must not clobber either last-known-good output."""
+    write_duplicate_project(tmp_path)
+    graph = tmp_path / ".quarto-needs/needs.json"
+    index = tmp_path / "_extensions/quarto-needs/generated-index.lua"
+    graph.parent.mkdir(parents=True)
+    index.parent.mkdir(parents=True)
+    graph.write_text("graph sentinel\n", encoding="utf-8")
+    index.write_text("index sentinel\n", encoding="utf-8")
+
+    assert cli.main(["--root", str(tmp_path), "scan"]) == 1
+
+    captured = capsys.readouterr()
+    assert captured.out == ""
+    assert captured.err == "[ERROR] REQ004: Duplicate ID: DUP-1\n"
+    assert graph.read_text(encoding="utf-8") == "graph sentinel\n"
+    assert index.read_text(encoding="utf-8") == "index sentinel\n"
+
+
+def test_quiet_invalid_build_does_not_print_or_replace_outputs(
+    tmp_path: Path,
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    """Quiet build suppresses findings without weakening write safety."""
+    write_duplicate_project(tmp_path)
+    graph = tmp_path / ".quarto-needs/needs.json"
+    index = tmp_path / "_extensions/quarto-needs/generated-index.lua"
+    graph.parent.mkdir(parents=True)
+    index.parent.mkdir(parents=True)
+    graph.write_text("graph sentinel\n", encoding="utf-8")
+    index.write_text("index sentinel\n", encoding="utf-8")
+
+    assert cli.build(tmp_path, quiet=True) == 1
+
+    captured = capsys.readouterr()
+    assert captured.out == ""
+    assert captured.err == ""
+    assert graph.read_text(encoding="utf-8") == "graph sentinel\n"
+    assert index.read_text(encoding="utf-8") == "index sentinel\n"
+
+
+def test_check_prints_structural_findings_and_legacy_summary(
+    tmp_path: Path,
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    """An absent snapshot must not hide check diagnostics or change its stream."""
+    write_duplicate_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "check"]) == 1
+
+    captured = capsys.readouterr()
+    assert captured.out == (
+        "[ERROR] REQ004: Duplicate ID: DUP-1\n"
+        "Checked 2 objects: 1 errors, 0 warnings\n"
+    )
+    assert captured.err == ""
+
+
+def test_coverage_keeps_exact_legacy_output(
+    tmp_path: Path,
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    """Snapshot-backed coverage must retain the documented six-key JSON."""
+    write_valid_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "coverage"]) == 0
+
+    captured = capsys.readouterr()
+    assert captured.out == (
+        "{\n"
+        '  "requirements": 0,\n'
+        '  "approved": 0,\n'
+        '  "implemented": 0,\n'
+        '  "verified": 0,\n'
+        '  "implementation_coverage": 100.0,\n'
+        '  "verification_coverage": 100.0\n'
+        "}\n"
+    )
+    assert captured.err == ""
+
+
+@pytest.mark.parametrize(
+    ("command", "sentinel_path"),
+    [
+        (["coverage"], None),
+        (["trace", "DUP-1"], None),
+        (["export", "--output", "exported.json"], "exported.json"),
+    ],
+    ids=["coverage", "trace", "export"],
+)
+def test_snapshot_consumers_report_structural_failure_to_stderr(
+    tmp_path: Path,
+    capsys: pytest.CaptureFixture[str],
+    command: list[str],
+    sentinel_path: str | None,
+) -> None:
+    """Commands requiring a graph must fail safely when no snapshot exists."""
+    write_duplicate_project(tmp_path)
+    destination = tmp_path / sentinel_path if sentinel_path is not None else None
+    if destination is not None:
+        destination.write_text("sentinel\n", encoding="utf-8")
+
+    assert cli.main(["--root", str(tmp_path), *command]) == 1
+
+    captured = capsys.readouterr()
+    assert captured.out == ""
+    assert captured.err == "[ERROR] REQ004: Duplicate ID: DUP-1\n"
+    if destination is not None:
+        assert destination.read_text(encoding="utf-8") == "sentinel\n"
+
+
+def test_trace_is_transitive_and_deterministically_sorted(
+    tmp_path: Path,
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    """Trace must traverse beyond direct neighbors using snapshot indexes."""
+    write_valid_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "trace", "REQ-1"]) == 0
+
+    captured = capsys.readouterr()
+    assert captured.out == (
+        "Upstream:\n"
+        "Downstream:\n"
+        "  REQ-2\n"
+        "  TC-1\n"
+    )
+    assert captured.err == ""
+
+
+def test_trace_unknown_id_keeps_exit_two_and_error_text(
+    tmp_path: Path,
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    """A valid snapshot with an unknown trace start remains usage failure 2."""
+    write_valid_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "trace", "UNKNOWN"]) == 2
+
+    captured = capsys.readouterr()
+    assert captured.out == ""
+    assert captured.err == "Unknown object: UNKNOWN\n"
+
+
+def test_export_writes_requested_graph_without_build_side_effects(
+    tmp_path: Path,
+    capsys: pytest.CaptureFixture[str],
+) -> None:
+    """Export writes only its requested v1 artifact and remains silent."""
+    write_valid_project(tmp_path)
+
+    assert cli.main(
+        ["--root", str(tmp_path), "export", "--output", "artifacts/graph.json"]
+    ) == 0
+
+    captured = capsys.readouterr()
+    assert captured.out == ""
+    assert captured.err == ""
+    assert json.loads(
+        (tmp_path / "artifacts/graph.json").read_text(encoding="utf-8")
+    )["schemaVersion"] == "1"
+    assert not (tmp_path / "_extensions/quarto-needs/generated-index.lua").exists()
+
+
+def test_export_does_not_run_legacy_object_reanalysis(
+    tmp_path: Path,
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    """Export must send the existing snapshot straight to the v1 writer."""
+    write_valid_project(tmp_path)
+
+    def fail_reanalysis(*args: object, **kwargs: object) -> None:
+        raise AssertionError("legacy export wrapper re-analyzed objects")
+
+    monkeypatch.setattr("quarto_needs.export.analyze_objects", fail_reanalysis)
+
+    assert cli.main(
+        ["--root", str(tmp_path), "export", "--output", "graph.json"]
+    ) == 0
+    assert json.loads(
+        (tmp_path / "graph.json").read_text(encoding="utf-8")
+    )["schemaVersion"] == "1"
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-before/tests/test_extension_sync.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-after/tests/test_extension_sync.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-before/tests/test_extension_sync.py	2026-08-25 10:32:11.677592728 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-7-after/tests/test_extension_sync.py	2026-08-25 10:41:00.076684456 -0300
@@ -79,3 +79,28 @@
     assert not stale_file.exists()
     assert not stale_directory.exists()
     assert generated_index.read_text(encoding="utf-8") == 'return { ["LOCAL"] = {} }\n'
+
+
+def test_pre_render_synchronizes_then_builds_exactly_once(
+    tmp_path: Path, monkeypatch
+):
+    """Pre-render must delegate all parsing and validation to one build call."""
+    module = pre_render_module()
+    events: list[tuple[object, ...]] = []
+
+    def sync(project_root: Path) -> None:
+        events.append(("sync", project_root))
+
+    def build(project_root: Path, quiet: bool = False) -> int:
+        events.append(("build", project_root, quiet))
+        return 7
+
+    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
+    monkeypatch.setattr(module, "sync_extension", sync)
+    monkeypatch.setattr(module, "build", build)
+
+    assert module.main() == 7
+    assert events == [
+        ("sync", tmp_path),
+        ("build", tmp_path, False),
+    ]
