# Task 2 Report: `export --format` plumbing and policy-failure artifact preservation

## Summary

Extended the `export` command with `--format <json|csv|sarif|junit|markdown>`
(default `json`) and `--baseline <path>` (markdown-only), routed the command
through a new `_export(root, args, config)` handler, and made the artifact
write happen BEFORE the profile exit code is computed and returned. The json
path dispatches to the existing `write_v1_graph`, so byte-identity with the
pre-task v1 projection holds by construction (and was verified empirically
against the `scan` artifact). Non-json formats temporarily raise
`NotImplementedError` at the dispatch point sanctioned by the brief's Step 3;
Tasks 3–6 replace that raise with their writers. Exactly the two brief tests
that require those writers carry `xfail(strict=True)` marks with
`# TODO(milestone-4a-writers)` notes (exact inventory below). Final state:
CLI export slice `7 passed, 2 xfailed`; full suite
`245 passed, 2 xfailed in 154.41s (0:02:34)`, no warnings
(243 pre-existing passing + 2 new passing + 2 expected-failing).

## Files changed

- Modified: `/home/lsbjordao/Repos/quarto-needs/src/quarto_needs/cli.py`
  (484 -> 515 lines)
  - lines 407-409 (`main`, export parser): the two brief argument lines,
    byte-identical to Step 3's snippet —
    `export.add_argument("--format", choices=("json", "csv", "sarif", "junit", "markdown"), default="json")`
    and
    `export.add_argument("--baseline", help="Baseline for the Markdown change summary (markdown format only)")`.
  - lines 362-394 (new `_export(root, args, config)` handler, placed after
    `_impact`): resolves the effective config with the same
    `config if config is not None else load_config(root)` pattern as
    `_query`/`_quality`; rejects `--baseline` with a non-markdown
    `--format` on stderr (message contains "markdown") and returns 2 BEFORE
    any analysis; analyzes exactly once; on a missing snapshot prints
    findings to stderr and returns 1 (preserving the established
    snapshot-consumer behavior and the sentinel-preservation guarantee);
    dispatches json to the existing `write_v1_graph(output, snapshot)` and
    the other four formats to a temporary `raise NotImplementedError` marked
    `TODO(milestone-4a-writers)`; wraps the dispatch in the same
    `except OSError` guard shape Task 1 landed (`Could not write {output}` ->
    exit 3, naming the artifact); finally computes
    `report_from_snapshot(result.snapshot, effective)` (pure — no second
    analysis) and returns
    `profile_exit_code(effective.profile, False, report.gate_failures())`.
  - line 474-475 (`main` dispatch): `export` now routes to
    `_export(root, args, config)` with the other handlers BEFORE the shared
    tail analysis (which now serves only `check`/`coverage`/`trace`); the old
    eight-line tail export block is deleted, leaving `return 2` as the
    fallthrough.
  - No import changes needed: `profile_exit_code` and
    `report_from_snapshot` were already imported from `.quality`, and
    `write_v1_graph` from `.export` (verified against the import block at
    lines 18/21, as the controller context noted).
- Modified: `/home/lsbjordao/Repos/quarto-needs/tests/test_cli.py`
  (858 -> 927 lines)
  - the four Step 1 tests appended after
    `test_export_to_an_unwritable_directory_is_operational_failure`,
    byte-identical to the brief (diff proof below), plus the two
    brief-sanctioned strict-xfail marks (inventory below).
- No other file touched (verified against the `task-2-before` snapshot; see
  Concerns for three files that changed during the session window through no
  action of this task).

## TDD evidence

### Verbatim transcription check (run against the brief)

```
$ diff <(sed -n '35,97p' briefs/task-2-brief.md) <(tail -n 63 tests/test_cli.py)
TESTS-BYTE-IDENTICAL
```

(No diff output means byte-identical; the check was run BEFORE the xfail
marks were added, so the test bodies match the brief exactly. The brief's
Step 3 parser snippet was likewise applied verbatim.)

### Step 2 — failing run (pre-implementation)

