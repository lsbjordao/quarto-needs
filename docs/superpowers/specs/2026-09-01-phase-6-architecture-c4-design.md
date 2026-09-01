# Phase 6 — Architecture model and C4 projections, design

**Date:** 2026-09-01
**Status:** Proposed — pending user review before handoff to writing-plans
**Roadmap:** `docs/ROADMAP.md`, Phase 6 (currently ⚪, one paragraph)
**Vision reference:** `docs/superpowers/specs/2026-08-29-quarto-needs-full-product-vision.md` already accepts "C4-inspired architecture projections derived from the canonical graph" as sequencing item 6.

## Goal

Give Quarto-Needs a formal architecture hierarchy (actors, external systems,
systems, containers, components, code) expressed with the same `.need` grammar
and relation graph every other object type already uses, and generate C4
System Context, Container, and Component views as Mermaid diagrams (plus a
plain Code-level listing) directly from that graph — never a second,
separately-maintained architecture model.

This phase formalizes an ad-hoc precedent that already exists:
`examples/quarto-needs/architecture.qmd` already declares `type="component"`
and `type="interface"` objects (`COMP-*`/`IF-*`), and
`examples/quarto-needs/implementation.qmd` already declares
`type="source-module"` objects (`SRC-*`) with `path`/`language`/`layer`
attributes. Neither has a formal place in a hierarchy today, and nothing
currently links a `SRC-*` file to the `COMP-*` component that owns it except
naming convention.

## Non-goals

- Dynamic (sequence/collaboration) or deployment C4 views. The roadmap is
  explicit that these follow only after the static hierarchy is stable —
  they are a later phase's slice, not part of this design.
- A new rendering pipeline. C4 diagrams reuse the exact same
  projection-then-Lua-render pipeline `need-graph` already uses
  (`select_graph`/`build_projection` in Python, `root_projection` in Lua),
  not a parallel mechanism.
- Multi-language/AST-derived Code views. Code-level content stays exactly
  what `SRC-*` objects already carry (`path`, `language`, `implements`) —
  no new code-analysis capability.
- Enforcing "exactly one system per project." Nothing here requires or
  forbids multiple `system` roots; each is independently viewable.
- A closed, hardcoded type enum. `actor`/`external-system`/`system`/
  `container` are new *conventional* type values, validated the same
  project-configurable way every other type already is
  (`required_attributes`/`allowed_statuses` in `NeedsConfig`) — not a new
  kind of schema mechanism.

## Data model

### New and formalized types

| Type | Status | Required attributes | Notes |
|---|---|---|---|
| `actor` | new | `title` only | A person/role outside the system. |
| `external-system` | new | `title` only | A system this one talks to but doesn't implement (e.g. GitHub, an OSLC-compliant RM tool). |
| `system` | new | `title` only | Top-level boundary. A project may declare more than one. |
| `container` | new | `technology` | A deployable/runnable unit inside a system (e.g. "Python package", "Quarto Lua extension"). `technology` is what a C4 diagram prints in the box and is required so every container renders meaningfully. |
| `component` | formalized (already exists) | unchanged | Now expected to carry a `part-of` relation to its owning container. |
| `source-module` | unchanged | unchanged | Already carries `path`/`language`/`layer`; now expected to carry `part-of` to its owning component. |

Type validation (required attributes, allowed statuses) uses the existing
project-config mechanism (`NeedsConfig.required_attributes`) — no new
validation *mechanism*, only new config entries the retrofit slice adds for
this project.

### Hierarchy: reusing `decomposes`, adding its missing inverse

`src/quarto_needs/relations.py`'s `decomposes` (`RelationKind`, semantic
family `decomposition`, source role `whole`, target role `part`) already
means exactly "contains." It currently has **no registered inverse** — a
child object cannot self-declare `part-of: <parent-id>`; only the parent can
list every child via `decomposes: <child-id>, <child-id>, ...`. This is a gap
independent of C4: it is inconvenient today for any decomposition, and this
phase closes it by adding one new `RelationKind`:

```python
RelationKind("part-of", "decomposes", "decomposes", "decomposition",
             "Part of", "Decomposes", "part", "whole",
             "source_to_target", "source_to_target")
```

This makes `part-of`/`decomposes` a normal authored-from-either-side pair,
the same shape `implements`/`implemented-by` or `verified-by`/`verifies`
already have. A `container` declares `part-of: SYS-X`; a `component`
declares `part-of: CONTAINER-X`; a `source-module` declares
`part-of: COMP-X`. `actor` and `external-system` never participate in
`part-of` — they sit outside the hierarchy and connect only via interaction
edges.

### Interaction arrows: reusing `depends-on`

