# Task 8 Report: `diff` command and its schema

## Summary

Implemented the `diff` command per the corrected brief: created
`schemas/diff-v1.schema.json`, registered the command in
`src/quarto_needs/cli.py` (parser block after `baseline`, `from . import diff
as diff_module` import, `profile_exit_code` added to the existing `.quality`
import line, `_print_diff_text` and `_diff` handlers above `main`, dispatch
alongside `baseline` and before the shared `analyze_project` line), and added
the six brief tests to `tests/test_cli.py`. All five brief code blocks are
byte-identical to the corrected brief (verified via `diff` against the
extracted blocks). TDD order followed with captured evidence for the failing
and every passing run. Final state: 49/49 CLI tests pass; full suite
`227 passed in 154.71s (0:02:34)`, no warnings (221 pre-existing + 6 new).

## Files changed

- Created: `/home/lsbjordao/Repos/quarto-needs/schemas/diff-v1.schema.json` (68 lines, byte-identical to the brief's Step 1 block)
- Modified: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/cli.py` (348 -> 417 lines)
  - `from . import diff as diff_module` added as the first relative import (line 12)
  - `profile_exit_code` added to the existing `from .quality import ...` line (line 20)
  - `diff` parser block after the `baseline` block, before `args = parser.parse_args(argv)` (lines 344-352)
  - `_print_diff_text` and `_diff` above `main` (lines 254-308)
  - Dispatch `if args.command == "diff": return _diff(root, args, config)` next to the `baseline` dispatch, before `result = analyze_project(root, config=config)` (lines 373-374)
- Modified: `/home/lsbjordao/Repos/quarto-needs/tests/test_cli.py` (686 -> 766 lines; six new tests appended verbatim, including the three controller-inserted `capsys.readouterr()` flush lines)
- No other file touched.

## TDD evidence

### Verbatim transcription checks (run against the corrected brief)

```
$ diff <(sed -n '37,104p' briefs/task-8-brief.md) schemas/diff-v1.schema.json
SCHEMA-BYTE-IDENTICAL
$ diff <(sed -n '112,189p' briefs/task-8-brief.md) <(sed -n '689,766p' tests/test_cli.py)
TESTS-BYTE-IDENTICAL
$ diff <(sed -n '203,211p' briefs/task-8-brief.md) <(sed -n '344,352p' src/quarto_needs/cli.py)
PARSER-BYTE-IDENTICAL
$ diff <(sed -n '221,275p' briefs/task-8-brief.md) <(sed -n '254,308p' src/quarto_needs/cli.py)
HANDLER-BYTE-IDENTICAL
$ diff <(sed -n '285,286p' briefs/task-8-brief.md) <(sed -n '373,374p' src/quarto_needs/cli.py)
DISPATCH-BYTE-IDENTICAL
```

(No diff output means byte-identical.)

### Step 3 — tests fail before implementation (brief's prediction met exactly)

```
$ .venv/bin/python -m pytest tests/test_cli.py -q -k diff
usage: quarto-needs [-h] [--root ROOT]
                    {scan,check,coverage,trace,export,quality,query,baseline} ...
quarto-needs: error: argument command: invalid choice: 'diff' (choose from scan, check, coverage, trace, export, quality, query, baseline)
...
E       SystemExit: 2
=========================== short test summary info ============================
FAILED tests/test_cli.py::test_diff_against_an_unchanged_project_is_empty_and_exits_zero
FAILED tests/test_cli.py::test_diff_validates_against_the_diff_schema - Syste...
FAILED tests/test_cli.py::test_diff_runs_exactly_one_analysis - SystemExit: 2
FAILED tests/test_cli.py::test_diff_rejects_a_diagnostic_baseline - SystemExi...
FAILED tests/test_cli.py::test_diff_reports_a_missing_baseline_as_usage_error
FAILED tests/test_cli.py::test_diff_recompute_with_current_clears_notices - S...
6 failed, 43 deselected in 1.30s
```

### Step 7 — CLI tests pass after implementation

```
$ .venv/bin/python -m pytest tests/test_cli.py -q
.................................................                        [100%]
49 passed in 0.25s
```

### Step 8 — full suite

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 63%]
........................................................................ [ 95%]
...........                                                              [100%]
227 passed in 154.71s (0:02:34)
```

227 = 221 pre-existing + 6 new diff tests. No warnings summary was emitted
(pytest shows one in `-q` mode when warnings exist).

### Step 9 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... else echo "Checkpoint 8 verified; workspace has no Git metadata."; fi
Checkpoint 8 verified; workspace has no Git metadata.
```

No `git init` was run.

## Self-review

- All five brief code blocks byte-identical to the corrected brief (diffs
  above), plus the two brief-specified import edits; nothing transcribed from
  memory of the first attempt. The redundant `from .diff import DiffError`
  considered in the first attempt was deliberately not added — the brief's
  handler references `diff_module.DiffError`, so the single
  `from . import diff as diff_module` import is exactly sufficient.
- One-analysis guarantee holds: `_diff` calls `analyze_project` exactly once
  (proven by the passing counting test, `calls == 1`), and the dispatch
  returns `_diff(root, args, config)` before the shared
  `result = analyze_project(...)` line in `main`, so a `diff` invocation never
  reaches it twice.
- Exit codes per Global Constraints: 0 on success (unchanged project, empty
  report), 1 for structurally invalid current input (findings on stderr,
  `snapshot is None`), 2 for unreadable/distrusted baselines
  (`BaselineError`), missing baseline files, and diagnostic artifacts
  (`DiffError`, "diagnostic artifact" message asserted on stderr); gate
  regressions map through `profile_exit_code(config.profile, False,
  len(report.gate_regressions))` (strict profile can exit 1, advisory/default
  stay 0). No path returns 3 — the command performs no file writes.
- The JSON payload validates against `schemas/diff-v1.schema.json` under
  `Draft202012Validator` (both `check_schema` and instance validation
  asserted), confirming `DiffReport.to_dict()` emits exactly the schema's
  required keys with `additionalProperties: false` satisfied.
- Recompute semantics verified as amended by controller ruling: the date-edited
  baseline yields `reference-date-changed` without `--recompute-with` and
  `notices == []` with `--recompute-with current`, while Task 7 keeps derived
  deltas suppressed in both runs (the suppressed-empty JSON still validates).
- Placement verified: parser block after the `baseline` block and before
  `args = parser.parse_args(argv)`; handlers above `main`; dispatch next to
  `baseline` and before the shared analysis line.
- Global Constraints: no new runtime dependency (reuses Task 7's
  `quarto_needs.diff`, Task 4's `load_baseline`, and `quality.profile_exit_code`;
  the schema test's `jsonschema` import is test-side only, already used by the
  existing suite); every existing command, signature, and shortcode preserved
  (all 43 pre-existing CLI tests pass unchanged); schema v1 `needs.json`
  untouched (`diff` writes nothing); no Git metadata created; preview server
  on 127.0.0.1:8777 untouched; no new shortcode and no `extensions.quartoNeeds`
  projection.

## Concerns

- First attempt blocked by the stop-and-report rule: the original brief's three
  JSON-parsing diff tests omitted the `capsys.readouterr()` flush after
  `baseline create` (the same capsys-pollution omission ruled on in Task 5), so
  `json.loads` saw the create line prefixed to the diff JSON; I restored all
  three files to pre-task state (verified `221 passed`), reported, and the
  controller applied the same one-line flush fix to brief and plan — this run
  used the corrected brief verbatim. No other concerns.
