# Phase 5.3 — OSLC Requirements Management federation

Status: **read-only federation, named project configuration, deterministic CLI discovery, bounded Service Provider Catalog inspection, bounded query execution, independent member observation, explicit non-mutating requirement reconciliation, and a deterministic, non-mutating import plan are all implemented and run locally end to end; POST/PUT/PATCH/DELETE and remote synchronization remain the only deliberately deferred slice.**

Quarto-Needs approaches OSLC Requirements Management as a federation boundary around the canonical engineering graph, not as a replacement authoring model and not as a second semantic authority.

The target standards are OSLC Requirements Management 2.1 and OSLC Core 3.0. The RM vocabulary namespace is `http://open-services.net/ns/rm#`. The implementation remains deliberately read-only so identity, projection, provenance, trust, cache, discovery, Resource Shapes, HTTP failure semantics, authentication, and reconciliation are explicit before any remote synchronization is considered.

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
- changed payloads create new observations instead of overwriting history;
- blobs are digest-validated before use;
- malformed manifests, duplicate observations, invalid identities, and corrupted blobs fail explicitly;
- rejected observations are not selected automatically;
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
- request-only authentication headers cannot override transport-owned headers;
- authentication, timeout, provider-unavailable, unsupported-media, malformed-metadata, oversized-response, and redirect violations remain distinct failures;
- stale-cache fallback is policy-controlled and never masks authentication failure.

A fresh cache hit avoids network I/O entirely.

## Network-free RDF normalization

`src/quarto_needs/oslc_rdf.py` normalizes supported representations into expanded JSON-LD:

- JSON-LD and JSON are expanded with PyLD;
- Turtle and RDF/XML are parsed through RDFLib and normalized through the same JSON-LD boundary;
- remote JSON-LD document/context loading is disabled;
- expanded-node counts are bounded;
- malformed RDF/JSON-LD and duplicate expanded node identities fail explicitly;
- RDF tooling stays in the optional `quarto-needs[oslc]` dependency set.

## RM discovery and Resource Shapes

`discover_rm_services()` remains a pure parser over expanded JSON-LD. It filters for the RM domain, validates Query Capability cardinality, preserves resource types, validates HTTP(S) discovery URIs, and sorts results deterministically.

`src/quarto_needs/oslc_federation.py` orchestrates the read-only path:

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

The configured Service Provider URI must exist in the normalized representation. A provider exposing no RM service fails explicitly. Advertised Resource Shapes must resolve to the advertised identity. Discovered resources remain external projections and are not merged into the canonical graph.

`src/quarto_needs/oslc_shape.py` preserves shape identity, described resource types, property definitions, occurrence cardinalities, value types/ranges, read-only state, representation, and nested value-shape links.

## Named project configuration

Named federation profiles now live inside the normal project configuration rather than in a second OSLC-specific TOML file:

```toml
[federation.oslc.profiles.production]
service-provider-uri = "https://provider.example/oslc/sp/requirements"
cache-dir = ".quarto-needs/oslc/production"
max-age-seconds = 3600
allow-stale = false
timeout-seconds = 10.0
max-bytes = 2000000
max-redirects = 3
max-nodes = 5000
fetch-shapes = true
bearer-token-env = "QUARTO_NEEDS_OSLC_PRODUCTION_TOKEN"
```

The profile stores only the **name** of the environment variable containing a token. Secret values are never valid configuration fields.

The federation section is recognized by `.quarto-needs.toml` but is intentionally excluded from the canonical engineering configuration document while federation remains read-only. Changing an endpoint or cache budget therefore does not silently change the local graph/configuration fingerprint. If a future import feature begins to affect canonical graph construction, that fingerprint boundary must be revisited explicitly.

The retired `.quarto-needs-oslc.toml` format fails with a migration message instead of being silently accepted as a second configuration authority.

See `docs/oslc-profiles.md`.

## Deterministic CLI surfaces

Installed CLI support includes:

```bash
quarto-needs oslc discover --profile production --format json
quarto-needs oslc discover https://provider.example/oslc/sp/requirements --format json
quarto-needs oslc catalog https://provider.example/oslc/catalog --format json
```

CLI values may override bounded profile values for one invocation. Direct URI and `--profile` are mutually exclusive.

Service Provider Catalog inspection is deliberately one-level and bounded. Nested catalog URIs may be reported but are not recursively crawled.

## Authentication boundary

Authentication remains provider-specific and outside the canonical model. Credentials/tokens are request-only adapter inputs and must never be written into `.quarto-needs.toml`, graph projections, evidence, logs, or cache metadata.

No POST, PUT, PATCH, or DELETE is permitted in this phase.

## Explicit reconciliation before import

`src/quarto_needs/oslc_reconcile.py` introduces the first external requirement reconciliation contract without mutating the canonical graph.

Its central rule is strict: **external URI identity is not inferred from display fields.** A matching `dcterms:identifier`, title, or description never creates an automatic merge. The sole identity bridge is an explicit `external URI → canonical ID` binding supplied to reconciliation.

`oslc-reconciliation-v1` reports deterministic statuses including:

