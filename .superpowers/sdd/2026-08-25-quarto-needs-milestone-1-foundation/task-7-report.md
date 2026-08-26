# Task 7 implementation report

## Scope and outcome

Implemented Task 7 only: every CLI command now uses exactly one canonical
`analyze_project` result, structurally invalid projects cannot replace generated
artifacts, and trace traversal uses the immutable snapshot indexes.

The pre-render helper already had the required synchronization followed by one
`build` call. Its production code was therefore left unchanged and that behavior
was locked with a new test.

No runtime dependency was added. No preview process was stopped, restarted, or
signaled.

## Strict TDD evidence

All Task 7 CLI and pre-render tests were added before modifying
`src/quarto_needs/cli.py`.

### RED: focused CLI and synchronization suite

Command:

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_extension_sync.py -q
```

Observed result before production changes:

```text
10 failed, 11 passed in 0.16s
```

The failures demonstrated the intended gaps:

- `cli.analyze_project` did not exist, so the five command single-pass tests
  failed;
- invalid `scan` and quiet `build` raised from the compatibility exporter;
- invalid `coverage` incorrectly returned 0 and printed metrics;
- invalid `trace` raised `DuplicateIdError`;
- invalid `export` raised `ValueError`.

Two final binding tests were then added before implementation and run directly:

```bash
.venv/bin/python -m pytest \
  tests/test_cli.py::test_scan_delegates_to_build_without_preanalysis \
  tests/test_cli.py::test_export_does_not_run_legacy_object_reanalysis -q
```

Observed result:

```text
2 failed in 0.05s
```

The scan test failed because the canonical analyzer entry point was absent, and
the export test failed because the old compatibility wrapper invoked
`analyze_objects` a second time.

### GREEN: focused Task 7 suite

Command:

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_extension_sync.py -q
```

Result:

```text
23 passed in 0.11s
```

### GREEN: required core regressions

Command:

```bash
.venv/bin/python -m pytest \
  tests/test_cli.py tests/test_extension_sync.py \
  tests/test_export.py tests/test_analysis.py -q
```

Result:

```text
46 passed in 0.15s
```

### GREEN: full suite

Command:

```bash
.venv/bin/python -m pytest -q
```

Fresh result:

```text
74 passed, 2 warnings in 45.40s
```

The two warnings are the pre-existing `jsonschema.RefResolver` deprecation
warnings in `tests/test_v1_contract.py`.

### Syntax verification

Command:

```bash
.venv/bin/python -m py_compile \
  src/quarto_needs/cli.py tools/quarto_needs_pre_render.py \
  tests/test_cli.py tests/test_extension_sync.py
```

Result: exit code 0 with no output.

## Files changed

- `src/quarto_needs/cli.py`
- `tests/test_cli.py` (new)
- `tests/test_extension_sync.py`
- `.superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/task-7-report.md`

`tools/quarto_needs_pre_render.py` was inspected and tested but not modified,
because it already synchronizes the extension and then calls `build` exactly
once.

## Implementation and compatibility evidence

- `build(root, quiet=False)` retains its signature and performs one
  `analyze_project(root)` call.
- `main(scan)` returns `build(root)` before any analysis in `main`.
- `check`, `coverage`, `trace`, and `export` each consume one shared
  `AnalysisResult` produced by their invocation.
- A valid build writes `needs.json` and `generated-index.lua` together through
  `write_build_outputs`.
- An invalid build returns 1 before either writer is called. Tests preserve
  sentinel content in both destinations, including the quiet path.
- Non-quiet invalid build/scan prints deterministic findings to stderr. Quiet
  invalid build emits no output.
- `check` prints findings and its legacy object/error/warning summary to stdout
  even when the snapshot is absent.
- Invalid `coverage`, `trace`, and `export` print findings to stderr and return 1.
- Valid coverage retains the exact six-key legacy JSON order and formatting.
- Valid scan retains its exact two-line summary.
- Trace retains `Upstream:`/`Downstream:` output, returns 2 with the legacy
  message for an unknown ID, and uses one breadth-first helper over
  `snapshot.incoming` and `snapshot.outgoing`.
- The three-node `REQ-1 -> REQ-2 -> TC-1` test proves direct and transitive IDs
  are emitted in deterministic case-insensitive lexical order.
- Export writes the requested v1 graph directly with `write_v1_graph`, does not
  invoke legacy `analyze_objects`, remains silent on success, and does not create
  the build's Lua index as a side effect.
- Pre-render test proves strict event order: `sync_extension(PROJECT_ROOT)`, then
  exactly one `build(PROJECT_ROOT, quiet=False)`, with the build status returned.

## Self-review

Reviewed the scoped implementation against every Task 7 binding and mentally
mutated each critical branch. Persisted tests catch:

- moving analysis above the scan branch;
- omitting or duplicating analysis for any legacy command;
- writing either build artifact before structural validity is known;
- suppressing invalid findings on non-quiet build or check;
- sending structural failures to the wrong stream or returning the wrong code;
- changing valid scan, check, coverage, trace, or export output/status behavior;
- treating an invalid trace ID as the legacy unknown-ID usage error;
- replacing BFS with direct-neighbor-only traversal;
- non-deterministic trace ordering;
- routing export through the legacy re-analysis wrapper;
- validating/parsing separately in the pre-render helper or changing its
  sync-before-build order.

No changes were made to analysis, snapshot, export compatibility wrappers, the
pre-render implementation, dependencies, or unrelated files.

## Concerns and intentional boundaries

- The permitted `jsonschema.RefResolver` deprecation warnings remain unrelated
  to Task 7.
- A read-only process/socket check showed no visible listener for
  `127.0.0.1:8777` in this agent namespace both before and after the work. No
  preview process operation was performed, so any preview server outside this
  namespace was left untouched.
- The CLI continues to use the legacy `ERROR`/`WARN` display mapping; adding a
  separate informational label is outside this compatibility task.

## Git checkpoint

The workspace has no Git metadata. The conditional checkpoint check printed:

```text
Checkpoint 7 verified; workspace has no Git metadata.
```

No repository was initialized and no commit was created.
