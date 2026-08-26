# Task 3 Report: CSV exporter (final run, after controller ruling)

## Summary

Implemented the CSV exporter per the corrected brief: new
`quarto_needs.exporters` package with `csv_export.render_objects` /
`render_relations` / `render_findings` and `csv_export.write_all(directory,
snapshot)` writing `objects.csv` / `relations.csv` / `findings.csv` with
formula-injection neutralization; wired `--format csv` into cli.py's
`_export` handler (replacing the temporary `NotImplementedError` for csv),
where `--output` names a DIRECTORY created on demand and the writes route
through the existing OSError -> exit-3 guard. TDD followed with captured red
(`ModuleNotFoundError: No module named 'quarto_needs.exporters'`, exactly
the brief's Step 2 prediction) and green (`3 passed` in
`tests/test_export_csv.py`, transcribed byte-identically from the corrected
brief). The strict loop xfail
(`test_export_runs_exactly_one_analysis_per_format`) STAYS until Task 6, as
instructed — the csv path was instead verified end-to-end manually: `export
--format csv` exits 0 and produces the three files in a directory created on
demand, and an unwritable destination exits 3 naming the artifact. Final
state: full suite `248 passed, 2 xfailed in 236.70s (0:03:56)`, no warnings
(245 pre-existing + 3 new).

This was the second attempt. The first was stopped at Step 4 and restored
because the brief's own fixture/test pairing was defective (see Concerns,
one line); the controller ruled (option 2: the test collects ALL cells and
the assertion message says "cell"), patched plan and brief, and re-dispatched.
The implementation reinstated here is byte-identical to the one removed
after the blocked attempt (preserved verbatim in the interim report).

## Files changed

- Created: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/exporters/__init__.py`
  — docstring-only package marker (future home of sarif_export/junit_export).
- Created: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/exporters/csv_export.py`
  — fixed column sets per the brief (objects: id, type, title, status,
  priority, tags, body, rationale; relations: source, authored_name, target,
  semantic_family; findings: code, severity, object_id, message, file, line);
  rows sorted by `(value.casefold(), value)` over the columns in order
  (case-insensitive by the leading identifying field, then by field);
  `\r\n` record separators per RFC 4180 via
  `csv.writer(io.StringIO(newline=""), lineterminator="\r\n")`;
  `_neutralize(value)` stringifies and prefixes `'` when a cell starts with
  `=`, `+`, `-`, `@`, tab, or CR; `tags` joined with `;` (round-trips the
  authored `tags: security;login` syntax); empty string for absent
  priority/object_id/file/line (file/line from `finding.location` when
  present); `write_all` renders all three, then writes each atomically
  through `export._write_atomic_text` (which creates the directory on
  demand) and returns the three paths sorted. Stdlib only (`csv`, `io`).
