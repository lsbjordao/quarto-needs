# Review package

Snapshot range: `task-6-before` -> `task-6-after`

## Files changed (3)

- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `src/quarto_needs/diff.py`
- `tests/test_diff.py`

## Summary

655 lines added, 3 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 01:38:10.668359063 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 02:03:22.863211465 -0300
@@ -1563,35 +1563,38 @@
     assert report.relocated == ()
 
 
 def test_added_and_removed_objects_are_classified(tmp_path: Path) -> None:
     write(tmp_path)
     before = baseline_of(tmp_path)
     (tmp_path / "extra.qmd").write_text(
         "::: {.need #REQ-2 type=functional-requirement status=draft}\n\n## Second\nBody.\n:::\n",
         encoding="utf-8",
     )
-    (tmp_path / "needs.qmd").write_text(REQUIREMENT.format(body="The service shall authenticate."), encoding="utf-8")
+    (tmp_path / "needs.qmd").write_text(
+        REQUIREMENT.format(body="The service shall authenticate.").replace("verified-by: TC-1\n", ""),
+        encoding="utf-8",
+    )
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     assert report.added_objects == ("REQ-2",)
     assert report.removed_objects == ("TC-1",)
 
 
 def test_a_changed_id_is_removal_plus_addition(tmp_path: Path) -> None:
     """Rename detection is deliberately excluded; it is inherently heuristic."""
     write(tmp_path)
     before = baseline_of(tmp_path)
     (tmp_path / "needs.qmd").write_text(
-        REQUIREMENT.format(body="The service shall authenticate.").replace("#REQ-1", "#REQ-9").replace("verified-by: TC-1", "verified-by: TC-1")
+        REQUIREMENT.format(body="The service shall authenticate.").replace("#REQ-1", "#REQ-9")
         + "\n" + TEST_CASE,
         encoding="utf-8",
     )
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     assert "REQ-9" in report.added_objects
     assert "REQ-1" in report.removed_objects
     assert report.modified == ()
