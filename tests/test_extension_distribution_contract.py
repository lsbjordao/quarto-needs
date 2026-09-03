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

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "_extensions" / "quarto-needs" / "_extension.yml"
PYPROJECT = ROOT / "pyproject.toml"
QUICKSTART = ROOT / "docs" / "quickstart.md"
INSTALLED_PATH_CHECK = ROOT / "tools" / "check_installed_path.sh"


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


def test_manifest_declares_the_quarto_floor() -> None:
    assert _manifest()["quarto-required"] == ">=1.6.0"


# --- The two-piece install, as documented today -----------------------------


def test_quickstart_tells_the_user_to_pip_install_the_engine_today() -> None:
    quickstart = QUICKSTART.read_text(encoding="utf-8")

    assert "pip install quarto-needs" in quickstart
    assert re.search(r"ships as two pieces", quickstart), (
        "the quickstart currently frames Quarto-Needs as two installations"
    )


def test_quickstart_tells_the_user_to_author_the_pre_render_hook_today() -> None:
    quickstart = QUICKSTART.read_text(encoding="utf-8")

    assert "pre-render: quarto-needs scan" in quickstart
    assert "## 3. Wire the pre-render hook" in quickstart


def test_quickstart_documents_extension_activation() -> None:
    """Activation survives Phase 8B; only the engine wiring disappears.

    `installation != activation` stays true: `quarto add` installs, and
    `filters: [quarto-needs]` is what turns the extension on.
    """
    quickstart = QUICKSTART.read_text(encoding="utf-8")

    assert "quarto add lsbjordao/quarto-needs" in quickstart
    assert "filters:\n  - quarto-needs" in quickstart


# --- What the installed-path check depends on today -------------------------


def test_installed_path_check_requires_a_python_package_install_today() -> None:
    script = INSTALLED_PATH_CHECK.read_text(encoding="utf-8")

    assert "pip install --quiet \"$REPO\"" in script, (
        "the installed-user scenario currently begins by installing the package"
    )


def test_installed_path_check_requires_the_cli_on_path_today() -> None:
    script = INSTALLED_PATH_CHECK.read_text(encoding="utf-8")

    assert 'command -v quarto-needs' in script
    assert 'export PATH="$WORK/venv/bin:$PATH"' in script


def test_installed_path_fixture_authors_a_quarto_needs_pre_render_today() -> None:
    """The fixture project wires the engine by hand.

    Phase 8B's acceptance contract is this exact project *without* the
    `pre-render` line, so this assertion is the one Task 7 inverts.
    """
    script = INSTALLED_PATH_CHECK.read_text(encoding="utf-8")

    assert "pre-render: quarto-needs scan" in script
    assert "filters:\n  - quarto-needs" in script


# --- The render golden that must survive the migration ----------------------


def test_installed_consumer_check_asserts_the_observable_render_contract() -> None:
    """Pin the user-visible behaviours, independent of how the engine ran.

    Phase 8B changes *who invokes the engine*. None of these may change: the
    same graph, the same resolved shortcode, the same card, and no leaked
    failure text. Task 7 rewrites the scenario around them, not through them.
    """
    script = INSTALLED_PATH_CHECK.read_text(encoding="utf-8")

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
