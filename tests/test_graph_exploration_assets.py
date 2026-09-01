from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "_extensions" / "quarto-needs"
SHOWCASE = ROOT / "examples" / "book" / "_extensions" / "quarto-needs"


def read(root: Path, name: str) -> str:
    return (root / name).read_text(encoding="utf-8")


def test_exploration_client_is_loaded_after_base_graph() -> None:
    views = read(EXTENSION, "views.lua")

    assert 'version = "0.1.6"' in views
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
