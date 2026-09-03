"""The deliberately broken teaching fixtures, asserted against the engine.

Phase 9's gallery under `examples/broken/` exists so that a developer can
read a failing project, not just a description of one. These tests are the
other half of that contract: each fixture's story ends with a specific,
engine-emitted finding, and if the engine ever stops reporting it -- or
reports something else -- the gallery is lying and this module fails.

Nothing here mutates the canonical self-hosted example; every fixture is
its own project root.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.localization import validate_localized_pair
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
