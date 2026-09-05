from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "_extensions" / "quarto-needs"
SHOWCASE = ROOT / "examples" / "quarto-needs" / "_extensions" / "quarto-needs"


def read(root: Path, name: str) -> str:
    return (root / name).read_text(encoding="utf-8")


def test_exploration_client_is_loaded_after_base_graph() -> None:
    views = read(EXTENSION, "views.lua")

    assert 'version = "0.1.9"' in views
    assert views.index('"graph-context.js"') < views.index('"graph.js"')
    assert views.index('"graph.js"') < views.index('"graph-explore.js"')
    assert views.index('"graph-explore.js"') < views.index('"graph-modes.js"')


def test_exploration_client_consumes_published_semantics() -> None:
    context = read(EXTENSION, "graph-context.js")
    explore = read(EXTENSION, "graph-explore.js")

    assert "relationSemantics" in context
    assert "traversalProfiles" in explore
    assert "traversalDirection" in explore
    assert "__needGraphTraversalFamilies" in context
    assert "__needGraphForcedNodes" in context
    assert "__needGraphForcedNodes" in explore
    assert 't("Path to root", "Caminho até a raiz")' in explore
    assert 't("Declared at", "Declarada em")' in explore

    # An empty profile/family intersection means no traversable families. Never
    # silently reinterpret an empty Set as "all relations".
    assert "allowedFamilies && !allowedFamilies.has(family)" in context
    assert "allowedFamilies && !allowedFamilies.has(family)" in explore
    assert "allowedFamilies && allowedFamilies.size &&" not in context
    assert "allowedFamilies && allowedFamilies.size &&" not in explore


def test_modes_client_consumes_published_annotations_only() -> None:
    modes = read(EXTENSION, "graph-modes.js")
    explore = read(EXTENSION, "graph-explore.js")

    assert "data-need-graph-overlays" in modes
    assert "need-graph-overlays-v1" in modes

    # It presents published values; it never classifies by itself. Changes to
    # live elements must read the artifact's maps — the only hardcoded change
    # value is the ghosts' published removal, presented inside their element
    # data exactly as the projection pipeline already ships it.
    assert 'data("change", "modified")' not in modes
    assert 'data("change", "added")' not in modes
    assert 'data("change", "removed")' not in modes
    assert 'change: "removed"' in modes

    assert 't("Catalog", "Catálogo")' in modes
    assert 't("Changes", "Mudanças")' in modes

    # The overlay's forced-visibility slot is composed by the explore
    # predicate's owner, never written by two features independently:
    assert "__needGraphOverlayForcedNodes" in modes
    assert "__needGraphOverlayForcedNodes" in explore


def test_showcase_graph_clients_match_canonical_extension() -> None:
    assert read(SHOWCASE, "graph-context.js") == read(EXTENSION, "graph-context.js")
    assert read(SHOWCASE, "graph-explore.js") == read(EXTENSION, "graph-explore.js")
    assert read(SHOWCASE, "graph-modes.js") == read(EXTENSION, "graph-modes.js")


def test_changes_mode_reflects_the_static_table_not_just_the_canvas() -> None:
    """Known limitation item 1's named follow-on: the static table stayed
    the catalog table in every mode before this. Changes mode must update
    it — the same reader relying on the table for accessibility should see
    the same information a sighted canvas user does."""
    modes = read(EXTENSION, "graph-modes.js")

    assert 'data-need-graph-role="node"' in modes
    assert 'data-need-graph-role="edge"' in modes
    assert "data-need-graph-row-id" in modes


def test_changes_mode_snapshots_the_table_before_any_mode_ever_applies() -> None:
    """The snapshot must be taken once, from the untouched catalog-rendered
    table, before any mode switch — not lazily inside applyChanges(), where
    a second Changes-mode entry would snapshot the table's own prior
    modifications instead of the true original."""
    modes = read(EXTENSION, "graph-modes.js")

    snapshot_index = modes.index("tableSnapshot")
    first_mode_switch_index = modes.index('modeField.select.addEventListener("change"')
    assert snapshot_index < first_mode_switch_index


def test_changes_mode_appends_ghost_rows_and_updates_existing_ones() -> None:
    source = read(EXTENSION, "graph-modes.js")
    apply_start = source.index("function applyChanges()")
    apply_end = source.index("\n    function applyImpact", apply_start)
    block = source[apply_start:apply_end]

    assert "appendGhostRow(nodeTable" in block
    assert "appendGhostRow(edgeTable" in block
    assert 'document.createElement("tr")' in source


