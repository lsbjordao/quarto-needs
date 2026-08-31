from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs import baseline, diff
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

REQUIREMENT = (
    "::: {{.need #REQ-1 type=system-requirement status=approved priority=high}}\n"
    "verified-by: TC-1\n"
    "\n## Authenticate\n{body}\n"
    "\n### Rationale\nProtect data.\n"
    ":::\n"
)
TEST_CASE = "::: {.need #TC-1 type=test-case status=passed}\n\n## Login\nSigns in.\n:::\n"


def write(root: Path, *, body: str = "The service shall authenticate.", order: str = "requirement-first", file: str = "needs.qmd") -> None:
    for existing in root.glob("*.qmd"):
        existing.unlink()
    blocks = [REQUIREMENT.format(body=body), TEST_CASE]
    if order != "requirement-first":
        blocks.reverse()
    (root / file).write_text("\n".join(blocks), encoding="utf-8")


def snapshot_of(root: Path):
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return result.snapshot, config


def baseline_of(root: Path) -> dict[str, object]:
    snapshot, config = snapshot_of(root)
    return baseline.build_baseline(snapshot, config)


def test_identical_input_produces_an_empty_diff(tmp_path: Path) -> None:
    """The round-trip guarantee the milestone gate names."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert report.is_empty()
    assert report.notices == ()


def test_reordering_declarations_is_not_a_change(tmp_path: Path) -> None:
    """Swapping two blocks in a file changes nothing semantic."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, order="test-first")
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert report.modified == ()
    assert report.relocated == ()
    assert report.is_empty()


def test_moving_a_need_to_another_file_is_relocation_only(tmp_path: Path) -> None:
    """File change is a relocation record; content is untouched."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, file="moved.qmd")
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert report.modified == ()
    assert {item["id"] for item in report.relocated} == {"REQ-1", "TC-1"}
    moved = next(item for item in report.relocated if item["id"] == "REQ-1")
    assert moved["from"]["file"] == "needs.qmd"
    assert moved["to"]["file"] == "moved.qmd"
    assert "line" in moved["from"] and "line" in moved["to"]


def test_editing_a_body_is_a_modification_named_by_field(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, body="The service shall authenticate every administrator.")
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert [item["id"] for item in report.modified] == ["REQ-1"]
    assert report.modified[0]["fields"] == ["body"]
    assert report.relocated == ()


def test_added_and_removed_objects_are_classified(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / "extra.qmd").write_text(
        "::: {.need #REQ-2 type=functional-requirement status=draft}\n\n## Second\nBody.\n:::\n",
        encoding="utf-8",
    )
    (tmp_path / "needs.qmd").write_text(
        REQUIREMENT.format(body="The service shall authenticate.").replace("verified-by: TC-1\n", ""),
        encoding="utf-8",
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert report.added_objects == ("REQ-2",)
    assert report.removed_objects == ("TC-1",)


def test_a_changed_id_is_removal_plus_addition(tmp_path: Path) -> None:
    """Rename detection is deliberately excluded; it is inherently heuristic."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / "needs.qmd").write_text(
        REQUIREMENT.format(body="The service shall authenticate.").replace("#REQ-1", "#REQ-9")
        + "\n" + TEST_CASE,
        encoding="utf-8",
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert "REQ-9" in report.added_objects
    assert "REQ-1" in report.removed_objects
    assert report.modified == ()


