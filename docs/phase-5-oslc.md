# Phase 5.3 — OSLC Requirements Management federation

Status: **network-free federation contracts implemented; local validation and live HTTP adapter pending**.

Quarto-Needs approaches OSLC Requirements Management as a federation boundary around the canonical engineering graph, not as a replacement authoring model and not as a second semantic authority.

The target standards are OSLC Requirements Management 2.1 and OSLC Core 3.0. The RM vocabulary namespace is `http://open-services.net/ns/rm#`. The first implementation slice is deliberately read-only and network-free so identity, projection, provenance, trust, cache, discovery, Resource Shapes, and failure semantics are fixed before authentication or remote synchronization is introduced.

## Standards boundary

OSLC RM 2.1 defines `rm:Requirement` and `rm:RequirementCollection` as the root RM classes. Its relationship vocabulary includes `affectedBy`, `elaboratedBy`, `implementedBy`, `satisfiedBy`, `specifiedBy`, `trackedBy`, `uses`, and `validatedBy`.

OSLC RM service providers are discovered through OSLC Core concepts. An RM service uses the domain URI `http://open-services.net/ns/rm#`; Query Capabilities expose an `oslc:queryBase` and may reference an `oslc:resourceShape`.

Quarto-Needs does **not** claim to be an OSLC RM server in Phase 5.3. Server conformance would require the complete mandatory HTTP/discovery/query behavior from the specifications and is outside this federation slice.

## Canonical-to-OSLC requirement projection

`src/quarto_needs/oslc_rm.py` provides a deterministic read-only projection from `AnalysisSnapshot`.

Only Quarto-Needs types named `requirement` or ending in `-requirement` are projected as `rm:Requirement`. Other engineering objects remain valid link targets but are not misclassified as requirements.

Projected requirements preserve:

- canonical ID as `dcterms:identifier` and Quarto-Needs extension metadata;
- title as `dcterms:title`;
- body as `dcterms:description`;
- `oslc:serviceProvider` URI;
- original Quarto-Needs type, status, rationale, authored attributes, and semantic graph fingerprint in the versioned Quarto-Needs OSLC extension namespace.

The projection uses caller-supplied HTTP(S) base and Service Provider URIs. Canonical IDs are percent-encoded into stable resource paths.

## Conservative relation mapping

OSLC terms are emitted only where the canonical Quarto-Needs meaning has a safe correspondence:

| Quarto-Needs canonical relation | OSLC RM property |
| --- | --- |
| `implemented-by` | `rm:implementedBy` |
| `verified-by` | `rm:validatedBy` |
| `validated-by` | `rm:validatedBy` |

No other relation is promoted merely because its English label looks similar. All outgoing relations remain available in Quarto-Needs extension metadata with canonical name, authored name, semantic family, and target URI. This makes unsupported mapping explicit rather than silently lossy.

## External identity and cache provenance

`ExternalResourceIdentity` establishes the minimum metadata required before a fetched OSLC resource can participate in federation:

- absolute HTTP(S) resource URI;
- absolute HTTP(S) Service Provider URI;
- SHA-256 content digest;
- timezone-aware retrieval timestamp;
- trust state: `trusted`, `unverified`, `stale`, or `rejected`;
- optional HTTP `ETag`;
- optional `Last-Modified` value.

The digest identifies the bytes actually inspected, not merely the remote URI. URI and digest therefore remain distinct notions: the former is external identity; the latter is the observed representation/version.

`CachePolicy` evaluates cache freshness deterministically against an explicit `now` instant. It returns one of `fresh`, `stale-allowed`, or `stale-rejected`; it never silently upgrades stale content to current data. Naive timestamps and backwards time are rejected.

## Service and Query Capability discovery

`discover_rm_services()` consumes an **already expanded JSON-LD** Service Provider representation. Expansion and HTTP transport deliberately remain outside this pure function.

The parser:

- ignores services whose `oslc:domain` is not the RM namespace;
- requires every discovered Query Capability to expose exactly one `oslc:queryBase`;
- accepts at most one `oslc:resourceShape` per Query Capability;
- retains advertised `oslc:resourceType` URIs;
- validates HTTP(S) query/service/shape URIs where the Core discovery contract requires dereferenceable resources;
- sorts services and query capabilities deterministically.

