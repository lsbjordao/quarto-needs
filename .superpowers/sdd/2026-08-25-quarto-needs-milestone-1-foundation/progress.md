# SDD ledger — plan: docs/superpowers/plans/2026-08-25-quarto-needs-milestone-1-foundation.md

Spec: docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md
Baseline: `.venv/bin/python -m pytest -q` — 18 passed in 82.04s on 2026-08-25.

## Preflight rulings

- Ruling: execute in the shared workspace because this directory has no Git metadata and the approved plan forbids initializing Git — reviews use per-task filesystem snapshots and `diff -ruN` instead of commits — if wrong, recovery loses commit-level granularity but retains file-level diffs and test evidence.
- Ruling: semantic/content fingerprints remain deferred to Milestone 3, matching the spec's explicit milestone acceptance split — if wrong, Milestone 1 will need a follow-up snapshot-schema change.
- Ruling: the v1 envelope rejects unknown top-level keys while all additive governance data lives under `extensions.quartoNeeds`, matching the approved compatibility contract — if wrong, an undocumented consumer emitting its own top-level keys will fail schema validation.
- Ruling: in Task 1, capture the fixture and configure test dependencies first, then write/run the contract test before creating or extending schemas; this overrides the plan's schema-before-test step ordering to satisfy mandatory TDD — if wrong, the implementation order differs from the prose but the final files and acceptance contract remain identical.

## Preflight task/interface scan

| Task(s) | Producer → consumer or self-check | Finding |
|---|---|---|
| 1 | Frozen Aegis v1 fixture + envelope schema → Task 6 compatibility writer | Consistent; fixture must be copied before production edits. |
| 1, 10 | Test extra/Makefile/CI install → final developer commands | Consistent; Task 10 only adds render targets. |
| 2 | Relation catalog + authored_name → parser/model tests | Consistent; positional Relation API remains four required arguments. |
| 2, 3 | Catalog-backed legacy parser → declaration parser wrappers | Consistent; Task 3 must thaw attributes for legacy DTOs. |
| 2, 6 | Catalog v1 names/labels → v1 relation and extension projection | Consistent; `derived-from` emits `derives-from`. |
| 3 | Frozen records + diagnostics → parser/snapshot tests | Consistent after optional declaration locations for source-less legacy DTOs. |
| 3, 4 | Finding re-export/location → deterministic validation | Consistent; validation converts SourceLocation to LocationRecord. |
| 3, 5 | DeclarationBatch/records → AnalysisResult builder | Consistent; snapshot fields are declared before orchestration. |
| 4 | DuplicateIdError + direct validation → graph/validation tests | Consistent; graph raises only for direct legacy construction, analysis returns findings. |
| 4, 5 | Structural findings → invalid AnalysisResult | Consistent; QND001/QND002/REQ004/REQ005/REQ007 suppress snapshots. |
| 5 | One-read deterministic analysis → analysis tests | Consistent; file-order and read-count tests precede implementation. |
| 5, 6 | Immutable snapshot/indexes → deterministic payload writer | Consistent; writer derives nested/top-level relations from one collection. |
| 6 | Canonical/atomic renderers → export and golden tests | Consistent; both build outputs render before either replacement. |
| 6, 7 | Writer APIs → one-pass CLI/build | Consistent; CLI uses snapshot writers directly and legacy wrappers remain external. |
| 7 | Snapshot traversal → CLI behavior | Consistent after explicit transitive BFS ruling in plan. |
| 7, 10 | Pre-render/build → example regeneration | Consistent; pre-render synchronizes then invokes build once. |
| 8 | Global Lua cache/index/link resolver → Lua/HTML tests | Consistent; assets flag and graph state are process-global. |
| 8, 9 | `views.get/outgoing/incoming/link` → relation renderer/cards/shortcode | Consistent; all links flow through the source-aware resolver. |
| 8, 10 | Canonical Lua assets → example sync | Consistent; generated-index remains excluded from canonical asset copying. |
| 9 | Pandoc-native relation renderer → HTML/DOCX/PDF tests | Consistent; nested fixture page is read separately from index. |
| 9, 10 | Card/backlink UI → Aegis acceptance | Consistent; IAM-SYS-001 has both outgoing and incoming edges. |
| 10 | Docs, sync, CLI, all-format render → Milestone 1 gate | Consistent; no later-milestone feature is required for acceptance. |

## Execution