```
$ .venv/bin/python -m pytest tests/test_cli.py -q -k export
...
E                   SystemExit: 2
...
Captured stderr call:
usage: quarto-needs [-h] [--root ROOT]
                    {scan,check,coverage,trace,export,quality,query,baseline,diff,impact} ...
quarto-needs: error: unrecognized arguments: --format markdown
=========================== short test summary info ============================
FAILED tests/test_cli.py::test_export_default_format_is_byte_identical_to_the_v1_projection
FAILED tests/test_cli.py::test_export_runs_exactly_one_analysis_per_format - ...
FAILED tests/test_cli.py::test_export_rejects_baseline_for_non_markdown_formats
FAILED tests/test_cli.py::test_export_preserves_artifacts_on_policy_failure
4 failed, 5 passed, 49 deselected in 0.69s
```

Exactly the brief's predicted failure mode: `--format`/`--baseline` do not
exist (argparse exit 2 via SystemExit) and the policy-failure path is absent.

### Step 4 — after implementation, before xfail marks

```
$ .venv/bin/python -m pytest tests/test_cli.py -q -k export
...
E               NotImplementedError: --format markdown writer lands with the milestone-4a exporter tasks
...
=========================== short test summary info ============================
FAILED tests/test_cli.py::test_export_runs_exactly_one_analysis_per_format - ...
FAILED tests/test_cli.py::test_export_preserves_artifacts_on_policy_failure
2 failed, 7 passed, 49 deselected in 0.13s
```

The byte-identity and baseline-rejection tests pass; the two writer-dependent
tests fail for exactly one reason — the temporary `NotImplementedError`
dispatch. The brief's Step 4 escape hatch was then applied (strict xfail), and
re-run:

```
$ .venv/bin/python -m pytest tests/test_cli.py -q -k export
......x.x                                                               [100%]
7 passed, 49 deselected, 2 xfailed in 0.16s
```

### Behavioral probes (outside the test files, run in /tmp scratch projects)

These verify the two hard constraints the xfailed tests cannot yet exercise:

```
# Probe 1: policy failure on the json path -> artifact written BEFORE exit 1.
probe1 exit: 1 | artifact: True
# Probe 2: --baseline with non-markdown -> exit 2 BEFORE any analysis.
usage error: --baseline is only valid with --format markdown (got --format sarif)
probe2 exit: 2 | analyses: 0
```

### Byte-identity cross-check against the pre-task projection

The default and `--format json` exports were compared byte-for-byte against
the `scan`-produced `.quarto-needs/needs.json` (the unchanged pre-task v1
projection path) for a config-less project:

```
scan==export-default: True
scan==export-json   : True
sha256: 3409a7659f35845837e0c91cb6e36ba60932890a68e0bd9784ed534a01597aba
```

### Step 5 — full suite and conditional checkpoint

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 29%]
.x.x.................................................................... [ 58%]
........................................................................ [ 87%]
...............................                                          [100%]
245 passed, 2 xfailed in 154.41s (0:02:34)

