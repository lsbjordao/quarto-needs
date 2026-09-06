"""BabelQuarto-safe setup hook for the self-hosted Quarto-Needs case study.

This project hook runs before the extension-contributed pre-render. It only
synchronizes the canonical extension assets into the staged BabelQuarto copy
and validates/writes presentation-only localization projections. The canonical
engineering build is intentionally left to the extension bootstrap so each
render analyzes the model exactly once.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


def repository_root() -> Path:
    configured = os.environ.get("QUARTO_NEEDS_REPO_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parents[2]
    helper = root / "tools" / "quarto_needs_pre_render.py"
    if not helper.is_file():
        raise RuntimeError(
            "Cannot locate quarto-needs pre-render helper at "
            f"{helper}. Set QUARTO_NEEDS_REPO_ROOT to the repository root."
        )
    return root


def main() -> None:
    root = repository_root()
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "tools"))

    from quarto_needs.localization import write_localized_projections
    from quarto_needs_pre_render import sync_extension

    project_root = Path.cwd().resolve()
    sync_extension(project_root)
    write_localized_projections(project_root)


if __name__ == "__main__":
    main()