@@ -2191,21 +2194,21 @@
         gate_regressions=gate_regressions,
     )
 ```
 
 Note the deliberate asymmetry: a configuration change still reports **authored** object and relation changes, exactly as the spec requires ("default `diff` compares authored object content and authored relation tuples only"). Only the derived categories are suppressed.
 
 - [ ] **Step 5: Run the diff tests**
 
 Run: `.venv/bin/python -m pytest tests/test_diff.py -q`
 
-Expected: PASS, all sixteen.
+Expected: PASS, all fifteen.
 
 - [ ] **Step 6: Run the full suite**
 
 Run: `.venv/bin/python -m pytest -q`
 
 Expected: PASS, no warnings.
 
 - [ ] **Step 7: Record the checkpoint conditionally**
 
 ```bash
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-before/src/quarto_needs/diff.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/src/quarto_needs/diff.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-before/src/quarto_needs/diff.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/src/quarto_needs/diff.py	2026-08-26 02:06:00.838941317 -0300
@@ -0,0 +1,378 @@
+"""Classified comparison between a baseline and the current snapshot.
+
+Two guards run before any comparison. A changed configuration or a changed
+reference date means the derived numbers were produced under different rules,
+so reporting their deltas as project changes would be a lie; the diff says so
+and suppresses them instead.
+"""
+from __future__ import annotations
+
+from dataclasses import dataclass, field
+from typing import Mapping, Sequence
+
+from . import fingerprints
+from .config import NeedsConfig
+from .quality import report_from_snapshot
+from .snapshot import AnalysisSnapshot
+
+SCHEMA_VERSION = "1"
+
+OBJECT_FIELDS = ("type", "title", "status", "body", "rationale", "attributes")
+
+
+class DiffError(Exception):
+    """The two sides cannot be compared."""
+
+
+@dataclass(frozen=True, slots=True)
+class DiffReport:
+    baseline_reference_date: str
+    current_reference_date: str
+    recomputed: bool
+    notices: tuple[str, ...]
+    added_objects: tuple[str, ...]
+    removed_objects: tuple[str, ...]
+    modified: tuple[Mapping[str, object], ...]
+    relocated: tuple[Mapping[str, object], ...]
+    added_relations: tuple[Mapping[str, object], ...]
+    removed_relations: tuple[Mapping[str, object], ...]
+    representation_changes: tuple[Mapping[str, object], ...]
+    findings_added: tuple[Mapping[str, object], ...]
+    findings_removed: tuple[Mapping[str, object], ...]
+    metric_deltas: tuple[Mapping[str, object], ...]
+    gate_regressions: tuple[Mapping[str, object], ...]
+
+    def is_empty(self) -> bool:
+        return not (
+            self.added_objects
+            or self.removed_objects
+            or self.modified
+            or self.relocated
+            or self.added_relations
+            or self.removed_relations
+            or self.representation_changes
+            or self.findings_added
+            or self.findings_removed
+            or self.metric_deltas
+            or self.gate_regressions
+        )
+
+    def to_dict(self) -> dict[str, object]:
+        return {
+            "schemaVersion": SCHEMA_VERSION,
+            "referenceDate": {
+                "baseline": self.baseline_reference_date,
+                "current": self.current_reference_date,
+            },
+            "recomputed": self.recomputed,
+            "notices": list(self.notices),
+            "objects": {
+                "added": list(self.added_objects),
+                "removed": list(self.removed_objects),
+                "modified": [dict(item) for item in self.modified],
+                "relocated": [dict(item) for item in self.relocated],
+            },
+            "relations": {
+                "added": [dict(item) for item in self.added_relations],
+                "removed": [dict(item) for item in self.removed_relations],
+                "representationChanged": [dict(item) for item in self.representation_changes],
+            },
+            "findings": {
+                "added": [dict(item) for item in self.findings_added],
+                "removed": [dict(item) for item in self.findings_removed],
+            },
+            "metrics": [dict(item) for item in self.metric_deltas],
+            "gates": {"regressed": [dict(item) for item in self.gate_regressions]},
+            "empty": self.is_empty(),
+        }
+
+
+def _baseline_objects(payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
+    return {str(item["id"]): item for item in payload.get("objects", [])}
+
+
+def _current_object(record) -> dict[str, object]:
+    from .snapshot import thaw_json
+
+    return {
+        "id": record.id,
+        "type": record.type,
+        "title": record.title,
+        "status": record.status,
+        "body": record.body,
+        "rationale": record.rationale,
+        "attributes": thaw_json(record.attributes),
+        "location": (
+            {
+                "file": record.locations[0].file,
+                "line": record.locations[0].line,
+                "anchor": record.locations[0].anchor,
+            }
+            if record.locations
+            else None
+        ),
+        "contentFingerprint": fingerprints.object_content_fingerprint(record),
+    }
+
+
+def _classify_objects(
+    before: Mapping[str, Mapping[str, object]], after: Mapping[str, Mapping[str, object]]
+) -> tuple[tuple[str, ...], tuple[str, ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
+    added = tuple(sorted(set(after) - set(before), key=lambda item: (item.casefold(), item)))
+    removed = tuple(sorted(set(before) - set(after), key=lambda item: (item.casefold(), item)))
+    modified: list[dict[str, object]] = []
+    relocated: list[dict[str, object]] = []
+    for object_id in sorted(set(before) & set(after), key=lambda item: (item.casefold(), item)):
+        old, new = before[object_id], after[object_id]
+        if old["contentFingerprint"] != new["contentFingerprint"]:
+            fields = [name for name in OBJECT_FIELDS if old.get(name) != new.get(name)]
+            modified.append({"id": object_id, "fields": fields})
+        old_location = old.get("location") or {}
+        new_location = new.get("location") or {}
+        # Relocation is keyed on the declaring file. A line-only shift is not a
+        # record: fingerprints already ignore line numbers, and one inserted
+        # paragraph would otherwise relocate every object below it.
+        if old_location.get("file") != new_location.get("file"):
+            relocated.append({"id": object_id, "from": old_location, "to": new_location})
+    return added, removed, tuple(modified), tuple(relocated)
+
+
+def _relation_entry(item: Mapping[str, object]) -> dict[str, object]:
+    return {
+        "source": item["source"],
+        "authoredName": item["authoredName"],
+        "target": item["target"],
+        "semanticFamily": item["semanticFamily"],
+    }
+
+
+def _current_relations(snapshot: AnalysisSnapshot) -> list[dict[str, object]]:
+    return [
+        {
+            "source": record.source,
+            "authoredName": record.authored_name,
+            "target": record.target,
+            "semanticFamily": record.semantic_family,
+            "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
+            "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
+        }
+        for record in snapshot.relations
+    ]
+
+
+def _classify_relations(
+    before: Sequence[Mapping[str, object]],
+    after: Sequence[Mapping[str, object]],
+    *,
+    key: str = "semanticFingerprint",
+) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
+    """Classify by `key`.
+
+    Semantic fingerprints are the default. When the configuration changed, the
+    caller keys on `authoredFingerprint` instead: a catalog change can move
+    families and roles, so semantic fingerprints from the two sides are not
+    comparable, and the spec requires authored tuples in that case.
+    """
+    before_semantic = {str(item[key]): item for item in before}
+    after_semantic = {str(item[key]): item for item in after}
+    added = tuple(
+        _relation_entry(after_semantic[key])
+        for key in sorted(set(after_semantic) - set(before_semantic))
+    )
+    removed = tuple(
+        _relation_entry(before_semantic[key])
+        for key in sorted(set(before_semantic) - set(after_semantic))
+    )
+    # Same edge, different authored spelling: informational, never a graph change.
+    representation = tuple(
+        {
+            **_relation_entry(after_semantic[key]),
+            "from": before_semantic[key]["authoredName"],
+            "to": after_semantic[key]["authoredName"],
+        }
+        for key in sorted(set(before_semantic) & set(after_semantic))
+        if before_semantic[key]["authoredFingerprint"] != after_semantic[key]["authoredFingerprint"]
+    )
+    return added, removed, representation
+
+
+def _finding_key(item: Mapping[str, object]) -> tuple[str, str, str]:
+    return (str(item.get("code")), str(item.get("object_id") or ""), str(item.get("message")))
+
+
+def _classify_findings(
+    before: Sequence[Mapping[str, object]], after: Sequence[Mapping[str, object]]
+) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
+    before_keys = {_finding_key(item): item for item in before}
+    after_keys = {_finding_key(item): item for item in after}
+    added = tuple(
+        {"code": key[0], "object_id": key[1] or None, "message": key[2], "severity": after_keys[key].get("severity")}
+        for key in sorted(set(after_keys) - set(before_keys))
+    )
+    removed = tuple(
+        {"code": key[0], "object_id": key[1] or None, "message": key[2], "severity": before_keys[key].get("severity")}
+        for key in sorted(set(before_keys) - set(after_keys))
+    )
+    return added, removed
+
+
+def _classify_metrics(
+    before: Mapping[str, object], after: Mapping[str, object]
+) -> tuple[dict[str, object], ...]:
+    deltas: list[dict[str, object]] = []
+    before_scopes = before.get("scopes", {}) if isinstance(before, Mapping) else {}
+    after_scopes = after.get("scopes", {})
+    for scope in sorted(set(before_scopes) | set(after_scopes)):
+        old_coverage = (before_scopes.get(scope) or {}).get("coverage", {})
+        new_coverage = (after_scopes.get(scope) or {}).get("coverage", {})
+        for strength in sorted(set(old_coverage) | set(new_coverage)):
+            old_percent = (old_coverage.get(strength) or {}).get("percent")
+            new_percent = (new_coverage.get(strength) or {}).get("percent")
+            if old_percent != new_percent:
+                deltas.append(
+                    {"scope": scope, "strength": strength, "before": old_percent, "after": new_percent}
+                )
+    return tuple(deltas)
+
+
+def _classify_gates(
+    before: Mapping[str, object], after: Mapping[str, object]
+) -> tuple[dict[str, object], ...]:
+    """Only pass -> fail is a regression; fail -> pass is progress, not a delta."""
+    before_gates = {
+        str(item["name"]): item for item in (before.get("gates", []) if isinstance(before, Mapping) else [])
+    }
+    regressions: list[dict[str, object]] = []
+    for item in after.get("gates", []):
+        name = str(item["name"])
+        was = before_gates.get(name)
+        if item.get("passed") is False and (was is None or was.get("passed") is not False):
+            regressions.append(
+                {"name": name, "scope": item.get("scope"), "threshold": item.get("threshold"), "actual": item.get("actual")}
+            )
+    return tuple(regressions)
+
+
+def _recomputed_relations(stored: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
+    """Re-resolve stored relations through the *current* catalog.
+
+    `--recompute-with current` must compare both sides under one policy, so the
+    baseline's authored names are resolved again rather than trusting the
+    families and roles that were canonical when it was written.
+    """
+    from .relations import DEFAULT_RELATION_CATALOG
+    from .snapshot import RelationRecord
+
+    recomputed: list[dict[str, object]] = []
+    for item in stored:
+        authored = str(item["authoredName"])
+        try:
+            kind = DEFAULT_RELATION_CATALOG.resolve(authored)
+        except ValueError:
+            # An authored name the current catalog no longer knows cannot be
+            # re-resolved; keep it verbatim so it surfaces as a real change.
+            recomputed.append(dict(item))
+            continue
+        record = RelationRecord(
+            source=str(item["source"]),
+            authored_name=authored,
+            catalog_name=kind.catalog_name,
+            v1_name=kind.v1_name,
+            target=str(item["target"]),
+            semantic_family=kind.semantic_family,
+            source_role=kind.source_role,
+            target_role=kind.target_role,
+            impact_direction=kind.impact_direction,
+            attributes=item.get("attributes") or {},
+            provenance=(),
+        )
+        recomputed.append(
+            {
+                "source": record.source,
+                "authoredName": record.authored_name,
+                "target": record.target,
+                "semanticFamily": record.semantic_family,
+                "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
+                "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
+            }
+        )
+    return recomputed
+
+
+def compare(
+    baseline_payload: Mapping[str, object],
+    snapshot: AnalysisSnapshot,
+    config: NeedsConfig,
+    *,
+    recompute: bool = False,
+) -> DiffReport:
+    if not baseline_payload.get("valid", False):
+        raise DiffError(
+            "This baseline is a diagnostic artifact (valid: false) and cannot be compared; "
+            "use `baseline inspect` to read it"
+        )
+
+    current_configuration = snapshot.configuration_fingerprint
+    baseline_configuration = str(baseline_payload.get("configurationFingerprint", ""))
+    baseline_date = str(baseline_payload.get("referenceDate", ""))
+
+    notices: list[str] = []
+    if not recompute:
+        if baseline_configuration != current_configuration:
+            notices.append("configuration-changed")
+        if baseline_date != snapshot.reference_date:
+            notices.append("reference-date-changed")
+
+    added, removed, modified, relocated = _classify_objects(
+        _baseline_objects(baseline_payload),
+        {record.id: _current_object(record) for record in snapshot.objects},
+    )
+
+    baseline_relations = list(baseline_payload.get("relations", []))
+    if recompute:
+        baseline_relations = _recomputed_relations(baseline_relations)
+    # A catalog change can move families and roles, so semantic fingerprints
+    # from the two sides stop being comparable. Fall back to authored tuples,
+    # which is exactly what the spec prescribes for this case.
+    relation_key = (
+        "authoredFingerprint" if "configuration-changed" in notices else "semanticFingerprint"
+    )
+    added_relations, removed_relations, representation = _classify_relations(
+        baseline_relations, _current_relations(snapshot), key=relation_key
+    )
+
+    # Derived results were computed under different rules or a different date,
+    # so their deltas describe the inputs, not the project. Suppress them and
+    # say why; `--recompute-with current` is the way to get them back.
+    derived_suppressed = bool(notices)
+    if derived_suppressed:
+        findings_added: tuple[dict[str, object], ...] = ()
+        findings_removed: tuple[dict[str, object], ...] = ()
+        metric_deltas: tuple[dict[str, object], ...] = ()
+        gate_regressions: tuple[dict[str, object], ...] = ()
+    else:
+        current_report = report_from_snapshot(snapshot, config).to_dict()
+        baseline_report = baseline_payload.get("report", {})
+        findings_added, findings_removed = _classify_findings(
+            baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
+        )
+        metric_deltas = _classify_metrics(baseline_report, current_report)
+        gate_regressions = _classify_gates(baseline_report, current_report)
+
+    return DiffReport(
+        baseline_reference_date=baseline_date,
+        current_reference_date=snapshot.reference_date,
+        recomputed=recompute,
+        notices=tuple(notices),
+        added_objects=added,
+        removed_objects=removed,
+        modified=modified,
+        relocated=relocated,
+        added_relations=added_relations,
+        removed_relations=removed_relations,
+        representation_changes=representation,
+        findings_added=findings_added,
+        findings_removed=findings_removed,
+        metric_deltas=metric_deltas,
+        gate_regressions=gate_regressions,
+    )
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-before/tests/test_diff.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/tests/test_diff.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-before/tests/test_diff.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-6-after/tests/test_diff.py	2026-08-26 02:05:08.719030445 -0300
@@ -0,0 +1,271 @@
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
+
+from quarto_needs import baseline, diff
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+
+REQUIREMENT = (
+    "::: {{.need #REQ-1 type=system-requirement status=approved priority=high}}\n"
+    "verified-by: TC-1\n"
+    "\n## Authenticate\n{body}\n"
+    "\n### Rationale\nProtect data.\n"
+    ":::\n"
+)
+TEST_CASE = "::: {.need #TC-1 type=test-case status=passed}\n\n## Login\nSigns in.\n:::\n"
+
+
+def write(root: Path, *, body: str = "The service shall authenticate.", order: str = "requirement-first", file: str = "needs.qmd") -> None:
+    for existing in root.glob("*.qmd"):
+        existing.unlink()
+    blocks = [REQUIREMENT.format(body=body), TEST_CASE]
+    if order != "requirement-first":
+        blocks.reverse()
+    (root / file).write_text("\n".join(blocks), encoding="utf-8")
+
+
+def snapshot_of(root: Path):
+    config = load_config(root)
+    result = analyze_project(root, config=config)
+    assert result.snapshot is not None
+    return result.snapshot, config
+
+
+def baseline_of(root: Path) -> dict[str, object]:
+    snapshot, config = snapshot_of(root)
+    return baseline.build_baseline(snapshot, config)
+
+
+def test_identical_input_produces_an_empty_diff(tmp_path: Path) -> None:
+    """The round-trip guarantee the milestone gate names."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert report.is_empty()
+    assert report.notices == ()
+
+
+def test_reordering_declarations_is_not_a_change(tmp_path: Path) -> None:
+    """Swapping two blocks in a file changes nothing semantic."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, order="test-first")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert report.modified == ()
+    assert report.relocated == ()
+    assert report.is_empty()
+
+
+def test_moving_a_need_to_another_file_is_relocation_only(tmp_path: Path) -> None:
+    """File change is a relocation record; content is untouched."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, file="moved.qmd")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert report.modified == ()
+    assert {item["id"] for item in report.relocated} == {"REQ-1", "TC-1"}
+    moved = next(item for item in report.relocated if item["id"] == "REQ-1")
+    assert moved["from"]["file"] == "needs.qmd"
+    assert moved["to"]["file"] == "moved.qmd"
+    assert "line" in moved["from"] and "line" in moved["to"]
+
+
+def test_editing_a_body_is_a_modification_named_by_field(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, body="The service shall authenticate every administrator.")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert [item["id"] for item in report.modified] == ["REQ-1"]
+    assert report.modified[0]["fields"] == ["body"]
+    assert report.relocated == ()
+
+
+def test_added_and_removed_objects_are_classified(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / "extra.qmd").write_text(
+        "::: {.need #REQ-2 type=functional-requirement status=draft}\n\n## Second\nBody.\n:::\n",
+        encoding="utf-8",
+    )
+    (tmp_path / "needs.qmd").write_text(
+        REQUIREMENT.format(body="The service shall authenticate.").replace("verified-by: TC-1\n", ""),
+        encoding="utf-8",
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert report.added_objects == ("REQ-2",)
+    assert report.removed_objects == ("TC-1",)
+
+
+def test_a_changed_id_is_removal_plus_addition(tmp_path: Path) -> None:
+    """Rename detection is deliberately excluded; it is inherently heuristic."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / "needs.qmd").write_text(
+        REQUIREMENT.format(body="The service shall authenticate.").replace("#REQ-1", "#REQ-9")
+        + "\n" + TEST_CASE,
+        encoding="utf-8",
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert "REQ-9" in report.added_objects
+    assert "REQ-1" in report.removed_objects
+    assert report.modified == ()
+
+
+def test_configuration_change_suppresses_derived_deltas(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert "configuration-changed" in report.notices
+    assert report.findings_added == ()
+    assert report.gate_regressions == ()
+
+
+def test_reference_date_change_suppresses_date_derived_deltas(tmp_path: Path) -> None:
+    """Evidence coverage and REQ015 depend on the date, not on authored content."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    before = {**before, "referenceDate": "1999-01-01"}
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert "reference-date-changed" in report.notices
+    assert report.metric_deltas == ()
+    assert report.findings_added == ()
+
+
+def test_recompute_clears_the_guards(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    before = {**before, "referenceDate": "1999-01-01"}
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config, recompute=True)
+
+    assert report.notices == ()
+    assert report.recomputed is True
+
+
+def test_configuration_change_still_compares_authored_relations(tmp_path: Path) -> None:
+    """Authored comparison keeps running; only the derived deltas stop."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text('profile = "strict"\n', encoding="utf-8")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert "configuration-changed" in report.notices
+    assert report.added_relations == ()
+    assert report.removed_relations == ()
+    assert report.representation_changes == ()
+    assert report.modified == ()
+
+
+def test_recompute_reresolves_baseline_relations_through_the_catalog(tmp_path: Path) -> None:
+    """Stored families are not trusted; authored names are resolved again."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    poisoned = {
+        **before,
+        "relations": [
+            {**item, "semanticFamily": "bogus", "semanticFingerprint": "0" * 64}
+            for item in before["relations"]
+        ],
+    }
+    snapshot, config = snapshot_of(tmp_path)
+
+    assert diff.compare(poisoned, snapshot, config).added_relations != ()
+    assert diff.compare(poisoned, snapshot, config, recompute=True).added_relations == ()
+
+
+def test_an_invalid_baseline_is_never_comparable(tmp_path: Path) -> None:
+    write(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(diff.DiffError):
+        diff.compare({"schemaVersion": "1", "valid": False}, snapshot, config)
+
+
+def test_new_findings_are_reported_when_the_configuration_is_stable(tmp_path: Path) -> None:
+    """A warning that appears with no policy change is a real regression."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    # Drop the rationale: REQ002 fires, and nothing about the policy moved.
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
+        "verified-by: TC-1\n"
+        "\n## Authenticate\nThe service shall authenticate.\n"
+        ":::\n" + "\n" + TEST_CASE,
+        encoding="utf-8",
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert any(item["code"] == "REQ002" for item in report.findings_added)
+    assert report.notices == ()
+
+
+def test_metric_deltas_name_the_scope_and_strength(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    # Remove the verification edge: verification coverage drops.
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
+        "\n## Authenticate\nThe service shall authenticate.\n"
+        "\n### Rationale\nProtect data.\n"
+        ":::\n" + "\n" + TEST_CASE,
+        encoding="utf-8",
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    verification = [
+        item for item in report.metric_deltas
+        if item["scope"] == "approved-requirements" and item["strength"] == "verification-trace"
+    ]
+    assert verification
+    assert verification[0]["before"] > verification[0]["after"]
+
+
+def test_report_dict_is_json_safe_and_flags_emptiness(tmp_path: Path) -> None:
+    import json as _json
+
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    payload = diff.compare(before, snapshot, config).to_dict()
+
+    assert payload["empty"] is True
+    assert payload["schemaVersion"] == "1"
+    _json.dumps(payload)
```
