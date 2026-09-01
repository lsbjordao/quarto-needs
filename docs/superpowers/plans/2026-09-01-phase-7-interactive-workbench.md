# Phase 7 — Interactive graph workbench (first slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two gaps between the Phase 7 roadmap's "bounded engineering analysis" promise and what the explorer can do today: (1) a reader cannot ask "what changed since the baseline, and what does it affect?" interactively — diff/impact overlays exist only as build-time projection modes chosen by `[graph] mode`; (2) the explorer cannot answer "how are A and B related?" — it can only walk path-to-root. This slice publishes a compact, pre-rendered **overlay artifact** (change annotations + impact paths + ghosts, derived from the *same* built overlay projections Python already computes), embeds it in `need-graph` pages, and adds a `graph-modes.js` module giving the reader a Catalog/Changes/Impact switcher, an *Affected only* visibility toggle, and — deferring the spec's other items — nothing else.

**Note on scope vs. the spec:** the spec's shortest-path-between-two-nodes item was **descoped from this slice during planning** after re-reading `build_impact_overlay`: the impact view is already "affected-only by construction" (it publishes exactly the propagation subgraph), so the switcher delivers the analysis value with far less new JS surface. The two-node path stays in the spec as this phase's next slice; this plan delivers the baseline-comparison half. The spec file is not edited (it is the proposed record); this note is the planning-time ruling.