def test_changes_mode_restores_the_table_on_reset() -> None:
    """Leaving Changes mode (switching away, or Reset) must restore the
    table exactly to its original catalog state — removed ghost rows gone,
    modified cells back to their snapshot text — not whatever text happens
    to be left over from the last mode."""
    modes = read(EXTENSION, "graph-modes.js")
    reset_start = modes.index("function resetChangeData()")
    reset_end = modes.index("\n    function addGhosts", reset_start)
    block = modes[reset_start:reset_end]

    assert "tableSnapshot" in block
    assert ".remove()" in block


def test_impact_mode_stores_path_and_classification_on_the_node() -> None:
    """distance/origin were already stored as node data; path/classification
    exist in the same overlays.impact.entries shape but were never carried
    over — the popup can't show what was never set."""
    modes = read(EXTENSION, "graph-modes.js")
    apply_start = modes.index("function applyImpact()")
    apply_end = modes.index("\n    const modeField", apply_start)
    block = modes[apply_start:apply_end]

    assert 'node.data("impactPath"' in block
    assert 'node.data("impactClassification"' in block


def test_impact_mode_cleans_up_path_and_classification_on_reset() -> None:
    """Leaving Impact mode must remove these two the same way distance/
    origin are already removed, or a popup opened afterward would still
    show stale impact rows for a node no longer being analyzed."""
    modes = read(EXTENSION, "graph-modes.js")
    reset_start = modes.index("function resetChangeData()")
    reset_end = modes.index("\n    function addGhosts", reset_start)
    block = modes[reset_start:reset_end]

    assert 'node.removeData("impactPath")' in block
    assert 'node.removeData("impactClassification")' in block


def test_impact_mode_composes_through_the_existing_predicates() -> None:
    modes = read(EXTENSION, "graph-modes.js")
    explore = read(EXTENSION, "graph-explore.js")

    assert "__needGraphAffectedOnly" in modes
    assert "__needGraphAffectedOnly" in explore
    # The empty-set rule the other slots already honor: a non-null set filters,
    # null never does.
    assert "affectedOnly && !affectedOnly.has(node.id())" in explore
    # The predicate owner re-derives; the modes client only flips slots:
    assert "__needGraphReapplyPredicates" in modes
    assert "__needGraphReapplyPredicates" in explore
    assert "pathMember" in modes
    assert "impactDistance" in modes
    assert 't("Affected only", "Somente afetados")' in modes


def test_affected_only_never_publishes_an_empty_filter() -> None:
    """An empty impacted set must mean 'nothing to filter', never 'hide the
    whole graph' — the toggle disables itself and the slot stays null."""
    modes = read(EXTENSION, "graph-modes.js")

    assert "affected.input.checked && impacted instanceof Set && impacted.size" in modes
    assert "affected.input.disabled = mode !== \"impact\" || !hasImpacted" in modes
    assert 't("No impacted objects to filter", "Nenhum objeto afetado para filtrar")' in modes


def test_shortest_path_neighbors_ignore_traversal_direction() -> None:
    """Two-node shortest path answers 'are these connected at all', not
    'can you walk from one to the other along declared directions' —
    unlike directParents (which only follows a relation's own declared
    traversalDirection), neighbors() must treat every edge in an allowed
    family as traversable both ways, including traversalDirection "none"
    relations (e.g. references) that directParents never follows at all.
    """
    explore = read(EXTENSION, "graph-explore.js")

    assert "function neighbors(cy, semantics, nodeId, allowedFamilies)" in explore
    neighbors_start = explore.index("function neighbors(cy, semantics, nodeId, allowedFamilies)")
    neighbors_end = explore.index("\n  }\n", neighbors_start)
    neighbors_body = explore[neighbors_start:neighbors_end]

    assert "traversalDirection" not in neighbors_body
    assert "allowedFamilies" in neighbors_body


def test_shortest_path_button_exists_and_reuses_the_root_path_highlight() -> None:
    """Reuses pathToRoot's own highlight classes and forced-visibility
    wiring rather than a second, parallel highlight system."""
    explore = read(EXTENSION, "graph-explore.js")

    assert 't("Path between…", "Caminho entre…")' in explore
    assert explore.count('"need-root-path-node need-root-path-edge"') >= 1
    assert "function shortestPath(cy, semantics, startId, endId, allowedFamilies)" in explore


