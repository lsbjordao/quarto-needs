from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _extension_version(path: Path) -> str:
    match = re.search(r"^version:\s*(\S+)\s*$", path.read_text(encoding="utf-8"), re.M)
    assert match, f"{path} declares no version"
    return match.group(1)


def test_release_version_surfaces_are_aligned() -> None:
    package_version = re.search(
        r'^version = "([^"]+)"$',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.M,
    )
    assert package_version
    version = package_version.group(1)

    assert (ROOT / "src" / "quarto_needs" / "__init__.py").read_text(
        encoding="utf-8"
    ).strip().endswith(f'__version__ = "{version}"')
    assert _extension_version(ROOT / "_extensions" / "quarto-needs" / "_extension.yml") == version
    assert _extension_version(ROOT / "templates" / "starter" / "_extension.yml") == version
    assert _extension_version(
        ROOT / "templates" / "starter" / "_extensions" / "quarto-needs" / "_extension.yml"
    ) == version
    assert _extension_version(
        ROOT
        / "examples"
        / "quarto-needs"
        / "_extensions"
        / "lsbjordao"
        / "quarto-needs"
        / "_extension.yml"
    ) == version

    vscode = json.loads((ROOT / "editors" / "vscode" / "package.json").read_text(encoding="utf-8"))
    assert vscode["version"] == version

    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "canonical" / "expected-needs-v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert fixture["extensions"]["quartoNeeds"]["generator"]["version"] == version
