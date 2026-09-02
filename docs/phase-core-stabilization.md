# Phase — Core stabilization

**Date:** 2026-09-02
**Design:** `docs/superpowers/specs/2026-09-02-core-stabilization-design.md`
**Plan:** `docs/superpowers/plans/2026-09-02-core-stabilization.md`
**Baseline record:** `docs/core-stabilization-baseline.md`

This phase stabilized the semantic kernel before further capability
expansion. It is the first slice of roadmap Phase 8 (scale, performance,
compatibility, release hardening).

---

## 1. Transitional architecture removed

The canonical analyzer no longer converts declarations into legacy DTOs to
validate them. Concretely:

* `analysis._legacy_objects()` — the `ObjectDeclaration → EngineeringObject`
  bridge — is deleted. Canonical `analyze_project()`/`_analyze_batch()`
  never construct an `EngineeringObject`.
* `validation.validate_declarations()` replaces the legacy
  `validate(list[EngineeringObject])` as the canonical pre-snapshot
  validation surface. It operates on `ObjectDeclaration` tokens and the
  relation catalog, and produces the entire historical pre-snapshot
  diagnostic set (REQ004/REQ005/REQ007 structural errors plus the
  REQ002/REQ006 declaration-local warnings).
* `model.to_declaration()` is the single, documented legacy→canonical
  adapter. Per the design's dependency rule, the legacy module depends on
  the canonical model — never the reverse.

The diagnostic behavior is preserved byte-for-byte and pinned by
characterization tests written before the refactor
(`tests/test_validation.py`, `tests/test_analysis.py`), including the
deliberately retained oddities: REQ004's first-occurrence location,
REQ005's resolved-v1-name message, and the presence of REQ002/REQ006
warnings on structurally blocked projects.

**Documented deviation from the plan's example classification:** the plan
suggested moving REQ002 (missing rationale) and REQ006 (approved without
verification) into post-snapshot validation. Characterization showed both
must remain pre-snapshot: structurally blocked projects produce no
snapshot, and their findings tuple is the only diagnostic surface, so
moving the warnings post-snapshot would silently hide them on broken
projects. Both checks are object-local (they need no resolved graph), so
they are computed declaration-natively; the snapshot-native semantic
governance layer (`run_rules`) is unchanged and already operated on
records. The choice is pinned by
`test_warnings_are_still_reported_when_the_snapshot_is_blocked`.

## 2. Final semantic pipeline

```text
source text
    → Parser (parse_project_declarations)          [QND001/QND002]
    → DeclarationBatch
    → validate_declarations (declaration-native)   [REQ004/005/007 errors; REQ002/006 warnings]
    → structural gate — errors block snapshot construction
    → _records (ObjectRecord/RelationRecord, catalog-resolved, deterministically sorted)
    → single-pass O(V+E) outgoing/incoming indexes
    → AnalysisSnapshot (+ fingerprints, derived fields, variants)
    → run_rules (snapshot-native governance)        [REQ008+, ID001, OBJ001/002, DEC001–006, ARC001, policies, constraints]
    → AnalysisResult → projections
```

The boundary is executable: `tests/test_semantic_kernel_contract.py`
(AST-based) fails if a canonical pipeline function references
`EngineeringObject`, if a kernel module imports the legacy model at
runtime, if graph/C4 projections stop consuming snapshots, or if browser
assets hardcode relation-family semantics.

## 3. Measured performance

Reproducible benchmarks added under `benchmarks/` (deterministic synthetic
model, fixed seed; sizes 100 / 1k / 10k / 50k; parse, analyze,
select_graph, rules, fingerprint stages). Baseline recorded in
`benchmarks/results/baseline-2026-09-02.json` and summarized in
`benchmarks/README.md`:

```text
   size    edges   parse_ms   analyze_ms  select_ms   rules_ms    fp_ms
    100      204        1.5          4.1        0.2        0.0      1.8
   1000     2049       15.1         39.6        0.7        0.1     14.7
  10000    20499      154.9        430.6        7.1        0.7    148.8
  50000   102499      887.9       2613.9       46.9        4.7    753.6
```

Every stage scales linearly; no superlinear behavior remains after the
index fix. CPython 3.13.5, Linux x86_64.

## 4. Optimizations adopted (each cites its measurement)

1. **Linear-time graph indexes** (`8854a65`): outgoing/incoming were built
   with one full relation scan per object — O(V·E). Replaced with a single
   bucketing pass, O(V+E), preserving deterministic ordering. Guarded by a
   scale test (4k objects/16k relations, 0.35 s) and an AST-level pattern
   guard.
2. **Single relation recomputation per impact run** (`8be3964`): profiling
   the 50k model showed `--recompute-with current` re-resolving every
   stored baseline relation twice (once in `diff.compare`, once for the
   traversal adjacency). `impact.analyze` now re-resolves once and hands
   the list to both. Measured 3.94 s → 2.86 s at 50k objects / 102k
   relations with identical output (290 impacted).

