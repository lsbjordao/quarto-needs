# Phase 5.4 — Migration adapters

Status: **three migration adapters — Sphinx-Needs, Doorstop, and StrictDoc — are implemented end to end on a shared contract: a source-specific deterministic plan, a reviewable non-mutating apply plan with a `.need` block content preview, and a create-only, atomic, rollback-protected `--write` step that generates authored files.**

Quarto-Needs treats migration as a reviewed interoperability operation, not as a parser shortcut. A migration source may have its own type system, relation semantics, computed fields, conditional links, backlinks, dynamic functions, rendering behavior, and identity conventions. Those concepts must not be silently reinterpreted as canonical Quarto-Needs semantics.

Sphinx-Needs is one of the inspirations for Quarto-Needs and was the first migration source supported by this phase; Doorstop and StrictDoc followed, each converging on the same apply-plan/write contract without any adapter guessing another's semantics.

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
reviewable, non-mutating apply plan (--apply-plan)
        ↓
create-only, atomic, rollback-protected write (--write)
```

The migration plan and the apply plan are analysis output; building either never writes an authored `.qmd`/`.md` file. Only the explicit `--write` step does, and only when the apply plan is fully `ready-create`. None of these stages become a second semantic model — every field, type, status, and relation in a written file still means exactly what it means anywhere else in the canonical graph.

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

Add `--write` (which requires `--apply-plan`) to actually create the files, only once every item is `ready-create`:

```bash
quarto-needs migrate sphinx-needs needs.json \
  --type-map req=system-requirement \
  --type-map test=test-case \
  --relation-map tests=verified-by \
  --apply-plan \
  --destination REQ_001=requirements/authentication.qmd \
  --destination TC_001=verification/authentication.qmd \
  --write
```

`--write` without `--apply-plan` is a usage error (exit code `2`). If any item is not `ready-create`, or a destination file already exists on disk, `--write` refuses and creates nothing.

The CLI dispatches on an explicit source identifier (`sphinx-needs` or `doorstop`). Unknown migration sources fail rather than selecting an adapter heuristically.

## Doorstop adapter

Doorstop stores each item as its own YAML file (`<PREFIX><NNN>.yml`) inside a directory anchored by a `.doorstop.yml` document-settings file (`settings.prefix`, optionally `settings.parent`). A subdirectory with its own `.doorstop.yml` forms a child document — e.g. `reqs/tutorial/.doorstop.yml` with `settings.parent: REQ` traces up into `reqs/.doorstop.yml`'s `REQ` items. `src/quarto_needs/migrations/doorstop.py` reads only this on-disk tree; it never executes Doorstop or arbitrary Python.

Doorstop items carry no `type` or free-text `status` field the way a Sphinx-Needs need does. The document's `prefix` is the only source-type signal an item has, so `--type-map`/`--relation-map` are keyed by prefix rather than by an authored field name, and every migrated candidate's `status` is left `None` (the written `.need` block simply carries no `status` attribute) unless the destination project's own defaults supply one. `links` is Doorstop's only relation concept, always meaning "this item traces up to its parent document's item"; the SHA-based value paired with each link entry is Doorstop's own review-integrity marker, not migrated.

```bash
quarto-needs migrate doorstop reqs \
  --type-map REQ=system-requirement \
  --type-map TUT=test-case \
  --relation-map TUT=derives-from