- Created: `/home/lsbjordao/Repos/quarto-needs/tests/test_export_csv.py`
  — 58 lines, byte-identical extraction of corrected-brief lines 37-94
  (fences at 36/95; the ruled lines verified: line 47 collects
  `{value: None for row in csv.DictReader(text.splitlines()) for value in
  row.values()}`, line 50 says "the neutralized cell must carry the
  apostrophe prefix").
- Modified: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/cli.py`
  (515 -> 522 lines, exactly two hunks):
  - import block: added `from .exporters import csv_export` between the
    `.export` and `.metrics` imports.
  - `_export` dispatch (lines ~382-397): new `elif args.format == "csv":`
    branch calling `csv_export.write_all(output, result.snapshot)` with a
    comment recording the directory semantics; the remaining
    `else: raise NotImplementedError(...)` now covers only sarif/junit/
    markdown and its TODO note reads "Tasks 4-6" (was "Tasks 3-6 ...
    csv/sarif/junit/markdown"). The branch sits inside the pre-existing
    `except OSError` guard, so csv write failures print
    `Could not write {output}: {error}` and return 3.
  - Nothing else in `_export` changed: the pre-analysis `--baseline`
    rejection, exactly-one `analyze_project` call, snapshot-None -> 1, and
    write-then-`profile_exit_code` ordering are Task 2's final code,
    untouched.
- Not touched: Task 2's two strict xfails in tests/test_cli.py (the loop
  xfail covers all five formats and must stay until Task 6; it remains
  xfailed because sarif/junit/markdown still raise — CLI export slice:
  `7 passed, 49 deselected, 2 xfailed`).

## TDD evidence

### Verbatim transcription check (run against the corrected brief)

```
$ sed -n '36p;95p' briefs/task-3-brief.md
```python
```
$ sed -n '37,94p' briefs/task-3-brief.md > tests/test_export_csv.py   # 58 lines
$ sed -n '46,52p' tests/test_export_csv.py
    text = (tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8")
    cells = {value: None for row in csv.DictReader(text.splitlines()) for value in row.values()}
    dangerous = [value for value in cells if value.startswith(("=", "+", "-", "@", "\t", "\r"))]
    assert not dangerous
    assert any(value.startswith("'=") for value in cells), "the neutralized cell must carry the apostrophe prefix"
```

### Step 2 — failing run (pre-implementation), exactly as the brief predicted

```
$ .venv/bin/python -m pytest tests/test_export_csv.py -q
...
tests/test_export_csv.py:8: in <module>
    from quarto_needs.exporters import csv_export
E   ModuleNotFoundError: No module named 'quarto_needs.exporters'
...
1 error in 0.16s
```

### Step 4 — after implementation (reinstated verbatim from the interim report)

```
$ .venv/bin/python -m pytest tests/test_export_csv.py -q
...                                                                      [100%]
3 passed in 0.05s
```

### CLI export slice after the wire-up (loop xfail intact, as instructed)

```
$ .venv/bin/python -m pytest tests/test_cli.py -q -k export
......x.x                                                               [100%]
7 passed, 49 deselected, 2 xfailed in 0.19s
```

(Same summary as Task 2's final state: the loop xfail now survives on
sarif/junit/markdown alone; csv and json both complete. It stays until
Task 6 removes it.)

### Manual end-to-end csv probe (Step 5; scratch project in /tmp)

```
$ quarto-needs --root proj export --format csv --output artifacts/csv
exit: 0
$ find proj/artifacts -type f | sort
proj/artifacts/csv/findings.csv
proj/artifacts/csv/objects.csv
proj/artifacts/csv/relations.csv
$ cat proj/artifacts/csv/objects.csv
id,type,title,status,priority,tags,body,rationale
REQ-1,system-requirement,Authenticate,approved,high,,The service shall authenticate.,Protect data.
TC-1,test-case,Login,passed,,,'=SUM(A1:A9) starts a formula when pasted into a spreadsheet,
$ cat proj/artifacts/csv/relations.csv
source,authored_name,target,semantic_family
REQ-1,verified-by,TC-1,verification
$ cat proj/artifacts/csv/findings.csv
code,severity,object_id,message,file,line
```

Directory created on demand (`artifacts/csv` did not exist); exit 0; three
files present; objects row 0 is REQ-1 / system-requirement; the dangerous
body cell carries the `'=` prefix. Raw-byte check of the emitted files
(`read_bytes`, so no newline translation):

```
objects.csv   | CRLF: 3 | bare LF: 0
relations.csv | CRLF: 2 | bare LF: 0
findings.csv  | CRLF: 1 | bare LF: 0
```

RFC 4180 `\r\n` endings confirmed in the actual bytes. (Note for Tasks 4-6:
`Path.read_text()` silently normalizes CRLF to LF on read — verify line
endings with `read_bytes()`.)

### Operational-failure probe through the csv path (OSError -> exit 3)

```
$ chmod 500 locked
$ quarto-needs --root proj export --format csv --output ../locked/sub/csv
Could not write /tmp/qn-task3-e2e/proj/../locked/sub/csv: [Errno 13] Permission denied: '/tmp/qn-task3-e2e/proj/../locked/sub'
exit: 3
```

The Task 1/2 guard shape catches `write_all`'s OSError, prints one stderr
line naming the requested output, and returns 3 — no traceback, no partial
files (the locked directory was never populated).

### Step 5 — full suite and conditional checkpoint

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 28%]
.x.x.................................................................... [ 57%]
........................................................................ [ 86%]
..................................                                       [100%]
248 passed, 2 xfailed in 236.70s (0:03:56)

$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... else echo "Checkpoint verified; workspace has no Git metadata."; fi
Checkpoint verified; workspace has no Git metadata.
```

248 = 245 pre-existing + 3 new CSV tests; the 2 xfails are Task 2's marks,
both still strict and neither XPASSed. No `git init` was run; the preview
server on 127.0.0.1:8777 was never contacted; all probes were confined to
/tmp scratch projects.

## Self-review

- The three tests are byte-identical to the corrected brief (sed-extracted,
  boundaries and ruled lines verified above); the implementation follows
  Step 3's specification exactly (columns, ordering, RFC 4180 endings via
  csv.writer over io.StringIO, `_neutralize` prefix rule, sorted-path
  `write_all` with directory created on demand through
  `export._write_atomic_text`).
- Hard constraint "one analysis per invocation": the wire-up only adds a
  branch inside `_export` that consumes the already-built snapshot;
  `analyze_project` is still called exactly once (the pre-existing
  `test_each_command_analyzes_project_once[export]` passes; the loop xfail
  still only reflects the unwritten sarif/junit/markdown writers).
- Hard constraint "byte-identical json": the json branch is untouched;
  `test_export_default_format_is_byte_identical_to_the_v1_projection` and
  the unwritable-directory exit-3 test pass unchanged.
- Exit-code contract: csv success exits 0 (probe), csv policy failure would
  still write all three files before `profile_exit_code` (Task 2's ordering,
  unchanged), csv operational failure exits 3 naming the output (probe).
  `--baseline` with csv still exits 2 before analysis (Task 2 code).
- Determinism: no wall-clock values anywhere in the CSV; the only inputs are
  the snapshot's frozen records; rows sorted by casefolded column tuples;
  `test_csv_is_deterministic` passes with SOURCE_DATE_EPOCH pinned.
- Global constraints: no new runtime dependency (stdlib csv/io only); only
  the three brief-listed files plus the sanctioned cli.py csv wire-up were
  touched; no Git metadata created; server untouched; existing signatures
  and the v1 JSON / `extensions.quartoNeeds` projection untouched.
- The reinstated `csv_export.py` is byte-identical to the implementation
  removed after the blocked first attempt (the brief's Step 3 text did not
  change under the ruling; only the test's cell collection did).

## Concerns

- First attempt was blocked at Step 4 by a plan defect (fixture placed the
  formula in the body while the test scanned only title cells); controller
  ruled option 2 (test collects all cells, message says "cell"), applied to
  plan and brief, and this run completed cleanly under it — no other issues.
- Two minor notes for the controller, neither blocking: (1) the csv exit-3
  stderr names the requested output directory; the specific failing file
  name appears only inside the OSError text — consistent with Task 1/2's
  guard shape and the json path, but worth knowing if CI greps for exact
  artifact names; (2) `write_all` writes the three files sequentially, so a
  failure on the second or third file can leave earlier files in place —
  the same per-artifact granularity `build`'s scan writer already has, and
  the global constraints only require atomic replacement per file, not
  all-or-nothing across the three.
