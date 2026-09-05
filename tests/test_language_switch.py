from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The navbar language switch is project-level tooling shared byte-for-byte by
# every multilingual project; these tests pin both that sync and its theming
# contract. Membership is existence-checked because the multilingual example
# roster changes over time; the self-hosted example is the only one today.
PROJECTS = tuple(
    project
    for project in ("docs/src", "examples/quarto-needs")
    if (ROOT / project / "language-switch.css").is_file()
)


def _css(project: str) -> str:
    raw = (ROOT / project / "language-switch.css").read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", raw, flags=re.S)


def _html(project: str) -> str:
    return (ROOT / project / "language-switch.html").read_text(encoding="utf-8")


def test_language_switch_stays_in_sync_across_projects() -> None:
    for project in PROJECTS[1:]:
        assert _css(project) == _css(PROJECTS[0])
        assert _html(project) == _html(PROJECTS[0])


def test_language_switch_pins_light_colors_and_scopes_dark_to_the_page_theme() -> None:
    """Two traps force explicit scoping. First, Quarto loads both theme
    bundles on dual-theme sites, and the dark theme's stylesheet declares its
    dark palette on unscoped :root selectors that also apply in light mode —
    var(--bs-body-bg) resolves to the dark background even on light pages,
    which used to paint the switcher dark under a white navbar. Second,
    quarto stamps data-bs-theme="dark" on the navbar element itself as a
    style island, so an ancestor attribute selector matches in every page
    theme. Light colors are therefore literal; dark colors are gated on
    :root[data-bs-theme="dark"], which only matches when the whole page —
    not just the navbar — is actually dark."""
    for project in PROJECTS:
        css = _css(project)
        dark_gated = css.count("body.quarto-dark #quarto-needs-language-switch")
        assert dark_gated >= 3, (
            "button, hover, and menu must have dark overrides gated on the "
            "page-level dark state (quarto's toggle class), not a navbar-local one"
        )
        assert css.count(':root[data-bs-theme="dark"] #quarto-needs-language-switch') >= dark_gated, (
            "bootstrap attribute mode must be gated alongside quarto's toggle class"
        )
        bare_dark = len(
            re.findall(r'(?<!:root)(?<!quarto-dark )\[data-bs-theme="dark"\] #quarto-needs-language-switch', css)
        )
        assert bare_dark == 0, "dark rules must not match a navbar-local style island"
        # Light chrome is literal, not variable-driven.
        assert "background: #fff !important" in css
        assert "color: #212529 !important" in css
        assert "background: #f8f9fa !important" in css
        # Dark chrome resolves through variables only inside dark-scoped rules.
        for variable in ("--bs-body-bg", "--bs-body-color", "--bs-tertiary-bg"):
            first_dark_use = css.index(f"var({variable}")
            assert css.count(f"var({variable}", 0, first_dark_use) == 0, (
                f"{variable} must never apply outside a dark-scoped rule"
            )


def test_language_switch_does_not_snapshot_page_colors_in_js() -> None:
    """Reading computed colors once at load time froze whatever the page
    looked like at that instant: on dark sites the snapshot missed the
    theme's body background and the switcher fell back to light chrome with
    white text. CSS variables adapt live; the script should not fight them."""
    for project in PROJECTS:
        html = _html(project)
        assert "getComputedStyle" not in html
        assert "setProperty" not in html