- Task 1: review ⚠️ resolved — historical ordering is evidenced by `task-1-before` (old object schema, no envelope/golden/test) versus `task-1-after`; focused verification was rerun by the controller.
- Task 1: minor (deferred): migrate deprecated `jsonschema.RefResolver` test infrastructure to `referencing`; the task brief explicitly permits the warning for this milestone.
- Task 1: complete (no commits: no Git metadata; review clean; controller verification `2 passed, 2 permitted deprecation warnings in 0.09s`).
- Task 2: minor (deferred): persist an assertion that `EngineeringObject.to_dict()` omits `Relation.authored_name`; implementation is correct, but the implementer's boundary check was not committed as a regression test.
- Task 2: complete (no commits: no Git metadata; review approved; controller verification `9 passed, 2 previously permitted deprecation warnings in 0.20s`).
- Task 3: complete (no commits: no Git metadata; review clean; controller verification `9 passed in 27.58s`).
- Task 4: review concern resolved — the one transient Quarto failure had no rendering-path diff, direct render passed, the implementer reran all 32 tests successfully, and the controller reran the 7 graph/validation/example tests successfully.
- Task 4: complete (no commits: no Git metadata; review clean; controller verification `7 passed in 24.88s`).
- Task 5: review found 2 important determinism defects (duplicate selected paths and a non-total finding key).
- Task 5: fix round 1/5 (2 addressed, 0 open; scoped re-review approved; no new issues).
- Task 5: complete (no commits: no Git metadata; controller verification `11 passed in 0.03s`; implementer full suite `43 passed, 2 permitted deprecation warnings in 40.78s`).
- Task 6: hardening opportunity (deferred to final acceptance): add a forced `os.replace` failure regression for sentinel preservation and temporary-file cleanup; reviewer confirmed the implementation is correct.
- Task 6: hardening opportunity (deferred to final acceptance): validate the current Aegis payload, including `extensions`, against the v1 envelope in a persisted test; reviewer independently validated it successfully.
- Task 6: complete (no commits: no Git metadata; review approved with no implementation findings; controller verification `15 passed, 2 permitted deprecation warnings in 0.13s`; implementer full suite `55 passed, 2 permitted warnings in 62.65s`).
- Task 7: hardening opportunity (deferred): persist invalid-input single-analysis counts and trace cycle/mixed-case sorting probes; reviewer independently probed the latter and confirmed current behavior.
- Task 7: complete (no commits: no Git metadata; review approved with no implementation findings; controller verification `23 passed in 0.12s`; implementer full suite `74 passed, 2 permitted deprecation warnings in 45.40s`).
- Ruling: the inherited preview expected on `127.0.0.1:8777` was found unavailable by a direct controller `curl` after Task 7, despite no task touching it; relaunch only after final implementation/acceptance so it serves the final synchronized state — if wrong, the user temporarily lacks a live preview during Tasks 8–10 but avoids repeated restarts and stale assets.
- Resumed by a new controller session on 2026-08-25; re-verified the inherited baseline as `74 passed, 2 permitted deprecation warnings in 37.97s` before starting Task 8.
- Ruling: Task 8 derives `current_input` from `quarto.doc.input_file`, keeping `PANDOC_STATE.input_files[1]` only as a fallback; Quarto hands Pandoc a temporary intermediate file (`/tmp/quarto-session*/quarto-input*.md`), so the plan's `PANDOC_STATE`-only step could never satisfy the same-page-anchor binding — if wrong, a harness that omits `quarto.doc.input_file` silently degrades to the documented `PANDOC_STATE` path.
- Task 8: complete (no commits: no Git metadata; focused verification `17 passed in 30.35s`; full suite `79 passed, 2 permitted deprecation warnings in 47.47s`).
- Ruling: Task 9 styles the relation sections with the stylesheet's existing `--bs-border-color` token instead of the plan's `--need-border`, which `needs.css` never defines — if wrong, the border color differs from an intended future token but no rule is dropped.
- Task 9: complete (no commits: no Git metadata; focused verification `22 passed in 53.10s`; full suite `83 passed, 2 permitted deprecation warnings in 69.98s`).
- Resumed by a new controller session on 2026-08-25 after the Task 10 implementer stopped mid-task; the inherited state already contained the Makefile `render-example-all` target, the strengthened example test, the README regeneration commands, and a synchronized example.
- Task 10: persisted both Task 6 deferred hardening regressions (envelope validation of the regenerated Aegis payload including `extensions`; forced `os.replace` failure preserving the sentinel and cleaning the temporary file).
- Ruling: each `quarto render --to <format>` rebuilds `_book`, so after `make render-example-all` only the final PDF remains on disk; each render was content-verified before the next and an explicit HTML re-render restored the usual `_book` state — if wrong, reordering the target to pdf→docx→html would leave HTML as the final state.
- Ruling: relaunched the preview on `127.0.0.1:8777` with `--no-browser` only after every acceptance gate passed, serving the final synchronized state, per the earlier relaunch ruling.
- Task 10: complete (no commits: no Git metadata; sync determinism verified by identical SHA-256 across two `make sync-example` runs; schema/compatibility `22 passed, 2 permitted warnings`; full suite `85 passed, 2 permitted deprecation warnings in 116.26s`; CLI smoke all exit 0 with `cmp`-identical export; html/docx/pdf renders exit 0 with relation labels, backlinks, badges, and no `need-ref-missing`; preview alive on 8777).
- Milestone 1 gate: PASSED — all ten tasks complete; Work on Milestone 2 starts only with a separate implementation plan.
