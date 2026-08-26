# Task 6 implementation report

## Scope and outcome

Implemented Task 6 only: deterministic, atomic schema-v1 JSON and Lua projections from the canonical `AnalysisSnapshot`, while preserving the legacy coverage and export entry points.

The implementation adds:

- `build_v1_payload`
- `render_v1_json`
- `write_v1_graph`
- `render_lua_index`
- `write_lua_index`
- internal build helper `write_build_outputs`

No runtime dependency was added. Task 5 analysis, snapshot, and relation-catalog logic was inspected for integration but not modified. The existing Quarto preview process was not stopped or restarted and remained running during final verification.

## Strict TDD evidence

### Baseline before new tests

Command:

```bash
.venv/bin/python -m pytest tests/test_export.py tests/test_v1_contract.py -q
```

Result before Task 6 tests:

```text
3 passed, 2 warnings in 0.09s
```

The warnings are the pre-existing `jsonschema.RefResolver` deprecation warnings in `tests/test_v1_contract.py`.

### RED

All focused Task 6 tests were written before modifying `src/quarto_needs/export.py`.

Command:

```bash
.venv/bin/python -m pytest tests/test_export.py tests/test_v1_contract.py -q
```

Observed result:

```text
ERROR tests/test_export.py
ImportError: cannot import name 'build_v1_payload' from 'quarto_needs.export'

ERROR tests/test_v1_contract.py
ImportError: cannot import name 'render_v1_json' from 'quarto_needs.export'

2 errors during collection, 2 warnings
```

This was the expected failure: the new renderer/writer API did not exist.

After the minimal implementation, the focused run reached one remaining expected failure:

```text
1 failed, 14 passed, 2 warnings
```

The sole failure was `FileNotFoundError` for the not-yet-created canonical golden, confirming that implemented behavior passed and the reviewed fixture still needed to be generated.

### Golden generation and inspection

The canonical renderer output was generated once after the renderer existed, then checked into:

- `tests/fixtures/canonical/expected-needs-v1.json`
- `tests/fixtures/canonical/expected-generated-index.lua`

The generated content was inspected for:

- exact ordered IDs `A-REQ-001`, `M-NEED-001`, and `Z-TC-001`;
- literal unescaped Unicode (`Autenticação`);
- v1 `derives-from` normalization and absence of authored `derived-from`;
- exact nested-relation concatenation equality with top-level relations;
- absence of repository absolute paths and timestamp fields;
- namespaced `extensions.quartoNeeds` relation-catalog metadata;
- final newline in both fixtures.

The inspection command reported:

```text
goldens inspected: IDs, Unicode, v1 names, relation equivalence, path/timestamp hygiene, final newlines
```

Subsequent test runs read but did not rewrite these fixtures.

### GREEN: focused tests

Command:

```bash
.venv/bin/python -m pytest tests/test_export.py tests/test_v1_contract.py -q
```

Result:

```text
15 passed, 2 warnings in 0.11s
```

### GREEN: relevant regressions

Command:

```bash
.venv/bin/python -m pytest \
  tests/test_analysis.py tests/test_snapshot.py tests/test_parser.py \
  tests/test_graph.py tests/test_validation.py tests/test_example_project.py \
  tests/test_relations.py tests/test_extension_sync.py \
  tests/test_export.py tests/test_v1_contract.py -q
```

Result:

```text
47 passed, 2 warnings in 12.45s
```

### GREEN: full suite

Command:

```bash
.venv/bin/python -m pytest -q
```

Fresh final result:

```text
55 passed, 2 warnings in 62.65s (0:01:02)
```

The two warnings remain the existing `jsonschema.RefResolver` deprecations.

## Files changed

- `src/quarto_needs/export.py`
- `tests/test_export.py`
- `tests/test_v1_contract.py`
- `tests/fixtures/canonical/expected-needs-v1.json`
- `tests/fixtures/canonical/expected-generated-index.lua`
- `.superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/task-6-report.md`

No unrelated source file was modified.

## Implementation and compatibility evidence

- JSON projection consumes the snapshot's ordered objects and outgoing relation tuples.
- Nested relation lists are concatenated to form the top-level relation list, so they are exactly equal in content and order.
- Relation types use `RelationRecord.v1_name`; `authored_name` is never exported.
- Backlinks use v1 names and are sorted by source and type.
- `extensions.quartoNeeds.relationCatalog` contains only distinct present v1 names in sorted order.
- Alias metadata conflicts raise `ValueError` instead of allowing traversal order to select metadata.
- JSON uses `ensure_ascii=False`, `indent=2`, `sort_keys=True`, and exactly one final newline.
- Lua renders one deterministic `return { ... }` table and escapes backslash, double quote, newline, and carriage return.
- Atomic writes use a same-directory temporary file, flush, `os.fsync`, and `os.replace`, with temporary-file cleanup on failure.
- `write_build_outputs` renders both outputs fully before replacing either destination.
- `coverage(objects)` retains exactly the legacy six keys and calculations, including behavior for structurally invalid legacy input through a compatibility fallback.
- `export_graph(path, objects, findings)` and `export_lua_index(path, objects)` retain their signatures and `None` success return.
- Both compatibility writers analyze structural validity before touching their destination and raise exactly `ValueError("Cannot export a structurally invalid requirements graph")` for invalid graphs.
- The frozen Aegis v1 projection remains semantically equal after excluding the allowed additive extension and deterministic ordering differences.
- Interface inspection confirmed all required and preserved signatures.
- The existing preview processes were observed still running after tests.

## Self-review

Reviewed the implementation line by line against Task 6 and the design's exporter/compatibility clauses. Mutation-oriented checks are covered for:

- using authored relation names instead of v1 names;
- omitting or adding relation-catalog entries;
- silently selecting conflicting alias metadata;
- producing different bytes from reversed input order;
- omitting final newlines or failing Lua control-character escaping;
- writing the graph before Lua serialization completes;
- bypassing structural validation in compatibility wrappers;
- changing the six-key legacy coverage surface;
- changing frozen Aegis schema-v1 semantics.

An independent read-only reviewer reported no Critical, Important, or Minor issues, independently validated the live `examples/book` payload against the v1 envelope schema, and marked the task ready.

## Concerns and intentional boundaries

- The existing `RefResolver` deprecation warnings remain; replacing that test API is unrelated to Task 6.
- `write_build_outputs` guarantees render-before-write and individual atomic replacement, as specified. It is intentionally not a two-file filesystem transaction if the second filesystem replacement itself fails.
- No timestamp or absolute-path field is emitted.
- No new dependency is used.

## Git checkpoint

The workspace has no Git metadata. The conditional checkpoint check printed:

```text
Checkpoint 6 verified; workspace has no Git metadata.
```

No repository was initialized and no commit was created.
