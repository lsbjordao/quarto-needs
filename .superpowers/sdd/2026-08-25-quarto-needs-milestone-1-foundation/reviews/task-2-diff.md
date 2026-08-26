# Task 2 review package (no Git metadata)

## Changed-file inventory
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/src/quarto_needs/model.py and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/src/quarto_needs/model.py differ
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/src/quarto_needs/parser.py and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/src/quarto_needs/parser.py differ
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/src/quarto_needs: relations.py
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/tests/test_parser.py and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/tests/test_parser.py differ
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/tests: test_relations.py

## Full diff
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/src/quarto_needs/model.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/src/quarto_needs/model.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/src/quarto_needs/model.py	2026-08-24 23:41:30.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/src/quarto_needs/model.py	2026-08-25 09:21:11.416622063 -0300
@@ -18,6 +18,16 @@
     source: str
     target: str
     attributes: dict[str, Any] = field(default_factory=dict)
+    authored_name: str | None = None
+
+
+def relation_to_v1_dict(relation: Relation) -> dict[str, Any]:
+    return {
+        "type": relation.type,
+        "source": relation.source,
+        "target": relation.target,
+        "attributes": relation.attributes,
+    }
 
 
 @dataclass(slots=True)
@@ -33,8 +43,17 @@
     source: SourceLocation | None = None
 
     def to_dict(self) -> dict[str, Any]:
-        data = asdict(self)
-        return data
+        return {
+            "id": self.id,
+            "type": self.type,
+            "title": self.title,
+            "status": self.status,
+            "body": self.body,
+            "rationale": self.rationale,
+            "attributes": self.attributes,
+            "relations": [relation_to_v1_dict(relation) for relation in self.relations],
+            "source": asdict(self.source) if self.source else None,
+        }
 
     @property
     def href(self) -> str:
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/src/quarto_needs/parser.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/src/quarto_needs/parser.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/src/quarto_needs/parser.py	2026-08-24 23:41:30.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/src/quarto_needs/parser.py	2026-08-25 09:21:11.416622063 -0300
@@ -5,6 +5,7 @@
 from typing import Iterable
 
 from .model import EngineeringObject, Relation, SourceLocation
+from .relations import DEFAULT_RELATION_CATALOG
 
 OPEN_RE = re.compile(r'^\s*:::\s*\{\.need\s+#(?P<id>[A-Za-z0-9_.:-]+)(?P<attrs>[^}]*)\}\s*$')
 ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)=(?:"([^"]*)"|\'([^\']*)\'|([^\s]+))')
@@ -12,13 +13,7 @@
 META_RE = re.compile(r'^(?P<key>[A-Za-z0-9_-]+):\s*(?P<value>.*)$')
 LIST_RE = re.compile(r'^\s*-\s+(?P<value>.+?)\s*$')
 
-RELATION_KEYS = {
-    "derives-from", "derived-from", "refines", "decomposes", "depends-on",
-    "conflicts-with", "constrains", "implements", "implemented-by",
-    "verified-by", "validated-by", "mitigates", "justified-by", "evidenced-by",
-    "references",
-}
-ALIASES = {"derived-from": "derives-from", "implemented-by": "implemented-by", "references": "references"}
+RELATION_KEYS = set(DEFAULT_RELATION_CATALOG.names)
 
 
 def _parse_attrs(raw: str) -> dict[str, str]:
@@ -110,9 +105,19 @@
             if key in {"type", "status"}:
                 continue
             if key in RELATION_KEYS:
-                rel_type = ALIASES.get(key, key)
+                kind = DEFAULT_RELATION_CATALOG.resolve(key)
                 targets = value if isinstance(value, list) else [value]