## 5. Optimizations deliberately rejected after measurement

* No snapshot-level adjacency/family indexes, no caching of undirected
  adjacency or relation-name maps: `select_graph` (47 ms at 100k edges),
  `run_rules` (5 ms), `queries.py`, and `policy.py` either already consume
  the canonical indexes or pay a single O(V+E) pass per user-invoked
  operation. Documented in `benchmarks/README.md`.
* No transitive-closure, all-pairs-paths, or query caches (spec non-goal).

## 6. Compatibility policy introduced

`docs/schema-compatibility.md` classifies every machine-consumable artifact
as **public-versioned** (needs envelope, baseline, diff, impact, public
graph projection, evidence envelopes, ReqIF, JSON-LD context, SARIF, JUnit,
GitHub projections) or **internal generated** (C4 view payloads, Lua index,
localized projections, PR reports), and defines additive vs breaking change
rules, the version-bump procedure, and the Python-internals-are-not-public
rule. Enforced by `tests/test_schema_contracts.py` (version markers,
parseable packaged schemas, allowlist-built payloads).

## 7. Quarto compatibility result

The extension declares `quarto-required: ">=1.6.0"`; CI previously exercised
only 1.10.18. The claim now has executable evidence:

* locally, `examples/minimal` renders correctly under exact **1.6.0** and
  **1.6.42** (1.6.0 emits headless-Chrome connection errors in this
  sandbox — its own bundled-Chromium probe, not an extension dependency —
  while exit code and output remain correct; 1.6.42 is fully clean) and
  under the installed 1.8.26;
* CI gains a `quarto-minimum` job pinned to exactly **1.6.0** running
  scan/check/render of the minimal example, while the expensive
  multilingual/DOCX/PDF matrix stays on the current integration version.

## 8. Minimal example result

`examples/minimal/` is a 15-object payments-retry-service project (one
stakeholder need, four requirements, one ADR, two components, four tests,
three evidence records) with one generated table, matrix, flow, and graph.
It analyzes cleanly (0 findings), passes `check`, supports `trace`, and
renders. `tests/test_minimal_example.py` pins the object/relation story,
the quality gate, and a real Quarto render where the environment provides
Quarto. It also serves as the small non-self-hosted integration fixture.

## 9. Verification

| Check | Result |
| --- | --- |
| `make test` (full suite) | **992 passed, 1 skipped** (baseline 959 passed, 1 skipped) |
| Aegis example (`--root examples/book check`) | 88 objects: 0 errors, 0 warnings |
| Self-hosted example (`--root examples/quarto-needs check`) | 159 objects: 0 errors, 0 warnings |
| Minimal example (`minimal-check`) | 15 objects: 0 findings |
| Multilingual Aegis HTML render (babelquarto, pt-BR) | 16/16 chapters rendered and normalized |
| Aegis DOCX render | passed |
| Installed consumer path (`check-install`) | PASS (non-editable install, out-of-repo render) |
| Root `make scan` / `make check` | **pre-existing failure**: they scan the whole repository without `--root` and hit intentionally-invalid test fixtures; the error set is byte-identical before (87 errors at `8a44a4f`) and after this phase — not a regression, not used by CI |
| PDF render | not run locally beyond tool availability (pdflatex present); covered by CI's 1.10.18 matrix |

## 10. Retained transitional paths (and why)

* `model.EngineeringObject` / `Relation` / `SourceLocation` — compatibility
  DTOs; convenience APIs and tests construct them; `to_declaration()`
  adapts them into the canonical pipeline.
* `analysis.analyze_objects(Iterable[EngineeringObject])` — public
  convenience entry point; adapts into the canonical analyzer.
* `validation.validate(list[EngineeringObject])` — compatibility wrapper
  over `validate_declarations` for external callers and existing tests.
* `parser.parse_qmd` / `parser.parse_project` / `_legacy_object` —
  compatibility constructors over the canonical parser (no internal
  callers).
* `graph.RequirementsGraph` — test-only surface over legacy DTOs.

Each is documented in place; a later deprecation decision can be made
independently (spec §6).

## 11. Remaining known limitations

* `run_rules` still skips the legacy four codes (REQ002/004/005/006) via
  `LEGACY_CODES`; their settings plumbing is dual-path (pre-snapshot
  severity application). A future cleanup could unify rule settings
  handling — deliberately deferred to avoid diagnostic churn in this
  phase.
* REQ002's rationale-governed types remain a hardcoded default set
  (`system-requirement`, `software-requirement`), as before.
* The root-level `make scan` / `make check` targets remain broken by
  design (they include intentionally-invalid fixtures); CI never calls
  them. A follow-up could point them at the self-hosted example.
* Benchmark absolute numbers are single-machine; only relative scaling is
  treated as signal.
* The extension's `">=1.6.0"` claim is exercised at exact 1.6.0 in CI; the
  1.7.x line remains untested (no declared support boundary change).
