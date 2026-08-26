# Task 3 review package (no Git metadata)

## Changed-file inventory
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs: diagnostics.py
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/parser.py and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/parser.py differ
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs: snapshot.py
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/validation.py and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/validation.py differ
Files .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/tests/test_parser.py and .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/tests/test_parser.py differ
Only in .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/tests: test_snapshot.py

## Full diff
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/diagnostics.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/diagnostics.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/diagnostics.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/diagnostics.py	2026-08-25 09:32:13.102541926 -0300
@@ -0,0 +1,36 @@
+from __future__ import annotations
+
+from dataclasses import dataclass, field
+from typing import Mapping
+
+from .snapshot import LocationRecord, freeze_json, thaw_json
+
+
+@dataclass(frozen=True, slots=True)
+class Finding:
+    code: str
+    severity: str
+    message: str
+    object_id: str | None = None
+    location: LocationRecord | None = None
+    properties: Mapping[str, object] = field(default_factory=dict)
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "properties", freeze_json(dict(self.properties)))
+
+    def to_dict(self) -> dict[str, object]:
+        result: dict[str, object] = {
+            "code": self.code,
+            "severity": self.severity,
+            "message": self.message,
+            "object_id": self.object_id,
+        }
+        if self.location is not None:
+            result["location"] = {
+                "file": self.location.file,
+                "line": self.location.line,
+                "anchor": self.location.anchor,
+            }
+        if self.properties:
+            result["properties"] = thaw_json(self.properties)
+        return result
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/parser.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/parser.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/parser.py	2026-08-25 09:21:11.416622063 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/parser.py	2026-08-25 09:33:07.162428657 -0300
@@ -2,12 +2,22 @@
 
 import re
 from pathlib import Path
-from typing import Iterable
+from typing import Iterable, cast
 
+from .diagnostics import Finding
 from .model import EngineeringObject, Relation, SourceLocation
 from .relations import DEFAULT_RELATION_CATALOG
-
-OPEN_RE = re.compile(r'^\s*:::\s*\{\.need\s+#(?P<id>[A-Za-z0-9_.:-]+)(?P<attrs>[^}]*)\}\s*$')
+from .snapshot import (
+    DeclarationBatch,
+    LocationRecord,
+    ObjectDeclaration,
+    RelationToken,
+    thaw_json,
+)
+
+OPEN_RE = re.compile(
+    r'^\s*:::\s*\{\.need\s+#(?P<id>[A-Za-z0-9_.:-]+)(?P<attrs>[^}]*)\}\s*$'
+)
 ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)=(?:"([^"]*)"|\'([^\']*)\'|([^\s]+))')
 HEADING_RE = re.compile(r'^##+\s+(?P<title>.+?)\s*$')
 META_RE = re.compile(r'^(?P<key>[A-Za-z0-9_-]+):\s*(?P<value>.*)$')
@@ -18,19 +28,19 @@
 
 def _parse_attrs(raw: str) -> dict[str, str]:
     out: dict[str, str] = {}
-    for m in ATTR_RE.finditer(raw):
-        out[m.group(1)] = next(v for v in m.groups()[1:] if v is not None)
+    for match in ATTR_RE.finditer(raw):
+        out[match.group(1)] = next(
+            value for value in match.groups()[1:] if value is not None
+        )
     return out
 
 
-def _collect_metadata(lines: list[str]) -> tuple[dict[str, object], int]:
-    """Parse the simple YAML-like preamble used inside a .need block.
-
-    Supports scalar values and lists of scalar values. The parser deliberately
-    stays conservative; richer authoring can be added later without making the
-    Quarto filter the canonical parser.
-    """
+def _collect_metadata(
+    lines: list[str],
+) -> tuple[dict[str, object], dict[str, int], int]:
+    """Parse the simple YAML-like preamble used inside a .need block."""
     meta: dict[str, object] = {}
+    offsets: dict[str, int] = {}
     i = 0
     while i < len(lines):
         line = lines[i]
@@ -39,10 +49,11 @@
             continue
         if HEADING_RE.match(line):
             break
-        m = META_RE.match(line)
-        if not m:
+        match = META_RE.match(line)
+        if not match:
             break
