from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs import baseline, impact
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

CHAIN = """::: {{.need #STK-1 type=stakeholder-need status=approved priority=high}}

## Stakeholder
Needs secure access.
:::

::: {{.need #REQ-1 type=functional-requirement status=approved priority=high}}
derives-from: STK-1
verified-by: TC-1
conflicts-with: DOC-1

## Authenticate
{body}

### Rationale
Protect data.
:::

::: {{.need #DOC-1 type=need status=draft}}

## Manual
Login manual.
:::

::: {{.need #TC-1 type=test-case status=passed}}

## Login
Signs in.
:::
"""


def write(root: Path, *, body: str = "The service shall authenticate.", keep_test: bool = True) -> None:
    text = CHAIN.format(body=body)
    if not keep_test:
        text = text.split("::: {.need #TC-1", 1)[0].replace("verified-by: TC-1\n", "")
    (root / "chain.qmd").write_text(text, encoding="utf-8")


def snapshot_of(root: Path):
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return result.snapshot, config


def baseline_of(root: Path) -> dict[str, object]:
    snapshot, config = snapshot_of(root)
    return baseline.build_baseline(snapshot, config)


def test_no_change_produces_no_impact(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    assert report.origins == ()
    assert report.impacted == ()


def test_editing_a_requirement_impacts_its_verification(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, body="The service shall authenticate every administrator.")
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    assert [item["id"] for item in report.origins] == ["REQ-1"]
    impacted = {item["id"]: item for item in report.impacted}
    assert "TC-1" in impacted
    assert impacted["TC-1"]["classification"] == "direct"
    assert impacted["TC-1"]["distance"] == 1
    assert impacted["TC-1"]["path"] == ["REQ-1", "TC-1"]
    assert impacted["TC-1"]["relations"] == ["verified-by"]


def test_every_impacted_result_carries_an_explicit_path(tmp_path: Path) -> None:
    """The gate forbids an opaque score; a path is the audit trail."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, body="Changed.")
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    assert report.impacted
    for item in report.impacted:
        assert item["path"][0] == item["origin"]
        assert item["path"][-1] == item["id"]
        assert len(item["path"]) == item["distance"] + 1
        assert item["classification"] in {"direct", "transitive"}
        assert "priority" in item


def test_removing_a_node_still_explains_its_neighbors(tmp_path: Path) -> None:
    """Union traversal is why a removed node and its removed edges stay explainable.

    `verified-by` propagates from requirement to test, so the removed test case
    cannot reach the requirement it verified; the removal surfaces instead as
    two origins — the removed node and the requirement that lost the edge.
    """
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, keep_test=False)
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    changes = {item["id"]: item["change"] for item in report.origins}
    assert changes.get("TC-1") == "removed"
    assert changes.get("REQ-1") == "relation-removed"


def test_removal_reaches_neighbors_through_baseline_only_edges(tmp_path: Path) -> None:
    """A dropped `conflicts-with` still propagates: the edge exists only in the
    baseline, so without the union adjacency DOC-1 would be unreachable."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    text = (tmp_path / "chain.qmd").read_text(encoding="utf-8").replace("conflicts-with: DOC-1\n", "")
    (tmp_path / "chain.qmd").write_text(text, encoding="utf-8")
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    changes = {item["id"]: item["change"] for item in report.origins}
    assert changes.get("REQ-1") == "relation-removed"
    doc = next(item for item in report.impacted if item["id"] == "DOC-1")
    assert doc["classification"] == "direct"
    assert doc["relations"] == ["conflicts-with"]


def test_impact_rejects_a_configuration_mismatch_without_recompute(tmp_path: Path) -> None:
    """One relation policy must govern the whole traversal."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
    )
    snapshot, config = snapshot_of(tmp_path)

    with pytest.raises(impact.ImpactError):
        impact.analyze(before, snapshot, config)

    assert impact.analyze(before, snapshot, config, recompute=True) is not None


def test_impact_rejects_a_diagnostic_baseline(tmp_path: Path) -> None:
    write(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    with pytest.raises(impact.ImpactError):
        impact.analyze({"schemaVersion": "1", "valid": False}, snapshot, config)