Keeping expanded RDF parsing separate means a later transport can support JSON-LD, Turtle, or RDF/XML without changing the semantic discovery contract.

## Resource Shape parsing

`src/quarto_needs/oslc_shape.py` implements a bounded parser for an already expanded OSLC Core 3.0 `ResourceShape`.

It preserves:

- shape URI;
- `oslc:describes` resource types;
- inline `oslc:property` constraints;
- required `oslc:name`, `oslc:occurs`, and `oslc:propertyDefinition` values;
- optional `oslc:valueType`, `oslc:range`, `oslc:readOnly`, `oslc:representation`, and `oslc:valueShape` values.

The occurrence contract is restricted to the four Core cardinalities: `Exactly-one`, `One-or-many`, `Zero-or-many`, and `Zero-or-one`. Invalid or structurally ambiguous shape data is rejected explicitly instead of guessed.

## Planned live discovery contract

The next slice will add read-only I/O in this order:

1. fetch a configured Service Provider or Service Provider Catalog URI with strict byte/time/redirect/media-type limits;
2. normalize supported RDF representations into expanded JSON-LD;
3. feed the normalized representation through the already-tested RM service discovery parser;
4. fetch advertised Resource Shapes subject to the same budgets and cache policy;
5. persist deterministic cache metadata and content digests;
6. expose discovery results locally before any remote requirement import is permitted.

Discovery will not recursively crawl arbitrary Linked Data graphs.

## Authentication boundary

Authentication is provider-specific and therefore not part of the canonical model. The federation layer will accept credentials/tokens only through an adapter boundary; secrets must never be written into `.quarto-needs.toml`, generated graph projections, evidence artifacts, logs, or cache metadata.

The first live adapter remains read-only. No POST, PUT, PATCH, or DELETE will be implemented until identity conflict policy, optimistic-concurrency behavior, authorization failure semantics, and audit/provenance contracts are complete.

## Offline and stale-cache behavior

The cache contract is fail-explicit:

- a fresh cached representation may be used according to configured policy;
- an expired but available representation is marked stale and is usable only when stale data is explicitly permitted;
- absence of both a live response and an admissible cache is an explicit unavailable result;
- digest changes create a new observed representation rather than mutating historical provenance;
- rejected/untrusted content is never merged into the canonical engineering graph automatically.

## Failure model

The live adapter will distinguish at least:

- authentication/authorization required;
- provider or resource unavailable;
- unsupported media type;
- malformed RDF/JSON-LD/Turtle representation;
- missing or incompatible RM service/domain declaration;
- unsupported/invalid Resource Shape;
- external identity collision;
- stale cache without permission to use stale data;
- response exceeding configured byte/resource/link budgets;
- redirect policy violation;
- remote resource changed during conditional retrieval.

These failures must be explainable diagnostics, not generic network exceptions leaking through the CLI.

## Current acceptance status

1. **implemented** — official RM/Core namespace boundary and requirement class projection;
2. **implemented** — conservative mapping for implementation and validation relations;
3. **implemented** — unsupported relations preserved explicitly as Quarto-Needs extension metadata;
4. **implemented** — deterministic local/external resource identity rules;
5. **implemented** — external cache/provenance/trust record, SHA-256 digest helper, and deterministic freshness policy;
6. **implemented** — bounded RM Service/Query Capability discovery parser over expanded JSON-LD;
7. **implemented** — bounded Core ResourceShape parser;
8. **implemented** — regression tests for projection, relation mapping, unsupported mapping, URI encoding, provenance, freshness, discovery ordering/cardinality, and shape contracts;
9. **pending local execution** — execute the complete OSLC foundation test set;
10. **pending** — deterministic persistent cache manifest;
11. **pending** — first HTTP read-only transport with explicit auth/offline/redirect/media-type/size/failure contracts;
12. **deferred** — remote writes or synchronization.

## Local foundation tests

```bash
pytest -q tests/test_oslc_rm.py tests/test_oslc_discovery.py tests/test_oslc_shape.py
```

No network connection is required for the current foundation tests.
