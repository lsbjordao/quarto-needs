# Review package

Snapshot range: `task-3-before` -> `task-3-after`

## Files changed (5)

- `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md`
- `src/quarto_needs/cli.py`
- `src/quarto_needs/exporters/__init__.py`
- `src/quarto_needs/exporters/csv_export.py`
- `tests/test_export_csv.py`

## Summary

187 lines added, 5 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md	2026-08-26 14:52:55.992058367 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md	2026-08-26 15:50:43.859907314 -0300
@@ -313,24 +313,24 @@
     rows = list(csv.DictReader((tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8").splitlines()))
     assert rows[0]["id"] == "REQ-1"
     assert rows[0]["type"] == "system-requirement"
 
 
 def test_csv_neutralizes_formula_injection(tmp_path: Path) -> None:
     write_project(tmp_path)
     csv_export.write_all(tmp_path / "csv", build(tmp_path))
 
     text = (tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8")
-    cells = {row["title"]: None for row in csv.DictReader(text.splitlines())}
+    cells = {value: None for row in csv.DictReader(text.splitlines()) for value in row.values()}
     dangerous = [value for value in cells if value.startswith(("=", "+", "-", "@", "\t", "\r"))]
     assert not dangerous
-    assert any(value.startswith("'=") for value in cells), "the neutralized title must carry the apostrophe prefix"
+    assert any(value.startswith("'=") for value in cells), "the neutralized cell must carry the apostrophe prefix"
 
 
 def test_csv_is_deterministic(tmp_path: Path, monkeypatch) -> None:
     monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
     write_project(tmp_path)
     first = csv_export.render_objects(build(tmp_path))
     second = csv_export.render_objects(build(tmp_path))
     assert first == second
 ```
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/src/quarto_needs/cli.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/src/quarto_needs/cli.py	2026-08-26 15:15:36.766060194 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/src/quarto_needs/cli.py	2026-08-26 15:52:20.763606152 -0300
@@ -9,20 +9,21 @@
 from pathlib import Path
 from typing import TextIO
 
 from . import diff as diff_module
 from . import impact as impact_module
 from .analysis import analyze_project
 from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline
 from .config import NeedsConfig, load_config
 from .diagnostics import Finding
 from .export import _write_atomic_text, write_build_outputs, write_v1_graph
+from .exporters import csv_export
 from .metrics import render_measure
 from .queries import materialize_queries
 from .quality import QualityReport, build_quality_report, profile_exit_code, report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
 
 class ConfigurationFailure(Exception):
     """Raised when `.quarto-needs.toml` cannot be used."""
 
 
@@ -372,24 +373,29 @@
     result = analyze_project(root, config=effective)
     if result.snapshot is None:
         print_findings(result.findings, stream=sys.stderr)
         return 1
     output = root / args.output
     try:
         if args.format == "json":
             # Byte-identity with the pre-task v1 projection holds by
             # construction: the default format keeps the existing writer.
             write_v1_graph(output, result.snapshot)
+        elif args.format == "csv":
+            # The csv format's --output names a directory (created on
+            # demand) receiving objects/relations/findings.csv, each
+            # written atomically through export._write_atomic_text.
+            csv_export.write_all(output, result.snapshot)
         else:
-            # TODO(milestone-4a-writers): Tasks 3-6 replace this raise with
-            # the csv/sarif/junit/markdown writers, each routing its writes
-            # through _write_atomic_text like the json path above.
+            # TODO(milestone-4a-writers): Tasks 4-6 replace this raise with
+            # the sarif/junit/markdown writers, each routing its writes
+            # through _write_atomic_text like the branches above.
             raise NotImplementedError(
                 f"--format {args.format} writer lands with the milestone-4a exporter tasks"
             )
     except OSError as error:
         print(f"Could not write {output}: {error}", file=sys.stderr)
         return 3
     # The artifact is on disk before the policy verdict leaves the process.
     report = report_from_snapshot(result.snapshot, effective)
     return profile_exit_code(effective.profile, False, report.gate_failures())
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/src/quarto_needs/exporters/csv_export.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/src/quarto_needs/exporters/csv_export.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/src/quarto_needs/exporters/csv_export.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/src/quarto_needs/exporters/csv_export.py	2026-08-26 15:52:02.611662565 -0300
@@ -0,0 +1,117 @@
+from __future__ import annotations
+
+import csv
+import io
+from pathlib import Path
+
+from ..diagnostics import Finding
+from ..export import _write_atomic_text
+from ..snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord
+
+OBJECT_COLUMNS = (
+    "id",
+    "type",
+    "title",
+    "status",
+    "priority",
+    "tags",
+    "body",
+    "rationale",
+)
+RELATION_COLUMNS = ("source", "authored_name", "target", "semantic_family")
+FINDING_COLUMNS = ("code", "severity", "object_id", "message", "file", "line")
+
+# A cell whose text starts with one of these characters would be interpreted
+# as a formula by spreadsheet applications (CSV injection), so it is prefixed
+# with an apostrophe, which spreadsheets render as literal text.
+_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
+
+
+def _neutralize(value: object) -> str:
+    text = str(value)
+    if text.startswith(_DANGEROUS_PREFIXES):
+        return f"'{text}"
+    return text
+
+
+def _row_key(row: dict[str, str], columns: tuple[str, ...]) -> tuple[str, ...]:
+    # Case-insensitive by the leading (identifying) field, then by each
+    # remaining field, with the raw spelling breaking casefold ties.
+    return tuple(
+        part
+        for column in columns
+        for part in (row[column].casefold(), row[column])
+    )
+
+
+def _render(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
+    buffer = io.StringIO(newline="")
+    writer = csv.writer(buffer, lineterminator="\r\n")
+    writer.writerow(columns)
+    for row in sorted(rows, key=lambda item: _row_key(item, columns)):
+        writer.writerow([_neutralize(row[column]) for column in columns])
+    return buffer.getvalue()
+
+
+def _object_row(item: ObjectRecord) -> dict[str, str]:
+    return {
+        "id": item.id,
+        "type": item.type,
+        "title": item.title,
+        "status": item.status,
+        "priority": item.priority or "",
+        "tags": ";".join(item.tags),
+        "body": item.body,
+        "rationale": item.rationale,
+    }
+
+
+def _relation_row(item: RelationRecord) -> dict[str, str]:
+    return {
+        "source": item.source,
+        "authored_name": item.authored_name,
+        "target": item.target,
+        "semantic_family": item.semantic_family,
+    }
+
+
+def _finding_row(item: Finding) -> dict[str, str]:
+    location = item.location
+    return {
+        "code": item.code,
+        "severity": item.severity,
+        "object_id": item.object_id or "",
+        "message": item.message,
+        "file": location.file if location is not None else "",
+        "line": str(location.line) if location is not None else "",
+    }
+
+
+def render_objects(snapshot: AnalysisSnapshot) -> str:
+    return _render(OBJECT_COLUMNS, [_object_row(item) for item in snapshot.objects])
+
+
+def render_relations(snapshot: AnalysisSnapshot) -> str:
+    return _render(
+        RELATION_COLUMNS, [_relation_row(item) for item in snapshot.relations]
+    )
+
+
+def render_findings(snapshot: AnalysisSnapshot) -> str:
+    return _render(
+        FINDING_COLUMNS, [_finding_row(item) for item in snapshot.findings]
+    )
+
+
+def write_all(directory: Path, snapshot: AnalysisSnapshot) -> tuple[Path, ...]:
+    rendered = {
+        "findings.csv": render_findings(snapshot),
+        "objects.csv": render_objects(snapshot),
+        "relations.csv": render_relations(snapshot),
+    }
+    written: list[Path] = []
+    for name in sorted(rendered):
+        path = Path(directory) / name
+        _write_atomic_text(path, rendered[name])
+        written.append(path)
+    return tuple(written)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/src/quarto_needs/exporters/__init__.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/src/quarto_needs/exporters/__init__.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/src/quarto_needs/exporters/__init__.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/src/quarto_needs/exporters/__init__.py	2026-08-26 15:52:02.591662627 -0300
@@ -0,0 +1 @@
+"""Deterministic artifact exporters for the canonical analysis snapshot."""
diff -ruN '--unified=10' .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/tests/test_export_csv.py .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/tests/test_export_csv.py
--- .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-before/tests/test_export_csv.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-26-quarto-needs-milestone-4a-exporters-ci/snapshots/task-3-after/tests/test_export_csv.py	2026-08-26 15:51:40.775730428 -0300
@@ -0,0 +1,58 @@
+from __future__ import annotations
+
+import csv
+from pathlib import Path
+
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+from quarto_needs.exporters import csv_export
+
+
+def write_project(root: Path) -> None:
+    (root / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
+        "verified-by: TC-1\n"
+        "rationale: Protect data.\n"
+        "\n## Authenticate\nThe service shall authenticate.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #TC-1 type=test-case status=passed}\n"
+        "\n## Login\n=SUM(A1:A9) starts a formula when pasted into a spreadsheet\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+
+def build(root: Path):
+    result = analyze_project(root, config=load_config(root))
+    assert result.snapshot is not None
+    return result.snapshot
+
+
+def test_csv_writes_three_files_with_expected_headers(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    written = csv_export.write_all(tmp_path / "csv", build(tmp_path))
+
+    assert [path.name for path in written] == ["findings.csv", "objects.csv", "relations.csv"]
+    rows = list(csv.DictReader((tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8").splitlines()))
+    assert rows[0]["id"] == "REQ-1"
+    assert rows[0]["type"] == "system-requirement"
+
+
+def test_csv_neutralizes_formula_injection(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    csv_export.write_all(tmp_path / "csv", build(tmp_path))
+
+    text = (tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8")
+    cells = {value: None for row in csv.DictReader(text.splitlines()) for value in row.values()}
+    dangerous = [value for value in cells if value.startswith(("=", "+", "-", "@", "\t", "\r"))]
+    assert not dangerous
+    assert any(value.startswith("'=") for value in cells), "the neutralized cell must carry the apostrophe prefix"
+
+
+def test_csv_is_deterministic(tmp_path: Path, monkeypatch) -> None:
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
+    write_project(tmp_path)
+    first = csv_export.render_objects(build(tmp_path))
+    second = csv_export.render_objects(build(tmp_path))
+    assert first == second
```
