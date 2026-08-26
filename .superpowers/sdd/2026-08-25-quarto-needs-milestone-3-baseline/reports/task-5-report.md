# Task 5 Report: `baseline create` and `baseline inspect`

## Summary

Implemented the nested `baseline` subcommand per the corrected brief: registered
`baseline create` / `baseline inspect` in `src/quarto_needs/cli.py` (parser
block, import line, four handler functions, dispatch routed before the shared
`analyze_project` call) and added the six brief tests to `tests/test_cli.py`.
All four brief code blocks are byte-identical to the brief (verified via
`diff` against the extracted blocks, including the controller-ruled
`capsys.readouterr()` flush line in `test_baseline_inspect_reports_both_variants`).
TDD order followed with captured evidence for the failing and every passing
run. Final state: 43/43 CLI tests pass; full suite `205 passed in 135.94s`,
no warnings (199 pre-existing + 6 new).

This is the second attempt. The first attempt stopped under the stop-and-report
rule on a genuine, plan-mandated test defect; the controller confirmed it and
applied exactly the recommended one-line fix to brief and plan. See Concerns
for the honest record.

## Files changed

- Modified: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/cli.py` (265 -> 348 lines)
  - Import added after `.analysis`: `from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline`
  - `baseline` parser block after the `query` block, before `args = parser.parse_args(argv)`
  - `_baseline_destination`, `_baseline_create`, `_baseline_summary`, `_baseline_inspect` above `main`
  - Dispatch next to `quality`/`query`, before `result = analyze_project(root, config=config)`
- Modified: `/home/lsbjordao/Repos/quarto-needs/tests/test_cli.py` (610 -> 686 lines; six new tests appended verbatim)
- No other file touched.

## TDD evidence

### Verbatim transcription checks (run against the corrected brief)

```
$ diff <(sed -n '36,109p' .../briefs/task-5-brief.md) <(sed -n '613,686p' tests/test_cli.py)
TESTS-BYTE-IDENTICAL
$ diff <(sed -n '123,136p' .../briefs/task-5-brief.md) <(sed -n '272,285p' src/quarto_needs/cli.py)
PARSER-BYTE-IDENTICAL
$ diff <(sed -n '146,207p' .../briefs/task-5-brief.md) <(sed -n '189,250p' src/quarto_needs/cli.py)
HANDLERS-BYTE-IDENTICAL
$ diff <(sed -n '215,218p' .../briefs/task-5-brief.md) <(sed -n '302,305p' src/quarto_needs/cli.py)
DISPATCH-BYTE-IDENTICAL
```

(No diff output means byte-identical; the corrected test block includes the
flush line `capsys.readouterr()  # flush the create command's text output
before the JSON run`.)

### Step 2 — tests fail before implementation (brief's prediction met exactly)

```
$ .venv/bin/python -m pytest tests/test_cli.py -q -k baseline
usage: quarto-needs [-h] [--root ROOT]
                    {scan,check,coverage,trace,export,quality,query} ...
quarto-needs: error: argument command: invalid choice: 'baseline' (choose from scan, check, coverage, trace, export, quality, query)
...
E       SystemExit: 2
=========================== short test summary info ============================
FAILED tests/test_cli.py::test_baseline_create_writes_the_default_path_with_one_analysis
FAILED tests/test_cli.py::test_baseline_create_refuses_to_clobber - SystemExi...
FAILED tests/test_cli.py::test_baseline_create_refuses_invalid_input_without_the_flag
FAILED tests/test_cli.py::test_baseline_create_allow_invalid_writes_a_diagnostic_artifact
FAILED tests/test_cli.py::test_baseline_inspect_reports_both_variants - Syste...
FAILED tests/test_cli.py::test_baseline_inspect_reports_a_missing_file_as_usage_error
6 failed, 37 deselected in 0.70s
```

### Step 6 — CLI tests pass after implementation

```
$ .venv/bin/python -m pytest tests/test_cli.py -q
...........................................                              [100%]
43 passed in 0.15s
```

### Step 7 — full suite

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 70%]
.............................................................            [100%]
205 passed in 135.94s (0:02:15)
```

205 = 199 pre-existing + 6 new baseline tests. No warnings summary was emitted
(pytest shows one in `-q` mode when warnings exist).

### Step 8 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... else echo "Checkpoint 5 verified; workspace has no Git metadata."; fi
Checkpoint 5 verified; workspace has no Git metadata.
```

No `git init` was run.

## Self-review

- All four brief code blocks byte-identical to the corrected brief (diffs
  above); nothing transcribed from memory of the first attempt.
- One-analysis guarantee holds: `baseline create` calls `analyze_project`
  exactly once (proven by the passing counting test,
  `calls == 1`), and `inspect` never analyzes because the dispatch returns
  `_baseline_inspect(args)` before the shared `result = analyze_project(...)`
  line in `main`.
- Exit codes per Global Constraints: 0 on success (create text/json, inspect
  text/json), 1 for structurally invalid input without `--allow-invalid`
  (REQ004 findings on stderr, no artifact written), 2 for refused overwrite
  (`--force` hint in the `BaselineError` message, sentinel bytes preserved)
  and for unreadable/untrusted baselines in `inspect`, 3 for `OSError` during
  the atomic write.
- The clobber test proves the sentinel bytes are unchanged after the refused
  write and that `--force` recovers; the allow-invalid test proves the
  diagnostic artifact carries `valid: false` plus `declarations`; the inspect
  tests prove both `--format json` (parsed summary: `valid`, `objects == 3`,
  truthy `referenceDate`) and text output, plus exit 2 for a missing file.
- Placement verified: parser block sits after the `query` block and before
  `args = parser.parse_args(argv)`; handlers sit above `main`; dispatch sits
  next to `quality`/`query` and before the shared analysis line.
- Global Constraints: no new runtime dependency (reuses Task 4's
  `quarto_needs.baseline` and existing modules); every existing command,
  signature, and shortcode preserved (all 37 pre-existing CLI tests pass
  unchanged); schema v1 `needs.json` untouched (baseline writes go only to
  `tmp_path` destinations in tests); baseline writes flow through
  `write_baseline` -> `export._write_atomic_text` (deterministic
  `render_baseline`); no Git metadata created; preview server on
  127.0.0.1:8777 untouched; no new shortcode and no `extensions.quartoNeeds`
  projection.

## Concerns

- First attempt (honest record, one line): the original brief and plan
  omitted the capsys flush between `baseline create` and
  `baseline inspect --format json` in
  `test_baseline_inspect_reports_both_variants`, making the test unpassable
  against the brief's own mandated handler output; I stopped, restored both
  files to their pre-task state (verified `199 passed`), and reported — the
  controller confirmed the defect and applied exactly my recommended one-line
  fix (`capsys.readouterr()` with a short comment) to brief and plan; this run
  used the corrected brief verbatim.
- Also disclosed from the first attempt, self-corrected with no lasting
  effect: while reverting I once inverted old/new in an Edit and briefly
  duplicated the six tests (file grew to 760 lines); detected immediately via
  `grep -n`, fixed by exact truncation at the original 610-line boundary, and
  verified by line count, byte-level tail inspection, zero `baseline`
  matches, `37 passed`, and a full-suite `199 passed` before this second
  attempt began.
- No other concerns.
