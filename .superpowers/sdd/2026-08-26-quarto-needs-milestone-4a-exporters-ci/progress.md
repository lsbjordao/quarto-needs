# SDD ledger — plan: docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md

Spec: docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md (Exporters, CI design, CLI and failure semantics, "### Milestone 4" gate for 4A)
Execution mode: superpowers:subagent-driven-development, requested explicitly by the user.
Baseline: `.venv/bin/python -m pytest -q` — 241 passed, 0 warnings on 2026-08-26 (post Milestone 3 whole-branch fixes).

## Preflight rulings

- Ruling (inherited): this workspace has no Git metadata; the skill's git-based scripts are replaced by the copied `task-brief.py`, `snap.sh`, and `review-package.py`, exactly as Milestones 1–3 ran.
- Ruling (fixture, verified empirically): a strict `min-verification-trace` gate over a project with NO approved requirements passes vacuously (0/0 → 100.0%). Task 2's policy-failure test therefore authors an approved requirement without verification so the denominator is non-zero; the plan carries that fixture.
- Ruling (platform, verified empirically): `scan` on a 0o500 root raises PermissionError during path collection today; Task 1's guard placement covers it, so the chmod-based test ships as written (no monkeypatch variant needed).
- Ruling (interface): SARIF's load-bearing producer is `render_from_findings(findings)` — findings must export even when a structural failure left `snapshot is None`. Task 4's brief carries this.
- Ruling (semantics): the Markdown summary runs `diff.compare(..., recompute=True)` and `impact.analyze(..., recompute=True)` when a baseline is supplied, so config/date mismatches cannot refuse a CI summary and one policy governs — consistent with the Milestone 3 amended spec wording.

## Preflight task/interface scan

| Task(s) | Producer -> consumer | Finding |
|---|---|---|
| 1 | OSError guards in cli.py -> Task 2's export paths | Consistent; Task 2 reuses the same guard shape for new writers. |
| 2 | `export --format` dispatch -> Tasks 3–6 writers | Consistent; writers land incrementally, xfail marks bridge the gap (strict xfail so a silently-passing mark fails). |
| 2 | `report_from_snapshot(snapshot, config)` for the exit code | Consistent; pure, no second analysis. |
| 3 | `csv_export.write_all(directory, snapshot)` -> Task 2 csv path | Consistent; --output is a directory for csv. |
| 4 | `sarif_export.render_from_findings` -> Task 2 sarif path | Consistent; findings-based per the ruling above. |
| 5 | `junit_export.render(report: QualityReport)` -> Task 2 junit path | Consistent; `report_from_snapshot` supplies the report. |
| 6 | `markdown_export.render(snapshot, config, baseline=)` -> Task 2 markdown path | Consistent; recompute=True per the ruling above. |
| 7 | workflow yaml -> `tests/test_ci_workflow.py` | Consistent; pyyaml enters the test extra only. |

## Execution

- Task 1: implementer DONE (`243 passed`, 0 warnings; red run captured with raw PermissionError tracebacks). One flagged deviation accepted: the scan guard spans analysis-through-write in `build()` (the empirical 0o500 failure surfaces in write_build_outputs' mkdir, not path collection) — a superset of the brief's wording that the brief's own test requires.
- Task 1: review Approved, 0 Critical/Important, 3 observational Minors (brief-mandated README list asymmetry; export's guard covers the write only, analysis-phase OSError still traces — matches the brief's interface, later exporter tasks route theirs; the exit-3 message prints even under quiet=True, deliberate per the stable exit-code contract). Reviewer falsified the red state in a scratch copy, probed all four exit codes live, confirmed stderr/stdout separation and message content, one-analysis counts, and the chmod finally-restore leaves no locked dirs.
- Task 1: complete (no commits: no Git metadata).
- Drift note (2026-08-26 15:11-15:14): the USER concurrently hardened `test_aegis_baseline_round_trips_to_an_empty_diff` (pins SOURCE_DATE_EPOCH from the baseline's stored referenceDate; asserts the JSON payload's `empty: true` and `notices: []` rather than exit code alone — exit code reflects only gate regressions) and matched CONTRIBUTING's fixture policy wording. Reviewer sanity-checked the assumptions against the code and both files are green. Accepted as user-side work; not attributed to any task.
- Task 2: implementer DONE (`245 passed, 2 xfailed`, 0 warnings; strict-XPASS mechanism proven live by the reviewer). Two brief-sanctioned strict xfails carry TODO(milestone-4a-writers): the 5-format one-analysis loop (remove after Tasks 3-6) and the policy-failure artifact test (remove after Task 6).
- Task 2: review Approved, 0 Critical/Important, 2 Minors. Reviewer proved byte-identity four ways (scan, both export spellings, and the PRE-TASK exporter run from the task-2-before snapshot — identical sha256), zero analyses on `--baseline` rejection (tripwire-verified ordering), write-before-exit-code via hook instrumentation, and the exit matrix 0/1/3. Minors: (a) `_export` does not guard read-side OSError from analyze_project (pre-existing parity with the old tail block — close when the writers land in Tasks 3-6); (b) strict-profile gate failures now make export exit 1 after writing — specified, but Task 7 CI steps and docs must not assume export is always-0.
- Task 2: complete (no commits: no Git metadata).
- Task 3: implementer DONE after one blocked round (the all-cells ruling above) — `248 passed, 2 xfailed`, 0 warnings. Implementation reinstated byte-identical (the ruling changed only the test); csv wired into `_export` (directory output, exit-3 guard); the loop xfail correctly STAYS (Tasks 4-6 own removal); manual end-to-end probe recorded (three files, neutralized cell visible, CRLF bytes, unwritable→3).
- Task 3: review Approved, 0 Critical/Important, 5 Minors (all observational/disclosed): neutralization test guards objects.csv only (shared `_render` path makes the gap low-risk; note for Tasks 4-6); embedded field newlines stay LF inside quoted fields (accepted everywhere); findings.csv file/line empty for CLI-reachable warnings (REQ002/REQ006 carry no location by construction; mapping verified correct via unit probe); exit-3 message names the directory; write_all atomic per file, not across the trio (same granularity as scan). Reviewer falsified the neutralization test live (removing `_neutralize` from render_objects fails it), crafted every dangerous prefix through a scratch project, and proved determinism/casefold ordering, RFC 4180 round-trip, one-analysis (1) and zero-analysis `--baseline` rejection, and the intact strict xfails.
- Task 3: complete (no commits: no Git metadata).