**Architecture:** Python emits ONE new artifact per project when a baseline exists: `.quarto-needs/graphs/need-graph-1-overlays.json` — `{"schemaVersion": "need-graph-overlays-v1", "diff": {node/edge change maps + ghosts}, "impact": {entries + path pairs + ghosts}}` — derived by *extracting annotations from the already-built* `build_diff_overlay`/`build_impact_overlay` projections (never a third derivation path, so the artifact cannot drift from what the overlays actually show). `graph.lua` embeds it as a second `<script type="application/json" data-need-graph-overlays>` tag next to the existing projection tag — no fetch, no `resources` config, works over `file://` (the artifact is size-proportional to *what changed*, not to the graph). New `graph-modes.js` (loaded after `graph-explore.js`) applies/clears annotations in place on the live Cytoscape instance — **no dataset rebuild, no re-initialization of the context/explore enhancements** — and composes with existing filters through the established shared-state-slot pattern (`__needGraph*` container slots consumed by `graph-explore.js`'s predicate owner).

**Tech Stack:** Python 3 (stdlib only), TOML config, Lua (Quarto/Pandoc filter), vanilla browser JS over the vendored Cytoscape.

**Spec:** `docs/superpowers/specs/2026-09-01-phase-7-interactive-workbench-design.md`

## Global Constraints

- **Python remains the semantic authority; the browser consumes projections.** Every annotation the JS applies is a value Python pre-computed and wrote into the artifact. The JS never decides what "changed" or "impacted" means — it presents. (Vision binding invariants.)
- **Progressive enhancement.** No baseline → no artifact → no mode UI; the graph renders exactly as today. JS disabled → static table/Mermaid as today.
- **No new traversal/derivation in JS or a third one in Python.** The artifact extracts from the built overlay projections; the predicate composition reuses the established slot pattern; the empty-intersection-means-empty (never "all") guard applies to the new affected-only check (the contract tests already pin this rule for the existing slots).
- Every commit: full `pytest` suite green, no GitHub Actions dependency (verify everything locally).
- TDD throughout: failing test first, watch it fail for the stated reason, minimal code, watch it pass, commit in the project's established style. Falsify load-bearing checks (break them; confirm the test catches it).
- **Known, deliberate simplification #1 (flag, don't hide):** the static `.need-graph-table` is rendered by Lua at build time from the catalog projection and **stays the catalog table** in every mode. Rather than duplicate the table builder in JS (drift risk, new surface), `graph-modes.js` labels it honestly when a non-catalog mode is active (a visible caption note + status announcement: the table reflects the catalog baseline; popups carry the live annotations). A JS table re-render is the named follow-on.
- **Known, deliberate simplification #2:** overlays exist for the **default view only** (`need-graph-1`), not for named-query projections. Multi-mode named queries are a follow-on if ever needed.
- **Known, deliberate simplification #3:** impact-mode node popups are not enriched with distance/path/classification rows in this slice (the node popup builder lives in `graph.js` and enrichment means touching its body assembly). Distance/classification are announced on selection; popup enrichment is a named follow-on.
- Determinism discipline: the overlays artifact must be byte-identical across re-runs on an unchanged tree (the overlay projections already guarantee this; the extraction is pure).

---

### Task 1: `[graph] baseline` — a config key pointing at the comparison baseline

**Files:**
- Modify: `src/quarto_needs/config.py` (`GraphConfig` dataclass ~line 83, the `[graph]` parser ~lines 501-553)
- Modify: `tests/test_graph_selection.py`

**Interfaces:**
- Produces: `GraphConfig.baseline: str | None = None`. `[graph] baseline = "baselines/quarto-needs.json"` — optional; absent means the historical default path `.quarto-needs/baseline.json` (unchanged behavior). Validated like its siblings: present ⇒ non-empty string, else `_fail`. Added to the allowed-keys list (line 501). Like every other `[graph]` key it must **not** change the configuration fingerprint (it names a presentation artifact, not semantics — the existing test at line 123 pins exactly this property).

- [ ] **Step 1: Write the failing tests**

In `tests/test_graph_selection.py`: extend `test_graph_section_parses_every_key` (line 76) to also author `baseline = "baselines/custom.json"` and assert `config.graph.baseline == "baselines/custom.json"`; extend `test_graph_rejects_invalid_values` (line 117, parametrized) with a `baseline = ""` case (empty string must be rejected); extend `test_graph_rejects_unknown_keys` only if it enumerates keys explicitly (read it first — if it asserts an unknown key is rejected, no change needed; do not weaken it). Extend `test_graph_settings_do_not_change_the_configuration_fingerprint` (line 123) to include `baseline` among the settings it proves fingerprint-neutral. Match each test's existing fixture/parametrize style exactly — read the file's helpers before editing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_graph_selection.py -v`
Expected: FAIL — `GraphConfig` has no `baseline` attribute (`AttributeError`), the empty-string case is not rejected (or the key is rejected as unknown), and the fingerprint test's new key has no effect to observe (this one may already pass; read the result and note it).

- [ ] **Step 3: Implement**

In `config.py`: add `baseline: str | None = None` to `GraphConfig`; add `"baseline"` to the allowed-keys tuple; parse after `seed`:

```python
    baseline = raw.get("baseline")
    if baseline is not None and (not isinstance(baseline, str) or not baseline.strip()):
        raise _fail("[graph] baseline must be a non-empty string when present")
```

and pass `baseline=baseline` into the `GraphConfig(...)` construction. Check whether `GraphConfig` is constructed anywhere else positionally (`grep -rn "GraphConfig(" src/ tests/`) — a new field with a default is safe for keyword construction only; fix any positional construction the grep finds.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_graph_selection.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. (The fingerprint stability means no golden fixture anywhere should change; if one does, investigate before touching it.)

- [ ] **Step 6: Commit**

```bash
git add src/quarto_needs/config.py tests/test_graph_selection.py
git commit -m "$(cat <<'EOF'
feat: add [graph] baseline as the comparison-baseline config key

A project's comparison baseline is a curated, tracked artifact (the
book example keeps one under baselines/), not the scratch
.quarto-needs/baseline.json the build writes — naming it in config
lets the overlay artifact (next commit) find it without repurposing
the default path. Presentation-only: deliberately fingerprint-neutral
like every other [graph] key.
EOF
)"
```

---

### Task 2: `build_graph_overlays` — extract the annotation artifact from the built overlays

**Files:**
- Modify: `src/quarto_needs/graph_output.py`
- Modify: `tests/test_graph_assets.py` (this is where `write_default_projection` is tested — `test_default_projection_is_written_and_embeds_projection` at line 121; reuse its `FIXTURE` project fixture and `analyze_project`/`load_config` style)

**Interfaces:**
- Consumes: `build_diff_overlay`/`build_impact_overlay` (same args `build_default_projection` already passes: the `_selection(snapshot, config)` node set, `_limits(config)`, `config.graph.relations`, layout, seed), `load_baseline`/`BaselineError` (already imported), `diff_module`/`impact_module` result shapes via the built projections' public fields (`PublicNode.change`, `PublicEdge.change`, `PublicEdge.path_member`, `GraphProjection.impact: tuple[PublicImpactEntry, ...]`).
- Produces: `def build_graph_overlays(snapshot, config, *, baseline_payload) -> dict` returning:

```python
{
    "schemaVersion": "need-graph-overlays-v1",
    "view": "default",  # DEFAULT_VIEW_ID, for diagnostics only
    "diff": {
        "nodes": {"<id>": "added" | "modified" | "relocated"},   # change != unchanged
        "edges": [["<source>", "<relation>", "<target>", "added"]],
        "ghostNodes": [ ...PublicNode.to_dict() shapes..., ],     # change == "removed"
        "ghostEdges": [ ...PublicEdge.to_dict() shapes..., ],
    },
    "impact": {
        "entries": [ ...PublicImpactEntry.to_dict() shapes..., ],
        "pathEdges": [["<source>", "<relation>", "<target>"], ...],  # path_member edges
        "ghostNodes": [...], "ghostEdges": [...],
    },
}
```

and `def write_graph_overlays(root, snapshot, config) -> Path | None` — loads the baseline from `config.graph.baseline` (root-relative) or `DEFAULT_BASELINE_PATH`; no baseline ⇒ returns `None` and writes nothing (the spec's graceful-degradation rule, verbatim). Called from `write_default_projection` after the default projection is written. Deterministic: sorted keys everywhere the projections already sort; `json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True)` like every sibling artifact.

- [ ] **Step 1: Read the overlay builders' tests to copy the baseline fixture style**

`tests/test_graph_overlays.py` builds small projects plus baseline payloads (`test_diff_overlay_classifies_every_change` line 109, `test_impact_overlay_maps_report_paths_onto_the_projection` line 256). Read those two tests fully and copy their project-authoring + `build_baseline`-style fixture mechanics for the new tests here — do not invent a second fixture style. Also read `graph_output.py`'s `_selection`/`_limits` helpers and `write_default_projection`'s current body (lines 270-300) before editing.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_graph_assets.py` (fixtures/adaptations from Step 1):