def test_shortest_path_picking_mode_does_not_clear_on_the_second_pick() -> None:
    """Focus changes normally clear any active path (so path-to-root
    doesn't linger) — but the second endpoint pick for shortest-path IS a
    focus change, and must not be swallowed by that same auto-clear."""
    explore = read(EXTENSION, "graph-explore.js")

    focus_start = explore.index('addEventListener("quarto-needs-node-focus"')
    focus_end = explore.index("});", focus_start)
    focus_body = explore[focus_start:focus_end]

    assert "pickingSecondEndpoint" in focus_body


def test_shortest_path_handles_the_same_node_picked_twice() -> None:
    explore = read(EXTENSION, "graph-explore.js")

    shortest_start = explore.index("function shortestPath(cy, semantics, startId, endId, allowedFamilies)")
    shortest_end = explore.index("\n  }\n", shortest_start)
    shortest_body = explore[shortest_start:shortest_end]

    assert "startId === endId" in shortest_body


def test_shortest_path_announces_when_no_path_exists() -> None:
    explore = read(EXTENSION, "graph-explore.js")

    assert 'No semantic path was found between the two objects' in explore
    assert "Nenhum caminho semântico foi encontrado entre os dois objetos" in explore


def test_active_path_is_exposed_on_the_container_for_deep_linking() -> None:
    """Deep-linking/saved-state needs to read which path (if any) is
    currently shown without reaching into graph-explore.js's private
    closure — the same container-property convention __needGraphFocusNode
    already uses."""
    explore = read(EXTENSION, "graph-explore.js")

    assert 'container.__needGraphActivePath = null;' in explore
    assert 'container.__needGraphActivePath = { kind: "root", nodes: result.nodes };' in explore
    assert 'container.__needGraphActivePath = { kind: "between", nodes: result.nodes };' in explore


def test_breadcrumbs_render_alongside_each_active_path() -> None:
    """A clickable trail is rendered from the exact same result.nodes array
    already stored on __needGraphActivePath — no new traversal, no second
    copy of path data to keep in sync."""
    explore = read(EXTENSION, "graph-explore.js")

    assert "need-graph-breadcrumbs" in explore
    assert "function renderBreadcrumbs(" in explore

    root_set = 'container.__needGraphActivePath = { kind: "root", nodes: result.nodes };'
    between_set = 'container.__needGraphActivePath = { kind: "between", nodes: result.nodes };'
    assert root_set in explore
    assert between_set in explore

    after_root = explore[explore.index(root_set) : explore.index(root_set) + 400]
    after_between = explore[explore.index(between_set) : explore.index(between_set) + 400]
    assert "renderBreadcrumbs(result.nodes)" in after_root
    assert "renderBreadcrumbs(result.nodes)" in after_between


def test_breadcrumbs_clear_with_the_active_path() -> None:
    explore = read(EXTENSION, "graph-explore.js")

    clear_start = explore.index("const clearPath = () => {")
    clear_end = explore.index("\n    };\n", clear_start)
    clear_body = explore[clear_start:clear_end]

    assert "renderBreadcrumbs(null)" in clear_body


def test_breadcrumb_click_refocuses_without_dropping_the_path() -> None:
    """Re-focusing a node that is already part of the shown path (a
    breadcrumb click, or re-tapping a highlighted node on canvas) is just
    moving attention within the same trail — it must not run the ordinary
    'any focus change clears the active path' behavior every other focus
    change already has."""
    explore = read(EXTENSION, "graph-explore.js")

    focus_start = explore.index('addEventListener("quarto-needs-node-focus"')
    focus_end = explore.index("});", focus_start)
    focus_body = explore[focus_start:focus_end]

    assert "pathNodes.has(nodeId)" in focus_body
    member_check_index = focus_body.index("pathNodes.has(nodeId)")
    clear_call_index = focus_body.index("clearPath();")
    assert member_check_index < clear_call_index


