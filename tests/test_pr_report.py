from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from quarto_needs.cli_entry import main
from quarto_needs.git_range import materialize_git_range
from quarto_needs.pr_report import analyze, render_markdown


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=merged,
    )
    return completed.stdout.strip()


def _commit(repo: Path, message: str, timestamp: str) -> str:
    env = {"GIT_AUTHOR_DATE": timestamp, "GIT_COMMITTER_DATE": timestamp}
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message, env=env)
    return _git(repo, "rev-parse", "HEAD")


def _repository(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    project = repo / "engineering"
    project.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Quarto Needs Test")
    _git(repo, "config", "user.email", "quarto-needs@example.invalid")
    (project / ".quarto-needs.toml").write_text(
        '''profile = "default"

[types.functional-requirement]
id-prefix = "FUN-"
role = "requirement"
allowed-statuses = ["approved"]

[types.test-case]
id-prefix = "TC-"
role = "verification"
allowed-statuses = ["passed"]

[relations."verified-by"]
allowed-source-types = ["functional-requirement"]
allowed-target-types = ["test-case"]
''',
        encoding="utf-8",
    )
    source = project / "requirements.qmd"
    source.write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Original behavior
Original body.
:::

::: {.need #TC-001 type="test-case" status="passed"}
## Verification
Verify FUN-001.
:::
''',
        encoding="utf-8",
    )
    base = _commit(repo, "base", "2026-08-29T10:00:00+00:00")
    source.write_text(
        '''::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Revised behavior
Revised body.
:::

::: {.need #TC-001 type="test-case" status="passed"}
## Verification
Verify FUN-001.
:::
''',
        encoding="utf-8",
    )
    head = _commit(repo, "head", "2026-08-30T12:34:56+00:00")
    return project, base, head


def test_pr_report_classifies_changed_and_affected_objects(tmp_path: Path) -> None:
    project, base, head = _repository(tmp_path)
    states = materialize_git_range(project, f"{base}..{head}")
    report = analyze(states.base_baseline, states.head_snapshot, states.head_config)

    assert report.changed["requirements"] == ("FUN-001",)
    assert report.changed["tests"] == ()
    assert report.affected["tests"] == ("TC-001",)
    assert report.stale_evidence == ()
    assert report.impact_paths == (
        {
            "origin": "FUN-001",
            "target": "TC-001",
            "classification": "direct",
            "distance": 1,
            "relations": ["verified-by"],
            "path": ["FUN-001", "TC-001"],
        },
    )
    assert report.suspect_claims[0]["witness"] == "FUN-001 --verified-by--> TC-001"


def test_pr_report_markdown_is_step_summary_friendly(tmp_path: Path) -> None:
    project, base, head = _repository(tmp_path)
    states = materialize_git_range(project, f"{base}..{head}")
    text = render_markdown(
        analyze(states.base_baseline, states.head_snapshot, states.head_config)
    )

    assert text.startswith("# Quarto-Needs engineering change report\n")
    assert "**requirements**: FUN-001" in text
    assert "**tests**: TC-001" in text
    assert "Suspect traceability claims: 1" in text
    assert "FUN-001 → TC-001" in text
    assert "[verified-by]" in text


def test_pr_report_git_cli_emits_structured_json(tmp_path: Path, capsys) -> None:
    project, base, head = _repository(tmp_path)
    exit_code = main([
        "--root",
        str(project),
        "pr-report",
        "--git",
        f"{base}..{head}",
        "--format",
        "json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["git"]["baseSha"] == base
    assert payload["git"]["headSha"] == head
    assert payload["changed"]["requirements"] == ["FUN-001"]
    assert payload["affected"]["tests"] == ["TC-001"]
    assert payload["impactPaths"][0]["path"] == ["FUN-001", "TC-001"]


def test_pr_report_git_cli_emits_markdown_without_git_header(tmp_path: Path, capsys) -> None:
    project, base, head = _repository(tmp_path)
    exit_code = main([
        "--root",
        str(project),
        "pr-report",
        "--git",
        f"{base}..{head}",
        "--format",
        "markdown",
    ])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert output.startswith("# Quarto-Needs engineering change report")
    assert "Git range " not in output