```python
def test_write_graph_overlays_extracts_annotations_from_the_built_overlays(tmp_path):
    # project + baseline per the Step 1 fixture style, with at least:
    # one added object, one modified, one removed (ghost), one added relation,
    # one impacted descendant reachable through an explicit path
    ...
    baseline_payload = ...  # loaded via quarto_needs.baseline.load_baseline
    overlays = graph_output.build_graph_overlays(result.snapshot, config, baseline_payload=baseline_payload)

    assert overlays["schemaVersion"] == "need-graph-overlays-v1"
    assert overlays["diff"]["nodes"]["<added-id>"] == "added"
    assert overlays["diff"]["nodes"]["<modified-id>"] == "modified"
    assert any(ghost["id"] == "<removed-id>" and ghost["change"] == "removed"
               for ghost in overlays["diff"]["ghostNodes"])
    assert ["<src>", "<rel>", "<dst>", "added"] in overlays["diff"]["edges"]
    assert overlays["impact"]["entries"], "impacted objects appear with paths"
    entry = next(e for e in overlays["impact"]["entries"] if e["id"] == "<impacted-id>")
    assert entry["origin"] == "<origin-id>" and entry["path"][0] == "<origin-id>"
    assert any(rel == "<rel>" for rel, *_ in
               [[e[0], e[1], e[2]] for e in overlays["impact"]["pathEdges"]])


def test_write_graph_overlays_is_a_no_op_without_a_baseline(tmp_path):
    # same project, no baseline file anywhere
    assert graph_output.write_graph_overlays(tmp_path, result.snapshot, config) is None
    assert not (tmp_path / ".quarto-needs" / "graphs" / "need-graph-1-overlays.json").exists()


def test_write_default_projection_writes_the_overlays_artifact_when_a_baseline_exists(tmp_path):
    # project + baseline; then the real entry point:
    target = graph_output.write_default_projection(tmp_path, result.snapshot, config)
    overlays_path = target.parent / "need-graph-1-overlays.json"
    assert overlays_path.is_file()
    payload = json.loads(overlays_path.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == "need-graph-overlays-v1"


def test_write_graph_overlays_honors_the_configured_baseline_path(tmp_path):
    # config with [graph] baseline = "baselines/quarto-needs.json" (Task 1's key);
    # baseline written there; artifact written and identical to the default-path run
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_graph_assets.py -k overlays -v`
Expected: FAIL with `AttributeError: ... has no attribute 'build_graph_overlays'` / `'write_graph_overlays'`.

- [ ] **Step 4: Implement**

In `graph_output.py`, near `write_default_projection`:

```python
OVERLAYS_SCHEMA = "need-graph-overlays-v1"


def build_graph_overlays(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    baseline_payload: Mapping[str, object],
) -> dict[str, object]:
    """The browser-facing annotation artifact, extracted from the *built*
    overlay projections — never re-derived. Whatever Context/Container-style
    drift a future change to the builders introduces, this artifact cannot
    disagree with what the overlays themselves show, because it is what they
    show."""
    selection = _selection(snapshot, config)
    node_ids = selection.node_ids
    common = dict(
        view_id=DEFAULT_VIEW_ID, recompute=True, relations=config.graph.relations,
        limits=_limits(config), layout=config.graph.layout, seed=config.graph.seed,
    )
    diff_view = build_diff_overlay(baseline_payload, snapshot, config, node_ids=node_ids, **common)
    impact_view = build_impact_overlay(baseline_payload, snapshot, config, node_ids=node_ids, **common)

    diff_nodes = {n.id: n.change for n in diff_view.nodes if n.change not in (None, "unchanged")}
    diff_edges = [
        [e.source, e.relation, e.target, e.change]
        for e in diff_view.edges if e.change not in (None, "unchanged")
    ]
    return {
        "schemaVersion": OVERLAYS_SCHEMA,
        "view": DEFAULT_VIEW_ID,
        "diff": {
            "nodes": diff_nodes,
            "edges": diff_edges,
            "ghostNodes": [n.to_dict() for n in diff_view.nodes if n.change == "removed"],
            "ghostEdges": [e.to_dict() for e in diff_view.edges if e.change == "removed"],
        },
        "impact": {
            "entries": [entry.to_dict() for entry in impact_view.impact],
            "pathEdges": [
                [e.source, e.relation, e.target]
                for e in impact_view.edges if e.path_member
            ],
            "ghostNodes": [n.to_dict() for n in impact_view.nodes if n.change == "removed"],
            "ghostEdges": [e.to_dict() for e in impact_view.edges if e.change == "removed"],
        },
    }
```

(Verify field names against the actual dataclasses before writing — `PublicEdge.path_member`, `GraphProjection.impact`, `PublicImpactEntry` fields at `graph_projection.py:89`; ghost edges in the diff view carry `change="removed"` via `_ghost_edge` — confirm, and adjust the filter to whatever the built view actually marks them with.)

