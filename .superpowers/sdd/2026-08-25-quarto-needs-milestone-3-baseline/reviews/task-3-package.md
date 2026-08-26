# Review package

Snapshot range: `task-3-before` -> `task-3-after`

## Files changed (5)

- `src/quarto_needs/analysis.py`
- `src/quarto_needs/fingerprints.py`
- `src/quarto_needs/snapshot.py`
- `tests/test_fingerprints.py`
- `tests/test_snapshot.py`

## Summary

251 lines added, 1 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/src/quarto_needs/analysis.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/src/quarto_needs/analysis.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/src/quarto_needs/analysis.py	2026-08-25 13:03:20.899930532 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/src/quarto_needs/analysis.py	2026-08-25 21:17:55.010723394 -0300
@@ -1,21 +1,22 @@
 from __future__ import annotations
 
 import json
 from collections.abc import Iterable
 from dataclasses import replace
 from pathlib import Path
 from typing import cast
 
 import quarto_needs
 
-from .config import NeedsConfig, embedded_defaults, load_config
+from . import fingerprints
+from .config import NeedsConfig, embedded_defaults, load_config, reference_date
 from .diagnostics import Finding
 from .model import EngineeringObject, Relation, SourceLocation
 from .parser import parse_project_declarations
 from .relations import DEFAULT_RELATION_CATALOG
 from .rules import apply_rule_settings, run_rules
 from .snapshot import (
     AnalysisResult,
     AnalysisSnapshot,
     DeclarationBatch,
     LocationRecord,
@@ -303,31 +304,40 @@
     outgoing: dict[str, tuple[RelationRecord, ...]] = {}
     incoming: dict[str, tuple[RelationRecord, ...]] = {}
     for item in objects:
         outgoing[item.id] = tuple(
             relation for relation in relations if relation.source == item.id
         )
         incoming[item.id] = tuple(
             relation for relation in relations if relation.target == item.id
         )
     metrics = legacy_coverage(objects, relations)
+    configuration = fingerprints.configuration_fingerprint(
+        effective_config, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
+    )
     draft = AnalysisSnapshot(
         objects=objects,
         relations=relations,
         findings=findings,
         metrics=metrics,
         objects_by_id=objects_by_id,
         outgoing=outgoing,
         incoming=incoming,
         generator_name="quarto-needs",
         generator_version=quarto_needs.__version__,
         relation_catalog_version=DEFAULT_RELATION_CATALOG.version,
+        reference_date=reference_date().isoformat(),
+        configuration_fingerprint=configuration,
+        semantic_graph_fingerprint=fingerprints.semantic_graph_fingerprint(
+            objects, relations, configuration
+        ),
+        representation_fingerprint=fingerprints.representation_fingerprint(relations),
     )
     rule_findings = run_rules(draft, effective_config)
     snapshot = (
         replace(draft, findings=_merge_findings(findings, rule_findings))
         if rule_findings
         else draft
     )
     return AnalysisResult(declarations, snapshot.findings, snapshot)
 
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/src/quarto_needs/fingerprints.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/src/quarto_needs/fingerprints.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/src/quarto_needs/fingerprints.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/src/quarto_needs/fingerprints.py	2026-08-25 21:20:54.690269061 -0300
@@ -0,0 +1,101 @@
+"""Pure content fingerprints over the canonical snapshot records.
+
+Every fingerprint excludes line numbers, `href` values, generated metrics,
+and any other derived data, so provenance changes and rendering changes can
+never masquerade as semantic ones.
+"""
+from __future__ import annotations
+
+import hashlib
+import json
+from typing import Iterable
+
+from .config import NeedsConfig
+from .rules import RULE_SET_VERSION
+from .snapshot import ObjectRecord, RelationRecord, thaw_json
+
+
+def _digest(payload: object) -> str:
+    encoded = json.dumps(
+        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
+    ).encode("utf-8")
+    return hashlib.sha256(encoded).hexdigest()
+
+
+def object_content_fingerprint(record: ObjectRecord) -> str:
+    return _digest(
+        {
+            "id": record.id,
+            "type": record.type,
+            "title": record.title,
+            "body": record.body,
+            "rationale": record.rationale,
+            "status": record.status,
+            "priority": record.priority,
+            "tags": list(record.tags),
+            "attributes": thaw_json(record.attributes),
+        }
+    )
+
+
+def relation_authored_fingerprint(record: RelationRecord) -> str:
+    return _digest(
+        {
+            "source": record.source,
+            "authored_name": record.authored_name,
+            "target": record.target,
+            "attributes": thaw_json(record.attributes),
+        }
+    )
+
+
+def relation_semantic_fingerprint(record: RelationRecord) -> str:
+    """Identity of the edge itself, independent of which end authored it.
+
+    Endpoints are sorted by role, so an alias flip that preserves the roles
+    yields the same fingerprint and is classified as representation-only.
+    """
+    endpoints = sorted(
+        (
+            {"id": record.source, "role": record.source_role},
+            {"id": record.target, "role": record.target_role},
+        ),
+        key=lambda item: (item["role"], item["id"]),
+    )
+    return _digest(
+        {
+            "family": record.semantic_family,
+            "endpoints": endpoints,
+            "attributes": thaw_json(record.attributes),
+        }
+    )
+
+
+def configuration_fingerprint(
+    config: NeedsConfig, *, relation_catalog_version: str
+) -> str:
+    return _digest(
+        {
+            "configuration": config.canonical_document(),
+            "relationCatalogVersion": relation_catalog_version,
+            "ruleSetVersion": RULE_SET_VERSION,
+        }
+    )
+
+
+def semantic_graph_fingerprint(
+    objects: Iterable[ObjectRecord],
+    relations: Iterable[RelationRecord],
+    configuration: str,
+) -> str:
+    return _digest(
+        {
+            "objects": sorted(object_content_fingerprint(item) for item in objects),
+            "relations": sorted(relation_semantic_fingerprint(item) for item in relations),
+            "configuration": configuration,
+        }
+    )
+
+
+def representation_fingerprint(relations: Iterable[RelationRecord]) -> str:
+    return _digest(sorted(relation_authored_fingerprint(item) for item in relations))
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/src/quarto_needs/snapshot.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/src/quarto_needs/snapshot.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/src/quarto_needs/snapshot.py	2026-08-25 09:32:13.098541935 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/src/quarto_needs/snapshot.py	2026-08-25 21:17:41.730756974 -0300
@@ -151,20 +151,24 @@
     objects: tuple[ObjectRecord, ...]
     relations: tuple[RelationRecord, ...]
     findings: tuple[Finding, ...]
     metrics: Mapping[str, object]
     objects_by_id: Mapping[str, ObjectRecord]
     outgoing: Mapping[str, tuple[RelationRecord, ...]]
     incoming: Mapping[str, tuple[RelationRecord, ...]]
     generator_name: str
     generator_version: str
     relation_catalog_version: str
+    reference_date: str = ""
+    configuration_fingerprint: str = ""
+    semantic_graph_fingerprint: str = ""
+    representation_fingerprint: str = ""
 
     def __post_init__(self) -> None:
         object.__setattr__(self, "objects", tuple(self.objects))
         object.__setattr__(self, "relations", tuple(self.relations))
         object.__setattr__(self, "findings", tuple(self.findings))
         object.__setattr__(self, "metrics", _freeze_mapping(self.metrics))
         object.__setattr__(
             self, "objects_by_id", MappingProxyType(dict(self.objects_by_id))
         )
         object.__setattr__(
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/tests/test_fingerprints.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/tests/test_fingerprints.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/tests/test_fingerprints.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/tests/test_fingerprints.py	2026-08-25 21:16:48.134892483 -0300
@@ -0,0 +1,116 @@
+from __future__ import annotations
+
+from quarto_needs import fingerprints
+from quarto_needs.config import embedded_defaults
+from quarto_needs.snapshot import LocationRecord, ObjectRecord, RelationRecord
+
+
+def make_object(**overrides: object) -> ObjectRecord:
+    base = dict(
+        id="REQ-1",
+        type="functional-requirement",
+        title="Authenticate",
+        status="approved",
+        body="The service shall authenticate.",
+        rationale="Protect data.",
+        attributes={"priority": "high", "tags": "security"},
+        locations=(LocationRecord("a.qmd", 10, "REQ-1"),),
+    )
+    base.update(overrides)
+    return ObjectRecord(**base)
+
+
+def make_relation(**overrides: object) -> RelationRecord:
+    base = dict(
+        source="REQ-1",
+        authored_name="verified-by",
+        catalog_name="verified-by",
+        v1_name="verified-by",
+        target="TC-1",
+        semantic_family="verification",
+        source_role="requirement",
+        target_role="test",
+        impact_direction="source_to_target",
+        attributes={},
+        provenance=(LocationRecord("a.qmd", 12, None),),
+    )
+    base.update(overrides)
+    return RelationRecord(**base)
+
+
+def test_object_fingerprint_ignores_line_numbers_and_file() -> None:
+    """Provenance is not authored semantics; moving a need must not modify it."""
+    moved = make_object(locations=(LocationRecord("b.qmd", 900, "REQ-1"),))
+
+    assert fingerprints.object_content_fingerprint(make_object()) == \
+        fingerprints.object_content_fingerprint(moved)
+
+
+def test_object_fingerprint_changes_with_every_authored_field() -> None:
+    """Each field the spec names must actually participate."""
+    original = fingerprints.object_content_fingerprint(make_object())
+    for field, value in (
+        ("type", "system-requirement"),
+        ("title", "Other"),
+        ("status", "draft"),
+        ("body", "Different body."),
+        ("rationale", "Different rationale."),
+        ("attributes", {"priority": "low", "tags": "security"}),
+    ):
+        assert fingerprints.object_content_fingerprint(make_object(**{field: value})) != original, field
+
+
+def test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation() -> None:
+    """REQ -verified-by-> TC and TC -verifies-> REQ are one semantic edge."""
+    forward = make_relation()
+    inverse = make_relation(
+        source="TC-1",
+        authored_name="verifies",
+        catalog_name="verifies",
+        v1_name="verifies",
+        target="REQ-1",
+        source_role="test",
+        target_role="requirement",
+        impact_direction="target_to_source",
+    )
+
+    assert fingerprints.relation_semantic_fingerprint(forward) == \
+        fingerprints.relation_semantic_fingerprint(inverse)
+    assert fingerprints.relation_authored_fingerprint(forward) != \
+        fingerprints.relation_authored_fingerprint(inverse)
+
+
+def test_semantic_relation_fingerprint_changes_with_family_and_endpoints() -> None:
+    original = fingerprints.relation_semantic_fingerprint(make_relation())
+
+    assert fingerprints.relation_semantic_fingerprint(make_relation(semantic_family="evidence")) != original
+    assert fingerprints.relation_semantic_fingerprint(make_relation(target="TC-2")) != original
+    assert fingerprints.relation_semantic_fingerprint(make_relation(attributes={"note": "x"})) != original
+
+
+def test_graph_fingerprint_is_order_independent_and_configuration_sensitive() -> None:
+    """Reordering declarations is not a change; changing policy is."""
+    objects = [make_object(), make_object(id="REQ-2")]
+    relations = [make_relation(), make_relation(target="TC-2")]
+    configuration = fingerprints.configuration_fingerprint(
+        embedded_defaults(), relation_catalog_version="1"
+    )
+
+    forward = fingerprints.semantic_graph_fingerprint(objects, relations, configuration)
+    reversed_order = fingerprints.semantic_graph_fingerprint(
+        list(reversed(objects)), list(reversed(relations)), configuration
+    )
+    other_configuration = fingerprints.semantic_graph_fingerprint(
+        objects, relations, configuration="different"
+    )
+
+    assert forward == reversed_order
+    assert forward != other_configuration
+
+
+def test_configuration_fingerprint_tracks_catalog_and_rule_set_versions() -> None:
+    """A catalog-only change must be visible as a configuration change."""
+    config = embedded_defaults()
+
+    assert fingerprints.configuration_fingerprint(config, relation_catalog_version="1") != \
+        fingerprints.configuration_fingerprint(config, relation_catalog_version="2")
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/tests/test_snapshot.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/tests/test_snapshot.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-before/tests/test_snapshot.py	2026-08-25 09:29:03.318949909 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/tests/test_snapshot.py	2026-08-25 21:17:31.450782966 -0300
@@ -1,10 +1,11 @@
+from pathlib import Path
 from types import MappingProxyType
 
 import pytest
 
 from quarto_needs.snapshot import freeze_json, thaw_json
 
 
 def test_freeze_json_is_recursive_and_round_trips() -> None:
     source = {"tags": ["security", "login"], "nested": {"rank": 1}}
 
@@ -12,10 +13,28 @@
     source["tags"].append("mutated")
 
     assert isinstance(frozen, MappingProxyType)
     assert frozen["tags"] == ("security", "login")
     with pytest.raises(TypeError):
         frozen["nested"]["rank"] = 2
     assert thaw_json(frozen) == {
         "nested": {"rank": 1},
         "tags": ["security", "login"],
     }
+
+
+def test_snapshot_records_reference_date_and_fingerprints(tmp_path: Path) -> None:
+    """Baselines need every comparison axis from the snapshot itself."""
+    from quarto_needs.analysis import analyze_project
+    from quarto_needs.config import reference_date
+
+    (tmp_path / "a.qmd").write_text(
+        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+
+    snapshot = analyze_project(tmp_path).snapshot
+
+    assert snapshot is not None
+    assert snapshot.reference_date == reference_date().isoformat()
+    assert len(snapshot.configuration_fingerprint) == 64
+    assert len(snapshot.semantic_graph_fingerprint) == 64
+    assert len(snapshot.representation_fingerprint) == 64
```
