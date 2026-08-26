# Task 1 Report: Close the exit-code-3 gap (carried from Milestone 3)

## Summary

Mapped `scan` and `export` operational write failures to exit code 3 with
one-line stderr messages, and documented exit code 3 plus `impact`'s
baseline-rejection semantics in the README, per the brief. Before this
task, `scan` on a 0o500 root and `export --output` into an unwritable
parent raised raw `PermissionError` tracebacks out of `cli.main` (exit 1
via unhandled exception); now both print `Could not scan <root>: <error>`
/ `Could not write <path>: <error>` to stderr and return 3. The two brief
tests were added byte-identical (verified with `diff` against the
extracted brief block) and the chmod-based variants ship as written — no
monkeypatch fallback was needed, because both failures reproduce reliably
on this platform (Linux, non-root). TDD order followed with captured
evidence for the failing and passing runs. Final state: 54/54 CLI tests
pass; full suite `243 passed in 249.12s (0:04:09)`, no warnings
(241 pre-existing + 2 new).

## Files changed

- Modified: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/cli.py`
  (473 -> 484 lines)
  - lines 70-101 (`build`): one `try/except OSError` around the whole
    operational body of `scan` — `analyze_project` (which performs path
    collection via `resolved_root.rglob("*.qmd")` and file reads) through
    `write_build_outputs` (both `_write_atomic_text` artifacts). Handler
    prints `Could not scan {root}: {error}` to stderr and returns 3. The
    config-error (exit 2) and invalid-snapshot (exit 1) paths are outside
    the OSError guard's reach: `load_config` failures are `ValueError`
    (caught before the try), validation reports findings instead of
    raising, and the `return 1` early-exit inside the try propagates
    normally.
  - lines 472-479 (`main`, `export` dispatch): `write_v1_graph` wrapped in
    `try/except OSError` printing `Could not write {output}: {error}` to
    stderr and returning 3, where `output = root / args.output` so the
    message names the exact artifact path. No other line touched.
- Modified: `/home/lsbjordao/Repos/quarto-needs/README.md`
  - lines 382-383: the exit-code list in `### Profiles and exit codes`
    gains code 3 after the existing code-2 sentence (line 380),
    byte-identical to the brief's markdown block (brief lines 104-105,
    proven with `diff`):
    `- `3`: operational failure — an artifact could not be read or written. ...`
  - lines 429-437: the impact paragraph in `### Baseline, diff, and
    impact` gains the brief's rejection sentence appended verbatim
    (whitespace-normalized comparison proven equal; the sentence is
    re-wrapped to the paragraph's width but word-for-word identical).
- Modified: `/home/lsbjordao/Repos/quarto-needs/tests/test_cli.py`
  (820 -> 858 lines; the two tests at lines 823 and 844 are byte-identical
  to the brief's Step 1 block, brief lines 41-76, proven with `diff`)
- No other file touched.

## TDD evidence

### Verbatim transcription checks (run against the brief)

```
$ diff <(sed -n '41,76p' briefs/task-1-brief.md) <(tail -n 36 tests/test_cli.py)
TESTS-BYTE-IDENTICAL
$ diff <(sed -n '104,105p' briefs/task-1-brief.md) <(sed -n '382,383p' README.md)
BULLET-BYTE-IDENTICAL
```

(No diff output means byte-identical. The impact sentence was verified
programmatically: extracted from the brief and from the README, both
whitespace-normalized, asserted equal — `IMPACT-SENTENCE-VERBATIM`.)

### Pre-implementation probes (failure mode confirmation)

Before writing anything, both scenarios were reproduced against the
unmodified CLI; each raises a raw `PermissionError` traceback out of
`cli.main`:

```
File ".../src/quarto_needs/cli.py", line 411, in main
    return build(root)
File ".../src/quarto_needs/cli.py", line 90, in build
    write_build_outputs(
File ".../src/quarto_needs/export.py", line 297, in write_build_outputs
    _write_atomic_text(graph_path, graph)
File ".../src/quarto_needs/export.py", line 252, in _write_atomic_text
    path.parent.mkdir(parents=True, exist_ok=True)
PermissionError: [Errno 13] Permission denied: '/tmp/qn-task1-probe/locked/.quarto-needs'
```

(same shape for `export`: `PermissionError: [Errno 13] Permission denied:
'/tmp/qn-task1-probe2/locked/sub'` from `main` line 467 ->
`write_v1_graph` -> `_write_atomic_text` -> `mkdir`.)

Note for the record: with mode 0o500 (r-x) on Linux, directory listing
succeeds, so `scan`'s failure surfaces in `write_build_outputs`'s
`mkdir` of `.quarto-needs`, not in `rglob` path collection. The
implemented guard covers both (path collection/reads and both artifact
writes) with the single `build()` handler, which is what makes the
chmod-based scan test pass as written.

### Step 2 — tests fail before implementation

```
$ .venv/bin/python -m pytest tests/test_cli.py -q -k operational_failure
...
E           PermissionError: [Errno 13] Permission denied: '/tmp/pytest-of-lsbjordao/pytest-398/test_export_to_an_unwritable_d0/locked/sub'
...
FAILED tests/test_cli.py::test_scan_on_an_unwritable_root_is_operational_failure
FAILED tests/test_cli.py::test_export_to_an_unwritable_directory_is_operational_failure
2 failed, 52 deselected in 0.24s
```

Exactly the brief's prediction: FAIL — the commands raise `PermissionError`
(test error), not exit 3.

### Step 5 — CLI tests pass after implementation

```
$ .venv/bin/python -m pytest tests/test_cli.py -q
......................................................                     [100%]
54 passed in 0.49s
```

54 = 52 pre-existing + 2 new operational-failure tests.

### Step 5 — full suite

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 29%]
........................................................................ [ 59%]
........................................................................ [ 88%]
...........................                                             [100%]
243 passed in 249.12s (0:04:09)
```

243 = 241 pre-existing + 2 new. No warnings summary was emitted (pytest
shows one in `-q` mode when warnings exist).

### Manual smoke (temp dir, real stderr)

```
$ quarto-needs --root <tmp>/locked scan
Could not scan /tmp/qn-task1-smoke/locked: [Errno 13] Permission denied: '/tmp/qn-task1-smoke/locked/.quarto-needs'
scan rc: 3

$ quarto-needs --root <tmp> export --output <tmp>/locked/sub/needs.json
Could not write /tmp/qn-task1-smoke/locked/sub/needs.json: [Errno 13] Permission denied: '/tmp/qn-task1-smoke/locked/sub'
export rc: 3
```

One-line messages, no traceback; the export message names the exact
destination artifact path (the load-bearing assertion of the export test).

### Step 6 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... else echo "Checkpoint 1 verified; workspace has no Git metadata."; fi
Checkpoint 1 verified; workspace has no Git metadata.
```

No `git init` was run.

## Self-review

- The two tests and the README bullet are byte-identical to the brief
  (`diff` proofs above); the impact sentence is verbatim modulo line
  wrapping (proven equal whitespace-normalized). The chmod-based variants
  ship as written; the monkeypatch fallback in the brief's note was not
  needed (recorded per the brief's instruction).
- Exit-code contract preserved and extended exactly: 0 gates passed, 1
  validation/policy, 2 usage/configuration (`ConfigurationFailure`-style
  `ValueError` paths untouched — `load_config` handling and the
  `args.command == "scan"` early return precede the new guard), 3
  operational I/O. `except OSError` cannot intercept validation paths
  because those report findings rather than raising.
- Scan's guard covers the full operational body (path collection, `.qmd`
  reads, both artifact writes) with one handler, so a mid-write failure
  after `needs.json` succeeded leaves the first artifact in place — which
  is precisely what the new README bullet states.
- `build(root, quiet=True)` semantics preserved: the four existing
  `cli.build(..., quiet=True)` tests pass unchanged; the exit-3 message
  prints unconditionally because the operational-failure message is part
  of the stable exit-code contract, unlike quiet-suppressed diagnostics.
- Export's guard names `output = root / args.output` computed once; for an
  absolute `--output` (as in the test) `str(output)` equals the requested
  destination, so the stderr assertion holds.
- Global constraints: no new dependency; only `src/quarto_needs/cli.py`,
  `README.md`, and `tests/test_cli.py` touched; every existing signature
  and command preserved (`build`'s signature is unchanged); no Git
  metadata created; the preview server on 127.0.0.1:8777 was never
  contacted; schema v1 JSON and `extensions.quartoNeeds` projection
  untouched (export's happy path is byte-for-byte the previous
  `write_v1_graph` call).
- Consistency note: the pre-existing `_quality` and `_baseline_create`
  handlers already returned 3 on OSError with "Could not write ..." style
  messages; this task brings `scan` and `export` in line with that
  established pattern.

## Concerns

- None blocking. One observation: the brief's Step 3 wording says to wrap
  "the `scan` path collection", but on this platform the 0o500 failure
  actually surfaces in the artifact write (`mkdir` of `.quarto-needs`), so
  the guard necessarily spans analysis-through-write inside `build()`.
  This is a superset of the brief's wording, required to make the brief's
  own scan test pass, and it matches the brief's interface contract
  ("`OSError` during artifact writes to exit 3") and the global
  constraint that operational failures return 3.
- Later tasks adding exporter formats (CSV, ReqIF, etc.) will need to
  route their writes through the same exit-3 mapping; only the
  `export --output` (v1 JSON) path exists today, and it is covered.