-        key, value = m.group("key"), m.group("value").strip()
+        key, value = match.group("key"), match.group("value").strip()
+        offsets[key] = i
         if value:
             meta[key] = value
             i += 1
@@ -50,45 +61,71 @@
         values: list[str] = []
         j = i + 1
         while j < len(lines):
-            lm = LIST_RE.match(lines[j])
-            if not lm:
+            list_match = LIST_RE.match(lines[j])
+            if not list_match:
                 break
-            values.append(lm.group("value"))
+            values.append(list_match.group("value"))
             j += 1
         meta[key] = values
         i = j
-    return meta, i
+    return meta, offsets, i
 
 
-def parse_qmd(path: Path, root: Path | None = None) -> list[EngineeringObject]:
+def _source_file(path: Path, root: Path | None) -> str:
+    relative = path if root is None else path.relative_to(root)
+    return relative.as_posix()
+
+
+def _relation_targets(value: object) -> list[str]:
+    values = value if isinstance(value, list) else [value]
+    return [str(target) for target in values if str(target).strip()]
+
+
+def parse_qmd_declarations(
+    path: Path,
+    root: Path | None = None,
+) -> DeclarationBatch:
     text = path.read_text(encoding="utf-8")
     lines = text.splitlines()
-    objects: list[EngineeringObject] = []
+    declarations: list[ObjectDeclaration] = []
+    findings: list[Finding] = []
+    source_file = _source_file(path, root)
     i = 0
     while i < len(lines):
-        m = OPEN_RE.match(lines[i])
-        if not m:
+        match = OPEN_RE.match(lines[i])
+        if not match:
             i += 1
             continue
         start_line = i + 1
-        need_id = m.group("id")
-        attrs = _parse_attrs(m.group("attrs"))
+        need_id = match.group("id")
+        attrs = _parse_attrs(match.group("attrs"))
         block: list[str] = []
         i += 1
         while i < len(lines) and lines[i].strip() != ":::":
             block.append(lines[i])
             i += 1
-        meta, body_start = _collect_metadata(block)
+        location = LocationRecord(source_file, start_line, need_id)
+        if i == len(lines):
+            findings.append(Finding(
+                "QND001",
+                "error",
+                f"Unclosed .need block: {need_id}",
+                need_id,
+                location,
+            ))
+            break
+
+        meta, meta_offsets, body_start = _collect_metadata(block)
         merged: dict[str, object] = {**attrs, **meta}
 
         title = str(merged.pop("title", "")).strip()
         title_index: int | None = None
         if not title:
-            for idx, line in enumerate(block[body_start:], start=body_start):
-                hm = HEADING_RE.match(line)
-                if hm:
-                    title = hm.group("title").strip()
-                    title_index = idx
+            for index, line in enumerate(block[body_start:], start=body_start):
+                heading_match = HEADING_RE.match(line)
+                if heading_match:
+                    title = heading_match.group("title").strip()
+                    title_index = index
                     break
         if not title:
             title = need_id
@@ -99,30 +136,40 @@
             body_lines = block[title_index + 1:]
         body = "\n".join(body_lines).strip()
 
-        relations: list[Relation] = []
+        relations: list[RelationToken] = []
         attributes: dict[str, object] = {}
         for key, value in merged.items():
             if key in {"type", "status"}:
                 continue
             if key in RELATION_KEYS:
-                kind = DEFAULT_RELATION_CATALOG.resolve(key)
-                targets = value if isinstance(value, list) else [value]
+                targets = _relation_targets(value)
+                if not targets:
+                    findings.append(Finding(
+                        "QND002",
+                        "error",
+                        f"Relation {key} on {need_id} has no targets",
+                        need_id,
+                        location,
+                    ))
+                    continue
+                relation_line = (
+                    start_line + 1 + meta_offsets[key]
+                    if key in meta_offsets
+                    else start_line
+                )
+                relation_location = LocationRecord(
+                    source_file,
+                    relation_line,
+                    need_id,
+                )
                 relations.extend(
-                    Relation(
-                        type=kind.v1_name,
-                        source=need_id,
-                        target=str(target),
-                        attributes={},
-                        authored_name=key,
-                    )
+                    RelationToken(key, target, {}, relation_location)
                     for target in targets
-                    if str(target).strip()
                 )
             else:
                 attributes[key] = value
 
