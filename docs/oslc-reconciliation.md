# OSLC requirement reconciliation

OSLC federation introduces remote identities into the trust boundary, but Quarto-Needs does not treat discovery as permission to merge remote requirements into the canonical engineering graph.

`src/quarto_needs/oslc_reconcile.py` defines the first explicit reconciliation contract. It is intentionally a **pure analysis layer**: it compares external observations with a local `AnalysisSnapshot`, produces `oslc-reconciliation-v1`, and mutates neither side.

## Identity rule

An external OSLC requirement is identified primarily by its absolute resource URI. A canonical Quarto-Needs object is identified by its authored canonical ID.

The only bridge between those identity domains is an explicit mapping:

```text
external resource URI  →  canonical Quarto-Needs ID
```

A matching `dcterms:identifier`, title, description, or other display field is never enough to create identity automatically.

This avoids accidental aliases when different providers reuse identifiers such as `REQ-1`, when a provider changes display text, or when imported data happens to resemble an existing local object.

## Inputs

Each `ExternalRequirementObservation` carries:

- `ExternalResourceIdentity`:
  - resource URI;
  - Service Provider URI;
  - SHA-256 digest of the observed representation;
  - retrieval timestamp;
  - trust state;
  - optional `ETag` and `Last-Modified`;
- title;
- description;
- optional external identifier;
- deterministic JSON-compatible external attributes.

Observations remain external data. Creating one does not create an engineering object in the canonical graph.

## Reconciliation states

`reconcile_external_requirements()` emits one deterministic item per observed resource:

| Status | Meaning |
| --- | --- |
| `matched` | An explicit binding resolves to an existing local object; differences are informational |
| `unbound` | No explicit URI→canonical-ID binding exists |
| `missing-local` | The explicit binding targets a canonical ID absent from the snapshot |
| `duplicate-local-binding` | Multiple external URIs are bound to the same canonical object |
| `stale-external` | The observed external representation is stale and must be refreshed |
| `rejected-external` | The observed representation is explicitly rejected and cannot be reconciled |

`unbound` is not treated as a conflict because discovery of a new external resource is not itself an error. It is also **not** treated as an instruction to create an object. Creation/import policy remains separate.

The remaining exceptional states set `hasConflicts=true`.

## Differences are not writes

For an explicitly matched item, the current contract compares:

- title;
- body/description;
- external identifier versus canonical ID.

Differences are reported as local/external pairs. They do not select a winner and do not update the snapshot.

Example projection:

```json
{
  "schema": "oslc-reconciliation-v1",
  "hasConflicts": false,
  "unboundCount": 0,
  "items": [
    {
      "externalUri": "https://provider.example/oslc/rm/requirements/7",
      "status": "matched",
      "canonicalId": "SYS-007",
      "externalIdentifier": "REMOTE-7",
      "differences": {
        "identifier": {
          "local": "SYS-007",
          "external": "REMOTE-7"
        }
      },
      "message": "explicit binding resolved; differences are informational only"
    }
  ]
}
```

## Security and provenance invariants

Reconciliation must not weaken the earlier federation boundary:

1. rejected observations never reconcile;
2. stale observations must be refreshed before reconciliation;
3. bindings cannot reference external URIs absent from the observed set;
4. multiple observed resources cannot silently collapse onto one canonical ID;
5. matching display metadata never creates identity;
6. reconciliation never mutates the canonical graph;
7. reconciliation never performs network activity;
8. reconciliation does not authorize import or remote writes.

## What remains deliberately absent

There is still no canonical import/synchronization command. Before one can exist, Quarto-Needs needs an explicit policy for at least:

- how an unbound external resource becomes a new authored object, if ever;
- where persistent URI→canonical-ID bindings live and how they are reviewed;
- conflict resolution when both local and external state changed;
- typed attribute mapping and loss semantics;
- relation mapping and unresolved external targets;
- provenance retained on imported objects;
- idempotency and replay behavior;
- deletion/tombstone semantics;
- optimistic concurrency for any future remote write;
- authorization and audit trails.

POST/PUT/PATCH/DELETE remain out of scope until those contracts are explicit and independently tested.

## Self-hosted traceability

The project models this boundary in `examples/quarto-needs/interoperability.qmd`:

```text
SYS-007
   ↓
FUN-011 / NFR-006
   ↓
ADR-009
   ↓
COMP-OSLC
   ↓
SRC-OSLC-RECONCILE
   ↓
TC-016
   ↓
EVD-016
```

`TC-016` is reciprocally bound to `tests/test_oslc_reconcile.py::test_matching_external_identifier_never_creates_implicit_identity` and participates in the same executable-evidence contract as the discovery regression.
