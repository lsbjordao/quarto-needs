# Review package

Snapshot range: `task-3-after` -> `task-3-fix1`

## Files changed (3)

- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `examples/book/.quarto-needs/needs.json`
- `tests/test_fingerprints.py`

## Summary

11 lines added, 1 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-25 21:04:43.613025593 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-25 21:28:57.805047471 -0300
@@ -491,26 +491,30 @@
     moved = make_object(locations=(LocationRecord("b.qmd", 900, "REQ-1"),))
 
     assert fingerprints.object_content_fingerprint(make_object()) == \
         fingerprints.object_content_fingerprint(moved)
 
 
 def test_object_fingerprint_changes_with_every_authored_field() -> None:
     """Each field the spec names must actually participate."""
     original = fingerprints.object_content_fingerprint(make_object())
     for field, value in (
+        ("id", "REQ-2"),
         ("type", "system-requirement"),
         ("title", "Other"),
         ("status", "draft"),
         ("body", "Different body."),
         ("rationale", "Different rationale."),
+        # Vary priority and tags separately so each computed property is proven
+        # to participate on its own.
         ("attributes", {"priority": "low", "tags": "security"}),
+        ("attributes", {"priority": "high", "tags": "authentication"}),
     ):
         assert fingerprints.object_content_fingerprint(make_object(**{field: value})) != original, field
 
 
 def test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation() -> None:
     """REQ -verified-by-> TC and TC -verifies-> REQ are one semantic edge."""
     forward = make_relation()
     inverse = make_relation(
         source="TC-1",
         authored_name="verifies",
@@ -526,20 +530,21 @@
         fingerprints.relation_semantic_fingerprint(inverse)
     assert fingerprints.relation_authored_fingerprint(forward) != \
         fingerprints.relation_authored_fingerprint(inverse)
 
 
 def test_semantic_relation_fingerprint_changes_with_family_and_endpoints() -> None:
     original = fingerprints.relation_semantic_fingerprint(make_relation())
 
     assert fingerprints.relation_semantic_fingerprint(make_relation(semantic_family="evidence")) != original
     assert fingerprints.relation_semantic_fingerprint(make_relation(target="TC-2")) != original
+    assert fingerprints.relation_semantic_fingerprint(make_relation(source="REQ-2")) != original
     assert fingerprints.relation_semantic_fingerprint(make_relation(attributes={"note": "x"})) != original
 
 
 def test_graph_fingerprint_is_order_independent_and_configuration_sensitive() -> None:
     """Reordering declarations is not a change; changing policy is."""
     objects = [make_object(), make_object(id="REQ-2")]
     relations = [make_relation(), make_relation(target="TC-2")]
     configuration = fingerprints.configuration_fingerprint(
         embedded_defaults(), relation_catalog_version="1"
     )
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/examples/book/.quarto-needs/needs.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-fix1/examples/book/.quarto-needs/needs.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/examples/book/.quarto-needs/needs.json	2026-08-25 21:21:01.634251503 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-fix1/examples/book/.quarto-needs/needs.json	2026-08-26 00:44:11.399010545 -0300
@@ -736,21 +736,21 @@
             "passed": true,
             "scope": "project",
             "threshold": 0
           }
         ],
         "generator": {
           "name": "quarto-needs",
           "version": "0.1.0"
         },
         "profile": "strict",
-        "referenceDate": "2026-08-25",
+        "referenceDate": "2026-08-26",
         "schemaVersion": "1",
         "scopes": {
           "approved-high-unverified": {
             "breakdowns": {
               "priority": {},
               "status": {},
               "type": {}
             },
             "coverage": {
               "evidence": {
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/tests/test_fingerprints.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-fix1/tests/test_fingerprints.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-after/tests/test_fingerprints.py	2026-08-25 21:16:48.134892483 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-3-fix1/tests/test_fingerprints.py	2026-08-26 00:49:44.521332899 -0300
@@ -43,26 +43,30 @@
     moved = make_object(locations=(LocationRecord("b.qmd", 900, "REQ-1"),))
 
     assert fingerprints.object_content_fingerprint(make_object()) == \
         fingerprints.object_content_fingerprint(moved)
 
 
 def test_object_fingerprint_changes_with_every_authored_field() -> None:
     """Each field the spec names must actually participate."""
     original = fingerprints.object_content_fingerprint(make_object())
     for field, value in (
+        ("id", "REQ-2"),
         ("type", "system-requirement"),
         ("title", "Other"),
         ("status", "draft"),
         ("body", "Different body."),
         ("rationale", "Different rationale."),
+        # Vary priority and tags separately so each computed property is proven
+        # to participate on its own.
         ("attributes", {"priority": "low", "tags": "security"}),
+        ("attributes", {"priority": "high", "tags": "authentication"}),
     ):
         assert fingerprints.object_content_fingerprint(make_object(**{field: value})) != original, field
 
 
 def test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation() -> None:
     """REQ -verified-by-> TC and TC -verifies-> REQ are one semantic edge."""
     forward = make_relation()
     inverse = make_relation(
         source="TC-1",
         authored_name="verifies",
@@ -78,20 +82,21 @@
         fingerprints.relation_semantic_fingerprint(inverse)
     assert fingerprints.relation_authored_fingerprint(forward) != \
         fingerprints.relation_authored_fingerprint(inverse)
 
 
 def test_semantic_relation_fingerprint_changes_with_family_and_endpoints() -> None:
     original = fingerprints.relation_semantic_fingerprint(make_relation())
 
     assert fingerprints.relation_semantic_fingerprint(make_relation(semantic_family="evidence")) != original
     assert fingerprints.relation_semantic_fingerprint(make_relation(target="TC-2")) != original
+    assert fingerprints.relation_semantic_fingerprint(make_relation(source="REQ-2")) != original
     assert fingerprints.relation_semantic_fingerprint(make_relation(attributes={"note": "x"})) != original
 
 
 def test_graph_fingerprint_is_order_independent_and_configuration_sensitive() -> None:
     """Reordering declarations is not a change; changing policy is."""
     objects = [make_object(), make_object(id="REQ-2")]
     relations = [make_relation(), make_relation(target="TC-2")]
     configuration = fingerprints.configuration_fingerprint(
         embedded_defaults(), relation_catalog_version="1"
     )
```
