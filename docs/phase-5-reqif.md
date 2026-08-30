# Phase 5.1 — ReqIF 1.2 interchange

Status: **active implementation**.

This phase adds ReqIF as an interchange projection of the canonical Quarto-Needs engineering graph. ReqIF does not become an authoring model or a second semantic authority.

## Implemented slice

The current branch contains an initial deterministic ReqIF 1.2 exporter in `src/quarto_needs/exporters/reqif_export.py` with regression tests in `tests/test_export_reqif.py`.

The exporter currently projects:

- deterministic ReqIF document/header metadata;
- canonical Quarto-Needs object types as `SPEC-OBJECT-TYPE` entries;
- canonical objects as `SPEC-OBJECT` entries;
- canonical relations as `SPEC-RELATION` entries;
- relation catalog names as `SPEC-RELATION-TYPE` entries;
- semantic-family provenance in relation-type metadata;
- a deterministic `SPECIFICATION`/`SPEC-HIERARCHY` containing the exported objects;
- canonical authored IDs as explicit exported attributes, while ReqIF `IDENTIFIER` values remain XML-ID-safe deterministic hashes;
- authored attributes as canonical JSON so information is not silently discarded in the first interchange slice.

## Interoperability gates now encoded

Two external-validation contracts are now represented directly in the test suite without becoming runtime dependencies:

- `reqif` is a test-only independent consumer. `test_reqif_is_accepted_by_independent_parser` writes the Quarto-Needs projection and parses it through `ReqIFParser.parse()`;
- `xmlschema` is a test-only normative validator. `test_reqif_validates_against_normative_xsd_when_supplied` validates the generated instance whenever `REQIF_12_XSD` points at the official OMG `ReqIF/20110401/reqif.xsd` file.

The XSD test deliberately skips when the environment variable is absent: the normative OMG schema is neither vendored into the project nor downloaded implicitly during an ordinary test run.

These gates are **implemented, not yet claimed as passed** until they execute successfully in a real environment with the corresponding dependencies/schema available.

## Acceptance gates before 5.1 is complete

The public CLI must not claim supported ReqIF export until all of the following are satisfied:

1. **encoded; execution pending** — validate generated output against the normative ReqIF 1.2 XSD;
2. **encoded; execution pending** — parse the generated artifact with at least one independent ReqIF implementation;
3. **partially implemented** — define and test the identity mapping between Quarto-Needs IDs and ReqIF identifiers;
4. **pending** — define loss semantics for rich text and unsupported authored values;
5. **implemented** — verify deterministic byte output for an unchanged semantic graph/reference date;
6. **pending** — document attribute-definition and relation mapping explicitly;
7. **blocked on gates 1–6** — add CLI integration (`export --format reqif`) only after the normative validation gate passes.

ReqIF import remains intentionally deferred until export identity, rich-text handling, attribute definitions, relation semantics, and round-trip losses are explicit.

## How to run the normative gate locally

Install the test extras, obtain the normative XSD from the OMG ReqIF 1.2 specification page, then point the test at that local file:

```bash
python -m pip install -e ".[test]"
REQIF_12_XSD=/path/to/reqif.xsd pytest -q tests/test_export_reqif.py
```

An ordinary `pytest` run remains offline-friendly: only the normative-XSD test is skipped when `REQIF_12_XSD` is not supplied.

## Phase 4.2 dependency note

The thin VS Code client already contains Extension Host smoke-test code, VSIX packaging scripts, installation documentation, and CI steps. The remaining release-hardening blockers are the missing real npm lockfile and a successful GitHub Actions execution. Current Actions runs fail before checkout (`steps: null`) for both Python and VS Code jobs, so they provide no repository-level test result.
