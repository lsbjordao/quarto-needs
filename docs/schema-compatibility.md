# Public artifact & schema compatibility policy

**Status:** adopted by the core-stabilization phase
(`docs/superpowers/specs/2026-09-02-core-stabilization-design.md`, section 12).

Quarto-Needs emits machine-consumable artifacts. This document defines which
of them are promised as stable contracts, how each may evolve before 1.0, and
how a contributor decides whether a change needs a schema version bump.

---

## 1. Classification

### Public-versioned contracts

Consumed by tools, repositories, or people *outside* the release that
produced them. Breaking change ⇒ schema version bump (see §3).

| Artifact | Producer | Version identifier | JSON Schema |
| --- | --- | --- | --- |
| Canonical exported needs/snapshot (needs envelope + objects) | `export.py` (`render_v1_json`) | `schemaVersion: "1"` | `schemas/needs-envelope-v1.schema.json`, `schemas/needs.schema.json` |
| Baseline document | `baseline.py` | `schemaVersion: "1"` | `schemas/baseline-v1.schema.json` |
| Diff report | `diff.py` | `schemaVersion: "1"` | `schemas/diff-v1.schema.json` |
| Impact report | `impact.py` | `schemaVersion: "1"` | `schemas/impact-v1.schema.json` |
| Public graph projection | `graph_projection.py` | `schemaVersion: "graph-public-v1"` | `schemas/graph-public-v1.schema.json` |
| Evidence attestations / envelopes / provider checks | `evidence.py`, `evidence_providers.py` | `schemaVersion: "1"` | `schemas/evidence-*.schema.json` |
| ReqIF export | `exporters/reqif_export.py` | ReqIF-1.0 header + tool identity | (external standard) |
| JSON-LD export | `exporters/jsonld_export.py` | `@context` namespace document | — (context IRI is the contract) |
| SARIF export | `exporters/sarif_export.py` | SARIF `version`/`schemaUri` | (external standard) |
| JUnit export | `exporters/junit_export.py` | JUnit XML dialect | (external standard) |
| GitHub issue projection payloads | `github_projection.py` | `schemaVersion: "1"` | — (write-once external state) |

### Internal generated artifacts

Regenerated from the snapshot on every build and consumed by tooling that
ships in the *same* release (the Lua filters, the bundled browser JS), so
producer and consumer move in lockstep. They still carry a version
identifier for diagnostics, but a breaking change is a coordinated
same-release change, not a public version bump:

* C4 view payloads (`c4-view-v1`, `graph_output.py`) — rendered by the
  bundled renderers;
* generated Lua lookup index (`_extensions/quarto-needs/generated-index.lua`);
* localized title projections;
* PR report payloads (`pr_report.py`) — rendered to human-readable markdown.

`tests/test_semantic_kernel_contract.py` enforces that public projections
stay allowlist-built; that test failing usually means an internal field
leaked into a public artifact — which §4 forbids.

---

## 2. Rules for additive changes (no version bump)

An additive change to a public-versioned artifact is allowed **without**
bumping the version when **all** hold:

1. a new field or value is added; nothing existing is removed, renamed,
   repurposed, or re-typed;
2. the field is optional for consumers (absent means "not applicable", not
   a new semantic);
3. the matching JSON Schema under `schemas/` is updated in the same change
   (fields there must not be `required` unless they were always present);
4. serialization stays deterministic (existing golden/contract tests
   continue to pass unchanged);
5. unknown-field tolerance holds: consumers MUST ignore fields they do not
   know. Producers rely on this rule, so validators under `schemas/` must
   not set `additionalProperties: false` on public artifacts.

## 3. Rules for breaking changes (version bump required)

A change is breaking — and MUST bump the version identifier and the
matching `schemas/*-v<N>.*` file — if it does any of:

* removes, renames, or re-types an existing field;
* changes the meaning of an existing value (including severity or
  fingerprint semantics);
* makes a previously optional field required, or tightens a schema
  constraint in a way existing valid documents fail;
* changes the identifier format itself.

Procedure:

1. new `schemaVersion` value (integer bump for the `"1"`-style artifacts,
   new suffix for named ones such as `graph-public-v2`);
2. new/updated JSON Schema under `schemas/`;
3. golden fixtures updated **with an explanation in the commit message**
   (a changed golden without a semantic reason is a bug, not a change);
4. readers of the previous version keep working where feasible: when the
   artifact is long-lived (baselines, evidence envelopes), the loader
   should accept the previous version explicitly with a clear error or a
   migration note rather than a raw schema failure.

## 4. Python internals are not public

Fields on `ObjectRecord`, `RelationRecord`, `AnalysisSnapshot`, or any
other Python class are internal. Adding a Python field MUST NOT change any
public artifact; public payloads are built field-by-field from explicit
allowlists (`PUBLIC_NODE_FIELDS`, `PUBLIC_EDGE_FIELDS`, the v1 export
dicts), never by dumping records. Protected by
`tests/test_semantic_kernel_contract.py` and `tests/test_schema_contracts.py`.

## 5. Deterministic serialization

Every public artifact must serialize deterministically: identical analysis
input ⇒ byte-identical output (module non-deterministic generator version
and timestamps where the format deliberately carries them, e.g. baselines'
`referenceDate` — which itself is pinned by `QUARTO_NEEDS_REFERENCE_DATE`
for reproducibility). Golden tests pin this for the needs envelope, graph
projection, ReqIF, JSON-LD, and SARIF exports.
