from pathlib import Path

from quarto_needs.parser import parse_project


ROOT = Path(__file__).resolve().parents[1]


def test_showcase_architecture_decisions_have_dates_and_renderer_exposes_them():
    objects = parse_project(ROOT / "examples/book")
    decisions = [obj for obj in objects if obj.type == "architecture-decision"]

    assert decisions
    assert all(obj.attributes.get("date") for obj in decisions)

    canonical_renderer = (ROOT / "_extensions/quarto-needs/needs.lua").read_text(
        encoding="utf-8"
    )
    showcase_renderer = (
        ROOT / "examples/book/_extensions/quarto-needs/needs.lua"
    ).read_text(encoding="utf-8")

    expected = 'append_badge("date", date)'
    assert expected in canonical_renderer
    assert expected in showcase_renderer
