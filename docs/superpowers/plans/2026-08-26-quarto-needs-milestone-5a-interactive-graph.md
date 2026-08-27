# Quarto-Needs Milestone 5A Interactive Graph Implementation Plan

**Date:** 2026-08-26  
**Status:** Fourth in the committed adoption arc — ready after 4A, 4D
distribution, and 4B are accepted. 4B still comes first for the reason the
amendment gives: the graph must show traceability from authored requirements
into code and tests, not merely redraw links this project already has.  
**Design inputs:** evolution design (contracts and acceptance gates) and the
capability evolution amendment (sequence and commitment). Where they disagree on
ordering, the amendment governs.

> **Note on hardening.** Earlier drafts assumed a separate Milestone 5C for
> security, accessibility, and performance. The amendment dissolves it: keyboard
> operation and an equivalent non-JavaScript representation are acceptance
> criteria for this milestone, not later polish, and performance budgets apply
> as continuous release gates.

## Goal

Deliver an offline-first, accessible `need-graph` experience that uses the same
query, relation, diff, and impact semantics as the CLI. HTML progressively adds
interaction; static formats and JavaScript-disabled HTML retain an equivalent
diagram and edge table.

The differentiating feature is a graph that explains engineering change. A user
can inspect a need, show its neighborhood, highlight a relation path, overlay a
baseline diff, and see why an object is impacted without leaving the rendered
book.

## Non-goals

- Editing requirements or governance state in the browser.
- Sending the full semantic snapshot to the browser.
- Fetching CDN assets or remote graph data at render time.
- Rendering an unbounded project graph and hiding truncated results.
- Reimplementing query, diff, impact, or relation rules in JavaScript.
- Replacing the static fallback with a screenshot of the interactive canvas.

## User-facing contract

```qmd
{{< need-graph
  query="approved-high"
  relations="implements,verified-by,evidenced-by"
  depth="2"
  layout="hierarchical"
  baseline="baselines/quarto-needs.json"
  mode="diff"
>}}
```

The minimal invocation remains `{{< need-graph >}}`. Options are validated in
Python and written into the generated index; Lua never evaluates a query string.

HTML controls include:

- search by ID or title;
- type, status, priority, tag, relation, and change-state facets;
- zoom, fit, reset, and keyboard focus controls;
- one-hop neighborhood expansion inside the already published projection;
- shortest explanatory path between two visible nodes;
- an inspector action using the existing inspector component;
- diff legend and baseline/current toggle when `mode="diff"`;
- impact origin, direct/transitive status, distance, path, and relation labels
  when `mode="impact"`.

Control state may be encoded in the URL fragment only when it contains public
IDs and declared facet values. It never stores titles, attributes, source
locations, or arbitrary query text.

## Data contracts

### Public projection

Add `schemas/graph-public-v1.schema.json` and a Python model/writer with this
logical shape:

```json
{
  "schemaVersion": "graph-public-v1",
  "view": {
    "id": "stable-render-local-id",
    "layout": "hierarchical",
    "mode": "catalog",
    "limits": {"nodes": 100, "edges": 300}
  },
  "nodes": [
    {
      "id": "REQ-1",
      "title": "Publishable title",
      "type": "requirement",
      "status": "approved",
      "priority": "high",
      "tags": ["iam"],
      "href": "requirements.html#req-1",
      "change": "modified"
    }
  ],
  "edges": [
    {
      "source": "REQ-1",
      "target": "TC-1",
      "relation": "verified-by",
      "label": "verified by",
      "change": "unchanged",
      "pathMember": true
    }
  ],
  "impact": []
}
```

Only ID, title, type, status, priority, allowed tags, publishable relations, and
resolved public hrefs are emitted by default. `change` and `impact` are included
only when their modes are requested. Removed nodes use baseline public fields,
are visually and textually marked as removed, and never regain fields denied by
the current publication policy.

### Static equivalence

For every graph instance the renderer emits:

1. a deterministic static graph asset with node labels and a legend;
2. an accessible table containing source, relation, target, change state, and
   impact explanation where applicable;
3. a summary with node/edge counts and any narrowing guidance;
4. the progressive HTML container and reduced JSON projection.

“Equivalent” means the same selected nodes, relations, change classifications,
and impact paths. It does not require identical spatial layout.

## Task 1 — Freeze projection and privacy contracts

**Files:** `src/quarto_needs/graph_projection.py`,
`schemas/graph-public-v1.schema.json`, `tests/test_graph_projection.py`

- Write failing tests for stable ordering, schema validation, allowed fields,
  unsafe custom attributes, local paths, source locations, bodies, and baseline
  ghost nodes.
- Add an adversarial fixture whose denied values are unique search tokens.
- Implement a small immutable projection model and atomic JSON writer.
- Falsify every deny assertion by temporarily exposing the field and proving the
  test fails.

## Task 2 — Add graph view configuration and bounded selection

**Files:** `src/quarto_needs/config.py`, `src/quarto_needs/queries.py`,
`src/quarto_needs/graph_projection.py`, `tests/test_graph_selection.py`

