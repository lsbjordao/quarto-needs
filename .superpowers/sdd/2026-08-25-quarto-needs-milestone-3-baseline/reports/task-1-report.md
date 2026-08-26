# Task 1 Report: Clear the inherited Milestone 1 debts

## Summary

Implemented all 10 steps of the brief: migrated the v1 contract test's schema
validator off the deprecated `jsonschema.RefResolver` onto `referencing`,
added a characterization test pinning that `authored_name` never leaks into
v1 output, and added the two deferred CLI probes (single-analysis-per-command
under invalid input, and cycle-safe case-insensitive trace traversal). The
full suite is green at 181 passed with zero warnings (up from the prior
175 passed / 2 permitted warnings baseline — the delta is exactly the 6 new
tests added by this task: 4 parametrized `test_invalid_input_still_runs_exactly_one_analysis`
cases + 1 `test_trace_orders_ids_case_insensitively_and_survives_cycles` +
1 `test_engineering_object_to_dict_omits_authored_name`).

No production code in `src/quarto_needs/` needed to change. The cycle-safety
concern flagged as a possible real defect in the brief turned out to already
be handled correctly: `cli._reachable` (src/quarto_needs/cli.py:36-57) is a
BFS with a `seen: set[str]` that gates `queue.append`, so it already
terminates on cycles. This was verified empirically (the cycle test runs in
well under a second, no hang) rather than assumed from reading the code.

## Files changed

- `pyproject.toml` — added `"referencing"` to the `test` optional-dependency
  list only (not a runtime dependency).
- `tests/test_v1_contract.py` — replaced the `RefResolver`-based
  `envelope_validator()` with a `referencing.Registry`/`Resource`-based one.
- `tests/test_relations.py` — added
  `test_engineering_object_to_dict_omits_authored_name`.
- `tests/test_cli.py` — added `test_invalid_input_still_runs_exactly_one_analysis`
  (parametrized over `check`, `coverage`, `export`, `trace DUP-1`) and
  `test_trace_orders_ids_case_insensitively_and_survives_cycles`.

No changes to `src/quarto_needs/*`.

## Step-by-step with commands and output

**Step 1 — pyproject.toml**

Added `"referencing"` under `[project.optional-dependencies] test`, alongside
`pytest>=8` and `jsonschema>=4.23`. Not added to runtime dependencies (there
is no runtime `[project.dependencies]` for this package to begin with).

**Step 2 — baseline deprecation count (TDD anchor before migration)**

```
$ .venv/bin/python -m pytest tests/test_v1_contract.py -q
....                                                                     [100%]
=============================== warnings summary ===============================
tests/test_v1_contract.py:6
tests/test_v1_contract.py:6
  .../tests/test_v1_contract.py:6: DeprecationWarning: jsonschema.RefResolver is deprecated ...
4 passed, 2 warnings in 0.24s
```
Confirmed exactly 2 `RefResolver` deprecation warnings, matching the brief's
"Expected" and the Milestone 1 ledger's carried-forward count.

**Step 3 — rewrite `envelope_validator`**

Replaced the `RefResolver` import/helper with the `Registry`/`Resource`
version. One deviation from the brief's literal snippet was required: the
snippet's `default_specification=Draft202012Validator.META_SCHEMA` fails at
runtime because `META_SCHEMA` is a plain `dict`, not a `referencing`
`Specification` object — `Resource.from_contents` calls
`default_specification.detect(contents)`, and `dict` has no `.detect`. This
reproduced immediately as `AttributeError: 'dict' object has no attribute
'detect'` when running Step 4 with the snippet verbatim. Fixed by importing
`referencing.jsonschema.DRAFT202012` (the correct `Specification` instance
for Draft 2020-12) and passing that instead. This is the same category of
"snippet vs. real API" adaptation the brief pre-authorized for the
`Relation` constructor — I adapted the construction to match the installed
`referencing` API, not the goal (a working non-deprecated validator).

The `Relation` constructor snippet in Step 5, by contrast, needed no
adaptation: `src/quarto_needs/model.py` defines
`Relation(type, source, target, attributes, authored_name=None)`, and the
brief's `Relation("derives-from", "REQ-1", "STK-1", {})` already matches that
positional order.

**Step 4 — verify migration under `-W error::DeprecationWarning`**