-        relative = path if root is None else path.relative_to(root)
-        obj = EngineeringObject(
+        declarations.append(ObjectDeclaration(
             id=need_id,
             type=str(merged.get("type", "need")),
             title=title,
@@ -130,21 +177,112 @@
             body=body,
             rationale=rationale,
             attributes=attributes,
-            relations=relations,
-            source=SourceLocation(file=relative.as_posix(), line=start_line, anchor=need_id),
-        )
-        objects.append(obj)
+            relations=tuple(relations),
+            location=location,
+        ))
         i += 1
-    return objects
+    return DeclarationBatch(tuple(declarations), tuple(findings))
 
 
-def parse_project(root: Path, files: Iterable[Path] | None = None) -> list[EngineeringObject]:
+def _resolved_project_path(root: Path, path: Path) -> Path:
+    if path.is_absolute():
+        return path.resolve()
+    resolved = path.resolve()
+    if resolved.is_relative_to(root):
+        return resolved
+    return (root / path).resolve()
+
+
+def parse_project_declarations(
+    root: Path,
+    files: Iterable[Path] | None = None,
+) -> DeclarationBatch:
+    resolved_root = root.resolve()
     if files is None:
         files = (
-            p for p in root.rglob("*.qmd")
-            if not any(part.startswith(".") or part.startswith("_") for part in p.relative_to(root).parts[:-1])
+            path
+            for path in resolved_root.rglob("*.qmd")
+            if not any(
+                part.startswith(".") or part.startswith("_")
+                for part in path.relative_to(resolved_root).parts[:-1]
+            )
+        )
+    paths = [_resolved_project_path(resolved_root, Path(path)) for path in files]
+    paths.sort(
+        key=lambda path: (
+            path.relative_to(resolved_root).as_posix().casefold(),
+            path.relative_to(resolved_root).as_posix(),
         )
-    objects: list[EngineeringObject] = []
-    for path in files:
-        objects.extend(parse_qmd(path, root))
+    )
+
+    declarations: list[ObjectDeclaration] = []
+    findings: list[Finding] = []
+    for path in paths:
+        batch = parse_qmd_declarations(path, resolved_root)
+        declarations.extend(batch.declarations)
+        findings.extend(batch.findings)
+    declarations.sort(key=lambda item: (
+        item.location.file.casefold() if item.location else "",
+        item.location.file if item.location else "",
+        item.location.line if item.location else 0,
+        item.id.casefold(),
+        item.id,
+    ))
+    return DeclarationBatch(tuple(declarations), tuple(findings))
+
+
+def _legacy_object(declaration: ObjectDeclaration) -> EngineeringObject:
+    relations: list[Relation] = []
+    for token in declaration.relations:
+        kind = DEFAULT_RELATION_CATALOG.resolve(token.authored_name)
+        relations.append(Relation(
+            type=kind.v1_name,
+            source=declaration.id,
+            target=token.target,
+            attributes=cast(dict[str, object], thaw_json(token.attributes)),
+            authored_name=token.authored_name,
+        ))
+    source = (
+        SourceLocation(
+            declaration.location.file,
+            declaration.location.line,
+            declaration.location.anchor,
+        )
+        if declaration.location is not None
+        else None
+    )
+    return EngineeringObject(
+        id=declaration.id,
+        type=declaration.type,
+        title=declaration.title,
+        status=declaration.status,
+        body=declaration.body,
+        rationale=declaration.rationale,
+        attributes=cast(dict[str, object], thaw_json(declaration.attributes)),
+        relations=relations,
+        source=source,
+    )
+
+
+def parse_qmd(path: Path, root: Path | None = None) -> list[EngineeringObject]:
+    return [
+        _legacy_object(declaration)
+        for declaration in parse_qmd_declarations(path, root).declarations
+    ]
+
+
+def parse_project(
+    root: Path,
+    files: Iterable[Path] | None = None,
+) -> list[EngineeringObject]:
+    objects = [
+        _legacy_object(declaration)
+        for declaration in parse_project_declarations(root, files).declarations
+    ]
+    objects.sort(key=lambda item: (
+        item.id.casefold(),
+        item.id,
+        item.source.file if item.source else "",
+        item.source.line if item.source else 0,
+    ))
     return objects
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/snapshot.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/snapshot.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/snapshot.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/snapshot.py	2026-08-25 09:32:13.098541935 -0300
@@ -0,0 +1,198 @@
+from __future__ import annotations
+
+import math
+from collections.abc import Mapping
+from dataclasses import dataclass
+from types import MappingProxyType
+from typing import TYPE_CHECKING
+
+if TYPE_CHECKING:
+    from .diagnostics import Finding
+
+JsonScalar = str | int | float | bool | None
+
+
+def freeze_json(value: object) -> object:
+    if value is None or isinstance(value, (str, int, bool)):
+        return value
+    if isinstance(value, float):
+        if not math.isfinite(value):
+            raise TypeError("JSON numbers must be finite")
+        return value
+    if isinstance(value, (list, tuple)):
+        return tuple(freeze_json(item) for item in value)
+    if isinstance(value, dict):
+        if not all(isinstance(key, str) for key in value):
+            raise TypeError("JSON object keys must be strings")
+        frozen = {
+            key: freeze_json(value[key])
+            for key in sorted(value, key=lambda item: (item.casefold(), item))
+        }
+        return MappingProxyType(frozen)
+    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")
+
+
+def thaw_json(value: object) -> object:
+    if isinstance(value, Mapping):
+        return {key: thaw_json(item) for key, item in value.items()}
+    if isinstance(value, tuple):
+        return [thaw_json(item) for item in value]
+    return value
+
+
+def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
+    frozen = freeze_json(dict(value))
+    assert isinstance(frozen, Mapping)
+    return frozen
+
+
+@dataclass(frozen=True, slots=True)
+class LocationRecord:
+    file: str
+    line: int
+    anchor: str | None = None
+
+
+@dataclass(frozen=True, slots=True)
+class RelationToken:
+    authored_name: str
+    target: str
+    attributes: Mapping[str, object]
+    location: LocationRecord | None
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))
+
+
+@dataclass(frozen=True, slots=True)
+class ObjectDeclaration:
+    id: str
+    type: str
+    title: str
+    status: str
+    body: str
+    rationale: str
+    attributes: Mapping[str, object]
+    relations: tuple[RelationToken, ...]
+    location: LocationRecord | None
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))
+        object.__setattr__(self, "relations", tuple(self.relations))
+
+
+@dataclass(frozen=True, slots=True)
+class DeclarationBatch:
+    declarations: tuple[ObjectDeclaration, ...]
+    findings: tuple[Finding, ...]
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "declarations", tuple(self.declarations))
+        object.__setattr__(self, "findings", tuple(self.findings))
+
+
+@dataclass(frozen=True, slots=True)
+class ObjectRecord:
+    id: str
+    type: str
+    title: str
+    status: str
+    body: str
+    rationale: str
+    attributes: Mapping[str, object]
+    locations: tuple[LocationRecord, ...]
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))
+        object.__setattr__(self, "locations", tuple(self.locations))
+
+    @property
+    def priority(self) -> str | None:
+        value = self.attributes.get("priority")
+        return str(value) if value is not None and str(value) != "" else None
+
+    @property
+    def tags(self) -> tuple[str, ...]:
+        value = self.attributes.get("tags")
+        if isinstance(value, tuple):
+            return tuple(
+                str(item).strip() for item in value if str(item).strip()
+            )
+        if value is None:
+            return ()
+        return tuple(
+            item.strip()
+            for item in str(value).replace(";", ",").split(",")
+            if item.strip()
+        )
+
+
+@dataclass(frozen=True, slots=True)
+class RelationRecord:
+    source: str
+    authored_name: str
+    catalog_name: str
+    v1_name: str
+    target: str
+    semantic_family: str
+    source_role: str
+    target_role: str
+    impact_direction: str
+    attributes: Mapping[str, object]
+    provenance: tuple[LocationRecord, ...]
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))
+        object.__setattr__(self, "provenance", tuple(self.provenance))
+
+
+@dataclass(frozen=True, slots=True)
+class AnalysisSnapshot:
+    objects: tuple[ObjectRecord, ...]
+    relations: tuple[RelationRecord, ...]
+    findings: tuple[Finding, ...]
+    metrics: Mapping[str, object]
+    objects_by_id: Mapping[str, ObjectRecord]
+    outgoing: Mapping[str, tuple[RelationRecord, ...]]
+    incoming: Mapping[str, tuple[RelationRecord, ...]]
+    generator_name: str
+    generator_version: str
+    relation_catalog_version: str
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "objects", tuple(self.objects))
+        object.__setattr__(self, "relations", tuple(self.relations))
+        object.__setattr__(self, "findings", tuple(self.findings))
+        object.__setattr__(self, "metrics", _freeze_mapping(self.metrics))
+        object.__setattr__(
+            self, "objects_by_id", MappingProxyType(dict(self.objects_by_id))
+        )
+        object.__setattr__(
+            self,
+            "outgoing",
+            MappingProxyType(
+                {key: tuple(value) for key, value in self.outgoing.items()}
+            ),
+        )
+        object.__setattr__(
+            self,
+            "incoming",
+            MappingProxyType(
+                {key: tuple(value) for key, value in self.incoming.items()}
+            ),
+        )
+
+
+@dataclass(frozen=True, slots=True)
+class AnalysisResult:
+    declarations: tuple[ObjectDeclaration, ...]
+    findings: tuple[Finding, ...]
+    snapshot: AnalysisSnapshot | None
+
+    def __post_init__(self) -> None:
+        object.__setattr__(self, "declarations", tuple(self.declarations))
+        object.__setattr__(self, "findings", tuple(self.findings))
+
+    @property
+    def valid(self) -> bool:
+        return self.snapshot is not None
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/validation.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/validation.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/src/quarto_needs/validation.py	2026-08-24 23:41:30.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/src/quarto_needs/validation.py	2026-08-25 09:32:13.102541926 -0300
@@ -1,26 +1,17 @@
 from __future__ import annotations
 
