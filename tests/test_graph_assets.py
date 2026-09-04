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
from quarto_needs.baseline import build_baseline, load_baseline, write_baseline
from quarto_needs.config import load_config

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "_extensions" / "quarto-needs" / "vendor" / "cytoscape"
MANIFEST = VENDOR / "ASSET_MANIFEST.json"
CYTOSCAPE = VENDOR / "cytoscape.min.js"
NAVIGATOR_VENDOR = ROOT / "_extensions" / "quarto-needs" / "vendor" / "cytoscape-navigator"
NAVIGATOR_MANIFEST = NAVIGATOR_VENDOR / "ASSET_MANIFEST.json"
NAVIGATOR_JS = NAVIGATOR_VENDOR / "cytoscape-navigator.js"
GRAPH_JS = ROOT / "_extensions" / "quarto-needs" / "graph.js"
GRAPH_CSS = ROOT / "_extensions" / "quarto-needs" / "graph.css"
GRAPH_LUA = ROOT / "_extensions" / "quarto-needs" / "graph.lua"
VIEWS_LUA = ROOT / "_extensions" / "quarto-needs" / "views.lua"
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


def test_cytoscape_navigator_is_vendored_and_not_remote() -> None:
    assert NAVIGATOR_JS.is_file()
    assert NAVIGATOR_JS.stat().st_size > 10_000
    assert b"unpkg.com" not in NAVIGATOR_JS.read_bytes()