```

A document prefix without an explicit `--type-map` entry produces `TYPE_UNMAPPED` for every one of its items, exactly like Sphinx-Needs. A *child* document prefix without an explicit `--relation-map` entry produces `RELATION_UNMAPPED`, and its links are preserved under `unmappedLinks` rather than silently dropped — the same fail-explicit treatment Sphinx-Needs gives `LINK_FIELD_UNMAPPED`. A link whose target UID is absent from the loaded document tree produces `EXTERNAL_LINK_TARGET`. Two documents that produce the same item UID (a prefix reused across directories by misconfiguration) fail closed with `DoorstopMigrationError` rather than one silently shadowing the other.

Each migrated candidate preserves Doorstop's `active`, `derived`, `normative`, `ref`, and `level` fields as `extras`. `header` becomes the title, falling back to the item's UID when the header is empty — which is the common case in real Doorstop trees, where most of an item's meaning lives in `text` rather than in a short heading. `text` becomes the body verbatim.

The apply-plan, `.need` block content-preview rendering, and `--write` contracts described above are not reimplemented per adapter: Doorstop's parser produces the same candidate/plan shape Sphinx-Needs' parser does (`SphinxNeedCandidate`/`SphinxNeedsMigrationPlan` in `migrations/sphinx_needs.py`, reused as the shared shape — the name is a holdover from being the first adapter, not a Sphinx-Needs-specific type), carrying its own `tool`/`schema` (`"Doorstop"` / `"doorstop-migration-plan-v1"`) through to every downstream artifact's provenance. Default paths are independent of the Sphinx-Needs adapter's, so both can run against the same project without colliding:

```text
.quarto-needs/migrations/doorstop-plan.json
.quarto-needs/migrations/doorstop-apply-plan.json
```

```bash
quarto-needs migrate doorstop reqs \
  --type-map REQ=system-requirement \
  --type-map TUT=test-case \
  --relation-map TUT=derives-from \
  --apply-plan \
  --destination REQ001=requirements/assets.qmd \
  --destination TUT008=verification/tree.qmd \
  --write
```

## StrictDoc adapter

StrictDoc stores requirements as `.sdoc` text files using its own SDoc grammar: `[TAG]` blocks (`[DOCUMENT]`, `[REQUIREMENT]`, `[TEXT]`, `[[SECTION]]`/`[[/SECTION]]`, and any project-custom tag declared in a `[GRAMMAR]` block) containing flat `KEY: value` fields, `KEY: >>>` … `<<<` multi-line fields, and an optional `RELATIONS:` list of `- TYPE: <type>` entries with their own sub-fields. `src/quarto_needs/migrations/strictdoc.py` reads only this text; it never executes StrictDoc.

Unlike Doorstop, a StrictDoc item's `UID` is authored directly and is globally unique across the whole project, not derived from a filename or a per-document prefix — so `--type-map` is keyed by the block's `[TAG]` (e.g. `REQUIREMENT`, exactly like Sphinx-Needs' `type` field) and `--relation-map` is keyed by each relation entry's own `TYPE` (e.g. `Parent`), which can point to a UID defined in a *different* `.sdoc` file; every file under the given root is loaded together so cross-document relations resolve. Only blocks that carry a non-empty `UID` become candidates — `[TEXT]` and `[[SECTION]]` prose blocks without one are structural presentation, not migrated. `RATIONALE`, when present, is folded into the candidate's content as a `### Rationale` subsection — the same convention `parser.py` already recognizes in authored `.qmd` bodies — rather than inventing a separate field the destination grammar has no slot for.

```bash
quarto-needs migrate strictdoc reqs \
  --type-map REQUIREMENT=system-requirement \
  --relation-map Parent=derives-from
```

A `[TAG]` without an explicit `--type-map` entry produces `TYPE_UNMAPPED`, exactly like the other two adapters. A relation `TYPE` without an explicit `--relation-map` entry produces `RELATION_UNMAPPED` and is preserved under `unmappedLinks` keyed by that `TYPE`, not dropped. A relation whose `VALUE` is not defined anywhere in the loaded project produces `EXTERNAL_LINK_TARGET`. Not every relation is UID-addressed: StrictDoc's `TYPE: File` relations carry `FORMAT`/`PATH` instead of `VALUE` (pointing at a source file, not a requirement), so they cannot resolve against the canonical ID space at all — rather than forcing them through the UID-relation path or discarding them, every such entry is preserved verbatim under the candidate's `extras.nonUidRelations`. The same duplicate-UID fail-closed behavior applies across files as within a single Doorstop tree, and both were verified not only against synthetic fixtures but by running the adapter against StrictDoc's own real, self-hosted `.sdoc` requirements documents (fetched from `strictdoc-project/strictdoc` on GitHub) — the `[GRAMMAR]`-block edge cases (`[DOCUMENT].OPTIONS`, `[GRAMMAR].ELEMENTS`, and `TYPE: File` relations) that synthetic fixtures alone would not have surfaced were found and handled this way specifically because of that real-data run.

