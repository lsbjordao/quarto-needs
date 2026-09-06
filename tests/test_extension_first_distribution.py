"""The extension-first contract, rendered by real Quarto.

The phase's promise is that `quarto add` plus `filters: [quarto-needs]` is
the whole installation. These tests render actual consumer projects with no
`quarto-needs` on PATH, no package installed into the environment, and no
user-authored pre-render, and assert the engineering model still comes out.

Manifest-text assertions cannot establish this. Whether Quarto merges a
contributed `metadata.project.pre-render`, whether a relative `quarto run`
command resolves, and what happens to a project's own hooks are all facts
about Quarto, not about our YAML.

Contract: Phase 8B extension-first distribution (consumer-projects slice).
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
    target = root / "_extensions" / "lsbjordao" / "quarto-needs"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "_extensions" / "quarto-needs", target)
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
    graph_path = project / ".quarto-needs" / "needs.json"
    assert graph_path.is_file(), "the extension did not build the graph"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert {"REQ-1", "TC-1"} <= {item["id"] for item in graph["objects"]}
    assert graph["schemaVersion"] == "1"

    generated_index = (
        project
        / "_extensions"
        / "lsbjordao"
        / "quarto-needs"
        / "generated-index.lua"
    )
    assert generated_index.is_file(), "the graph index was not written beside the active extension"
    assert "REQ-1" in generated_index.read_text(encoding="utf-8")

    html = (project / "index.html").read_text(encoding="utf-8")
    assert "need-card" in html, "the filter did not turn the div into a card"
    assert 'data-need-count="1"' in html, "the shortcode did not resolve"
    assert "{{<" not in html, "an unexpanded shortcode reached the output"
    assert "need-view-warning" not in html, "the extension warned about the graph"


@pytest.mark.slow
@pytest.mark.requirement("SYS-009", "FUN-018", "FUN-019")
@pytest.mark.quarto_need_test_case("TC-025")
def test_a_clean_consumer_project_needs_no_engine_installation(tmp_path) -> None:
    project = consumer_project(tmp_path / "consumer")
    completed = render(project)
    assert completed.returncode == 0, completed.stderr
    assert_render_contract(project)

    markers = list((project / ".quarto-needs" / "runtime").rglob("installed.json"))
    assert markers, "no managed runtime was provisioned"
    marker = json.loads(markers[0].read_text(encoding="utf-8"))
    assert marker["schemaVersion"] == "quarto-needs-managed-runtime-v1"


@pytest.mark.slow
@pytest.mark.requirement("SYS-009", "NFR-009")
@pytest.mark.quarto_need_test_case("TC-026")
def test_a_second_render_succeeds_without_any_engine_source(tmp_path) -> None:
    project = consumer_project(tmp_path / "consumer")
    assert render(project).returncode == 0
    (project / ".quarto-needs" / "needs.json").unlink()
    completed = render(project, offline=True)
    assert completed.returncode == 0, completed.stderr
    assert_render_contract(project)


@pytest.mark.slow
@pytest.mark.requirement("FUN-018")
@pytest.mark.quarto_need_test_case("TC-030")
def test_the_project_path_may_contain_spaces(tmp_path) -> None:
    project = consumer_project(tmp_path / "Quarto Needs Consumer Project")
    completed = render(project)
    assert completed.returncode == 0, completed.stderr
    assert_render_contract(project)


@pytest.mark.slow
def test_a_project_pre_render_hook_still_runs_and_runs_first(tmp_path) -> None:
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
        "source = Path('index.qmd')\n"
        "source.write_text(source.read_text(encoding='utf-8') + '''\\n"
        "::: {.need #USER-HOOK-REQ type=risk status=approved}\\n"
        "## Authored by the user's hook\\n\\n"
        "The hook generated this requirement before the engine scanned the project.\\n"
        ":::\\n''', encoding='utf-8')\n",
        encoding="utf-8",
    )

    completed = render(project)
    assert completed.returncode == 0, completed.stderr
    graph = json.loads(
        (project / ".quarto-needs" / "needs.json").read_text(encoding="utf-8")
    )
    ids = {item["id"] for item in graph["objects"]}
    assert "USER-HOOK-REQ" in ids
    assert {"REQ-1", "TC-1"} <= ids
    assert_render_contract(project)


@pytest.mark.slow
def test_the_obsolete_two_piece_pre_render_line_fails_without_the_cli(tmp_path) -> None:
    project = consumer_project(
        tmp_path / "consumer",
        quarto_yml="""project:
  type: default
  pre-render:
    - quarto-needs scan

filters:
  - quarto-needs
""",
    )
    completed = render(project)
    assert completed.returncode != 0


@pytest.mark.slow
def test_the_manifest_command_matches_the_github_install_layout(tmp_path) -> None:
    manifest = (ROOT / "_extensions" / "quarto-needs" / "_extension.yml").read_text(
        encoding="utf-8"
    )
    assert (
        "quarto run _extensions/lsbjordao/quarto-needs/bootstrap-entry.py" in manifest
    )
    assert str(ROOT) not in manifest


MINIMUM_QUARTO_ENV = "QUARTO_NEEDS_MIN_QUARTO_BIN"


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get(MINIMUM_QUARTO_ENV),
    reason=f"set {MINIMUM_QUARTO_ENV} to a Quarto 1.6.0 binary to run the floor gate",
)
def test_the_declared_quarto_floor_actually_renders(tmp_path) -> None:
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


STARTER_TEMPLATE = ROOT / "templates" / "starter"


@pytest.mark.slow
def test_the_starter_template_needs_no_manual_activation_edit(tmp_path) -> None:
    """The starter stays unscoped until Quarto fixes scoped template copies."""
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    completed = subprocess.run(
        ["quarto", "use", "template", str(STARTER_TEMPLATE), "--no-prompt"],
        cwd=str(consumer),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr

    assert not (consumer / "_extension.yml").is_file()
    assert (
        consumer / "_extensions" / "quarto-needs" / "_extension.yml"
    ).is_file()

    rendered = render(consumer)
    assert rendered.returncode == 0, rendered.stderr

    graph = json.loads(
        (consumer / ".quarto-needs" / "needs.json").read_text(encoding="utf-8")
    )
    assert {item["id"] for item in graph["objects"]} == {"REQ-1", "TC-1"}
    html = (consumer / "index.html").read_text(encoding="utf-8")
    assert "need-card" in html
    assert "{{<" not in html
