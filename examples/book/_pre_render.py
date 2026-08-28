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


def main() -> None:
    entrypoint = repository_root() / "tools" / "quarto_needs_pre_render.py"
    runpy.run_path(str(entrypoint), run_name="__main__")


if __name__ == "__main__":
    main()
