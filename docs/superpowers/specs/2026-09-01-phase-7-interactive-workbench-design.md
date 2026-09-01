# Phase 7 — Interactive graph workbench, design (first slice: bounded analysis depth)

**Date:** 2026-09-01
**Status:** Proposed — pending user review before handoff to writing-plans
**Roadmap:** `docs/ROADMAP.md`, Phase 7 (currently ⚪, one paragraph)
**Vision reference:** `docs/superpowers/specs/2026-08-29-quarto-needs-full-product-vision.md`, sequencing item 7 ("interactive graph-workbench depth") under the binding invariants "Python remains semantic authority", "browser layers consume projections rather than redefine engineering meaning", and "interactive behavior is progressive enhancement".

## Goal

Turn the existing Cytoscape explorer from a *visualizer with filters* into a *bounded analysis workbench*, by closing the two gaps between what the roadmap's first sentence promises and what a reader can do today:

1. **Two-node semantic shortest path.** The explorer can already walk *up* (path-to-root). It cannot answer "how are A and B related?" — the single most common traceability question — without the reader eyeballing the canvas. This slice adds a focus→target path search that consumes exactly the published semantics the root path already uses.
2. **Interactive baseline comparison.** Diff and impact overlays fully exist as *build-time projection modes* (`build_diff_overlay`/`build_impact_overlay` in `graph_output.py`, `change`/`pathMember` fields, coloring already wired in `graph.js`) — but a reader sees whichever single mode the project's `[graph]` config picked at build time. This slice publishes the catalog, diff, and impact variants of the default view side by side and gives the reader a mode switcher plus an *affected-only* visibility toggle, so "what changed, and what does it affect?" becomes an interactive operation instead of a build-time either/or.

Everything else the roadmap lists for Phase 7 (semantic clustering, breadcrumbs, deep-linkable/saved exploration state, fullscreen, SVG/PNG export, mini-map, keyboard navigation, accessibility depth) is explicitly out of this first slice and named as such in Non-goals.

## Current state this design builds on (verified)

- `graph.js` renders the Cytoscape canvas, search, node popups, neighbor highlighting, focus→origin path highlighting (`highlightPath`, using `projection.view.originId`), color-by-facet including the `change` facet (added/removed/modified/relocated palettes), edge styling for `pathMember = 'true'`, and a semantic HTML table as the primary accessible representation. Escape closes popups; that is the entire current keyboard surface.
- `graph-context.js` provides the selection/context API with visibility predicates (`__needGraphNodeAllowed`, `__needGraphEdgeAllowed`, `__needGraphForcedNodes`, `__needGraphTraversalFamilies`) that filters compose through.
- `graph-explore.js` provides type/status/family filters, traversal profiles, the path-to-root BFS (`pathToRoot` — client-side, direction-aware via published `traversalDirection`, constrained by the active profile/family set), and edge provenance popups.
- The build publishes per-relation semantics (`relationSemantics`: family, direction, roles, impact direction) and traversal profiles into every projection JSON (`graph_output.py`), plus optional `change` fields on nodes/edges when the projection is built in `diff` or `impact` mode with a baseline present.
- The mode is decided once per build: `config.graph.mode` (default `catalog`) flows through `build_default_projection`, and `write_default_projection` writes exactly one `default.json`. `{{< need-graph >}}` has no `mode` kwarg — the shortcode loads a projection file and presents what it carries.
- JS is tested the way this project tests everything else: source-level contract assertions (`tests/test_graph_exploration_assets.py`, e.g. load order, "consumes published semantics", the empty-set-is-never-all guard) plus real `quarto render` subprocess tests (`tests/test_quarto_views.py`). There is no jsdom/node harness, and this slice does not introduce one.

## Non-goals (this slice)

- **No new Python semantics.** No new relation kinds, no new traversal algorithm on the Python side, no change to what `select_graph`/`build_projection` compute. The two-node path is computed client-side over the *published* projection using the *published* per-relation direction/family metadata — the exact precedent `pathToRoot` already set and the contract tests already pin. Python remains the semantic authority: the JS algorithm consumes semantics, never defines them.
- **Semantic clustering** — needs its own design (what clusters *mean* must be a published, canonical notion, not a client-side layout heuristic). Later slice.
- **Breadcrumbs, deep-linkable/saved exploration state, fullscreen, SVG/PNG export, mini-map, keyboard-navigation depth, accessibility depth** — all deferred, each its own reviewed slice. They are ergonomics; this slice is analysis depth.
- **Per-query projections in diff/impact modes.** Named-query projections keep their current single-mode behavior; only the *default* view gains published variants. Multi-mode named queries are a follow-on if ever needed.
- **Editing anything.** The explorer stays read-only, as every phase so far.