$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then ... else echo "Checkpoint 2 verified; workspace has no Git metadata."; fi
Checkpoint 2 verified; workspace has no Git metadata.
```

No `git init` was run; the preview server on 127.0.0.1:8777 was never
contacted.

## Exact xfail inventory (for Tasks 3-6 to remove)

Both marks are `strict=True`, so a silently-passing mark fails the suite;
neither XPASSed (the full-suite summary shows only `2 xfailed`).

1. `/home/lsbjordao/Repos/quarto-needs/tests/test_cli.py` lines 875-876, on
   `test_export_runs_exactly_one_analysis_per_format` (line 877):

   ```
   # TODO(milestone-4a-writers): remove this xfail when Tasks 3-6 land the writers.
   @pytest.mark.xfail(strict=True, reason="csv/sarif/junit writers land in Tasks 3-6")
   ```

   Removal condition: ALL of Tasks 3-6 — the loop drives all five formats
   (json passes today; csv/sarif/junit/markdown each hit the temporary
   `NotImplementedError` in `_export`), so the mark can only come off once
   the markdown writer (Task 6) has landed too.

2. `/home/lsbjordao/Repos/quarto-needs/tests/test_cli.py` lines 909-910, on
   `test_export_preserves_artifacts_on_policy_failure` (line 911):

   ```
   # TODO(milestone-4a-writers): remove this xfail when Task 6 lands the markdown writer.
   @pytest.mark.xfail(strict=True, reason="markdown writer lands in Task 6")
   ```

   Removal condition: Task 6 (markdown writer).

The writers' integration point is the `else: raise NotImplementedError(...)`
branch in `_export` (cli.py lines 383-393), marked with the same
`TODO(milestone-4a-writers)` comment: replace the raise with the format's
writer call, routed through `_write_atomic_text` (the json branch above it is
the template). Everything else in the handler — the pre-analysis baseline
rejection, the one-analysis snapshot reuse, the OSError -> exit 3 guard, and
the write-then-`profile_exit_code` ordering — is final and must not change.

## Self-review

- The four tests, the two parser lines, and the `_export`
  signature/dispatch/exit semantics follow the brief verbatim; the only
  additions beyond the brief's literal text are the two Step-4-sanctioned
  xfail marks and their TODO notes.
- Hard constraint "one analysis per invocation": `_export` calls
  `analyze_project` exactly once; `report_from_snapshot` is pure (it
  materializes queries from the snapshot, never rescans); the
  `--baseline` rejection returns before `analyze_project` is reached (probe 2:
  0 analyses). The existing
  `test_each_command_analyzes_project_once[export]` and
  `test_invalid_input_still_runs_exactly_one_analysis[export]` still pass
  with `calls == 1`.
- Hard constraint "byte-identical json": preserved by construction (same
  `write_v1_graph(output, snapshot)` call, `extra_extensions` unset) and
  locked empirically against the `scan` artifact; the brief's golden-hash
  test (`a.json == b.json`, sha256 length 64) passes.
- Exit-code contract: 0 gates passed (default/advisory profiles), 1 policy
  failure (strict) or structural failure (snapshot None), 2 usage
  (`--baseline` misuse, before analysis; broken config still handled in
  `main`), 3 operational writes (`Could not write {output}` names the
  artifact — Task 1's guard shape reused verbatim). Policy failures write
  the artifact before `profile_exit_code` is even evaluated (probe 1).
- Existing behavior preserved: `export` stays silent on success (no stdout);
  the unwritable-directory test (exit 3, destination named in stderr), the
  sentinel-preservation test on structural failure, and the no-legacy-
  reanalysis test all pass unchanged. Every existing command, handler
  signature, and the shared `main` tail for check/coverage/trace are
  untouched apart from removing the superseded export block.
- No new dependency; only `src/quarto_needs/cli.py` and `tests/test_cli.py`
  modified by this task (verified by diff against the task-2-before
  snapshot: cli.py 47 changed lines, test_cli.py 69 changed lines, no other
  file differs that snap.sh actually tracks — see Concerns).
- `--format` choices are enforced by argparse, so an unknown format exits 2
  via SystemExit exactly like the brief's Step 2 prediction showed for
  missing flags.

## Concerns

- None blocking for this task. Three observations for the controller:
  1. Concurrent workspace drift (NOT caused by this task): `README.md`
     (mtime 15:14:32), `CONTRIBUTING.md` (15:13:55), and
     `tests/test_example_project.py` (15:11:45) changed after the
     task-2-before snapshot was taken (14:57) and around this task's edit
     window, but no tool call of this task touched them; the changes look
     like user/editor-side Milestone 3 polish (the "0.5 — Change management
     (shipped)" roadmap rewrite, the CONTRIBUTING diff-example description,
     and a SOURCE_DATE_EPOCH-pinning refactor of
     `test_aegis_baseline_round_trips_to_an_empty_diff` — same 8 tests
     before/after). The full green suite ran WITH these versions in place.
     `examples/book/diagrams_files` (15:16:52) is regenerated by the suite's
     own diagrams render test and is excluded by snap.sh, as are
     `.gitignore`, `.luarc.json`, `.github/`, and `LICENSE` (the snapshot is
     intentionally partial).
  2. Exit-code semantics note for later tasks: `export --format json` under
     a strict profile with failing gates now returns 1 (artifact still
     written) where it previously returned 0. This is the brief's specified
     behavior ("Export artifacts are still written when policy returns exit
     1"), and no pre-existing test asserted the old behavior — but CI tasks
     and docs (Task 7) should be aware `export` is no longer always-0.
  3. The temporary `NotImplementedError` propagates out of `cli.main` for
     csv/sarif/junit/markdown (a traceback, not a clean exit code). The
     brief sanctions this within this task's branch and Tasks 3-6 remove it;
     nothing between now and then should ship that state.
