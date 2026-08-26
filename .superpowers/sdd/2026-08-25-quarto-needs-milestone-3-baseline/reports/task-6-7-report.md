# Task 6+7 Report: Diff engine — report, guards, classification, and `compare`

## Summary

Implemented the complete semantic diff engine per the corrected briefs:
`src/quarto_needs/diff.py` (378 lines) containing `DiffError`, the frozen
`DiffReport` dataclass with `to_dict()`/`is_empty()`, object and relocation
classification, relation classification keyed by semantic or authored
fingerprint, findings/metrics/gates classification, `_recomputed_relations`,
and `compare` with both guards (configuration-changed, reference-date-changed)
plus the `recompute` escape hatch; and `tests/test_diff.py` (271 lines) with
all fifteen brief tests (6 structural, 6 guard, 3 derived-delta). Every code
block is byte-verbatim from the two briefs.

This is the second attempt. The first attempt stopped under the stop-and-report
rule on a genuine plan-mandated fixture defect; the controller confirmed it and
applied exactly my recommended corrections to plan and brief (see Concerns).
This run used the corrected briefs verbatim, and every brief prediction was
met exactly, including Task 6 Step 7's designed red state. Final state: 15/15
diff tests pass; full suite `220 passed in 226.21s`, no warnings
(205 pre-existing + 15 new).

## Files changed

- Created: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/diff.py`
  (0 -> 378 lines; the four brief blocks in order: module docstring +
  `DiffReport`/`DiffError` from Task 6 Step 4, object/relocation
  classification from Step 5, relation classification from Step 6, then the
  Task 7 Step 3 derived-delta helpers and Step 4 `_recomputed_relations` +
  `compare`)
- Created: `/home/lsbjordao/Repos/quarto-needs/tests/test_diff.py`
  (0 -> 271 lines; Task 6 Step 1 structural tests, Step 2 guard tests, and
  Task 7 Step 1 derived-delta tests, in brief order)
- No other file touched.

## TDD evidence

### Task 6 Step 3 — tests fail before the module exists

Brief predicted `ModuleNotFoundError: No module named 'quarto_needs.diff'`.
The failure has the same cause at the same stage (module missing, collection
time) but surfaces as an `ImportError` because the import is
`from quarto_needs import baseline, diff` into an existing package
(cosmetic wording difference only; flagged in Concerns):

```
$ .venv/bin/python -m pytest tests/test_diff.py -q
==================================== ERRORS ====================================
_____________________ ERROR collecting tests/test_diff.py ______________________
ImportError while importing test module '/home/lsbjordao/Repos/quarto-needs/tests/test_diff.py'.
Traceback:
tests/test_diff.py:7: in <module>
    from quarto_needs import baseline, diff
E   ImportError: cannot import name 'diff' from 'quarto_needs' (/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/__init__.py)
=========================== short test summary info ============================
ERROR tests/test_diff.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.26s
```

### Task 6 Step 7 — structural tests still red after the helpers (designed end state)

All six fail with exactly the predicted
`AttributeError: module 'quarto_needs.diff' has no attribute 'compare'` and
nothing else — including `test_added_and_removed_objects_are_classified`,
which under the corrected fixture now reaches `diff.compare` (its fixture no
longer dangles `verified-by: TC-1`), confirming the failures are the designed
`compare`-does-not-exist state, not errors inside the helpers:

```
$ .venv/bin/python -m pytest tests/test_diff.py -q -k "identical or reordering or moving or editing or added_and_removed or changed_id"
>       report = diff.compare(before, snapshot, config)
                 ^^^^^^^^
