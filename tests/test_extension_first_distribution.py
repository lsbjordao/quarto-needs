"""The extension-first contract, rendered by real Quarto.

The phase's promise is that `quarto add` plus `filters: [quarto-needs]` is
the whole installation. These tests render actual consumer projects with no
`quarto-needs` on PATH, no package installed into the environment, and no
user-authored pre-render, and assert the engineering model still comes out.

Manifest-text assertions cannot establish this. Whether Quarto merges a
contributed `metadata.project.pre-render`, whether a relative `quarto run`
command resolves, and what happens to a project's own hooks are all facts
about Quarto, not about our YAML.

Spec: docs/superpowers/specs/2026-09-02-extension-first-distribution-design.md
Plan: docs/superpowers/plans/2026-09-02-extension-first-distribution.md (Task 6)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    shutil.which("quarto") is None, reason="Quarto is not installed"
)

CONSUMER_QMD = """---
title: "Extension-first consumer"
---

::: {.need #REQ-1 type=functional-requirement status=approved priority=high}
## Authenticate the user

The system shall authenticate the user.

### Rationale
Protect private data.
:::

::: {.need #TC-1 type=test-case status=passed}
## Login test

Signs a user in.
:::

Count: {{< need-count types="functional-requirement" >}}
"""

# Deliberately no `pre-render`: that is the whole point of the phase.
CONSUMER_QUARTO_YML = """project:
  type: default

filters:
  - quarto-needs
"""


def consumer_project(root: Path, quarto_yml: str = CONSUMER_QUARTO_YML) -> Path:
    """A project as `quarto add lsbjordao/quarto-needs` would leave it."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "_extensions").mkdir(exist_ok=True)
    shutil.copytree(
        ROOT / "_extensions" / "quarto-needs", root / "_extensions" / "quarto-needs"
    )
    (root / "_quarto.yml").write_text(quarto_yml, encoding="utf-8")
    (root / "index.qmd").write_text(CONSUMER_QMD, encoding="utf-8")
    return root


def render(project: Path, *, offline: bool = False) -> subprocess.CompletedProcess:
    """Render the way a user would: no repository tooling on PATH.

    PATH carries the system directories Quarto itself needs and nothing
    else, so a `quarto-needs` executable cannot be what makes this work.
    """
    environment = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": os.environ.get("HOME", str(project)),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    if not offline:
        # The engine is unpublished, so provision it from this checkout.
        environment["QUARTO_NEEDS_ENGINE_SOURCE"] = os.environ[
            "QUARTO_NEEDS_ENGINE_SOURCE"
        ]
    return subprocess.run(
        ["quarto", "render"],
        cwd=str(project),
        capture_output=True,
        text=True,
        env=environment,
        timeout=900,
    )


def assert_render_contract(project: Path) -> None:
    """The observable behaviours Task 1 pinned, unchanged by the new path."""
    graph_path = project / ".quarto-needs" / "needs.json"
    assert graph_path.is_file(), "the extension did not build the graph"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert {item["id"] for item in graph["objects"]} == {"REQ-1", "TC-1"}
    assert graph["schemaVersion"] == "1"

    html = (project / "index.html").read_text(encoding="utf-8")
    assert "need-card" in html, "the filter did not turn the div into a card"
    assert 'data-need-count="1"' in html, "the shortcode did not resolve"
    assert "{{<" not in html, "an unexpanded shortcode reached the output"
    assert "need-view-warning" not in html, "the extension warned about the graph"


@pytest.mark.slow
def test_a_clean_consumer_project_needs_no_engine_installation(tmp_path) -> None:
    """`quarto add` + activation + `quarto render`. Nothing else.

    This is the phase's definition of done.
    """
    project = consumer_project(tmp_path / "consumer")

    completed = render(project)

    assert completed.returncode == 0, completed.stderr
    assert_render_contract(project)

    # The engine came from a project-local managed runtime, not the system.
    markers = list((project / ".quarto-needs" / "runtime").rglob("installed.json"))
    assert markers, "no managed runtime was provisioned"
    marker = json.loads(markers[0].read_text(encoding="utf-8"))
    assert marker["schemaVersion"] == "quarto-needs-managed-runtime-v1"


@pytest.mark.slow
def test_a_second_render_succeeds_without_any_engine_source(tmp_path) -> None:
    """After one provisioning, rendering must not need an index again."""
    project = consumer_project(tmp_path / "consumer")
    assert render(project).returncode == 0

    (project / ".quarto-needs" / "needs.json").unlink()
    completed = render(project, offline=True)

    assert completed.returncode == 0, completed.stderr
    assert_render_contract(project)


@pytest.mark.slow
def test_the_project_path_may_contain_spaces(tmp_path) -> None:
    """A release gate: `quarto run` must survive a quoted project path."""
    project = consumer_project(tmp_path / "Quarto Needs Consumer Project")

    completed = render(project)

    assert completed.returncode == 0, completed.stderr
    assert_render_contract(project)


@pytest.mark.slow
def test_a_project_pre_render_hook_still_runs_and_runs_first(tmp_path) -> None:
    """Quarto-Needs must coexist with a project's own pre-render hooks.

    The observed order is the project's hooks first, then the extension's.
    That is the order the integration needs: a hook that generates or edits
    `.qmd` content must run before the engine reads the project, or its
    output would be missing from the graph.
    """
    project = consumer_project(
        tmp_path / "consumer",
        quarto_yml="""project:
  type: default
  pre-render:
    - user-hook.py

filters:
  - quarto-needs
""",
    )
    (project / "user-hook.py").write_text(
        "from pathlib import Path\n"
        "Path('ORDER.txt').write_text('user\\n')\n",
        encoding="utf-8",
    )

    completed = render(project)

    assert completed.returncode == 0, completed.stderr
    assert (project / "ORDER.txt").read_text(encoding="utf-8") == "user\n", (
        "the project's own pre-render hook did not run"
    )
    assert_render_contract(project)


@pytest.mark.slow
def test_the_manifest_command_is_relative_to_the_project(tmp_path) -> None:
    """Quarto's absolute extension-path resolution is not dependable.

    Asserted on the shipped manifest rather than a copy, because this is a
    property of what we publish.
    """
    manifest = (ROOT / "_extensions" / "quarto-needs" / "_extension.yml").read_text(
        encoding="utf-8"
    )

    assert "quarto run _extensions/quarto-needs/bootstrap.py" in manifest
    assert str(ROOT) not in manifest, "an absolute path leaked into the manifest"


# --- Minimum supported Quarto ----------------------------------------------

MINIMUM_QUARTO_ENV = "QUARTO_NEEDS_MIN_QUARTO_BIN"


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get(MINIMUM_QUARTO_ENV),
    reason=f"set {MINIMUM_QUARTO_ENV} to a Quarto 1.6.0 binary to run the floor gate",
)
def test_the_declared_quarto_floor_actually_renders(tmp_path) -> None:
    """`quarto-required: ">=1.6.0"` is a claim, so prove it on 1.6.0 itself.

    Metadata extensions predate the floor, but "predates" is not "works":
    whether Quarto 1.6.0 merges a contributed `project.pre-render` and
    resolves a relative `quarto run` is a fact about that release. Keeping
    the floor requires this to pass; if it ever stops passing, the floor
    moves, deliberately and with documentation, rather than the test being
    weakened.

    The project path contains spaces here too, so the release gate is
    covered on the minimum version and not only the current one.
    """
    binary = Path(os.environ[MINIMUM_QUARTO_ENV]).resolve()
    assert binary.is_file(), binary

    project = consumer_project(tmp_path / "Minimum Quarto Consumer")
    completed = subprocess.run(
        [str(binary), "render"],
        cwd=str(project),
        capture_output=True,
        text=True,
        env={
            "PATH": f"{binary.parent}:/usr/local/bin:/usr/bin:/bin",
            "HOME": os.environ.get("HOME", str(project)),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "QUARTO_NEEDS_ENGINE_SOURCE": os.environ["QUARTO_NEEDS_ENGINE_SOURCE"],
        },
        timeout=900,
    )

    assert completed.returncode == 0, completed.stderr
    assert_render_contract(project)
