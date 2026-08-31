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

Reviewable apply plan, added against the current project graph and configuration (no file is written or changed):

```bash
quarto-needs migrate sphinx-needs needs.json \
  --type-map req=system-requirement \
  --type-map test=test-case \
  --relation-map tests=verified-by \
  --apply-plan \
  --destination REQ_001=requirements/authentication.qmd \
  --destination TC_001=verification/authentication.qmd
```

Each candidate without an explicit `--destination` is reported `review-required` rather than guessed; a canonical-ID collision, disallowed type/status, or unresolved relation target is reported `blocked` with its reasons. The CLI exits `0` only when every item is `ready-create`.

Add `--show-content` to print the exact `.need` block text that would be written for every item that has one (see below):

```bash
quarto-needs migrate sphinx-needs needs.json \
  --type-map req=system-requirement \
  --type-map test=test-case \
  --relation-map tests=verified-by \
  --apply-plan \
  --destination REQ_001=requirements/authentication.qmd \
  --destination TC_001=verification/authentication.qmd \
  --show-content
```

The CLI currently supports Sphinx-Needs as the explicit source identifier. Unknown migration sources fail rather than selecting an adapter heuristically.

## Non-mutating apply-plan artifact

The `--apply-plan` flag emits:

```text
migration-apply-plan-v1
```

Default path:

```text
.quarto-needs/migrations/sphinx-needs-apply-plan.json
```

Each item carries the proposed canonical ID, destination file (or `null` pending review), target type/status, title/content/tags, canonically resolved relations, source provenance (tool/project/version/source ID), a `contentPreview` (see below), and — when not `ready-create` — the explicit reasons it is `blocked` or `review-required`. This plan is validated against the *current* project's snapshot and `.quarto-needs.toml`, so it reflects collisions and configuration as they exist right now; it is not itself a guarantee that a later `--apply` run against a changed project will reproduce it. Building this plan never writes, creates, or modifies an authored `.qmd`/`.md` file.

## Content preview: rendering into `.need` blocks

`src/quarto_needs/migrations/render.py` renders a candidate's title/body/tags/relations into authored `.need` block text using the same grammar `parser.py` reads (`::: {.need #ID type="..." status="..."}`, flat `relation: target` lines, an `##` heading, then body). The authored grammar has no escape mechanism, so rather than risk producing text that fails to round-trip, `need_block_problems(...)` refuses to render whenever the source data cannot be represented safely:

- a canonical ID outside `[A-Za-z0-9_.:-]+`;
- a target type, target status, or tag containing `"` or `}`, or a tag containing `;` (the tag separator);
- a title containing a newline;
- source content containing a line that is exactly `:::`, which would close the block early and silently truncate everything after it;
- a relation target outside the same ID character set.

Every `MigrationApplyItem` whose content renders cleanly carries the exact text in `content_preview` (`contentPreview` in JSON); any problem found is appended to the item's `reasons` and forces `status="blocked"`, even if destination/collision/type checks all pass. The renderer itself is verified by round-tripping its output through the real `parse_qmd_text_declarations` parser, not by asserting on its own string output.

Rendering a preview never writes a file — it is purely part of the reviewable apply plan.

## Existing regression coverage

The implementation is covered by:

```text
tests/test_sphinx_needs_migration.py
tests/test_migration_cli.py
tests/test_migration_apply_plan.py
tests/test_migration_apply_plan_cli.py
tests/test_migration_need_render.py
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
- unknown-source rejection;
- apply-plan destination/collision/type/status/relation validation and status classification;
- apply-plan CLI wiring, ready/review-required exit contracts, and default artifact path;
- `.need` block content-preview rendering, its unrepresentable-content guard, and `--show-content` CLI output, verified by round-tripping through the real parser.

## What is intentionally not implemented

Phase 5.4 does **not** yet provide `migrate ... --apply`. No command in this phase writes, creates, or modifies an authored `.qmd`/`.md` file.

The non-mutating apply-plan contract (`--apply-plan`, see above) now covers:

- (1) destination-file selection and collision policy;
- (2) canonical-ID collision checks against the current project;
- (3) type/status validation against `.quarto-needs.toml`;
- (4) canonical relation resolution and endpoint validation;
- (5) source-provenance retention in generated declarations;
- (6) escaping and lossless rendering of source content into `.need` blocks (as a preview; nothing is written yet);
- (12) a reviewable dry-run diff before mutation (the plan's text/JSON CLI output, including the rendered content itself via `--show-content`).

Before authored files can actually be generated or changed, Quarto-Needs still needs:

- (7) atomic multi-file writes;
- (8) rollback behavior on any failed write or post-write validation;
- (9) post-write `scan/check` verification;
- (10) an idempotence contract for rerunning the same migration;
- (11) explicit handling of source fields that cannot be represented canonically.

Until those remaining contracts exist, the apply plan is the terminal artifact.

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