- Define defaults: 100 nodes, 300 edges, depth 1, catalog mode, deterministic
  layout seed, and an explicit relation allowlist.
- Reuse named-query evaluation; do not introduce a browser query evaluator.
- Return a structured `GraphLimitExceeded` diagnostic containing actual counts,
  configured limits, and suggested facets.
- Test sparse, dense, cyclic, disconnected, high-fanout, and empty selections.

## Task 3 — Compose catalog, diff, and impact overlays

**Files:** `src/quarto_needs/graph_projection.py`,
`tests/test_graph_overlays.py`

- Map the existing `DiffReport` classifications onto nodes and relations.
- Keep removed objects and relations as baseline ghosts in diff mode.
- Map existing `ImpactReport` paths without recomputing traversal in the view.
- Test configuration/reference-date guards and `--recompute-with current`
  behavior through the existing engines.
- Assert that projection order remains byte-identical across input permutations.

## Task 4 — Generate the static fallback

**Files:** `src/quarto_needs/graph_render.py`,
`tests/test_graph_render.py`

- Produce a deterministic graph description and accessible edge-table data.
- Use a local renderer selected during implementation; pin its version and
  document its license. Do not add a required network call.
- Keep text labels, change markers, and relation labels visible without relying
  on color.
- Add golden tests plus a semantic assertion that the asset/table/projection
  contain identical node and edge sets.

## Task 5 — Add the Quarto shortcode and static AST

**Files:** `examples/book/_extensions/quarto-needs/shortcodes.lua`,
`examples/book/_extensions/quarto-needs/graph.lua`,
`examples/book/_extensions/quarto-needs/_extension.yml`,
`tests/test_quarto_graph.py`

- Parse prevalidated view identifiers and options from the generated index.
- Emit semantic figure, legend, summary, table, narrowing message, and progressive
  container through Pandoc AST.
- Ensure HTML without JavaScript, PDF, and DOCX contain the essential graph data.
- Add malformed/missing projection tests that render a visible diagnostic rather
  than an empty container.

## Task 6 — Build the local interactive client

**Files:** `examples/book/_extensions/quarto-needs/graph.js`,
`examples/book/_extensions/quarto-needs/graph.css`, vendored dependency files,
`tests/test_graph_assets.py`

- Vendor and checksum a pinned Cytoscape.js release and record license metadata.
- Initialize only after the static fallback and projection validate successfully.
- Implement search, facets, fit/reset, selection, neighborhood, path highlighting,
  diff toggle, impact explanation, and inspector integration.
- Use deterministic node ordering and seed. Persist only safe state in the URL
  fragment.
- Hide the canvas from assistive technology when its information is already
  represented by the synchronized semantic table.

## Task 7 — Accessibility and interaction conformance

**Files:** `tests/test_graph_accessibility.py`, browser-level test fixtures

- Verify complete keyboard operation, visible focus, control names, status
  announcements, legend text, contrast, reduced motion, and dialog focus return.
- Verify the fallback remains visible if script loading or initialization fails.
- Verify filters update the semantic table and announced counts, not only the
  canvas.
- Run automated accessibility checks and record a manual keyboard protocol.

## Task 8 — Aegis showcase and author documentation

**Files:** Aegis QMD/configuration, `README.md`, `ARCHITECTURE.md`,
`CONTRIBUTING.md`

- Add catalog, diff, and impact graph examples with named queries.
- Include one deliberately large fixture that exercises visible limit guidance.
- Document privacy projection, offline assets, configuration, static behavior,
  baseline modes, troubleshooting, and regeneration commands.
- Keep the default published Aegis book passing its strict quality profile.

## Task 9 — Performance and security gates

**Files:** `tests/test_graph_performance.py`, `tests/test_graph_security.py`, CI

- Benchmark 100/300, 1,000/3,000, dense, cyclic, and high-fanout synthetic graphs.
  The default interactive cap remains 100/300; larger figures require an explicit
  project override and still receive a warning.
- Establish budgets for projection generation, asset size, initialization, facet
  latency, and memory before optimizing.
- Test HTML/JSON escaping, malicious titles/IDs/tags, path traversal, unsafe hrefs,
  prototype-pollution keys, and denied-field token absence.
- Run the graph without external network access and under a restrictive content
  security policy.

## Acceptance gate

- Full Python and Lua helper suites pass with no xfails or warnings.
- Aegis renders cleanly in HTML, PDF, and DOCX.
- The HTML graph works with network access disabled.
- Disabling JavaScript preserves the selected nodes, relations, change states,
  impact paths, legend, and counts.
- Keyboard-only operation completes search, filtering, selection, path display,
  and inspector open/close.
- Adversarial denied values do not occur in any shipped browser asset.
- Repeated builds with fixed semantic inputs and layout seed are byte-identical.
- Limits are visible and actionable; no selection is silently truncated.
- Catalog, diff, and impact graph contents match the corresponding engine
  reports exactly.

