# Reviewed OSLC import plans

`oslc-import-plan-v1` is the review boundary between read-only OSLC federation and any future mutation of authored Quarto-Needs source files.

It is intentionally **not an importer**. Building a plan does not write `.qmd`/`.md` files, mutate an `AnalysisSnapshot`, create canonical objects, or update external OSLC resources.

## Why a separate plan exists

Federation now has four distinct semantic stages:

```text
OSLC discovery
    ↓
query result
    ↓
independent member observations
    ↓
explicit identity reconciliation
    ↓
reviewed import plan
    ↓
future apply step (not implemented)
```

Keeping these stages separate prevents a network response from silently becoming authored project truth.

A query result answers which external resources were advertised. A member observation records what bytes were actually observed for one external resource. Reconciliation answers whether an explicit external-URI → canonical-ID identity bridge exists and whether trust/conflict state permits comparison. The import plan records a reviewer's explicit intent about what a future source-file edit would be allowed to propose.

## Core rule: reconciliation does not imply mutation

The following transitions are deliberately forbidden:

- `unbound` does not mean `create`;
- `matched` does not mean `update`;
- matching `dcterms:identifier`, title, or description does not authorize identity or mutation;
- `missing-local` does not authorize creation of the missing ID;
- stale or rejected observations cannot be promoted by an import directive;
- duplicate identity bindings remain blocking conflicts.

A resource without an explicit import directive is reported as `review-required`.

## Explicit directives

A reviewer may provide one directive per observed external URI.

### Ignore

`ignore` records an explicit decision that the observation should not participate in a future apply step. It carries no target metadata.

### Update

`update` is accepted only when reconciliation already produced `matched` through an explicit URI-to-canonical-ID binding.

The canonical ID, type, and status come from the matched local object; they cannot be overridden by the directive. The reviewer must supply a normalized project-relative authored `.qmd` or `.md` target path.

The current plan only proposes changes to presentation-bearing requirement fields that have a conservative mapping:

- `title`;
- `body` / external `dcterms:description`.

External identifiers are comparison/provenance data and are not proposed as canonical ID changes.

### Create

`create` is accepted only when reconciliation reports `unbound` and the reviewer explicitly supplies:

- a new canonical ID;
- canonical type;
- canonical status;
- target authored `.qmd` or `.md` file.

The proposed ID must not already exist in the canonical snapshot. No value is inferred from `dcterms:identifier`.

The plan records the proposed initial `id`, `type`, `status`, `title`, and `body` values, but it still writes nothing.

## Authored-file placement

Every mutating directive must identify a project-relative target source file. Paths are rejected when they:

- are absolute;
- contain `..` traversal;
- use a leading `./` non-normalized form;
- do not end in `.qmd` or `.md`.

This makes source placement a reviewed part of the import contract rather than an implementation guess.

## Provenance binding

Every plan item carries the external observation's:

- resource URI;
- content digest;
- retrieval timestamp.

The whole plan also carries the current canonical semantic graph fingerprint.

A future apply command should require those values to still match before editing authored files. If either the remote observation or local semantic graph changed after review, the plan should be considered stale and rebuilt rather than applied optimistically.

## Dispositions

`oslc-import-plan-v1` uses explicit dispositions:

- `review-required` — no reviewer directive exists;
- `ignored` — reviewer explicitly declined import;
- `ready-create` — an explicit create directive is structurally admissible;
- `ready-update` — an explicit update directive is structurally admissible and has changes;
- `no-change` — an explicit update directive resolves to an already-equal title/body;
- `blocked` — reconciliation/trust/identity constraints prohibit the requested action.

`ready-*` means ready for a **future separately designed apply step**, not already applied.

## Deterministic machine artifact

Example shape:

```json
{
  "schema": "oslc-import-plan-v1",
  "semanticGraphFingerprint": "...",
  "hasBlocked": false,
  "requiresReview": false,
  "readyCount": 1,
  "items": [
    {
      "externalUri": "https://provider.example/oslc/rm/requirements/7",
      "disposition": "ready-update",
      "canonicalId": "SYS-007",
      "canonicalType": "system-requirement",
      "canonicalStatus": "approved",
      "targetPath": "requirements/system.qmd",
      "sourceDigest": "sha256:...",
      "fetchedAt": "2026-08-30T21:10:00Z",
      "changes": {
        "title": {
          "from": "Old title",
          "to": "Remote title"
        }
      },
      "message": "explicit reviewer directive is ready for a future apply step"
    }
  ]
}
```

Items are sorted by external resource URI. The artifact is intended to be reviewable, diffable, cacheable, and suitable as an auditable input to a future apply operation.

## Deferred apply semantics

No apply command exists yet. Before one is introduced, Quarto-Needs still needs explicit contracts for:

1. plan staleness checks against semantic graph fingerprint and external digests;
2. exact `.need` insertion/update mechanics;
3. preservation of unrelated authored formatting and prose;
4. relation handling and unsupported external RDF properties;
5. atomic writes and rollback behavior;
6. post-write re-analysis and validation;
7. reviewer/audit metadata;
8. conflict behavior when a target file changed after planning.

Remote OSLC POST/PUT/PATCH/DELETE remains outside this path and remains deferred.