## Design

### 1. Published variants: catalog, diff, impact — side by side

`write_default_projection` (or the CLI step that calls it) additionally writes two sibling artifacts next to the existing `default.json`:

- `default-diff.json` — the same selection built through `build_diff_overlay`;
- `default-impact.json` — the same selection built through `build_impact_overlay`.

Contract decisions, each following an existing precedent rather than inventing one:

- **Graceful degradation, verbatim from `build_default_projection`'s current rule:** a variant is written only when a baseline actually exists (`load_baseline` succeeds). Without a baseline, the project gets `default.json` alone — exactly what `mode="diff"` does today when the baseline file is missing. No empty or misleading variant is ever published.
- **Same bounded selection.** Variants reuse the same node selection, limits, layout, and seed as the catalog default (the same arguments `build_diff_overlay`/`build_impact_overlay` already accept) — switching modes must never change *what* is being compared, only *how it is annotated*.
- **Deterministic, atomic, stale-safe** like every other artifact in `graph_output.py` (atomic write, stale-variant cleanup keyed to the new filenames).
- **No Lua change is required for emission** — but `views.lua`'s published asset/version bookkeeping and the showcase copy sync follow the existing pattern (the showcase-mirrors-canonical test already enforces this).

The variants are *presentation artifacts* in exactly the sense the docstring on `write_default_projection` already claims for named-query projections: a project that never authors a baseline simply never gets them, and nothing else in the build changes.

### 2. The explorer's mode switcher

A new small module `graph-modes.js` (loaded after `graph-explore.js`, mirroring the existing layered-enhancement load order) adds a mode select to the existing controls row when — and only when — the page actually carries variant data:

- `graph.lua` embeds the catalog projection as today. The variants are *not* inlined into the page (three full projections per graph would bloat every page); instead the build writes them as sibling files and `graph.lua` records their availability (e.g. a `data-need-graph-modes="catalog,diff,impact"` attribute on the container, plus the base URL it can fetch them from). Exact transport (fetch-on-demand vs. embed-if-small) is an implementation-planning decision with one hard constraint: **no new server-side or runtime computation** — the files are pre-rendered, the browser only chooses among them.
- Switching mode replaces the explorer's dataset and rebuilds the graph in place. The current filter/profile/path state is either preserved (filters re-apply; a root path or two-node path that no longer resolves in the new dataset is cleared with an announcement) or reset with an announcement — decided by what the rebuild mechanics make simplest, but never silently: the status region announces the mode and what happened to active analysis state.
- The mode select and its announcements follow the existing `views.tr` en/pt-BR pattern; the `change`-facet coloring, ghost nodes (`removed` entries rendered from baseline fields), and `pathMember` edge styling need **zero new rendering code** — they are already wired in `graph.js` for exactly these field values.
- The semantic table below the canvas must follow the active mode (it is the primary accessible representation; a table describing the catalog while the canvas shows the impact overlay would be worse than no table). The table-rendering path already consumes the projection object, so this is a re-render call on mode switch, not a new table implementation.

### 3. Affected-only visibility (impact mode)

In impact mode the overlay already marks the affected set (`change` on nodes, `pathMember` on explanation edges). The switcher gains a companion toggle, *Affected only*, that composes with the existing visibility predicates — the same `__needGraphNodeAllowed` mechanism the type/status/family filters and forced-path sets already use — to hide everything outside the affected set:

- affected = nodes whose `change` is present and not `"unchanged"`, plus the `pathMember` edges between them;
- the toggle is offered only when the active dataset actually carries change data (catalog mode greys it out or hides it — it must never pretend to filter on absent fields);
- composing with existing filters follows the existing rule: predicates intersect; the empty-intersection-means-empty (never "all") guard the contract tests already pin applies here too;
- clearing the toggle (or switching to catalog mode) restores the full graph.

### 4. Two-node semantic path

The path-to-root button becomes a two-field path tool: the existing focus node (selected by tap/search, exactly as today) is the *start*; a new text input accepts a *target* object id (validated against the current dataset; unknown ids announce and refuse). `Find path` runs a BFS from start to target over the current dataset under the *active profile/family constraints* — the same `directParents`-style edge scan `pathToRoot` uses, extended to walk both directions (a semantic edge is traversable source→target or target→source per its published `traversalDirection`, so an undirected-in-effect search over directed-permitted steps).

