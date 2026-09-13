from __future__ import annotations

import json
from pathlib import Path

from quarto_needs import surface


ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
SNAPSHOTS = ROOT / "release-surfaces"


def _release_section(text: str, version: str) -> str:
    marker = f"## [{version}]"
    assert marker in text, f"CHANGELOG has no section for {version}"
    section = text.split(marker, 1)[1]
    return section.split("\n## [", 1)[0]


def _unreleased_section(text: str) -> str:
    marker = "## [Unreleased]"
    assert marker in text
    section = text.split(marker, 1)[1]
    return section.split("\n## [", 1)[0]


def test_current_registry_contract_lives_in_unreleased() -> None:
    """The live registry describes the next release, never a published one."""
    unreleased = _unreleased_section(CHANGELOG.read_text(encoding="utf-8"))
    for tier in surface.TIERS:
        assert surface.contract_block(tier) in unreleased, tier


def test_every_published_surface_snapshot_is_frozen_in_the_changelog() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    manifests = sorted(SNAPSHOTS.glob("*.json"))
    assert manifests, "at least one published release surface must be frozen"

    for path in manifests:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert path.stem == data["version"]
        assert data["tag"] == f"v{data['version']}"
        assert len(data["tag_commit"]) == 40
        int(data["tag_commit"], 16)

        section = _release_section(text, data["version"])
        for line in data["contract_lines"]:
            assert line in section, f"{path.name} drifted from CHANGELOG"


def test_published_sections_do_not_claim_to_be_generated_from_the_live_registry() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    for path in sorted(SNAPSHOTS.glob("*.json")):
        version = json.loads(path.read_text(encoding="utf-8"))["version"]
        section = _release_section(text, version)
        assert "generated from `src/quarto_needs/surface.py`" not in section