-from dataclasses import dataclass
 from collections import Counter
 
+from .diagnostics import Finding
 from .graph import RequirementsGraph
-from .model import EngineeringObject
+from .model import EngineeringObject, SourceLocation
+from .snapshot import LocationRecord
 
 
-@dataclass(slots=True)
-class Finding:
-    code: str
-    severity: str
-    message: str
-    object_id: str | None = None
-
-    def to_dict(self) -> dict[str, str | None]:
-        return {
-            "code": self.code,
-            "severity": self.severity,
-            "message": self.message,
-            "object_id": self.object_id,
-        }
+def _location_record(source: SourceLocation | None) -> LocationRecord | None:
+    if source is None:
+        return None
+    return LocationRecord(source.file, source.line, source.anchor)
 
 
 def validate(objects: list[EngineeringObject], require_rationale_for: set[str] | None = None) -> list[Finding]:
@@ -28,7 +19,14 @@
     counts = Counter(o.id for o in objects)
     for need_id, count in counts.items():
         if count > 1:
-            findings.append(Finding("REQ004", "error", f"Duplicate ID: {need_id}", need_id))
+            source = next(obj.source for obj in objects if obj.id == need_id)
+            findings.append(Finding(
+                "REQ004",
+                "error",
+                f"Duplicate ID: {need_id}",
+                need_id,
+                _location_record(source),
+            ))
 
     graph = RequirementsGraph.build(objects)
     known = set(graph.objects)