`write_graph_overlays(root, snapshot, config)`: resolve `candidate = root / config.graph.baseline if config.graph.baseline else root / DEFAULT_BASELINE_PATH`; `try: baseline_payload = load_baseline(candidate) except BaselineError: return None`; build; write atomically to `root / ".quarto-needs" / "graphs" / f"{DEFAULT_VIEW_ID}-overlays.json"` with the same `_atomic_text` + `json.dumps` conventions as `write_default_projection`; return the path. Call it from `write_default_projection` right after the default target is written (ignore its return or log nothing — silent optional artifact, matching named-query projections' "unavailable beats failed build" rule).

- [ ] **Step 5: Falsify the no-third-derivation claim**

Temporarily change `diff_nodes` to `{"ADV-1": "modified"}` (hardcoded): `test_write_graph_overlays_extracts_annotations_from_the_built_overlays` must FAIL on the wrong classification. Revert. (This pins that classifications come from the built view, not local logic.)

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. Byte-identical determinism is inherited from the builders (their own permutation tests already pin it); if any unrelated test now fails, the most likely cause is `write_default_projection`'s new baseline probe touching a fixture that has a stray baseline file — read the failure before changing anything.

- [ ] **Step 7: Commit**

```bash
git add src/quarto_needs/graph_output.py tests/test_graph_assets.py
git commit -m "$(cat <<'EOF'
feat: publish the graph overlay annotation artifact

One compact JSON next to the default projection when a baseline
exists: diff change maps + ghosts, impact entries + explanation-path
edges + ghosts. Extracted from the built overlay projections rather
than re-derived, so the browser can never show annotations that
disagree with what the overlays themselves compute. Size is
proportional to what changed, not to the graph.
EOF
)"
```

---

### Task 3: `graph.lua` embeds the overlay artifact when present

**Files:**
- Modify: `_extensions/quarto-needs/graph.lua` (the projection load + embed block, lines ~220-320)
- Modify: `tests/test_graph_assets.py` (Lua source-contract tests; `test_graph_lua_registers_the_shortcode` at line 104 is the style)

**Interfaces:**
- Consumes: `load_projection`-style file reading (graph.lua already reads `need-graph-1.json` — reuse its exact io/pcall pattern), `pandoc.json.encode` for embedding (line 298 precedent).
- Produces: when the sibling file `"<view_id>-overlays.json"` exists next to the loaded projection, embed `<script type="application/json" data-need-graph-overlays="{instance_id}">{json}</script>` right after the existing `data-need-graph-data` script. Absent file ⇒ embed nothing (presence of the script tag IS the availability signal — no extra marker attribute to drift).

- [ ] **Step 1: Write the failing source-contract test**

In `tests/test_graph_assets.py`, following the existing Lua-contract tests' read-and-assert style:

```python
def test_graph_lua_embeds_the_overlay_artifact_when_present() -> None:
    lua = read(EXTENSION, "graph.lua")
    assert "data-need-graph-overlays" in lua
    assert '-overlays.json"' in lua  # the sibling-file naming convention
    # Embedded as JSON, never interpolated into HTML unescaped:
    assert "pandoc.json.encode" in lua
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_graph_assets.py -k lua_embeds_the_overlay -v`
Expected: FAIL (no `data-need-graph-overlays` in graph.lua).

- [ ] **Step 3: Implement**

In `graph.lua`, immediately after the existing projection `data_script` is built (line ~318): attempt to read `<view_id>-overlays.json` from the same directory with the same io.open/pcall-decode pattern the projection load uses; on success, build a second raw block:

```lua
  local overlays_script = nil
  local overlays_path = graph_dir .. "/" .. view_id .. "-overlays.json"
  local overlays_file = io.open(overlays_path, "rb")
  if overlays_file then
    local overlays_contents = overlays_file:read("*a"); overlays_file:close()
    local overlays_ok, overlays_decoded = pcall(pandoc.json.decode, overlays_contents)
    if overlays_ok and type(overlays_decoded) == "table" then
      local overlays_json = pandoc.json.encode(overlays_decoded)
      overlays_script = pandoc.RawBlock("html",
        '<script type="application/json" data-need-graph-overlays="' .. instance_id .. '">'
        .. overlays_json .. '</script>')
    end
  end
```

and append it to the returned block list right after `data_script` (match however `data_script` is appended — copy that exact mechanism). Match the actual local names (`graph_dir`, `view_id`) from the file — read lines 215-320 first and use its variables, do not guess names.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_graph_assets.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add _extensions/quarto-needs/graph.lua tests/test_graph_assets.py
git commit -m "$(cat <<'EOF'
feat: embed the overlay artifact into need-graph pages

The sibling overlays file rides along when it exists; its script
tag's presence is the browser-side availability signal, so there is
no marker attribute to drift out of sync. No fetch, no resource-path
config, works over file:// — the same embed-not-link choice the
projection itself already made.
EOF
)"
```

---

### Task 4: `graph-modes.js` — the module, mode switcher, and Changes mode

**Files:**
- Create: `_extensions/quarto-needs/graph-modes.js`
- Modify: `_extensions/quarto-needs/views.lua` (scripts list; version `0.1.5` → `0.1.6`)
- Modify: `examples/book/_extensions/quarto-needs/` (the showcase copy — sync `graph-modes.js` + `views.lua` + `graph.lua`; `make sync-example` may do this — check the Makefile target and use it)
- Modify: `tests/test_graph_exploration_assets.py` (load order + semantics contracts)
- Modify: `tests/test_graph_assets.py` (`test_graph_js_ships_expected_markers`, showcase-mirrors-canonical)

**Interfaces:**
- Consumes: the overlays script tag (`data-need-graph-overlays`), the live `cy` instance (`canvas.__quartoNeedsCy`), the status region (`[data-need-graph-status]`), the color facet select (`.need-graph-color`, values include `"change"` — graph.lua line 310), the container slot pattern (`container.__needGraph*`), and the node/edge data-field shape `graph.js` builds at init (id, label, type, status, href, change — read graph.js lines 85-100 and copy field construction exactly for ghost elements).
- Produces: a mode select in the controls row (Catalog / Changes / Impact) when the overlays tag is present; in Changes mode: node/edge `change` data applied from the artifact's maps, ghost nodes/edges added (marked with classes `need-ghost-node`/`need-ghost-edge`, ids prefixed `overlay-` so `graph-explore.js`'s index-parse popups degrade gracefully to their fallback), forced-visible via a new shared slot `__needGraphOverlayForcedNodes` (Set of ghost ids), facet select switched to `change`; on leaving: ghosts removed, change data reset to `"unchanged"` (edge data too), facet restored to its pre-mode value. Announcements via the status region, en/pt-BR through the module-local `t()` pattern (copy `graph-explore.js`'s `isPt`/`t` helpers verbatim).

- [ ] **Step 1: Write the failing contract tests**

In `tests/test_graph_exploration_assets.py`:

```python
def test_modes_client_is_loaded_after_explore_and_consumes_published_annotations() -> None:
    views = read(EXTENSION, "views.lua")
    modes = read(EXTENSION, "graph-modes.js")

    assert 'version = "0.1.6"' in views
    assert views.index('"graph-explore.js"') < views.index('"graph-modes.js"')
    assert "data-need-graph-overlays" in modes
    assert "schemaVersion" in modes
    # It presents published values; it never classifies by itself.
    assert 'change = "modified"' not in modes and 'change = "added"' not in modes
    # pt-BR strings exist for every new control label:
    assert 't("Changes", "Mudanças")' in modes
    assert 't("Catalog", "Catálogo")' in modes
