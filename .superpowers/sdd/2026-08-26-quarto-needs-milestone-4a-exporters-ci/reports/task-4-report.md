# Task 4 Report: SARIF exporter

**Status: complete.** Full suite: `252 passed, 2 xfailed in 183.07s` (baseline before the task: `248 passed, 2 xfailed`; the +4 are the new SARIF tests). 0 warnings.

## What was built

- `schemas/vendor/sarif-2.1.0/sarif-schema.json` — vendored SARIF 2.1.0 JSON Schema from `https://json.schemastore.org/sarif-2.1.0.json` (111720 bytes; its `$id` is the OASIS canonical `https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json`; declares draft-07).
- `schemas/vendor/sarif-2.1.0/VENDORED.md` — upstream URL, canonical `$id`, version 2.1.0, MIT license notice, retrieval date 2026-08-26, SHA-256 `7c9688f0a1c4a4e1649ecc78521087e664729c1dff56ee8212ff195c7b16132a`.
- `src/quarto_needs/exporters/sarif_export.py`:
  - `render_from_findings(findings: Sequence[Finding]) -> str` — load-bearing producer (works when a structural failure left `snapshot` None).
  - `render(snapshot: AnalysisSnapshot) -> str` — convenience forwarding `snapshot.findings`.
  - `write(path, findings) -> Path` — atomic write through `export._write_atomic_text`.
  - Payload: `$schema` pinned to the vendored schema's `$id`, `version: "2.1.0"`, one run; `tool.driver` name `quarto-needs` + `quarto_needs.__version__`; one `reportingDescriptor` per distinct finding code (`id`, `shortDescription` from `RuleSpec.title`, `fullDescription` from `RuleSpec.help`, falling back to the bare code when not in `rules.RULES`); one `result` per finding with `level` error→error / warning→warning / info→note (fallback `note`), `message.text`, `locations[0].physicalLocation` (`artifactLocation.uri` = the parser's already project-relative `location.file`, `region.startLine`), `fingerprints.primaryLocationLineHash` = the existing `Finding.fingerprint` property; results sorted by (code, object_id, message); `automationDetails.id` fixed at `quarto-needs/export`; no timestamps; `json.dumps(..., indent=2, sort_keys=True) + "\n"` house style.
- `tests/test_export_sarif.py` — the brief's three tests verbatim (with the corrected `Draft7Validator` imports) plus the controller-mandated checksum test (`test_vendored_sarif_schema_checksum_is_locked`, sha256 of the vendored file against the value recorded in VENDORED.md).
- `src/quarto_needs/cli.py` `_export` — sarif branch replaces the NotImplementedError (single-file output via `sarif_export.write(output, result.findings)`); the snapshot-None guard now exempts sarif, so a structurally invalid project still writes its artifact, then prints findings and returns 1 after the write; json/csv behavior unchanged (early exit 1 before write); TODO comment updated to "Tasks 5-6 / junit/markdown".

No new runtime dependency: `sarif_export` imports only stdlib (`json`) and package internals; `jsonschema` remains test-only (`[project.optional-dependencies].test`).

## Manual end-to-end verification (controller-required probes)

| Probe | Result |
|---|---|
| `export --format sarif` on a clean project | exit 0, single file `out.sarif` written, validates against the vendored schema via `Draft7Validator` |
| `export --format sarif --baseline <path>` | exit 2 pre-analysis: `usage error: --baseline is only valid with --format markdown (got --format sarif)` |
| Structural failure (duplicate IDs → snapshot None) | SARIF artifact written (REQ004 result: level error, `uri: "needs.qmd"`, `startLine: 1`, `primaryLocationLineHash` set), findings printed to stderr, exit 1 |
| Unwritable destination (`--output` under a 0500 dir) | exit 3, message names the artifact path: `Could not write ...: [Errno 13] Permission denied` |

## Deviations

1. **Red-state exception class (cosmetic).** Step 3 predicted `ModuleNotFoundError`; the actual failing import was `ImportError: cannot import name 'sarif_export'` (the package `quarto_needs.exporters` exists, so the module-name import fails this way). Same failure mode; no action.
2. **`write` signature.** The brief's Interfaces block said `write(path, snapshot)`; per the brief's own Interface note (SARIF consumes findings, not the snapshot) and the controller summary, it is implemented findings-based: `write(path, findings) -> Path`. `cli._export` passes `result.findings`, which is what makes the structural-failure export possible.
3. **The loop xfail STAYS (controller supersedes brief Step 5).** The only sarif-related xfail is `test_export_runs_exactly_one_analysis_per_format` in `tests/test_cli.py`, whose loop also covers junit and markdown (Tasks 5-6, not landed). Per the controller's verified context it was left untouched (strict xfail still passes because junit/markdown still raise). No sarif-only xfail existed to remove.
4. **RuleSpec field names.** The brief described the registry as "code/name/description/default severity"; the real fields are `code`/`title`/`help`/`default_severity` (read from `rules.py` as instructed) and are what the exporter uses.
5. **Brief test file kept verbatim**, including the unused `snapshot_with_findings` helper, per "use every value in it verbatim".

## Concerns

- None blocking. The vendored schemastore copy differs at byte level from the raw OASIS repo file (hash `d5558c…` vs vendored `7c9688…`; likely trailing-newline/serialization differences) — the controller verified the schemastore artifact is the official schema and its `$id` points at the OASIS repo; the checksum test pins the vendored bytes so drift is impossible offline.
- Checkpoint: the workspace is not a Git worktree (`git rev-parse` fails), so the conditional end-of-task checkpoint was skipped per the Global Constraint.

## Files touched (complete list)

- Created: `schemas/vendor/sarif-2.1.0/sarif-schema.json`, `schemas/vendor/sarif-2.1.0/VENDORED.md`, `src/quarto_needs/exporters/sarif_export.py`, `tests/test_export_sarif.py`
- Edited: `src/quarto_needs/cli.py` (import line + `_export` sarif wiring only)
