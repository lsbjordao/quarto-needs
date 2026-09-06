"""Characterization of the extension-first distribution contract."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "_extensions" / "quarto-needs" / "_extension.yml"
PYPROJECT = ROOT / "pyproject.toml"
QUICKSTART = ROOT / "notes" / "quickstart.md"
CLI_PATH_CHECK = ROOT / "tools" / "check_installed_path.sh"
EXTENSION_FIRST_CHECK = ROOT / "tools" / "check_extension_first_path.sh"


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def test_extension_version_and_package_version_agree() -> None:
    extension_version = str(_manifest()["version"])
    package_version = str(_pyproject()["project"]["version"])
    assert extension_version == package_version, (
        f"extension {extension_version} != package {package_version}; "
        "the managed runtime installs the extension's own version exactly"
    )


def test_the_installed_package_reports_that_same_version() -> None:
    import quarto_needs

    assert quarto_needs.__version__ == str(_pyproject()["project"]["version"])


def test_manifest_contributes_filters_and_shortcodes() -> None:
    contributes = _manifest()["contributes"]
    assert contributes["filters"] == ["needs.lua", "margin-sidebar.lua"]
    assert contributes["shortcodes"] == ["shortcodes.lua", "adr-shortcodes.lua"]


def test_manifest_contributes_its_own_pre_render() -> None:
    contributes = _manifest()["contributes"]
    assert contributes["metadata"]["project"]["pre-render"] == [
        "quarto run _extensions/lsbjordao/quarto-needs/bootstrap-entry.py"
    ]


def test_quickstart_points_at_the_zero_friction_starter_template() -> None:
    quickstart = QUICKSTART.read_text(encoding="utf-8")
    assert "quarto use template lsbjordao/quarto-needs/templates/starter" in quickstart


@pytest.mark.requirement("SYS-009")
@pytest.mark.quarto_need_test_case("TC-031")
def test_manifest_declares_the_quarto_floor() -> None:
    assert _manifest()["quarto-required"] == ">=1.6.0"


def test_quickstart_leads_with_the_extension_not_a_pip_install() -> None:
    quickstart = QUICKSTART.read_text(encoding="utf-8")
    assert quickstart.index("quarto add lsbjordao/quarto-needs") < quickstart.index(
        "pip install quarto-needs"
    ), "the extension must be the first install step, not pip"
    assert "## Optional: the standalone CLI and editor tooling" in quickstart


def test_quickstart_authors_no_pre_render_hook() -> None:
    quickstart = QUICKSTART.read_text(encoding="utf-8")
    assert "pre-render: quarto-needs scan" not in quickstart
    assert "Activating the filter also installs the" in quickstart


def test_quickstart_documents_extension_activation() -> None:
    quickstart = QUICKSTART.read_text(encoding="utf-8")
    assert "quarto add lsbjordao/quarto-needs" in quickstart
    assert "filters:\n  - quarto-needs" in quickstart
    assert "_extensions/lsbjordao/quarto-needs/" in quickstart


def test_the_cli_path_check_still_covers_the_package_install() -> None:
    script = CLI_PATH_CHECK.read_text(encoding="utf-8")
    assert 'pip install --quiet "$REPO"' in script
    assert "command -v quarto-needs" in script
    assert "pre-render: quarto-needs scan" in script


def test_the_cli_path_check_is_no_longer_the_primary_scenario() -> None:
    script = CLI_PATH_CHECK.read_text(encoding="utf-8")
    assert "no longer the primary user-installation scenario" in script
    assert "check_extension_first_path.sh" in script


def test_the_primary_check_installs_no_engine_and_authors_no_pre_render() -> None:
    script = EXTENSION_FIRST_CHECK.read_text(encoding="utf-8")
    assert "filters:\n  - quarto-needs" in script
    assert "pre-render: quarto-needs scan" not in script
    assert "a quarto-needs executable is on PATH" in script
    assert "importable from the ambient interpreter" in script
    assert "PIP_NO_INDEX=1" in script
    assert '"$PROJECT/_extensions/lsbjordao"' in script


def test_installed_consumer_check_asserts_the_observable_render_contract() -> None:
    script = CLI_PATH_CHECK.read_text(encoding="utf-8")
    assert ".quarto-needs/needs.json" in script
    assert "{'REQ-1', 'TC-1'}" in script
    assert "graph['schemaVersion'] == '1'" in script
    assert 'data-need-count="1"' in script
    assert "need-card" in script
    assert "'{{<'" in script or "'{{<' " in script
    assert "need-view-warning" in script