```

In `tests/test_graph_assets.py`: extend `test_graph_js_ships_expected_markers` (or the showcase-mirrors test) to include `graph-modes.js` in both trees. Update the existing `test_exploration_client_is_loaded_after_base_graph` version assertion `0.1.5` → `0.1.6`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_graph_exploration_assets.py tests/test_graph_assets.py -v`
Expected: FAIL — `graph-modes.js` does not exist (file read error), version still `0.1.5`.

- [ ] **Step 3: Implement the module**

Create `graph-modes.js` following `graph-explore.js`'s module skeleton exactly (IIFE, `window.__quartoNeedsGraphModesInstalled` guard, `enhance`/`enhanceAll`/`schedule` with the same readiness retries, `projectionFor`-style tag reader). Core behavior:

```lua
```

(no — JavaScript:)

```javascript
(() => {
  if (window.__quartoNeedsGraphModesInstalled) return;
  window.__quartoNeedsGraphModesInstalled = true;
  // isPt/t: copy graph-explore.js's helpers verbatim.
  // overlaysFor(container): parse the [data-need-graph-overlays] script tag;
  //   return null unless it exists and decodes with the expected schemaVersion.
  // enhance(container):
  //   - overlays = overlaysFor(container); if (!overlays) return false;
  //   - require canvas/controls/cy/status as graph-explore.js does;
  //   - build a mode <select> (Catalog/Changes/Impact) in the controls row,
  //     styled like graph-explore.js's makeSelect;
  //   - applyMode(mode):
  //       clearMode();  // ghosts removed, change data reset, slot released
  //       if (mode === "changes") applyDiff(overlays.diff);
  //       if (mode === "impact")  applyImpact(overlays.impact);  // Task 5
  //       announce; refresh via container.__needGraphContextApi.refresh();
  //   - applyDiff: cy.batch(() => {
  //       for (const [id, change] of Object.entries(diff.nodes))
  //         cy.getElementById(id).data("change", change);
  //       diff.ghostNodes.forEach(n => cy.add({ group: "nodes", data: ghostData(n),
  //         classes: "need-ghost-node" }));
  //       diff.ghostEdges likewise (explicit id: "overlay-e" + index);
  //       forced = new Set(ghost ids); container.__needGraphOverlayForcedNodes = forced;
  //       remember the facet select's current value; set it to "change" and
  //       dispatch a change event so graph.js's own recolor path runs.
  //     });
  //   - ghostData(n): the exact field set graph.js builds at init
  //     (id, label via its own composition rule, type, status, href,
  //     change: n.change || "removed") — copy the composition, don't invent one.
})();
```

Style requirement: match `graph-explore.js`'s conventions precisely (no framework, no build step, `const`/arrow functions, `String(...) || ""` defensiveness, `announce` helper writing to the status region).

In `views.lua`: add `"graph-modes.js"` after `"graph-explore.js"`; bump `version` to `"0.1.6"`. Sync the showcase copy (`examples/book/_extensions/quarto-needs/`) — check `make sync-example` first (`grep -n "sync-example" Makefile`) and use it if it copies the extension; otherwise copy the three touched files by hand, byte-identical.

**Composition edit (small, in this task, because Changes-mode ghosts need it):** in `graph-explore.js`'s `installPredicates`, the forced-nodes slot currently starts from `pathNodes`. Change to a union so the two features cannot clobber each other:

```javascript
      const overlayForced = container.__needGraphOverlayForcedNodes;
      const forced = overlayForced
        ? new Set([...pathNodes, ...overlayForced])
        : pathNodes;
      container.__needGraphForcedNodes = forced;
      container.__needGraphNodeAllowed = (node) => {
        if (forced.has(node.id())) return true;
        ...
```