C4's labeled arrows between boxes ("calls via HTTPS, sends order data") reuse
the existing `depends-on` relation unchanged. `depends-on` is registered in
the catalog but not used anywhere in the current self-hosted example today
(verified: `grep -rn "depends-on" examples/quarto-needs/*.qmd` returns
nothing), so there is no existing-usage conflict to resolve.
`Relation.attributes` (already a free-form `dict[str, Any]`) carries
`technology`/`description` — e.g.
`depends-on: SYS-EXT-GITHUB technology="HTTPS/REST" description="fetches issues"` —
which the C4 renderer reads directly; no schema change to `Relation` itself.

### Validation: two rules, only one of them new code

1. **Exactly one parent.** A `container`/`component`/`source-module` must
   have exactly one outgoing `part-of` edge. This is already fully
   expressible with the *existing*, generic `relation_policies` cardinality
   mechanism (`RelationPolicy.minimum_per_source`/`maximum_per_source` in
   `NeedsConfig`, enforced in `rules.py` today). **No new validation code** —
   the retrofit slice configures `part-of` with `minimum-per-source: 1,
   maximum-per-source: 1` in this project's own config, the same way any
   project using this pattern would.

2. **Adjacent layers only.** A `system` must not `part-of`-receive a
   `component` directly, skipping `container` (and symmetric skip-level
   mistakes at any layer). This is *not* expressible with the existing
   `allowed_source_types`/`allowed_target_types` mechanism, because that
   mechanism checks set membership independently on each side of a relation,
   not that a *specific pairing* is the adjacent one — a single
   `allowed_source_types=(container, component, source-module)` /
   `allowed_target_types=(system, container, component)` pair would
   incorrectly also permit "component `part-of` system." This phase adds
   one small, self-contained new rule (alongside `rules.py`'s existing
   bespoke structural checks) verifying that a `part-of` edge's target sits
   exactly one layer above its source in the fixed layer order
   `system > container > component > source-module`. New finding code
   (e.g. `ARC001`), scoped narrowly to this one check.

## View computation

One generic operation covers System Context, Container, and Component views
symmetrically: **given a focus node, show its direct `part-of` children (one
level down), plus any actor/external-system/sibling connected via
`depends-on`, rendered as opaque boxes without further expansion.**

- **Context** — focus = a `system`. Show the system as one opaque box (no
  children), plus every actor/external-system with a `depends-on` edge
  touching it.
- **Container** — focus = the same `system`. Show its direct `container`
  children, plus actors/external-systems connected to the system or to any
  of its containers.
- **Component** — focus = a `container`. Show its direct `component`
  children, plus actors/external-systems/other containers directly
  connected to it or its components.

This is exactly what the existing `need-graph` shortcode's `root="<id>"`
kwarg already computes (`root_projection` in `graph.lua`, re-rooting an
already-computed `GraphProjection` to one focus node at a given depth) —
**no new Python projection module.** The only filtering C4 views add beyond
what `root_projection` already does is restricting edges to the
`decomposition` and `dependency` semantic families; both are already
published per-edge in the emitted graph JSON via `graph_output.py`'s
`_public_relation_semantics()`, so this filter is a small addition inside
the new Lua rendering path, not a new Python computation — consistent with
`data.lua`'s own stated boundary ("Python owns relation semantics; this
module only indexes the emitted graph").

### Code view: a listing, not a diagram

Mermaid has no native C4-Code diagram type, and `source-module` objects
don't carry meaningful inter-module call arrows to draw (their only
relation today is `implements` to a requirement, not to each other). Code
view therefore renders as a plain Markdown table (path, language, what it
implements) generated the same way — focus = a `component`, list its direct
`source-module` children — rather than forcing Mermaid syntax onto content
that isn't diagram-shaped.

## Rendering integration

New Lua module `_extensions/quarto-needs/c4.lua`, following `graph.lua`'s
existing structure, registered as a new shortcode (`need-c4`) in
`shortcodes.lua`'s dispatch table alongside `need-graph`:

```qmd
{{< need-c4 root="SYS-QUARTO-NEEDS" level="context" >}}
{{< need-c4 root="SYS-QUARTO-NEEDS" level="container" >}}
{{< need-c4 root="CONTAINER-PYTHON-PKG" level="component" >}}
{{< need-c4 root="COMP-PARSER" level="code" >}}
```

`c4.lua`:

1. Calls the existing projection/root machinery to get the focus node + one
   level of children (`root`, `depth=1`, same as `need-graph` today).
2. Filters edges to `decomposition`/`dependency` families using the
   already-published per-edge family metadata.
