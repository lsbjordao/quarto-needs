# OSLC external requirement observations

Quarto-Needs keeps OSLC query results and external requirement observations as distinct artifacts.

A query result proves that a Query Capability reported a member URI at a particular time. It does **not** prove that the query response bytes are the authoritative representation bytes for that member. For that reason, Quarto-Needs does not reuse the query-container digest as the digest of an individual requirement.

## Observation materialization boundary

`src/quarto_needs/oslc_observe.py` implements a bounded second step after query execution:

```text
OSLC Query Capability
        ↓
bounded query result
        ↓
member URI set
        ↓
explicit bounded GET per member
        ↓
RDF normalization
        ↓
resource identity check
        ↓
ExternalRequirementObservation
```

Each member fetch uses the existing read-only HTTP/cache boundary. The resulting `ExternalResourceIdentity` therefore records provenance for the bytes actually observed for that resource:

- external resource URI;
- Service Provider URI;
- SHA-256 content digest;
- fetch timestamp;
- trust state;
- optional `ETag`;
- optional `Last-Modified`.

Even when a query container carries an inline RDF node for a member, materialization performs the individual bounded retrieval before constructing the authoritative observation. Inline query content remains useful as a preview, not as a substitute for per-resource provenance.

## Extraction contract

The first observation slice extracts:

- `dcterms:title` — required, exactly one string literal;
- `dcterms:description` — optional, at most one string literal;
- `dcterms:identifier` — optional, at most one string literal.

All other expanded RDF properties are retained as external observation attributes rather than interpreted as canonical Quarto-Needs semantics.

The external identifier remains comparison data. It is never promoted automatically to a canonical Quarto-Needs ID.

## Bounded fan-out

Observation materialization is not a crawler. It enforces:

- an explicit maximum number of member fetches;
- the existing per-response byte/time/redirect budgets;
- an explicit per-member RDF node budget;
- same-origin redirect protection;
- network-free JSON-LD context normalization;
- no recursive dereferencing of relationships found inside the member resource.

The implementation is sequential in this first slice so an advertised member set cannot create implicit unbounded parallel fan-out.

## Stale cache semantics

A member satisfied from explicitly allowed stale cache is materialized with `trust_state="stale"`. Reconciliation already treats stale observations as blocking and requires refresh before a matched reconciliation result can be accepted.

## Relationship to reconciliation

`materialize_query_observations()` returns `oslc-observation-batch-v1`. Its observations are valid inputs to `reconcile_external_requirements()`.

The separation is intentional:

```text
query result
   ≠
resource observation
   ≠
identity binding
   ≠
canonical import
```

Quarto-Needs therefore has four independently reviewable boundaries before any future write to authored requirement files is considered.

## What remains deferred

Observation materialization does not:

- infer canonical identity;
- create local objects;
- update local objects;
- persist an import decision;
- POST, PUT, PATCH, or DELETE remote resources.

The next architectural artifact should be a reviewed import-plan format that consumes reconciled observations and describes proposed canonical changes without applying them automatically.