(Keep the existing empty-set guard semantics: an empty overlay set must behave as "no forcing", never as "force nothing visible" — `new Set([...pathNodes, ...overlayForced])` naturally unions, and the affected-only check in Task 5 gets the same treatment.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_graph_exploration_assets.py tests/test_graph_assets.py -v`
Expected: all PASS.

- [ ] **Step 5: Falsify the "presents, never classifies" contract**

The contract test asserts the literal strings `'change = "modified"'` / `'change = "added"'` are absent from `graph-modes.js`. Falsify the *test*: temporarily add a hardcoded `node.data("change", "modified")` line and confirm the test fails, then remove it. (This is the invariant that keeps Python the semantic authority — it deserves a real mutation check.)

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add _extensions/quarto-needs/graph-modes.js _extensions/quarto-needs/views.lua \
        _extensions/quarto-needs/graph-explore.js examples/book/_extensions/quarto-needs \
        tests/test_graph_exploration_assets.py tests/test_graph_assets.py
git commit -m "$(cat <<'EOF'
feat: add the graph modes client with a Changes mode

The switcher only applies annotations the overlay artifact already
carries — classifications are Python's, presentation is the browser's
(pinned by a source contract that fails if the client ever hardcodes
a classification). Ghosts ride the existing forced-node mechanism via
a dedicated slot unioned by the explore predicate, so filters, root
paths, and overlays compose instead of clobbering. Version bump to
0.1.6; showcase copy kept byte-identical.
EOF
)"
```

---

### Task 5: Impact mode and the Affected-only toggle

**Files:**
- Modify: `_extensions/quarto-needs/graph-modes.js`
- Modify: `_extensions/quarto-needs/graph-explore.js` (the predicate owner consumes the new slot)
- Modify: `examples/book/_extensions/quarto-needs/` (sync both files)
- Modify: `tests/test_graph_exploration_assets.py`

**Interfaces:**
- Consumes: `overlays.impact.entries` (`{id, origin, distance, path, classification}`), `overlays.impact.pathEdges`, `overlays.impact.ghost*`; the visibility slot pattern; the existing `pathMember` edge style (`graph.js` line 207 styles `edge[pathMember = 'true']`).
- Produces: in Impact mode — path edges get `pathMember: "true"` data (and `need-ghost-edge` ghosts added as in Task 4); impacted nodes get `data("impactDistance", n)` / `data("impactOrigin", origin)`; origin-bearing nodes additionally get class `need-impact-origin`; the *Affected only* checkbox (next to the mode select, enabled only in Impact mode) sets `container.__needGraphAffectedOnly` to a Set of impacted ids + ghost ids, consumed by `graph-explore.js`'s `installPredicates` (`if (affectedOnly && !affectedOnly.has(node.id())) return false;` — intersecting with the existing type/status/family predicates, empty-set-means-empty respected because a non-null empty set filters everything out and the module only ever publishes a non-empty set or null); on selection of an impacted node, the status region announces id, distance, origin, and classification (popup body enrichment is deliberately out of scope — Global Constraint #3). Leaving Impact mode: clears `pathMember` data, impact data/classes, ghosts, and the affected-only slot.

- [ ] **Step 1: Write the failing contract tests**

```python
def test_impact_mode_composes_through_the_existing_predicates() -> None:
    modes = read(EXTENSION, "graph-modes.js")
    explore = read(EXTENSION, "graph-explore.js")

    assert "__needGraphAffectedOnly" in modes
    assert "__needGraphAffectedOnly" in explore
    # The empty-set rule the other slots already honor:
    assert "affectedOnly && !affectedOnly.has(node.id())" in explore
    assert "pathMember" in modes          # published path edges, presented
    assert "impactDistance" in modes
    assert 't("Affected only", "Somente afetados")' in modes
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_graph_exploration_assets.py -k impact_mode -v`
Expected: FAIL (nothing implements the slot yet).

- [ ] **Step 3: Implement**

`graph-modes.js`: `applyImpact`/`clearImpact` per the interfaces above; the checkbox follows `makeToggle`-style construction (`graph-context.js` has `makeToggle` at line 94 — copy its construction, or `makeSelect`'s label-wrapping if a checkbox helper doesn't transfer cleanly). Disabled state in Catalog/Changes modes (`checkbox.disabled = mode !== "impact"`); switching modes while checked clears the slot and announces it.

`graph-explore.js` `installPredicates`: consume `__needGraphAffectedOnly` after the type/status/incident checks:

```javascript
        const affectedOnly = container.__needGraphAffectedOnly;
        ...
        container.__needGraphNodeAllowed = (node) => {
          if (forced.has(node.id())) return true;
          if (affectedOnly && !affectedOnly.has(node.id())) return false;
          if (type && ...) return false;
          ...
```

and call `installPredicates(); refresh();` when the checkbox toggles (modes.js drives this through its own listeners — it may call `container.__needGraphInstallPredicates` if that is exposed, otherwise dispatch the existing filter-change pathway; read how `graph-explore.js` re-installs on filter change and use the same entry point).

- [ ] **Step 4: Run tests to verify they pass, then falsify**

Run: `.venv/bin/python -m pytest tests/test_graph_exploration_assets.py -v` — all PASS.
Falsify: remove the `affectedOnly` check from `graph-explore.js` — the contract test must fail. Restore.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add _extensions/quarto-needs/graph-modes.js _extensions/quarto-needs/graph-explore.js \
        examples/book/_extensions/quarto-needs tests/test_graph_exploration_assets.py
git commit -m "$(cat <<'EOF'
feat: add Impact mode with an affected-only visibility toggle

The impact artifact's entries and explanation-path edges are
presented on the live graph — pathMember edges, distance/origin
data, origin highlighting — and the affected-only toggle narrows
through the same predicate owner every other filter uses, so it
intersects with type/status/family instead of fighting them.
Distances and classifications are announced on selection; popup
enrichment is a named follow-on.
EOF
)"
```

---

### Task 6: End-to-end — a real `quarto render` proves the full path

**Files:**
- Modify: `tests/test_quarto_views.py` (add to the existing file; reuse its fixture-project helper exactly — the same one `test_need_c4_renders_a_context_diagram` uses, including how it triggers the CLI build step before rendering)

**Interfaces:**
- Consumes: the real `quarto` binary; a fixture project *with* a baseline (authored in the test via the same `build_baseline` mechanics Task 2's tests use, written to the fixture project before the build step runs).

- [ ] **Step 1: Write the failing tests**

```python
def test_need_graph_embeds_the_overlay_artifact_when_a_baseline_exists(tmp_path: Path) -> None:
    # fixture project (helper) + one relation change worth of baseline drift:
    #   author the project, run the build step once, create+write a baseline
    #   from the CURRENT state via the same build_baseline call the CLI's
    #   baseline create path uses (copy it, or invoke the CLI via subprocess
    #   exactly as the c4 test triggers its build step), then edit one object
    #   in the .qmd (e.g. change a status) so diff/impact are non-empty.
    subprocess.run(["quarto", "render", str(project)], cwd=ROOT, check=True)
    html = (project / "_book" / "index.html").read_text(encoding="utf-8")
    assert "data-need-graph-overlays" in html
    assert "need-graph-overlays-v1" in html