-                relations.extend(Relation(rel_type, need_id, str(t)) for t in targets if str(t).strip())
+                relations.extend(
+                    Relation(
+                        type=kind.v1_name,
+                        source=need_id,
+                        target=str(target),
+                        attributes={},
+                        authored_name=key,
+                    )
+                    for target in targets
+                    if str(target).strip()
+                )
             else:
                 attributes[key] = value
 
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/src/quarto_needs/relations.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/src/quarto_needs/relations.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/src/quarto_needs/relations.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/src/quarto_needs/relations.py	2026-08-25 09:21:11.412622079 -0300
@@ -0,0 +1,75 @@
+from __future__ import annotations
+
+from dataclasses import dataclass
+from types import MappingProxyType
+from typing import Literal, Mapping
+
+ImpactDirection = Literal["source_to_target", "target_to_source", "both", "none"]
+
+
+@dataclass(frozen=True, slots=True)
+class RelationKind:
+    authored_name: str
+    catalog_name: str
+    v1_name: str
+    semantic_family: str
+    direct_label: str
+    inverse_label: str
+    source_role: str
+    target_role: str
+    impact_direction: ImpactDirection
+    public: bool = True
+    allowed_source_types: tuple[str, ...] = ()
+    allowed_target_types: tuple[str, ...] = ()
+    minimum_per_source: int | None = None
+    maximum_per_source: int | None = None
+
+
+@dataclass(frozen=True, slots=True)
+class RelationCatalog:
+    version: str
+    entries: Mapping[str, RelationKind]
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))
+
+    @classmethod
+    def create(cls, version: str, entries: tuple[RelationKind, ...]) -> "RelationCatalog":
+        by_name = {entry.authored_name: entry for entry in entries}
+        if len(by_name) != len(entries):
+            raise ValueError("Relation catalog contains duplicate authored names")
+        return cls(version=version, entries=MappingProxyType(by_name))
+
+    @property
+    def names(self) -> tuple[str, ...]:
+        return tuple(sorted(self.entries))
+
+    def resolve(self, authored_name: str) -> RelationKind:
+        try:
+            return self.entries[authored_name]
+        except KeyError as error:
+            raise ValueError(f"Unknown relation type: {authored_name}") from error
+
+
+DEFAULT_RELATION_CATALOG = RelationCatalog.create(
+    "1",
+    (
+        RelationKind("derives-from", "derives-from", "derives-from", "derivation", "Derives from", "Source for", "derived", "source", "target_to_source"),
+        RelationKind("derived-from", "derives-from", "derives-from", "derivation", "Derives from", "Source for", "derived", "source", "target_to_source"),
+        RelationKind("refines", "refines", "refines", "refinement", "Refines", "Refined by", "refinement", "subject", "target_to_source"),
+        RelationKind("decomposes", "decomposes", "decomposes", "decomposition", "Decomposes", "Part of", "whole", "part", "none"),
+        RelationKind("depends-on", "depends-on", "depends-on", "dependency", "Depends on", "Depended on by", "dependent", "dependency", "target_to_source"),
+        RelationKind("conflicts-with", "conflicts-with", "conflicts-with", "conflict", "Conflicts with", "Conflicts with", "subject", "subject", "both"),
+        RelationKind("constrains", "constrains", "constrains", "constraint", "Constrains", "Constrained by", "constraint", "subject", "none"),
+        RelationKind("implements", "implements", "implements", "implementation", "Implements", "Implemented by", "implementation-artifact", "requirement", "target_to_source"),
+        RelationKind("implemented-by", "implemented-by", "implemented-by", "implementation", "Implemented by", "Implements", "requirement", "implementation-artifact", "source_to_target"),
+        RelationKind("verifies", "verifies", "verifies", "verification", "Verifies", "Verified by", "test", "requirement", "target_to_source"),
+        RelationKind("verified-by", "verified-by", "verified-by", "verification", "Verified by", "Verifies", "requirement", "test", "source_to_target"),
+        RelationKind("validated-by", "validated-by", "validated-by", "verification", "Validated by", "Validates", "requirement", "test", "source_to_target"),
+        RelationKind("mitigates", "mitigates", "mitigates", "mitigation", "Mitigates", "Mitigated by", "mitigation", "risk", "target_to_source"),
+        RelationKind("justified-by", "justified-by", "justified-by", "justification", "Justified by", "Justifies", "subject", "justification", "none"),
+        RelationKind("evidences", "evidences", "evidences", "evidence", "Evidences", "Evidenced by", "evidence", "test", "target_to_source"),
+        RelationKind("evidenced-by", "evidenced-by", "evidenced-by", "evidence", "Evidenced by", "Evidences", "test", "evidence", "source_to_target"),
+        RelationKind("references", "references", "references", "reference", "References", "Referenced by", "source", "target", "none"),
+    ),
+)
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/tests/test_parser.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/tests/test_parser.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/tests/test_parser.py	2026-08-24 23:41:30.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/tests/test_parser.py	2026-08-25 09:20:24.628799388 -0300
@@ -19,3 +19,24 @@
     qmd.write_text('''::: {.need #SYS-REQ-001 type="system-requirement" verified-by="TC-404"}\n## Login\nText.\n:::\n''', encoding="utf-8")
     findings = validate(parse_qmd(qmd, tmp_path))
     assert any(f.code == "REQ005" for f in findings)