First attempt (with the literal brief snippet) failed:
```
$ .venv/bin/python -m pytest tests/test_v1_contract.py -q -W error::DeprecationWarning
...
E       AttributeError: 'dict' object has no attribute 'detect'
2 failed, 2 passed in 0.17s
```
After the `DRAFT202012` fix:
```
$ .venv/bin/python -m pytest tests/test_v1_contract.py -q -W error::DeprecationWarning
....                                                                     [100%]
4 passed in 0.26s
```
Promoting the warning to an error and getting a clean pass proves the
migration rather than merely hiding the warning behind a filter.

**Step 5/6 — `authored_name` boundary test**

Added the test verbatim (constructor order already matched, per above).

```
$ .venv/bin/python -m pytest tests/test_relations.py::test_engineering_object_to_dict_omits_authored_name -v
tests/test_relations.py::test_engineering_object_to_dict_omits_authored_name PASSED [100%]
1 passed in 0.03s
```
Confirmed as a characterization test: `EngineeringObject.to_dict()`
(src/quarto_needs/model.py) already routes relations through
`relation_to_v1_dict()`, which builds an explicit dict of `type`, `source`,
`target`, `attributes` only — `authored_name` was never included. No
production code changed for this step.

**Step 7/8 — deferred CLI probes**

Added both tests verbatim to `tests/test_cli.py`; both already had their
prerequisites (`pytest`, `Path`, `cli`, `write_duplicate_project`) in scope.

```
$ timeout 30 .venv/bin/python -m pytest tests/test_cli.py -q -k "invalid_input_still_runs or survives_cycles"
.....                                                                    [100%]
5 passed, 32 deselected in 0.16s
```
Run under an explicit 30s `timeout` specifically to catch a hang if the
cycle-safety concern were real. It was not: `cli._reachable` already
maintains a `seen` set that is checked before enqueueing a candidate id, so
BFS terminates correctly on the REQ-A/req-b mutual-reference cycle. No fix
was needed in `src/quarto_needs/cli.py`.

**Step 9 — full suite**

```
$ .venv/bin/python -m pytest -q
........................................................................ [ 39%]
........................................................................ [ 79%]
.....................................                                    [100%]
181 passed in 215.42s (0:03:35)
```
181 = 175 (Milestone 1/2 baseline) + 6 new tests from this task. No warnings
section at all — zero warnings, as required. The run took ~3.5 minutes
because several existing tests invoke real Quarto/Deno renders
(e.g. `test_dashboard_renders_precomp...`, `test_named_query_filters_inter...`);
this is pre-existing test behavior, not something introduced by this task.

**Step 10 — conditional checkpoint**

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git add pyproject.toml tests/test_v1_contract.py tests/test_relations.py tests/test_cli.py
    git commit -m "chore: clear milestone one test debts"
  else
    echo "Checkpoint 1 verified; workspace has no Git metadata."
  fi