- The result reuses the existing path machinery wholesale: `pathNodes`/`pathEdges` forced sets, `need-root-path-*` highlight classes, predicate installation, fit-to-path, and the "Clear path" affordance. One path is active at a time; finding a two-node path replaces an active root path and vice versa (the tool labels the active mode and announces it).
- No path found is an announced fact ("no semantic path under the current traversal profile"), not a silent no-op — matching how the root path already reports failure.
- The BFS deliberately stays client-side and bounded by the already-published projection: the projection is the bounded artifact, the semantics are published per edge, and the algorithm never needs information the JSON does not carry. If a future analysis needs *unpublished* semantics (weights, costs, closure rules), that is the moment it moves to Python — stated here so the boundary is a decision, not drift.

## Invariants honored

- **Python remains semantic authority; the browser consumes projections.** The only Python change is *emitting more pre-rendered artifacts* of machinery that already exists. Every traversal decision the JS makes reads `relationSemantics`/`traversalProfiles` — the same published contract `pathToRoot` and the context module already consume and the contract tests already pin.
- **Progressive enhancement.** A reader with JS disabled gets the static Mermaid/table output exactly as today. A project without a baseline gets no variants and sees no mode switcher. A project with variants but no interaction gets the catalog by default.
- **Bounded projections.** Variants reuse the catalog selection's limits; the affected-only toggle only ever narrows; the path search only ever traverses the published node/edge set.
- **Determinism and versioned artifacts.** New filenames follow the existing `default.json` naming family, atomic-write and stale-cleanup conventions; the availability marker in the HTML is versioned (a `v1`-style suffix like the extension's other flags) so future format changes cannot be silently misread.

## Testing strategy

Same discipline as every phase (failing test first, minimal code, falsify load-bearing checks, full suite green per commit), using the two established JS-verification mechanisms — there is no third one and none is introduced:

- **Source-contract tests** (`tests/test_graph_exploration_assets.py`, extended): load order (base → context → explore → modes); the modes module consumes `relationSemantics` (never redefines direction); the empty-intersection guard appears in the new predicate composition; the availability marker and variant filenames are referenced by their exact versioned names; the pt-BR strings exist for every new `views.tr` pair.
- **Projection-variant tests** (`tests/test_graph_output.py`, extended): a project with a baseline gets all three files with the right `view.mode` values and identical node *sets* across modes (differs only in annotations); without a baseline, only `default.json` exists; stale variants are cleaned; atomicity/determinism re-render byte-identical.
- **Real-render e2e** (`tests/test_quarto_views.py`, extended): a fixture project *with* a checked-in baseline renders, and the built HTML carries the availability marker; a render without a baseline does not. (The existing pattern for authoring a small baseline fixture already exists in the diff/impact overlay tests' fixtures — reuse its shape.)
- **Self-hosted example:** the example project gains a committed baseline and embeds the graph once with modes available, verified through the project's own pre-render + `quarto render` gate, with the pt-BR mirror carrying the same embed. The example's baseline is generated through the documented CLI (never hand-edited), pinned so renders are reproducible.
- **Falsification:** removing the direction check from the two-node BFS must break the direction-aware path test; removing the baseline-existence guard must break the no-baseline variant test; removing the affected-set narrowing must break the affected-only predicate test.

## Open questions for implementation planning (not blocking this design)

- **Transport for variants** — fetch-on-demand vs. embed-if-small: measure the example's actual variant file sizes during planning and pick once; the constraint (pre-rendered, no runtime computation) does not change either way.
- **Rebuild mechanics for mode switch** — destroy-and-recreate the Cytoscape instance vs. swap datasets in place: whichever the instance bookkeeping in `graph.js`/`graph-context.js` makes safest; the contract is the announced, non-silent state handling, not the mechanism.
- **Exact affected-set definition at the edges** — whether nodes *adjacent to* the affected set (e.g. a requirement whose verification changed) belong in the affected-only view or stay hidden: default is strict (changed + path edges only); revisit if the retrofit's real content makes the strict view too sparse to read.
- **Whether the example's committed baseline is generated in the pre-render pipeline or checked in as a fixture**: whichever the existing `make` evidence targets make most reproducible, decided while planning the retrofit task.