@@ -39,6 +37,7 @@
                     "REQ005", "error",
                     f"{obj.id} references unknown object {rel.target} via {rel.type}",
                     obj.id,
+                    _location_record(obj.source),
                 ))
 
     require_rationale_for = require_rationale_for or {"system-requirement", "software-requirement"}
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/tests/test_parser.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/tests/test_parser.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/tests/test_parser.py	2026-08-25 09:20:24.628799388 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/tests/test_parser.py	2026-08-25 09:29:03.322949900 -0300
@@ -1,9 +1,36 @@
 from pathlib import Path
 
-from quarto_needs.parser import parse_qmd
+from quarto_needs.parser import (
+    parse_project_declarations,
+    parse_qmd,
+    parse_qmd_declarations,
+)
 from quarto_needs.validation import validate
 
 
+def write_need(
+    path: Path,
+    need_id: str,
+    relation_name: str | None,
+    relation_target: str | None,
+    *,
+    need_type: str = "system-requirement",
+) -> None:
+    relation = (
+        f"{relation_name}: {relation_target}\n"
+        if relation_name is not None and relation_target is not None
+        else ""
+    )
+    path.write_text(
+        f"::: {{.need #{need_id} type={need_type}}}\n"
+        f"{relation}"
+        f"\n## {need_id}\n"
+        "Body.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+
 def test_parse_need(tmp_path: Path):
     qmd = tmp_path / "req.qmd"
     qmd.write_text('''::: {.need #SYS-REQ-001 type="system-requirement" status="approved" derived-from="NEED-001"}\n## Login\nText.\n:::\n''', encoding="utf-8")
@@ -40,3 +67,55 @@
         ("verifies", "verifies", "REQ-1"),
         ("evidences", "evidences", "EVD-1"),
     ]