Checkpoint 1 verified; workspace has no Git metadata.
```
Confirmed: this workspace has no `.git` directory (verified separately with
`git status` style commands failing outside a repo), so the else-branch
printed as expected. No Git repository was initialized, per the instruction
never to run `git init`.

## Self-review

- **Completeness**: all 10 steps executed in order; TDD ordering respected
  (Step 2 recorded the pre-migration warning count before Step 3 changed
  code; Step 6/8 ran the new tests immediately after adding them).
- **Global Constraints check**:
  - No runtime dependency added — `referencing` is in the `test` extra only.
  - "One analysis per command" — untouched; the new
    `test_invalid_input_still_runs_exactly_one_analysis` test actually
    exercises and confirms this guarantee under invalid input, which the
    Milestone 1 ledger had left unverified.
  - All the "preserve every existing signature" items were not touched;
    only test files and `pyproject.toml` changed.
  - Schema v1 bytes unaffected — no schema files were modified, and
    `envelope_validator` is a test helper, not part of `export`.
  - No Git metadata created.
  - Did not touch the preview server on port 8777 (irrelevant to this task;
    left it running as observed via `ps aux` incidentally during the slow
    full-suite run).
  - No Quarto shortcode / `extensions.quartoNeeds` projections added.
- **Naming**: kept the brief's exact test names (`envelope_validator`,
  `test_engineering_object_to_dict_omits_authored_name`,
  `test_invalid_input_still_runs_exactly_one_analysis`,
  `test_trace_orders_ids_case_insensitively_and_survives_cycles`) since the
  brief's Interfaces section says `envelope_validator` is reused by Tasks 4,
  8, and 10 — renaming it would break that contract.
- **YAGNI**: no extra helpers, no speculative generalization. The one
  deviation from the literal brief text (`DRAFT202012` instead of
  `Draft202012Validator.META_SCHEMA`) is the minimum fix to make the
  specified interface (`envelope_validator() -> Draft202012Validator` built
  on `referencing`) actually work, verified by running it.
- **Do the tests verify real behavior?** Yes for all four new/pinned tests:
  - `test_engineering_object_to_dict_omits_authored_name` exercises the real
    `EngineeringObject.to_dict()` / `Relation` dataclasses, not a mock.
  - `test_invalid_input_still_runs_exactly_one_analysis` wraps the *real*
    `cli.analyze_project` (calls through to it via `real_analyze`) and only
    counts invocations — it would fail if the CLI re-analyzed on any of the
    four invalid-input command paths.
  - `test_trace_orders_ids_case_insensitively_and_survives_cycles` runs the
    actual CLI entrypoint (`cli.main`) against a real two-file mutual-cycle
    project and asserts on real stdout capture, with an external `timeout`
    wrapper as a safety net during my own verification (the test itself has
    no internal timeout, matching the brief).
  - `envelope_validator`'s migration is proven by the `-W
    error::DeprecationWarning` run turning would-be warnings into failures
    that did not occur.

## Concerns

None outstanding. One noteworthy finding, not a concern: the brief's Step 3
code snippet has a small bug (`default_specification=Draft202012Validator.META_SCHEMA`
does not satisfy `referencing`'s `Resource.from_contents` API — it needs a
`Specification` object, not the raw meta-schema dict). I fixed it by using
`referencing.jsonschema.DRAFT202012` instead, verified by both Step 4 runs
(the failing one with the literal snippet, and the passing one after the
fix). This is documented above and in the diff; flagging it explicitly in
case other tasks copy this snippet pattern elsewhere.

No other, unexpected warnings appeared anywhere in the full suite run (Step
9) that would need to be reported per the ambiguity-resolution guidance —
the full 181-test run had zero warnings of any kind.

---

# Fix report: reviewer finding on `test_trace_orders_ids_case_insensitively_and_survives_cycles`

## Finding addressed

Code review flagged (Important, plan-mandated) that the original cycle test
— the brief's Step 7 snippet, copied verbatim — did not actually exercise
cycle-safety or case-insensitive ordering:

- Its 2-node mutual cycle (`req-b` <-> `REQ-A`) only ever revisits `start`,
  which the separate `candidate != start` filter already excludes
  independent of the `seen` set. Removing `seen` would not hang on this
  fixture.
- Both `_reachable` calls returned single-element sets, so
  `sorted(seen, key=lambda item: (item.casefold(), item))` was never
  exercised on more than one element.

The coordinator ruled the finding correct (defect in the plan text, not in
my execution) and directed a fix with two requirements: (1) a subcycle among
non-start nodes so the `seen` set is load-bearing, and (2) a reachable set
with >=2 differently-cased ids whose plain-sort and casefold-sort orders
disagree, with the assertion pinning the case-insensitive order.

## What changed

`tests/test_cli.py` — replaced the body of
`test_trace_orders_ids_case_insensitively_and_survives_cycles` (previously
lines 570-588) with a new fixture:

```
REQ-A (start) --references--> sub-b --references--> SUB-C
                                 ^-------references-------/
```

- `REQ-A` "references: sub-b" (edge REQ-A -> sub-b)
- `sub-b` "references: SUB-C" (edge sub-b -> SUB-C)
- `SUB-C` "references: sub-b" (edge SUB-C -> sub-b, closing a subcycle
  between `sub-b` and `SUB-C` that does **not** touch the start node)

This satisfies requirement 1: the only cycle in the graph is among
non-start nodes, so the `seen` set is the only thing that can stop
`_reachable`'s BFS from looping between `sub-b` and `SUB-C` forever.

The two reachable ids are cased so plain `sorted()` disagrees with the
casefold-keyed sort actually used by `cli._reachable`
(src/quarto_needs/cli.py:57): ASCII-order `sorted(["SUB-C", "sub-b"])` puts
`"SUB-C"` first (uppercase sorts before lowercase in ASCII), while
`sorted(..., key=lambda item: (item.casefold(), item))` puts `"sub-b"`
first (`"sub-b"` < `"sub-c"` alphabetically). This satisfies requirement 2.

Before writing the assertion I read the real CLI output by running the
fixture directly (not guessed):

```
$ .venv/bin/python -c "... cli.main(['--root', tmp, 'trace', 'REQ-A']) ..."
Upstream:
Downstream:
  sub-b
  SUB-C
