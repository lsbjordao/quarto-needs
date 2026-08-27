# Task 2: Add graph view configuration and bounded selection

> Expanded from `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph.md`
> (Task 2 outline) and its user-facing/data contracts. This brief is the complete
> requirement; the execution plan carries only the outline.

## Global Constraints (bind every task)

- Do not add a runtime Python dependency.
- The browser receives only the public projection; projection construction fails closed.
- Graph limits produce a visible narrowing prompt naming actual counts and
  configured limits. They never silently truncate.
- Layout is deterministic: a stored seed and explicit tie-breaking.
- Preserve every existing CLI command, shortcode, exit code, and schema.
  `needs.json` bytes do not change for a project that requests no graph.
- Do not stop or restart the preview server on `127.0.0.1:8777`.

## Requirement

**Files:** `src/quarto_needs/config.py`, `src/quarto_needs/queries.py`,
`src/quarto_needs/graph_projection.py`, `tests/test_graph_selection.py`.

1. **`[graph]` configuration section** (`config.py`), parsed with the same
   unknown-key rejection as every other section:

   ```toml
   [graph]
   max-nodes = 100
   max-edges = 300
   depth = 1
   mode = "catalog"
   layout = "hierarchical"
   seed = 1
   relations = ["implements", "verified-by", "evidenced-by"]
   ```

   - Defaults exactly as shown; `relations` omitted means "every relation the
     catalog publishes".
   - `max-nodes`/`max-edges` are integers ≥ 1; `depth` is an integer in 1..10;
     `mode` is one of `catalog`, `diff`, `impact`; `layout` is a non-empty
     string; `seed` is an integer ≥ 0; `relations` is an array of names that
     must resolve in the relation catalog (authored alias or canonical).
   - The stored allowlist is the deduplicated, sorted tuple of resolved v1
     names.
   - Graph settings are presentation policy, not graph semantics: they are
     **excluded** from `NeedsConfig.canonical_document()` (same ruling as
     `present`), so tweaking a limit never masquerades as a configuration
     change for diff/impact. A test pins this.

2. **Named-query seed evaluation** (`queries.py`):

   - `queries.query_ids(config, snapshot, name) -> tuple[str, ...]` evaluates
     one named query through the existing safe grammar — compile from
     `named_query_sources` (the built-in `approved-requirements` query remains
     available when the name matches it and no user query overrides it), then
     `evaluate`. An unknown name raises `QueryError`. No new grammar, no
     browser evaluator.

3. **Bounded selection** (`graph_projection.py`):

   - `graph_projection.PUBLIC_RELATIONS`: sorted v1 names of every catalog
     relation with `public=True` — the default allowlist.
   - `graph_projection.select_graph(snapshot, *, seeds, relations=(), depth=1,
     limits=None) -> Selection` where `Selection` is a frozen dataclass with
     `node_ids: tuple[str, ...]` and `edges: tuple[tuple[str, str, str], ...]`
     (source, target, v1 relation name).
   - Expansion is undirected over the allowlisted relations only, BFS from the
     seeds (which keep the query's order), each frontier sorted
     case-insensitively with an ASCII tiebreak; a visited set makes cycles
     terminate; seed ids absent from the snapshot are ignored; depth counts
     hops beyond the seeds.
   - Edges are every snapshot relation whose endpoints are both selected and
     whose v1 name is allowlisted, ordered by (source, target, relation)
     case-insensitively.
   - When the selection exceeds a limit, raise
     `graph_projection.GraphLimitExceeded` carrying `actual` counts,
     `limits`, and `suggested_facets`: up to two values per field for
     `type`, `status`, `priority`, and `tags`, each with its node count,
     deterministic order (count descending, then value). Never truncate.
   - An empty selection (query matches nothing) is valid, not an error.

4. **Projection consumption** (`graph_projection.py`):

   - `build_projection` gains optional keyword-only `relations=()` (allowlist;
     empty means `PUBLIC_RELATIONS`, and non-public relations are always
     denied), `layout=None`, and `seed=None`; the latter two serialize into
     `view.layout` / `view.seed` when provided (the schema already allows
     them). Existing call sites and behavior are unchanged.

5. **Tests** (`tests/test_graph_selection.py`): defaults and full parsing;
   rejection of unknown keys and each invalid value class; allowlist
   normalization; fingerprint exclusion; `query_ids` evaluation, default
   query, unknown name; sparse, dense, cyclic, disconnected, high-fanout,
   and empty selections; determinism under seed permutation; node-limit,
   edge-limit, and at-the-boundary cases; facet content of the diagnostic;
   projection consumption of a selection with an allowlist; layout/seed
   serialization with schema validation.

## Verification duties

- Falsify the load-bearing assertions before reporting done: (a) delete the
  allowlist edge filter, (b) delete the limit raise, (c) delete one facet
  field from the suggestions, (d) delete the BFS visited set (cycle test must
  hang, killed by timeout) — each mutation must fail its test, each
  restoration verified by checksum.
- Full suite green with no new warnings; `needs.json` bytes for a project
  without `[graph]` are unchanged (`make sync-example` idempotence still
  holds via the existing gates).
