from __future__ import annotations

import re
import tomllib
from pathlib import Path

import quarto_needs

ROOT = Path(__file__).resolve().parents[1]


def extension_version(manifest: Path) -> str:
    match = re.search(r"^version:\s*(\S+)\s*$", manifest.read_text(encoding="utf-8"), re.M)
    assert match, f"{manifest} declares no version"
    return match.group(1)


def test_all_manifests_declare_the_same_version() -> None:
    """A user pairs a `quarto add` extension with a `pip install` engine.

    Those are two distributions a user updates independently, so a version they
    disagree on is a support burden that surfaces as confusing behavior rather
    than a clear error. Pin them together here, where drift is cheap to find.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packaged = pyproject["project"]["version"]
    canonical = extension_version(ROOT / "_extensions" / "quarto-needs" / "_extension.yml")

    assert quarto_needs.__version__ == packaged, (
        f"__init__ declares {quarto_needs.__version__}, pyproject declares {packaged}"
    )
    assert canonical == packaged, (
        f"the Quarto extension declares {canonical}, the package declares {packaged}"
    )


def test_the_showcase_extension_matches_the_canonical_one() -> None:
    """The example's installed copy is synchronized, never hand-edited.

    `tests/test_extension_sync.py` already compares the assets byte for byte;
    this names the version specifically, because a stale version there is what a
    reader of the showcase would see and believe.
    """
    canonical = extension_version(ROOT / "_extensions" / "quarto-needs" / "_extension.yml")
    installed = extension_version(
        ROOT / "examples" / "book" / "_extensions" / "quarto-needs" / "_extension.yml"
    )

    assert installed == canonical
