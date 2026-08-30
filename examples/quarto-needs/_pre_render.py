"""BabelQuarto-safe pre-render entry point for the self-hosted Quarto-Needs case study."""
from __future__ import annotations

import os
from pathlib import Path
import runpy


def repository_root() -> Path:
    configured = os.environ.get("QUARTO_NEEDS_REPO_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parents[2]
    entrypoint = root / "tools" / "quarto_needs_pre_render.py"
    if not entrypoint.is_file():
        raise RuntimeError(
            "Cannot locate quarto-needs pre-render entry point at "
            f"{entrypoint}. Set QUARTO_NEEDS_REPO_ROOT to the repository root."
        )
    return root


def main() -> None:
    entrypoint = repository_root() / "tools" / "quarto_needs_pre_render.py"
    try:
        runpy.run_path(str(entrypoint), run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            raise


if __name__ == "__main__":
    main()
