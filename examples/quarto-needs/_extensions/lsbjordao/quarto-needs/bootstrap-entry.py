"""Stable project-relative entry point for the Quarto extension bootstrap."""
from __future__ import annotations

import os
from pathlib import Path
import runpy


EXTENSION_DIR = Path(__file__).resolve().parent


def _project_root() -> Path:
    """Resolve the owning Quarto project without trusting an arbitrary env path."""
    candidates = []
    declared = os.environ.get("QUARTO_PROJECT_DIR")
    if declared:
        candidates.append(Path(declared).expanduser())
    candidates.append(Path.cwd())

    for candidate in candidates:
        root = candidate.resolve()
        extensions = (root / "_extensions").resolve()
        try:
            extensions.relative_to(root)
            EXTENSION_DIR.relative_to(extensions)
        except ValueError:
            continue
        return root

    raise RuntimeError(
        "Quarto-Needs extension is not located inside the active project's "
        "_extensions directory"
    )


PROJECT_ROOT = _project_root()
os.environ["QUARTO_PROJECT_DIR"] = str(PROJECT_ROOT)
os.environ["QUARTO_NEEDS_EXTENSION_DIR"] = str(EXTENSION_DIR)

runpy.run_path(str(EXTENSION_DIR / "bootstrap.py"), run_name="__main__")