E       AttributeError: module 'quarto_needs.diff' has no attribute 'compare'
tests/test_diff.py:128: AttributeError
=========================== short test summary info ============================
FAILED tests/test_diff.py::test_identical_input_produces_an_empty_diff - Attr...
FAILED tests/test_diff.py::test_reordering_declarations_is_not_a_change - Att...
FAILED tests/test_diff.py::test_moving_a_need_to_another_file_is_relocation_only
FAILED tests/test_diff.py::test_editing_a_body_is_a_modification_named_by_field
FAILED tests/test_diff.py::test_added_and_removed_objects_are_classified - At...
FAILED tests/test_diff.py::test_a_changed_id_is_removal_plus_addition - Attri...
6 failed, 6 deselected in 0.15s
```

### Task 6 Step 8 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... fi
Checkpoint 6 verified; workspace has no Git metadata.
```

### Task 7 Step 2 — all fifteen tests red before `compare`

Every failure is the predicted AttributeError at `diff.compare`:

```
$ .venv/bin/python -m pytest tests/test_diff.py -q
>       report = diff.compare(before, snapshot, config)
                 ^^^^^^^^
E       AttributeError: module 'quarto_needs.diff' has no attribute 'compare'
...
=========================== short test summary info ============================
FAILED tests/test_diff.py::test_identical_input_produces_an_empty_diff - Attr...
FAILED tests/test_diff.py::test_reordering_declarations_is_not_a_change - Att...
FAILED tests/test_diff.py::test_moving_a_need_to_another_file_is_relocation_only
FAILED tests/test_diff.py::test_editing_a_body_is_a_modification_named_by_field
FAILED tests/test_diff.py::test_added_and_removed_objects_are_classified - At...
FAILED tests/test_diff.py::test_a_changed_id_is_removal_plus_addition - Attri...
FAILED tests/test_diff.py::test_configuration_change_suppresses_derived_deltas
FAILED tests/test_diff.py::test_reference_date_change_suppresses_date_derived_deltas
FAILED tests/test_diff.py::test_recompute_clears_the_guards - AttributeError:...
FAILED tests/test_diff.py::test_configuration_change_still_compares_authored_relations
FAILED tests/test_diff.py::test_recompute_reresolves_baseline_relations_through_the_catalog
FAILED tests/test_diff.py::test_an_invalid_baseline_is_never_comparable - Att...
FAILED tests/test_diff.py::test_new_findings_are_reported_when_the_configuration_is_stable
FAILED tests/test_diff.py::test_metric_deltas_name_the_scope_and_strength - A...
FAILED tests/test_diff.py::test_report_dict_is_json_safe_and_flags_emptiness
15 failed in 0.27s
```

### Task 7 Step 5 — diff tests pass

Brief expected "PASS, all fifteen":

```
$ .venv/bin/python -m pytest tests/test_diff.py -q
...............                                                          [100%]
15 passed in 0.14s
```

### Task 7 Step 6 — full suite

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 98%]
....                                                                     [100%]
220 passed in 226.21s (0:03:46)
```

220 = 205 pre-existing + 15 new diff tests. No warnings summary was emitted
(pytest shows one in `-q` mode when warnings exist).

### Task 7 Step 7 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... fi
Checkpoint 7 verified; workspace has no Git metadata.
```

No `git init` was run; the workspace still has no Git metadata.

## Self-review

- All six brief code blocks (Task 6 Steps 1, 2, 4, 5, 6; Task 7 Steps 1, 3, 4)
  transcribed verbatim from the corrected briefs; nothing written from memory
  of the first attempt without re-checking the corrected text — the two ruled
  test corrections are present in the delivered file and the previously
  defective test now passes through the real `compare`.
- The structural acceptance gate in miniature is green: identical input diffs
  empty; reordering two blocks is not a change; moving a need to another file
  is relocation only (file + line on both sides, no modification); a body
  edit is a modification named `["body"]`; added/removed objects are
  classified; a changed id is removal plus addition, never a rename heuristic.
- Guard behavior verified by the tests: a configuration change or reference
  date change emits its notice and suppresses only the derived categories
  (findings, metrics, gates) while authored object and relation comparison
  continues (authored-fingerprint keying); `recompute=True` clears the guards
  and re-resolves baseline relations through the current catalog (the poisoned
  semanticFingerprint test proves stored families are not trusted); an invalid
  baseline raises `DiffError` before any comparison.