+
+
+def test_project_declarations_sort_paths_and_keep_authored_relation(
+    tmp_path: Path,
+) -> None:
+    write_need(tmp_path / "z.qmd", "Z-REQ", "verified-by", "A-TC")
+    write_need(tmp_path / "a.qmd", "A-TC", None, None, need_type="test-case")
+
+    batch = parse_project_declarations(
+        tmp_path,
+        files=[tmp_path / "z.qmd", tmp_path / "a.qmd"],
+    )
+
+    assert [item.id for item in batch.declarations] == ["A-TC", "Z-REQ"]
+    relation = next(
+        item for item in batch.declarations if item.id == "Z-REQ"
+    ).relations[0]
+    assert relation.authored_name == "verified-by"
+    assert relation.location is not None
+    assert relation.location.file == "z.qmd"
+
+
+def test_unclosed_need_block_is_a_located_structural_finding(tmp_path: Path) -> None:
+    source = tmp_path / "broken.qmd"
+    source.write_text("::: {.need #REQ-BROKEN}\n## Broken\n", encoding="utf-8")
+
+    batch = parse_qmd_declarations(source, tmp_path)
+
+    assert batch.declarations == ()
+    assert [
+        (item.code, item.severity, item.location.file, item.location.line)
+        for item in batch.findings
+    ] == [("QND001", "error", "broken.qmd", 1)]
+
+
+def test_known_relation_without_targets_is_structurally_invalid(
+    tmp_path: Path,
+) -> None:
+    source = tmp_path / "empty-relation.qmd"
+    source.write_text(
+        "::: {.need #REQ-EMPTY}\n"
+        "verified-by:\n\n"
+        "## Empty relation\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+    batch = parse_qmd_declarations(source, tmp_path)
+
+    assert [(item.code, item.object_id) for item in batch.findings] == [
+        ("QND002", "REQ-EMPTY")
+    ]
diff -ruN .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/tests/test_snapshot.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/tests/test_snapshot.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-before/tests/test_snapshot.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-1-foundation/snapshots/task-3-after/tests/test_snapshot.py	2026-08-25 09:29:03.318949909 -0300
@@ -0,0 +1,21 @@
+from types import MappingProxyType
+
+import pytest
+
+from quarto_needs.snapshot import freeze_json, thaw_json
+
+
+def test_freeze_json_is_recursive_and_round_trips() -> None:
+    source = {"tags": ["security", "login"], "nested": {"rank": 1}}
+
+    frozen = freeze_json(source)
+    source["tags"].append("mutated")
+
+    assert isinstance(frozen, MappingProxyType)
+    assert frozen["tags"] == ("security", "login")
+    with pytest.raises(TypeError):
+        frozen["nested"]["rank"] = 2
+    assert thaw_json(frozen) == {
+        "nested": {"rank": 1},
+        "tags": ["security", "login"],
+    }
