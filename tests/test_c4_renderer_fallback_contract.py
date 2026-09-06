"""Regression contract for optional C4 renderer failures.

Quarto/Pandoc can surface a failed ``pandoc.pipe`` invocation as a PandocError
userdata. Optional C4 renderers must never let that failure abort a document:
the shortcode catches renderer exceptions and falls back to the already
materialized source block instead.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "_extensions" / "quarto-needs" / "c4.lua"
STARTER = ROOT / "templates" / "starter" / "_extensions" / "quarto-needs" / "c4.lua"


def test_optional_c4_renderers_are_guarded_at_the_shortcode_boundary() -> None:
    source = CANONICAL.read_text(encoding="utf-8")
    compact = "".join(source.split())

    assert "localfunctionsafe_renderer_call(renderer,...)" in compact
    assert "pcall(renderer,...)" in compact
    assert "tostring(value)" in compact
    assert "safe_renderer_call(views.diagram_inline_svg" in compact
    assert "safe_renderer_call(views.render_diagram_asset" in compact
    assert "pandoc.CodeBlock(decoded.source" in source


def test_starter_ships_the_same_fail_soft_c4_boundary() -> None:
    assert STARTER.read_text(encoding="utf-8") == CANONICAL.read_text(encoding="utf-8")
