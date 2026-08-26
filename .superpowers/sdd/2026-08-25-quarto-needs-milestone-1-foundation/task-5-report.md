# Task 5 Report: Deterministic Valid-or-Invalid Analysis Result

## Status

Complete. The analysis pipeline now returns one immutable, deterministic
`AnalysisResult`: structurally valid inputs receive a canonical snapshot, while
parser errors, duplicate IDs, unknown targets, and unsupported authored
relations retain declarations/findings and suppress the snapshot.

The workspace has no Git metadata, so no commit was created. The existing
Quarto preview process remained running.

## TDD evidence

### RED

The canonical fixtures and real behavior tests were created before production
code.

Command:

```text
.venv/bin/python -m pytest tests/test_analysis.py -q
```

Observed result (exit 2):

```text
ModuleNotFoundError: No module named 'quarto_needs.analysis'
1 error in 0.11s
```

This was the intended failure: the orchestration module and public analysis
entry points did not exist.

### GREEN

Initial focused command after the minimal implementation:

```text
.venv/bin/python -m pytest tests/test_analysis.py -q
7 passed in 0.04s
```

Required focused regression set:

```text
.venv/bin/python -m pytest tests/test_analysis.py tests/test_snapshot.py tests/test_parser.py tests/test_graph.py tests/test_validation.py tests/test_example_project.py -q
21 passed in 22.63s
```

After the mutation-check regressions for QND001/QND002 suppression,
source-less relation provenance, metrics, and generator metadata:

```text
.venv/bin/python -m pytest tests/test_analysis.py -q
9 passed in 0.06s
```

Bytecode compilation also succeeded:

```text
.venv/bin/python -m compileall -q src/quarto_needs tests
```

### Final full verification

The full suite was run once after implementation and self-review:

```text
.venv/bin/python -m pytest -q
41 passed, 2 warnings in 74.34s
```

The two warnings are the existing `jsonschema.RefResolver` deprecation
warnings from `tests/test_v1_contract.py`.

## Files

- Created `src/quarto_needs/analysis.py` with the public analysis entry points,
  named canonical sort helpers, compatibility metrics, structural gating, and
  immutable snapshot/index construction.
- Created `tests/test_analysis.py` with deterministic ordering, immutability,
  structural invalidity, single-read, source-less DTO, supplied-findings, and
  unsupported-relation coverage.
- Created `tests/fixtures/canonical/a-tests.qmd`.
- Created `tests/fixtures/canonical/z-requirements.qmd`.
- Created `tests/fixtures/canonical/invalid-duplicates.qmd`.
- `src/quarto_needs/snapshot.py` required no further edit because Task 3 had
  already introduced the exact immutable `AnalysisSnapshot` and
  `AnalysisResult` records needed by this builder.

## Self-review

- `analyze_project` obtains exactly one `DeclarationBatch`; the selected-file
  test confirms each source is read exactly once.
- Parser and compatibility findings are retained and sorted with
  `finding_key`; all five structural codes suppress snapshot construction.
- `analyze_objects(..., reported_findings=[])` still independently discovers
  duplicate IDs and unknown targets.
- Unknown authored legacy relations become located REQ007 findings rather than
  leaking `ValueError`.
- Source-less DTOs retain `location=None`, empty object locations, and empty
  relation provenance; no synthetic memory path is introduced.
- Objects, relations, outgoing/incoming values, metrics, and indexes are
  canonical and immutable. Fixture reversal yields equal snapshots.
- Generator name/version and relation-catalog version come from their canonical
  package/catalog sources.
- Legacy coverage matches the schema-v1 coverage semantics.
- No semantic or content fingerprint logic was added; that remains Milestone 3.
- The conditional checkpoint printed `Checkpoint 5 verified; workspace has no
  Git metadata.` No Git initialization or commit was attempted.
- `make preview-example`, its Quarto child, and the Deno preview process were
  still alive after self-review.

## Concerns

No Task 5 implementation concerns. The only verification noise is the
pre-existing `jsonschema.RefResolver` deprecation warning described above.

## Fix round 1

### Scope

Addressed only the two P2 review findings:

- repeated selected source paths are resolved, deduplicated, and ordered before
  parsing, so one physical source is read once and cannot create false duplicate
  declarations;
- analysis finding ordering now includes the previously omitted anchor and
  recursively canonical JSON properties, plus the remaining field-presence
  discriminators needed for a total key. Exact duplicate filtering uses that
  same key, preserving genuinely distinct JSON values such as `true` and `1`.

### RED evidence

The two focused regression tests were added before the production fix.

```text
.venv/bin/python -m pytest tests/test_analysis.py -q -k 'deduplicates_repeated_selected_source or finding_order_includes_anchor_and_canonical_properties'
2 failed, 9 deselected in 0.05s
```

The failures showed the repeated path produced `snapshot=None`, while reversing
findings changed snapshot equality.

The mutation check then strengthened the existing finding test with JSON
`true` versus `1` properties and captured the remaining equality bug:

```text
.venv/bin/python -m pytest tests/test_analysis.py -q -k 'finding_order_includes_anchor_and_canonical_properties'
1 failed, 10 deselected in 0.03s
```

The failure retained only four of five genuinely distinct findings.

### GREEN evidence

Focused analysis suite:

```text
.venv/bin/python -m pytest tests/test_analysis.py -q
11 passed in 0.03s
```

Fresh full-suite verification:

```text
.venv/bin/python -m pytest -q
43 passed, 2 warnings in 40.78s
```

The two warnings remain the pre-existing `jsonschema.RefResolver` deprecation
warnings.

### Changed files

- `tests/test_analysis.py`: adds duplicate-selected-path and total finding-order
  regressions, including distinct canonical JSON property values.
- `src/quarto_needs/analysis.py`: deduplicates resolved selected paths before
  parsing and uses a total canonical finding key for ordering/deduplication.
- This report: records fix-round RED/GREEN evidence.

No Git metadata or commits were created. No new concerns were found.
