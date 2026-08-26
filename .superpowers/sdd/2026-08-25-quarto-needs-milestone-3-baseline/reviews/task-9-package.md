# Review package

Snapshot range: `task-9-before` -> `task-9-after`

## Files changed (3)

- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `src/quarto_needs/impact.py`
- `tests/test_impact.py`

## Summary

330 lines added, 6 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 10:13:39.734700226 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 10:32:49.309293383 -0300
@@ -2590,31 +2590,31 @@
 verified-by: TC-1
 conflicts-with: DOC-1
 
 ## Authenticate
 {body}
 
 ### Rationale
 Protect data.
 :::
 
-::: {{.need #TC-1 type=test-case status=passed}}
-
-## Login
-Signs in.
-:::
-
 ::: {{.need #DOC-1 type=need status=draft}}
 
 ## Manual
 Login manual.
 :::
+
+::: {{.need #TC-1 type=test-case status=passed}}
+
+## Login
+Signs in.
+:::
 """
 
 
 def write(root: Path, *, body: str = "The service shall authenticate.", keep_test: bool = True) -> None:
     text = CHAIN.format(body=body)
     if not keep_test:
         text = text.split("::: {.need #TC-1", 1)[0].replace("verified-by: TC-1\n", "")
     (root / "chain.qmd").write_text(text, encoding="utf-8")
 
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-before/src/quarto_needs/impact.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-after/src/quarto_needs/impact.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-before/src/quarto_needs/impact.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-after/src/quarto_needs/impact.py	2026-08-26 10:34:50.553167579 -0300
@@ -0,0 +1,159 @@
+"""Union-graph impact traversal with explicit, auditable paths.
+
+The traversal runs over the union of the baseline and current graphs so a
+removed node or edge remains explainable. There is deliberately no risk score:
+the output is the path that produced each result.
+"""
+from __future__ import annotations
+
+from collections import deque
+from dataclasses import dataclass
+from typing import Mapping, Sequence
+
+from . import diff as diff_module
+from .config import NeedsConfig
+from .snapshot import AnalysisSnapshot
+
+SCHEMA_VERSION = "1"
+MAX_DISTANCE = 10
+
+
+class ImpactError(Exception):
+    """The two graphs cannot be traversed together."""
+
+
+@dataclass(frozen=True, slots=True)
+class ImpactReport:
+    origins: tuple[Mapping[str, object], ...]
+    impacted: tuple[Mapping[str, object], ...]
+
+    def to_dict(self) -> dict[str, object]:
+        return {
+            "schemaVersion": SCHEMA_VERSION,
+            "origins": [dict(item) for item in self.origins],
+            "impacted": [dict(item) for item in self.impacted],
+        }
+
+
+def _union_edges(
+    baseline_relations: Sequence[Mapping[str, object]], snapshot: AnalysisSnapshot
+) -> dict[str, list[tuple[str, str]]]:
+    """Adjacency keyed by source, following each relation's impact direction.
+
+    `both` yields an edge in each direction; `none` yields none at all.
+    """
+    adjacency: dict[str, list[tuple[str, str]]] = {}
+
+    def add(source: str, target: str, name: str, direction: str) -> None:
+        if direction in {"source_to_target", "both"}:
+            adjacency.setdefault(source, []).append((target, name))
+        if direction in {"target_to_source", "both"}:
+            adjacency.setdefault(target, []).append((source, name))
+
+    for item in baseline_relations:
+        add(
+            str(item["source"]),
+            str(item["target"]),
+            str(item["authoredName"]),
+            str(item.get("impactDirection", "none")),
+        )
+    for record in snapshot.relations:
+        add(record.source, record.target, record.authored_name, record.impact_direction)
+
+    for key in adjacency:
+        adjacency[key] = sorted(set(adjacency[key]))
+    return adjacency
+
+
+def _origins(report: diff_module.DiffReport) -> tuple[dict[str, object], ...]:
+    origins: list[dict[str, object]] = []
+    for object_id in report.added_objects:
+        origins.append({"id": object_id, "change": "added"})
+    for object_id in report.removed_objects:
+        origins.append({"id": object_id, "change": "removed"})
+    for item in report.modified:
+        origins.append({"id": str(item["id"]), "change": "modified", "fields": list(item["fields"])})
+    for item in report.added_relations:
+        origins.append({"id": str(item["source"]), "change": "relation-added"})
+    for item in report.removed_relations:
+        origins.append({"id": str(item["source"]), "change": "relation-removed"})
+    seen: dict[str, dict[str, object]] = {}
+    for origin in origins:
+        seen.setdefault(str(origin["id"]), origin)
+    return tuple(seen[key] for key in sorted(seen, key=lambda item: (item.casefold(), item)))
+
+
+def _priority(
+    object_id: str, snapshot: AnalysisSnapshot, baseline_objects: Mapping[str, Mapping[str, object]]
+) -> str | None:
+    record = snapshot.objects_by_id.get(object_id)
+    if record is not None:
+        return record.priority
+    stored = baseline_objects.get(object_id)
+    if stored is None:
+        return None
+    attributes = stored.get("attributes") or {}
+    value = attributes.get("priority")
+    return str(value) if value not in (None, "") else None
+
+
+def analyze(
+    baseline_payload: Mapping[str, object],
+    snapshot: AnalysisSnapshot,
+    config: NeedsConfig,
+    *,
+    recompute: bool = False,
+) -> ImpactReport:
+    if not baseline_payload.get("valid", False):
+        raise ImpactError(
+            "This baseline is a diagnostic artifact (valid: false) and cannot be traversed"
+        )
+    if not recompute and str(
+        baseline_payload.get("configurationFingerprint", "")
+    ) != snapshot.configuration_fingerprint:
+        raise ImpactError(
+            "The baseline was produced under a different configuration; "
+            "pass --recompute-with current so one relation policy governs the traversal"
+        )
+
+    report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
+    origins = _origins(report)
+    adjacency = _union_edges(baseline_payload.get("relations", []), snapshot)
+    baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
+    origin_ids = {str(item["id"]) for item in origins}
+
+    impacted: dict[tuple[str, str], dict[str, object]] = {}
+    for origin in origins:
+        start = str(origin["id"])
+        queue: deque[tuple[str, tuple[str, ...], tuple[str, ...]]] = deque([(start, (start,), ())])
+        visited = {start}
+        while queue:
+            current, path, relations = queue.popleft()
+            distance = len(path) - 1
+            if distance >= MAX_DISTANCE:
+                continue
+            for neighbor, relation_name in adjacency.get(current, []):
+                if neighbor in visited:
+                    continue
+                visited.add(neighbor)
+                next_path = path + (neighbor,)
+                next_relations = relations + (relation_name,)
+                key = (start, neighbor)
+                if neighbor not in origin_ids and key not in impacted:
+                    impacted[key] = {
+                        "id": neighbor,
+                        "origin": start,
+                        "change": origin["change"],
+                        "classification": "direct" if len(next_path) == 2 else "transitive",
+                        "distance": len(next_path) - 1,
+                        "relations": list(next_relations),
+                        "path": list(next_path),
+                        "priority": _priority(neighbor, snapshot, baseline_objects),
+                    }
+                queue.append((neighbor, next_path, next_relations))
+
+    ordered = tuple(
+        impacted[key]
+        for key in sorted(impacted, key=lambda item: (item[0].casefold(), item[0], item[1].casefold(), item[1]))
+    )
+    return ImpactReport(origins=origins, impacted=ordered)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-before/tests/test_impact.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-after/tests/test_impact.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-before/tests/test_impact.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-9-after/tests/test_impact.py	2026-08-26 10:34:05.789206103 -0300
@@ -0,0 +1,165 @@
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
+
+from quarto_needs import baseline, impact
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+
+CHAIN = """::: {{.need #STK-1 type=stakeholder-need status=approved priority=high}}
+
+## Stakeholder
+Needs secure access.
+:::
+
+::: {{.need #REQ-1 type=functional-requirement status=approved priority=high}}
+derives-from: STK-1
+verified-by: TC-1
+conflicts-with: DOC-1
+
+## Authenticate
+{body}
+
+### Rationale
+Protect data.
+:::
+
+::: {{.need #DOC-1 type=need status=draft}}
+
+## Manual
+Login manual.
+:::
+
+::: {{.need #TC-1 type=test-case status=passed}}
+
+## Login
+Signs in.
+:::
+"""
+
+
+def write(root: Path, *, body: str = "The service shall authenticate.", keep_test: bool = True) -> None:
+    text = CHAIN.format(body=body)
+    if not keep_test:
+        text = text.split("::: {.need #TC-1", 1)[0].replace("verified-by: TC-1\n", "")
+    (root / "chain.qmd").write_text(text, encoding="utf-8")
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
+def test_no_change_produces_no_impact(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    assert report.origins == ()
+    assert report.impacted == ()
+
+
+def test_editing_a_requirement_impacts_its_verification(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, body="The service shall authenticate every administrator.")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    assert [item["id"] for item in report.origins] == ["REQ-1"]
+    impacted = {item["id"]: item for item in report.impacted}
+    assert "TC-1" in impacted
+    assert impacted["TC-1"]["classification"] == "direct"
+    assert impacted["TC-1"]["distance"] == 1
+    assert impacted["TC-1"]["path"] == ["REQ-1", "TC-1"]
+    assert impacted["TC-1"]["relations"] == ["verified-by"]
+
+
+def test_every_impacted_result_carries_an_explicit_path(tmp_path: Path) -> None:
+    """The gate forbids an opaque score; a path is the audit trail."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, body="Changed.")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    assert report.impacted
+    for item in report.impacted:
+        assert item["path"][0] == item["origin"]
+        assert item["path"][-1] == item["id"]
+        assert len(item["path"]) == item["distance"] + 1
+        assert item["classification"] in {"direct", "transitive"}
+        assert "priority" in item
+
+
+def test_removing_a_node_still_explains_its_neighbors(tmp_path: Path) -> None:
+    """Union traversal is why a removed node and its removed edges stay explainable.
+
+    `verified-by` propagates from requirement to test, so the removed test case
+    cannot reach the requirement it verified; the removal surfaces instead as
+    two origins — the removed node and the requirement that lost the edge.
+    """
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, keep_test=False)
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    changes = {item["id"]: item["change"] for item in report.origins}
+    assert changes.get("TC-1") == "removed"
+    assert changes.get("REQ-1") == "relation-removed"
+
+
+def test_removal_reaches_neighbors_through_baseline_only_edges(tmp_path: Path) -> None:
+    """A dropped `conflicts-with` still propagates: the edge exists only in the
+    baseline, so without the union adjacency DOC-1 would be unreachable."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    text = (tmp_path / "chain.qmd").read_text(encoding="utf-8").replace("conflicts-with: DOC-1\n", "")
+    (tmp_path / "chain.qmd").write_text(text, encoding="utf-8")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    changes = {item["id"]: item["change"] for item in report.origins}
+    assert changes.get("REQ-1") == "relation-removed"
+    doc = next(item for item in report.impacted if item["id"] == "DOC-1")
+    assert doc["classification"] == "direct"
+    assert doc["relations"] == ["conflicts-with"]
+
+
+def test_impact_rejects_a_configuration_mismatch_without_recompute(tmp_path: Path) -> None:
+    """One relation policy must govern the whole traversal."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(impact.ImpactError):
+        impact.analyze(before, snapshot, config)
+
+    assert impact.analyze(before, snapshot, config, recompute=True) is not None
+
+
+def test_impact_rejects_a_diagnostic_baseline(tmp_path: Path) -> None:
+    write(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(impact.ImpactError):
+        impact.analyze({"schemaVersion": "1", "valid": False}, snapshot, config)
```
