"""Stable project-relative entry point for the Quarto extension bootstrap."""
from __future__ import annotations

import os
from pathlib import Path
import runpy


EXTENSION_DIR = Path(__file__).resolve().parent

# Quarto runs pre-render commands with the project as cwd. Recording both
# values here removes layout assumptions from bootstrap.py and from the paired
# Python engine, including GitHub's `_extensions/<owner>/<name>` namespace.
os.environ.setdefault("QUARTO_PROJECT_DIR", str(Path.cwd().resolve()))
os.environ["QUARTO_NEEDS_EXTENSION_DIR"] = str(EXTENSION_DIR)

runpy.run_path(str(EXTENSION_DIR / "bootstrap.py"), run_name="__main__")
