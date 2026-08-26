# Task 3 Report: Immutable Declarations, Records, and Located Diagnostics

## Status

Complete. No Git metadata is present, so no commit was created. The existing
Quarto preview process remains alive.

## RED evidence

Behavioral tests were added before production changes for recursive freezing,
deterministic project declarations with authored relation provenance, unclosed
blocks, and empty known relations.

Command:

```text
.venv/bin/python -m pytest tests/test_snapshot.py tests/test_parser.py -q
```

Observed failure (exit 2):

```text
ModuleNotFoundError: No module named 'quarto_needs.snapshot'
ImportError: cannot import name 'parse_project_declarations' from 'quarto_needs.parser'
2 errors during collection
```

These failures were expected and directly identified the missing immutable API
and declaration parser entry points.

## GREEN evidence

Initial focused checkpoint:

```text
.venv/bin/python -m pytest tests/test_snapshot.py tests/test_parser.py -q
7 passed in 0.13s
```

Required parser/snapshot/example regression:

```text
.venv/bin/python -m pytest tests/test_snapshot.py tests/test_parser.py tests/test_example_project.py -q
9 passed in 24.33s
```

The Aegis compatibility parse was also inspected and contains exactly 85
objects.

Full suite (run once):

```text
.venv/bin/python -m pytest -q
28 passed, 2 warnings in 72.96s
```

The two warnings are existing `jsonschema.RefResolver` deprecation warnings
from `tests/test_v1_contract.py`.

## Files

- Created `src/quarto_needs/snapshot.py`
- Created `src/quarto_needs/diagnostics.py`
- Modified `src/quarto_needs/parser.py`
- Modified `src/quarto_needs/validation.py`
- Created `tests/test_snapshot.py`
- Modified `tests/test_parser.py`

## Implementation summary

- Added recursive, deterministic JSON freeze/thaw helpers that reject invalid
  JSON values and non-finite numbers.
- Added frozen, slotted declaration, record, snapshot, and result dataclasses;
  mapping and sequence inputs are defensively frozen.
- Moved `Finding` to the dependency-neutral diagnostics module while preserving
  `from quarto_needs.validation import Finding`.
- Added immutable parser declarations and located `QND001`/`QND002` findings.
- Recorded relation provenance from metadata offsets, with inline attributes
  located on the `.need` opening line.
- Kept legacy parser wrappers and thawed immutable attributes back to ordinary
  dictionaries/lists; project DTOs now use the required deterministic ID sort.
- Located legacy duplicate-ID and unknown-target structural findings.

## Self-review

- Confirmed every parser-produced declaration and relation token has a source
  location; optional locations remain available for future source-less legacy
  adapters.
- Confirmed the diagnostics/snapshot imports have no runtime cycle.
- Confirmed title, body, rationale, unknown-metadata, and v1 authored-relation
  behavior remains compatible on the example project and golden-contract suite.
- Confirmed metadata relation lines are calculated during preamble collection,
  not recovered by ambiguous text search.
- Confirmed the existing Quarto preview process remains running.
- Ran bytecode compilation successfully for `src/quarto_needs` and `tests`.

## Concerns

No implementation concerns. The only outstanding noise is the pre-existing
`jsonschema.RefResolver` deprecation warning noted above.
