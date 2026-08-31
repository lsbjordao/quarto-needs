# Phase 5.4 — Sphinx-Needs migration adapter

Status: **conservative migration planning implemented; project-aware QMD materialization remains pending**.

Sphinx-Needs is one of the original inspirations for Quarto-Needs, and it is also the first migration source implemented for Phase 5.4. The objective is not syntax emulation. The adapter consumes Sphinx-Needs' machine-readable `needs.json` exchange artifact and builds an auditable migration plan into Quarto-Needs concepts.

## Source boundary

Sphinx-Needs' `needs` builder stores needs under versioned entries in `needs.json`. Modern exports include:

- `current_version`;
- `versions`;
- per-version `needs`;
- per-version `needs_schema`;
- schema `field_type` metadata distinguishing core, link, backlink, extra, and global fields.

The Quarto-Needs adapter uses that machine representation rather than scraping rendered Sphinx HTML or attempting to parse arbitrary reStructuredText directives.

## Version selection

`src/quarto_needs/migrations/sphinx_needs.py` selects source data using explicit, fail-closed rules:

1. an explicit requested version wins;
2. otherwise `current_version` is used when it names an existing version;
3. otherwise a single available version is unambiguous and may be selected;
4. multiple versions without a valid current/explicit selection are rejected.

Both object-keyed and array-shaped `needs` collections are normalized. Object-keyed exports may recover the ID from the dictionary key when the inner object omits `id`.

## Semantic mapping policy

The adapter deliberately does **not** infer that similarly named concepts are equivalent.

### Types

Sphinx-Needs `type` values require an explicit source→target map, for example:

```text
req  → system-requirement
test → test-case
```

Without a mapping the candidate remains in the plan, but carries `TYPE_UNMAPPED` and no target type.

### Relations

Outgoing link fields are identified from `needs_schema.properties.*.field_type == "links"`. Backlink fields are recognized as derived reverse information and are not migrated as independent authored relations.

Each outgoing link field requires an explicit field→canonical-relation map, for example:

```text
tests → verified-by
```

Without it, values are preserved under `unmappedLinks` and the plan carries `LINK_FIELD_UNMAPPED`.

### Conditional links

Current Sphinx-Needs exports may retain conditions in outgoing links such as:

```text
TC_002[status=='passed']
```

Quarto-Needs does not silently strip or execute that condition. The raw link is preserved and the plan emits `CONDITIONAL_LINK` so the migration policy can decide whether the condition belongs in a requirement policy, a variant, a query, or should be dropped explicitly.

### External targets

A mapped link whose target does not occur in the selected Sphinx-Needs version remains visible in the plan and emits `EXTERNAL_LINK_TARGET`. The adapter does not manufacture a local object merely to satisfy the link.

## Preserved information

For every candidate the plan retains:

- source ID;
- source type;
- explicitly mapped target type when available;
- title and content;
- status;
- tags;
- mapped relations with their original Sphinx link-field name;
- unmapped links;
- all remaining non-core/non-link/non-backlink fields as deterministic `extras`.

This makes loss visible before any QMD is created.

## Machine-readable plan

The first artifact schema is `sphinx-needs-migration-plan-v1`.

```bash
quarto-needs migrate sphinx-needs needs.json
```

The default artifact is:

```text
.quarto-needs/migrations/sphinx-needs-plan.json
```

Explicit mapping example:

```bash
quarto-needs migrate sphinx-needs needs.json \
  --type-map req=system-requirement \
  --type-map test=test-case \
  --relation-map tests=verified-by \
  --format json
```

The command returns:

- `0` when the generated plan contains no unresolved migration issues;
- `1` when a useful plan was generated but semantic decisions remain unresolved;
- `2` for malformed input or invalid mapping configuration;
- `3` for I/O failure.

Returning `1` for an unresolved plan is intentional: the artifact is valuable for review, but must not be mistaken for a migration-ready transformation.

## Why QMD generation is not automatic yet

A semantically complete QMD migration also needs project-aware decisions about:

- target type existence;
- target ID-prefix policy;
- target lifecycle/status mapping;
- canonical relation endpoint constraints;
- required target attributes;
- custom Sphinx fields and whether they become attributes, tags, policy inputs, or are intentionally dropped;
- external-link identity policy;
- conditional-link semantics.

Generating QMD before those checks would create text that looks migrated while failing Quarto-Needs governance or, worse, silently changing meaning.

## Current acceptance status

1. **implemented** — deterministic `needs.json` reader;
2. **implemented** — explicit/`current_version`/single-version selection policy;
3. **implemented** — object-keyed and array-shaped need normalization;
4. **implemented** — link/backlink discovery from `needs_schema.field_type`;
5. **implemented** — explicit type mapping with `TYPE_UNMAPPED` diagnostics;
6. **implemented** — explicit relation-field mapping with `LINK_FIELD_UNMAPPED` diagnostics;
7. **implemented** — conditional-link preservation and `CONDITIONAL_LINK` diagnostics;
8. **implemented** — unresolved/external target preservation and `EXTERNAL_LINK_TARGET` diagnostics;
9. **implemented** — deterministic extras preservation and `sphinx-needs-migration-plan-v1` JSON;
10. **implemented, pending execution gate** — installed `quarto-needs migrate sphinx-needs` preview CLI;
11. **pending** — project-aware status/ID/type/relation validation against a target `.quarto-needs.toml`;
12. **pending** — QMD materialization only from a migration-ready plan;
13. **pending** — round-trip/source-provenance report tying generated QMD objects back to their Sphinx source IDs/version;
14. **deferred** — direct parsing of arbitrary Sphinx/reStructuredText source when `needs.json` is unavailable.

## Regression set

```bash
pytest -q \
  tests/test_sphinx_needs_migration.py \
  tests/test_migration_cli.py
```

As with the current OSLC work, these regressions are committed but are not represented as successfully executed while the available GitHub Actions runner continues to terminate jobs before checkout.