def test_cytoscape_navigator_matches_its_recorded_checksum() -> None:
    manifest = json.loads(NAVIGATOR_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["integrity"].startswith("sha256-")
    expected = manifest["integrity"].removeprefix("sha256-")
    assert _sha256(NAVIGATOR_JS) == expected


def test_cytoscape_navigator_manifest_pins_version_and_license() -> None:
    manifest = json.loads(NAVIGATOR_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["name"] == "cytoscape-navigator"
    assert manifest["version"]
    # MIT, not GPLv3 — the license actually checked before vendoring, unlike
    # the SVG-export slice's cytoscape-svg near-miss (GPLv3 in every release).
    assert manifest["license"] == "MIT"


def test_cytoscape_navigator_license_is_recorded() -> None:
    license_file = NAVIGATOR_VENDOR / "LICENSE"
    assert license_file.is_file()
    contents = license_file.read_text(encoding="utf-8")
    assert "Permission is hereby granted" in contents


def test_navigator_is_loaded_after_cytoscape_core_and_before_graph_js() -> None:
    views = VIEWS_LUA.read_text(encoding="utf-8")
    assert 'version = "0.1.9"' in views
    assert views.index('"vendor/cytoscape/cytoscape.min.js"') < views.index(
        '"vendor/cytoscape-navigator/cytoscape-navigator.js"'
    )
    assert views.index('"vendor/cytoscape-navigator/cytoscape-navigator.js"') < views.index('"graph.js"')
    assert '"vendor/cytoscape-navigator/cytoscape.js-navigator.css"' in views


def test_graph_lua_gives_each_minimap_a_unique_id() -> None:
    """cytoscape-navigator's own container lookup is a global
    getElementById/getElementsByClassName with no per-graph scoping — a
    shared id or class would make a second need-graph instance's minimap
    grab the first instance's panel. instance_id keeps them apart."""
    lua = GRAPH_LUA.read_text(encoding="utf-8")
    assert "-minimap" in lua
    assert 'data-need-graph-minimap="' in lua
    assert 'class="cytoscape-navigator"' in lua


def test_graph_js_wires_the_minimap_when_the_plugin_loaded() -> None:
    source = GRAPH_JS.read_text(encoding="utf-8")
    minimap_start = source.index("data-need-graph-minimap")
    block = source[minimap_start : minimap_start + 300]
    assert 'typeof cy.navigator === "function"' in block
    assert "cy.navigator(" in block


def test_graph_css_overrides_the_navigators_default_page_corner_panel() -> None:
    """The vendored default is position:fixed, 400x400, bottom-right of the
    whole page — a corner of the actual canvas is what's wanted here."""
    source = GRAPH_CSS.read_text(encoding="utf-8")
    assert ".need-graph-canvas .cytoscape-navigator" in source
    assert "position: absolute" in source


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


def test_graph_canvas_becomes_keyboard_focusable_not_aria_hidden() -> None:
    """A focusable element left aria-hidden is a real WCAG anti-pattern
    (phantom focus a screen reader user can tab into but gets nothing
    from) — once the canvas gets a tabindex, aria-hidden must go, and
    role="img" (implying static, non-interactive content) must go too."""
    source = GRAPH_JS.read_text(encoding="utf-8")
    assert 'canvasRoot.setAttribute("tabindex", "0")' in source
    assert 'canvasRoot.removeAttribute("aria-hidden")' in source
    assert 'canvasRoot.setAttribute("role", "group")' in source
    assert 'canvasRoot.setAttribute("aria-hidden", "true")' not in source


def test_graph_js_defines_a_visible_keyboard_cursor_style() -> None:
    source = GRAPH_JS.read_text(encoding="utf-8")
    assert "keyboard-focus-node" in source
    # Cytoscape classes need a style rule to render at all — a bare
    # .addClass() with no matching selector is a silent no-op.
    assert '"node.keyboard-focus-node"' in source


def test_graph_js_arrow_keys_cycle_all_visible_nodes_not_topology() -> None:
    """Neighbor-based 'next/previous' has no stable meaning once you've
    moved (each node has a different neighbor list, so there's no
    guaranteed way back) — a linear cycle through every visible node in
    stable id order is fully reversible instead."""
    source = GRAPH_JS.read_text(encoding="utf-8")
    keydown_start = source.index('canvasRoot.addEventListener("keydown"')
    keydown_end = source.index("\n      });\n", keydown_start)
    block = source[keydown_start:keydown_end]

    assert "ArrowRight" in block
    assert "ArrowLeft" in block
    assert "visibleNodesSorted()" in block
    assert 'cy.nodes(":visible")' in source
    assert ".emit(\"tap\")" in block


def test_graph_js_enter_activates_via_the_real_tap_event() -> None:
    """Re-emitting the real tap event (rather than duplicating its body)
    means both existing tap listeners — this file's popup/highlight, and
    graph-context.js's shared quarto-needs-node-focus dispatch — run
    unchanged for a keyboard activation exactly as they do for a mouse
    tap, with zero duplicated logic."""
    source = GRAPH_JS.read_text(encoding="utf-8")
    keydown_start = source.index('canvasRoot.addEventListener("keydown"')
    keydown_end = source.index("\n      });\n", keydown_start)
    block = source[keydown_start:keydown_end]

    assert '"Enter"' in block
    assert '" "' in block


def test_graph_js_popup_shows_impact_rows_when_present_on_the_node() -> None:
    """Mirrors the existing Change row's own precedent exactly: the popup
    doesn't know about "modes" at all, it just presents whatever node data
    fields happen to be set — Impact mode setting them, and Reset/leaving
    Impact mode clearing them, is what makes these rows mode-scoped."""
    source = GRAPH_JS.read_text(encoding="utf-8")
    popup_start = source.index("function buildNodePopup(node)")
    popup_end = source.index("\n    return popup;\n", popup_start)
    block = source[popup_start:popup_end]

    assert "data.impactDistance" in block
    assert "data.impactOrigin" in block
    assert "data.impactClassification" in block
    assert "data.impactPath" in block


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


def test_graph_lua_ships_a_fullscreen_button_next_to_reset() -> None:
    lua = (ROOT / "_extensions" / "quarto-needs" / "graph.lua").read_text(encoding="utf-8")
    assert '<button type="button" class="need-graph-fullscreen">' in lua
    assert 'views.tr("Fullscreen", "Tela cheia")' in lua
    assert lua.index('need-graph-reset') < lua.index('need-graph-fullscreen')


def test_graph_js_feature_detects_the_fullscreen_api() -> None:
    """An old browser or a restrictive iframe policy without
    requestFullscreen must hide the button entirely rather than leave a
    dead control on the page."""
    source = GRAPH_JS.read_text(encoding="utf-8")
    fullscreen_start = source.index("need-graph-fullscreen")
    block = source[fullscreen_start : fullscreen_start + 800]
    assert "requestFullscreen" in block
    assert ".remove()" in block


def test_graph_js_fullscreen_toggle_checks_the_active_element() -> None:
    """Clicking must toggle based on whether THIS graph's own container is
    the fullscreen element — not any global on/off flag — so multiple
    need-graph instances on one page never fight over shared state."""
    source = GRAPH_JS.read_text(encoding="utf-8")
    assert "document.fullscreenElement ===" in source
    assert ".exitFullscreen()" in source
    assert ".requestFullscreen()" in source


def test_graph_js_fullscreenchange_restabilizes_the_canvas() -> None:
    """Entering/exiting fullscreen changes the container's real pixel size
    without Cytoscape being told — reuse the exact same resize+fit pattern
    already used to recover from a 0-width init, rather than new logic."""
    source = GRAPH_JS.read_text(encoding="utf-8")
    change_start = source.index('addEventListener("fullscreenchange"')
    change_end = source.index("\n        });", change_start)
    block = source[change_start:change_end]
    assert "stabilize()" in block


def test_graph_js_announces_when_fullscreen_is_denied() -> None:
    source = GRAPH_JS.read_text(encoding="utf-8")
    assert ".catch(" in source
    assert "Fullscreen unavailable" in source


def test_graph_css_sizes_the_canvas_to_fill_fullscreen() -> None:
    source = GRAPH_CSS.read_text(encoding="utf-8")
    assert ".need-graph-container:fullscreen" in source
    assert ".need-graph-container:fullscreen .need-graph-canvas" in source


def test_graph_css_keeps_native_controls_readable_on_dark_themes() -> None:
    """Native <select>/<input> ink stays at the UA's light-scheme default no
    matter what the page theme does, so under a dark Quarto theme the mode,
    filter, traversal, and search controls render black-on-dark. Every
    toolbar control must carry the theme variables explicitly, and the
    container must follow the page's dark scheme (data-bs-theme, quarto-dark)
    so the dropdown popup and its arrow render dark too."""
    source = GRAPH_CSS.read_text(encoding="utf-8")
    rule_start = source.index(".need-graph-controls select")
    rule_end = source.index("}", rule_start)
    rule = source[rule_start:rule_end]
    assert 'input[type="search"]' in rule
    assert "var(--bs-body-bg" in rule
    assert "var(--bs-body-color" in rule
    assert "var(--bs-border-color" in rule
    dark_start = source.index('[data-bs-theme="dark"] .need-graph-container')
    dark_end = source.index("}", dark_start)
    assert "color-scheme: dark" in source[dark_start:dark_end]


def test_graph_lua_ships_a_png_export_button_after_fullscreen() -> None:
    lua = (ROOT / "_extensions" / "quarto-needs" / "graph.lua").read_text(encoding="utf-8")
    assert '<button type="button" class="need-graph-export-png">' in lua
    assert 'views.tr("Export PNG", "Exportar PNG")' in lua
    assert lua.index("need-graph-fullscreen") < lua.index("need-graph-export-png")


def test_graph_js_exports_png_via_the_pinned_cytoscape_build() -> None:
    """cy.svg() does not exist on the vendored core (cytoscape-svg is a
    separate, GPLv3-licensed plugin — a real license conflict for an
    MIT project, deliberately not vendored). PNG export uses only what
    the pinned build already ships."""
    source = GRAPH_JS.read_text(encoding="utf-8")
    export_start = source.index("need-graph-export-png")
    block = source[export_start : export_start + 700]
    assert "cy.png(" in block
    assert "full: true" in block
    assert "cy.svg(" not in block


def test_graph_js_png_export_downloads_a_named_file() -> None:
    """The exported filename carries the graph's own instance id so
    multiple need-graph embeds on one page never collide or overwrite
    each other's downloads."""
    source = GRAPH_JS.read_text(encoding="utf-8")
    export_start = source.index("need-graph-export-png")
    block = source[export_start : export_start + 700]
    assert ".download = " in block
    assert "container.id" in block
    assert ".click()" in block


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
    dot = target.with_suffix(".dot")
    assert dot.is_file()
    assert '"ADV-1"' in dot.read_text(encoding="utf-8")


def test_write_c4_projections_writes_one_file_per_system_and_container_level(tmp_path) -> None:
    (tmp_path / "arch.qmd").write_text(
        '::: {.need #SYS-1 type="system" status="draft"}\n## System\n:::\n\n'
        '::: {.need #CONTAINER-1 type="container" status="draft" '
        'part-of="SYS-1" technology="Python"}\n## Container\n:::\n',
        encoding="utf-8",
    )
    result = analyze_project(tmp_path)
    assert result.snapshot is not None

    graph_output.write_c4_projections(tmp_path, result.snapshot)

    graph_dir = tmp_path / ".quarto-needs" / "graphs"
    context_path = graph_dir / "c4-context-SYS-1.json"
    container_path = graph_dir / "c4-container-SYS-1.json"
    component_path = graph_dir / "c4-component-CONTAINER-1.json"
    assert context_path.is_file()
    assert container_path.is_file()
    assert component_path.is_file()

    context_payload = json.loads(context_path.read_text(encoding="utf-8"))
    assert context_payload["schemaVersion"] == "c4-view-v1"
    assert context_payload["kind"] == "mermaid"
    assert context_payload["source"].splitlines()[0] == "C4Context"

    container_payload = json.loads(container_path.read_text(encoding="utf-8"))
    assert "System_Boundary(" in container_payload["source"]

    component_payload = json.loads(component_path.read_text(encoding="utf-8"))
    assert component_payload["kind"] == "mermaid"
    assert component_payload["source"].splitlines()[0] == "C4Component"


def test_write_c4_projections_also_writes_the_structurizr_plantuml_and_d2_backends(
    tmp_path,
) -> None:
    (tmp_path / "arch.qmd").write_text(
        '::: {.need #SYS-1 type="system" status="draft"}\n## System\n:::\n\n'
        '::: {.need #CONTAINER-1 type="container" status="draft" '
        'part-of="SYS-1" technology="Python"}\n## Container\n:::\n',
        encoding="utf-8",
    )
    result = analyze_project(tmp_path)
    assert result.snapshot is not None

    graph_output.write_c4_projections(tmp_path, result.snapshot)

    graph_dir = tmp_path / ".quarto-needs" / "graphs"
    for backend, marker in (
        ("structurizr", "workspace {"),
        ("plantuml", "@startuml"),
        ("d2", "shape:"),
    ):
        payload = json.loads(
            (graph_dir / f"c4-context-SYS-1.{backend}.json").read_text(encoding="utf-8")
        )
        assert payload["schemaVersion"] == "c4-view-v1"
        assert payload["kind"] == "source"
        assert payload["language"] == backend
        assert marker in payload["source"]

    component_payload = json.loads(
        (graph_dir / "c4-component-CONTAINER-1.structurizr.json").read_text(encoding="utf-8")
    )
    assert "= container " in component_payload["source"]


def test_write_c4_projections_writes_a_code_table_for_every_component(tmp_path) -> None:
    (tmp_path / "arch.qmd").write_text(
        '::: {.need #CONTAINER-1 type="container" status="draft"}\n## Container\n:::\n\n'
        '::: {.need #COMPONENT-1 type="component" status="draft" '
        'part-of="CONTAINER-1"}\n## Component\n:::\n',
        encoding="utf-8",
    )
    result = analyze_project(tmp_path)
    assert result.snapshot is not None

    graph_output.write_c4_projections(tmp_path, result.snapshot)

    graph_dir = tmp_path / ".quarto-needs" / "graphs"
    code_path = graph_dir / "c4-code-COMPONENT-1.json"
    assert code_path.is_file()

    code_payload = json.loads(code_path.read_text(encoding="utf-8"))
    assert code_payload["schemaVersion"] == "c4-view-v1"
    assert code_payload["kind"] == "table"
    assert code_payload["source"].splitlines()[0].startswith("|")


def test_write_c4_projections_is_a_no_op_when_there_are_no_systems_or_containers(tmp_path) -> None:
    (tmp_path / "arch.qmd").write_text(
        '::: {.need #REQ-1 type="functional-requirement" status="draft"}\n## Req\n:::\n',
        encoding="utf-8",
    )
    result = analyze_project(tmp_path)
    assert result.snapshot is not None

    graph_output.write_c4_projections(tmp_path, result.snapshot)

    graph_dir = tmp_path / ".quarto-needs" / "graphs"
    assert not graph_dir.exists() or list(graph_dir.glob("c4-*.json")) == []


# --- the overlay annotation artifact ---------------------------------------------

CHAIN_V1 = (
    "::: {.need #STK-1 type=need status=approved priority=high}\n"
    "\n## Stake\nStakeholder concern.\n:::\n"
    "\n"
    "::: {.need #SYS-1 type=system-requirement status=approved priority=high "
    'derives-from="STK-1" verified-by="TC-9"}\n'
    "\n## System\nThe system shall do it.\n:::\n"
    "\n"
    "::: {.need #TC-9 type=test-case status=passed}\n\n## Verify\nChecks the system.\n:::\n"
)

CHAIN_V2 = CHAIN_V1.replace("Stakeholder concern.", "Stakeholder concern, revised.")

DIFF_V1 = (
    '::: {.need #REQ-1 type="functional-requirement" status="approved"}\n'
    "verified-by:\n  - TC-1\n  - TC-2\n  - TC-3\n\n## Authenticate\nOriginal body.\n:::\n"
    "\n"
    '::: {.need #REQ-2 type="functional-requirement" status="draft"}\n\n## Legacy\nOnly in the baseline.\n:::\n'
    "\n"
    '::: {.need #TC-1 type="test-case" status="passed"}\n\n## Login test\nSigns a user in.\n:::\n'
    "\n"
    '::: {.need #TC-2 type="test-case" status="passed"}\n\n## Logout test\nSigns a user out.\n:::\n'
    "\n"
    '::: {.need #TC-3 type="test-case" status="passed"}\n\n## Session test\nChecks the session.\n:::\n'
)

DIFF_V2 = (
    '::: {.need #REQ-1 type="functional-requirement" status="approved"}\n'
    "verified-by: TC-2\n\n## Authenticate\nEdited body.\n:::\n"
    "\n"
    '::: {.need #REQ-3 type="functional-requirement" status="approved"}\n'
    "verified-by: TC-2\n\n## Fresh\nA brand-new requirement.\n:::\n"
    "\n"
    '::: {.need #TC-1 type="test-case" status="passed"}\n\n## Login test\nSigns a user in.\n:::\n'
    "\n"
    '::: {.need #TC-2 type="test-case" status="passed"}\n\n## Logout test\nSigns a user out.\n:::\n'
)

DEFAULT_BASELINE_FILE = Path(".quarto-needs") / "baseline.json"


def _analyze(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None
    return result


def _write_baseline(root: Path, body: str) -> None:
    (root / "graph.qmd").write_text(body, encoding="utf-8")
    result = _analyze(root)
    write_baseline(root / DEFAULT_BASELINE_FILE, build_baseline(result.snapshot, load_config(root)), force=True)


def test_write_graph_overlays_extracts_diff_annotations_from_the_built_overlays(
    tmp_path: Path,
) -> None:
    _write_baseline(tmp_path, DIFF_V1)
    (tmp_path / "graph.qmd").write_text(DIFF_V2, encoding="utf-8")
    result = _analyze(tmp_path)

    overlays = graph_output.build_graph_overlays(
        result.snapshot,
        load_config(tmp_path),
        baseline_payload=load_baseline(tmp_path / DEFAULT_BASELINE_FILE),
    )

    assert overlays["schemaVersion"] == "need-graph-overlays-v1"
    assert overlays["view"] == "need-graph-1"
    diff = overlays["diff"]
    assert diff["nodes"] == {"REQ-1": "modified", "REQ-3": "added"}
    ghosts = {ghost["id"]: ghost for ghost in diff["ghostNodes"]}
    assert set(ghosts) == {"REQ-2", "TC-3"}
    assert ghosts["REQ-2"]["change"] == "removed"
    assert ["REQ-3", "verified-by", "TC-2", "added"] in diff["edges"]
    removed_edge = [
        edge
        for edge in diff["ghostEdges"]
        if edge["source"] == "REQ-1" and edge["target"] == "TC-3"
    ]
    assert removed_edge and removed_edge[0]["change"] == "removed"


def test_write_graph_overlays_extracts_impact_annotations_from_the_built_overlays(
    tmp_path: Path,
) -> None:
    _write_baseline(tmp_path, CHAIN_V1)
    (tmp_path / "graph.qmd").write_text(CHAIN_V2, encoding="utf-8")
    result = _analyze(tmp_path)

    overlays = graph_output.build_graph_overlays(
        result.snapshot,
        load_config(tmp_path),
        baseline_payload=load_baseline(tmp_path / DEFAULT_BASELINE_FILE),
    )

    impact = overlays["impact"]
    entries = {entry["id"]: entry for entry in impact["entries"]}
    assert entries["SYS-1"] == {
        "id": "SYS-1",
        "origin": "STK-1",
        "distance": 1,
        "path": ["STK-1", "SYS-1"],
        "classification": "direct",
    }
    assert entries["TC-9"]["distance"] == 2
    assert ("SYS-1", "derives-from", "STK-1") in [
        (source, relation, target) for source, relation, target in impact["pathEdges"]
    ]
    assert ("SYS-1", "verified-by", "TC-9") in [
        (source, relation, target) for source, relation, target in impact["pathEdges"]
    ]


def test_write_graph_overlays_is_a_no_op_without_a_baseline(tmp_path: Path) -> None:
    _write_baseline(tmp_path, CHAIN_V1)
    (tmp_path / ".quarto-needs" / "baseline.json").unlink()
    result = _analyze(tmp_path)

    assert graph_output.write_graph_overlays(tmp_path, result.snapshot, load_config(tmp_path)) is None
    assert not (tmp_path / ".quarto-needs" / "graphs" / "need-graph-1-overlays.json").exists()


def test_write_default_projection_writes_the_overlays_artifact_when_a_baseline_exists(
    tmp_path: Path,
) -> None:
    _write_baseline(tmp_path, CHAIN_V1)
    (tmp_path / "graph.qmd").write_text(CHAIN_V2, encoding="utf-8")
    result = _analyze(tmp_path)

    target = graph_output.write_default_projection(tmp_path, result.snapshot, load_config(tmp_path))

    overlays_path = target.parent / "need-graph-1-overlays.json"
    assert overlays_path.is_file()
    payload = json.loads(overlays_path.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == "need-graph-overlays-v1"


def test_write_graph_overlays_degrades_gracefully_when_the_overlay_exceeds_budget(
    tmp_path: Path,
) -> None:
    """A too-large diff/impact traversal must not crash the build.

    write_graph_overlays already treats a missing baseline as "no artifact,
    not a failed build" — the same optional-presentation-artifact contract
    the named-query loop in write_default_projection already honors for
    GraphLimitExceeded. The overlay's own traversal (diff AND impact, over
    the full baseline-union graph) can exceed the configured budget even
    when the plain catalog view comfortably fits, since it isn't the same
    selection.
    """
    _write_baseline(tmp_path, CHAIN_V1)
    (tmp_path / "graph.qmd").write_text(CHAIN_V2, encoding="utf-8")
    (tmp_path / ".quarto-needs.toml").write_text(
        "[graph]\nmax-nodes = 1\n", encoding="utf-8"
    )
    result = _analyze(tmp_path)

    assert graph_output.write_graph_overlays(tmp_path, result.snapshot, load_config(tmp_path)) is None
    assert not (tmp_path / ".quarto-needs" / "graphs" / "need-graph-1-overlays.json").exists()


def test_write_graph_overlays_writes_one_overlay_per_allowlisted_named_query(
    tmp_path: Path,
) -> None:
    """Known limitation item 2's named follow-on: overlays covered only the
    default view before this. A named query's own overlay must reflect
    *its own* selection (a diff/impact traversal scoped to that query, not
    the default view's), so distances/classifications are correct relative
    to what that query actually shows — reusing the default overlay's data
    and filtering client-side would give wrong numbers, not just extra
    rows."""
    _write_baseline(tmp_path, CHAIN_V1)
    (tmp_path / "graph.qmd").write_text(CHAIN_V2, encoding="utf-8")
    (tmp_path / ".quarto-needs.toml").write_text(
        '[queries.sys-only]\nall = [{ field = "type", op = "eq", value = "system-requirement" }]\n'
        '[graph]\noverlay-queries = ["sys-only"]\n',
        encoding="utf-8",
    )
    result = _analyze(tmp_path)

    graph_output.write_default_projection(tmp_path, result.snapshot, load_config(tmp_path))

    view_id = graph_output.query_view_id("sys-only")
    overlay_path = tmp_path / ".quarto-needs" / "graphs" / f"{view_id}-overlays.json"
    assert overlay_path.is_file()
    payload = json.loads(overlay_path.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == "need-graph-overlays-v1"
    assert payload["view"] == view_id


def test_write_graph_overlays_skips_a_name_that_matches_no_configured_query(
    tmp_path: Path,
) -> None:
    """An optional presentation artifact, same contract as a missing
    baseline or a too-large overlay traversal — a typo'd or stale name in
    overlay-queries must never fail the build."""
    _write_baseline(tmp_path, CHAIN_V1)
    (tmp_path / "graph.qmd").write_text(CHAIN_V2, encoding="utf-8")
    (tmp_path / ".quarto-needs.toml").write_text(
        '[graph]\noverlay-queries = ["no-such-query"]\n', encoding="utf-8"
    )
    result = _analyze(tmp_path)

    # Must not raise.
    graph_output.write_default_projection(tmp_path, result.snapshot, load_config(tmp_path))
    graphs_dir = tmp_path / ".quarto-needs" / "graphs"
    assert not any("no-such-query" in f.name for f in graphs_dir.glob("*-overlays.json"))


def test_write_graph_overlays_writes_no_named_query_overlays_by_default(
    tmp_path: Path,
) -> None:
    """Regression guard: an empty/absent overlay-queries must behave
    exactly as it did before this slice — only the default view's overlay,
    nothing per named query, even when named queries are configured."""
    _write_baseline(tmp_path, CHAIN_V1)
    (tmp_path / "graph.qmd").write_text(CHAIN_V2, encoding="utf-8")
    (tmp_path / ".quarto-needs.toml").write_text(
        '[queries.sys-only]\nall = [{ field = "type", op = "eq", value = "system-requirement" }]\n',
        encoding="utf-8",
    )
    result = _analyze(tmp_path)

    graph_output.write_default_projection(tmp_path, result.snapshot, load_config(tmp_path))

    graphs_dir = tmp_path / ".quarto-needs" / "graphs"
    overlay_files = sorted(f.name for f in graphs_dir.glob("*-overlays.json"))
    assert overlay_files == ["need-graph-1-overlays.json"]


def test_write_graph_overlays_honors_the_configured_baseline_path(tmp_path: Path) -> None:
    (tmp_path / "baselines").mkdir()
    _write_baseline(tmp_path, CHAIN_V1)
    baseline_path = tmp_path / DEFAULT_BASELINE_FILE
    baseline_path.rename(tmp_path / "baselines" / "quarto-needs.json")
    config_text = '[graph]\nbaseline = "baselines/quarto-needs.json"\n'
    (tmp_path / ".quarto-needs.toml").write_text(config_text, encoding="utf-8")
    result = _analyze(tmp_path)

    assert (
        graph_output.write_graph_overlays(tmp_path, result.snapshot, load_config(tmp_path))
        is not None
    )
    assert (tmp_path / ".quarto-needs" / "graphs" / "need-graph-1-overlays.json").is_file()


def test_graph_lua_embeds_the_overlay_artifact_when_present() -> None:
    lua = (ROOT / "_extensions" / "quarto-needs" / "graph.lua").read_text(encoding="utf-8")

    assert "data-need-graph-overlays" in lua
    assert '-overlays.json"' in lua
    # The sibling file is validated as JSON before being embedded, never
    # interpolated unvalidated:
    assert "pandoc.json.decode" in lua
