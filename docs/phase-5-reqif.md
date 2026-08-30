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

## Acceptance gates before 5.1 is complete

The public CLI must not claim supported ReqIF export until all of the following are satisfied:

1. validate generated output against the normative ReqIF 1.2 XSD;
2. parse the generated artifact with at least one independent ReqIF implementation;
3. define and test the identity mapping between Quarto-Needs IDs and ReqIF identifiers;
4. define loss semantics for rich text and unsupported authored values;
5. verify deterministic byte output for an unchanged semantic graph/reference date;
6. document attribute-definition and relation mapping explicitly;
7. add CLI integration (`export --format reqif`) only after the normative validation gate passes.

ReqIF import remains intentionally deferred until export identity, rich-text handling, attribute definitions, relation semantics, and round-trip losses are explicit.

## Phase 4.2 dependency note

The thin VS Code client already contains Extension Host smoke-test code, VSIX packaging scripts, installation documentation, and CI steps. The remaining release-hardening blockers are the missing real npm lockfile and a successful GitHub Actions execution. Current Actions runs fail before checkout (`steps: null`) for both Python and VS Code jobs, so they provide no repository-level test result.