def test_breadcrumb_items_dispatch_the_shared_focus_event() -> None:
    """Clicking a breadcrumb reuses the exact same focus mechanism a canvas
    tap already uses, rather than a second, parallel navigation path."""
    explore = read(EXTENSION, "graph-explore.js")

    render_start = explore.index("function renderBreadcrumbs(")
    render_end = explore.index("\n  }\n", render_start)
    render_body = explore[render_start:render_end]

    assert "container.__needGraphFocusNode = id;" in render_body
    assert 'new CustomEvent("quarto-needs-node-focus", { detail: { nodeId: id } })' in render_body


def test_affected_only_toggle_refreshes_visibility_not_just_predicates() -> None:
    """Toggling the checkbox must actually re-render node visibility.

    Every other place that mutates __needGraphAffectedOnly (the mode-select
    handler, the context-reset handler) calls syncSlots(), which both
    re-derives the predicate closures AND calls contextApi.refresh() (the
    function that actually calls setVisible() on the canvas). The checkbox's
    own change handler previously called only reapplyPredicates() — the
    slot updated but the graph kept showing every node until an unrelated
    action happened to trigger a refresh.
    """
    modes = read(EXTENSION, "graph-modes.js")

    handler_start = modes.index('affected.input.addEventListener("change"')
    handler_end = modes.index("});", handler_start)
    handler_body = modes[handler_start:handler_end]

    assert "syncSlots();" in handler_body
    assert "reapplyPredicates();" not in handler_body


def test_find_edge_miss_is_skipped_not_crashed() -> None:
    """findEdge returns null (not an empty Cytoscape collection) on a miss.

    diff.edges/impact.pathEdges entries can reference a source/relation/
    target triple absent from the live catalog graph (the overlay is built
    from a separate traversal than the rendered projection) — checking
    `.length` on a null throws inside cy.batch() and aborts the whole
    apply, leaving ghosts added but predicates never reapplied.
    """
    modes = read(EXTENSION, "graph-modes.js")

    assert "if (!edge.length) return;" not in modes
    assert modes.count("if (!edge) return;") == 2


def test_state_client_is_loaded_last() -> None:
    views = read(EXTENSION, "views.lua")

    assert 'version = "0.1.9"' in views
    assert views.index('"graph-modes.js"') < views.index('"graph-state.js"')


def test_state_client_reads_the_same_selectors_the_other_modules_publish() -> None:
    """The state client must read/drive the real controls other modules
    already own — not a second, drifting copy of their selectors."""
    state = read(EXTENSION, "graph-state.js")
    explore = read(EXTENSION, "graph-explore.js")
    modes = read(EXTENSION, "graph-modes.js")

    for kind in ("type", "status", "family", "profile"):
        assert f'data-need-graph-explore="{kind}"' in state
        assert f'select.dataset.needGraphExplore = "{kind}"' in explore or "select.dataset.needGraphExplore = kind" in explore

    assert 'data-need-graph-modes="mode"' in state
    assert 'data-need-graph-modes="affected"' in state
    assert 'select.dataset.needGraphModes = "mode"' in modes
    assert 'input.dataset.needGraphModes = "affected"' in modes

    assert ".need-graph-root-path" in state
    assert ".need-graph-shortest-path" in state
    assert 'pathButton.className = "need-graph-root-path"' in explore
    assert 'betweenButton.className = "need-graph-shortest-path"' in explore

    assert ".need-graph-search" in state


def test_state_client_hash_wins_over_storage_and_uses_replace_state() -> None:
    state = read(EXTENSION, "graph-state.js")

    assert "readHashState" in state
    assert "readStoredState" in state
    assert "hashState || readStoredState" in state
    assert "history.replaceState" in state
    assert "history.pushState" not in state


def test_state_client_clears_both_stores_on_context_reset() -> None:
    state = read(EXTENSION, "graph-state.js")

    reset_start = state.index('addEventListener("quarto-needs-context-reset"')
    reset_end = state.index("});", reset_start)
    reset_body = state[reset_start:reset_end]

    assert "clearHashState" in reset_body
    assert "clearStoredState" in reset_body


def test_state_client_storage_failures_never_throw() -> None:
    """localStorage can be unavailable (private browsing, quota) — state
    persistence is a convenience, never a hard requirement."""
    state = read(EXTENSION, "graph-state.js")

    assert state.count("try {") >= 2
    assert "localStorage.getItem" in state
    assert "localStorage.setItem" in state


def test_showcase_state_client_matches_canonical_extension() -> None:
    assert read(SHOWCASE, "graph-state.js") == read(EXTENSION, "graph-state.js")
