# Task 11 Report: Showcase, documentation, and milestone acceptance

## Summary

Implemented Task 11 in full, in brief step order: added the three showcase
tests to `tests/test_example_project.py`, confirmed they fail for the
expected reason (missing baseline file), added the three Make targets to
`Makefile`, created the checked-in Aegis baseline at
`examples/book/baselines/quarto-needs.json`, confirmed the showcase tests
pass, wrote the README/ARCHITECTURE/CONTRIBUTING documentation the brief
requires, and ran the full Step 9 acceptance command set. Both critical
gates — `make diff-example` and `make impact-example` against the
freshly-created baseline — came back clean on the first try (`No changes.`
/ `No changes to propagate.`, both exit 0), so there was no fingerprint bug
to chase and nothing to escalate as BLOCKED. The final full suite is
**241 passed, zero warnings** (238 pre-existing + 3 new). Step 10's
checkpoint is conditional and this workspace has no `.git`, so it printed
the "no Git metadata" line and created no commit, exactly as required.

## Files changed

- Modified: `/home/lsbjordao/Repos/quarto-needs/tests/test_example_project.py`
  (233 -> 277 lines) — inserted the three brief tests
  (`test_aegis_baseline_round_trips_to_an_empty_diff`,
  `test_aegis_baseline_validates_against_the_baseline_schema`,
  `test_aegis_impact_explains_a_removed_verification`) verbatim between
  `test_aegis_named_queries_resolve` and
  `test_aegis_quality_report_projects_passing_gates`.
- Modified: `/home/lsbjordao/Repos/quarto-needs/Makefile` (39 -> 50 lines) —
  added `baseline-example diff-example impact-example` to `.PHONY` and
  appended the three targets verbatim from the brief.
- Created: `/home/lsbjordao/Repos/quarto-needs/examples/book/baselines/quarto-needs.json`
  — the checked-in Aegis baseline. `schemaVersion: "1"`, `valid: true`,
  `referenceDate: "2026-08-26"`, 85 objects, 106 relations, 0 findings.
- Modified: `/home/lsbjordao/Repos/quarto-needs/README.md` (479 -> 539
  lines) — extended the `## Commands` fenced block with `baseline create`,
  `diff`, and `impact` entries, and added a new `### Baseline, diff, and
  impact` subsection immediately after `### Profiles and exit codes` (i.e.
  still inside the Configuration section, immediately before `## Commands`)
  covering all eight required points: what `baseline create` writes and its
  two refusal conditions; what `--allow-invalid` produces and why `diff`
  and `impact` reject it; what `diff` classifies and why a changed ID is a
  removal-plus-addition; the relocation-keyed-on-file rule and why (one
  edited paragraph would otherwise relocate every object below it); the
  alias-flip-is-representation-not-add/remove rule and why (the semantic
  fingerprint sorts endpoints by role, not by which side authored the
  attribute); the two guards (`configuration-changed` /
  `reference-date-changed`) and what `--recompute-with current` does and
  does not restore; and the determinism/`SOURCE_DATE_EPOCH` statement.
- Modified: `/home/lsbjordao/Repos/quarto-needs/ARCHITECTURE.md` (84 -> 99
  lines) — extended the "Canonical pipeline" fenced block with the exact
  four-line addition from the brief's Step 7
  (`AnalysisSnapshot -> fingerprints -> baselines/quarto-needs.json` / the
  `diff`/`impact` branch), and added a paragraph stating that `diff` and
  `impact` are pure functions over two snapshots, that the CLI is the only
  layer touching the filesystem, and that the configuration fingerprint and
  reference date are the two guards deciding which delta categories are
  meaningful.
- Modified: `/home/lsbjordao/Repos/quarto-needs/CONTRIBUTING.md` (83 -> 93
  lines) — added one bullet to the Fixture policy list documenting
  `examples/book/baselines/quarto-needs.json`: regenerate only via
  `make baseline-example` on an approved deliberate change, inspect
  `make diff-example` before committing, never regenerate to silence a
  failing test.

No other file was touched. `pyproject.toml`'s `referencing` test-extra entry
(Global Constraint) was already in place from an earlier task and required
no change.

## TDD evidence

### Step 2 — failing run before the baseline existed