- `matched` — an explicit binding resolves to an existing local object;
- `unbound` — no identity binding exists;
- `missing-local` — a binding targets a canonical ID that does not exist;
- `duplicate-local-binding` — multiple external URIs bind to one canonical object;
- `rejected-external` — the observation is explicitly rejected;
- `stale-external` — the external observation must be refreshed before reconciliation.

Differences in title/body/external identifier are reported for review and do not mutate either side. An explicit binding to a missing local object is **not** interpreted as permission to create it.

This establishes conflict and identity semantics before any import command exists. See `docs/oslc-reconciliation.md`.

## Self-hosted engineering slice

The official self-hosted example models both discovery and reconciliation in English and Brazilian Portuguese:

```text
STK-006
   ↓
SYS-007
   ├── FUN-010 / NFR-006 → ADR-008 → SRC-OSLC-RM / CACHE / HTTP / RDF / FEDERATION → TC-015 → EVD-015
   ├── FUN-012 / NFR-006 → ADR-008 → SRC-OSLC-QUERY                                → TC-017 → EVD-017
   ├── FUN-013 / NFR-006 → ADR-008 → SRC-OSLC-OBSERVE                              → TC-018 → EVD-018
   ├── FUN-011 / NFR-006 → ADR-009 → SRC-OSLC-RECONCILE                           → TC-016 → EVD-016
   └── FUN-011 / FUN-013 / NFR-006 → ADR-008 → SRC-OSLC-IMPORT                     → TC-019 → EVD-019
```

`TC-015` exercises deterministic federation discovery and Resource Shape orchestration. `TC-016` exercises explicit identity reconciliation and prevents identifier/title matching from becoming an implicit merge rule. `TC-017` exercises bounded query execution and response provenance. `TC-018` exercises independent per-member observation provenance. `TC-019` exercises the reviewed, non-mutating import-plan directive boundary built from that observation and reconciliation. All five participate in `make evidence-self-example` (eleven attested tests in total, including the non-OSLC self-hosted slices).

## Failure model

The current phase distinguishes authentication/authorization failure, provider unavailability, timeout, unsupported media type, invalid response metadata, byte-budget violation, redirect-count/origin violation, malformed cache state, corrupted cached bytes, stale cache rejected by policy, malformed RDF/JSON-LD, missing configured Service Provider identity, incompatible/non-RM discovery data, invalid Resource Shapes, stale/rejected external observations, missing explicit bindings, duplicate bindings, and bindings to absent local objects.

## Current acceptance status

1. **implemented** — official RM/Core namespace boundary and deterministic requirement projection;
2. **implemented** — conservative relation mapping and explicit unsupported-relation preservation;
3. **implemented** — external identity, provenance, trust, digest, and freshness contracts;
4. **implemented** — deterministic persistent cache with content-addressed validated blobs and historical observations;
5. **implemented** — bounded GET-only HTTP transport;
6. **implemented** — network-free JSON-LD/Turtle/RDFXML normalization;
7. **implemented** — bounded RM Service/Query Capability parser;
8. **implemented** — bounded Core Resource Shape parser;
9. **implemented** — Service Provider → RM discovery → Resource Shape orchestration;
10. **implemented** — `.quarto-needs.toml` named OSLC federation profiles with environment-variable-only secret binding, centrally validated by `load_config()`;
11. **implemented** — deterministic `oslc discover` CLI for direct URI or named profile;
12. **implemented** — bounded one-level `oslc catalog` inspection without recursive crawling;
13. **implemented** — explicit non-mutating external requirement reconciliation contract (`oslc-reconciliation-v1`);
14. **implemented** — self-hosted discovery, query, observation, reconciliation, and import-plan requirements/ADRs/source/test/evidence traceability through `TC-019`/`EVD-019`;
15. **implemented** — the complete OSLC regression/evidence set runs locally end to end (`make evidence-self-example`, eleven attested tests);
16. **implemented** — provider query execution and normalized requirement observation extraction through discovered Query Capabilities (`SRC-OSLC-QUERY`, `SRC-OSLC-OBSERVE`);
17. **implemented** — reviewed, non-mutating import plan (`oslc-import-plan-v1`, `SRC-OSLC-IMPORT`) with explicit create/update/ignore/review directives;
18. **deferred** — POST/PUT/PATCH/DELETE and remote synchronization.

## Regression set

```bash
pytest -q \
  tests/test_oslc_rm.py \
  tests/test_oslc_discovery.py \
  tests/test_oslc_shape.py \
  tests/test_oslc_cache.py \
  tests/test_oslc_http.py \
  tests/test_oslc_rdf.py \
  tests/test_oslc_federation.py \
  tests/test_oslc_profiles.py \
  tests/test_oslc_cli.py \
  tests/test_oslc_catalog.py \
  tests/test_oslc_query.py \
  tests/test_oslc_query_cli.py \
  tests/test_oslc_observe.py \
  tests/test_oslc_reconcile.py \
  tests/test_oslc_import_plan.py
```

The suite is network-free by design where provider behavior is simulated. The repository must not represent committed regression coverage as successful execution evidence until the tests are actually executed. The self-hosted executable-evidence gate is:

```bash
make evidence-self-example
```
