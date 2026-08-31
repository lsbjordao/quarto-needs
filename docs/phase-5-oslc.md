# Phase 5.3 — OSLC Requirements Management federation

Status: **read-only federation foundation implemented through deterministic cache persistence and bounded HTTP transport; local execution and RDF normalization/discovery orchestration remain pending**.

Quarto-Needs approaches OSLC Requirements Management as a federation boundary around the canonical engineering graph, not as a replacement authoring model and not as a second semantic authority.

The target standards are OSLC Requirements Management 2.1 and OSLC Core 3.0. The RM vocabulary namespace is `http://open-services.net/ns/rm#`. The implementation remains deliberately read-only so identity, projection, provenance, trust, cache, discovery, Resource Shapes, HTTP failure semantics, and authentication boundaries are fixed before remote synchronization is considered.

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

## Persistent deterministic cache

`src/quarto_needs/oslc_cache.py` implements the first persistent federation cache contract.

The cache is intentionally append-observational rather than mutable-current-state storage:

- the manifest schema is versioned as `oslc-cache-v1`;
- remote bytes are content-addressed under their SHA-256 digest;
- the manifest preserves distinct observations by `resourceUri + digest + fetchedAt`;
- observations are serialized deterministically by resource URI, retrieval time, then digest;
- re-storing the same observation is idempotent and byte-stable;
- a changed remote payload produces a new digest and a new historical observation instead of overwriting the old one;
- every cached blob is digest-validated before use;
- unknown manifest fields, duplicate observations, unsupported schemas, malformed identities, and corrupted blobs fail explicitly;
- rejected trust-state observations are never selected automatically.

The manifest stores only federation provenance and representation metadata. Request credentials and authorization headers have no persistence path.

## Service and Query Capability discovery

`discover_rm_services()` consumes an **already expanded JSON-LD** Service Provider representation. RDF expansion remains outside this pure function so transport/serialization concerns do not redefine discovery semantics.

The parser:

- ignores services whose `oslc:domain` is not the RM namespace;
- requires every discovered Query Capability to expose exactly one `oslc:queryBase`;
- accepts at most one `oslc:resourceShape` per Query Capability;
- retains advertised `oslc:resourceType` URIs;
- validates HTTP(S) query/service/shape URIs where the Core discovery contract requires dereferenceable resources;
- sorts services and query capabilities deterministically.

Keeping expanded RDF parsing separate allows JSON-LD, Turtle, or RDF/XML normalization to converge on one discovery contract.

## Resource Shape parsing

`src/quarto_needs/oslc_shape.py` implements a bounded parser for an already expanded OSLC Core 3.0 `ResourceShape`.

It preserves:

- shape URI;
- `oslc:describes` resource types;
- inline `oslc:property` constraints;
- required `oslc:name`, `oslc:occurs`, and `oslc:propertyDefinition` values;
- optional `oslc:valueType`, `oslc:range`, `oslc:readOnly`, `oslc:representation`, and `oslc:valueShape` values.

The occurrence contract is restricted to the four Core cardinalities: `Exactly-one`, `One-or-many`, `Zero-or-many`, and `Zero-or-one`. Invalid or structurally ambiguous shape data is rejected explicitly instead of guessed.

## Bounded read-only HTTP transport

`src/quarto_needs/oslc_http.py` implements the first live transport boundary. It is deliberately narrow:

- only HTTP `GET` is emitted;
- resource and Service Provider identifiers must be absolute HTTP(S) URIs;
- timeout, byte budget, and redirect count are explicit `HttpFetchPolicy` values;
- supported representation media types are bounded to JSON-LD/JSON, Turtle, and RDF/XML;
- declared `Content-Length` and streamed bytes are both checked against the configured byte budget;
- stale cached observations contribute `If-None-Match` and `If-Modified-Since` conditional headers;
- HTTP `304` refreshes the observation timestamp while retaining the validated cached bytes/digest;
- redirects are accepted only within the original origin (`scheme + host + port`) so authorization material cannot leak across hosts;
- authentication headers are request-only inputs and are never stored;
- `401/403`, unsupported media type, invalid response, timeout, unavailability, redirect violation, and oversized responses are distinct `OslcTransportError` categories;
- offline fallback is permitted only for genuine provider unavailability/timeout and only when the configured cache policy admits the stale representation;
- authentication failures are never hidden by stale-cache fallback.

