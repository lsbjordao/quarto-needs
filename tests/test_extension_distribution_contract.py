"""Characterization of the *current* two-piece distribution contract.

Phase 8B replaces a distribution in which the user installs two things and
wires the engine together themselves. These tests pin that starting point so
the migration is visible in the diff rather than asserted in a commit
message: each one describes what is true today, and the task that changes
the behaviour is expected to change the test with it.

They are deliberately not the desired final contract. `test_..._today`
names mark the assertions Phase 8B is meant to invalidate; the render golden
in `test_installed_consumer_check_asserts_the_observable_render_contract` is
the part that must survive the migration unchanged, because it describes
what the user sees rather than how the engine got there.

Spec: docs/superpowers/specs/2026-09-02-extension-first-distribution-design.md
Plan: docs/superpowers/plans/2026-09-02-extension-first-distribution.md (Task 1)
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "_extensions" / "quarto-needs" / "_extension.yml"
PYPROJECT = ROOT / "pyproject.toml"
QUICKSTART = ROOT / "docs" / "quickstart.md"
CLI_PATH_CHECK = ROOT / "tools" / "check_installed_path.sh"
EXTENSION_FIRST_CHECK = ROOT / "tools" / "check_extension_first_path.sh"


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


def _pyproject() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


# --- Version parity ---------------------------------------------------------
#
# This one is not a migration marker: the managed runtime installs
# `quarto-needs==<extension version>`, so parity stops being a tidiness
# property and becomes the precondition that makes provisioning resolvable.


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


# --- What the manifest contributes today ------------------------------------


def test_manifest_contributes_filters_and_shortcodes() -> None:
    contributes = _manifest()["contributes"]

    assert contributes["filters"] == ["needs.lua", "margin-sidebar.lua"]
    assert contributes["shortcodes"] == ["shortcodes.lua", "adr-shortcodes.lua"]


def test_manifest_contributes_its_own_pre_render() -> None:
    """Migrated in Task 6, and this is the assertion that records it.

    This test previously pinned the opposite: the extension contributed no
    project metadata, so activating it gave a project filters and shortcodes
    but no engine -- which is exactly why the user had to wire one up. The
    contribution is what removes that step.

    `tests/test_extension_first_distribution.py` proves the contribution
    actually works when real Quarto renders a project; this only pins what
    the shipped manifest declares.
    """
    contributes = _manifest()["contributes"]

    assert contributes["metadata"]["project"]["pre-render"] == [
        "quarto run _extensions/quarto-needs/bootstrap.py"
    ]


def test_quickstart_points_at_the_zero_friction_starter_template() -> None:
    quickstart = QUICKSTART.read_text(encoding="utf-8")

    assert "quarto use template lsbjordao/quarto-needs/templates/starter" in quickstart


@pytest.mark.requirement("SYS-009")
@pytest.mark.quarto_need_test_case("TC-031")
def test_manifest_declares_the_quarto_floor() -> None:
    assert _manifest()["quarto-required"] == ">=1.6.0"


# --- The two-piece install, as documented today -----------------------------


def test_quickstart_leads_with_the_extension_not_a_pip_install() -> None:
    """Migrated in Task 10. This previously pinned the opposite.

    The quickstart used to open with `pip install quarto-needs` and frame
    Quarto-Needs as two installations. It now opens with `quarto add`, and
    the pip install moves to an explicitly optional CLI/editor-tooling
    section further down the page.
    """
    quickstart = QUICKSTART.read_text(encoding="utf-8")

    assert quickstart.index("quarto add lsbjordao/quarto-needs") < quickstart.index(
        "pip install quarto-needs"
    ), "the extension must be the first install step, not pip"
    assert "## Optional: the standalone CLI and editor tooling" in quickstart


def test_quickstart_authors_no_pre_render_hook() -> None:
    """Migrated in Task 10. This previously pinned the opposite: a hand-authored
    `pre-render: quarto-needs scan` line in the documented `_quarto.yml`.

    Activating the filter now installs the pre-render step itself, so the
    documented project file must not tell the reader to author one.
    """
    quickstart = QUICKSTART.read_text(encoding="utf-8")

    assert "pre-render: quarto-needs scan" not in quickstart
    assert "Activating the filter also installs the" in quickstart


def test_quickstart_documents_extension_activation() -> None:
    """Activation survives Phase 8B; only the engine wiring disappears.

    `installation != activation` stays true: `quarto add` installs, and
    `filters: [quarto-needs]` is what turns the extension on.
    """
    quickstart = QUICKSTART.read_text(encoding="utf-8")

    assert "quarto add lsbjordao/quarto-needs" in quickstart
    assert "filters:\n  - quarto-needs" in quickstart


# --- What the installed-path check depends on today -------------------------


def test_the_cli_path_check_still_covers_the_package_install() -> None:
    """The CLI-installed path stays supported, and stays tested.

    Extension-first distribution does not remove the Python distribution:
    engineering users still install it for `diff`, `impact` and `baseline`.
    This scenario is what catches a missing packaging entry or a broken
    console script.
    """
    script = CLI_PATH_CHECK.read_text(encoding="utf-8")

    assert 'pip install --quiet "$REPO"' in script
    assert "command -v quarto-needs" in script
    assert "pre-render: quarto-needs scan" in script


def test_the_cli_path_check_is_no_longer_the_primary_scenario() -> None:
    """Migrated in Task 7. This previously pinned the opposite.

    The two-piece install used to be the only installed-user scenario the
    repository tested, which made it the de facto contract.
    """
    script = CLI_PATH_CHECK.read_text(encoding="utf-8")

    assert "no longer the primary user-installation scenario" in script
    assert "check_extension_first_path.sh" in script


def test_the_primary_check_installs_no_engine_and_authors_no_pre_render() -> None:
    """The phase's acceptance contract, as an executable scenario.

    The absence of `pre-render: quarto-needs scan` from the consumer project
    is the whole point, so it is asserted directly rather than inferred.
    """
    script = EXTENSION_FIRST_CHECK.read_text(encoding="utf-8")

    assert "filters:\n  - quarto-needs" in script
    assert "pre-render: quarto-needs scan" not in script
    # It must prove the engine is absent rather than hope it is.
    assert "a quarto-needs executable is on PATH" in script
    assert "importable from the ambient interpreter" in script
    # And prove the cached runtime needs no index on the second render.
    assert "PIP_NO_INDEX=1" in script


# --- The render golden that must survive the migration ----------------------


def test_installed_consumer_check_asserts_the_observable_render_contract() -> None:
    """Pin the user-visible behaviours, independent of how the engine ran.

    Phase 8B changes *who invokes the engine*. None of these may change: the
    same graph, the same resolved shortcode, the same card, and no leaked
    failure text. Task 7 rewrites the scenario around them, not through them.
    """
    script = CLI_PATH_CHECK.read_text(encoding="utf-8")

    # The engine ran and wrote the canonical graph where consumers read it.
    assert ".quarto-needs/needs.json" in script
    # The graph says what the source declared.
    assert "{'REQ-1', 'TC-1'}" in script
    # The public schema marker is pinned, not merely present.
    assert "graph['schemaVersion'] == '1'" in script
    # The shortcode resolved against that graph.
    assert 'data-need-count="1"' in script
    # The filter turned the authored div into a card.
    assert "need-card" in script
    # Two silent-failure modes that render as text rather than failing.
    assert "'{{<'" in script or "'{{<' " in script
    assert "need-view-warning" in script
