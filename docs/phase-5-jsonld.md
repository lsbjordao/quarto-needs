# Phase 5.2 — JSON-LD projection

Status: **implemented and independently verified: `pytest -q tests/test_export_jsonld.py tests/test_interchange_cli.py` ran locally against a real installed PyLD and passed (10 passed).**

JSON-LD is a machine-readable semantic projection of the canonical Quarto-Needs engineering graph. It is not an alternate authoring model and does not introduce a second relation catalog, query engine, or rule engine.

## Current projection

`src/quarto_needs/exporters/jsonld_export.py` emits a deterministic JSON-LD 1.1 document with a single `@graph` containing:

- one `qn:EngineeringGraph` node with reference date, configuration fingerprint, semantic graph fingerprint, and generator metadata;
- one `qn:EngineeringObject` node for every canonical engineering object;
- one `qn:Relation` node for every resolved canonical relation.

Object IRIs use the versioned namespace `urn:quarto-needs:v1:object:<percent-encoded-canonical-id>`. Relation IRIs are deterministic SHA-256-derived URNs over source ID, canonical relation name, target ID, and ordinal. The engineering-graph IRI is bound to the semantic graph fingerprint.

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

## Public namespace and versioning policy

The JSON-LD vocabulary uses `urn:quarto-needs:v1:` rather than a dereferenceable Web URL. Quarto-Needs therefore does not create a runtime dependency on an external context server.

`v1` is the public semantic-major version of the vocabulary. Within `v1`, additive terms may be introduced provided existing term meanings, object identity rules, relation endpoint semantics, and datatype contracts remain compatible. A breaking semantic change requires a new namespace such as `urn:quarto-needs:v2:` and a corresponding increment of `quartoNeedsJsonLdVersion`.

The context is embedded in each projection. Remote context resolution is neither required nor used by the exporter or its tests.

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

## Independent processor and RDF contract

`PyLD` is a test-only dependency. The test suite now performs two independent semantic checks:

- `jsonld.expand()` must expand the embedded JSON-LD 1.1 context without remote resolution and preserve the canonical object IRIs and relation type;
- `jsonld.to_rdf(..., {"format": "application/n-quads"})` must preserve source and target object IRIs as RDF statements.

This is intentionally stronger than checking that the JSON document merely parses: the RDF projection must retain the engineering relationship endpoints produced by the canonical graph.

## Acceptance status

1. **implemented** — deterministic JSON-LD document and stable object/relation IRIs;
2. **implemented** — preservation of canonical relation semantics and authored attributes;
3. **implemented** — installed CLI integration through `export --format jsonld`;
4. **implemented** — regression tests for graph shape, attributes, relation endpoints, and byte determinism;
5. **implemented and verified locally** — expansion through independent JSON-LD 1.1 processor (`PyLD`);
6. **implemented and documented** — versioned public namespace and compatibility policy;
7. **implemented and verified locally** — RDF/N-Quads projection preserves canonical relation endpoints.

No RDF store, SPARQL engine, or remote-context dependency is introduced in this phase. Those may be evaluated later as consumers of the projection rather than semantic authorities inside Quarto-Needs.

## Local acceptance command

```bash
python -m pip install -e ".[test]"
pytest -q tests/test_export_jsonld.py tests/test_interchange_cli.py
```

Run locally: 10 passed, 0 skipped — `tests/test_export_jsonld.py` imports `pyld.jsonld` at module level with no skip guard, so a pass here is proof PyLD actually executed the expansion and RDF conversion, not that it was merely available. Phase 5.2 is complete independently of the still-broken repository runner infrastructure.
