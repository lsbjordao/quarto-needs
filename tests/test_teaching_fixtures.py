"""The deliberately broken teaching fixtures, asserted against the engine.

Phase 9's gallery under `examples/broken/` exists so that a developer can
read a failing project, not just a description of one. These tests are the
other half of that contract: each fixture's story ends with a specific,
engine-emitted finding, and if the engine ever stops reporting it -- or
reports something else -- the gallery is lying and this module fails.

Nothing here mutates the canonical self-hosted example; every fixture is
its own project root.

`suspect-after-change` is the one gallery member with no static directory:
its whole point is two states of a project across a Git history, so it is
built dynamically -- a throwaway repo in `tmp_path`, two commits -- rather
than forced into a single checked-in snapshot.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.cli_entry import main as cli_main
from quarto_needs.config import load_config
from quarto_needs.exporters import jsonld_export, reqif_export
from quarto_needs.localization import validate_localized_pair
from quarto_needs.lsp_server import LspSession
from quarto_needs.migrations.sphinx_needs import (
    build_migration_plan,
    load_needs_json,
)


ROOT = Path(__file__).resolve().parents[1]
BROKEN = ROOT / "examples" / "broken"


def _analyze(name: str):
    root = BROKEN / name
    return analyze_project(root, config=load_config(root))


def test_missing_evidence_flags_the_passed_test_without_evidence() -> None:
    result = _analyze("missing-evidence")
    assert result.snapshot is not None
    assert ("REQ012", "TC-001") in {
        (finding.code, finding.object_id) for finding in result.findings
    }


def test_invalid_relations_block_the_snapshot_with_exact_causes() -> None:
    """Both invalid structures are reported, and nothing downstream is produced."""
    result = _analyze("invalid-relations")

    assert result.snapshot is None, "error findings must block the snapshot"
    findings = result.findings
    assert ("REQ004", "REQ-D") in {
        (finding.code, finding.object_id) for finding in findings
    }, "the duplicated identifier must be named with its object"
    assert ("REQ005", "REQ-B") in {
        (finding.code, finding.object_id) for finding in findings
    }, "the ghost target must be named with its object"


def test_a_relation_typo_becomes_an_inert_attribute_not_an_edge() -> None:
    """Only catalog names parse as relations; a typo neither fails nor links.

    The gallery teaches this trap explicitly: the project scans clean, the
    author's intended edge does not exist, and the mistyped name survives
    only as an attribute. That silence is exactly why `check` belongs in CI.
    """
    result = _analyze("relation-typo")

    assert result.snapshot is not None
    assert result.findings == (), "a typo must not invent findings either"
    records = {item.id: item for item in result.snapshot.objects}
    assert not result.snapshot.outgoing.get("REQ-A", ()), (
        "the mistyped relation must not link"
    )
    assert records["REQ-A"].attributes.get("linked-to") == "REQ-B", (
        "the typo must stay visible as an attribute"
    )


def test_orphan_requirements_stay_visible_as_info() -> None:
    """A well-formed but disconnected project still scans; gaps become info."""
    result = _analyze("orphan-requirements")

    assert result.snapshot is not None
    orphans = [finding for finding in result.findings if finding.code == "REQ014"]
    assert {finding.object_id for finding in orphans} == {"REQ-010", "REQ-011"}
    assert all(finding.severity == "info" for finding in orphans)


def test_overdue_decision_is_flagged_for_review() -> None:
    result = _analyze("overdue-decision")

    assert result.snapshot is not None
    assert ("DEC006", "ADR-001") in {
        (finding.code, finding.object_id) for finding in result.findings
    }


def test_expired_evidence_is_flagged_before_publication() -> None:
    result = _analyze("expired-evidence")

    assert result.snapshot is not None
    assert ("REQ015", "EVD-001") in {
        (finding.code, finding.object_id) for finding in result.findings
    }


def test_stale_evidence_is_refused_by_the_semantic_graph_fingerprint(capsys) -> None:
    """Intact, unexpired, provider-matching evidence is still refused when the
    model changed after it was attested: the payload is not the problem, the
    fingerprint binding is.
    """
    root = BROKEN / "stale-evidence"

    exit_code = cli_main(
        [
            "--root",
            str(root),
            "evidence",
            "check",
            "evidence/attested.json",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["valid"] is False
    assert payload["attested"] is True
    assert payload["checks"] == 1
    assert [issue["code"] for issue in payload["issues"]] == ["EVD203"]


def test_localization_drift_is_refused_naming_the_object() -> None:
    root = BROKEN / "localization-drift"

    with pytest.raises(RuntimeError, match="REQ-001"):
        validate_localized_pair(
            root / "index.qmd",
            root / "index.pt-BR.qmd",
            root,
        )


def test_migration_loss_is_planned_as_review_not_guessed() -> None:
    """An unmapped type and an unmapped link field must surface, not vanish."""
    document = load_needs_json(BROKEN / "migration-loss" / "needs.json")

    plan = build_migration_plan(
        document,
        type_map={"req": "functional-requirement"},
        relation_map={"links": "derived-from"},
    )

    issues = {(issue.code, issue.need_id) for issue in plan.issues}
    assert ("TYPE_UNMAPPED", "MIS_001") in issues, (
        "the exotic type must be an explicit review item"
    )
    assert ("LINK_FIELD_UNMAPPED", "REQ_001") in issues, (
        "the unmapped 'violates' link must be an explicit review item"
    )
    # The unmapped link is preserved as data, never silently dropped.
    candidate = {item.source_id: item for item in plan.candidates}["REQ_001"]
    assert candidate.unmapped_links.get("violates") == ("MIS_001",)


def test_interchange_loss_projections_document_exactly_what_stays_behind() -> None:
    """Both projections report the same loss instead of pretending to round-trip."""
    result = _analyze("interchange-loss")
    assert result.snapshot is not None
    assert not any(finding.severity == "error" for finding in result.findings)

    root = ET.fromstring(reqif_export.render(result.snapshot))
    notes = {
        node.text
        for node in root.findall(
            f".//{{{reqif_export.REQIF_NS}}}PROJECTION-NOTE"
        )
    }
    assert notes, "the ReqIF projection must document the details it drops"
    assert any(
        "object source locations stay behind" in note
        and "REQ-A (index.qmd:1)" in note
        for note in notes
    ), notes
    assert any(
        "relation source locations stay behind" in note
        and "REQ-A --verified-by--> TC-B" in note
        for note in notes
    ), notes

    document = jsonld_export.build_document(result.snapshot)
    projection_notes = document.get("quartoNeedsProjectionNotes")
    assert projection_notes, "the JSON-LD projection must document the same loss"
    assert any(
        "object source locations stay behind" in note
        and "REQ-A (index.qmd:1)" in note
        for note in projection_notes
    ), projection_notes
    assert any(
        "relation source locations stay behind" in note
        and "REQ-A --verified-by--> TC-B" in note
        for note in projection_notes
    ), projection_notes

    req_a = next(
        node
        for node in document["@graph"]
        if node.get("canonicalId") == "REQ-A"
    )
    assert req_a["attributes"]["priority"] == "high", (
        "attribute text itself must survive; only the documented loss is loss"
    )


def test_editor_refactor_rename_collision_is_refused_with_the_canonical_message() -> None:
    """The in-memory buffer surfaces the same diagnostic as the engine.

    Renaming REQ-2 onto the existing REQ-1 must be refused before anything
    touches disk; the safe refactor onto a free identifier still returns a
    complete, relation-aware edit.
    """
    root = BROKEN / "editor-refactor"
    session = LspSession.load(root)
    requirements = root / "requirements.qmd"
    lines = requirements.read_text(encoding="utf-8").splitlines()
    req2_line = next(index for index, line in enumerate(lines) if "REQ-2" in line)
    position = {
        "textDocument": {"uri": requirements.resolve().as_uri()},
        "position": {"line": req2_line, "character": lines[req2_line].index("REQ-2") + 2},
    }

    prepared = session.handle("textDocument/prepareRename", position)
    assert prepared["placeholder"] == "REQ-2"

    with pytest.raises(ValueError, match="existing object ID REQ-1"):
        session.handle(
            "textDocument/rename",
            {**position, "newName": "REQ-1"},
        )

    edit = session.handle(
        "textDocument/rename",
        {**position, "newName": "REQ-NEW"},
    )
    changes = edit["changes"]
    assert requirements.resolve().as_uri() in changes
    assert all(
        item["newText"] == "REQ-NEW"
        for items in changes.values()
        for item in items
    ), "a refactor onto a free identifier rewrites every reference"


# --- suspect-after-change: the one dynamic fixture in the gallery -----------


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


def _requirements_qmd(behavior: str) -> str:
    return f'''# Requirements

::: {{.need #REQ-1 type="functional-requirement" status="approved" verified-by="TC-1"}}
## Authenticate the user

{behavior}
:::

::: {{.need #TC-1 type="test-case" status="passed"}}
## Login test

Verifies REQ-1.
:::
'''


def build_suspect_after_change_repository(repo: Path) -> tuple[Path, str, str]:
    """A two-commit history: the second commit edits a verified requirement.

    REQ-1 (approved, verified-by TC-1) changes its meaning between commits --
    not a typo, an actual behavioral edit -- while TC-1 itself never moves.
    That is exactly what `suspect` exists to catch: a verification relation
    that still points at the requirement, but at a version of it nobody has
    re-checked.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Quarto Needs Teaching Fixture")
    _git(repo, "config", "user.email", "quarto-needs@example.invalid")
    (repo / "index.qmd").write_text(
        _requirements_qmd(
            "The system shall authenticate the user with a password."
        ),
        encoding="utf-8",
    )
    base = _commit(repo, "REQ-1: password authentication", "2026-09-01T10:00:00+00:00")
    (repo / "index.qmd").write_text(
        _requirements_qmd(
            "The system shall authenticate the user with a password and a "
            "second factor."
        ),
        encoding="utf-8",
    )
    head = _commit(repo, "REQ-1: require a second factor", "2026-09-03T10:00:00+00:00")
    return repo, base, head


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_suspect_after_change_names_the_now_stale_verification(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Editing a verified requirement must mark its verification suspect.

    TC-1 never changed. What changed is what it is supposed to be verifying,
    which is precisely the gap `suspect` reports: TC-1 still says "passed"
    for a version of REQ-1 that no longer exists.
    """
    repo, base, head = build_suspect_after_change_repository(tmp_path / "repo")

    status = cli_main(
        ["--root", str(repo), "suspect", "--git", f"{base}..{head}"]
    )

    assert status == 0
    output = capsys.readouterr().out
    assert "suspect TC-1" in output, output
    assert "from REQ-1" in output, output
    assert "REQ-1 --verified-by--> TC-1" in output, output