def test_need_graph_omits_the_overlay_artifact_without_a_baseline(tmp_path: Path) -> None:
    # same fixture, no baseline file
    subprocess.run(["quarto", "render", str(project)], cwd=ROOT, check=True)
    html = (project / "_book" / "index.html").read_text(encoding="utf-8")
    assert "data-need-graph-overlays" not in html
```

(Adapt the fixture/build-step sequencing to whatever `test_need_c4_*` does — copy it, don't guess. If the helper doesn't make baseline authoring easy, prefer the direct-Python route (`build_baseline` + `write_baseline` from `quarto_needs.baseline`) over CLI subprocess gymnastics.)

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -k overlay -v`
Expected: the with-baseline test FAILS (no overlays tag yet — Tasks 3-5's pieces may exist but the fixture project has no baseline wired) or errors in fixture setup; the without-baseline test likely PASSES already (absence is the current state) — that is fine, it is the regression pin, note it.

- [ ] **Step 3: Fix whatever the failures actually say**

Deliberately open-ended, as in Task 8 of the Phase 6 plan: the failure depends on fixture mechanics only visible at runtime (baseline authoring shape, build-step sequencing, `_quarto.yml` resources). Diagnose from pytest + quarto's stderr before changing anything.

- [ ] **Step 4: Run tests to verify they pass, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -k overlay -v` — both PASS.
Run: `.venv/bin/python -m pytest -q` — all pass (real renders; slower than the unit tasks — expected).

- [ ] **Step 5: Commit**

```bash
git add tests/test_quarto_views.py
git commit -m "$(cat <<'EOF'
test: verify the overlay embed end to end through a real Quarto render

The artifact exists only when a baseline exists, and the page embeds
it only when the artifact exists — both directions pinned through the
same subprocess quarto render pattern every other shortcode is
verified with.
EOF
)"
```

---

### Task 7: Self-hosted retrofit — the example project adopts the baseline + modes

**Files:**
- Create: `examples/quarto-needs/baselines/quarto-needs.json` (tracked; follow `examples/book/baselines/`'s exact precedent — read `examples/book/baselines/README.md` first and follow its curation contract for what the file is and how it is regenerated)
- Modify: `examples/quarto-needs/.quarto-needs.toml` (`[graph] baseline = "baselines/quarto-needs.json"`)
- Modify: `Makefile` (a `baseline-self-example` target alongside the existing `baseline-example`/`sync-self-example`/`check-self-example` targets, pinning `SOURCE_DATE_EPOCH` the way `AEGIS_REFERENCE_EPOCH` does for the book — read lines 1-115 first and mirror the established pattern)
- Verify (possibly modify if parity demands): the page(s) embedding `{{< need-graph >}}` and their pt-BR twins

**Interfaces:**
- Produces: the self-hosted example renders with the mode switcher present in both languages, driven by a tracked, deterministically regenerable baseline. With baseline == current tree, diff/impact are honestly empty — the switcher appears, switching announces "no changes" — which is the truthful first adoption (the book's baseline has real drift because it was captured at an earlier milestone; the self example's will accumulate drift the same way over time).

- [ ] **Step 1: Read the book's baseline curation contract**

Read `examples/book/baselines/README.md` and the book's Makefile targets (lines 105-112). Note: how the file is generated (`baseline create --force --output ...`), whether/why `SOURCE_DATE_EPOCH` is pinned for *creation* (the diff/impact targets pin it for *comparison*; check whether creation is pinned too — `config.reference_date()` reads `SOURCE_DATE_EPOCH`, so an unpinned create bakes today's date into the tracked file; if the book's README says to pin it, pin it identically).

- [ ] **Step 2: Generate the self example's baseline**

```bash
mkdir -p examples/quarto-needs/baselines
PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/quarto-needs \
  baseline create --force --output baselines/quarto-needs.json
