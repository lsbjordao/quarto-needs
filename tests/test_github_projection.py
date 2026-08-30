from __future__ import annotations

from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.github_projection import build, render_workflow_commands
from quarto_needs.git_range_cli import git_action
from quarto_needs.pr_report import PullRequestReport


def _snapshot(tmp_path: Path):
    (tmp_path / ".quarto-needs.toml").write_text(
        '''[types.functional-requirement]
id-prefix = "FUN-"
role = "requirement"
allowed-statuses = ["approved"]

[types.test-case]
id-prefix = "TC-"
role = "verification"
allowed-statuses = ["passed"]
''',
        encoding="utf-8",
    )
    (tmp_path / "requirements.qmd").write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="approved"}
## Requirement
Requirement body.
:::

::: {.need #TC-001 type="test-case" status="passed"}
## Verification
Verification body.
:::
''',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    return result.snapshot


def _report() -> PullRequestReport:
    return PullRequestReport(
        changed={
            "requirements": ("FUN-001",),
            "decisions": (),
            "architectureElements": (),
            "sourceModules": (),
            "tests": (),
            "evidence": (),
            "other": (),
        },
        affected={
            "requirements": (),
            "decisions": (),
            "architectureElements": (),
            "sourceModules": (),
            "tests": ("TC-001",),
            "evidence": (),
            "other": (),
        },
        stale_evidence=(),
        findings_added=(
            {
                "code": "REQ:001",
                "object_id": "FUN-001",
                "message": "Needs 100%, review\nnow",
                "severity": "error",
            },
        ),
        findings_removed=(),
        gate_regressions=(),
        impact_paths=(
            {
                "origin": "FUN-001",
                "target": "TC-001",
                "classification": "direct",
                "distance": 1,
                "relations": ["verified-by"],
                "path": ["FUN-001", "TC-001"],
            },
        ),
        suspect_claims=(
            {
                "id": "TC-001",
                "origin": "FUN-001",
                "witness": "FUN-001 --verified-by--> TC-001",
            },
        ),
    )


def test_github_projection_adds_locations_deep_links_and_failure_conclusion(tmp_path: Path) -> None:
    projection = build(
        _report(),
        _snapshot(tmp_path),
        model_url="https://example.invalid/model",
    )

    assert projection.check["conclusion"] == "failure"
    assert projection.check["modelUrl"] == "https://example.invalid/model"
    assert projection.check["annotationCount"] == 2
    finding, suspect = projection.annotations
    assert finding["level"] == "error"
    assert finding["objectId"] == "FUN-001"
    assert finding["file"] == "requirements.qmd"
    assert finding["line"] == 1
    assert finding["url"] == "https://example.invalid/model#FUN-001"
    assert suspect["level"] == "warning"
    assert suspect["objectId"] == "TC-001"
    assert suspect["url"] == "https://example.invalid/model#TC-001"


def test_workflow_commands_escape_protocol_sensitive_characters(tmp_path: Path) -> None:
    commands = render_workflow_commands(build(_report(), _snapshot(tmp_path)))

    assert "title=Quarto-Needs REQ%3A001" in commands
    assert "Needs 100%25, review%0Anow" in commands
    assert "file=requirements.qmd" in commands
    assert "line=1" in commands
    assert "::warning " in commands


def test_neutral_conclusion_for_suspect_only(tmp_path: Path) -> None:
    report = _report()
    suspect_only = PullRequestReport(
        changed=report.changed,
        affected=report.affected,
        stale_evidence=(),
        findings_added=(),
        findings_removed=(),
        gate_regressions=(),
        impact_paths=report.impact_paths,
        suspect_claims=report.suspect_claims,
    )
    projection = build(suspect_only, _snapshot(tmp_path))
    assert projection.check["conclusion"] == "neutral"


def test_git_action_recognizes_github_report() -> None:
    assert git_action(["github-report", "--git", "main..HEAD", "--format", "json"]) == (
        "github-report",
        "main..HEAD",
    )
