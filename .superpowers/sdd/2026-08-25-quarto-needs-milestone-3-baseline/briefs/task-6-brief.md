# Task 6: Diff engine — guards, objects, relations, relocation

> Extracted from `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`. This brief is your complete requirements.
> Use every value in it verbatim.

## Global Constraints (bind every task)

- Do not add a runtime dependency. `referencing` enters the `test` optional dependency group only; it already ships as a `jsonschema` dependency.
- One analysis per command invocation. `baseline create`, `diff`, and `impact` each call `analyze_project` exactly once, matching the Milestone 1 guarantee locked by `tests/test_cli.py`.
- Preserve every existing signature and documented behavior: `parse_qmd`, `parse_project`, `RequirementsGraph.build`, `validate`, `coverage`, `export_graph`, `export_lua_index`, `cli.build`, `build_v1_payload`, `write_build_outputs`, `report_from_snapshot`, `build_quality_report`, and every existing CLI command and shortcode.
- Preserve schema v1 exactly. Fingerprints and baselines are new, separately named and versioned schemas. Nothing in this milestone changes `needs.json` bytes for a project whose configuration and reference date are unchanged.
- Fingerprints exclude line numbers, `href` values, generated metrics, and every other derived value.
- Exit codes are stable: `0` success, `1` validation or policy failure, `2` invalid usage or configuration, `3` operational I/O or serialization failure.
- Generated artifacts are deterministic for a fixed configuration and a fixed reference date, and are written atomically through `export._write_atomic_text`.
- The workspace has no `.git` metadata. Do not initialize Git. Every task ends with a conditional checkpoint that records a commit only when the executor is inside a Git worktree.
- Do not stop or restart the preview server listening on `127.0.0.1:8777`.
- Milestone 3 adds no Quarto shortcode and no `extensions.quartoNeeds` projection for diff or impact. `need-graph` and the interactive graph remain Milestone 5A.

## Task 6

Diff engine — guards, objects, relations, relocation

**Files:**
- Create: `src/quarto_needs/diff.py`
- Create: `tests/test_diff.py`

**Interfaces:**
- Consumes: `baseline.load_baseline` output shape from Task 4; fingerprint helpers from Task 3.
- Produces:
  - `diff.DiffReport` dataclass with `.to_dict()`
  - `diff.compare(baseline_payload: dict[str, object], snapshot: AnalysisSnapshot, config: NeedsConfig, *, recompute: bool = False) -> DiffReport`
  - `diff.DiffError(Exception)`

- [ ] **Step 1: Write the failing structural tests**

Create `tests/test_diff.py`. The first three tests are the acceptance gate in miniature.

```python
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
```

- [ ] **Step 2: Write the failing guard tests**

Append to `tests/test_diff.py`:

```python
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


def test_recompute_clears_the_guards(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    before = {**before, "referenceDate": "1999-01-01"}
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config, recompute=True)

    assert report.notices == ()
    assert report.recomputed is True


def test_recompute_does_not_manufacture_derived_deltas_from_a_config_change(tmp_path: Path) -> None:
    """The baseline stores its derived results; they cannot be re-derived, so a
    config-only change must stay silent even under recompute.

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

    assert report.notices == ()
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
```

