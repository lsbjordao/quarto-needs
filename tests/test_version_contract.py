from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _match(path: str, pattern: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(pattern, text, flags=re.MULTILINE)
    assert match, f"could not find version in {path}"
    return match.group(1)


def test_every_shipped_version_copy_matches_the_python_project() -> None:
    project_version = _match("pyproject.toml", r'^version = "([^"]+)"$')

    versions = {
        "python package": _match(
            "src/quarto_needs/__init__.py",
            r'^__version__ = "([^"]+)"$',
        ),
        "canonical Quarto extension": _match(
            "_extensions/quarto-needs/_extension.yml",
            r"^version: ([^\s]+)$",
        ),
        "starter template": _match(
            "templates/starter/_extension.yml",
            r"^version: ([^\s]+)$",
        ),
        "starter bundled extension": _match(
            "templates/starter/_extensions/quarto-needs/_extension.yml",
            r"^version: ([^\s]+)$",
        ),
        "self-hosted installed extension": _match(
            "examples/quarto-needs/_extensions/lsbjordao/quarto-needs/_extension.yml",
            r"^version: ([^\s]+)$",
        ),
    }

    package = json.loads((ROOT / "editors/vscode/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "editors/vscode/package-lock.json").read_text(encoding="utf-8"))
    versions["VS Code package"] = package["version"]
    versions["VS Code lock root"] = lock["version"]
    versions["VS Code lock package root"] = lock["packages"][""]["version"]

    assert set(versions.values()) == {project_version}, versions
