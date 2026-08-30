# Phase 5.3 — OSLC Requirements Management federation

Status: **foundation implemented; live discovery/fetch adapters pending**.

Quarto-Needs approaches OSLC Requirements Management as a federation boundary around the canonical engineering graph, not as a replacement authoring model and not as a second semantic authority.

The target standards are OSLC Requirements Management 2.1 and OSLC Core 3.0. The RM vocabulary namespace is `http://open-services.net/ns/rm#`. The first implementation slice is deliberately read-only and network-free so identity, projection, provenance, trust, cache, and failure semantics are fixed before authentication or remote synchronization is introduced.

## Standards boundary

OSLC RM 2.1 defines `rm:Requirement` and `rm:RequirementCollection` as the root RM classes. Its relationship vocabulary includes `affectedBy`, `elaboratedBy`, `implementedBy`, `satisfiedBy`, `specifiedBy`, `trackedBy`, `uses`, and `validatedBy`.

OSLC RM service providers are discovered through OSLC Core concepts. An RM service uses the domain URI `http://open-services.net/ns/rm#`; implementations may advertise resource shapes and query capabilities through their service descriptions.

Quarto-Needs does **not** claim to be an OSLC RM server in Phase 5.3. Server conformance would require the complete mandatory HTTP/discovery/query behavior from the specifications and is outside this first federation slice.

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
- retrieval timestamp;
- trust state: `trusted`, `unverified`, `stale`, or `rejected`;
- optional HTTP `ETag`;
- optional `Last-Modified` value.

The digest identifies the bytes actually inspected, not merely the remote URI. URI and digest therefore remain distinct notions: the former is external identity; the latter is the observed representation/version.

## Planned discovery contract

The next slice will add read-only discovery in this order:

1. fetch a configured Service Provider or Service Provider Catalog URI;
2. select only services whose `oslc:domain` is the OSLC RM namespace;
3. discover Query Capabilities and Resource Shapes without executing arbitrary remote code or following unbounded links;
4. cache fetched representations together with digest, retrieval metadata, media type, ETag/Last-Modified, and trust state;
5. expose the discovered metadata as a bounded local projection before any remote requirement import is permitted.

Discovery will have explicit depth/size/time limits and will not recursively crawl arbitrary Linked Data graphs.

## Authentication boundary

Authentication is provider-specific and therefore not part of the canonical model. The federation layer will accept credentials/tokens only through an adapter boundary; secrets must never be written into `.quarto-needs.toml`, generated graph projections, evidence artifacts, logs, or cache metadata.

The first live adapter remains read-only. No POST, PUT, PATCH, or DELETE will be implemented until identity conflict policy, optimistic-concurrency behavior, authorization failure semantics, and audit/provenance contracts are complete.

## Offline and stale-cache behavior

The intended cache contract is fail-explicit:

- a fresh cached representation may be used according to configured policy;
- an expired but available representation is marked `stale`, never silently promoted to current;
- absence of both a live response and an admissible cache is an explicit unavailable result;
- digest changes create a new observed representation rather than mutating historical provenance;
- rejected/untrusted content is retained only when useful for diagnostics and is never merged into the canonical engineering graph automatically.

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
- remote resource changed during conditional retrieval.

These failures must be explainable diagnostics, not generic network exceptions leaking through the CLI.

## Current acceptance status

1. **implemented** — official RM/Core namespace boundary and requirement class projection;
2. **implemented** — conservative mapping for implementation and validation relations;
3. **implemented** — unsupported relations preserved explicitly as Quarto-Needs extension metadata;
4. **implemented** — deterministic local/external resource identity rules;
5. **implemented** — minimum external cache/provenance/trust record and SHA-256 digest helper;
6. **implemented** — regression tests for requirement filtering, relation mapping, unsupported mapping, URI encoding, and provenance records;
7. **pending** — bounded Service Provider discovery parser;
8. **pending** — Resource Shape and Query Capability discovery projection;
9. **pending** — deterministic cache manifest and freshness policy engine;
10. **pending** — first HTTP read-only transport with explicit auth/offline/failure contracts;
11. **deferred** — remote writes or synchronization.

## Local foundation test

```bash
pytest -q tests/test_oslc_rm.py
```

No network connection is required for the current foundation tests.
