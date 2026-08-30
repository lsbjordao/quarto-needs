"""Vendored-asset integrity for the interactive graph client.

Cytoscape.js is vendored into the extension with a pinned version, a recorded
license, and a SHA-256 checksum — it is never fetched at render time. These tests
verify that the shipped asset matches its recorded checksum, that the license is
present, and that the supporting client files ship the expected markers.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from quarto_needs import graph_output
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "_extensions" / "quarto-needs" / "vendor" / "cytoscape"
MANIFEST = VENDOR / "ASSET_MANIFEST.json"
CYTOSCAPE = VENDOR / "cytoscape.min.js"
GRAPH_JS = ROOT / "_extensions" / "quarto-needs" / "graph.js"
GRAPH_CSS = ROOT / "_extensions" / "quarto-needs" / "graph.css"
NEEDS_JS = ROOT / "_extensions" / "quarto-needs" / "needs.js"
MARGIN_SIDEBAR = ROOT / "_extensions" / "quarto-needs" / "margin-sidebar.js"

FIXTURE = ROOT / "tests" / "fixtures" / "graph" / "adversarial.qmd"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_cytoscape_is_vendored_and_not_remote() -> None:
    """The main vendored bundle is present and corporeal (not a 404 stub)."""
    assert CYTOSCAPE.is_file()
    assert CYTOSCAPE.stat().st_size > 400_000
    assert b"unpkg.com" not in CYTOSCAPE.read_bytes()


def test_cytoscape_matches_its_recorded_checksum() -> None:
    """The shipped bundle's SHA-256 equals the checksum in the manifest."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["integrity"].startswith("sha256-")
    expected = manifest["integrity"].removeprefix("sha256-")
    assert _sha256(CYTOSCAPE) == expected


def test_manifest_pins_version_and_source() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["name"] == "cytoscape"
    assert manifest["version"]
    assert manifest["license"] == "MIT"
    assert "unpkg.com" in manifest["sourceUrl"]


def test_cytoscape_license_is_recorded() -> None:
    license_file = VENDOR / "LICENSE"
    assert license_file.is_file()
    contents = license_file.read_text(encoding="utf-8")
    assert "Permission is hereby granted" in contents
    assert "Cytoscape" in contents


def test_graph_js_ships_expected_markers() -> None:
    source = GRAPH_JS.read_text(encoding="utf-8")
    assert "window.cytoscape" in source
    assert "data-need-graph-data" in source
    assert "schemaVersion" in source


def test_graph_css_ships_the_progressive_canvas() -> None:
    source = GRAPH_CSS.read_text(encoding="utf-8")
    assert ".need-graph-canvas" in source
    assert ".need-graph-controls" in source
    assert "--qn-graph-edge" in source
    assert "var(--bs-body-bg" in source


def test_graph_theme_sync_uses_the_registered_cytoscape_instance() -> None:
    source = NEEDS_JS.read_text(encoding="utf-8")
    assert "canvas.__quartoNeedsCy" in source
    assert "graphSurfaceIsDark" in source
    assert 'closest(".quarto-color-scheme-toggle")' in source
    assert 'document.addEventListener("quarto:themeChanged"' in source
    assert 'selector("edge[pathMember = \'true\']")' in source


@pytest.mark.requirement("FUN-009")
@pytest.mark.quarto_need_test_case("TC-014")
def test_margin_sidebar_toggle_stays_entirely_outside_page_toc() -> None:
    source = MARGIN_SIDEBAR.read_text(encoding="utf-8")
    assert "const gap = 8;" in source
    assert "rect.left - button.offsetWidth - gap" in source
    assert "button.offsetWidth / 2" not in source
    assert 'body.classList.add("fullcontent", FORCED)' in source
    assert 'localStorage.setItem(KEY, value ? "true" : "false")' in source


def test_graph_lua_registers_the_shortcode() -> None:
    shortcodes = (ROOT / "_extensions" / "quarto-needs" / "shortcodes.lua").read_text(
        encoding="utf-8"
    )
    compact = "".join(shortcodes.split())
    assert '["need-graph"]=render_need_graph' in compact
    assert "returngraph.render_shortcode(args,kwargs)" in compact


def test_graph_lua_reads_and_applies_a_filter_argument() -> None:
    """The need-graph shortcode honours a `filter` kwarg over node facets."""
    source = (ROOT / "_extensions" / "quarto-needs" / "graph.lua").read_text(encoding="utf-8")
    assert 'views.kwarg(kwargs, "filter", "")' in source
    assert "parse_filter" in source
    assert "filter_projection" in source


def test_default_projection_is_written_and_embeds_projection(tmp_path) -> None:
    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"))
    result = analyze_project(tmp_path)
    assert result.snapshot is not None
    target = graph_output.write_default_projection(tmp_path, result.snapshot, load_config(tmp_path))
    assert target.is_file()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == "graph-public-v1"
    assert payload["view"]["mode"] == "catalog"
    assert [node["id"] for node in payload["nodes"]] == ["ADV-1", "ADV-2"]
