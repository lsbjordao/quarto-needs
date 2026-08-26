### Task 3: Add immutable declarations, records, and located diagnostics

**Files:**
- Create: `src/quarto_needs/diagnostics.py`
- Create: `src/quarto_needs/snapshot.py`
- Modify: `src/quarto_needs/validation.py`
- Modify: `src/quarto_needs/parser.py`
- Create: `tests/test_snapshot.py`
- Modify: `tests/test_parser.py`

**Interfaces:**
- Produces: `freeze_json`, `thaw_json`, `LocationRecord`, `RelationToken`, `ObjectDeclaration`, `DeclarationBatch`, `ObjectRecord`, `RelationRecord`, `AnalysisSnapshot`, `AnalysisResult`, `parse_qmd_declarations`, and `parse_project_declarations`.
- Preserves: `Finding` importability from `quarto_needs.validation` and valid legacy parser results.

- [ ] **Step 1: Write failing deep-immutability and declaration tests**

```python
from types import MappingProxyType

import pytest

from quarto_needs.parser import parse_project_declarations, parse_qmd_declarations
from quarto_needs.snapshot import freeze_json, thaw_json


def test_freeze_json_is_recursive_and_round_trips() -> None:
    source = {"tags": ["security", "login"], "nested": {"rank": 1}}
    frozen = freeze_json(source)
    source["tags"].append("mutated")
    assert isinstance(frozen, MappingProxyType)
    assert frozen["tags"] == ("security", "login")
    with pytest.raises(TypeError):
        frozen["nested"]["rank"] = 2
    assert thaw_json(frozen) == {"nested": {"rank": 1}, "tags": ["security", "login"]}


def test_project_declarations_sort_paths_and_keep_authored_relation(tmp_path: Path) -> None:
    write_need(tmp_path / "z.qmd", "Z-REQ", "verified-by", "A-TC")
    write_need(tmp_path / "a.qmd", "A-TC", None, None, need_type="test-case")
    batch = parse_project_declarations(tmp_path, files=[tmp_path / "z.qmd", tmp_path / "a.qmd"])
    assert [item.id for item in batch.declarations] == ["A-TC", "Z-REQ"]
    relation = next(item for item in batch.declarations if item.id == "Z-REQ").relations[0]
    assert relation.authored_name == "verified-by"
    assert relation.location is not None
    assert relation.location.file == "z.qmd"


def test_unclosed_need_block_is_a_located_structural_finding(tmp_path: Path) -> None:
    source = tmp_path / "broken.qmd"
    source.write_text("::: {.need #REQ-BROKEN}\n## Broken\n", encoding="utf-8")
    batch = parse_qmd_declarations(source, tmp_path)
    assert batch.declarations == ()
    assert [(item.code, item.severity, item.location.file, item.location.line) for item in batch.findings] == [
        ("QND001", "error", "broken.qmd", 1)
    ]


def test_known_relation_without_targets_is_structurally_invalid(tmp_path: Path) -> None:
    source = tmp_path / "empty-relation.qmd"
    source.write_text(
        "::: {.need #REQ-EMPTY}\nverified-by:\n\n## Empty relation\n:::\n",
        encoding="utf-8",
    )
    batch = parse_qmd_declarations(source, tmp_path)
    assert [(item.code, item.object_id) for item in batch.findings] == [("QND002", "REQ-EMPTY")]
```

The local `write_need` helper must write a complete closed `.need` block and must not depend on production parser helpers.

- [ ] **Step 2: Run the focused tests and verify missing immutable APIs**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py tests/test_parser.py -q`

Expected: FAIL on missing modules/functions.

- [ ] **Step 3: Move `Finding` to a dependency-neutral diagnostics module**

Create this compatibility-safe, deeply immutable shape in `diagnostics.py`. `snapshot.py` refers to `Finding` only inside `TYPE_CHECKING`, so `diagnostics.py` can reuse `LocationRecord` and `freeze_json` without a runtime import cycle:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .snapshot import LocationRecord, freeze_json, thaw_json


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: str
    message: str
    object_id: str | None = None
    location: LocationRecord | None = None
    properties: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "properties", freeze_json(dict(self.properties)))

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "object_id": self.object_id,
        }
        if self.location is not None:
            result["location"] = {
                "file": self.location.file,
                "line": self.location.line,
                "anchor": self.location.anchor,
            }
        if self.properties:
            result["properties"] = thaw_json(self.properties)
        return result
```

In `snapshot.py`, guard `from .diagnostics import Finding` with `if TYPE_CHECKING:`; postponed annotations keep it out of runtime initialization. In `validation.py`, import `Finding` and `LocationRecord` at module scope so `from quarto_needs.validation import Finding` remains valid. Convert a legacy `SourceLocation` to a `LocationRecord` when attaching structural findings. Existing semantic warnings need not gain locations in this milestone; structural parser/graph findings must be located.

- [ ] **Step 4: Implement recursive freezing and canonical records**

In `snapshot.py`, reject unsupported JSON values rather than silently stringifying them. Sort mapping keys with `(key.casefold(), key)`, reject non-finite floats, and preserve list order as tuples:

```python
from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .diagnostics import Finding

JsonScalar = str | int | float | bool | None


def freeze_json(value: object) -> object:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("JSON numbers must be finite")
        return value
    if isinstance(value, list) or isinstance(value, tuple):
        return tuple(freeze_json(item) for item in value)
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("JSON object keys must be strings")
        frozen = {
            key: freeze_json(value[key])
            for key in sorted(value, key=lambda item: (item.casefold(), item))
        }
        return MappingProxyType(frozen)
    raise TypeError(f"Unsupported JSON value: {type(value).__name__}")


def thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value
```

Define frozen, slotted dataclasses with these exact fields:

```python
@dataclass(frozen=True, slots=True)
class LocationRecord:
    file: str
    line: int
    anchor: str | None = None


@dataclass(frozen=True, slots=True)
class RelationToken:
    authored_name: str
    target: str
    attributes: Mapping[str, object]
    location: LocationRecord | None


@dataclass(frozen=True, slots=True)
class ObjectDeclaration:
    id: str
    type: str
    title: str
    status: str
    body: str
    rationale: str
    attributes: Mapping[str, object]
    relations: tuple[RelationToken, ...]
    location: LocationRecord | None


@dataclass(frozen=True, slots=True)
class DeclarationBatch:
    declarations: tuple[ObjectDeclaration, ...]
    findings: tuple[Finding, ...]


@dataclass(frozen=True, slots=True)
class ObjectRecord:
    id: str
    type: str
    title: str
    status: str
    body: str
    rationale: str
    attributes: Mapping[str, object]
    locations: tuple[LocationRecord, ...]

    @property
    def priority(self) -> str | None:
        value = self.attributes.get("priority")
        return str(value) if value is not None and str(value) != "" else None

    @property
    def tags(self) -> tuple[str, ...]:
        value = self.attributes.get("tags")
        if isinstance(value, tuple):
            return tuple(str(item).strip() for item in value if str(item).strip())
        if value is None:
            return ()
        return tuple(item.strip() for item in str(value).replace(";", ",").split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class RelationRecord:
    source: str
    authored_name: str
    catalog_name: str
    v1_name: str
    target: str
    semantic_family: str
    source_role: str
    target_role: str
    impact_direction: str
    attributes: Mapping[str, object]
    provenance: tuple[LocationRecord, ...]
```

Declare `AnalysisSnapshot` and `AnalysisResult` now with the fields implemented in Task 5, so later work fills the builder without changing public type names:

```python
@dataclass(frozen=True, slots=True)
class AnalysisSnapshot:
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


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    declarations: tuple[ObjectDeclaration, ...]
    findings: tuple[Finding, ...]
    snapshot: AnalysisSnapshot | None

    @property
    def valid(self) -> bool:
        return self.snapshot is not None
```

- [ ] **Step 5: Implement declaration parsing and keep wrappers compatible**

Refactor the current block parser into `parse_qmd_declarations(path, root=None) -> DeclarationBatch`. It must:

- read UTF-8 once;
- preserve current metadata/title/body/rationale behavior for closed valid blocks;
- deep-freeze attributes and relation attributes;
- preserve authored relation tokens and record the metadata-key line as relation provenance (`.need` opening attributes use the opening line);
- report `QND001` at the opening line and omit the incomplete declaration when EOF occurs before `:::`;
- report `QND002` at the opening line when a known catalog relation has no non-empty scalar targets; keep unknown metadata keys as ordinary attributes for compatibility;
- use project-relative POSIX paths when `root` is supplied.

Refactor `_collect_metadata` to return the source-line offset for every key alongside its parsed value; do not attempt to recover relation provenance later by searching text, because repeated values would make that ambiguous.

Implement `parse_project_declarations(root, files=None) -> DeclarationBatch` by resolving and sorting paths with `(relative_path.casefold(), relative_path)`, concatenating declarations/findings, and sorting declarations by `(location.file.casefold(), location.file, location.line, id.casefold(), id)`. The parser always supplies a location; the field remains optional only so `analyze_objects` can faithfully adapt legacy in-memory DTOs whose `source` is `None`.

Implement `parse_qmd` and `parse_project` as wrappers that convert declarations to legacy DTOs. Use `thaw_json` for object/relation attributes so compatibility DTOs keep ordinary dictionaries/lists rather than mapping proxies/tuples. Relation conversion resolves the catalog and sets `type=kind.v1_name` plus `authored_name=token.authored_name`. `parse_project` returns objects sorted by `(id.casefold(), id, source.file, source.line)`; this is the documented deterministic change.

- [ ] **Step 6: Run parser, snapshot, validation, and example regressions**

Run:

```bash
.venv/bin/python -m pytest tests/test_snapshot.py tests/test_parser.py tests/test_example_project.py -q
```

Expected: PASS with the same 85-object Aegis semantics and deterministic ordering.

- [ ] **Step 7: Record the immutable-model checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/diagnostics.py src/quarto_needs/snapshot.py src/quarto_needs/validation.py src/quarto_needs/parser.py tests/test_snapshot.py tests/test_parser.py
  git commit -m "refactor: add immutable analysis records"
else
  echo "Checkpoint 3 verified; workspace has no Git metadata."
fi
```

---

