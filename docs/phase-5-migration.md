# Phase 5.4 — Migration adapters

Status: **the first Sphinx-Needs migration adapter is implemented as a deterministic, plan-only workflow; automatic authored-file mutation remains deliberately deferred.**

Quarto-Needs treats migration as a reviewed interoperability operation, not as a parser shortcut. A migration source may have its own type system, relation semantics, computed fields, conditional links, backlinks, dynamic functions, rendering behavior, and identity conventions. Those concepts must not be silently reinterpreted as canonical Quarto-Needs semantics.

Sphinx-Needs is one of the inspirations for Quarto-Needs and is also the first migration source supported by this phase.

## Architectural rule

Migration follows the same authority boundary as the rest of Quarto-Needs:

```text
external source artifact
        ↓
source-specific parser
        ↓
explicit semantic mappings
        ↓
reviewable migration plan
        ↓
future apply contract
        ✕ not implemented yet
```

The migration plan is analysis output. It does not become a second semantic model and it does not write authored `.qmd` or `.md` files.

## Sphinx-Needs source boundary

The first adapter consumes a Sphinx-Needs `needs.json` document and supports the versioned wire shape used by exported Sphinx-Needs data:

- a non-empty `versions` object is required;
- `current_version` is preferred when valid;
- a single available version may be selected implicitly;
- ambiguous multi-version input requires explicit `--version` selection;
- needs may be represented as an object keyed by need ID or as an array;
- object-keyed IDs are recovered from the dictionary key when the embedded `id` is absent;
- duplicate need IDs fail closed.

The adapter deliberately reads the exported data model rather than attempting to execute a Sphinx project, Python configuration, dynamic functions, or directives.

## Explicit type mapping

Sphinx-Needs type names do not automatically become Quarto-Needs types.

Example:

```bash
quarto-needs migrate sphinx-needs needs.json \
  --type-map req=system-requirement \
  --type-map test=test-case
```

Every source type without an explicit mapping produces `TYPE_UNMAPPED`. The candidate is preserved in the plan, but the plan is not migration-ready.

This prevents source-local type labels such as `req`, `spec`, `impl`, or organization-specific names from being assigned canonical meaning by heuristic.

## Explicit relation mapping

Sphinx-Needs link fields are discovered from `needs_schema.properties.*.field_type = "links"`.

They are migrated only when the user supplies a mapping from source field to canonical Quarto-Needs relation:

```bash
quarto-needs migrate sphinx-needs needs.json \
  --relation-map tests=verified-by \
  --relation-map implements=implemented-by
```

Unmapped link fields remain preserved in `unmappedLinks` and produce `LINK_FIELD_UNMAPPED`.

Backlink fields are not imported as independent authored relations because they are normally inverse/computed projections of forward links. This avoids duplicating relation authority during migration.

## Conditional and external links

The first slice fails explicit rather than guessing semantics:

- conditional link expressions produce `CONDITIONAL_LINK` and remain unmapped;
- mapped targets absent from the selected source version produce `EXTERNAL_LINK_TARGET`;
- the original target text is preserved for review.

A future adapter may add a documented expression translator only if the source construct can be mapped without executing arbitrary Python or recreating Sphinx-Needs evaluation semantics.

## Preserved content

Each `SphinxNeedCandidate` preserves:

- source ID;
- source type;
- explicitly mapped target type, when available;
- title;
- content;
- status;
- tags;
- explicitly mapped relations;
- unmapped links;
- remaining source fields as deterministic `extras`.

The source ID remains the primary migration identity. The adapter does not silently regenerate IDs merely because a configured Quarto-Needs prefix would produce a different spelling.

## Deterministic plan artifact

The adapter emits:

```text
sphinx-needs-migration-plan-v1
```

Default path:

```text
.quarto-needs/migrations/sphinx-needs-plan.json
```

The projection is deterministic and machine-readable. A plan with unresolved semantic issues is still written so it can be reviewed, but the CLI returns exit code `1` to signal that it is not migration-ready.

A malformed source, invalid mapping declaration, or structurally invalid input returns an error rather than a partial authoritative migration.

## CLI

Typical ready-plan invocation:

```bash
quarto-needs migrate sphinx-needs needs.json \
  --type-map req=system-requirement \
  --type-map test=test-case \
  --relation-map tests=verified-by
```

JSON report:

```bash
quarto-needs migrate sphinx-needs needs.json \
  --type-map req=system-requirement \
  --type-map test=test-case \
  --relation-map tests=verified-by \
  --format json
```

The CLI currently supports Sphinx-Needs as the explicit source identifier. Unknown migration sources fail rather than selecting an adapter heuristically.

## Existing regression coverage

The implementation is covered by:

```text
tests/test_sphinx_needs_migration.py
tests/test_migration_cli.py
```

Current tests protect:

- deterministic version selection;
- ambiguous-version rejection;
- explicit type semantics;
- explicit relation semantics;
- source ID recovery;
- duplicate-ID rejection;
- object and array wire shapes;
- conditional-link preservation;
- external-target diagnostics;
- deterministic plan serialization;
- CLI ready/unresolved exit contracts;
- conflicting mapping rejection;
- unknown-source rejection.

## What is intentionally not implemented

Phase 5.4 does **not** yet provide `migrate ... --apply`.

Before authored files can be generated or changed, Quarto-Needs needs an explicit apply contract covering:

1. destination-file selection and collision policy;
2. canonical-ID collision checks against the current project;
3. type/status validation against `.quarto-needs.toml`;
4. canonical relation resolution and endpoint validation;
5. source-provenance retention in generated declarations;
6. escaping and lossless rendering of source content into `.need` blocks;
7. atomic multi-file writes;
8. rollback behavior on any failed write or post-write validation;
9. post-write `scan/check` verification;
10. an idempotence contract for rerunning the same migration;
11. explicit handling of source fields that cannot be represented canonically;
12. reviewable dry-run diff before mutation.

Until those contracts exist, the migration plan is the terminal artifact.

## Candidate next adapters

After the Sphinx-Needs path is hardened, additional adapters may target other requirements/docs-as-code ecosystems such as StrictDoc, Doorstop, and OpenFastTrace.

Each adapter must remain source-specific at the parsing boundary and converge only at a shared migration-plan contract. The project should not build a generic heuristic importer that guesses semantics across unrelated source ecosystems.

## Phase 5.4 acceptance direction

The Sphinx-Needs adapter is considered functionally useful when:

- its regression and CLI suites pass locally;
- the plan schema/contract is documented and stable;
- a representative real-world `needs.json` can be processed without hidden source execution;
- unresolved semantics are surfaced explicitly rather than silently dropped;
- the future apply contract is specified before mutation code is introduced.

Automatic migration writes remain a later controlled slice, not a prerequisite for recognizing the current plan-only adapter as implemented.