3. For `level` in `{context, container, component}`: maps each *non-focus*
   node's `type` to a C4 macro (`Person` for `actor`, `System`/`System_Ext`
   for `system`/`external-system`, `Container` for `container`, `Component`
   for `component`) and each `depends-on` edge to `Rel(from, to,
   description, technology)`. The **focus node itself** renders differently
   depending on level: at `context` it is the opaque `System(...)` box being
   described; at `container`/`component` it becomes the grouping boundary
   its children nest inside (Mermaid's `System_Boundary(alias, label) {
   Container(...) ... }` / `Container_Boundary(alias, label) {
   Component(...) ... }`), never a `System`/`Container` box of its own at
   that level — matching how real C4 Container/Component diagrams always
   draw the thing being zoomed into as a boundary, not a box. Output is a
   Mermaid `C4Context`/`C4Container`/`C4Component` block (mirroring
   `views.lua`'s existing `escape_mermaid` helper for label/edge text).
4. For `level="code"`: emits a plain Markdown table instead, no Mermaid.

An invalid `root`/`level` combination (e.g. `level="context"` where `root`
is not a `system`) fails loudly with the shortcode's own warning helper
(`views.warning`, already used elsewhere for shortcode misuse) rather than
rendering a misleading diagram.

## First-slice retrofit (self-hosted example)

Concrete, since "prove it on the real thing" was the chosen scope:

1. One `system` object, `SYS-QUARTO-NEEDS`.
2. `actor`/`external-system` objects for participants already implied by
   existing content but never modeled as boxes: an actor for the
   requirements-engineer/reviewer role; external-systems for GitHub and an
   OSLC-compliant RM tool (both already justified by the Phase 5/5.5
   federation work).
3. Two `container` objects splitting the existing 8 `COMP-*` by actual
   deployable unit: the Python package (`COMP-PARSER`, `COMP-ANALYSIS`,
   `COMP-RULES`, `COMP-CLI`, `COMP-GRAPH`, `COMP-BASELINE`, `COMP-I18N`) and
   the Quarto Lua extension (`COMP-EXTENSION`).
4. Retrofit the 8 existing `COMP-*` objects with `part-of: <container-id>`.
5. Retrofit `SRC-*` objects in `implementation.qmd` with
   `part-of: <component-id>` — verified this link does not exist as a graph
   edge today (only as implied naming/tags), so this is a real structural
   addition, not relabeling.
6. Configure this project's own `relation_policies` for `part-of`
   (`minimum-per-source: 1, maximum-per-source: 1`).
7. Embed `need-c4` at Context/Container/Component levels in
   `architecture.qmd` (or a new `architecture-views.qmd`, decided during
   implementation planning).
8. Mirror every new/changed object and the embedded shortcodes into
   `architecture.pt-BR.qmd`/`implementation.pt-BR.qmd`, including using this
   project's established `### Justificativa` heading convention for any new
   rationale prose (a gap this session already found and fixed once for
   `interoperability.pt-BR.qmd`).

## Testing strategy

Follows this project's standing TDD discipline (failing test first, minimal
code, falsify safety-relevant checks by breaking them and confirming the
test catches it, full suite green before each commit):

- `relations.py`: a test proving `part-of`/`decomposes` resolve to the same
  `v1_name` and are mutual inverses via `inverse_v1_name`, mirroring the
  existing `derives-from`/`derived-from` alias tests.
- `rules.py`: tests for the new layer-adjacency rule — a valid adjacent
  `part-of` passes; a skip-level `part-of` (e.g. `component` directly
  `part-of` a `system`) is caught; a same-layer `part-of` is caught;
  falsified by temporarily removing the layer-order check and confirming
  the skip-level test fails.
- `config.py`/existing `relation_policies` tests: a project config declaring
  `part-of` cardinality 1/1 rejects a container with zero or two parents —
  this exercises the *existing* generic mechanism against the *new*
  relation, not new mechanism code.
- `c4.lua`: unit-style tests (matching however this project already tests
  Lua shortcodes, e.g. `tests/test_*graph*` snapshot/golden-output style if
  one exists — to confirm during planning) proving: a `level="context"`
  projection emits `C4Context` syntax with the system as one opaque
  `System(...)` box and its actors/external-systems as `Person`/
  `System_Ext`; a `level="container"` projection on the same root instead
  shows its containers; `level="code"` emits a Markdown table, not Mermaid;
  an invalid root/level pairing warns instead of rendering.
- Self-hosted example: `tests/test_self_hosted_example.py`-style parity
  checks extended to cover the new `SYS-*`/actor/external-system/container
  objects and their EN/pt-BR semantic-signature parity (this session's own
  review found this file's parity check currently excludes `rationale` —
  worth revisiting whether the new architecture objects need any additional
  signature fields checked, decided during implementation planning).
- Full suite (`pytest -m` gated appropriately) green after each commit, per
  this project's standing discipline.

## Open questions for implementation planning (not blocking this design)

- Exact `.qmd` file layout for the new architecture objects (extend
  `architecture.qmd` in place vs. a new file) — cosmetic, decide during
  planning.
- Whether `need-c4`'s Lua tests follow an existing golden-Mermaid-output
  test pattern already established for `need-graph`, or need a new one —
  depends on what `need-graph`'s own test suite currently does, to be
  confirmed while planning.
- Whether the new `ARC001` layer-adjacency finding should be `error` or
  `warning` severity by default — likely `error` (it is a structural
  contradiction, not a style nit), confirm against this project's existing
  severity conventions during planning.
