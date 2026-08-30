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
    assert quality["permissions"] == {
        "actions": "read",
        "contents": "read",
        "security-events": "write",
    }
    steps = quality["steps"]
    upload_steps = [step for step in steps if "upload-artifact" in str(step.get("uses", ""))]
    assert upload_steps, "quality must upload artifacts"
    assert any(
        step.get("uses") == "github/codeql-action/upload-sarif@v4" for step in steps
    )


def test_quality_generates_every_export_format_and_summary() -> None:
    run_steps = [str(step.get("run", "")) for step in parsed()["jobs"]["quality"]["steps"]]
    joined = "\n".join(run_steps)
    for name in ("json", "csv", "sarif", "junit", "markdown"):
        assert f"--format {name}" in joined, name
    assert "$GITHUB_STEP_SUMMARY" in joined


def test_pull_requests_generate_git_native_change_intelligence() -> None:
    quality = parsed()["jobs"]["quality"]
    checkout = next(step for step in quality["steps"] if step.get("name") == "Check out repository")
    assert checkout["with"]["fetch-depth"] == 0

    change = next(
        step
        for step in quality["steps"]
        if step.get("name") == "Generate PR engineering change projections"
    )
    assert change["if"] == "github.event_name == 'pull_request'"
    assert change["env"] == {
        "BASE_SHA": "${{ github.event.pull_request.base.sha }}",
        "HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
    }
    run = change["run"]
    assert "pr-report --git \"$RANGE\"" in run
    assert "github-report --git \"$RANGE\"" in run
    assert "--recompute-with current" in run
    assert "--format markdown" in run
    assert "--format annotations" in run
    assert "artifacts/pr-report.json" in run
    assert "artifacts/pr-summary.md" in run
    assert "artifacts/pr-annotations.txt" in run
    assert 'cat artifacts/pr-summary.md >> "$GITHUB_STEP_SUMMARY"' in run
    assert "cat artifacts/pr-annotations.txt" in run


def test_quarto_is_pinned_to_a_stable_release() -> None:
    steps = parsed()["jobs"]["quarto"]["steps"]
    install = next(step for step in steps if step.get("name") == "Install project and test dependencies")
    setup = next(step for step in steps if "quarto-actions/setup" in str(step.get("uses", "")))
    assert install["run"] == "make setup"
    assert setup["uses"] == "quarto-dev/quarto-actions/setup@v2"
    assert setup["with"]["version"] == "1.10.18"
