"""The comparison page makes claims about other people's software.

Nothing in this repository can check whether those claims are true, which is
exactly why the parts that *can* be checked are checked here: that every
competitor cell carries a source, that the Quarto-Needs column comes from
the stability registry rather than a free reading of the README, and that no
experimental capability is presented next to a competitor's mature one
without saying which it is.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from quarto_needs import surface

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("docs/src/comparison.qmd", "docs/src/comparison.pt-BR.qmd")
COMPETITORS = ("Sphinx-Needs", "StrictDoc", "Doorstop", "OpenFastTrace")

# The versions every claim on the page was verified against. Changing a
# version here without re-verifying the page is the mistake this guards.
VERIFIED_VERSIONS = {
    "Sphinx-Needs": "8.5.0",
    "StrictDoc": "0.29.0",
    "Doorstop": "3.2",
    "OpenFastTrace": "4.9.0",
}
CONSULTED = "2026-09-10"


def read(page: str) -> str:
    return (ROOT / page).read_text(encoding="utf-8")


@pytest.mark.parametrize("page", PAGES)
def test_every_compared_tool_is_pinned_to_a_verified_version(page):
    """"Sphinx-Needs does not do X" without a version ages badly."""
    text = read(page)
    for tool, version in VERIFIED_VERSIONS.items():
        assert f"{tool} {version}" in text, f"{page} does not pin {tool}"


@pytest.mark.parametrize("page", PAGES)
def test_every_footnote_carries_a_url_and_a_consultation_date(page):
    text = read(page)
    definitions = re.findall(r"^\[\^([\w-]+)\]:(.*)$", text, re.MULTILINE)
    assert definitions, f"{page} has no footnote definitions"
    for name, body in definitions:
        assert "http" in body, f"{page} footnote {name} has no URL"
        assert CONSULTED in body, f"{page} footnote {name} has no consultation date"


@pytest.mark.parametrize("page", PAGES)
def test_every_footnote_reference_resolves(page):
    text = read(page)
    defined = set(re.findall(r"^\[\^([\w-]+)\]:", text, re.MULTILINE))
    used = set(re.findall(r"\[\^([\w-]+)\](?!:)", text))
    assert used - defined == set(), f"{page} cites undefined footnotes"
    assert defined - used == set(), f"{page} defines unused footnotes"


@pytest.mark.parametrize("page", PAGES)
def test_every_competitor_cell_is_sourced_or_explicitly_unverified(page):
    """A cell is either footnoted or says it was not verified. Never blank."""
    text = read(page)
    unverified = "not verified" if page.endswith("comparison.qmd") else "não verificado"
    rows = [line for line in text.splitlines() if line.startswith("| **")]
    assert len(rows) >= 6, f"{page} comparison table looks truncated"
    for row in rows:
        # An unescaped pipe inside a cell silently shifts every column after
        # it, which puts a claim under the wrong tool's name.
        assert row.count("|") == 7, (
            f"{page}: {row.split('|')[1].strip()} has {row.count('|')} pipes, "
            "expected 7 -- escape a literal | inside a cell"
        )
    for row in rows:
        # Columns 3..6 are the four competitors; column 2 is Quarto-Needs.
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        for tool, cell in zip(COMPETITORS, cells[2:6]):
            assert cell, f"{page}: empty cell for {tool} in {cells[0]}"
            assert "[^" in cell or unverified in cell, (
                f"{page}: {tool} cell in {cells[0]} has neither a source "
                f"nor an explicit unverified marker: {cell!r}"
            )


@pytest.mark.parametrize("page", PAGES)
def test_the_quarto_needs_column_comes_from_the_stability_registry(page):
    """Generated from the registry, not from a reading of the README."""
    text = read(page)
    for tier in surface.TIERS:
        assert surface.contract_block(tier) in text, f"{page} is stale for {tier}"


@pytest.mark.parametrize("page", PAGES)
def test_no_experimental_capability_is_listed_without_its_tier(page):
    """Advertising OSLC beside a competitor's mature feature is the failure
    mode the rest of this page exists to avoid.
    """
    text = read(page)
    experimental = [
        item.name.split()[0]
        for item in surface.COMMANDS
        if item.tier == surface.EXPERIMENTAL
    ]
    rows = [line for line in text.splitlines() if line.startswith("| **")]
    for row in rows:
        quarto_cell = [cell.strip() for cell in row.strip("|").split("|")][1]
        for name in experimental:
            if re.search(rf"`{re.escape(name)}\b", quarto_cell):
                assert "experimental" in quarto_cell.lower(), (
                    f"{page}: {name} appears without its tier in {row[:60]!r}"
                )


@pytest.mark.parametrize("page", PAGES)
def test_no_sphinx_needs_compatibility_is_claimed(page):
    text = read(page).lower()
    for phrase in ("sphinx-needs compatible", "compatible with sphinx-needs",
                   "compatível com sphinx-needs"):
        assert phrase not in text, f"{page} claims Sphinx-Needs compatibility"


@pytest.mark.parametrize("page", PAGES)
def test_no_marketing_superlatives(page):
    text = read(page).lower()
    for word in ("unlike every other", "the only tool", "first and only",
                 "único no mercado", "diferente de todos"):
        assert word not in text, f"{page} contains marketing language: {word}"


@pytest.mark.parametrize("page", PAGES)
def test_the_when_not_to_use_section_names_a_better_tool_per_case(page):
    """Performative humility names no alternative. This one has to."""
    text = read(page)
    section = text.split("{#when-not}", 1)[1]
    for tool in COMPETITORS:
        assert tool in section, f"{page}: 'when not to use' never names {tool}"
    assert "DOORS" in section or "Polarion" in section


@pytest.mark.parametrize("page", PAGES)
def test_commercial_tools_are_a_category_not_a_table_row(page):
    text = read(page)
    table = text.split("{#table}", 1)[1].split("{#surface}", 1)[0]
    for name in ("DOORS", "Polarion", "Codebeamer"):
        assert name not in table, f"{page} compares {name} row by row"
        assert name in text, f"{page} never explains why {name} is out of scope"


def test_the_readme_points_at_the_comparison():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/src/comparison.qmd" in text
    assert "When not to use Quarto-Needs" in text
