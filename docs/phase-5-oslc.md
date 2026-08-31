# Phase 5.3 — OSLC Requirements Management federation

Status: **read-only federation foundation implemented through deterministic cache persistence, bounded HTTP transport, network-free RDF normalization, RM discovery, and Resource Shape orchestration; executable validation and user-facing CLI/configuration remain pending**.

Quarto-Needs approaches OSLC Requirements Management as a federation boundary around the canonical engineering graph, not as a replacement authoring model and not as a second semantic authority.

The target standards are OSLC Requirements Management 2.1 and OSLC Core 3.0. The RM vocabulary namespace is `http://open-services.net/ns/rm#`. The implementation remains deliberately read-only so identity, projection, provenance, trust, cache, discovery, Resource Shapes, HTTP failure semantics, and authentication boundaries are fixed before remote synchronization is considered.

## Standards boundary

OSLC RM 2.1 defines `rm:Requirement` and `rm:RequirementCollection` as the root RM classes. Its relationship vocabulary includes `affectedBy`, `elaboratedBy`, `implementedBy`, `satisfiedBy`, `specifiedBy`, `trackedBy`, `uses`, and `validatedBy`.

OSLC RM service providers are discovered through OSLC Core concepts. An RM service uses the domain URI `http://open-services.net/ns/rm#`; Query Capabilities expose an `oslc:queryBase` and may reference an `oslc:resourceShape`.

Quarto-Needs does **not** claim to be an OSLC RM server in Phase 5.3. Server conformance would require the complete mandatory HTTP/discovery/query behavior from the specifications and is outside this federation slice.

## Canonical-to-OSLC requirement projection

`src/quarto_needs/oslc_rm.py` provides a deterministic read-only projection from `AnalysisSnapshot`.

Only Quarto-Needs types named `requirement` or ending in `-requirement` are projected as `rm:Requirement`. Other engineering objects remain valid link targets but are not misclassified as requirements.

Projected requirements preserve canonical ID, title, body, Service Provider URI, original Quarto-Needs type/status/rationale/attributes, and the semantic graph fingerprint. Canonical IDs are percent-encoded into stable resource paths.

## Conservative relation mapping

OSLC terms are emitted only where the canonical Quarto-Needs meaning has a safe correspondence:

| Quarto-Needs canonical relation | OSLC RM property |
| --- | --- |
| `implemented-by` | `rm:implementedBy` |
| `verified-by` | `rm:validatedBy` |
| `validated-by` | `rm:validatedBy` |

Unsupported relations are retained in Quarto-Needs extension metadata rather than guessed into superficially similar OSLC terms.

## External identity and cache provenance

`ExternalResourceIdentity` records the external resource URI, Service Provider URI, SHA-256 digest of the bytes actually observed, timezone-aware retrieval time, trust state, optional `ETag`, and optional `Last-Modified` value.

`CachePolicy` evaluates freshness against an explicit `now`. It returns `fresh`, `stale-allowed`, or `stale-rejected`; stale content is never silently upgraded to current data.

## Persistent deterministic cache

`src/quarto_needs/oslc_cache.py` implements `oslc-cache-v1`:

- remote bytes are content-addressed under SHA-256;
- distinct observations are preserved by `resourceUri + digest + fetchedAt`;
- manifest serialization is deterministic by resource URI, retrieval time, and digest;
- re-storing the same observation is idempotent and byte-stable;
- a changed payload produces a new observation instead of overwriting history;
- blobs are digest-validated before use;
- unknown fields/schemas, duplicate observations, malformed identities, and corrupted blobs fail explicitly;
- rejected trust-state observations are not selected automatically;
- request credentials have no persistence path.

## Bounded read-only HTTP transport

`src/quarto_needs/oslc_http.py` provides the live transport boundary:

- HTTP `GET` only;
- absolute HTTP(S) identifiers;
- explicit timeout, byte, and redirect budgets;
- bounded media types: JSON-LD/JSON, Turtle, and RDF/XML;
- `Content-Length` and streamed payload size validation;
- conditional retrieval with `If-None-Match` / `If-Modified-Since`;
- deterministic `304 Not Modified` refresh over previously validated bytes;
- same-origin redirects only, with default ports normalized (`http:80`, `https:443`);
- request-only authentication headers cannot override transport-owned `Accept`, `User-Agent`, or conditional headers;
- `401/403`, timeout, provider unavailability, unsupported media type, malformed response metadata, oversized responses, and redirect violations have distinct error codes;
- offline fallback occurs only for genuine unavailability/timeout and only when cache policy explicitly admits the stale representation;
- authentication failures are never hidden by stale-cache fallback.

A fresh cache hit avoids network I/O entirely.

## Network-free RDF normalization

`src/quarto_needs/oslc_rdf.py` normalizes supported representations into expanded JSON-LD:

- JSON-LD and JSON are expanded with PyLD;
- Turtle and RDF/XML are parsed through RDFLib and then expanded through the same JSON-LD boundary;
- remote JSON-LD document/context loading is disabled, so parsing cannot create hidden network traffic;
- expanded-node counts are bounded;
- malformed RDF/JSON-LD and duplicate expanded node identities fail explicitly;
- RDF tooling is exposed through the optional `quarto-needs[oslc]` dependency set rather than inflating the minimal runtime core.

## RM Service and Query Capability discovery

`discover_rm_services()` remains a pure parser over expanded JSON-LD. It filters for the RM domain, validates Query Capability cardinality, preserves resource types, validates HTTP(S) discovery URIs, and sorts results deterministically.

`src/quarto_needs/oslc_federation.py` now orchestrates the full read-only path for a configured Service Provider:

```text
bounded GET/cache
      ↓
RDF → expanded JSON-LD
      ↓
materialize referenced service/query nodes
      ↓
RM Service + Query Capability discovery
      ↓
fetch advertised Resource Shapes
      ↓
normalize/materialize/parse shapes
      ↓
deterministic discovery result
```

The configured Service Provider URI must exist in the normalized representation. A provider exposing no RM service fails explicitly. Advertised Resource Shapes must resolve to the advertised identity. Discovered resources remain external projections; they are **not** merged into the canonical engineering graph.

## Resource Shape parsing

`src/quarto_needs/oslc_shape.py` preserves shape identity, described resource types, property definitions, occurrence cardinalities, value types/ranges, read-only state, representation, and nested value-shape links. The occurrence contract is bounded to the four OSLC Core cardinalities and ambiguous shape data is rejected rather than guessed.

## Authentication boundary

Authentication remains provider-specific and outside the canonical model. Credentials/tokens are request-only adapter inputs and must never be written into `.quarto-needs.toml`, graph projections, evidence, logs, or cache metadata.

No POST, PUT, PATCH, or DELETE will be implemented until identity conflict policy, optimistic concurrency, authorization failure behavior, and audit/provenance contracts are explicit.

## Self-hosted engineering slice

The official self-hosted example now models Phase 5.3 end to end in English and Brazilian Portuguese:

```text
STK-006
   ↓
SYS-007
   ↓
FUN-010 / NFR-006
   ↓
ADR-008
   ↓
COMP-OSLC / IF-005
   ↓
SRC-OSLC-RM / CACHE / HTTP / RDF / FEDERATION
   ↓
TC-015
   ↓
EVD-015
```

`TC-015` is reciprocally bound to `tests/test_oslc_federation.py::test_discovery_orchestrates_fetch_normalization_service_and_shape_parsing` and therefore participates in the same executable-evidence model used by other self-hosted capabilities.

## Failure model

The current foundation distinguishes at least authentication/authorization failure, provider unavailability, timeout, unsupported media type, invalid response metadata, byte-budget violation, redirect-count/origin violation, malformed cache state, corrupted cached bytes, stale cache rejected by policy, malformed RDF/JSON-LD, missing configured Service Provider identity, incompatible/non-RM discovery data, and invalid Resource Shapes.

External requirement identity collision/reconciliation belongs to the later import boundary and is not silently approximated here.

## Current acceptance status

1. **implemented** — official RM/Core namespace boundary and requirement projection;
2. **implemented** — conservative relation mapping and explicit unsupported-relation preservation;
3. **implemented** — external identity, provenance, trust, digest, and freshness contracts;
4. **implemented** — deterministic persistent cache with content-addressed validated blobs and historical observations;
5. **implemented, pending execution gate** — bounded GET-only HTTP transport with conditional retrieval, same-origin redirect security, auth/offline/media/size/failure contracts;
6. **implemented, pending execution gate** — JSON-LD/Turtle/RDFXML normalization with no implicit network dereferencing;
7. **implemented** — bounded RM Service/Query Capability parser;
8. **implemented** — bounded Core Resource Shape parser;
9. **implemented, pending execution gate** — read-only Service Provider → RM discovery → Resource Shape orchestration;
10. **implemented** — self-hosted requirements/ADR/component/source/test/evidence traceability for the OSLC slice;
11. **pending local execution** — run the complete OSLC regression set in a working environment;
12. **pending** — user-facing named federation configuration and deterministic CLI discovery report;
13. **candidate next** — bounded Service Provider Catalog selection where required by real providers;
14. **deferred** — external requirement import/conflict/reconciliation;
15. **deferred** — remote writes or synchronization.

## Regression set

```bash
pytest -q \
  tests/test_oslc_rm.py \
  tests/test_oslc_discovery.py \
  tests/test_oslc_shape.py \
  tests/test_oslc_cache.py \
  tests/test_oslc_http.py \
  tests/test_oslc_rdf.py \
  tests/test_oslc_federation.py
```

The suite is network-free by design: HTTP behavior is exercised through deterministic fake openers/responses. In the current execution environment it remains **unexecuted** because GitHub Actions jobs terminate before repository checkout and this session cannot run the private repository in a local clone. Committed regression coverage is therefore not represented as successful execution evidence.
