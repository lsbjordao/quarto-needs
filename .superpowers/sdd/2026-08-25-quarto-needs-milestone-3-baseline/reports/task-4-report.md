# Task 4 Report: Baseline artifact — schema, serialization, and load

## Summary

Implemented the baseline artifact per the corrected brief: created
`src/quarto_needs/baseline.py` (six public names: `BaselineError`,
`build_baseline`, `build_invalid_baseline`, `render_baseline`, `write_baseline`,
`load_baseline`), `schemas/baseline-v1.schema.json` (separately versioned
baseline schema, no reference to the v1 graph schema), and
`tests/test_baseline.py` (7 tests). All three files are byte-identical to the
brief's code blocks (verified via `diff` against the extracted blocks). The
TDD step order was followed with captured evidence for the failing and every
passing run. Final state: 7/7 baseline tests pass; full suite 199 passed, no
warnings.

## Files changed

- Created: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/baseline.py`
- Created: `/home/lsbjordao/Repos/quarto-needs/schemas/baseline-v1.schema.json`
- Created: `/home/lsbjordao/Repos/quarto-needs/tests/test_baseline.py`
- No other file touched.

## TDD evidence

### Verbatim transcription checks (run before/alongside each step)

```
$ diff <(sed -n '43,117p' .../briefs/task-4-brief.md) schemas/baseline-v1.schema.json
SCHEMA BYTE-IDENTICAL
$ diff <(sed -n '125,255p' .../briefs/task-4-brief.md) tests/test_baseline.py
TESTS BYTE-IDENTICAL
$ diff <(sed -n '267,413p' .../briefs/task-4-brief.md) src/quarto_needs/baseline.py
BASELINE.PY BYTE-IDENTICAL
```

### Step 3 — baseline tests fail before implementation

```
$ .venv/bin/python -m pytest tests/test_baseline.py -q
==================================== ERRORS ====================================
___________________ ERROR collecting tests/test_baseline.py ____________________
ImportError while importing test module '/home/lsbjordao/Repos/quarto-needs/tests/test_baseline.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.13/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_baseline.py:9: in <module>
    from quarto_needs import baseline
E   ImportError: cannot import name 'baseline' from 'quarto_needs' (/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/__init__.py)
=========================== short test summary info ============================
ERROR tests/test_baseline.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.11s
```

Failure for the correct underlying reason: the module does not exist yet.
Wording deviation versus the brief's prediction noted under Concerns.

### Step 5 — baseline tests pass after implementation

```
$ .venv/bin/python -m pytest tests/test_baseline.py -q
.......                                                                  [100%]
7 passed in 0.10s
```

### Step 6 — full suite

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 36%]
........................................................................ [ 72%]
.......................................................                  [100%]
199 passed in 128.70s (0:02:08)
```

199 = 192 pre-existing + 7 new baseline tests. No warnings summary was
emitted (pytest shows one in `-q` mode when warnings exist).

### Step 7 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... else echo "Checkpoint 4 verified; workspace has no Git metadata."; fi
Checkpoint 4 verified; workspace has no Git metadata.
```

No `git init` was run.

## Self-review

- All three files byte-identical to the corrected brief (diffs above);
  nothing transcribed from memory of the first attempt.
- The corrected fixture (`rationale: Protect data.` as metadata) populates
  the `rationale` field, satisfying
  `requirement["rationale"].startswith("Protect")`; all other assertions in
  that test (`title`, `attributes["priority"]`, `location["file"]`) were
  already passing.
- Load-bearing payload key spellings confirmed present exactly once each in
  `baseline.py`: `authoredName`, `authoredFingerprint`,
  `semanticFingerprint`, `contentFingerprint`, `location` — emitted under
  the camelCase names the schema requires and later tasks read.
- The invalid-baseline test proves the diagnostic payload is schema-valid
  with `valid: false`, carries `declarations` and the REQ004 finding, and
  omits `objects`/`semanticGraphFingerprint` (both absent from the payload
  and optional in the schema — exactly the designed asymmetry).
- `write_baseline` routes all writes through `export._write_atomic_text`
  (deterministic `render_baseline`: sorted keys, `indent=2`, trailing
  newline) and refuses to overwrite without `force`; the test verifies the
  sentinel bytes are unchanged after the refused write.
- Pre-verified before implementing (first attempt, unchanged since): every
  import the brief's `baseline.py` needs exists with the assumed shape —
  `fingerprints.*`, `snapshot.AnalysisSnapshot/LocationRecord/thaw_json`,
  `analysis.AnalysisResult`, `config.NeedsConfig/reference_date`,
  `export._write_atomic_text` (creates parent dirs),
  `quality.report_from_snapshot(snapshot, config, queries=...)`,
  `relations.DEFAULT_RELATION_CATALOG.version`,
  `rules.RULE_SET_VERSION == "1"`, `quarto_needs.__version__`.
- Global Constraints: no new runtime dependency (stdlib + existing package
  modules only; `jsonschema` already used by the new test); no signature or
  exit-code changes; no CLI command touched, so the one-`analyze_project`
  per invocation guarantee is unaffected; schema v1 `needs.json` untouched
  (this task writes only to `tmp_path` destinations); no Git metadata
  created; preview server on 127.0.0.1:8777 untouched; no new shortcode and
  no `extensions.quartoNeeds` projection.

## Concerns

- First attempt (honest record, one line): the original brief's fixture
  authored rationale as a `### Rationale` heading, which the Milestone-1
  parser leaves in `body` (rationale is populated only from metadata lines),
  so `test_baseline_stores_authored_content_not_only_fingerprints` failed
  6/7; I stopped and restored per the stop-and-report rule, the controller
  confirmed the defect and applied my recommended one-line fixture fix to
  brief and plan, and this run used the corrected brief verbatim.
- Minor, non-blocking: Step 3's actual exception class/message is
  `ImportError: cannot import name 'baseline' from 'quarto_needs'` rather
  than the brief's predicted `ModuleNotFoundError: No module named
  'quarto_needs.baseline'` — same root cause (module absent), and
  `ModuleNotFoundError` is an `ImportError` subclass; identical to the
  wording deviation Task 3's report already flagged.
- No other concerns.
