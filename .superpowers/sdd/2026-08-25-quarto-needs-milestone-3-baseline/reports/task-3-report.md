# Task 3 Report: Fingerprints and the reference-date-bearing snapshot

## Summary

Implemented `src/quarto_needs/fingerprints.py` with six pure content-fingerprint
functions, added four defaulted fields to `AnalysisSnapshot`
(`reference_date`, `configuration_fingerprint`, `semantic_graph_fingerprint`,
`representation_fingerprint`) in `src/quarto_needs/snapshot.py`, and wired
population of those fields into the final (post-rule-merge) snapshot in
`src/quarto_needs/analysis.py`. All code and test text was taken verbatim
from the task brief.

## Files changed

- Created: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/fingerprints.py`
- Modified: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/snapshot.py`
  (added 4 defaulted fields to `AnalysisSnapshot`)
- Modified: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/analysis.py`
  (added `from . import fingerprints` and `reference_date` to the existing
  `.config` import line; replaced the draft/snapshot construction block to
  compute and attach the four fingerprint/date fields from the final objects
  and relations)
- Created: `/home/lsbjordao/Repos/quarto-needs/tests/test_fingerprints.py`
- Modified: `/home/lsbjordao/Repos/quarto-needs/tests/test_snapshot.py`
  (added `Path` import and the new
  `test_snapshot_records_reference_date_and_fingerprints` test)

## TDD evidence

### Step 2 — fingerprint tests fail before implementation

```
$ .venv/bin/python -m pytest tests/test_fingerprints.py -q
==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_fingerprints.py __________________
ImportError while importing test module '.../tests/test_fingerprints.py'.
tests/test_fingerprints.py:3: in <module>
    from quarto_needs import fingerprints
E   ImportError: cannot import name 'fingerprints' from 'quarto_needs' (.../src/quarto_needs/__init__.py)
=========================== short test summary info ============================
ERROR tests/test_fingerprints.py
1 error in 0.06s
```

Note: the brief predicted `ModuleNotFoundError: No module named
'quarto_needs.fingerprints'`. The actual exception raised by `from
quarto_needs import fingerprints` when the submodule doesn't exist is
`ImportError: cannot import name 'fingerprints' from 'quarto_needs'`
(`ModuleNotFoundError` is a subclass of `ImportError`; the message differs
because this is a "from X import Y" failure rather than a bare `import
quarto_needs.fingerprints`). The failure is for the correct underlying
reason — the module does not exist yet — so this is not a concern, just a
wording mismatch worth flagging.

### Step 4 — fingerprint tests pass after implementation

```
$ .venv/bin/python -m pytest tests/test_fingerprints.py -q
......                                                                   [100%]
6 passed in 0.02s
```

### Step 6 — snapshot-field test fails before implementation

```
$ .venv/bin/python -m pytest tests/test_snapshot.py -q -k reference_date_and_fingerprints
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_snapshot_records_reference_date_and_fingerprints _____________
    snapshot = analyze_project(tmp_path).snapshot
    assert snapshot is not None
>   assert snapshot.reference_date == reference_date().isoformat()
           ^^^^^^^^^^^^^^^^^^^^^^^
E   AttributeError: 'AnalysisSnapshot' object has no attribute 'reference_date'
1 failed, 1 deselected in 0.04s
```

Exact match to the brief's expected failure.

### Step 9 — snapshot and analysis tests pass after implementation

```
$ .venv/bin/python -m pytest tests/test_snapshot.py tests/test_analysis.py -q
.............                                                            [100%]
13 passed in 0.04s
```

## Import chain check

Per the task instructions, verified by actually importing the package
rather than reasoning about it:

```
$ .venv/bin/python -c "import quarto_needs.analysis; print('OK import chain works')"
OK import chain works
```

The chain `analysis -> fingerprints -> rules -> config -> snapshot` resolves
with no cycle.

## Alias-flip falsification experiment

The load-bearing test is
`test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation`.
Per instructions, I removed the `sorted(...)` around the endpoint pair in
`relation_semantic_fingerprint` (replacing it with an unsorted tuple in
source/target order) and re-ran the fingerprint tests:

```
$ .venv/bin/python -m pytest tests/test_fingerprints.py -q
..F...                                                                   [100%]
=================================== FAILURES ===================================
__ test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation ___
    assert fingerprints.relation_semantic_fingerprint(forward) == \
        fingerprints.relation_semantic_fingerprint(inverse)