Each migrated candidate preserves every field the adapter does not consume as `extras` (`MID`, `COMMENT`, any project-custom field), keyed exactly as StrictDoc authored them.

```bash
quarto-needs migrate strictdoc reqs \
  --type-map REQUIREMENT=system-requirement \
  --relation-map Parent=derives-from \
  --apply-plan \
  --destination SRS-1=requirements/config.qmd \
  --write
```

Default artifact paths, independent of the other two adapters':

```text
.quarto-needs/migrations/strictdoc-plan.json
.quarto-needs/migrations/strictdoc-apply-plan.json
```

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

## Writing files: `--apply-plan --write`

`src/quarto_needs/migrations/apply_write.py` implements `apply_migration_plan(root, plan, config)`, wired into the CLI as `--write` (which requires `--apply-plan`). Its contract:

- **all-or-nothing**: if any item in the plan is not `ready-create`, nothing is written — the whole call is refused before touching disk;
- **create-only**: if a destination file already exists on disk, the whole call is refused; this is never an update path;
- **atomic per file**: each file is written through the same temp-file-plus-`os.replace` helper (`export._write_atomic_text`) every other exporter in this project uses;
- **all-or-nothing across files, with real rollback**: if any file write fails, or the required post-write check fails, every file this call wrote is deleted before the error propagates — verified by forcing an OS-level write failure on the second of two files and confirming the first is rolled back, not by asserting on the rollback code's own logic;
- **post-write scan/check verification**: after every file is written, the project is re-analyzed (`analyze_project`, the same engine `quarto-needs scan`/`check` use) and any structural failure or `error`-severity finding triggers the rollback above — verified by injecting a synthetic error finding and confirming rollback, since the plan's own checks already prevent every "natural" way to reach this path;
- **idempotence**: rerunning `--write` for the same plan is refused, not silently duplicated or silently skipped — the canonical IDs it would create now exist in the project graph, so `build_sphinx_apply_plan` reclassifies every item as `blocked` on the next run and `apply_migration_plan` refuses a plan that isn't fully `ready-create`. This refusal *is* the idempotence contract: a rerun is a safe no-op, not a silent duplicate.
- **unrepresentable fields**: already excluded upstream — an item only reaches `ready-create` (and therefore only reaches `apply_migration_plan`) once `need_block_problems` has found nothing it cannot represent.

`--write` prints (or, in `--format json`, emits) a `migration-apply-result-v1` payload listing the destination files actually written; it never prints or writes anything on refusal.

## Existing regression coverage

The implementation is covered by:

```text
tests/test_sphinx_needs_migration.py
tests/test_migration_cli.py
tests/test_migration_apply_plan.py
tests/test_migration_apply_plan_cli.py
tests/test_migration_need_render.py
tests/test_migration_apply_write.py
tests/test_doorstop_migration.py
tests/test_doorstop_migration_cli.py
tests/test_strictdoc_migration.py
tests/test_strictdoc_migration_cli.py
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
- `.need` block content-preview rendering, its unrepresentable-content guard, and `--show-content` CLI output, verified by round-tripping through the real parser;
- `--apply-plan --write`: create-only, atomic-per-file, all-or-nothing-with-rollback authored-file generation, with post-write `scan`/`check` re-verification and a refusal-based idempotence contract;
- the apply-plan contract carrying a non-Sphinx `tool`/`schema` through provenance and the plan artifact, proven directly rather than only through Doorstop;
- Doorstop document/item discovery across nested `.doorstop.yml` document boundaries, prefix-keyed type/relation mapping, unmapped-type/unmapped-relation/external-link diagnostics (falsified, not just asserted, for duplicate-UID rejection), and the same CLI plan/apply-plan/write contract end to end with independent default artifact paths;
- StrictDoc `.sdoc` parsing across multiple files with globally-unique, cross-file UID resolution, TAG-keyed type mapping and relation-TYPE-keyed relation mapping, rationale folded into content as a `### Rationale` subsection, `TYPE: File` (non-UID) relations preserved rather than misresolved or dropped, and the same CLI plan/apply-plan/write contract end to end — additionally validated by running against StrictDoc's own real, self-hosted `.sdoc` requirements documents.

