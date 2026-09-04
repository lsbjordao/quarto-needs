from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "_extensions" / "quarto-needs"
SELF_EXAMPLE = ROOT / "examples" / "quarto-needs"
RESPONSIVE_PROBE = ROOT / "tests" / "browser" / "margin_sidebar_transition.mjs"


def render_margin_sidebar_fixture(tmp_path: Path, *, toggle: bool | None) -> str:
    project = tmp_path / ("toggle-on" if toggle else "toggle-off")
    project.mkdir()
    shutil.copytree(EXTENSION, project / "_extensions" / "quarto-needs")
    toggle_metadata = ""
    if toggle is not None:
        toggle_metadata = (
            "\nquarto-needs:\n"
            f"  margin-sidebar-toggle: {str(toggle).lower()}\n"
        )
    (project / "index.qmd").write_text(
        "---\n"
        'title: "Margin sidebar fixture"\n'
        "format:\n"
        "  html:\n"
        "    toc: true\n"
        "filters:\n"
        "  - _extensions/quarto-needs/margin-sidebar.lua\n"
        f"{toggle_metadata}"
        "---\n\n"
        "## Structural section\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["quarto", "render", "index.qmd"],
        cwd=project,
        check=True,
        text=True,
        capture_output=True,
    )
    return (project / "index.html").read_text(encoding="utf-8")


def rendered_toc_style_probe(tmp_path: Path) -> str:
    page = tmp_path / "toc-style-probe.html"
    stylesheet = (EXTENSION / "margin-sidebar.css").as_uri()
    page.write_text(
        "<!doctype html>\n"
        '<html><head><meta charset="utf-8">\n'
        "<style>\n"
        "body.quarto-light .nav-link { font-weight: 400; }\n"
        "body.quarto-dark .nav-link { font-weight: 300; }\n"
        "</style>\n"
        f'<link rel="stylesheet" href="{stylesheet}">\n'
        "</head><body class=\"quarto-light\">\n"
        '<div id="quarto-margin-sidebar"><nav role="doc-toc"><ul>\n'
        '<li><a id="structural" class="nav-link"><span class="header-section-number">4.1</span> Structural section</a></li>\n'
        '<li><a id="need" class="nav-link"><span class="need-id">FUN-001</span> Requirement</a></li>\n'
        '<li><a id="parent" class="nav-link">Parent</a><ul><li><a id="nested" class="nav-link"><span class="header-section-number">4.1.1</span> Nested section</a></li></ul></li>\n'
        "</ul></nav></div>\n"
        "<script>\n"
        "const weight = (id) => getComputedStyle(document.getElementById(id)).fontWeight;\n"
        'document.body.dataset.lightStructural = weight("structural");\n'
        'document.body.dataset.lightNeed = weight("need");\n'
        'document.body.dataset.lightNested = weight("nested");\n'
        'document.body.className = "quarto-dark";\n'
        'document.body.dataset.darkStructural = weight("structural");\n'
        'document.body.dataset.darkNeed = weight("need");\n'
        'document.body.dataset.darkNested = weight("nested");\n'
        "</script></body></html>\n",
        encoding="utf-8",
    )
    return subprocess.run(
        [
            "google-chrome",
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--dump-dom",
            page.as_uri(),
        ],
        check=True,
        text=True,
        capture_output=True,
    ).stdout


