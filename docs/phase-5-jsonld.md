# Phase 5.2 — JSON-LD projection

Status: **active implementation**.

JSON-LD is a machine-readable semantic projection of the canonical Quarto-Needs engineering graph. It is not an alternate authoring model and does not introduce a second relation catalog, query engine, or rule engine.

## Current projection

`src/quarto_needs/exporters/jsonld_export.py` emits a deterministic JSON-LD 1.1 document with a single `@graph` containing:

- one `qn:EngineeringGraph` node with reference date, configuration fingerprint, semantic graph fingerprint, and generator metadata;
- one `qn:EngineeringObject` node for every canonical engineering object;
- one `qn:Relation` node for every resolved canonical relation.

Object IRIs use `urn:quarto-needs:object:<percent-encoded-canonical-id>`. Relation IRIs are deterministic SHA-256-derived URNs over source ID, canonical relation name, target ID, and ordinal. The engineering-graph IRI is bound to the semantic graph fingerprint.

The projection preserves:

- canonical object ID and type;
- title, status, body, and rationale;
- authored attributes as JSON values using JSON-LD 1.1 `@json` typing;
- canonical relation name;
- authored relation name for provenance;
- semantic family;
- source and target roles;
- impact direction;
- explicit source and target object IRIs.

## CLI

The installed interchange adapter exposes JSON-LD directly:

```bash
quarto-needs --root . export --format jsonld
```

The default output is `.quarto-needs/graph.jsonld`. A custom destination is supported:

```bash
quarto-needs --root . export --format jsonld --output exchange/graph.jsonld
```

## Determinism and authority

The exporter consumes only `AnalysisSnapshot`. It does not parse source files, resolve aliases, infer relation families, recompute impact direction, or evaluate configuration independently. All semantic meaning is therefore inherited from the same Python core that drives Quarto, CLI validation, evidence, baseline/diff, impact, ReqIF, LSP, and editor tooling.

Output ordering is deterministic for equivalent snapshots, and the writer uses the repository's atomic text-write primitive.

## Acceptance gates before Phase 5.2 is complete

1. **implemented** — deterministic JSON-LD document and stable object/relation IRIs;
2. **implemented** — preservation of canonical relation semantics and authored attributes;
3. **implemented** — installed CLI integration through `export --format jsonld`;
4. **implemented** — regression tests for graph shape, attributes, relation endpoints, and byte determinism;
5. **pending** — validate expansion/compaction with an independent JSON-LD 1.1 processor;
6. **pending** — document the public vocabulary/namespace stability policy and versioning contract;
7. **pending** — add a semantic round-trip test proving that expanded RDF statements preserve the intended canonical object/relation identity.

No RDF-store, SPARQL, or remote-context dependency is introduced in this phase. Those may be evaluated later as consumers of the projection rather than semantic authorities inside Quarto-Needs.