```
$ .venv/bin/python -m pytest tests/test_example_project.py -q -k baseline
FF                                                                       [100%]
=================================== FAILURES ===================================
_______________ test_aegis_baseline_round_trips_to_an_empty_diff _______________
    ...
>       assert baseline_path.is_file(), "run `make baseline-example` to create it"
E       AssertionError: run `make baseline-example` to create it
E       assert False
E        +  where False = is_file()
E        +    where is_file = PosixPath('/home/lsbjordao/Repos/quarto-needs/examples/book/baselines/quarto-needs.json').is_file
__________ test_aegis_baseline_validates_against_the_baseline_schema ___________
    ...
E       FileNotFoundError: [Errno 2] No such file or directory: '/home/lsbjordao/Repos/quarto-needs/examples/book/baselines/quarto-needs.json'
=========================== short test summary info ============================
FAILED tests/test_example_project.py::test_aegis_baseline_round_trips_to_an_empty_diff
FAILED tests/test_example_project.py::test_aegis_baseline_validates_against_the_baseline_schema
2 failed, 6 deselected in 0.21s
```

(`-k baseline` does not match `test_aegis_impact_explains_a_removed_verification`
by name — expected, matches the brief's Step 2 instruction exactly.)

### Step 4 — baseline creation and the critical gate

```
$ make sync-example
Quarto-Needs: 85 objects, 0 findings
Requirements: 33 | implemented: 78.8% | verified: 78.8%

$ make baseline-example
Wrote valid baseline to /home/lsbjordao/Repos/quarto-needs/examples/book/baselines/quarto-needs.json

$ make diff-example
No changes.
```

Exit code 0 for all three. The diff came back clean on the very first
comparison against the just-created baseline — no fingerprint leak was
found, so there was nothing to fix in Task 3 and no BLOCKED escalation was
needed. `make impact-example` (checked at the same time, ahead of Step 9)
also came back clean:

```
$ make impact-example
No changes to propagate.
```

### Step 5 — showcase tests passing after the baseline exists

```
$ .venv/bin/python -m pytest tests/test_example_project.py -q
........                                                                 [100%]
8 passed in 22.53s
```

All 8 tests in the file pass, including the 3 new ones.

## Step 9 — full acceptance run, command by command

### 1. `make setup && make test`

`make setup` re-installed the editable package (`Successfully installed
quarto-needs-0.1.0`), confirming `pytest>=8`, `jsonschema>=4.23`, and
`referencing` are already satisfied test-extra dependencies (no runtime
dependency added). `make test` (full suite, run before the render/baseline
steps below re-touched examples/book) passed:

```
241 passed in 221.11s (0:03:41)
```

### 2. `make sync-example && make sync-example` — SHA-256 pairs

Run 1:

```
3f03e14518c8bb821581571275b8c9d02618c84fd5f841cdb75ff12c243dbd05  examples/book/.quarto-needs/needs.json
d3192c7fe13640e171d4f9f2f1885b3ec38b03303c211cad3f10b974005a0d64  examples/book/_extensions/quarto-needs/generated-index.lua
```

Run 2 (immediately after):

```
3f03e14518c8bb821581571275b8c9d02618c84fd5f841cdb75ff12c243dbd05  examples/book/.quarto-needs/needs.json
d3192c7fe13640e171d4f9f2f1885b3ec38b03303c211cad3f10b974005a0d64  examples/book/_extensions/quarto-needs/generated-index.lua
```

Byte-identical, as required.

### 3. `make check-example`

```
Checked 85 objects: 0 errors, 0 warnings
```

Exit code 0.

### 4. `quality --format json`

Exit code 0. Excerpt of the JSON payload (all gates `"passed": true`,
0 findings of any severity):

```json
{
  "configurationPresent": true,
  "findings": {"byCode": {}, "counts": {"error": 0, "info": 0, "total": 0, "warning": 0}},
  "gates": [
    {"actual": 0, "denominator": null, "name": "max-errors", "passed": true, "scope": "project", "threshold": 0},
    {"actual": 100.0, "denominator": 26, "name": "min-implementation-trace", "passed": true, "scope": "approved-requirements", "threshold": 100.0},
    {"actual": 100.0, "denominator": 26, "name": "min-implementation-effective", "passed": true, "scope": "approved-requirements", "threshold": 100.0},
    ...
  ]
}
```

### 5. `query approved-high-unverified`

Exit code 0, empty stdout — the named query is empty in the published book,
matching `tests/test_example_project.py::test_aegis_quality_report_projects_passing_gates`
and the existing `test_aegis_book_renders_generated_views` assertion that
both named queries render as `No needs match this query.` in the book.

### 6. `make baseline-example && make diff-example && make impact-example`

```
Wrote valid baseline to /home/lsbjordao/Repos/quarto-needs/examples/book/baselines/quarto-needs.json
No changes.
No changes to propagate.
```

Combined exit code 0.

### 7. `make render-example-all`

All three formats exited 0:

```
quarto render examples/book --to html
...
Output created: _book/index.html

quarto render examples/book --to docx
...
Output created: _book/Aegis-IAM-—-requisitos-rastreáveis.docx

quarto render examples/book --to pdf
...
running lualatex - 1 / 2 / 3
Output created: _book/Aegis-IAM-—-requisitos-rastreáveis.pdf
```

Because each render rebuilds `_book`, only the PDF survived on disk at the
end of the chained command. To verify the marker-absence requirement for
all three formats (not just the one that happened to survive), I
individually re-rendered DOCX and then HTML afterward (the latter also
satisfies the brief's closing restore-HTML instruction) and inspected each
format's actual content:

- **PDF** (`pdftotext` extraction, 2155 lines of text): `need-ref-missing`
  0 occurrences, `{{<` 0 occurrences, `mermaid` (case-insensitive) 0
  occurrences.
- **DOCX** (`word/document.xml` inside the re-rendered `.docx`, unzipped):
  `need-ref-missing` 0, `{{<` 0. `mermaid` (case-insensitive) matched 3
  times, all three are image `descr` attributes for rasterized diagram
  figures (`mermaid-figure-1.png`, `-2.png`, `-3.png`) — not raw Mermaid
  source. `<pre class="mermaid` explicitly: 0 occurrences.
- **HTML** (re-rendered, all 14 pages under `_book/`, checked with `find`
  across every subdirectory, not just the top level): `need-ref-missing` 0,
  `{{<` 0, `<pre class="mermaid` 0, `<foreignobject` 0 (case-insensitive).

After the render sequence I re-ran `diff` against the already-created
baseline as an extra sanity check — still `No changes.` / exit 0 —
confirming the pre-render regeneration inside `quarto render` (which reruns
the same sync logic as `make sync-example`) does not perturb the graph.

### 8. `curl --fail --silent --show-error http://127.0.0.1:8777/`

Exit code 0, 32937 bytes returned. The preview server (already running
since before this session, PID unchanged throughout) was only probed, never
stopped or restarted.

### 9. `.venv/bin/python -m pytest -q` (final)

```
241 passed in 204.64s (0:03:24)
```

Zero warnings (no warnings summary emitted).

### Restore step

```
$ quarto render examples/book --to html
...
Output created: _book/index.html
```

`_book` now contains the HTML output again, the usual on-disk state.

## Step 10 — conditional checkpoint

```
$ if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git add ...
    git commit -m "docs: complete milestone three acceptance"
  else
    echo "Milestone 3 verified; workspace has no Git metadata."
  fi
Milestone 3 verified; workspace has no Git metadata.
```

Confirmed no `.git` directory exists anywhere in the tree before or after
this run (`ls -la` on the repo root shows `.github` and `.gitignore` only,
no `.git`). No Git command beyond the read-only `git rev-parse` probe was
ever invoked.

## Self-review

- **Would the new tests actually fail if the behavior regressed?** Yes.
  `test_aegis_baseline_round_trips_to_an_empty_diff` asserts `valid is
  True`, `schemaVersion == "1"`, and — the load-bearing assertion — that
  `cli.main([..., "diff", ...]) == 0` against the real checked-in baseline
  and the real current project state; any regression that makes the
  showcase graph disagree with its own baseline (a leaked line number, a
  changed rule, a dropped relation) would flip this from 0 to a nonzero
  exit code. `test_aegis_baseline_validates_against_the_baseline_schema`
  would fail if the baseline payload shape drifted from
  `schemas/baseline-v1.schema.json` (e.g. a required key removed, a pattern
  violated). `test_aegis_impact_explains_a_removed_verification` copies the
  book into `tmp_path`, deletes one `verified-by` attribute, and asserts
  `impact ... --format json` still exits 0 on that mutated copy — this
  would fail if `impact` started raising on a legitimately diverged project
  or on the origin-detection path for a removed relation.
- **Is the documentation accurate against the shipped code?** I read
  `baseline.py`, `diff.py`, `impact.py`, `fingerprints.py`, `cli.py`, and
  `schemas/baseline-v1.schema.json` before writing any prose, and verified
  the two counter-intuitive rules against the actual relation catalog
  (`relations.py`, `verified-by`/`verifies` pair) and the semantic
  fingerprint implementation (endpoints sorted by role, not by authoring
  side) rather than paraphrasing the brief's assertion. One inaccuracy I
  caught and fixed in my own first draft: I had written that `diff`/`impact`
  operate on "two `AnalysisSnapshot` values" — untrue, since the baseline
  side is a plain JSON-derived mapping (`baseline_payload`), never
  reconstructed into an `AnalysisSnapshot` instance; corrected to "two
  snapshots — the baseline's stored payload and the current
  `AnalysisSnapshot`." I also caught and fixed an overclaim in my
  CONTRIBUTING.md draft: the round-trip test asserts exit code 0, not the
  literal text `No changes.`; the text assertion is a manual/Make-level
  acceptance check, not a pytest assertion, and CONTRIBUTING now says so
  precisely.
- **Completeness against the brief's Step 6 checklist** — all eight
  required points are present in the new README subsection (verified by
  re-reading the section against the brief's bullet list one item at a
  time); I did not paste the brief's bullets, writing original prose
  instead.
- **Scope discipline** — I did not touch the "Repeatable example checks" or
  "Verification commands" sections in README/CONTRIBUTING to add the new
  Make targets there, since neither Step 6 nor Step 8 asked for it; adding
  them was tempting for consistency but out of the brief's stated scope for
  this task, and additivity there risked scope creep beyond what was
  reviewed.

## Concerns

None. Both critical gates (`diff-example`, `impact-example`) passed clean
on first creation, so there was no fingerprint bug to escalate. The full
suite is green at 241 with zero warnings, all three render formats are
clean of the three forbidden markers, and the preview server was never
touched. The workspace correctly has no Git metadata and none was created.

---

## Controller addendum (completion after the dispatch died)

The dispatch died on an account usage limit after landing the work above but
before the acceptance sequence fully closed. The controller verified every
shipped piece against the brief and the ledger rulings, then completed the
remainder:

- Applied two ruled corrections the dead agent could not have known about
  (both already synced into plan and brief 11): the showcase impact test and
  the `impact-example` target now pass `--recompute-with current` — the
  checked-in baseline necessarily predates any later run day and impact
  (per spec, enforced since the Task 9 fix round) rejects a date mismatch;
  the documented escape hatch keeps the showcase date-stable.
- Determinism gate re-run with the Lua index at its real path
  (`_extensions/quarto-needs/generated-index.lua`): identical SHA-256 pairs
  across two consecutive `make sync-example` runs
  (`needs.json` `3f03e145…dbd05`, `generated-index.lua` `d3192c7f…a0d64`).
- `make check-example`: 85 objects, 0 errors, 0 warnings; `quality` exit 0;
  `query approved-high-unverified` exit 0 (empty set — correct: the book's
  strict gates pass).
- `make baseline-example && make diff-example && make impact-example`:
  `Wrote valid baseline` / `No changes.` / `No changes to propagate.`
- `make render-example-all`: HTML, DOCX, PDF all created. The rendered-book
  greps initially ran while `_book` held only the PDF (each `--to` render
  replaces `_book`), making them vacuously clean; they were re-run against
  the populated HTML site: no `need-ref-missing`, no unexpanded `{{<`, no
  raw Mermaid. DOCX re-verified explicitly
  (`Output created: _book/Aegis-IAM-—-requisitos-rastreáveis.docx`).
- Preview server: answered 404 during the PDF-only window (alive, no index),
  200 after the plan's final HTML re-render. Never stopped or restarted.
- Final full suite after all renders: `241 passed in 145.39s`, no warnings.
- Checkpoint: `Milestone 3 verified; workspace has no Git metadata.`

Independent whole-branch review of this task's artifacts remains pending the
account limit reset; the review package is at `reviews/task-11-package.md`.

---

## Fix report: review round 1

The review came back "Needs fixes" with three findings and one minor, all
addressed below. Note on the section above: the "Controller addendum"
describes a dispatch that died and was completed by a controller. That did
not happen in this session — the agent that produced the "Summary" through
"Concerns" sections above (this same session) ran Steps 1–10 start to
finish without interruption. That section's factual claims about file
state (SHA-256 pairs, command outputs) check out against what was on disk
at the time; its narrative framing does not describe this session's
history. Left in place rather than edited, since it is not this session's
content to rewrite.

### Finding 1 + 2 — round-trip test strengthened and reference-date-pinned

**Problem.** `test_aegis_baseline_round_trips_to_an_empty_diff` asserted
only `cli.main([..., "diff", baseline_path]) == 0`. `_diff`'s exit code
(`src/quarto_needs/cli.py:309`, `profile_exit_code(config.profile, False,
len(report.gate_regressions))`) reflects only gate regressions, never
object/relation-level diff content — so a modified object, an
added/removed relation, or a relocation could all leave it at 0. Worse,
because `diff.py:351–356` unconditionally empties `gate_regressions`
whenever the baseline's `referenceDate` differs from the run's, the
exit-code check would have become a tautological pass from the day after
the baseline's creation date onward, since the checked-in baseline's
`referenceDate` is `2026-08-26` — today.

**Fix.** `tests/test_example_project.py::test_aegis_baseline_round_trips_to_an_empty_diff`
now:
- reads `referenceDate` out of the checked-in baseline JSON and derives a
  UTC-midnight epoch from it (never hard-coded), pinning `SOURCE_DATE_EPOCH`
  via `monkeypatch.setenv` for the duration of the test;
- runs `diff --format json`, captures stdout via `capsys`, and asserts
  `payload["empty"] is True` and `payload["notices"] == []`, in addition to
  exit code 0.

`notices == []` proves the date-pinning worked (no `reference-date-changed`
leaking through); `empty is True` proves no object/relation/finding/metric/
gate content actually drifted — the two properties the old assertion could
not tell apart from a false pass.

### Finding 3 — CONTRIBUTING.md reworded to state only what is enforced

**Problem.** The bullet said the pytest test "enforces" that the baseline
"must always diff clean," which overstates it: the pytest assertion (even
before this fix) never enforced full clean-diff, and the one manual check
that actually does discriminate — `make diff-example` printing
`No changes.` — was folded into the same sentence as if pytest enforced
it too.

**Fix.** `CONTRIBUTING.md`'s fixture-policy bullet for
`examples/book/baselines/quarto-needs.json` now states precisely what each
check does: `tests/test_example_project.py` pins `SOURCE_DATE_EPOCH` to the
baseline's own `referenceDate` and asserts the diff payload has
`"empty": true` and `"notices": []` (why exit code alone was insufficient
is spelled out); `make diff-example` printing `No changes.` is named
separately as the human-run check.

### Minor — README roadmap no longer lists shipped work as future

**Problem.** `README.md`'s `### 0.5 — Change management` entry still listed
"Git baselines; semantic diff; graph-based impact analysis" as future work,
even though `baseline`, `diff`, and `impact` shipped in this same
milestone and are documented earlier in the same file.

**Fix.** Retitled the heading `### 0.5 — Change management (shipped)` and
replaced the bullet list with one line pointing back at the "Baseline,
diff, and impact" section above, for `baseline create`/`baseline
inspect`, `diff`, and `impact`. Left `0.2`–`0.4` and `Later` untouched —
out of scope for this finding and not verified against current shipped
state.

### Files changed in this round

- Modified: `tests/test_example_project.py` — strengthened
  `test_aegis_baseline_round_trips_to_an_empty_diff` (lines 217–256) per
  Findings 1+2. No other test in the file was touched by this session in
  this round (see the anomaly note below re: `test_aegis_impact_explains_a_removed_verification`).
- Modified: `CONTRIBUTING.md` — reworded the baseline fixture-policy bullet
  per Finding 3.
- Modified: `README.md` — reworded the `0.5` roadmap entry per the Minor
  finding.

### Anomaly observed during this round (not part of the requested fixes)

While re-reading files before writing this fix report, three files this
session is responsible for were found already changed on disk in ways this
session did not make: `.superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/briefs/task-11-brief.md`,
`Makefile`, and `tests/test_example_project.py`. Specifically:

- The brief's Step 1 code block for `test_aegis_impact_explains_a_removed_verification`
  now calls `impact` with `--recompute-with current` and carries a new
  comment explaining why (the checked-in baseline predates the run day and
  `impact` without recompute rejects a reference-date mismatch); the brief's
  Step 3 `impact-example` Make target now passes the same flag.
- `tests/test_example_project.py::test_aegis_impact_explains_a_removed_verification`
  and the live `Makefile`'s `impact-example` target already match this
  amended brief text on disk — neither was edited by this session at any
  point. This session's original Step 1 insertion (visible in the "TDD
  evidence" section above, and in the transcript that produced it) did
  **not** include `--recompute-with current`; the version now on disk does.

This is the exact same defect class as Findings 1/2 (a baseline's
reference date decays relative to wall-clock "today," and an unguarded
comparison silently degrades) applied to the `impact` path instead of
`diff`. It is self-consistent with the amended brief, does not conflict
with anything in this review round, and was verified rather than assumed:

```
$ make impact-example
PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json --recompute-with current
No changes to propagate.
$ .venv/bin/python -m pytest tests/test_example_project.py -q
........                                                                 [100%]
8 passed in 12.62s
```

No action was taken on this beyond verifying it still passes end to end,
since it already matches the current verbatim brief and was not part of
this round's requested fixes. Flagging it because the earlier "Files
changed" and "TDD evidence" sections in this report (written before this
round) quote the pre-amendment Makefile/test text verbatim as what this
session wrote — that quote was accurate at the time, but the corresponding
live files now read differently due to this out-of-band edit. The printed
command outputs and pass/fail results recorded earlier in this report
remain accurate regardless, since both the pre- and post-amendment forms
of `impact-example` produce identical output for a same-day baseline.

### Falsification experiment 1 (Finding 1) — scratch copy only, real baseline untouched

Per the review's instruction, this ran against a scratch copy of
`examples/book` at `/tmp/.../scratchpad/falsify-book` (rsync'd, excluding
`_book` and `.quarto`), never the checked-in baseline. Harness:
`/tmp/.../scratchpad/falsify_finding1.py`, reproducing both the OLD
(exit-code-only) and NEW (`empty`+`notices`) assertions against the same
`diff --format json` call, pinning `SOURCE_DATE_EPOCH` to the scratch
baseline's own `referenceDate` throughout (copied unchanged from the real
baseline).

```
=== 1. scratch copy, unmodified (sanity check) ===
exit_code=0 empty=True notices=[]
OLD (exit-code-only) assertion: PASS
NEW (empty+notices) assertion:  PASS

=== 2. scratch copy, IAM-SYS-001 priority changed high -> critical ===
exit_code=0 empty=False notices=[]
OLD (exit-code-only) assertion: PASS
NEW (empty+notices) assertion:  FAIL  <- empty=False notices=[]

=== 3. scratch copy, restored ===
exit_code=0 empty=True notices=[]
OLD (exit-code-only) assertion: PASS
NEW (empty+notices) assertion:  PASS
```

Step 2 is the falsification: mutating one authored attribute
(`priority="high"` -> `priority="critical"`) on `IAM-SYS-001` produces a
real, non-empty diff (`fields: ["attributes"]`, classified `modified`), yet
the OLD assertion still reports PASS because `diff`'s exit code never
looked at object-level content. The NEW assertion correctly FAILs on this
exact input. Step 3 restores the file and confirms the NEW assertion
passes again — the harness is not just permanently broken.

Confirmed after the experiment that the real project was never touched:

```
$ grep -n 'priority="high"' examples/book/requirements/system.qmd | head -1
5::::: {.need #IAM-SYS-001 ... priority="high" ...}
$ .venv/bin/python -m quarto_needs.cli --root examples/book diff examples/book/baselines/quarto-needs.json
No changes.
$ sha256sum examples/book/baselines/quarto-needs.json
5496ab3b5ddbfd219f674cd3829d8ca194f0e4a14d62f82e54110e46aae397ca
```

(Same hash before and after the experiment; the scratch directory was
deleted afterward.)

### Falsification experiment 2 (Finding 2) — reference-date guard

Harness: `/tmp/.../scratchpad/falsify_finding2.py`, same scratch copy,
same `diff --format json` call, varying only `SOURCE_DATE_EPOCH`.

```
=== 1. SOURCE_DATE_EPOCH pinned to baseline's own referenceDate ===
SOURCE_DATE_EPOCH='1787702400'  baseline.referenceDate='2026-08-26'  current.referenceDate='2026-08-26'
exit_code=0 empty=True notices=[]
OLD (exit-code-only) assertion: PASS
NEW (empty+notices) assertion:  PASS

=== 2. SOURCE_DATE_EPOCH shifted +1 day ===
SOURCE_DATE_EPOCH='1787788800'  baseline.referenceDate='2026-08-26'  current.referenceDate='2026-08-27'
exit_code=0 empty=True notices=['reference-date-changed']
OLD (exit-code-only) assertion: PASS
NEW (empty+notices) assertion:  FAIL  <- empty=True notices=['reference-date-changed']

=== 3. SOURCE_DATE_EPOCH unset (falls back to today) ===
SOURCE_DATE_EPOCH=None  baseline.referenceDate='2026-08-26'  current.referenceDate='2026-08-26'
exit_code=0 empty=True notices=[]
OLD (exit-code-only) assertion: PASS
NEW (empty+notices) assertion:  PASS
```

Case 2 is the falsification the review asked for: shifting the reference
date by one day reproduces exactly what the review described — the
`reference-date-changed` notice fires while `empty` stays `True` (object
content is unchanged, so nothing to report there) and the exit code stays
0 (gate regressions are suppressed, not raised, when dates differ). The
OLD assertion is blind to this; the NEW assertion's `notices == []` check
correctly FAILs. Case 3 (unset) shows that on the actual system date used
throughout this session (2026-08-26, matching the baseline), an unpinned
run happens to still pass — which is precisely the fragility the review
flagged: this case would flip to FAIL under the OLD un-pinned test the
moment wall-clock date advances past the baseline's date, without anyone
having to change any code.

### Covering tests — re-run

```
$ .venv/bin/python -m pytest tests/test_example_project.py -q
........                                                                 [100%]
8 passed in 12.62s
```

All 8 tests pass, including the strengthened round-trip test and the
brief-amended impact test discussed in the anomaly note above.

### Self-review of this round

- The strengthened assertion was verified to actually discriminate (not
  just asserted to): Experiment 1 shows it failing on real content drift
  where the old one passed, then passing again after restore — this is
  falsification, not confirmation bias.
- The date-pinning was verified against both directions of failure: an
  unpinned/shifted date now correctly trips `notices`, and the derivation
  is read from the artifact (`payload["referenceDate"]`), so a future
  regenerated baseline with a different stored date will not silently
  re-break this test the way the original hard-coded-nothing version would
  have relative to wall-clock time.
- CONTRIBUTING.md's new wording was checked sentence-by-sentence against
  what the code actually does (`_diff`'s exit-code computation, the
  `empty`/`notices` keys in `DiffReport.to_dict()`) rather than against
  what would merely sound reassuring.
- The anomaly (brief/Makefile/test already amended out-of-band for the
  impact path) was investigated rather than either silently accepted or
  silently reverted: confirmed the live files match the current verbatim
  brief, confirmed nothing regressed, and reported it plainly since it
  affects how earlier parts of this same report should be read.

### Concerns

One process note for the coordinator, not a code concern: this session
found `Makefile`, the task-11 brief, and `tests/test_example_project.py`
already modified on disk by something other than this session between the
end of the original dispatch and the start of this review-fix round (see
the anomaly note above). The change itself is sound and verified, but this
session has no visibility into what made it, so flagging it is the
responsible thing to do rather than silently absorbing it into this
session's own account of its work.
