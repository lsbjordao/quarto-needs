# Task 5 review package (no Git metadata)

## Changed-file inventory
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/src/quarto_needs: analysis.py
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after: tests

## Full diff
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/src/quarto_needs/analysis.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/src/quarto_needs/analysis.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/src/quarto_needs/analysis.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/src/quarto_needs/analysis.py	2026-08-25 09:54:14.691193129 -0300
@@ -0,0 +1,312 @@
+from __future__ import annotations
+
+import json
+from collections.abc import Iterable
+from pathlib import Path
+from typing import cast
+
+import quarto_needs
+
+from .diagnostics import Finding
+from .model import EngineeringObject, Relation, SourceLocation
+from .parser import parse_project_declarations
+from .relations import DEFAULT_RELATION_CATALOG
+from .snapshot import (
+    AnalysisResult,
+    AnalysisSnapshot,
+    DeclarationBatch,
+    LocationRecord,
+    ObjectDeclaration,
+    ObjectRecord,
+    RelationRecord,
+    RelationToken,
+    thaw_json,
+)
+from .validation import finding_key, validate
+
+
+STRUCTURAL_ERROR_CODES = frozenset(
+    {"QND001", "QND002", "REQ004", "REQ005", "REQ007"}
+)
+
+
+def text_key(value: str) -> tuple[str, str]:
+    return value.casefold(), value
+
+
+def object_key(item: ObjectRecord) -> tuple[object, ...]:
+    location = item.locations[0] if item.locations else None
+    return (
+        *text_key(item.id),
+        location.file.casefold() if location else "",
+        location.file if location else "",
+        location.line if location else 0,
+    )
+
+
+def relation_key(item: RelationRecord) -> tuple[object, ...]:
+    attributes = json.dumps(
+        thaw_json(item.attributes),
+        ensure_ascii=False,
+        sort_keys=True,
+        separators=(",", ":"),
+    )
+    return (
+        *text_key(item.source),
+        item.v1_name,
+        *text_key(item.target),
+        item.authored_name,
+        attributes,
+    )
+
+
+def legacy_coverage(
+    objects: tuple[ObjectRecord, ...],
+    relations: tuple[RelationRecord, ...],
+) -> dict[str, object]:
+    requirements = [item for item in objects if item.type.endswith("requirement")]
+    outgoing = {item.id: [] for item in objects}
+    for relation in relations:
+        outgoing.setdefault(relation.source, []).append(relation)
+    implemented = [
+        item
+        for item in requirements
+        if any(
+            relation.v1_name in {"implements", "implemented-by"}
+            for relation in outgoing[item.id]
+        )
+    ]
+    verified = [
+        item
+        for item in requirements
+        if any(
+            relation.v1_name in {"verified-by", "validated-by"}
+            for relation in outgoing[item.id]
+        )
+    ]
+    total = len(requirements)
+    return {
+        "requirements": total,
+        "approved": sum(item.status == "approved" for item in requirements),
+        "implemented": len(implemented),
+        "verified": len(verified),
+        "implementation_coverage": (
+            round(100 * len(implemented) / total, 1) if total else 100.0
+        ),
+        "verification_coverage": (
+            round(100 * len(verified) / total, 1) if total else 100.0
+        ),
+    }
+
+
+def _location(source: SourceLocation | None) -> LocationRecord | None:
+    if source is None:
+        return None
+    return LocationRecord(source.file, source.line, source.anchor)
+
+
+def _declaration(item: EngineeringObject) -> ObjectDeclaration:
+    location = _location(item.source)
+    return ObjectDeclaration(
+        id=item.id,
+        type=item.type,
+        title=item.title,
+        status=item.status,
+        body=item.body,
+        rationale=item.rationale,
+        attributes=item.attributes,
+        relations=tuple(
+            RelationToken(
+                relation.authored_name or relation.type,
+                relation.target,
+                relation.attributes,
+                location,
+            )
+            for relation in item.relations
+        ),
+        location=location,
+    )
+
+
+def _legacy_objects(
+    declarations: tuple[ObjectDeclaration, ...],
+) -> tuple[list[EngineeringObject], list[Finding]]:
+    objects: list[EngineeringObject] = []
+    unsupported: list[Finding] = []
+    for declaration in declarations:
+        relations: list[Relation] = []
+        for token in declaration.relations:
+            try:
+                relation_type = DEFAULT_RELATION_CATALOG.resolve(
+                    token.authored_name
+                ).v1_name
+            except ValueError:
+                relation_type = token.authored_name
+                unsupported.append(
+                    Finding(
+                        "REQ007",
+                        "error",
+                        "Unsupported relation type "
+                        f"{token.authored_name} on {declaration.id}",
+                        declaration.id,
+                        token.location or declaration.location,
+                    )
+                )
+            relations.append(
+                Relation(
+                    relation_type,
+                    declaration.id,
+                    token.target,
+                    cast(dict[str, object], thaw_json(token.attributes)),
+                    token.authored_name,
+                )
+            )
+        source = (
+            SourceLocation(
+                declaration.location.file,
+                declaration.location.line,
+                declaration.location.anchor,
+            )
+            if declaration.location is not None
+            else None
+        )
+        objects.append(
+            EngineeringObject(
+                id=declaration.id,
+                type=declaration.type,
+                title=declaration.title,
+                status=declaration.status,
+                body=declaration.body,
+                rationale=declaration.rationale,
+                attributes=cast(
+                    dict[str, object], thaw_json(declaration.attributes)
+                ),
+                relations=relations,
+                source=source,
+            )
+        )
+    return objects, unsupported
+
+
+def _merge_findings(*groups: Iterable[Finding]) -> tuple[Finding, ...]:
+    merged: list[Finding] = []
+    for group in groups:
+        for finding in group:
+            if finding not in merged:
+                merged.append(finding)
+    return tuple(sorted(merged, key=finding_key))
+
+
+def _records(
+    declarations: tuple[ObjectDeclaration, ...],
+) -> tuple[tuple[ObjectRecord, ...], tuple[RelationRecord, ...]]:
+    objects = tuple(
+        sorted(
+            (
+                ObjectRecord(
+                    id=declaration.id,
+                    type=declaration.type,
+                    title=declaration.title,
+                    status=declaration.status,
+                    body=declaration.body,
+                    rationale=declaration.rationale,
+                    attributes=declaration.attributes,
+                    locations=(declaration.location,)
+                    if declaration.location is not None
+                    else (),
+                )
+                for declaration in declarations
+            ),
+            key=object_key,
+        )
+    )
+    relations: list[RelationRecord] = []
+    for declaration in declarations:
+        for token in declaration.relations:
+            kind = DEFAULT_RELATION_CATALOG.resolve(token.authored_name)
+            relations.append(
+                RelationRecord(
+                    source=declaration.id,
+                    authored_name=token.authored_name,
+                    catalog_name=kind.catalog_name,
+                    v1_name=kind.v1_name,
+                    target=token.target,
+                    semantic_family=kind.semantic_family,
+                    source_role=kind.source_role,
+                    target_role=kind.target_role,
+                    impact_direction=kind.impact_direction,
+                    attributes=token.attributes,
+                    provenance=(token.location,)
+                    if token.location is not None
+                    else (),
+                )
+            )
+    return objects, tuple(sorted(relations, key=relation_key))
+
+
+def _analyze_batch(
+    batch: DeclarationBatch,
+    reported_findings: Iterable[Finding] | None = None,
+) -> AnalysisResult:
+    declarations = batch.declarations
+    legacy_objects, unsupported = _legacy_objects(declarations)
+    compatibility_findings = validate(legacy_objects)
+    if reported_findings is None:
+        selected_findings = compatibility_findings
+    else:
+        selected_findings = [
+            finding
+            for finding in compatibility_findings
+            if finding.code in STRUCTURAL_ERROR_CODES
+        ]
+    findings = _merge_findings(
+        batch.findings,
+        () if reported_findings is None else reported_findings,
+        selected_findings,
+        unsupported,
+    )
+    if any(finding.code in STRUCTURAL_ERROR_CODES for finding in findings):
+        return AnalysisResult(declarations, findings, None)
+
+    objects, relations = _records(declarations)
+    objects_by_id = {item.id: item for item in objects}
+    outgoing: dict[str, tuple[RelationRecord, ...]] = {}
+    incoming: dict[str, tuple[RelationRecord, ...]] = {}
+    for item in objects:
+        outgoing[item.id] = tuple(
+            relation for relation in relations if relation.source == item.id
+        )
+        incoming[item.id] = tuple(
+            relation for relation in relations if relation.target == item.id
+        )
+    snapshot = AnalysisSnapshot(
+        objects=objects,
+        relations=relations,
+        findings=findings,
+        metrics=legacy_coverage(objects, relations),
+        objects_by_id=objects_by_id,
+        outgoing=outgoing,
+        incoming=incoming,
+        generator_name="quarto-needs",
+        generator_version=quarto_needs.__version__,
+        relation_catalog_version=DEFAULT_RELATION_CATALOG.version,
+    )
+    return AnalysisResult(declarations, findings, snapshot)
+
+
+def analyze_project(
+    root: Path,
+    files: Iterable[Path] | None = None,
+) -> AnalysisResult:
+    return _analyze_batch(parse_project_declarations(root, files))
+
+
+def analyze_objects(
+    objects: Iterable[EngineeringObject],
+    reported_findings: Iterable[Finding] | None = None,
+) -> AnalysisResult:
+    declarations = tuple(_declaration(item) for item in objects)
+    return _analyze_batch(
+        DeclarationBatch(declarations, ()),
+        reported_findings,
+    )
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/tests/fixtures/canonical/a-tests.qmd .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/tests/fixtures/canonical/a-tests.qmd
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/tests/fixtures/canonical/a-tests.qmd	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/tests/fixtures/canonical/a-tests.qmd	2026-08-25 09:51:47.927607683 -0300
@@ -0,0 +1,8 @@
+::: {.need #Z-TC-001 type=test-case status=passed}
+priority: medium
+tags: verification; unicode
+
+## Verifies autenticação
+
+The test passes for valid credentials.
+:::
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/tests/fixtures/canonical/invalid-duplicates.qmd .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/tests/fixtures/canonical/invalid-duplicates.qmd
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/tests/fixtures/canonical/invalid-duplicates.qmd	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/tests/fixtures/canonical/invalid-duplicates.qmd	2026-08-25 09:51:47.927607683 -0300
@@ -0,0 +1,14 @@
+::: {.need #DUP-1 type=functional-requirement}
+references: UNKNOWN-1
+
+## First duplicate
+
+The first declaration references an unknown object.
+:::
+
+::: {.need #DUP-1 type=functional-requirement}
+
+## Second duplicate
+
+The second declaration repeats the identifier.
+:::
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/tests/fixtures/canonical/z-requirements.qmd .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/tests/fixtures/canonical/z-requirements.qmd
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/tests/fixtures/canonical/z-requirements.qmd	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/tests/fixtures/canonical/z-requirements.qmd	2026-08-25 09:51:47.927607683 -0300
@@ -0,0 +1,22 @@
+::: {.need #M-NEED-001 type=stakeholder-need status=approved}
+priority: medium
+tags: identity; access
+
+## Administrators need secure access
+
+Administrative access must be protected.
+:::
+
+::: {.need #A-REQ-001 type=functional-requirement status=approved}
+priority: high
+tags:
+  - authentication
+  - security
+derived-from: M-NEED-001
+verified-by: Z-TC-001
+rationale: Prevent unauthorized administrative access.
+
+## Autenticação forte
+
+The service shall authenticate administrators.
+:::
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/tests/test_analysis.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/tests/test_analysis.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-before/tests/test_analysis.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-5-after/tests/test_analysis.py	2026-08-25 09:56:44.186763787 -0300
@@ -0,0 +1,200 @@
+from collections import Counter
+from pathlib import Path
+
+import pytest
+import quarto_needs
+
+from quarto_needs.analysis import analyze_objects, analyze_project
+from quarto_needs.diagnostics import Finding
+from quarto_needs.model import EngineeringObject, Relation
+from quarto_needs.relations import DEFAULT_RELATION_CATALOG
+
+
+ROOT = Path(__file__).resolve().parents[1]
+
+
+def test_analysis_snapshot_is_sorted_indexed_and_deeply_immutable() -> None:
+    root = ROOT / "tests/fixtures/canonical"
+    result = analyze_project(
+        root,
+        files=[root / "z-requirements.qmd", root / "a-tests.qmd"],
+    )
+
+    assert result.valid is True
+    assert result.snapshot is not None
+    assert [item.id for item in result.snapshot.objects] == [
+        "A-REQ-001",
+        "M-NEED-001",
+        "Z-TC-001",
+    ]
+    assert [
+        (item.source, item.authored_name, item.target)
+        for item in result.snapshot.relations
+    ] == [
+        ("A-REQ-001", "derived-from", "M-NEED-001"),
+        ("A-REQ-001", "verified-by", "Z-TC-001"),
+    ]
+    assert result.snapshot.relations[0].v1_name == "derives-from"
+    assert tuple(
+        item.target for item in result.snapshot.outgoing["A-REQ-001"]
+    ) == ("M-NEED-001", "Z-TC-001")
+    assert tuple(
+        item.source for item in result.snapshot.incoming["Z-TC-001"]
+    ) == ("A-REQ-001",)
+    assert result.snapshot.metrics == {
+        "requirements": 1,
+        "approved": 1,
+        "implemented": 0,
+        "verified": 1,
+        "implementation_coverage": 0.0,
+        "verification_coverage": 100.0,
+    }
+    assert result.snapshot.generator_name == "quarto-needs"
+    assert result.snapshot.generator_version == quarto_needs.__version__
+    assert (
+        result.snapshot.relation_catalog_version
+        == DEFAULT_RELATION_CATALOG.version
+    )
+    with pytest.raises(TypeError):
+        result.snapshot.objects_by_id["NEW"] = result.snapshot.objects[0]
+    with pytest.raises(TypeError):
+        result.snapshot.metrics["requirements"] = 0
+
+
+def test_structurally_invalid_analysis_has_no_snapshot_and_keeps_all_declarations() -> None:
+    source = ROOT / "tests/fixtures/canonical/invalid-duplicates.qmd"
+
+    result = analyze_project(source.parent, files=[source])
+
+    assert result.valid is False
+    assert result.snapshot is None
+    assert [item.id for item in result.declarations].count("DUP-1") == 2
+    assert [
+        (item.code, item.object_id)
+        for item in result.findings
+        if item.severity == "error"
+    ] == [
+        ("REQ004", "DUP-1"),
+        ("REQ005", "DUP-1"),
+    ]
+
+
+def test_analysis_is_independent_of_explicit_file_order() -> None:
+    root = ROOT / "tests/fixtures/canonical"
+
+    forward = analyze_project(
+        root,
+        files=[root / "a-tests.qmd", root / "z-requirements.qmd"],
+    )
+    reverse = analyze_project(
+        root,
+        files=[root / "z-requirements.qmd", root / "a-tests.qmd"],
+    )
+
+    assert forward.snapshot == reverse.snapshot
+
+
+def test_analysis_reads_each_selected_source_once(
+    monkeypatch: pytest.MonkeyPatch,
+) -> None:
+    root = ROOT / "tests/fixtures/canonical"
+    selected = {root / "a-tests.qmd", root / "z-requirements.qmd"}
+    resolved_selected = {item.resolve() for item in selected}
+    reads: Counter[Path] = Counter()
+    original = Path.read_text
+
+    def counted(path: Path, *args: object, **kwargs: object) -> str:
+        resolved = path.resolve()
+        if resolved in resolved_selected:
+            reads[resolved] += 1
+        return original(path, *args, **kwargs)
+
+    monkeypatch.setattr(Path, "read_text", counted)
+
+    result = analyze_project(root, files=selected)
+
+    assert result.snapshot is not None
+    assert reads == Counter({item.resolve(): 1 for item in selected})
+
+
+def test_source_less_legacy_object_keeps_empty_location_and_provenance() -> None:
+    legacy = EngineeringObject(
+        "REQ-1",
+        "functional-requirement",
+        "Source-less",
+        relations=[Relation("references", "REQ-1", "REQ-1")],
+    )
+
+    result = analyze_objects([legacy])
+
+    assert result.snapshot is not None
+    assert result.declarations[0].location is None
+    assert result.snapshot.objects[0].locations == ()
+    assert result.snapshot.relations[0].provenance == ()
+
+
+@pytest.mark.parametrize(
+    ("contents", "expected_code"),
+    [
+        ("::: {.need #BROKEN}\n## Unclosed\n", "QND001"),
+        (
+            "::: {.need #EMPTY}\n"
+            "verified-by:\n\n"
+            "## Empty relation\n"
+            ":::\n",
+            "QND002",
+        ),
+    ],
+)
+def test_parser_structural_findings_suppress_snapshots(
+    tmp_path: Path,
+    contents: str,
+    expected_code: str,
+) -> None:
+    source = tmp_path / "broken.qmd"
+    source.write_text(contents, encoding="utf-8")
+
+    result = analyze_project(tmp_path, files=[source])
+
+    assert result.snapshot is None
+    assert [item.code for item in result.findings] == [expected_code]
+    assert result.findings[0].location is not None
+    assert result.findings[0].location.file == "broken.qmd"
+
+
+def test_reported_findings_do_not_bypass_structural_validation() -> None:
+    first = EngineeringObject(
+        "DUP-1",
+        "need",
+        "First",
+        relations=[Relation("references", "DUP-1", "UNKNOWN-1")],
+    )
+    second = EngineeringObject("DUP-1", "need", "Second")
+
+    result = analyze_objects([first, second], reported_findings=[])
+
+    assert result.snapshot is None
+    assert [(item.code, item.object_id) for item in result.findings] == [
+        ("REQ004", "DUP-1"),
+        ("REQ005", "DUP-1"),
+    ]
+
+
+def test_unknown_legacy_relation_becomes_structural_finding() -> None:
+    legacy = EngineeringObject(
+        "REQ-1",
+        "need",
+        "Unsupported relation",
+        relations=[Relation("custom-link", "REQ-1", "REQ-1")],
+    )
+
+    result = analyze_objects(
+        [legacy],
+        reported_findings=[Finding("INFO001", "info", "Preserved")],
+    )
+
+    assert result.snapshot is None
+    assert [(item.code, item.message) for item in result.findings] == [
+        ("REQ007", "Unsupported relation type custom-link on REQ-1"),
+        ("INFO001", "Preserved"),
+    ]