## What is intentionally not implemented

`--apply-plan --write` (see above) covers all twelve items originally listed for the apply contract: destination selection/collision policy, canonical-ID collision checks, type/status validation, relation/endpoint resolution, source-provenance retention, escaped `.need` block rendering, atomic multi-file writes, rollback on failed writes or post-write validation, post-write `scan`/`check` verification, a refusal-based idempotence contract, upstream handling of unrepresentable fields, and a reviewable dry-run diff before mutation. This holds for all three adapters, since they converge on the same `build_sphinx_apply_plan`/`apply_migration_plan` implementation.

What is still explicitly out of scope for this phase:

- **update/match semantics.** `build_sphinx_apply_plan` is create-only by design (see its docstring): an existing canonical ID is always a collision, never an implicit update. Migrating a *changed* upstream project (Sphinx-Needs, Doorstop, or StrictDoc) onto an already-migrated Quarto-Needs project needs its own reviewed identity/merge contract, not an extension of this one.
- **multi-file/partial-batch review.** A plan is applied whole or not at all; there is no "apply only the ready subset and leave the rest for later" mode.
- **non-UID relation resolution**, such as StrictDoc's file-addressed `TYPE: File` relations — preserved for review, never guessed into a canonical relation.
- **additional source-specific adapters** (OpenFastTrace, …) beyond the three implemented.

Automatic migration writes now existing for these adapters does not change the terminal-artifact posture of Phase 5.3's OSLC federation (still plan-only) or of any future external adapter: each adapter earns its own reviewed apply contract independently.

## Candidate next adapters

Additional adapters may target other requirements/docs-as-code ecosystems such as OpenFastTrace.

Each adapter must remain source-specific at the parsing boundary and converge only at a shared migration-plan contract, exactly as Doorstop and StrictDoc converged onto Sphinx-Needs' apply-plan/render/write implementation rather than reimplementing it. The project should not build a generic heuristic importer that guesses semantics across unrelated source ecosystems.

## Phase 5.4 acceptance direction

The Sphinx-Needs, Doorstop, and StrictDoc adapters are considered functionally complete for their sources now that:

- their regression and CLI suites pass locally;
- the plan, apply-plan, and apply-result schemas/contracts are documented, stable, and shared across all three adapters (each carrying its own `tool`/`schema` provenance);
- a representative real-world source tree can be processed without hidden source execution (no Sphinx project, no Doorstop invocation, no StrictDoc invocation, no arbitrary Python) — StrictDoc's adapter specifically against StrictDoc's own real self-hosted `.sdoc` documents, not only synthetic fixtures;
- unresolved semantics are surfaced explicitly rather than silently dropped;
- the apply contract was specified (this document, and the roadmap) before any mutation code was introduced, and every one of its explicit requirements — atomicity, rollback, post-write verification, idempotence, create-only identity, unrepresentable-content refusal — is exercised by a test that fails when the corresponding behavior is removed;
- adding a second and third adapter required no change to the apply-plan/render/write contract itself, only to each source-specific parser — evidence that the contract, not just the first adapter, is what was actually built.

What remains is further breadth (OpenFastTrace), and, independently, an update/match identity contract if migrating an already-migrated project ever becomes a requirement.
