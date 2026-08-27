# Task 3: Compose catalog, diff, and impact overlays

> Expanded from `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph.md`
> (Task 3 outline) and its data contracts. This brief is the complete
> requirement; the execution plan carries only the outline.

## Global Constraints (bind every task)

- Same as Task 2's brief (no runtime dependency, public projection only,
  limits never truncate silently, deterministic layout/seed, preserve every
  existing CLI command/shortcode/exit code/schema, `needs.json` unchanged for
  a project that requests no graph).

## Requirement

**Files:** `src/quarto_needs/graph_projection.py`, `tests/test_graph_overlays.py`.

The overlay layer consumes the existing engines and never re-derives their
classifications or traversal: `diff.compare` produces the change classes,
`impact.analyze` produces the paths.

1. **Diff overlay** —
   `build_diff_projection(baseline_payload, snapshot, config, *, node_ids,
   view_id, recompute=False, relations=(), limits=None, layout=None,
   seed=None) -> GraphProjection` with `mode="diff"`:

   - Runs `diff.compare(..., recompute=recompute)`; `DiffError` propagates.
   - Current nodes (from `node_ids`) carry `change` by precedence
     `added > modified > relocated > unchanged` (an object can be both
     modified and relocated; content change is the stronger signal).
   - Every object in `report.removed_objects` becomes a **ghost node** built
     from the baseline's public fields only (id, title, type, status,
     priority and tags re-derived from baseline attributes with the same
     normalization `ObjectRecord` uses, anchor href, `change="removed"`).
     Ghost bodies, rationales, locations, and arbitrary attributes never
     re-enter through the ghost path.
   - Current edges (allowlisted, both endpoints selected) carry
     `change="added"` when their `(source, authored_name, target)` tuple is
     in `report.added_relations`, else `"unchanged"`. Representation changes
     are informational and stay `"unchanged"`.
   - Every entry in `report.removed_relations` with both endpoints in the
     extended node set (selected ∪ ghosts) becomes a **ghost edge** with
     `change="removed"`, its relation resolved through the current catalog
     (authored name as fallback) and the catalog's direct label.
   - Ghost nodes and ghost edges count toward the limits;
     `GraphLimitExceeded` carries actual counts including ghosts.
   - Node order: snapshot order for current nodes, ghosts appended sorted
     (casefold, ASCII tiebreak); edges: snapshot order, ghost edges appended
     sorted by (source, target, relation). Byte-stable across input
     permutations.

2. **Impact overlay** —
   `build_impact_projection(baseline_payload, snapshot, config, *, node_ids,
   view_id, recompute=False, relations=(), limits=None, layout=None,
   seed=None) -> GraphProjection` with `mode="impact"`:

   - Runs `impact.analyze(..., recompute=recompute)`; `ImpactError`
     propagates unchanged — the overlay never swallows the configuration or
     reference-date guards, and never re-runs the traversal itself.
   - `report.impacted` entries map one-to-one onto `PublicImpactEntry`
     (id, origin, distance, path, classification).
   - The node set is the selection plus every id on an impacted path; nodes
     that exist only in the baseline (removed but still explainable) are
     ghosts built exactly as in diff mode.
   - Current edges among that node set carry `pathMember=True` when their
     endpoints are consecutive on some impacted path (in either direction);
     non-path edges carry no marker.
   - Limits apply as in diff mode.

3. **Tests** (`tests/test_graph_overlays.py`): full change classification
   (added/modified/relocated/unchanged nodes, added/removed edges, ghost
   node fields); ghost privacy (a body canary from the baseline must not
   reach the serialized overlay); schema validation of both modes; guards —
   diff builds across configuration and reference-date changes (notices are
   the engine's, suppression does not affect content classes), impact
   refuses without `recompute=True` and traverses with it, and a `[graph]`-
   only configuration change trips neither guard; limits raised with ghosts
   counted; projection bytes identical across authored-declaration
   permutations for both modes.

## Verification duties

- Falsify: (a) delete the ghost-construction field allowlist (let a private
  baseline field through) → canary test must fail; (b) delete the
  added-relation edge marking → diff test must fail; (c) delete the
  pathMember marking → impact test must fail; (d) delete the ghost-inclusive
  limit accounting → limits test must fail. Each restoration verified by
  checksum.
- Full suite green with no new warnings.
