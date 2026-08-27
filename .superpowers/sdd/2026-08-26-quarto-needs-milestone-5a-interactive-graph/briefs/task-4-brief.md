# Task 4: Generate the static fallback

> Expanded from `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph.md`
> (Task 4 outline) and its static-equivalence contract. This brief is the
> complete requirement; the execution plan carries only the outline.

## Global Constraints (bind every task)

- Same as Task 2's brief. Additionally, from the milestone contract: static
  output is not a lesser fallback — every graph instance gets a deterministic
  diagram, an accessible table, and a summary with counts; "equivalent" means
  the same nodes, relations, change classifications, and impact paths, not
  identical layout. Text labels, change markers, and relation labels must stay
  visible **without relying on color**.

## Requirement

**Files:** `src/quarto_needs/graph_render.py`, `tests/test_graph_render.py`,
golden fixtures under `tests/fixtures/graph/`.

**Renderer decision (made during implementation, as the outline directs):**
Mermaid.js as bundled with Quarto, rendered locally by Quarto's built-in
mermaid support — the project itself adds no network call. License: MIT.
Verified against the locally installed Quarto 1.8.26; the emitted source is
plain `flowchart LR` text. The Python side emits source text only; it never
invokes a browser or a JS runtime.

1. **`graph_render.mermaid_source(projection) -> str`** — deterministic
   Mermaid source from a `GraphProjection`, following the conventions the
   extension's Lua already uses (`_extensions/quarto-needs/views.lua`):
   node ids as `need_` + UTF-8 hex of the public id (collision-free),
   labels escaped `"`→`'`, `\`→`/`, newlines/tabs→space, edge syntax
   `A -->|"label"| B`.

   - Node label: `"ID · Title<br/>type · status"` plus ` · priority` when
     present; change markers are **text**, appended as ` — modified`,
     ` — added`, ` — relocated`, ` — removed` (ghosts included).
   - Edge label: the relation label, with `(added)` / `(removed)` when the
     edge carries a change and `(path)` when it is an impact path member.
   - Lines follow the projection's canonical node/edge order; two renders of
     the same projection are byte-identical.

2. **`graph_render.EdgeRow`** (frozen dataclass: `source`, `relation`,
   `target`, `change`, `impact`) and
   **`graph_render.edge_table_rows(projection) -> tuple[EdgeRow, ...]`** —
   one row per projected edge, carrying source id, relation label, target
   id, change state text, and the impact explanation: for every impacted
   entry whose path uses that edge (consecutive pair, either direction),
   `"A → B → C (direct, 1 hop)"`-style text, joined with `"; "`; empty
   outside impact paths.

3. **`graph_render.summary_entries(projection) -> tuple[tuple[str, str], ...]`**
   — display pairs: mode; node and edge counts against the configured limits
   (`"5 / 100"`); in diff mode, counts of added/removed/modified/relocated
   nodes; in impact mode, counts of impacted, direct, and transitive entries.

4. **Tests:** golden byte-comparison of the Mermaid source for a catalog-mode
   projection (the adversarial fixture) and a diff-mode projection (the V1/V2
   overlay scenario); a semantic assertion that the diagram, the table rows,
   and the projection contain identical node and edge sets (the diagram is
   parsed back, not eyeballed); change markers present as text; hostile
   labels (quotes, backslashes, newlines, `-->`) escaped; impact explanations
   on path rows only; ghost nodes and ghost edges present and marked removed;
   summary counts correct for both modes; double render byte-identical.

## Verification duties

- Falsify: (a) reverse the node iteration order → golden test fails;
  (b) delete the change-marker text → marker test fails; (c) delete the
  escaping → hostile-label test fails; (d) build table rows from nodes
  instead of edges → the set-equality assertion fails. Each restoration
  verified by checksum.
- Full suite green with no new warnings.
