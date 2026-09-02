"""Pre-render hook: analyze the project and sync the extension before render.

A thin wrapper so the example stays readable: the canonical entry point is
``tools/quarto_needs_pre_render.py`` in the repository. BabelQuarto-style
staging is not needed here, but honoring ``QUARTO_NEEDS_REPO_ROOT`` keeps
the contract identical to the other examples.
"""

from __future__ import annotations

import os
from pathlib import Path
import runpy


def repository_root() -> Path:
    configured = os.environ.get("QUARTO_NEEDS_REPO_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    runpy.run_path(
        str(repository_root() / "tools" / "quarto_needs_pre_render.py"),
        run_name="__main__",
    )