+
+
+def test_parser_accepts_catalog_only_relation_names(tmp_path: Path):
+    qmd = tmp_path / "req.qmd"
+    qmd.write_text(
+        '''::: {.need #TC-1 type="test-case"}
+verifies: REQ-1
+evidences: EVD-1
+## Login test
+Text.
+:::
+''',
+        encoding="utf-8",
+    )
+
+    relations = parse_qmd(qmd, tmp_path)[0].relations
+
+    assert [(relation.type, relation.authored_name, relation.target) for relation in relations] == [
+        ("verifies", "verifies", "REQ-1"),
+        ("evidences", "evidences", "EVD-1"),
+    ]
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/tests/test_relations.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/tests/test_relations.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-before/tests/test_relations.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-2-after/tests/test_relations.py	2026-08-25 09:20:24.628799388 -0300
@@ -0,0 +1,45 @@
+from pathlib import Path
+
+from quarto_needs.parser import parse_qmd
+from quarto_needs.relations import DEFAULT_RELATION_CATALOG
+
+
+def test_default_catalog_covers_every_legacy_and_inverse_authoring_name() -> None:
+    assert DEFAULT_RELATION_CATALOG.names == (
+        "conflicts-with", "constrains", "decomposes", "depends-on",
+        "derived-from", "derives-from", "evidenced-by", "evidences",
+        "implemented-by", "implements", "justified-by", "mitigates",
+        "references", "refines", "validated-by", "verified-by", "verifies",
+    )
+
+
+def test_inverse_authoring_forms_share_semantic_families_and_swap_roles() -> None:
+    implements = DEFAULT_RELATION_CATALOG.resolve("implements")
+    implemented_by = DEFAULT_RELATION_CATALOG.resolve("implemented-by")
+
+    assert implements.semantic_family == implemented_by.semantic_family == "implementation"
+    assert (implements.source_role, implements.target_role) == (
+        "implementation-artifact",
+        "requirement",
+    )
+    assert (implemented_by.source_role, implemented_by.target_role) == (
+        "requirement",
+        "implementation-artifact",
+    )
+    assert implements.inverse_label == implemented_by.direct_label
+
+
+def test_derived_from_preserves_authored_name_but_keeps_v1_normalization(tmp_path: Path) -> None:
+    source = tmp_path / "requirements.qmd"
+    source.write_text(
+        "::: {.need #REQ-2 type=system-requirement}\n"
+        "derived-from: REQ-1\n\n"
+        "## Derived requirement\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+    relation = parse_qmd(source)[0].relations[0]
+
+    assert relation.authored_name == "derived-from"
+    assert relation.type == "derives-from"
