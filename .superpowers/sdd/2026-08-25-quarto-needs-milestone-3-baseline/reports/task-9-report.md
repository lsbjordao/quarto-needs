# Task 9 Report: Impact traversal over the union graph

## Summary

Implemented the union-graph impact traversal per the corrected brief: created
`src/quarto_needs/impact.py` (`ImpactError`, `ImpactReport` with `.to_dict()`,
`_union_edges`, `_origins`, `_priority`, `analyze`) and
`tests/test_impact.py` (7 tests). Both files are byte-identical to the
corrected brief's code blocks (verified via `diff` against the extracted
blocks). TDD order followed with captured evidence for the failing run and
every passing run. Final state: 7/7 impact tests pass; full suite
`234 passed in 231.97s (0:03:51)`, no warnings (227 pre-existing + 7 new).

## Files changed

- Created: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/impact.py`
  (159 lines, byte-identical to the brief's Step 3 block, brief lines 215-373)
- Created: `/home/lsbjordao/Repos/quarto-needs/tests/test_impact.py`
  (165 lines, 7 tests, byte-identical to the brief's Step 1 block, brief
  lines 39-203, including the controller's DOC-1-before-TC-1 `CHAIN` order)
- No other file touched.

## TDD evidence

### Verbatim transcription checks (run against the corrected brief)

```
$ diff <(sed -n '215,373p' briefs/task-9-brief.md) src/quarto_needs/impact.py
IMPACT-BYTE-IDENTICAL
$ diff <(sed -n '39,203p' briefs/task-9-brief.md) tests/test_impact.py
TESTS-BYTE-IDENTICAL
```

(No diff output means byte-identical.) Fixture order confirmed in the
extracted file: DOC-1 block at line 29, TC-1 block at line 35, so
`write(keep_test=False)` truncates only the TC-1 block and REQ-1's
`conflicts-with: DOC-1` edge stays resolvable.

### Step 2 — tests fail before implementation

```
$ .venv/bin/python -m pytest tests/test_impact.py -q
ImportError while importing test module '.../tests/test_impact.py'
tests/test_impact.py:7: in <module>
    from quarto_needs import baseline, impact
E   ImportError: cannot import name 'impact' from 'quarto_needs' (...)
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.93s
```

The brief predicted `ModuleNotFoundError: No module named
'quarto_needs.impact'`; the from-import from an existing package surfaces as
`ImportError: cannot import name 'impact'` instead. Same failure mode (module
absent) — cosmetic wording difference only.

### Step 4 — impact tests pass after implementation

```
$ .venv/bin/python -m pytest tests/test_impact.py -q
.......                                                                  [100%]
7 passed in 0.08s
```

### Step 5 — full suite

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 30%]
........................................................................ [ 61%]
........................................................................ [ 92%]
..................                                                        [100%]
234 passed in 231.97s (0:03:51)
```

234 = 227 pre-existing + 7 new impact tests. No warnings summary was emitted
(pytest shows one in `-q` mode when warnings exist).