```

(SOURCE_DATE_EPOCH per Step 1's finding.) Regenerate once more and `git diff --no-index` / `cmp` the two runs to prove byte-stability before committing — a tracked artifact that churns on every regen violates the project's determinism discipline.

- [ ] **Step 3: Point the config at it and prove the artifact appears**

Add to `examples/quarto-needs/.quarto-needs.toml`:

```toml
[graph]
baseline = "baselines/quarto-needs.json"
```

(check whether a `[graph]` section already exists in the file — extend it, don't duplicate the header). Then run the project's own pipeline:

```bash
make sync-self-example   # or whatever target syncs the extension copy — confirm from the Makefile
PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/quarto-needs scan
ls examples/quarto-needs/.quarto-needs/graphs/need-graph-1-overlays.json
```

(If the canonical build entry is the pre-render tool rather than `scan`, use that — confirm with `grep -n "scan\|pre_render" Makefile`.)

- [ ] **Step 4: Render and verify both languages**

```bash
make render-self-example   # confirm the exact target name from the Makefile first
grep -c "data-need-graph-overlays" examples/quarto-needs/_book/*/index.html \
  examples/quarto-needs/_book/*.html 2>/dev/null
```

Expected: every page embedding `{{< need-graph >}}` (and its pt-BR twin) carries exactly one overlays tag. Manually open the rendered page and exercise the switcher (Catalog → Changes → Impact → Affected only) — this is a look-at-it check per the project's UI-verification discipline: the select appears, switching announces in the right language, ghosts/facet behave, no console errors.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass — the self-hosted gates (parity, quality, ownership) are unaffected by a config key and a tracked artifact; if the parity checker or any gate reads `[graph]` exhaustively, extend its expectation rather than loosening it.

- [ ] **Step 6: Commit**

```bash
git add examples/quarto-needs/baselines examples/quarto-needs/.quarto-needs.toml Makefile
git commit -m "$(cat <<'EOF'
feat: adopt the graph mode switcher in the self-hosted example

A tracked, deterministically regenerable baseline (book precedent)
plus the [graph] baseline key pointing the overlay artifact at it.
Baseline equals the current tree, so Changes/Impact start honestly
empty — the pipeline is real, the drift will accumulate the same way
the book's did.
EOF
)"
```

---

### Task 8: Documentation — phase doc and roadmap status

**Files:**
- Create: `docs/phase-7-interactive-workbench.md` (mirroring `docs/phase-6-architecture-c4.md`'s structure: status line, current-state summary, what's implemented, what was learned, known limitations, what is intentionally not implemented yet, regression coverage)
- Modify: `docs/ROADMAP.md` (Phase 7 heading, currently ⚪ at line ~227)

**Interfaces:**
- Produces: ground-truth record naming all three deliberate simplifications explicitly (static table stays catalog-only with honest labeling; overlays are default-view-only; impact popup enrichment deferred) and the planning-time descope ruling (two-node shortest path moved to the phase's next slice), plus the empty-baseline semantics.

- [ ] **Step 1: Write `docs/phase-7-interactive-workbench.md`** — same shape and citation style as the Phase 6 doc; list every new/extended test file with what it proves.

- [ ] **Step 2: Update `docs/ROADMAP.md`** — Phase 7 heading to `✅ (first slice: overlay annotation artifact, Catalog/Changes/Impact mode switcher, affected-only toggle)` plus a short paragraph pointing at the new doc, mirroring the Phase 6 entry's wording pattern.

- [ ] **Step 3: Run the full suite** — `.venv/bin/python -m pytest -q`; all pass.

- [ ] **Step 4: Commit**

```bash
git add docs/phase-7-interactive-workbench.md docs/ROADMAP.md
git commit -m "$(cat <<'EOF'
docs: record Phase 7's interactive-workbench first slice

Names the three deliberate simplifications and the planning-time
descope (two-node shortest path deferred to the next slice) so the
ground-truth record reads as scope decisions, not silently-dropped
spec claims.
EOF
)"
```

---

## Self-Review

**Spec coverage:** the spec's baseline-comparison half (published variants + switcher + affected-only) is delivered as Tasks 1-7; the shortest-path half is **descoped with an explicit, stated ruling** in the header (the impact view already being affected-only by construction changed the cost/benefit); ergonomics items remain named non-goals in the spec. The spec's transport open question is resolved (embed, annotation-delta-shaped — *stronger* than the spec's fetch-or-embed framing because the artifact is proportional to the change set); the rebuild-mechanics question is resolved (none — in-place annotations); the affected-set-edges question is resolved (strict: changed + path edges only, per the artifact's extraction); the baseline-curation question is resolved (book precedent, Task 7).

**Invariant audit:** no new Python semantics (Task 2 only extracts from built projections — falsified in its Step 5); no JS classification (pinned by a source contract that a mutation check falsifies in Task 4's Step 5); no dataset rebuild (annotation application on the live instance); empty-set-means-empty preserved in the new predicate (contract test); graceful degradation without a baseline (Task 2's no-op test + Task 6's without-baseline render).

**Type consistency:** `build_graph_overlays(snapshot, config, *, baseline_payload)` is built in Task 2 and consumed only via `write_graph_overlays`; the artifact's field names (`nodes`/`edges`/`ghostNodes`/`ghostEdges`/`entries`/`pathEdges`) are produced in Task 2 and consumed verbatim in Tasks 4-5 (`diff.nodes`, `impact.entries`, ...); the slot names (`__needGraphOverlayForcedNodes`, `__needGraphAffectedOnly`) are written by `graph-modes.js` and read by `graph-explore.js` with the exact strings pinned by contract tests on both sides.

Plan complete and saved to `docs/superpowers/plans/2026-09-01-phase-7-interactive-workbench.md`. Execution follows the same loop as Phase 6: task-by-task, TDD, full suite green per commit.
