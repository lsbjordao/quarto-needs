"""BabelQuarto-safe entry point for the Aegis showcase pre-render hook.

BabelQuarto renders from a temporary copy of ``examples/book``. Relative paths
that escape the book (for example ``../../tools/...``) therefore cannot work in
that staging directory. The multilingual render helper exports the original
repository root, while ordinary in-repository Quarto renders can derive it from
this file's location.
"""

from __future__ import annotations

import os
from pathlib import Path
import runpy
import sys


ROOTED_GRAPH_ID = "need-graph-stk-001"
ROOTED_GRAPH_SEED = "STK-001"
ROOTED_GRAPH_DEPTH = 10


def repository_root() -> Path:
    configured = os.environ.get("QUARTO_NEEDS_REPO_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
    else:
        # <repo>/examples/book/_pre_render.py
        root = Path(__file__).resolve().parents[2]

    entrypoint = root / "tools" / "quarto_needs_pre_render.py"
    if not entrypoint.is_file():
        raise RuntimeError(
            "Cannot locate quarto-needs pre-render entry point at "
            f"{entrypoint}. Set QUARTO_NEEDS_REPO_ROOT to the repository root."
        )
    return root


def run_generic_pre_render(entrypoint: Path) -> None:
    """Run the canonical pre-render hook but retain control on success."""
    try:
        runpy.run_path(str(entrypoint), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if code not in (None, 0):
            raise


def write_rooted_graph_projection(repo_root: Path, project_root: Path) -> None:
    """Emit the showcase graph rooted at STK-001 as its own public projection.

    Keeping this as a real ``.quarto-needs/graphs/*.json`` artifact means the
    second ``need-graph`` works with the same loading contract as the complete
    graph. It does not depend on client-side filtering or on the default graph
    already containing the root.
    """
    source_root = str(repo_root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)

    from quarto_needs.analysis import analyze_project
    from quarto_needs.config import load_config
    from quarto_needs.graph_projection import (
        build_projection,
        render_projection,
        select_graph,
    )

    config = load_config(project_root)
    result = analyze_project(project_root, config=config)
    if result.snapshot is None:
        raise RuntimeError(
            f"Cannot build {ROOTED_GRAPH_ID}: showcase analysis produced no snapshot"
        )

    known_ids = {record.id for record in result.snapshot.objects}
    if ROOTED_GRAPH_SEED not in known_ids:
        raise RuntimeError(
            f"Cannot build {ROOTED_GRAPH_ID}: unknown root {ROOTED_GRAPH_SEED}"
        )

    limits = {"nodes": config.graph.max_nodes, "edges": config.graph.max_edges}
    selection = select_graph(
        result.snapshot,
        seeds=(ROOTED_GRAPH_SEED,),
        relations=config.graph.relations,
        depth=ROOTED_GRAPH_DEPTH,
        limits=limits,
    )
    projection = build_projection(
        result.snapshot,
        node_ids=selection.node_ids,
        view_id=ROOTED_GRAPH_ID,
        mode="catalog",
        limits=limits,
        relations=config.graph.relations,
        layout=config.graph.layout,
        seed=config.graph.seed,
    )

    target = project_root / ".quarto-needs" / "graphs" / f"{ROOTED_GRAPH_ID}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_projection(projection), encoding="utf-8")


def main() -> None:
    repo_root = repository_root()
    entrypoint = repo_root / "tools" / "quarto_needs_pre_render.py"
    run_generic_pre_render(entrypoint)
    write_rooted_graph_projection(repo_root, Path.cwd().resolve())


if __name__ == "__main__":
    main()
