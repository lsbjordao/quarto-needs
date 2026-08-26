# Task 4: Duplicate-safe graph construction and validation

## Status

Complete. The workspace has no Git metadata, so no checkpoint commit was created.

## TDD evidence

- **RED:** `.venv/bin/python -m pytest tests/test_graph.py tests/test_validation.py -q`
  produced 2 expected failures and 3 passes. The failures showed that duplicate
  IDs did not raise and that adjacency lists preserved authored order.
- **GREEN:** the same focused command produced `5 passed in 0.03s` after the
  minimal graph and validation changes.
- **Integration:** `.venv/bin/python -m pytest tests/test_graph.py tests/test_validation.py tests/test_example_project.py -q`
  produced `7 passed in 24.90s`.
- **Full suite:** `.venv/bin/python -m pytest -q` produced `32 passed, 2 warnings
  in 77.63s`. The warnings are existing `jsonschema.RefResolver` deprecations.

## Changed files

- `src/quarto_needs/graph.py`
  - Adds `DuplicateIdError` with duplicate ID and sorted available locations.
  - Detects duplicate declaration IDs before graph materialization, choosing the
    first duplicate by `(id.casefold(), id)`.
  - Sorts valid outgoing and incoming adjacency lists deterministically.
- `src/quarto_needs/validation.py`
  - Validates duplicate IDs and unknown targets directly from declarations,
    without building an ambiguous graph.
  - Sorts all findings by severity, code, object, location, and message.
- `tests/test_graph.py`
  - Covers duplicate rejection/location ordering and deterministic adjacency
    ordering while retaining the traversal check.
- `tests/test_validation.py`
  - Covers combined duplicate and unknown-target diagnostics, including location
    provenance.

## Self-review

- Confirmed `RequirementsGraph.build()` raises before creating the public graph
  dictionaries when duplicates are present.
- Confirmed validation emits REQ004 and REQ005 together and still runs the
  established REQ002 and REQ006 rules.
- Confirmed valid traversal behavior and the example project remain covered.
- Confirmed no preview process was stopped.

## Concern

The first full-suite render test failed once with Quarto exit status 1 while its
captured renderer stderr was unavailable. A direct `quarto render examples/book`
immediately succeeded (85 objects, 0 findings), and the subsequent full-suite
rerun passed all 32 tests. Treat this as a transient renderer/environment event;
no product change was made for it.
