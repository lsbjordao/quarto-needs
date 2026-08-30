# Phase 5.1 — ReqIF 1.2 interchange

Status: **implemented; repository CI validation remains externally blocked**.

This phase adds ReqIF as an interchange projection of the canonical Quarto-Needs engineering graph. ReqIF does not become an authoring model or a second semantic authority.

## Implemented slice

The current branch contains a deterministic ReqIF 1.2 exporter in `src/quarto_needs/exporters/reqif_export.py`, installed-CLI routing in `src/quarto_needs/interchange_cli.py`, and regression tests in `tests/test_export_reqif.py` and `tests/test_interchange_cli.py`.

The exporter projects:

- deterministic ReqIF document/header metadata;
- canonical Quarto-Needs object types as `SPEC-OBJECT-TYPE` entries;
- canonical objects as `SPEC-OBJECT` entries;
- canonical relations as `SPEC-RELATION` entries;
- relation catalog names as `SPEC-RELATION-TYPE` entries;
- semantic-family provenance in relation-type metadata;
- a deterministic `SPECIFICATION`/`SPEC-HIERARCHY` containing the exported objects;
- canonical authored IDs as explicit exported attributes, while ReqIF `IDENTIFIER` values remain XML-ID-safe deterministic hashes;
- authored attributes as canonical JSON so unsupported typed values are not silently discarded.

## Normative and independent validation

Two external-validation contracts are represented directly in the test suite without becoming runtime dependencies:

- `reqif` is a test-only independent consumer. `test_reqif_is_accepted_by_independent_parser` writes the Quarto-Needs projection and parses it through `ReqIFParser.parse()`;
- `xmlschema` is a test-only normative validator. `test_reqif_validates_against_normative_xsd_when_supplied` validates the generated instance whenever `REQIF_12_XSD` points at the official OMG `ReqIF/20110401/reqif.xsd` file.

Local development validation on 2026-08-30 exercised both contracts successfully after correcting the normative ReqIF header rule: the ReqIF 1.2 XSD fixes the `REQ-IF-VERSION` document-header value to `1.0`. The exporter therefore distinguishes `REQIF_SPECIFICATION_VERSION = "1.2"` from `REQIF_HEADER_VERSION = "1.0"` explicitly.

The XSD test deliberately skips when the environment variable is absent: the normative OMG schema is neither vendored into the project nor downloaded implicitly during an ordinary test run.

## Identity mapping

Quarto-Needs authored IDs remain the human-facing canonical identity.

ReqIF `IDENTIFIER` values are generated deterministically as XML-ID-safe SHA-256-derived identifiers over a namespaced tuple containing the entity kind and canonical identity. This prevents authored-ID syntax from being constrained by ReqIF/XML requirements while preserving stable export identity.

The original Quarto-Needs object ID is always exported through the `quarto-needs.canonical-id` string attribute. A consumer therefore does not need to reverse the hash to recover canonical identity.

For relations, the ReqIF relation identifier is deterministic over `(source canonical ID, canonical relation name, target canonical ID, ordinal)`. Relation endpoints always reference the deterministic ReqIF object identifiers.

## Attribute and relation mapping

Each Quarto-Needs object type becomes one `SPEC-OBJECT-TYPE`. Every exported object receives the following string attributes:

- `quarto-needs.canonical-id` — canonical authored ID;
- `quarto-needs.status` — resolved lifecycle status;
- `quarto-needs.body` — authored body as text;
- `quarto-needs.rationale` — authored rationale as text;
- `quarto-needs.attributes-json` — deterministic canonical JSON representation of authored attributes not otherwise promoted to first-class ReqIF attributes.

Canonical relation catalog names become `SPEC-RELATION-TYPE` names. Their semantic family is preserved in relation-type metadata. Authored aliases are intentionally normalized to the canonical relation name because the canonical graph, not source spelling, is the interchange semantic authority.

## Explicit loss semantics

The current ReqIF exporter is intentionally conservative:

- Markdown/rich presentation is exported as string content, not XHTML. Formatting semantics are therefore not promised to round-trip;
- arbitrary authored attribute values are preserved in canonical JSON, but their original ReqIF-native datatype is not inferred. A future typed-mapping layer may promote selected attributes explicitly;
- authored relation aliases are normalized to canonical relation names and are not round-tripped as source spelling;
- source-location/provenance details that are presentation- or repository-specific are not represented as core ReqIF semantics in this phase;
- no import or round-trip equivalence claim is made by Phase 5.1.

These are documented transformations rather than silent loss. ReqIF import remains deferred until import conflict policy, typed attribute recovery, provenance handling, and round-trip guarantees are designed explicitly.

## CLI

The installed CLI now exposes ReqIF export through the thin interchange adapter:

```bash
quarto-needs --root . export --format reqif
```

The default destination is `.quarto-needs/requirements.reqif`. A custom path can be supplied with `--output`:

```bash
quarto-needs --root . export --format reqif --output exchange/model.reqif
```

The adapter analyzes the project through the same canonical Python core as every other projection and refuses to export when no valid semantic snapshot exists.

## Acceptance status

Phase 5.1 acceptance gates are now:

1. **passed locally** — generated output validates against the normative ReqIF 1.2 XSD;
2. **passed locally** — generated output parses with an independent ReqIF implementation;
3. **implemented and documented** — deterministic identity mapping between Quarto-Needs IDs and ReqIF identifiers;
4. **implemented and documented** — explicit loss semantics for rich text, authored aliases, and unsupported typed values;
5. **implemented** — deterministic byte output for an unchanged semantic graph/reference date;
6. **implemented and documented** — attribute-definition and relation mapping;
7. **implemented** — installed CLI integration via `export --format reqif`.

Repository-level CI confirmation remains blocked by the existing GitHub Actions runner condition in which jobs terminate before checkout with `steps: null`; this does not change the local acceptance result but remains a release-hardening dependency.

## How to reproduce the normative gate locally

```bash
python -m pip install -e ".[test]"
REQIF_12_XSD=/path/to/reqif.xsd pytest -q tests/test_export_reqif.py
pytest -q tests/test_interchange_cli.py
```

## Phase 4.2 dependency note

The thin VS Code client already contains Extension Host smoke-test code, VSIX packaging scripts, installation documentation, and CI steps. The remaining release-hardening blockers are the missing real npm lockfile and a successful GitHub Actions execution. Current Actions runs fail before checkout (`steps: null`) for both Python and VS Code jobs, so they provide no repository-level test result.