A fresh cache hit avoids network I/O entirely.

## Next discovery orchestration slice

The next slice will connect the pieces in this order:

1. normalize supported RDF representations into expanded JSON-LD;
2. fetch a configured Service Provider or Service Provider Catalog through the bounded transport;
3. feed normalized data through the existing RM service discovery parser;
4. fetch advertised Resource Shapes through the same transport/cache budgets;
5. expose deterministic local discovery results before any remote requirement import is permitted;
6. add CLI configuration and explainable diagnostics around this orchestration.

Discovery will not recursively crawl arbitrary Linked Data graphs.

## Authentication boundary

Authentication is provider-specific and therefore not part of the canonical model. The federation layer accepts credentials/tokens only through the transport adapter boundary; secrets must never be written into `.quarto-needs.toml`, generated graph projections, evidence artifacts, logs, or cache metadata.

The live adapter remains read-only. No POST, PUT, PATCH, or DELETE will be implemented until identity conflict policy, optimistic-concurrency behavior, authorization failure semantics, and audit/provenance contracts are complete.

## Offline and stale-cache behavior

The cache contract is fail-explicit:

- a fresh cached representation may be used according to configured policy;
- an expired but available representation is usable only when stale data is explicitly permitted;
- absence of both a live response and an admissible cache is an explicit unavailable result;
- digest changes create a new observed representation rather than mutating historical provenance;
- rejected/untrusted content is never merged into the canonical engineering graph automatically;
- stale fallback does not mask authentication or policy failures.

## Failure model

The read-only transport and federation foundation now distinguish:

- authentication/authorization required;
- provider or resource unavailable;
- request timeout;
- unsupported media type;
- invalid response metadata;
- response exceeding configured byte budget;
- redirect count violation;
- redirect origin violation;
- malformed cache manifest or identity;
- corrupted cached bytes;
- stale cache without permission to use stale data;
- malformed or incompatible RM discovery data;
- unsupported/invalid Resource Shape.

RDF parsing/normalization failures and higher-level external identity conflicts will be added at the discovery orchestration boundary.

## Current acceptance status

1. **implemented** — official RM/Core namespace boundary and requirement class projection;
2. **implemented** — conservative mapping for implementation and validation relations;
3. **implemented** — unsupported relations preserved explicitly as Quarto-Needs extension metadata;
4. **implemented** — deterministic local/external resource identity rules;
5. **implemented** — external cache/provenance/trust record, SHA-256 digest helper, and deterministic freshness policy;
6. **implemented** — bounded RM Service/Query Capability discovery parser over expanded JSON-LD;
7. **implemented** — bounded Core ResourceShape parser;
8. **implemented** — regression tests for projection, relation mapping, unsupported mapping, URI encoding, provenance, freshness, discovery ordering/cardinality, and shape contracts;
9. **pending local execution** — execute the complete OSLC foundation/cache/transport test set in a real runner;
10. **implemented** — deterministic persistent cache manifest with content-addressed validated blobs and historical observations;
11. **implemented, pending execution gate** — first HTTP read-only transport with explicit auth/offline/redirect/media-type/size/failure contracts;
12. **pending** — RDF representation normalization plus live discovery/Resource Shape orchestration;
13. **pending** — CLI/configuration surface for configured OSLC federation;
14. **deferred** — remote writes or synchronization.

## Local foundation tests

```bash
pytest -q \
  tests/test_oslc_rm.py \
  tests/test_oslc_discovery.py \
  tests/test_oslc_shape.py \
  tests/test_oslc_cache.py \
  tests/test_oslc_http.py
```

The tests are network-free by design; HTTP behavior is exercised through deterministic fake openers/responses. In the current execution environment they remain **unexecuted** because the available GitHub Actions jobs terminate before repository checkout and this session cannot clone the private repository into a runnable container. The implementation status above therefore distinguishes committed regression coverage from a successful execution claim.
