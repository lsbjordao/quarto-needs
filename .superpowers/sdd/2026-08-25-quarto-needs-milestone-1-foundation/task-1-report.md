# Task 1 Report: Freeze the schema-v1 compatibility contract

Status: DONE_WITH_CONCERNS

## TDD record

The Aegis payload was captured before any production-schema change:

```bash
mkdir -p tests/fixtures/v1
cp examples/book/.quarto-needs/needs.json tests/fixtures/v1/aegis-needs-v1.json
cmp -s examples/book/.quarto-needs/needs.json tests/fixtures/v1/aegis-needs-v1.json
```

The final comparison confirms a byte-for-byte match (92,735 bytes).

Test dependency installation was configured first and then run:

```bash
.venv/bin/python -m pip install -e ".[test]"
```

It installed the project editable with `pytest>=8` and `jsonschema>=4.23` (resolved to jsonschema 4.26.0).

### RED

Command:

```bash
.venv/bin/python -m pytest tests/test_v1_contract.py -q
```

Output:

```text
F.
FAILED tests/test_v1_contract.py::test_frozen_aegis_payload_validates_against_v1_envelope
FileNotFoundError: .../schemas/needs-envelope-v1.schema.json
1 failed, 1 passed, 2 warnings
```

This is the intended failure: the contract test existed, the nested/top-level relation equivalence already held, and the envelope schema did not yet exist.

### GREEN

Command:

```bash
.venv/bin/python -m pytest tests/test_v1_contract.py -q
```

Output:

```text
..
2 passed, 2 warnings in 0.11s
```

Both warnings are the expected `jsonschema.RefResolver` deprecation warning.

## Files changed

- `pyproject.toml`: adds the `test` optional dependency group with `pytest>=8` and `jsonschema>=4.23`.
- `Makefile` and `.github/workflows/ci.yml`: install with `python -m pip install -e ".[test]"`.
- `schemas/needs.schema.json`: adds v1 `source` and `href` properties and makes relation `attributes` required with closed relation objects. Object-level additional properties remain allowed.
- `schemas/needs-envelope-v1.schema.json`: adds the Draft 2020-12 closed v1 graph-envelope schema and definitions for relations, coverage, findings, and backlinks.
- `tests/fixtures/v1/aegis-needs-v1.json`: byte-for-byte frozen Aegis v1 fixture.
- `tests/test_v1_contract.py`: validates the frozen fixture and asserts nested/top-level relation equivalence; includes `legacy_projection(payload)` for downstream semantic compatibility comparisons.

## Self-review

- Verified the frozen fixture still exactly matches `examples/book/.quarto-needs/needs.json`.
- Verified envelope ID, draft, required top-level fields, closed envelope, and closed required-attribute relation definition with `jq`.
- Verified the object schema preserved its ID, includes the exact `source`/`href` shapes, closes relation items, and has no object-level `additionalProperties` restriction.
- Verified both setup paths use the test extra (`make -n setup` and CI inspection).
- Ran the focused contract suite successfully after the final schema changes.
- Ran the conditional checkpoint command; it reported: `Checkpoint 1 verified; workspace has no Git metadata.` No commit was attempted.

## Concerns / follow-up

- `RefResolver` is deprecated in jsonschema 4.26.0. It was retained as required for this milestone; migrate this test infrastructure to the `referencing` registry in a later cleanup.
- Because the deprecated resolver changes resolution scope after the external object-schema reference, envelope properties that use local `$defs` are placed before `objects`. JSON object member order is semantically irrelevant, and the contract remains fully validated locally, but the follow-up migration should remove this resolver-specific ordering sensitivity.
