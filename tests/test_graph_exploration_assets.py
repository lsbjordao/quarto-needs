from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "_extensions" / "quarto-needs"
SHOWCASE = ROOT / "examples" / "book" / "_extensions" / "quarto-needs"


def read(root: Path, name: str) -> str:
    return (root / name).read_text(encoding="utf-8")


def test_exploration_client_is_loaded_after_base_graph() -> None:
    views = read(EXTENSION, "views.lua")

    assert 'version = "0.1.5"' in views
    assert views.index('"graph-context.js"') < views.index('"graph.js"')
    assert views.index('"graph.js"') < views.index('"graph-explore.js"')


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


def test_showcase_graph_clients_match_canonical_extension() -> None:
    assert read(SHOWCASE, "graph-context.js") == read(EXTENSION, "graph-context.js")
    assert read(SHOWCASE, "graph-explore.js") == read(EXTENSION, "graph-explore.js")
