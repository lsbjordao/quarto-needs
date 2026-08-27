from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def parsed() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_has_the_three_specified_jobs() -> None:
    jobs = parsed()["jobs"]
    assert {"core", "quarto", "quality"} <= set(jobs)


def test_core_runs_the_python_matrix() -> None:
    matrix = parsed()["jobs"]["core"]["strategy"]["matrix"]["python-version"]
    assert ["3.10", "3.11", "3.12", "3.13", "3.14"] == matrix


def test_artifacts_upload_always_and_sarif_is_least_privilege() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if: always()" in text
    assert "pull_request_target" not in text
    quality = parsed()["jobs"]["quality"]
    assert quality["permissions"] == {"contents": "read", "security-events": "write"}
    steps = quality["steps"]
    upload_steps = [step for step in steps if "upload-artifact" in str(step.get("uses", ""))]
    assert upload_steps, "quality must upload artifacts"
    assert any("github/codeql-action/upload-sarif" in str(step.get("uses", "")) for step in steps)


def test_quality_generates_every_export_format_and_summary() -> None:
    run_steps = [str(step.get("run", "")) for step in parsed()["jobs"]["quality"]["steps"]]
    joined = "\n".join(run_steps)
    for name in ("json", "csv", "sarif", "junit", "markdown"):
        assert f"--format {name}" in joined, name
    assert "$GITHUB_STEP_SUMMARY" in joined


def test_quarto_is_pinned_to_a_stable_release() -> None:
    steps = parsed()["jobs"]["quarto"]["steps"]
    install = next(step for step in steps if step.get("name") == "Install project and test dependencies")
    setup = next(step for step in steps if "quarto-actions/setup" in str(step.get("uses", "")))
    assert install["run"] == "make setup"
    assert setup["uses"] == "quarto-dev/quarto-actions/setup@v2"
    assert setup["with"]["version"] == "1.10.18"
