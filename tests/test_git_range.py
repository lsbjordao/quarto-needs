from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from quarto_needs import diff as diff_module
from quarto_needs import impact as impact_module
from quarto_needs.git_range import GitRangeError, materialize_git_range, parse_git_range


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
    env = {
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_DATE": timestamp,
    }
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message, env=env)
    return _git(repo, "rev-parse", "HEAD")


def _project(repo: Path) -> Path:
    project = repo / "engineering"
    project.mkdir()
    (project / "requirements.qmd").write_text(
        '''# Requirements

::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Original behavior
The system shall preserve the original behavior.
:::

::: {.need #TC-001 type="test-case" status="passed"}
## Verification
Verify FUN-001.
:::
''',
        encoding="utf-8",
    )
    (project / "note.txt").write_text("archived helper\n", encoding="utf-8")
    try:
        (project / "note-link.txt").symlink_to("note.txt")
    except OSError:
        pass
    return project


def _repository(tmp_path: Path) -> tuple[Path, Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Quarto Needs Test")
    _git(repo, "config", "user.email", "quarto-needs@example.invalid")
    project = _project(repo)
    base = _commit(repo, "base", "2026-08-29T10:00:00+00:00")
    (project / "requirements.qmd").write_text(
        '''# Requirements

::: {.need #FUN-001 type="functional-requirement" status="approved" verified-by="TC-001"}
## Revised behavior
The system shall preserve the revised behavior.
:::

::: {.need #TC-001 type="test-case" status="passed"}
## Verification
Verify FUN-001.
:::
''',
        encoding="utf-8",
    )
    head = _commit(repo, "head", "2026-08-30T12:34:56+00:00")
    return repo, project, base, head


def test_parse_git_range_accepts_only_two_dot_form() -> None:
    assert parse_git_range("main..HEAD") == ("main", "HEAD")
    for invalid in ("main", "main...HEAD", "..HEAD", "main..", "a..b..c"):
        with pytest.raises(GitRangeError):
            parse_git_range(invalid)


def test_git_range_materializes_both_states_and_reuses_canonical_diff_impact(tmp_path: Path) -> None:
    _, project, base, head = _repository(tmp_path)
    states = materialize_git_range(project, f"{base}..{head}")

    assert states.base_sha == base
    assert states.head_sha == head
    assert states.base_snapshot.reference_date == "2026-08-30"
    assert states.head_snapshot.reference_date == "2026-08-30"
    assert states.base_snapshot.reference_date == states.head_snapshot.reference_date
    assert states.reference_epoch == 1788093296

    report = diff_module.compare(
        states.base_baseline,
        states.head_snapshot,
        states.head_config,
    )
    assert report.added_objects == ()
    assert report.removed_objects == ()
    assert [item["id"] for item in report.modified] == ["FUN-001"]
    assert set(report.modified[0]["fields"]) == {"title", "body"}

    impact = impact_module.analyze(
        states.base_baseline,
        states.head_snapshot,
        states.head_config,
    )
    assert [item["id"] for item in impact.origins] == ["FUN-001"]
    assert [(item["id"], item["path"], item["relations"]) for item in impact.impacted] == [
        ("TC-001", ["FUN-001", "TC-001"], ["verified-by"])
    ]


def test_git_range_ignores_wall_clock_source_date_epoch(tmp_path: Path, monkeypatch) -> None:
    _, project, base, head = _repository(tmp_path)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "0")
    first = materialize_git_range(project, f"{base}..{head}")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "4102444800")
    second = materialize_git_range(project, f"{base}..{head}")

    assert first.reference_epoch == second.reference_epoch
    assert first.base_snapshot.semantic_graph_fingerprint == second.base_snapshot.semantic_graph_fingerprint
    assert first.head_snapshot.semantic_graph_fingerprint == second.head_snapshot.semantic_graph_fingerprint
    assert os.environ["SOURCE_DATE_EPOCH"] == "4102444800"