- Derived deltas verified: a new REQ002 warning with stable configuration
  lands in `findings_added` with no notices; removing the verification edge
  produces a metric delta naming scope `approved-requirements`, strength
  `verification-trace`, with `before > after`; `to_dict()` is JSON-safe,
  flags `empty: true`, and declares schema version "1".
- `compare` is a pure function: it reads only its arguments plus in-memory
  re-derivations (`report_from_snapshot(snapshot, config)`); no filesystem
  access, no new runtime dependency, no new CLI command or shortcode, and no
  change to any existing signature. All 205 pre-existing tests still pass,
  proving the protected surface is untouched.
- Global Constraints: no new dependency; no git init (both checkpoints
  conditional no-ops); the preview server on 127.0.0.1:8777 was never
  touched; only the two permitted files were created; schema v1 and all
  existing commands/signatures preserved.

## Concerns

- Honest record of the blocked first attempt: the original briefs contained a
  plan-mandated defect — `test_added_and_removed_objects_are_classified`
  removed `TC-1` but left REQ-1's `verified-by: TC-1` dangling, firing
  structural REQ005 so `analyze_project` returned `snapshot=None` and the
  shared `snapshot_of` helper failed before `diff.compare` was ever called.
  I stopped under the stop-and-report rule, restored both files (verified
  `205 passed`), and reported with a recommended fix. The controller
  confirmed the defect and applied exactly three corrections to plan and
  brief: (1) that test's `needs.qmd` rewrite now ends with
  `.replace("verified-by: TC-1\n", "")`; (2) the no-op
  `.replace("verified-by: TC-1", "verified-by: TC-1")` fossil was removed
  from `test_a_changed_id_is_removal_plus_addition`; (3) Task 7 Step 5 now
  says "all fifteen". This run used the corrected briefs verbatim and every
  prediction held.
- Cosmetic deviation (unchanged from the first attempt): Task 6 Step 3
  predicts `ModuleNotFoundError: No module named 'quarto_needs.diff'`, but
  Python surfaces the missing submodule as
  `ImportError: cannot import name 'diff' from 'quarto_needs'` for a
  `from package import name` import. Same failure cause and stage (collection
  time, module absent); no action needed.
- No other concerns.

## Fix round 1 (executed by the controller)

The original fix-round dispatch to the implementer died on an account usage
limit before touching any file (verified: live tree byte-identical to
task-6-after). Per the Task 1 precedent (ledger), the controller executed the
ruled fix round directly:

- Added `test_recompute_does_not_manufacture_derived_deltas_from_a_config_change`
  to tests/test_diff.py. First version of the test passed vacuously against the
  buggy code (fixture coverage was 100%, so the 100.0 gate still passed); the
  sharpened fixture adds an approved-but-unverified REQ-2 so verification
  coverage is 50% and the phantom regression actually fires. Plan and brief 6
  carry the sharpened version.
- RED evidence (buggy code, sharpened test): FAILED with
  `{'name': 'min-verification-trace', 'scope': 'approved-requirements', 'threshold': 100.0, 'actual': 50.0}`
  in gate_regressions — exactly the reviewer's falsification.
- Applied the ruled `compare` change: `configuration_differs` / `date_differs`
  booleans; `derived_suppressed = configuration_differs or date_differs`;
  corrected comment. Dropped the unused `field` import (review Minor).
- GREEN: tests/test_diff.py 16 passed; full suite `221 passed in 248.66s`,
  no warnings.
- Reverse falsification: reverting only the predicate to `bool(notices)` makes
  the new test fail again; restoration verified byte-identical; 16 passed.

File-size correction (review Minor #3): src/quarto_needs/diff.py and
tests/test_diff.py sizes in the original report were wrong; the shipped sizes
per the review package are authoritative. Independent re-review of this fix is
pending the account limit reset; the fix1 package is at
reviews/task-6-fix1-package.md.