def rendered_responsive_sidebar_probe(tmp_path: Path) -> dict[str, object]:
    project = tmp_path / "responsive-sidebar"
    project.mkdir()
    shutil.copytree(EXTENSION, project / "_extensions" / "quarto-needs")
    (project / "_quarto.yml").write_text(
        "project:\n"
        "  type: book\n"
        "book:\n"
        '  title: "Responsive sidebar fixture"\n'
        "  sidebar:\n"
        "    collapse-level: 1\n"
        "  chapters:\n"
        "    - index.qmd\n"
        "format:\n"
        "  html:\n"
        "    toc: true\n"
        "filters:\n"
        "  - _extensions/quarto-needs/margin-sidebar.lua\n"
        "quarto-needs:\n"
        "  margin-sidebar-toggle: true\n",
        encoding="utf-8",
    )
    (project / "index.qmd").write_text(
        "---\n"
        'title: "Responsive sidebar probe"\n'
        "---\n\n"
        "## Structural section\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["quarto", "render", "index.qmd"],
        cwd=project,
        check=True,
        text=True,
        capture_output=True,
    )
    node = shutil.which("node")
    chrome = shutil.which("google-chrome")
    assert node is not None and chrome is not None
    result = subprocess.run(
        [
            node,
            str(RESPONSIVE_PROBE),
            str(project / "_book"),
            chrome,
        ],
        check=True,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def test_margin_sidebar_filter_is_registered_and_assets_exist() -> None:
    manifest = yaml.safe_load((EXTENSION / "_extension.yml").read_text(encoding="utf-8"))
    filters = manifest["contributes"]["filters"]

    assert "margin-sidebar.lua" in filters
    assert (EXTENSION / "margin-sidebar.lua").is_file()
    assert (EXTENSION / "margin-sidebar.js").is_file()
    assert (EXTENSION / "margin-sidebar.css").is_file()


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
@pytest.mark.parametrize(("toggle", "expects_script"), [(None, False), (True, True)])
def test_margin_sidebar_style_is_always_loaded_while_toggle_script_stays_opt_in(
    tmp_path: Path,
    toggle: bool | None,
    expects_script: bool,
) -> None:
    html = render_margin_sidebar_fixture(tmp_path, toggle=toggle)

    assert "margin-sidebar.css" in html
    assert ("margin-sidebar.js" in html) is expects_script


@pytest.mark.skipif(
    shutil.which("google-chrome") is None,
    reason="Google Chrome is not installed",
)
def test_margin_sidebar_bolds_only_numbered_top_level_sections_in_both_themes(
    tmp_path: Path,
) -> None:
    dom = rendered_toc_style_probe(tmp_path)

    assert 'data-light-structural="700"' in dom
    assert 'data-dark-structural="700"' in dom
    assert 'data-light-need="400"' in dom
    assert 'data-dark-need="300"' in dom
    assert 'data-light-nested="400"' in dom
    assert 'data-dark-nested="300"' in dom


@pytest.mark.skipif(
    shutil.which("quarto") is None
    or shutil.which("google-chrome") is None
    or shutil.which("node") is None,
    reason="Quarto, Google Chrome, and Node.js are required",
)
def test_collapsed_margin_sidebar_stays_hidden_across_left_sidebar_breakpoint(
    tmp_path: Path,
) -> None:
    transition = rendered_responsive_sidebar_probe(tmp_path)

    expanded = transition["expanded"]
    assert expanded["innerWidth"] == 1200
    assert expanded["leftDisplay"] != "none"
    assert expanded["marginDisplay"] != "none"
    assert expanded["toggleDisplay"] != "none"
    assert expanded["bodyCollapsed"] is False

    collapsed = transition["collapsed"]
    assert collapsed["innerWidth"] == 1200
    assert collapsed["marginDisplay"] == "none"
    assert collapsed["toggleDisplay"] != "none"
    assert collapsed["bodyCollapsed"] is True
    assert collapsed["storedCollapsed"] == "true"

    responsive = transition["responsive"]
    assert responsive["innerWidth"] == 991
    assert responsive["leftDisplay"] == "none"
    assert responsive["marginDisplay"] == "none"
    assert responsive["marginWidth"] == 0
    assert responsive["toggleDisplay"] != "none"
    assert responsive["bodyCollapsed"] is True
    assert responsive["storedCollapsed"] == "true"


def test_margin_sidebar_option_is_opt_in_and_targets_quarto_margin_toc() -> None:
    lua = (EXTENSION / "margin-sidebar.lua").read_text(encoding="utf-8")
    js = (EXTENSION / "margin-sidebar.js").read_text(encoding="utf-8")
    css = (EXTENSION / "margin-sidebar.css").read_text(encoding="utf-8")

    assert 'meta["quarto-needs"]' in lua
    assert 'options["margin-sidebar-toggle"]' in lua
    assert 'getElementById("quarto-margin-sidebar")' in js
    assert "localStorage" in js
    assert "fullcontent" in js
    assert "body.qn-margin-sidebar-collapsed #quarto-margin-sidebar" in css


def test_self_hosted_example_exercises_margin_and_native_left_sidebar_options() -> None:
    config = yaml.safe_load((SELF_EXAMPLE / "_quarto.yml").read_text(encoding="utf-8"))

    assert config["quarto-needs"]["margin-sidebar-toggle"] is True
    assert config["book"]["sidebar"]["collapse-level"] == 1


def test_self_hosted_bootstrap_filter_matches_canonical_filter() -> None:
    canonical = (EXTENSION / "margin-sidebar.lua").read_text(encoding="utf-8")
    bootstrap = (
        SELF_EXAMPLE / "_extensions" / "quarto-needs" / "margin-sidebar.lua"
    ).read_text(encoding="utf-8")

    assert bootstrap == canonical