RC= 0
```

The new test asserts on this exact captured stdout:

```python
assert output == (
    "Upstream:\n"
    "Downstream:\n"
    "  sub-b\n"
    "  SUB-C\n"
)
```

`Upstream:` has no entries because nothing in the fixture references
`REQ-A`; that's expected given the graph shape, not a gap — the point of
this test is downstream traversal through the non-start subcycle.

An earlier draft appended a redundant static assertion
(`assert sorted(["SUB-C", "sub-b"]) != ["sub-b", "SUB-C"]`) to spell out the
ordering disagreement; removed it during self-review since it is a
compile-time truth unrelated to runtime behavior and the exact-output
assertion above already pins the case-insensitive order — keeping it would
have been clutter, not coverage.

## Verifying requirement 1 (the removed-`seen` experiment)

Per the coordinator's instruction, I reproduced the reviewer's check
directly rather than arguing it: temporarily edited
`src/quarto_needs/cli.py:54` from

```python
if candidate not in seen and candidate != start:
```

to

```python
if candidate != start:
```

(keeping `seen.add(candidate)` so the return-value sort still works, but no
longer gating re-enqueueing on it — the exact "seen-membership check
hypothetically removed" the reviewer described), then ran the new test
under a hard timeout:

```
$ timeout 10 .venv/bin/python -m pytest tests/test_cli.py -q -k "survives_cycles"
Terminado
EXIT CODE: 143
```

Exit code 143 (128+SIGTERM) confirms `timeout` had to kill the test process
after 10s — the regression makes the test hang, exactly as required. This
is direct evidence the fixture's `sub-b`<->`SUB-C` subcycle is load-bearing:
without the `seen` gate, `_reachable` bounces between the two nodes forever.

I then restored the original file from a pre-edit copy and diffed to
confirm byte-for-byte restoration:

```
$ diff /tmp/cli.py.orig src/quarto_needs/cli.py && echo "RESTORED - identical"
RESTORED - identical
```

## Covering tests re-run (as instructed, not the full suite)

```
$ .venv/bin/python -m pytest tests/test_cli.py -q -k "survives_cycles or invalid_input_still_runs"
.....                                                                    [100%]
5 passed, 32 deselected in 0.08s
```

5 passed: the 4 parametrized `test_invalid_input_still_runs_exactly_one_analysis`
cases plus the rewritten `test_trace_orders_ids_case_insensitively_and_survives_cycles`.

## Files changed in this fix

- `tests/test_cli.py` — rewrote the fixture and assertions for
  `test_trace_orders_ids_case_insensitively_and_survives_cycles` only.
  No other test in the file was touched.
- `src/quarto_needs/cli.py` — touched only transiently during the
  removed-`seen` experiment; restored to its original content
  (verified with `diff`) before finishing. No net change shipped here.

## Self-review of the fix

- Requirement 1 verified experimentally (hang + `timeout` kill), not just
  asserted by hand-tracing — matches the coordinator's explicit ask for
  evidence.
- Requirement 2 satisfied by construction and pinned by an exact-output
  string assertion, so a regression that drops the `casefold` key (e.g.
  `sorted(seen)` instead of `sorted(seen, key=...)`) would flip the
  asserted order and fail the test.
- Assertion is against real, observed CLI output (captured via a manual run
  before writing the test), not a guess at the format.
- No other files or tests were modified; the two originally-covering tests
  for Step 8 remain otherwise unchanged.

## Concerns

None. The fix is verified both structurally (fixture graph shape) and
empirically (the regression experiment). No new warnings or side effects
were introduced; `src/quarto_needs/cli.py` ends this fix byte-identical to
its state at the end of the original Task 1 submission.