### Step 6 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... else echo "Checkpoint 9 verified; workspace has no Git metadata."; fi
Checkpoint 9 verified; workspace has no Git metadata.
```

No `git init` was run.

## Self-review

- Both files byte-identical to the corrected brief (diffs above); nothing
  transcribed by hand — the code blocks were extracted directly from the brief
  with `sed` and the byte-identity proven with `diff`.
- The corrected fixture behaves as ruled: with DOC-1 before TC-1, the
  `keep_test=False` truncation drops only the test case; REQ-1 keeps
  `conflicts-with: DOC-1` resolvable, so the snapshot stays valid and the
  removal test's two-origin assertion (TC-1 "removed", REQ-1
  "relation-removed") passes — `verified-by` is `source_to_target`, so the
  removed test can never reach the requirement it verified, exactly as the
  test docstring documents.
- Union adjacency is load-bearing and falsifiable: test 5 drops only the
  `conflicts-with` line, so DOC-1 is reachable solely through the
  baseline-only edge (direction `both`), and the report shows
  `classification: direct`, `relations: ["conflicts-with"]`.
- Guards verified: `ImpactError` on a diagnostic baseline (`valid: false`)
  and on a configuration fingerprint mismatch without `recompute`; success
  with `recompute=True`. `analyze` internally calls
  `diff_module.compare(..., recompute=True)` unconditionally by design, so
  origins are always classified under one policy.
- Path invariants hold in every impacted record (`path[0] == origin`,
  `path[-1] == id`, `len(path) == distance + 1`, classification in
  {direct, transitive}, priority present); the BFS queue guarantees the
  first path found is the shortest, so `distance` and `path` always agree.
- Global Constraints: no new runtime dependency (reuses Task 7's
  `quarto_needs.diff` and stdlib `collections`/`dataclasses`/`typing`);
  `analyze` is pure — no filesystem access; every existing signature and
  command preserved (all 227 pre-existing tests pass unchanged); schema v1
  `needs.json` untouched (impact writes nothing); no Git metadata created;
  preview server on 127.0.0.1:8777 untouched; no new shortcode and no
  `extensions.quartoNeeds` projection.

## Concerns

- The first attempt was blocked and restored under the stop-and-report rule
  (the pre-correction fixture placed DOC-1 after TC-1, so
  `write(keep_test=False)` truncated DOC-1 too and left
  `conflicts-with: DOC-1` dangling — REQ005 error, `snapshot=None`); the
  controller accepted the report, confirmed the defect was theirs, and moved
  the DOC-1 block before TC-1 in plan and brief 9 — this run used the
  corrected brief verbatim and completes the task. No other concerns.

## Fix-round addendum: reference-date guard (post-Task 10 review)

Task 10's review falsified a spec violation inherited from the plan's Task 9
code: `analyze` guarded only on `configurationFingerprint`, so a baseline
written under a different reference date traversed silently (exit 0). The
controller amended plan and brief 9; this round applied the amended brief
verbatim. Both files remain byte-identical to the brief (same `sed`/`diff`
method, block ranges updated: tests lines 39-217, implementation lines
229-393).

Changes:

- `tests/test_impact.py` (165 -> 179 lines): new
  `test_impact_rejects_a_reference_date_mismatch_without_recompute`
  (brief lines 198-209) — baseline `referenceDate` edited to `1999-01-01`;
  `analyze` must raise `ImpactError` without `recompute` and succeed with
  `recompute=True`.
- `src/quarto_needs/impact.py` (159 -> 165 lines): the guard block now nests
  both checks under `if not recompute:` — configuration fingerprint first,
  then `referenceDate` vs `snapshot.reference_date`, each with its own
  `ImpactError` message (the date message names `--recompute-with current`).

TDD evidence:

```
$ .venv/bin/python -m pytest tests/test_impact.py -q        # new test first, old guard
1 failed, 7 passed in 0.07s
FAILED tests/test_impact.py::test_impact_rejects_a_reference_date_mismatch_without_recompute
>       with pytest.raises(impact.ImpactError):
E       Failed: DID NOT RAISE ImpactError
tests/test_impact.py:168: Failed
```

The failure is the spec violation itself (no raise on date mismatch), not a
fixture artifact.

```
$ .venv/bin/python -m pytest tests/test_impact.py -q        # after the guard change
........                                                                  [100%]
8 passed in 0.05s

$ .venv/bin/python -m pytest -q
........................................................................ [ 30%]
........................................................................ [ 60%]
........................................................................ [ 90%]
......................                                                   [100%]
238 passed in 156.07s (0:02:36)
```

238 = 237 collected before this round (234 from my original completion + 3
added by Task 10) + 1 new date-mismatch test. No warnings summary emitted.

```
$ (conditional checkpoint)
Checkpoint 9 verified; workspace has no Git metadata.
```

Fix-round self-review: the nested guard preserves the original configuration
message byte-for-byte and adds the date check only inside `if not recompute:`,
so `recompute=True` still bypasses both (matching the test's success half and
`compare(..., recompute=True)` downstream); the date guard reads
`baseline_payload.get("referenceDate", "")` against
`snapshot.reference_date`, mirroring `diff.compare`'s own date axis; no other
file touched, no new dependency, `analyze` remains pure.
