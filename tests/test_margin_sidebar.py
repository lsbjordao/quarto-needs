from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "_extensions" / "quarto-needs"
SELF_EXAMPLE = ROOT / "examples" / "quarto-needs"


def test_margin_sidebar_filter_is_registered_and_assets_exist() -> None:
    manifest = yaml.safe_load((EXTENSION / "_extension.yml").read_text(encoding="utf-8"))
    filters = manifest["contributes"]["filters"]

    assert "margin-sidebar.lua" in filters
    assert (EXTENSION / "margin-sidebar.lua").is_file()
    assert (EXTENSION / "margin-sidebar.js").is_file()
    assert (EXTENSION / "margin-sidebar.css").is_file()


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
