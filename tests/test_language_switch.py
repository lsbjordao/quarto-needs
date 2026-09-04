# The navbar language switch is project-level tooling shared byte-for-byte by
# every multilingual project (docs/manual, examples/book,
# examples/quarto-needs); these tests pin both that sync and its theming
# contract.

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROJECTS = ("docs/manual", "examples/book", "examples/quarto-needs")


def _css(project: str) -> str:
    return (ROOT / project / "language-switch.css").read_text(encoding="utf-8")


def _html(project: str) -> str:
    return (ROOT / project / "language-switch.html").read_text(encoding="utf-8")


def test_language_switch_stays_in_sync_across_projects() -> None:
    for project in PROJECTS[1:]:
        assert _css(project) == _css(PROJECTS[0])
        assert _html(project) == _html(PROJECTS[0])


def test_language_switch_resolves_colors_through_live_theme_variables() -> None:
    """The switcher's colors must come from Bootstrap theme variables, the
    same ones the rest of the UI uses, so a dark theme (or a runtime toggle)
    yields a dark pill with light ink automatically. A fallback hardcoded to
    a light value at the top level of the var() chain is the dark-theme
    black-on-light / white-on-light bug this file exists to prevent."""
    for project in PROJECTS:
        css = _css(project)
        assert "var(--qn-language-bg, var(--bs-body-bg," in css
        assert "var(--qn-language-fg, var(--bs-body-color," in css
        assert "var(--qn-language-hover, var(--bs-tertiary-bg," in css
        assert "var(--qn-language-border, var(--bs-border-color," in css
        for variable, light in (
            ("--qn-language-bg", "#fff)"),
            ("--qn-language-fg", "#212529)"),
            ("--qn-language-hover", "#f8f9fa)"),
            ("--qn-language-border", "#dee2e6)"),
        ):
            assert f"var({variable}, {light}" not in css


def test_language_switch_does_not_snapshot_page_colors_in_js() -> None:
    """Reading computed colors once at load time froze whatever the page
    looked like at that instant: on dark sites the snapshot missed the
    theme's body background and the switcher fell back to light chrome with
    white text. CSS variables adapt live; the script should not fight them."""
    for project in PROJECTS:
        html = _html(project)
        assert "getComputedStyle" not in html
        assert "setProperty" not in html
