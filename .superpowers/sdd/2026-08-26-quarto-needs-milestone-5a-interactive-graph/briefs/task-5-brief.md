# Task 5: Add the Quarto shortcode and static AST

> Expanded from `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph.md`
> (Task 5 outline) and its user-facing contract. Complete requirement.

## Global Constraints (bind every task)

- Same as Task 2's brief, plus: `needs.json` bytes do not change for a project
  that requests no graph; Lua never evaluates a query string — Python
  prevalidates every option and precomputes every view.
- Do not stop or restart the preview server on 127.0.0.1:8777.

## Requirement

**Files:** `src/quarto_needs/graph_views.py` (new), `src/quarto_needs/cli.py`
(wiring only), `_extensions/quarto-needs/graph.lua` (new),
`_extensions/quarto-needs/shortcodes.lua` (registration),
`tests/test_quarto_graph.py` (new). The book copy of the extension is
refreshed by `make sync-example` (the pre-render tool syncs root → book).

### Python: prevalidated views (`graph_views.py`)

- `parse_graph_shortcodes(text) -> list[dict[str, str]]` — scan `.qmd`
  content for `{{< need-graph ... >}}` invocations; parse Pandoc-style
  `key="value"` / `key=value` attributes; reject unknown option keys.
- Options (the contract's set): `query`, `relations`, `depth`, `layout`,
  `mode`, `baseline`. `view_key(options)` joins non-empty `key=value` pairs
  over the alphabetically fixed key order with `;` — whitespace-stripped,
  insensitive to attribute order; `view_id` = `need-graph-` + first 12 hex of
  SHA-1 over the key. Lua computes the identical key from its kwargs.
- `build_graph_views(root, snapshot, config, *, queries) -> dict | None`:
  for each distinct invocation —
  - validate: mode ∈ catalog/diff/impact; depth integer 1..10; relations
    resolve in the catalog; query name is materialized (unknown → error);
    baseline path required for diff/impact and loadable. Validation failures
    raise `ConfigurationError` — the build exits 2 naming the shortcode.
  - defaults come from `[graph]`: depth, mode, layout, relations, budgets;
    layout option overrides config layout; seed always from config.
  - catalog: seeds = `queries[query]`, selection via `select_graph`,
    projection via `build_projection`. diff/impact: `build_*_overlay` with
    the loaded baseline (guards propagate; the date pin stays the
    milestone-3 pattern: `SOURCE_DATE_EPOCH` in the make target).
  - `GraphLimitExceeded` and engine guard errors become a **recorded
    diagnostic entry** (`{"id", "mode", "error", "facets"}`) — rendered
    visibly by Lua, never an empty container, never a silently truncated
    graph.
  - success writes `.quarto-needs/graphs/<view_id>.json`
    (`render_projection`) and `.quarto-needs/graphs/<view_id>.mmd`
    (`graph_render.mermaid_source`) atomically, and records
    `{"id", "mode", "path", "mermaid"}` (project-relative, forward slashes).
  - returns `{"graphs": {view_key: entry, ...}}` or `None` when the project
    authors no `need-graph` shortcode.
- `cli.build` merges the graphs table into `extensions.quartoNeeds`
  (alongside `queries`/`report`; graphs work with or without a config file);
  `ValueError` from view validation prints and returns 2.

### Lua: `graph.lua` + registration

- `graph.render(graph_payload, kwargs, views, render_png)`:
  - rebuilds the view key from kwargs exactly as Python does; looks the
    entry up in `graph_payload.extensions.quartoNeeds.graphs`;
  - missing entry → visible `need-view-warning` diagnostic ("re-run the
    quarto-needs build");
  - error entry → visible diagnostic carrying the message and facet hints;
  - otherwise reads and decodes the projection JSON, reads the `.mmd`
    source, and emits, through Pandoc AST: a summary paragraph (mode,
    counts against limits, diff/impact counts), the diagram as a PNG figure
    (via the existing `render_mermaid_png` precedent — local nested quarto
    render, no network), the accessible edge table (Source, Relation,
    Target, Change, Impact; impact cells carry the full path, class, and
    distance exactly as `graph_render` formats them), a text legend for the
    markers, and — for `html:js` formats only — the progressive container
    (`div.need-graph-container` with `data-need-graph` = view id and
    `data-projection` = JSON path) wrapping the static content for Task 6.
- `shortcodes.lua` registers `["need-graph"]`.

### Tests (`tests/test_quarto_graph.py`)

- Unit: shortcode parsing (quoted/bare/multiple/unknown key), key
  normalization, artifacts written and schema-valid, diagnostic entries for
  limits, `ConfigurationError` for unknown query/mode/depth/baseline,
  diff/impact views via a real baseline (date pinned), and no `graphs`
  extension plus unchanged `needs.json` when no shortcode is authored.
- Integration (quarto render in a temporary project with the extension
  copied in, after running the Python build): HTML contains the table
  headers, summary counts, the figure, and the container's data attributes
  without executing any JavaScript; DOCX (`word/document.xml`) and PDF
  contain the table and summary; a shortcode whose projection is missing
  renders the visible diagnostic, not an empty page.

## Verification duties

- Falsify: (a) break key parity between Python and Lua (rename one option
  key on the Lua side) → integration render falls into the missing-view
  diagnostic and the HTML test fails; (b) drop the error-entry branch in
  Lua → limit-diagnostic integration assertion fails; (c) Python: skip
  writing the `.mmd` → unit artifact test fails; (d) let `graphs` leak into
  `needs.json` without shortcodes → the bytes-unchanged test fails. Each
  restoration verified by checksum.
- Full suite green, no new warnings.