def test_configuration_change_suppresses_derived_deltas(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert "configuration-changed" in report.notices
    assert report.findings_added == ()
    assert report.gate_regressions == ()


def test_reference_date_change_suppresses_date_derived_deltas(tmp_path: Path) -> None:
    """Evidence coverage and REQ015 depend on the date, not on authored content."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    before = {**before, "referenceDate": "1999-01-01"}
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert "reference-date-changed" in report.notices
    assert report.metric_deltas == ()
    assert report.findings_added == ()


def test_recompute_keeps_suppressed_categories_visible(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    before = {**before, "referenceDate": "1999-01-01"}
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config, recompute=True)

    assert report.notices == ("reference-date-changed",)
    assert report.suppressed == ("findings", "metrics", "gates")
    assert report.is_empty()
    assert report.recomputed is True


def test_recompute_does_not_manufacture_derived_deltas_from_a_config_change(tmp_path: Path) -> None:
    """The baseline stores its derived results; they cannot be re-derived, so a
    config-only change must not manufacture derived deltas under recompute.

    REQ-2 is approved but unverified, so verification coverage is 1 of 2 (50%).
    The baseline is taken under the default configuration (no verification
    gate); only then does the configuration grow a 100.0 threshold. Authored
    content never moves — any derived delta is manufactured by the config edit.
    """
    write(tmp_path)
    (tmp_path / "extra.qmd").write_text(
        "::: {.need #REQ-2 type=system-requirement status=approved priority=low}\n"
        "\n## Second\nSecond body.\n"
        "\n### Rationale\nSecond why.\n"
        ":::\n",
        encoding="utf-8",
    )
    before = baseline_of(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        "[gates]\nmin-verification-trace = 100.0\n", encoding="utf-8"
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config, recompute=True)

    assert report.notices == ("configuration-changed",)
    assert report.suppressed == ("findings", "metrics", "gates")
    assert report.modified == ()
    assert report.gate_regressions == ()
    assert report.metric_deltas == ()
    assert report.findings_added == ()


def test_configuration_change_still_compares_authored_relations(tmp_path: Path) -> None:
    """Authored comparison keeps running; only the derived deltas stop."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text('profile = "strict"\n', encoding="utf-8")
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert "configuration-changed" in report.notices
    assert report.added_relations == ()
    assert report.removed_relations == ()
    assert report.representation_changes == ()
    assert report.modified == ()


def test_recompute_reresolves_baseline_relations_through_the_catalog(tmp_path: Path) -> None:
    """Stored families are not trusted; authored names are resolved again."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    poisoned = {
        **before,
        "relations": [
            {**item, "semanticFamily": "bogus", "semanticFingerprint": "0" * 64}
            for item in before["relations"]
        ],
    }
    snapshot, config = snapshot_of(tmp_path)

    assert diff.compare(poisoned, snapshot, config).added_relations != ()
    assert diff.compare(poisoned, snapshot, config, recompute=True).added_relations == ()


def test_an_invalid_baseline_is_never_comparable(tmp_path: Path) -> None:
    write(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    with pytest.raises(diff.DiffError):
        diff.compare({"schemaVersion": "1", "valid": False}, snapshot, config)


def test_new_findings_are_reported_when_the_configuration_is_stable(tmp_path: Path) -> None:
    """A warning that appears with no policy change is a real regression."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    # Drop the rationale: REQ002 fires, and nothing about the policy moved.
    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        ":::\n" + "\n" + TEST_CASE,
        encoding="utf-8",
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert any(item["code"] == "REQ002" for item in report.findings_added)
    assert report.notices == ()


def test_metric_deltas_name_the_scope_and_strength(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    # Remove the verification edge: verification coverage drops.
    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        "\n### Rationale\nProtect data.\n"
        ":::\n" + "\n" + TEST_CASE,
        encoding="utf-8",
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    verification = [
        item for item in report.metric_deltas
        if item["scope"] == "approved-requirements" and item["strength"] == "verification-trace"
    ]
    assert verification
    assert verification[0]["before"] > verification[0]["after"]


def test_report_dict_is_json_safe_and_flags_emptiness(tmp_path: Path) -> None:
    import json as _json

    write(tmp_path)
    before = baseline_of(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    payload = diff.compare(before, snapshot, config).to_dict()

    assert payload["empty"] is True
    assert payload["schemaVersion"] == "1"
    _json.dumps(payload)


def test_editing_a_rationale_section_is_a_named_modification(tmp_path: Path) -> None:
    """The rationale heading is indexed into the field, so authoring it via
    Markdown still produces a per-field modification — alongside the body
    edit, since the section is part of the authored body by contract."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / "needs.qmd").write_text(
        REQUIREMENT.format(body="The service shall authenticate.").replace(
            "Protect data.", "Protect every privileged operation."
        )
        + TEST_CASE
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert [item["id"] for item in report.modified] == ["REQ-1"]
    assert "rationale" in report.modified[0]["fields"]
