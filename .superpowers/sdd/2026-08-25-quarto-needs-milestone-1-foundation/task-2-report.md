# Task 2 report: complete relation catalog

## Status

Implemented the immutable version-1 relation catalog, catalog-backed parser
normalization, and authored-name provenance while preserving the v1 DTO shape.
The existing Quarto preview process was left running.

## TDD evidence

### RED

Command:

```bash
.venv/bin/python -m pytest tests/test_relations.py tests/test_parser.py -q
```

Result: collection failed as intended with
`ModuleNotFoundError: No module named 'quarto_needs.relations'`. The missing
module prevented collection from reaching the new `Relation.authored_name`
assertions.

### GREEN / focused compatibility

Command:

```bash
.venv/bin/python -m pytest tests/test_relations.py tests/test_parser.py tests/test_export.py tests/test_v1_contract.py -q
```

Result: `9 passed, 2 warnings in 0.33s`. The warnings are the pre-existing
`jsonschema.RefResolver` deprecation notices from `tests/test_v1_contract.py`.

### Full verification

Command:

```bash
.venv/bin/python -m pytest -q
```

Result: `24 passed, 2 warnings in 65.37s (0:01:05)`. The same
`jsonschema.RefResolver` deprecation warnings were emitted.

Additional boundary check created a relation with
`authored_name="derived-from"` and verified that `EngineeringObject.to_dict()`
emits only `type`, `source`, `target`, and `attributes`; it passed. The check
also confirmed 17 catalog names and the `derived-from` -> `derives-from` v1
normalization.

## Files changed

- `src/quarto_needs/relations.py` — immutable `RelationKind` and
  `RelationCatalog` types plus all 17 version-1 entries.
- `src/quarto_needs/model.py` — optional trailing `Relation.authored_name` and
  explicit v1-safe serialization.
- `src/quarto_needs/parser.py` — derives accepted relation keys and v1 names
  from `DEFAULT_RELATION_CATALOG`.
- `tests/test_relations.py` — catalog coverage, inverse-family/role behavior,
  and authored-alias provenance regression tests.
- `tests/test_parser.py` — parser regression for catalog-only names
  `verifies` and `evidences`.

## Self-review

- Compared every embedded entry against the task table: authored/catalog/v1
  names, semantic family, roles, labels, and impact direction match.
- `Relation` retains four-argument positional construction; provenance was
  appended after `attributes`.
- `EngineeringObject.to_dict()` explicitly projects relations to the frozen
  schema-v1 shape and excludes `authored_name`.
- The parser no longer has an alias table or hard-coded relation-name list;
  catalog lookup is the sole normalization source.
- Confirmed the preview command remains live: `make preview-example` and its
  `quarto preview examples/book` child were still present after verification.

## Checkpoint and concerns

The required conditional checkpoint reported: `Checkpoint 2 verified;
workspace has no Git metadata.` No commit was created.

No implementation concerns found. The only test output concern is the existing
`jsonschema.RefResolver` deprecation warning, which is outside this task.
