# Task 10 Report: `impact` command and its schema

## Summary

Implemented the `impact` CLI command per the brief: created
`schemas/impact-v1.schema.json`, added the `impact` parser block, the
`_impact` handler, and the dispatch to `src/quarto_needs/cli.py`, and added
the 3 brief tests to `tests/test_cli.py`. Every inserted block is
byte-identical to the brief's code blocks (verified via `diff` against the
extracted lines). The one ruled change from the Task 8 review was also
applied: the live `diff` parser's `--recompute-with` help string now carries
the corrected wording. TDD order followed with captured evidence for the
failing run and every passing run. Final state: 52/52 CLI tests pass; full
suite `237 passed in 169.00s (0:02:48)`, no warnings (234 pre-existing + 3
new).

## Files changed

- Created: `/home/lsbjordao/Repos/quarto-needs/schemas/impact-v1.schema.json`
  (42 lines, byte-identical to the brief's Step 1 block, brief lines 37-78)
- Modified: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/cli.py`
  (418 -> 466 lines)
  - line 13: `from . import impact as impact_module` (brief Step 4)
  - lines 312-346: `_impact` handler above `main` (brief Step 5 block,
    brief lines 169-203, byte-identical)
  - lines 391-399: `impact` parser block after the `diff` parser block
    (brief Step 4 block, brief lines 151-159, byte-identical)
  - lines 422-423: dispatch next to `diff`, before the shared
    `result = analyze_project(root, config=config)` line (brief Step 6
    block, brief lines 211-212, byte-identical)
  - line 389: the ONE ruled change beyond the brief's insertions — the
    live `diff` parser's `--recompute-with` help string changed from
    "Re-evaluate both sides under the current configuration and reference
    date" to "Re-resolve the baseline's relations under the current
    configuration and reference date" (same wording the brief uses for
    `impact`). No test asserts the string; no other existing cli.py line
    was touched.
- Modified: `/home/lsbjordao/Repos/quarto-needs/tests/test_cli.py`
  (766 -> 820 lines; the 3 tests at lines 769, 792, 809 are byte-identical
  to the brief's Step 2 block, brief lines 86-137)
- No other file touched.

## TDD evidence

### Verbatim transcription checks (run against the brief)

```
$ diff <(sed -n '37,78p' briefs/task-10-brief.md) schemas/impact-v1.schema.json
SCHEMA-BYTE-IDENTICAL
$ diff <(sed -n '86,137p' briefs/task-10-brief.md) <(tail -n 52 tests/test_cli.py)
TESTS-BYTE-IDENTICAL
$ diff <(sed -n '169,203p' briefs/task-10-brief.md) <(sed -n '312,346p' src/quarto_needs/cli.py)
HANDLER-BYTE-IDENTICAL
$ diff <(sed -n '151,159p' briefs/task-10-brief.md) <(sed -n '391,399p' src/quarto_needs/cli.py)
PARSER-BYTE-IDENTICAL
$ diff <(sed -n '211,212p' briefs/task-10-brief.md) <(sed -n '422,423p' src/quarto_needs/cli.py)
DISPATCH-BYTE-IDENTICAL
```

(No diff output means byte-identical.)

### Step 3 — tests fail before implementation

```
$ .venv/bin/python -m pytest tests/test_cli.py -q -k impact
...
E       SystemExit: 2
...
message = "quarto-needs: error: argument command: invalid choice: 'impact' (choose from scan, check, coverage, trace, export, quality, query, baseline, diff)\n"
...
FAILED tests/test_cli.py::test_impact_validates_against_the_impact_schema - S...
FAILED tests/test_cli.py::test_impact_runs_exactly_one_analysis - SystemExit: 2
FAILED tests/test_cli.py::test_impact_rejects_a_configuration_mismatch - Syst...
3 failed, 49 deselected in 0.45s
```

Exactly the brief's prediction: FAIL with `SystemExit: 2`, the `impact`
command does not exist.

### Step 7 — CLI tests pass after implementation

```
$ .venv/bin/python -m pytest tests/test_cli.py -q
....................................................                     [100%]
52 passed in 0.40s
```

52 = 49 pre-existing + 3 new impact tests.

### Step 8 — full suite

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 30%]
........................................................................ [ 60%]
........................................................................ [ 91%]
.....................                                                    [100%]
237 passed in 169.00s (0:02:48)
```

237 = 234 pre-existing + 3 new. No warnings summary was emitted (pytest
shows one in `-q` mode when warnings exist).

### Manual smoke (both output formats, temp dir)

```
$ quarto-needs --root <tmp> impact <tmp>/baselines/quarto-needs.json
origin REQ-1 (modified)
impact rc: 0

$ quarto-needs --root <tmp> impact <tmp>/baselines/quarto-needs.json --format json
{
  "impacted": [],
  "origins": [
    {
      "change": "modified",
      "fields": [
        "body"
      ],
      "id": "REQ-1"
    }
  ],
  "schemaVersion": "1"
}
```

The empty `impacted` array is correct for this fixture: the `references`
relation has `impactDirection "none"` (`src/quarto_needs/relations.py`
line 73), so a body change to REQ-1 propagates nothing — the schema test
asserts only `payload["origins"]`, which is non-empty.

### Step 9 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... else echo "Checkpoint 10 verified; workspace has no Git metadata."; fi
Checkpoint 10 verified; workspace has no Git metadata.
```

No `git init` was run.

## Self-review

- Every inserted block is byte-identical to the brief (five `diff` proofs
  above); nothing was transcribed by hand — blocks were extracted from the
  brief with `sed` and proven identical with `diff`.
- One analysis per invocation: `_impact` calls `analyze_project` exactly
  once and its dispatch returns before the shared
  `result = analyze_project(root, config=config)` line, mirroring `diff`;
  `test_impact_runs_exactly_one_analysis` locks the guarantee.
- Exit codes match the stable contract: 2 for baseline load failure and for
  `ImpactError` (diagnostic baseline, configuration fingerprint mismatch
  without `--recompute-with` — the error text names `--recompute-with`, so
  the mismatch test's stderr assertion holds), 1 for an invalid project
  (snapshot is None), 0 on success in both formats.
- `ImpactReport.to_dict()` emits exactly `schemaVersion`/`origins`/
  `impacted`, and every origin/impacted record satisfies the schema's
  `additionalProperties: false` and required-key sets; the schema test
  also runs `Draft202012Validator.check_schema` on the file itself.
- The dispatch is routed before the shared analysis line, so `impact`
  never triggers a second analysis through the fallthrough path
  (`check`/`coverage`/`trace`/`export` remain untouched).
- Global Constraints: no new runtime dependency (`jsonschema` is imported
  only inside the new test and already ships for the diff schema test);
  every existing signature and command preserved (all 234 pre-existing
  tests pass unchanged); schema v1 `needs.json` untouched (impact writes
  nothing); no Git metadata created; preview server on 127.0.0.1:8777
  untouched; no new shortcode and no `extensions.quartoNeeds` projection.

## Concerns

- None blocking. One observation for the reviewer: unlike `diff`, `_impact`
  returns 0 on success regardless of profile or gate regressions. This is
  the brief's verbatim handler — impact explains propagation, it is not a
  policy gate — but the asymmetry with `diff`'s `profile_exit_code` return
  is intentional and worth knowing when documenting exit codes.
- The text-format `impacted` rendering is exercised only by the manual
  smoke above, not by a brief test (the brief specifies exactly 3 tests;
  the JSON path is the one validated against the schema).