- [ ] **Step 3: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_diff.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'quarto_needs.diff'`.

- [ ] **Step 4: Implement the report and the guards**

Create `src/quarto_needs/diff.py`:

```python
"""Classified comparison between a baseline and the current snapshot.

Two guards run before any comparison. A changed configuration or a changed
reference date means the derived numbers were produced under different rules,
so reporting their deltas as project changes would be a lie; the diff says so
and suppresses them instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from . import fingerprints
from .config import NeedsConfig
from .quality import report_from_snapshot
from .snapshot import AnalysisSnapshot

SCHEMA_VERSION = "1"

OBJECT_FIELDS = ("type", "title", "status", "body", "rationale", "attributes")


class DiffError(Exception):
    """The two sides cannot be compared."""


@dataclass(frozen=True, slots=True)
class DiffReport:
    baseline_reference_date: str
    current_reference_date: str
    recomputed: bool
    notices: tuple[str, ...]
    added_objects: tuple[str, ...]
    removed_objects: tuple[str, ...]
    modified: tuple[Mapping[str, object], ...]
    relocated: tuple[Mapping[str, object], ...]
    added_relations: tuple[Mapping[str, object], ...]
    removed_relations: tuple[Mapping[str, object], ...]
    representation_changes: tuple[Mapping[str, object], ...]
    findings_added: tuple[Mapping[str, object], ...]
    findings_removed: tuple[Mapping[str, object], ...]
    metric_deltas: tuple[Mapping[str, object], ...]
    gate_regressions: tuple[Mapping[str, object], ...]

    def is_empty(self) -> bool:
        return not (
            self.added_objects
            or self.removed_objects
            or self.modified
            or self.relocated
            or self.added_relations
            or self.removed_relations
            or self.representation_changes
            or self.findings_added
            or self.findings_removed
            or self.metric_deltas
            or self.gate_regressions
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "referenceDate": {
                "baseline": self.baseline_reference_date,
                "current": self.current_reference_date,
            },
            "recomputed": self.recomputed,
            "notices": list(self.notices),
            "objects": {
                "added": list(self.added_objects),
                "removed": list(self.removed_objects),
                "modified": [dict(item) for item in self.modified],
                "relocated": [dict(item) for item in self.relocated],
            },
            "relations": {
                "added": [dict(item) for item in self.added_relations],
                "removed": [dict(item) for item in self.removed_relations],
                "representationChanged": [dict(item) for item in self.representation_changes],
            },
            "findings": {
                "added": [dict(item) for item in self.findings_added],
                "removed": [dict(item) for item in self.findings_removed],
            },
            "metrics": [dict(item) for item in self.metric_deltas],
            "gates": {"regressed": [dict(item) for item in self.gate_regressions]},
            "empty": self.is_empty(),
        }
```

- [ ] **Step 5: Implement object and relocation classification**

Append to `diff.py`:

```python
def _baseline_objects(payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    return {str(item["id"]): item for item in payload.get("objects", [])}


def _current_object(record) -> dict[str, object]:
    from .snapshot import thaw_json

    return {
        "id": record.id,
        "type": record.type,
        "title": record.title,
        "status": record.status,
        "body": record.body,
        "rationale": record.rationale,
        "attributes": thaw_json(record.attributes),
        "location": (
            {
                "file": record.locations[0].file,
                "line": record.locations[0].line,
                "anchor": record.locations[0].anchor,
            }
            if record.locations
            else None
        ),
        "contentFingerprint": fingerprints.object_content_fingerprint(record),
    }


def _classify_objects(
    before: Mapping[str, Mapping[str, object]], after: Mapping[str, Mapping[str, object]]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    added = tuple(sorted(set(after) - set(before), key=lambda item: (item.casefold(), item)))
    removed = tuple(sorted(set(before) - set(after), key=lambda item: (item.casefold(), item)))
    modified: list[dict[str, object]] = []
    relocated: list[dict[str, object]] = []
    for object_id in sorted(set(before) & set(after), key=lambda item: (item.casefold(), item)):
        old, new = before[object_id], after[object_id]
        if old["contentFingerprint"] != new["contentFingerprint"]:
            fields = [name for name in OBJECT_FIELDS if old.get(name) != new.get(name)]
            modified.append({"id": object_id, "fields": fields})
        old_location = old.get("location") or {}
        new_location = new.get("location") or {}
        # Relocation is keyed on the declaring file. A line-only shift is not a
        # record: fingerprints already ignore line numbers, and one inserted
        # paragraph would otherwise relocate every object below it.
        if old_location.get("file") != new_location.get("file"):
            relocated.append({"id": object_id, "from": old_location, "to": new_location})
    return added, removed, tuple(modified), tuple(relocated)
```

- [ ] **Step 6: Implement relation classification**

Append to `diff.py`:

```python
def _relation_entry(item: Mapping[str, object]) -> dict[str, object]:
    return {
        "source": item["source"],
        "authoredName": item["authoredName"],
        "target": item["target"],
        "semanticFamily": item["semanticFamily"],
    }


def _current_relations(snapshot: AnalysisSnapshot) -> list[dict[str, object]]:
    return [
        {
            "source": record.source,
            "authoredName": record.authored_name,
            "target": record.target,
            "semanticFamily": record.semantic_family,
            "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
            "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
        }
        for record in snapshot.relations
    ]


def _classify_relations(
    before: Sequence[Mapping[str, object]],
    after: Sequence[Mapping[str, object]],
    *,
    key: str = "semanticFingerprint",
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    """Classify by `key`.

    Semantic fingerprints are the default. When the configuration changed, the
    caller keys on `authoredFingerprint` instead: a catalog change can move
    families and roles, so semantic fingerprints from the two sides are not
    comparable, and the spec requires authored tuples in that case.
    """
    before_semantic = {str(item[key]): item for item in before}
    after_semantic = {str(item[key]): item for item in after}
    added = tuple(
        _relation_entry(after_semantic[key])
        for key in sorted(set(after_semantic) - set(before_semantic))
    )
    removed = tuple(
        _relation_entry(before_semantic[key])
        for key in sorted(set(before_semantic) - set(after_semantic))
    )
    # Same edge, different authored spelling: informational, never a graph change.
    representation = tuple(
        {
            **_relation_entry(after_semantic[key]),
            "from": before_semantic[key]["authoredName"],
            "to": after_semantic[key]["authoredName"],
        }
        for key in sorted(set(before_semantic) & set(after_semantic))
        if before_semantic[key]["authoredFingerprint"] != after_semantic[key]["authoredFingerprint"]
    )
    return added, removed, representation
```

- [ ] **Step 7: Run the structural tests**

Run: `.venv/bin/python -m pytest tests/test_diff.py -q -k "identical or reordering or moving or editing or added_and_removed or changed_id"`

Expected: FAIL — `compare` does not exist yet. Task 7 adds it. Confirm the failure is `AttributeError: module 'quarto_needs.diff' has no attribute 'compare'` and not an error inside the helpers.

- [ ] **Step 8: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/diff.py tests/test_diff.py
  git commit -m "feat: add diff classification helpers"
else
  echo "Checkpoint 6 verified; workspace has no Git metadata."
fi
```