E   AssertionError: assert '99c5e4ddf136...cc302d7477541' == '6df83aed16fe...6b960c94cf917'
E
E     - 6df83aed16feea4a4bb911d3b235f696aba29c10ded15542e166b960c94cf917
E     + 99c5e4ddf13691bd4825ee3f7d6387a3fe19a6a5525e69c3d53cc302d7477541
1 failed, 5 passed in 0.07s
```

This confirms the test actually exercises the endpoint-sort mechanism: with
source/target order used verbatim, `REQ -verified-by-> TC` and
`TC -verifies-> REQ` hash differently, exactly the false "edge
removed + edge added" report this milestone exists to prevent.

I then restored the original file from a backup made before the edit and
verified the restoration with `diff` (not by assuming it):

```
$ diff /tmp/.../scratchpad/fingerprints.py.bak src/quarto_needs/fingerprints.py
$ echo "diff exit code: $?"
diff exit code: 0
```

Zero-byte diff confirms exact restoration. Re-ran the fingerprint suite to
confirm recovery:

```
$ .venv/bin/python -m pytest tests/test_fingerprints.py -q
......                                                                   [100%]
6 passed in 0.02s
```

## Step 10 — needs.json byte-identity gate

```
$ sha256sum examples/book/.quarto-needs/needs.json
d53be57fe6c2e438b7e06083ab64868e6dd3c93e50fedbf45f58a4470a5616da  examples/book/.quarto-needs/needs.json
$ make sync-example >/dev/null 2>&1
$ sha256sum examples/book/.quarto-needs/needs.json
d53be57fe6c2e438b7e06083ab64868e6dd3c93e50fedbf45f58a4470a5616da  examples/book/.quarto-needs/needs.json
```

Identical hashes before and after. Fingerprints did not reach the v1 JSON
projection — the Global Constraint that schema v1 bytes are unchanged holds.

## Step 11 — full suite

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 37%]
........................................................................ [ 75%]
................................................                         [100%]
192 passed in 122.49s (0:02:02)
```

192 = 185 baseline + 6 new fingerprint tests + 1 new snapshot test. Zero
warnings (also confirmed with a separate `-W error` run that passed cleanly,
meaning no warnings were emitted at all).

## Step 12 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... else echo "Checkpoint 3 verified; workspace has no Git metadata."; fi
Checkpoint 3 verified; workspace has no Git metadata.
```

No `git init` was run, per the task's explicit instruction that this
workspace has no Git metadata and none should be created.

## Self-review

- Reviewed the final content of all three modified/created source files
  side-by-side against the brief's verbatim code blocks — they match
  exactly (confirmed via `diff` after the falsification/restoration cycle
  for `fingerprints.py`, and by direct reading for `snapshot.py` and
  `analysis.py`).
- Checked for other construction sites of `AnalysisSnapshot` in the live
  source tree (`grep -rn "AnalysisSnapshot(" --include="*.py" .`): only one
  live call site exists (`src/quarto_needs/analysis.py`), already updated.
  Other matches are historical snapshots under
  `.superpowers/sdd/.../snapshots/` and are not part of the live package.
  The four new fields all carry defaults, so no other test or call site
  needed updating — confirmed empirically by the full suite staying green.
- Checked that `object_content_fingerprint` deliberately includes both
  `attributes` and the derived `priority`/`tags` fields as instructed (not
  simplified away), matching the ambiguity resolution given in the task
  context.
- Confirmed each new test would actually fail if its named property
  regressed:
  - `test_object_fingerprint_ignores_line_numbers_and_file`: would fail if
    `locations`/line numbers were folded into the digest.
  - `test_object_fingerprint_changes_with_every_authored_field`: iterates
    every field named in the spec and asserts a fingerprint change per
    field — would catch a field silently dropped from the digest.
  - `test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation`:
    falsified live (see above) — proven to fail when the sort is removed.
  - `test_semantic_relation_fingerprint_changes_with_family_and_endpoints`:
    exercises family, endpoint identity, and attributes independently.
  - `test_graph_fingerprint_is_order_independent_and_configuration_sensitive`:
    would fail if `semantic_graph_fingerprint` stopped sorting its inputs,
    or if it ignored the `configuration` parameter.
  - `test_configuration_fingerprint_tracks_catalog_and_rule_set_versions`:
    would fail if `relation_catalog_version` were dropped from the digest.
  - `test_snapshot_records_reference_date_and_fingerprints`: exercises the
    full `analyze_project` pipeline end-to-end, so it would fail if wiring
    in `analysis.py` were incomplete or fields were left at their `""`
    defaults.
- No dead code, no renamed identifiers, no signature changes to any of the
  preserved functions listed in the Global Constraints.

## Concerns

- Minor, non-blocking: the actual exception class/message when importing a
  nonexistent submodule via `from package import submodule` is
  `ImportError: cannot import name 'X' from 'package'` rather than the
  brief's stated `ModuleNotFoundError: No module named
  'quarto_needs.fingerprints'`. Both indicate the same root cause (module
  absent) and `ModuleNotFoundError` is a subclass of `ImportError`, so this
  is purely a documentation/wording discrepancy in the brief, not a defect.
- No other concerns. All Global Constraints verified: no new runtime
  dependency added, single `analyze_project` call per invocation preserved
  (no CLI command touched), all listed preserved signatures untouched,
  schema v1 bytes unchanged (Step 10), fingerprints exclude line
  numbers/`href`/generated metrics, exit codes untouched, no Git metadata
  created, preview server untouched, no new shortcode or
  `extensions.quartoNeeds` projection added.
