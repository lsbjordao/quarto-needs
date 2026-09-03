from __future__ import annotations

import re
import sys
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


def test_the_bootstrap_provisions_the_version_the_extension_declares() -> None:
    """The managed runtime installs `quarto-needs==<extension version>`.

    Version parity stops being tidiness in the extension-first distribution
    and becomes a resolvable-install precondition: the bootstrap reads its
    own manifest to decide what to provision, so a bootstrap that read a
    different version would install an engine the extension was never tested
    against. Assert it reads what the manifest declares, and that the exact
    pin -- not a range, not `latest` -- is what it asks for.
    """
    import importlib.util

    path = ROOT / "_extensions" / "quarto-needs" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("quarto_needs_bootstrap", path)
    assert spec and spec.loader
    bootstrap = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(bootstrap)
    finally:
        sys.dont_write_bytecode = previous

    canonical = extension_version(ROOT / "_extensions" / "quarto-needs" / "_extension.yml")

    assert bootstrap.extension_version() == canonical
    assert bootstrap.engine_source(canonical) == f"quarto-needs=={canonical}"
