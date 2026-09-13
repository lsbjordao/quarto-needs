from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

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


def _historical_contract_section(
    text: str, version: str, source: str
) -> str:
    if source == "release":
        return _release_section(text, version)
    if source == "unreleased":
        return _unreleased_section(text)
    raise AssertionError(
        f"unsupported tag_changelog_section {source!r} for release {version}"
    )


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _published_manifests() -> tuple[tuple[Path, dict[str, object]], ...]:
    manifests = tuple(sorted(SNAPSHOTS.glob("*.json")))
    assert manifests, "at least one published release surface must be frozen"
    return tuple(
        (path, json.loads(path.read_text(encoding="utf-8"))) for path in manifests
    )


def _require_tag(tag: str) -> str:
    try:
        return _git("rev-parse", f"{tag}^{{commit}}")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        if os.environ.get("QUARTO_NEEDS_REQUIRE_RELEASE_TAGS") == "1":
            pytest.fail(f"published tag {tag} is unavailable: {exc}")
        pytest.skip(
            "published tags are not present in this shallow checkout; "
            "the Quality artifacts job verifies them with fetch-depth: 0"
        )


def test_current_registry_contract_lives_in_unreleased() -> None:
    """The live registry describes the next release, never a published one."""
    unreleased = _unreleased_section(CHANGELOG.read_text(encoding="utf-8"))
    for tier in surface.TIERS:
        assert surface.contract_block(tier) in unreleased, tier


def test_every_published_surface_snapshot_is_frozen_in_the_changelog() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")

    for path, data in _published_manifests():
        version = str(data["version"])
        tag_commit = str(data["tag_commit"])
        tag_section = str(data.get("tag_changelog_section", "release"))
        assert path.stem == version
        assert data["tag"] == f"v{version}"
        assert len(tag_commit) == 40
        int(tag_commit, 16)
        assert tag_section in {"release", "unreleased"}

        section = _release_section(text, version)
        for line in data["contract_lines"]:
            assert str(line) in section, f"{path.name} drifted from CHANGELOG"


def test_published_surface_snapshots_match_their_immutable_tags() -> None:
    """A mutable manifest cannot rewrite history already published by a tag."""
    for path, data in _published_manifests():
        tag = str(data["tag"])
        version = str(data["version"])
        anchored_commit = str(data["tag_commit"])
        tag_section = str(data.get("tag_changelog_section", "release"))

        resolved_commit = _require_tag(tag)
        assert resolved_commit == anchored_commit, (
            f"{path.name} anchors {anchored_commit}, but {tag} resolves to "
            f"{resolved_commit}"
        )

        historical_changelog = _git("show", f"{tag}:CHANGELOG.md")
        historical_section = _historical_contract_section(
            historical_changelog, version, tag_section
        )
        for line in data["contract_lines"]:
            assert str(line) in historical_section, (
                f"{path.name} does not match the immutable {tag} CHANGELOG"
            )


def test_published_sections_do_not_claim_to_be_generated_from_the_live_registry() -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    for _, data in _published_manifests():
        version = str(data["version"])
        section = _release_section(text, version)
        assert "generated from `src/quarto_needs/surface.py`" not in section
