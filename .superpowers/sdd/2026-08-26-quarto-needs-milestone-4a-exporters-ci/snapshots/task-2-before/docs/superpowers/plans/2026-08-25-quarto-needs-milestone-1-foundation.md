# Quarto-Needs Milestone 1 Canonical Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a deterministic, duplicate-safe canonical analysis pipeline and a visibly improved Quarto experience with cached graph access, format-aware links, outgoing relations, and backlinks, while preserving the schema-v1 graph and every documented compatibility surface.

**Architecture:** QMD files are parsed once into immutable declarations. `analysis.py` validates structure, resolves authored relations through the Python relation catalog, and returns either a valid immutable `AnalysisSnapshot` or an invalid `AnalysisResult` with located findings and no graph. Exporters consume the snapshot and write deterministic, atomic schema-v1 JSON plus the legacy Lua index. Quarto Lua modules cache that JSON, build indexes once, resolve links for HTML/DOCX/PDF, and render relation sections as Pandoc-native content.

**Tech Stack:** Python 3.10+, standard-library dataclasses/typing/JSON, pytest, jsonschema as a test-only dependency, Quarto/Pandoc Lua, CSS, vanilla JavaScript

**Spec:** `docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md`, Milestone 1

## Global Constraints

- Do not add a runtime dependency in this milestone. Add `pytest` and `jsonschema` only to the `test` optional dependency group.
- Preserve the signatures and documented behavior of `parse_qmd`, `parse_project`, `RequirementsGraph.build` for valid unique inputs, `validate`, `coverage`, `export_graph`, `export_lua_index`, `cli.build`, existing CLI commands, and existing shortcodes.
- Preserve schema-v1 required keys, value types, relation orientation, `derived-from` to `derives-from` output normalization, nested/top-level relation duplication, backlink meaning, HTML `href` behavior, and legacy coverage keys. Byte order may become deterministic and additive metadata belongs under `extensions.quartoNeeds`.
- Never silently overwrite duplicate IDs. Structural errors produce findings and no snapshot; build/export commands must not replace an existing output with an invalid partial graph.
- Keep Python authoritative for relation semantics. Lua consumes the catalog projection and must not hard-code competing inverse semantics.
- Keep essential information in Pandoc AST so HTML, DOCX, and PDF remain useful without JavaScript.
- `_extensions/quarto-needs` is canonical. `examples/book/_extensions/quarto-needs` is synchronized through the pre-render helper and checked by tests.
- Keep generated JSON and Lua output deterministic and atomic. Do not include wall-clock timestamps or absolute local paths.
- Full semantic fingerprints, TOML configuration, queries, configurable rules/gates, baselines/diff/impact, scanners, advanced exporters, public browser projection, inspector/dashboard, and interactive graph remain assigned to Milestones 2–5.
- The workspace currently has no `.git` metadata. Do not initialize Git. Every task includes a conditional commit checkpoint that records a commit only if the executor is operating in a Git worktree.
- Keep the existing preview server running; implementation and verification must not terminate the server listening on `127.0.0.1:8777`.

## File Map

| Area | Files | Responsibility after Milestone 1 |
|---|---|---|
| Compatibility DTOs | `src/quarto_needs/model.py` | Existing mutable `EngineeringObject`, `Relation`, and `SourceLocation`; `Relation.authored_name` is additive and omitted from v1 serialization. |
| Diagnostics | `src/quarto_needs/diagnostics.py`, `src/quarto_needs/validation.py` | Immutable findings, deterministic validation, and compatibility re-export of `Finding`. |
| Relation semantics | `src/quarto_needs/relations.py` | Complete embedded catalog, aliases, display labels, semantic families, endpoint roles, impact direction, and v1 names. |
| Canonical records | `src/quarto_needs/snapshot.py` | Deep-freezing helpers, declarations, immutable records, indexes, `AnalysisSnapshot`, and `AnalysisResult`. |
| Ingestion | `src/quarto_needs/parser.py` | Located declaration parser, deterministic project traversal, and legacy parser wrappers. |
| Graph | `src/quarto_needs/graph.py` | Duplicate-safe legacy graph with deterministic adjacency. |
| Orchestration | `src/quarto_needs/analysis.py` | One-pass project/object analysis and valid-or-invalid result construction. |
| Compatibility writers | `src/quarto_needs/export.py` | v1 payload projection, canonical JSON/Lua rendering, atomic writes, and legacy wrappers. |
| Commands | `src/quarto_needs/cli.py`, `tools/quarto_needs_pre_render.py` | One analysis per invocation and no writes for invalid results. |
| Lua data boundary | `_extensions/quarto-needs/data.lua`, `_extensions/quarto-needs/views.lua` | Per-process graph cache, object/relation indexes, exact filters, and format-aware links. |
| Lua relation UI | `_extensions/quarto-needs/relations.lua`, `_extensions/quarto-needs/needs.lua`, `_extensions/quarto-needs/shortcodes.lua` | Static outgoing/backlink sections, card integration, and `need-backlinks`. |
| Schemas and fixtures | `schemas/needs.schema.json`, `schemas/needs-envelope-v1.schema.json`, `tests/fixtures/canonical/*`, `tests/fixtures/v1/*`, `tests/fixtures/views/*` | Frozen v1 contract, deterministic canonical fixture, and three-format rendering inputs. |
| Tests | `tests/test_v1_contract.py`, `tests/test_relations.py`, `tests/test_snapshot.py`, `tests/test_analysis.py`, `tests/test_cli.py`, existing test modules | Unit, contract, golden, CLI, Lua, render, and regression coverage. |
| Developer UX | `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`, `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md` | Reproducible setup, regeneration, architecture, and milestone acceptance commands. |

---

### Task 1: Freeze the schema-v1 compatibility contract

**Files:**
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Create: `schemas/needs-envelope-v1.schema.json`
- Create: `tests/fixtures/v1/aegis-needs-v1.json`
- Create: `tests/test_v1_contract.py`

**Interfaces:**
- Consumes: the currently generated `examples/book/.quarto-needs/needs.json` before any production refactor.
- Produces: a frozen representative v1 payload, a Draft 2020-12 envelope schema, and `legacy_projection(payload)` for semantic compatibility comparisons.

- [ ] **Step 1: Capture the current Aegis payload before changing production code**

Run:

```bash
mkdir -p tests/fixtures/v1
cp examples/book/.quarto-needs/needs.json tests/fixtures/v1/aegis-needs-v1.json
```

Expected: the fixture contains the current Aegis objects, nested relations, top-level relations, coverage, validation, backlinks, and schema version. This is a mechanical byte-for-byte fixture capture; do not regenerate it after the refactor.

- [ ] **Step 2: Declare test dependencies once and use the extra everywhere**

Add this exact group to `pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
  "pytest>=8",
  "jsonschema>=4.23",
]
```

Change setup/install commands to `python -m pip install -e ".[test]"` in `Makefile` and `.github/workflows/ci.yml`. Do not add either package to `[project.dependencies]`.

- [ ] **Step 3: Add the complete v1 envelope schema**

Create `schemas/needs-envelope-v1.schema.json` with these required top-level fields and definitions:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schema/needs-envelope-v1.schema.json",
  "title": "Quarto-Needs Graph Envelope v1",
  "type": "object",
  "required": ["schemaVersion", "objects", "relations", "coverage", "validation", "backlinks"],
  "properties": {
    "schemaVersion": {"const": "1"},
    "objects": {
      "type": "array",
      "items": {
        "allOf": [
          {"$ref": "needs.schema.json"},
          {"required": ["id", "type", "title", "status", "body", "rationale", "attributes", "relations", "source", "href"]}
        ]
      }
    },
    "relations": {"type": "array", "items": {"$ref": "#/$defs/relation"}},
    "coverage": {"$ref": "#/$defs/coverage"},
    "validation": {"type": "array", "items": {"$ref": "#/$defs/finding"}},
    "backlinks": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {"$ref": "#/$defs/backlink"}
      }
    },
    "extensions": {"type": "object"}
  },
  "additionalProperties": false,
  "$defs": {
    "relation": {
      "type": "object",
      "required": ["type", "source", "target", "attributes"],
      "properties": {
        "type": {"type": "string", "minLength": 1},
        "source": {"type": "string", "minLength": 1},
        "target": {"type": "string", "minLength": 1},
        "attributes": {"type": "object"}
      },
      "additionalProperties": false
    },
    "coverage": {
      "type": "object",
      "required": ["requirements", "approved", "implemented", "verified", "implementation_coverage", "verification_coverage"],
      "properties": {
        "requirements": {"type": "integer", "minimum": 0},
        "approved": {"type": "integer", "minimum": 0},
        "implemented": {"type": "integer", "minimum": 0},
        "verified": {"type": "integer", "minimum": 0},
        "implementation_coverage": {"type": "number", "minimum": 0, "maximum": 100},
        "verification_coverage": {"type": "number", "minimum": 0, "maximum": 100}
      },
      "additionalProperties": false
    },
    "finding": {
      "type": "object",
      "required": ["code", "severity", "message", "object_id"],
      "properties": {
        "code": {"type": "string"},
        "severity": {"enum": ["error", "warning", "info"]},
        "message": {"type": "string"},
        "object_id": {"type": ["string", "null"]}
      },
      "additionalProperties": true
    },
    "backlink": {
      "type": "object",
      "required": ["source", "type"],
      "properties": {
        "source": {"type": "string"},
        "type": {"type": "string"}
      },
      "additionalProperties": false
    }
  }
}
```

Also extend `schemas/needs.schema.json` so its existing `properties` map contains these exact additions while keeping the current `$id` and object-level purpose:

```json
"source": {
  "type": ["object", "null"],
  "required": ["file", "line", "anchor"],
  "properties": {
    "file": {"type": "string"},
    "line": {"type": "integer", "minimum": 1},
    "anchor": {"type": ["string", "null"]}
  },
  "additionalProperties": false
},
"href": {"type": "string", "minLength": 1}
```

Require `attributes` on relation items because the actual v1 writer always emits it, and set `additionalProperties: false` on relation items. Leave object-level additional properties allowed so older/newer tolerant object consumers are not accidentally narrowed by the object-only schema.

- [ ] **Step 4: Write contract tests against the frozen fixture**

Add these test helpers and assertions to `tests/test_v1_contract.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
GOLDEN = ROOT / "tests/fixtures/v1/aegis-needs-v1.json"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def legacy_projection(payload: dict[str, object]) -> dict[str, object]:
    projected = {key: value for key, value in payload.items() if key != "extensions"}
    projected["objects"] = sorted(projected["objects"], key=lambda item: (item["id"].casefold(), item["id"]))
    projected["relations"] = sorted(
        projected["relations"],
        key=lambda item: (
            item["source"].casefold(), item["source"], item["type"],
            item["target"].casefold(), item["target"],
            json.dumps(item.get("attributes", {}), ensure_ascii=False, sort_keys=True),
        ),
    )
    projected["validation"] = sorted(
        projected["validation"],
        key=lambda item: (item["severity"], item["code"], item.get("object_id") or "", item["message"]),
    )
    projected["backlinks"] = {
        key: sorted(value, key=lambda item: (item["source"].casefold(), item["type"]))
        for key, value in sorted(projected["backlinks"].items())
    }
    for item in projected["objects"]:
        item["relations"] = sorted(
            item.get("relations", []),
            key=lambda relation: (
                relation["type"], relation["target"].casefold(), relation["target"],
                json.dumps(relation.get("attributes", {}), ensure_ascii=False, sort_keys=True),
            ),
        )
    return projected


def test_frozen_aegis_payload_validates_against_v1_envelope() -> None:
    schema = load_json(SCHEMAS / "needs-envelope-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    resolver = RefResolver((SCHEMAS / "needs-envelope-v1.schema.json").as_uri(), schema)
    Draft202012Validator(schema, resolver=resolver).validate(load_json(GOLDEN))


def test_frozen_payload_has_nested_and_top_level_relation_equivalence() -> None:
    payload = load_json(GOLDEN)
    nested = [relation for item in payload["objects"] for relation in item.get("relations", [])]
    key = lambda relation: json.dumps(relation, ensure_ascii=False, sort_keys=True)
    assert sorted(nested, key=key) == sorted(payload["relations"], key=key)
```

If the installed jsonschema version warns that `RefResolver` is deprecated, keep the test behavior for this milestone and record migration to the referencing registry as test-infrastructure cleanup; do not weaken validation.

- [ ] **Step 5: Run the contract tests before refactoring**

Run:

```bash
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest tests/test_v1_contract.py -q
```

Expected: PASS against the current payload. If the frozen file lacks a field required by the proposed schema, correct the schema to describe the actual v1 payload; do not edit the frozen payload to make the test pass.

- [ ] **Step 6: Record the compatibility checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add pyproject.toml Makefile .github/workflows/ci.yml schemas/needs.schema.json schemas/needs-envelope-v1.schema.json tests/fixtures/v1/aegis-needs-v1.json tests/test_v1_contract.py
  git commit -m "test: freeze schema v1 compatibility contract"
else
  echo "Checkpoint 1 verified; workspace has no Git metadata."
fi
```

Expected: a commit is created only inside an existing Git worktree; otherwise the verified changes remain in place.

---

### Task 2: Introduce the complete relation catalog without breaking legacy DTOs

**Files:**
- Create: `src/quarto_needs/relations.py`
- Modify: `src/quarto_needs/model.py`
- Modify: `src/quarto_needs/parser.py`
- Create: `tests/test_relations.py`
- Modify: `tests/test_parser.py`

**Interfaces:**
- Produces: `RelationKind`, `RelationCatalog`, `DEFAULT_RELATION_CATALOG`, `Relation.authored_name`, and catalog-backed parsing.
- Preserves: `Relation(type, source, target, attributes)` positional construction and `EngineeringObject.to_dict()` schema-v1 shape.

- [ ] **Step 1: Write failing catalog and alias tests**

```python
from quarto_needs.relations import DEFAULT_RELATION_CATALOG


def test_default_catalog_covers_every_legacy_and_inverse_authoring_name() -> None:
    assert DEFAULT_RELATION_CATALOG.names == (
        "conflicts-with", "constrains", "decomposes", "depends-on",
        "derived-from", "derives-from", "evidenced-by", "evidences",
        "implemented-by", "implements", "justified-by", "mitigates",
        "references", "refines", "validated-by", "verified-by", "verifies",
    )


def test_inverse_authoring_forms_share_semantic_families_and_swap_roles() -> None:
    implements = DEFAULT_RELATION_CATALOG.resolve("implements")
    implemented_by = DEFAULT_RELATION_CATALOG.resolve("implemented-by")
    assert implements.semantic_family == implemented_by.semantic_family == "implementation"
    assert (implements.source_role, implements.target_role) == ("implementation-artifact", "requirement")
    assert (implemented_by.source_role, implemented_by.target_role) == ("requirement", "implementation-artifact")
    assert implements.inverse_label == implemented_by.direct_label


def test_derived_from_preserves_authored_name_but_keeps_v1_normalization(tmp_path: Path) -> None:
    source = tmp_path / "requirements.qmd"
    source.write_text(
        "::: {.need #REQ-2 type=system-requirement}\n"
        "derived-from: REQ-1\n\n"
        "## Derived requirement\n"
        ":::\n",
        encoding="utf-8",
    )
    relation = parse_qmd(source)[0].relations[0]
    assert relation.authored_name == "derived-from"
    assert relation.type == "derives-from"
```

- [ ] **Step 2: Run the focused tests and verify the missing module/field failures**

Run: `.venv/bin/python -m pytest tests/test_relations.py tests/test_parser.py -q`

Expected: FAIL because `relations.py` and `Relation.authored_name` do not exist.

- [ ] **Step 3: Implement immutable catalog types and all 17 embedded entries**

Use this public shape in `relations.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

ImpactDirection = Literal["source_to_target", "target_to_source", "both", "none"]


@dataclass(frozen=True, slots=True)
class RelationKind:
    authored_name: str
    catalog_name: str
    v1_name: str
    semantic_family: str
    direct_label: str
    inverse_label: str
    source_role: str
    target_role: str
    impact_direction: ImpactDirection
    public: bool = True
    allowed_source_types: tuple[str, ...] = ()
    allowed_target_types: tuple[str, ...] = ()
    minimum_per_source: int | None = None
    maximum_per_source: int | None = None


@dataclass(frozen=True, slots=True)
class RelationCatalog:
    version: str
    entries: Mapping[str, RelationKind]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))

    @classmethod
    def create(cls, version: str, entries: tuple[RelationKind, ...]) -> "RelationCatalog":
        by_name = {entry.authored_name: entry for entry in entries}
        if len(by_name) != len(entries):
            raise ValueError("Relation catalog contains duplicate authored names")
        return cls(version=version, entries=MappingProxyType(by_name))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.entries))

    def resolve(self, authored_name: str) -> RelationKind:
        try:
            return self.entries[authored_name]
        except KeyError as error:
            raise ValueError(f"Unknown relation type: {authored_name}") from error
```

Create `DEFAULT_RELATION_CATALOG` version `1` with exactly this behavior table:

| Authored name | Catalog/v1 name | Family | Source role → target role | Direct / inverse label | Impact |
|---|---|---|---|---|---|
| `derives-from` | `derives-from` | `derivation` | `derived` → `source` | Derives from / Source for | `target_to_source` |
| `derived-from` | `derives-from` | `derivation` | `derived` → `source` | Derives from / Source for | `target_to_source` |
| `refines` | `refines` | `refinement` | `refinement` → `subject` | Refines / Refined by | `target_to_source` |
| `decomposes` | `decomposes` | `decomposition` | `whole` → `part` | Decomposes / Part of | `none` |
| `depends-on` | `depends-on` | `dependency` | `dependent` → `dependency` | Depends on / Depended on by | `target_to_source` |
| `conflicts-with` | `conflicts-with` | `conflict` | `subject` → `subject` | Conflicts with / Conflicts with | `both` |
| `constrains` | `constrains` | `constraint` | `constraint` → `subject` | Constrains / Constrained by | `none` |
| `implements` | `implements` | `implementation` | `implementation-artifact` → `requirement` | Implements / Implemented by | `target_to_source` |
| `implemented-by` | `implemented-by` | `implementation` | `requirement` → `implementation-artifact` | Implemented by / Implements | `source_to_target` |
| `verifies` | `verifies` | `verification` | `test` → `requirement` | Verifies / Verified by | `target_to_source` |
| `verified-by` | `verified-by` | `verification` | `requirement` → `test` | Verified by / Verifies | `source_to_target` |
| `validated-by` | `validated-by` | `verification` | `requirement` → `test` | Validated by / Validates | `source_to_target` |
| `mitigates` | `mitigates` | `mitigation` | `mitigation` → `risk` | Mitigates / Mitigated by | `target_to_source` |
| `justified-by` | `justified-by` | `justification` | `subject` → `justification` | Justified by / Justifies | `none` |
| `evidences` | `evidences` | `evidence` | `evidence` → `test` | Evidences / Evidenced by | `target_to_source` |
| `evidenced-by` | `evidenced-by` | `evidence` | `test` → `evidence` | Evidenced by / Evidences | `source_to_target` |
| `references` | `references` | `reference` | `source` → `target` | References / Referenced by | `none` |

In Milestone 1, empty allowed-type tuples mean “permissive embedded default,” and `None` cardinalities mean “not constrained.” The fields are present now so Milestone 2 can merge configured endpoint/cardinality policies without changing the catalog type. The `implementation`, `verification`, `evidence`, and `mitigation` semantic families are the declared metric-contribution categories; no separate Boolean flags may drift from them.

- [ ] **Step 4: Add authored provenance without leaking it into v1 DTO serialization**

Append `authored_name: str | None = None` after `attributes` in `Relation`, preserving four-argument positional construction. Replace `EngineeringObject.to_dict()` with explicit serialization:

```python
def relation_to_v1_dict(relation: Relation) -> dict[str, Any]:
    return {
        "type": relation.type,
        "source": relation.source,
        "target": relation.target,
        "attributes": relation.attributes,
    }


def to_dict(self) -> dict[str, Any]:
    return {
        "id": self.id,
        "type": self.type,
        "title": self.title,
        "status": self.status,
        "body": self.body,
        "rationale": self.rationale,
        "attributes": self.attributes,
        "relations": [relation_to_v1_dict(relation) for relation in self.relations],
        "source": asdict(self.source) if self.source else None,
    }
```

- [ ] **Step 5: Replace parser hard-coding with catalog lookup**

`RELATION_KEYS` becomes `set(DEFAULT_RELATION_CATALOG.names)`. For each relation metadata key, resolve the entry and create:

```python
Relation(
    type=kind.v1_name,
    source=need_id,
    target=str(target),
    attributes={},
    authored_name=key,
)
```

The legacy wrapper still emits `type="derives-from"` for authored `derived-from`, but the new field retains the original token.

- [ ] **Step 6: Run focused and compatibility tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_relations.py tests/test_parser.py tests/test_export.py tests/test_v1_contract.py -q
```

Expected: PASS; the only new legacy DTO state is `authored_name`, and it is absent from `EngineeringObject.to_dict()`.

- [ ] **Step 7: Record the relation-catalog checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/relations.py src/quarto_needs/model.py src/quarto_needs/parser.py tests/test_relations.py tests/test_parser.py
  git commit -m "feat: add canonical relation catalog"
else
  echo "Checkpoint 2 verified; workspace has no Git metadata."
fi
```

---

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

### Task 4: Make graph construction and validation duplicate-safe

**Files:**
- Modify: `src/quarto_needs/graph.py`
- Modify: `src/quarto_needs/validation.py`
- Modify: `tests/test_graph.py`
- Create: `tests/test_validation.py`

**Interfaces:**
- Produces: located `DuplicateIdError` and deterministically ordered legacy graph adjacency/findings.
- Preserves: valid `RequirementsGraph.build()` traversal behavior and existing REQ002/REQ004/REQ005/REQ006 meanings.

- [ ] **Step 1: Write failing duplicate and multi-diagnostic tests**

```python
import pytest

from quarto_needs.graph import DuplicateIdError, RequirementsGraph


def test_graph_rejects_duplicate_ids_instead_of_overwriting() -> None:
    first = EngineeringObject("REQ-1", "need", "First", source=SourceLocation("a.qmd", 1, "REQ-1"))
    second = EngineeringObject("REQ-1", "need", "Second", source=SourceLocation("b.qmd", 7, "REQ-1"))
    with pytest.raises(DuplicateIdError) as caught:
        RequirementsGraph.build([second, first])
    assert caught.value.duplicate_id == "REQ-1"
    assert [(item.file, item.line) for item in caught.value.locations] == [("a.qmd", 1), ("b.qmd", 7)]


def test_validation_reports_duplicate_and_unknown_target_without_throwing() -> None:
    first = EngineeringObject("REQ-1", "need", "First", relations=[Relation("references", "REQ-1", "MISSING")])
    second = EngineeringObject("REQ-1", "need", "Second")
    findings = validate([second, first])
    assert [(item.code, item.object_id) for item in findings if item.severity == "error"] == [
        ("REQ004", "REQ-1"),
        ("REQ005", "REQ-1"),
    ]
```

- [ ] **Step 2: Run the focused tests and verify silent-overwrite behavior fails them**

Run: `.venv/bin/python -m pytest tests/test_graph.py tests/test_validation.py -q`

Expected: FAIL because graph construction currently overwrites duplicates and validation builds that ambiguous graph.

- [ ] **Step 3: Detect all duplicate declarations before building the graph**

Add this error type:

```python
class DuplicateIdError(ValueError):
    def __init__(self, duplicate_id: str, locations: tuple[SourceLocation, ...]):
        self.duplicate_id = duplicate_id
        self.locations = locations
        rendered = ", ".join(f"{item.file}:{item.line}" for item in locations) or "unknown locations"
        super().__init__(f"Duplicate ID {duplicate_id}: {rendered}")
```

`RequirementsGraph.build` must group objects first, choose the first duplicate ID by `(id.casefold(), id)`, sort its available locations by `(file.casefold(), file, line, anchor or "")`, and raise before creating `objects`, `outgoing`, or `incoming`. For valid input, sort outgoing lists by `(relation.type, relation.target.casefold(), relation.target, relation.source.casefold(), relation.source)` and incoming lists by `(relation.type, relation.source.casefold(), relation.source, relation.target.casefold(), relation.target)`.

- [ ] **Step 4: Validate directly over declarations without constructing an ambiguous graph**

In `validate`, build `counts` and `known_ids` directly. Emit one REQ004 per duplicate ID, then inspect every authored relation for REQ005, then run current rationale/verification rules. Sort the final findings with:

```python
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def finding_key(item: Finding) -> tuple[object, ...]:
    location = item.location
    return (
        SEVERITY_ORDER.get(item.severity, 99),
        item.code,
        (item.object_id or "").casefold(),
        item.object_id or "",
        location.file.casefold() if location else "",
        location.file if location else "",
        location.line if location else 0,
        item.message,
    )
```

Use the first duplicate declaration's source as REQ004 location and the relation owner's source as REQ005 location. Do not call `RequirementsGraph.build` inside `validate`.

- [ ] **Step 5: Run graph, validation, and example tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_graph.py tests/test_validation.py tests/test_example_project.py -q
```

Expected: PASS; valid graph traversal is unchanged, and duplicates can no longer be mistaken for a valid graph.

- [ ] **Step 6: Record the graph-safety checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/graph.py src/quarto_needs/validation.py tests/test_graph.py tests/test_validation.py
  git commit -m "fix: reject duplicate requirement identifiers"
else
  echo "Checkpoint 4 verified; workspace has no Git metadata."
fi
```

---

### Task 5: Build one deterministic valid-or-invalid analysis result

**Files:**
- Create: `src/quarto_needs/analysis.py`
- Modify: `src/quarto_needs/snapshot.py`
- Create: `tests/fixtures/canonical/a-tests.qmd`
- Create: `tests/fixtures/canonical/z-requirements.qmd`
- Create: `tests/fixtures/canonical/invalid-duplicates.qmd`
- Create: `tests/test_analysis.py`

**Interfaces:**
- Produces: `analyze_project(root, files=None) -> AnalysisResult`, `analyze_objects(objects, reported_findings=None) -> AnalysisResult`, canonical ordering, immutable indexes, and legacy trace metrics.
- Invalid semantics: parser errors, duplicate IDs, unknown targets, and unsupported authored relation types yield `snapshot is None`; declarations and all located findings remain available.

- [ ] **Step 1: Create the canonical fixture with deliberately non-canonical file/ID order**

`tests/fixtures/canonical/a-tests.qmd`:

```qmd
::: {.need #Z-TC-001 type=test-case status=passed}
priority: medium
tags: verification; unicode

## Verifies autenticação

The test passes for valid credentials.
:::
```

`tests/fixtures/canonical/z-requirements.qmd`:

```qmd
::: {.need #M-NEED-001 type=stakeholder-need status=approved}
priority: medium
tags: identity; access

## Administrators need secure access

Administrative access must be protected.
:::

::: {.need #A-REQ-001 type=functional-requirement status=approved}
priority: high
tags:
  - authentication
  - security
derived-from: M-NEED-001
verified-by: Z-TC-001
rationale: Prevent unauthorized administrative access.

## Autenticação forte

The service shall authenticate administrators.
:::
```

`tests/fixtures/canonical/invalid-duplicates.qmd` declares `DUP-1` twice and makes the first declaration reference `UNKNOWN-1`, so one analysis must retain both REQ004 and REQ005.

- [ ] **Step 2: Write failing analysis-result tests**

```python
from collections import Counter
from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project

ROOT = Path(__file__).resolve().parents[1]


def test_analysis_snapshot_is_sorted_indexed_and_deeply_immutable() -> None:
    root = ROOT / "tests/fixtures/canonical"
    result = analyze_project(root, files=[root / "z-requirements.qmd", root / "a-tests.qmd"])
    assert result.valid is True
    assert result.snapshot is not None
    assert [item.id for item in result.snapshot.objects] == ["A-REQ-001", "M-NEED-001", "Z-TC-001"]
    assert [(item.source, item.authored_name, item.target) for item in result.snapshot.relations] == [
        ("A-REQ-001", "derived-from", "M-NEED-001"),
        ("A-REQ-001", "verified-by", "Z-TC-001"),
    ]
    assert result.snapshot.relations[0].v1_name == "derives-from"
    assert tuple(item.target for item in result.snapshot.outgoing["A-REQ-001"]) == ("M-NEED-001", "Z-TC-001")
    assert tuple(item.source for item in result.snapshot.incoming["Z-TC-001"]) == ("A-REQ-001",)
    with pytest.raises(TypeError):
        result.snapshot.objects_by_id["NEW"] = result.snapshot.objects[0]


def test_structurally_invalid_analysis_has_no_snapshot_and_keeps_all_declarations() -> None:
    source = ROOT / "tests/fixtures/canonical/invalid-duplicates.qmd"
    result = analyze_project(source.parent, files=[source])
    assert result.valid is False
    assert result.snapshot is None
    assert [item.id for item in result.declarations].count("DUP-1") == 2
    assert [(item.code, item.object_id) for item in result.findings if item.severity == "error"] == [
        ("REQ004", "DUP-1"),
        ("REQ005", "DUP-1"),
    ]


def test_analysis_is_independent_of_explicit_file_order() -> None:
    root = ROOT / "tests/fixtures/canonical"
    forward = analyze_project(root, files=[root / "a-tests.qmd", root / "z-requirements.qmd"])
    reverse = analyze_project(root, files=[root / "z-requirements.qmd", root / "a-tests.qmd"])
    assert forward.snapshot == reverse.snapshot


def test_analysis_reads_each_selected_source_once(monkeypatch: pytest.MonkeyPatch) -> None:
    root = ROOT / "tests/fixtures/canonical"
    selected = {root / "a-tests.qmd", root / "z-requirements.qmd"}
    reads: Counter[Path] = Counter()
    original = Path.read_text

    def counted(path: Path, *args: object, **kwargs: object) -> str:
        resolved = path.resolve()
        if resolved in {item.resolve() for item in selected}:
            reads[resolved] += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)
    result = analyze_project(root, files=selected)
    assert result.snapshot is not None
    assert reads == Counter({item.resolve(): 1 for item in selected})
```

- [ ] **Step 3: Run the analysis tests and verify the orchestration module is absent**

Run: `.venv/bin/python -m pytest tests/test_analysis.py -q`

Expected: FAIL on importing `quarto_needs.analysis`.

- [ ] **Step 4: Implement canonical sort keys and legacy coverage in `analysis.py`**

Use named helpers so exporters and tests do not duplicate ordering rules:

```python
def text_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def object_key(item: ObjectRecord) -> tuple[object, ...]:
    location = item.locations[0] if item.locations else None
    return (
        *text_key(item.id),
        location.file.casefold() if location else "",
        location.file if location else "",
        location.line if location else 0,
    )


def relation_key(item: RelationRecord) -> tuple[object, ...]:
    attributes = json.dumps(thaw_json(item.attributes), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (*text_key(item.source), item.v1_name, *text_key(item.target), item.authored_name, attributes)


def legacy_coverage(objects: tuple[ObjectRecord, ...], relations: tuple[RelationRecord, ...]) -> dict[str, object]:
    requirements = [item for item in objects if item.type.endswith("requirement")]
    outgoing = {item.id: [] for item in objects}
    for relation in relations:
        outgoing.setdefault(relation.source, []).append(relation)
    implemented = [item for item in requirements if any(rel.v1_name in {"implements", "implemented-by"} for rel in outgoing[item.id])]
    verified = [item for item in requirements if any(rel.v1_name in {"verified-by", "validated-by"} for rel in outgoing[item.id])]
    total = len(requirements)
    return {
        "requirements": total,
        "approved": sum(item.status == "approved" for item in requirements),
        "implemented": len(implemented),
        "verified": len(verified),
        "implementation_coverage": round(100 * len(implemented) / total, 1) if total else 100.0,
        "verification_coverage": round(100 * len(verified) / total, 1) if total else 100.0,
    }
```

- [ ] **Step 5: Implement `analyze_project` and `analyze_objects`**

The implementation sequence is fixed:

1. obtain one `DeclarationBatch`;
2. preserve every declaration and parser finding;
3. convert declarations to temporary legacy objects only to run the compatibility validator;
4. merge parser/validation findings and sort them with `finding_key`;
5. if any structural error code is `QND001`, `QND002`, `REQ004`, `REQ005`, or `REQ007`, return `AnalysisResult(declarations, findings, None)`;
6. otherwise resolve every token through `DEFAULT_RELATION_CATALOG`, build sorted `ObjectRecord`/`RelationRecord` tuples, and build mapping-proxy indexes whose values are sorted tuples;
7. return a snapshot with `generator_name="quarto-needs"`, `generator_version=quarto_needs.__version__`, and the catalog version.

`analyze_objects` converts each legacy DTO into an `ObjectDeclaration`. It uses `relation.authored_name or relation.type` and resolves that name through the catalog. Catch an unknown relation name and emit located structural `REQ007` (`Unsupported relation type <name> on <object-id>`) rather than leaking `ValueError`. A DTO without `source` produces `location=None`, an empty `ObjectRecord.locations`, empty relation provenance, schema-v1 `source: null`, and `href: #<id>`; never invent a memory-path location. If `reported_findings` is `None`, it runs all compatibility validation; if findings are supplied by a compatibility caller, it uses those semantic findings but still independently adds duplicate/unknown/unsupported-relation structural errors. This prevents `export_graph(..., findings=[])` from bypassing graph safety.

Do not compute semantic/content fingerprints in this task; those are the explicit Milestone 3 deliverable.

- [ ] **Step 6: Run analysis, parser, graph, and example tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_analysis.py tests/test_snapshot.py tests/test_parser.py tests/test_graph.py tests/test_validation.py tests/test_example_project.py -q
```

Expected: PASS. Reversing fixture file order produces an equal snapshot, and invalid declarations never produce indexes.

- [ ] **Step 7: Record the analysis-pipeline checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/analysis.py src/quarto_needs/snapshot.py tests/fixtures/canonical tests/test_analysis.py
  git commit -m "feat: build deterministic analysis snapshots"
else
  echo "Checkpoint 5 verified; workspace has no Git metadata."
fi
```

---

### Task 6: Write deterministic, atomic, v1-compatible JSON and Lua projections

**Files:**
- Modify: `src/quarto_needs/export.py`
- Create: `tests/fixtures/canonical/expected-needs-v1.json`
- Create: `tests/fixtures/canonical/expected-generated-index.lua`
- Modify: `tests/test_export.py`
- Modify: `tests/test_v1_contract.py`

**Interfaces:**
- Produces: `build_v1_payload`, `render_v1_json`, `write_v1_graph`, `render_lua_index`, `write_lua_index`, and internal `write_build_outputs`.
- Preserves: `coverage`, `export_graph`, `export_lua_index`, schema-v1 object/relation/backlink behavior, and HTML `href` generation.

- [ ] **Step 1: Write failing deterministic/golden/atomic tests**

```python
from quarto_needs.analysis import analyze_project
from quarto_needs.export import render_lua_index, render_v1_json, write_build_outputs, write_v1_graph
from quarto_needs.snapshot import AnalysisSnapshot


def test_v1_render_is_byte_identical_for_reversed_file_order() -> None:
    root = ROOT / "tests/fixtures/canonical"
    first = analyze_project(root, files=[root / "a-tests.qmd", root / "z-requirements.qmd"])
    second = analyze_project(root, files=[root / "z-requirements.qmd", root / "a-tests.qmd"])
    assert first.snapshot is not None and second.snapshot is not None
    assert render_v1_json(first.snapshot) == render_v1_json(second.snapshot)
    assert render_v1_json(first.snapshot).endswith("\n")
    assert render_lua_index(first.snapshot).endswith("\n")


def test_v1_nested_relations_exactly_equal_top_level_relations() -> None:
    snapshot = canonical_snapshot()
    payload = json.loads(render_v1_json(snapshot))
    nested = [relation for item in payload["objects"] for relation in item["relations"]]
    assert nested == payload["relations"]
    assert payload["relations"][0]["type"] == "derives-from"
    assert "authored_name" not in json.dumps(payload)


def test_v1_writer_replaces_destination_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = tmp_path / "needs.json"
    destination.write_text("sentinel", encoding="utf-8")
    replacements: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source: str | Path, target: str | Path) -> None:
        replacements.append((Path(source), Path(target)))
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", recording_replace)
    write_v1_graph(destination, canonical_snapshot())
    assert replacements and replacements[-1][1] == destination
    assert json.loads(destination.read_text(encoding="utf-8"))["schemaVersion"] == "1"
    assert not list(tmp_path.glob(".needs.json.*.tmp"))


def test_build_outputs_render_both_before_replacing_either_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    graph_path = tmp_path / "needs.json"
    index_path = tmp_path / "generated-index.lua"
    graph_path.write_text("old graph\n", encoding="utf-8")
    index_path.write_text("old index\n", encoding="utf-8")

    def fail_lua_render(snapshot: AnalysisSnapshot) -> str:
        raise TypeError("unsupported Lua index value")

    monkeypatch.setattr("quarto_needs.export.render_lua_index", fail_lua_render)
    with pytest.raises(TypeError, match="unsupported Lua index value"):
        write_build_outputs(graph_path, index_path, canonical_snapshot())
    assert graph_path.read_text(encoding="utf-8") == "old graph\n"
    assert index_path.read_text(encoding="utf-8") == "old index\n"


def test_canonical_fixture_matches_checked_in_bytes() -> None:
    snapshot = canonical_snapshot()
    assert render_v1_json(snapshot) == (FIXTURE / "expected-needs-v1.json").read_text(encoding="utf-8")
    assert render_lua_index(snapshot) == (FIXTURE / "expected-generated-index.lua").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run focused tests and verify the new writer API is absent**

Run: `.venv/bin/python -m pytest tests/test_export.py tests/test_v1_contract.py -q`

Expected: FAIL on missing render/write functions and golden files.

- [ ] **Step 3: Implement the v1 payload from the snapshot's single relation collection**

Use these projections:

```python
def relation_v1(item: RelationRecord) -> dict[str, object]:
    return {
        "type": item.v1_name,
        "source": item.source,
        "target": item.target,
        "attributes": thaw_json(item.attributes),
    }


def object_v1(item: ObjectRecord, outgoing: tuple[RelationRecord, ...]) -> dict[str, object]:
    source = item.locations[0] if item.locations else None
    href = f"{Path(source.file).with_suffix('').as_posix()}.html#{source.anchor or item.id}" if source else f"#{item.id}"
    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "status": item.status,
        "body": item.body,
        "rationale": item.rationale,
        "attributes": thaw_json(item.attributes),
        "relations": [relation_v1(relation) for relation in outgoing],
        "source": {
            "file": source.file,
            "line": source.line,
            "anchor": source.anchor,
        } if source else None,
        "href": href,
    }
```

`build_v1_payload(snapshot)` must use the already sorted snapshot order, create top-level relations by concatenating each object's sorted outgoing tuple so nested and top-level lists are exactly equal, and create backlinks for every object. Backlink entries are `{"source": relation.source, "type": relation.v1_name}` sorted by source/type.

Under `extensions.quartoNeeds`, emit:

```json
{
  "generator": {"name": "quarto-needs", "version": "0.1.0"},
  "relationCatalogVersion": "1",
  "relationCatalog": {
    "verified-by": {
      "directLabel": "Verified by",
      "inverseLabel": "Verifies",
      "semanticFamily": "verification",
      "sourceRole": "requirement",
      "targetRole": "test",
      "impactDirection": "source_to_target",
      "public": true
    }
  }
}
```

The example above shows one present relation. Emit one entry for each distinct `v1_name` present in the snapshot, sorted by name. For authored `derived-from`, project the `derives-from` catalog entry. If multiple authored names share a v1 name, assert their projected label/family/role metadata is identical or raise `ValueError`; do not let traversal order select a meaning.

- [ ] **Step 4: Implement canonical rendering and atomic replacement**

```python
def render_v1_json(snapshot: AnalysisSnapshot) -> str:
    return json.dumps(build_v1_payload(snapshot), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_atomic_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
```

`render_lua_index(snapshot)` sorts objects by snapshot order, escapes backslash/double-quote/newline/carriage-return, and renders exactly one `return {` table with ID/title/href/type/status fields and a final newline. Both write functions call `_write_atomic_text`.

`write_build_outputs(graph_path, index_path, snapshot)` first computes both rendered strings in memory, then calls `_write_atomic_text` for the graph and index. A serialization failure therefore changes neither existing file; each subsequent filesystem replacement remains individually atomic.

- [ ] **Step 5: Keep compatibility wrappers and legacy coverage exact**

- `coverage(objects)` converts through the same legacy metric logic and returns exactly the existing six keys.
- `export_graph(path, objects, findings)` calls `analyze_objects(objects, reported_findings=findings)`, raises `ValueError("Cannot export a structurally invalid requirements graph")` without touching `path` if invalid, and otherwise calls `write_v1_graph`; return remains `None`.
- `export_lua_index(path, objects)` uses `analyze_objects`, refuses invalid input without touching `path`, and writes the deterministic index; return remains `None`.

- [ ] **Step 6: Generate the two small canonical goldens once and inspect them**

After the renderer exists, run:

```bash
.venv/bin/python -c 'from pathlib import Path; from quarto_needs.analysis import analyze_project; from quarto_needs.export import render_lua_index, render_v1_json; root=Path("tests/fixtures/canonical"); result=analyze_project(root, files=[root/"a-tests.qmd", root/"z-requirements.qmd"]); assert result.snapshot is not None; print(render_v1_json(result.snapshot), end="")' > tests/fixtures/canonical/expected-needs-v1.json
.venv/bin/python -c 'from pathlib import Path; from quarto_needs.analysis import analyze_project; from quarto_needs.export import render_lua_index; root=Path("tests/fixtures/canonical"); result=analyze_project(root, files=[root/"a-tests.qmd", root/"z-requirements.qmd"]); assert result.snapshot is not None; print(render_lua_index(result.snapshot), end="")' > tests/fixtures/canonical/expected-generated-index.lua
```

Expected inspection:

- object IDs are `A-REQ-001`, `M-NEED-001`, `Z-TC-001`;
- Unicode text is unescaped;
- `derived-from` is retained only in internal tests, while v1 uses `derives-from`;
- nested relations concatenate to the exact top-level list;
- no absolute path or timestamp exists;
- relation-catalog metadata is namespaced.

The two generated files become reviewed fixtures; subsequent test runs must never rewrite them.

- [ ] **Step 7: Compare the refactored Aegis export to the frozen legacy projection**

Add:

```python
def test_refactored_aegis_export_preserves_v1_semantics() -> None:
    frozen = load_json(GOLDEN)
    result = analyze_project(ROOT / "examples/book")
    assert result.snapshot is not None
    current = json.loads(render_v1_json(result.snapshot))
    assert legacy_projection(current) == legacy_projection(frozen)
```

Run:

```bash
.venv/bin/python -m pytest tests/test_export.py tests/test_v1_contract.py -q
```

Expected: PASS. Differences are permitted only in deterministic ordering and `extensions.quartoNeeds`.

- [ ] **Step 8: Record the deterministic-writer checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/export.py tests/test_export.py tests/test_v1_contract.py tests/fixtures/canonical/expected-needs-v1.json tests/fixtures/canonical/expected-generated-index.lua
  git commit -m "feat: write deterministic schema v1 projections"
else
  echo "Checkpoint 6 verified; workspace has no Git metadata."
fi
```

---

### Task 7: Route every CLI command through one analysis pass

**Files:**
- Modify: `src/quarto_needs/cli.py`
- Modify: `tools/quarto_needs_pre_render.py`
- Create: `tests/test_cli.py`
- Modify: `tests/test_extension_sync.py`

**Interfaces:**
- Preserves: `scan`, `check`, `coverage`, `trace`, `export`, `build(root, quiet=False)`, and current exit-code behavior.
- Adds invariant: exactly one `analyze_project` call per invocation and no partial write on invalid structure.

- [ ] **Step 1: Write failing single-pass and no-clobber CLI tests**

```python
from quarto_needs import cli


def test_scan_analyzes_project_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_valid_project(tmp_path)
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path):
        nonlocal calls
        calls += 1
        return real_analyze(root)

    monkeypatch.setattr(cli, "analyze_project", counted)
    assert cli.main(["--root", str(tmp_path), "scan"]) == 0
    assert calls == 1
    assert (tmp_path / ".quarto-needs/needs.json").is_file()


def test_invalid_scan_does_not_replace_existing_graph(tmp_path: Path) -> None:
    write_duplicate_project(tmp_path)
    output = tmp_path / ".quarto-needs/needs.json"
    output.parent.mkdir(parents=True)
    output.write_text("sentinel\n", encoding="utf-8")
    assert cli.main(["--root", str(tmp_path), "scan"]) == 1
    assert output.read_text(encoding="utf-8") == "sentinel\n"


def test_trace_uses_snapshot_indexes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_trace_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "trace", "REQ-1"]) == 0
    assert capsys.readouterr().out == "Upstream:\nDownstream:\n  TC-1\n"
```

- [ ] **Step 2: Run focused tests and verify scan currently analyzes twice**

Run: `.venv/bin/python -m pytest tests/test_cli.py tests/test_extension_sync.py -q`

Expected: FAIL because `main(scan)` parses/validates and then `build` parses/validates again, and invalid build can write an ambiguous payload.

- [ ] **Step 3: Make `build` consume one result and write only valid snapshots**

```python
def build(root: Path, quiet: bool = False) -> int:
    result = analyze_project(root)
    if result.snapshot is None:
        if not quiet:
            print_findings(result.findings, stream=sys.stderr)
        return 1
    write_build_outputs(
        root / ".quarto-needs" / "needs.json",
        root / "_extensions" / "quarto-needs" / "generated-index.lua",
        result.snapshot,
    )
    if not quiet:
        metrics = result.snapshot.metrics
        print(f"Quarto-Needs: {len(result.snapshot.objects)} objects, {len(result.findings)} findings")
        print(
            f"Requirements: {metrics['requirements']} | "
            f"implemented: {metrics['implementation_coverage']}% | "
            f"verified: {metrics['verification_coverage']}%"
        )
    return 1 if any(item.severity == "error" for item in result.findings) else 0
```

Keep `main` from analyzing before the scan branch:

```python
if args.command == "scan":
    return build(root)
result = analyze_project(root)
```

For `check`, print findings even when invalid. For `coverage`, `trace`, and `export`, print structural findings to stderr and return 1 when `snapshot is None`. Unknown trace IDs continue returning 2. `export` calls `write_v1_graph` directly so it does not re-analyze.

Preserve transitive trace behavior with one shared breadth-first helper over immutable indexes:

```python
def _reachable(snapshot: AnalysisSnapshot, start: str, direction: str) -> list[str]:
    seen: set[str] = set()
    queue = deque([start])
    while queue:
        current = queue.popleft()
        relations = snapshot.outgoing.get(current, ()) if direction == "downstream" else snapshot.incoming.get(current, ())
        for relation in relations:
            candidate = relation.target if direction == "downstream" else relation.source
            if candidate not in seen and candidate != start:
                seen.add(candidate)
                queue.append(candidate)
    return sorted(seen, key=lambda item: (item.casefold(), item))
```

Add a three-node CLI test (`REQ-1 -> REQ-2 -> TC-1`) so both direct and transitive IDs must appear in the same order as the legacy graph traversal.

- [ ] **Step 4: Keep the pre-render helper as synchronization plus one `build` call**

`tools/quarto_needs_pre_render.py` already calls `build` once; retain that shape. Extend its tests to monkeypatch `build` and assert one call after `sync_extension`. Do not make the helper parse or validate separately.

- [ ] **Step 5: Run CLI and core regressions**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_extension_sync.py tests/test_export.py tests/test_analysis.py -q
```

Expected: PASS; every command analyzes once and invalid scan/export paths remain untouched.

- [ ] **Step 6: Record the single-pass CLI checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/cli.py tools/quarto_needs_pre_render.py tests/test_cli.py tests/test_extension_sync.py
  git commit -m "refactor: use one analysis per command"
else
  echo "Checkpoint 7 verified; workspace has no Git metadata."
fi
```

---

### Task 8: Cache the Lua graph and resolve links by output format

**Files:**
- Create: `_extensions/quarto-needs/data.lua`
- Modify: `_extensions/quarto-needs/views.lua`
- Modify: `_extensions/quarto-needs/shortcodes.lua`
- Create: `tests/test_lua_data.py`
- Modify: `tests/test_views_helpers.py`
- Modify: `tests/fixtures/views/.quarto-needs/needs.json`
- Modify: `tests/fixtures/views/index.qmd`
- Create: `tests/fixtures/views/nested/details.qmd`

**Interfaces:**
- Produces: cached `data.load`, `data.get`, `data.outgoing`, `data.incoming`, and pure `data.link_target`.
- Preserves: `views.load`, `views.link`, exact filters/sorting, and `{{< need ID title=true >}}`.

- [ ] **Step 1: Write failing Lua cache/index/link tests**

Create `tests/test_lua_data.py` using the existing `quarto pandoc --lua-filter` test pattern. Its Lua assertions must include:

```lua
local original_open = io.open
local opens = 0
io.open = function(path, mode)
  if path == __GRAPH_PATH__ then opens = opens + 1 end
  return original_open(path, mode)
end

local first, first_error = data.load(__GRAPH_PATH__)
local second, second_error = data.load(__GRAPH_PATH__)
assert(first_error == nil and second_error == nil)
assert(first == second, "cache must return the same graph table")
assert(opens == 1, "graph JSON must be opened once per process and path")
assert(data.get(first, "REQ-APPROVED").title == "Authenticate administrators")
assert(#data.outgoing(first, "REQ-APPROVED", "verified-by") == 1)
assert(#data.incoming(first, "TC-LOGIN", "verified-by") == 1)

local target = {id = "TC-LOGIN", href = "nested/details.html#TC-LOGIN", source = {file = "nested/details.qmd", anchor = "TC-LOGIN"}}
assert(data.link_target(target, {format = "html", current_input = "index.qmd"}) == "nested/details.html#TC-LOGIN")
assert(data.link_target(target, {format = "html", current_input = "nested/details.qmd"}) == "#TC-LOGIN")
assert(data.link_target(target, {format = "html", current_input = "chapters/trace.qmd"}) == "../nested/details.html#TC-LOGIN")
assert(data.link_target(target, {format = "docx", current_input = "index.qmd"}) == "#TC-LOGIN")
assert(data.link_target(target, {format = "pdf", current_input = "index.qmd"}) == "#TC-LOGIN")
```

- [ ] **Step 2: Run Lua helper tests and verify `data.lua` is missing**

Run: `.venv/bin/python -m pytest tests/test_lua_data.py tests/test_views_helpers.py -q`

Expected: FAIL because `data.lua` and the new APIs do not exist.

- [ ] **Step 3: Implement one global cache per normalized graph path**

In `data.lua`, share state across repeated `dofile` calls:

```lua
local M = {}
local CACHE_KEY = "__quarto_needs_data_cache_v1"
local cache = rawget(_G, CACHE_KEY)
if type(cache) ~= "table" or type(cache.by_path) ~= "table" or type(cache.by_graph) ~= "table" then
  cache = {
    by_path = {},
    by_graph = setmetatable({}, {__mode = "k"}),
  }
  rawset(_G, CACHE_KEY, cache)
end

local function build_entry(graph)
  local by_id, outgoing, incoming = {}, {}, {}
  for _, object in ipairs(graph.objects or {}) do
    by_id[tostring(object.id)] = object
  end
  for _, relation in ipairs(graph.relations or {}) do
    local source, target = tostring(relation.source), tostring(relation.target)
    outgoing[source] = outgoing[source] or {}
    incoming[target] = incoming[target] or {}
    table.insert(outgoing[source], relation)
    table.insert(incoming[target], relation)
  end
  local relation_key = function(item)
    return tostring(item.type) .. "\0" .. tostring(item.source) .. "\0" .. tostring(item.target)
  end
  for _, index in pairs({outgoing, incoming}) do
    for _, items in pairs(index) do
      table.sort(items, function(a, b) return relation_key(a) < relation_key(b) end)
    end
  end
  return {graph = graph, by_id = by_id, outgoing = outgoing, incoming = incoming}
end
```

`data.load(path)` normalizes the key with `pandoc.path.normalize(path)`, checks `cache.by_path`, opens/decodes once, then stores either the built entry or `{error = <exact message>}`. For a valid entry, also assign `cache.by_graph[entry.graph] = entry`. A missing/invalid file must keep returning the same meaningful error, not an empty graph. `get`, `outgoing`, and `incoming` take the graph table for compatibility, retrieve `cache.by_graph[graph]`, and optionally filter by emitted v1 relation type. Return a fresh result list from relation filters so callers cannot mutate the cached adjacency tuple order.

- [ ] **Step 4: Implement a pure POSIX relative-link resolver**

`data.link_target(object, options)` must:

1. choose `source.anchor or object.id` as the anchor;
2. for `docx`, `pdf`, `latex`, or non-HTML formats, return `#<anchor>`;
3. for HTML with `source.file`, change `.qmd` to `.html`, normalize `.` segments, reject `..` traversal above the project root, and calculate a path relative to the directory of `options.current_input`;
4. return only `#<anchor>` when current and target source files match;
5. for legacy objects without `source.file`, use non-empty `object.href`, falling back to `#<id>`.

Do not call the filesystem from `link_target`; the function is string-only and directly unit-tested.

- [ ] **Step 5: Make `views.lua` a compatible facade over cached data**

- Load `data.lua` once at module initialization.
- Keep `views.load()` returning `(graph, error)`.
- Add `views.get(graph, id)`, `views.outgoing(graph, id, relation_type)`, and `views.incoming(graph, id, relation_type)` delegates.
- Change `views.related` to delegate to the outgoing index.
- Change `views.link(object, label, options)` to create the Pandoc link with `data.link_target`.
- Derive default format from `quarto.doc.is_format`. Normalize `PANDOC_STATE.input_files[1]`; when it is absolute, strip the normalized `quarto.project.directory` prefix before passing `current_input` to `data.link_target`. Keep explicit options available in tests.
- Move the `assets_added` state behind a `_G.__quarto_needs_assets_added_v1` flag so separate `views.lua` instances created by Quarto filters/shortcodes register CSS/JavaScript only once per Pandoc process.

- [ ] **Step 6: Remove generated-index reads from the `need` shortcode**

Delete `load_index()` and the `index` local from `shortcodes.lua`. Resolve references through the graph cache:

```lua
local graph, message = views.load()
if not graph then
  quarto.log.warning(message)
  return pandoc.Span({pandoc.Str(id)}, pandoc.Attr("", {"need-ref", "need-ref-missing"}))
end
local object = views.get(graph, id)
if not object then
  quarto.log.warning("Unknown need ID: " .. id)
  return pandoc.Span({pandoc.Str(id)}, pandoc.Attr("", {"need-ref", "need-ref-missing"}))
end
return views.link(object, label)
```

Keep generating `generated-index.lua` for compatibility, but the bundled extension no longer uses it at runtime. Replace the matrix cell's direct `column_object.href` access with `views.link(column_object, "✓")`; all shortcode link creation must flow through `views.link`.

- [ ] **Step 7: Extend the view fixture for cross-page resolution**

Add complete `source` values to every object in the fixture JSON. Place `REQ-APPROVED`, `REQ-DRAFT`, and `REQ-UNPRIORITIZED` in `index.qmd`; place `TC-LOGIN` in `nested/details.qmd`. Add `{{< need TC-LOGIN title=true >}}` to the index. Ensure the JSON `href` remains the legacy HTML target and rendering uses the source-aware resolver.

- [ ] **Step 8: Run Lua, shortcode, HTML, and extension-sync tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_lua_data.py tests/test_views_helpers.py tests/test_quarto_views.py::test_filtered_table_list_and_count_render tests/test_extension_sync.py -q
```

Expected: PASS; the index HTML links to `nested/details.html#TC-LOGIN`, and the graph file is opened once per path in the Lua unit test.

- [ ] **Step 9: Record the cached-data checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add _extensions/quarto-needs/data.lua _extensions/quarto-needs/views.lua _extensions/quarto-needs/shortcodes.lua tests/test_lua_data.py tests/test_views_helpers.py tests/fixtures/views tests/test_quarto_views.py
  git commit -m "feat: cache Quarto graph and resolve format links"
else
  echo "Checkpoint 8 verified; workspace has no Git metadata."
fi
```

---

### Task 9: Render outgoing relations and backlinks on cards and via shortcode

**Files:**
- Create: `_extensions/quarto-needs/relations.lua`
- Modify: `_extensions/quarto-needs/needs.lua`
- Modify: `_extensions/quarto-needs/shortcodes.lua`
- Modify: `_extensions/quarto-needs/needs.css`
- Modify: `tests/fixtures/views/.quarto-needs/needs.json`
- Modify: `tests/fixtures/views/index.qmd`
- Modify: `tests/fixtures/views/nested/details.qmd`
- Modify: `tests/test_quarto_views.py`

**Interfaces:**
- Produces: `relations.render_for_card`, `relations.render_backlinks`, grouped direct/inverse labels, and `{{< need-backlinks ID >}}`.
- Static guarantee: the same essential relation text and IDs appear in HTML, DOCX, and PDF without JavaScript.

- [ ] **Step 1: Add failing HTML/card/backlink assertions**

Add `render_view_pages(tmp_path) -> tuple[str, str]`, which copies/renders the fixture once and returns `_site/index.html` plus `_site/nested/details.html`. Then add these tests:

```python
@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_need_cards_render_catalog_labeled_outgoing_and_incoming_relations(tmp_path: Path) -> None:
    index_html, details_html = render_view_pages(tmp_path)
    assert 'id="REQ-APPROVED"' in index_html
    assert "Need relations" in index_html
    assert "Verified by" in index_html
    assert 'href="nested/details.html#TC-LOGIN"' in index_html
    assert 'id="TC-LOGIN"' in details_html
    assert "Need backlinks" in details_html
    assert "Verifies" in details_html
    assert 'href="../index.html#REQ-APPROVED"' in details_html
    assert "No backlinks for REQ-DRAFT." in index_html


def test_need_backlinks_reports_unknown_id_without_empty_success_state(tmp_path: Path) -> None:
    index_html, _ = render_view_pages(tmp_path)
    assert "Unknown need ID: UNKNOWN-NEED" in index_html
    assert 'class="need-view-warning"' in index_html
```

Fixture shortcodes:

```qmd
{{< need-backlinks TC-LOGIN >}}
{{< need-backlinks REQ-DRAFT >}}
{{< need-backlinks UNKNOWN-NEED >}}
```

- [ ] **Step 2: Add failing DOCX/PDF static-content assertions**

Extend existing three-format tests:

```python
def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    return re.sub(r"<[^>]+>", " ", xml)


def test_relations_are_static_content_in_docx(tmp_path: Path) -> None:
    document = render_views_to(tmp_path, "docx")
    text = docx_text(document)
    assert "Need relations" in text
    assert "Verified by" in text
    assert "TC-LOGIN" in text
    assert "Need backlinks" in text
    assert "REQ-APPROVED" in text


def test_relations_are_static_content_in_pdf(tmp_path: Path) -> None:
    document = render_views_to(tmp_path, "pdf")
    text = subprocess.run(["pdftotext", str(document), "-"], check=True, text=True, capture_output=True).stdout
    assert "Need relations" in text
    assert "Verified by" in text
    assert "TC-LOGIN" in text
    assert "Need backlinks" in text
    assert "REQ-APPROVED" in text
```

Use the existing Quarto/LuaLaTeX/pdftotext skip conditions locally; Milestone 4 will provision an unskipped pinned rendering job.

- [ ] **Step 3: Run focused render tests and verify relation sections are absent**

Run:

```bash
.venv/bin/python -m pytest tests/test_quarto_views.py -q
```

Expected: FAIL on the new relation/backlink assertions; existing table/matrix/flow tests continue passing.

- [ ] **Step 4: Implement catalog-driven static relation groups**

`relations.lua` loads `views.lua` and exposes:

```lua
function M.render_for_card(graph, object_id)
  local blocks = {}
  append_direction(blocks, graph, object_id, views.outgoing(graph, object_id), "outgoing")
  append_direction(blocks, graph, object_id, views.incoming(graph, object_id), "incoming")
  return blocks
end


function M.render_backlinks(graph, object_id)
  local incoming = views.incoming(graph, object_id)
  if #incoming == 0 then
    return views.empty("No backlinks for " .. object_id .. ".")
  end
  return direction_div(graph, object_id, incoming, "incoming")
end
```

Read the catalog projection at `graph.extensions.quartoNeeds.relationCatalog[relation.type]`. Outgoing groups use `directLabel`; incoming groups use `inverseLabel`. If catalog metadata is absent, use the emitted relation type for outgoing and `Referenced by: <type>` for incoming. Group keys sort case-insensitively by label; relations inside a group sort by the opposite endpoint ID.

Each direction is a Pandoc `Div` with a visible heading (`Need relations` or `Need backlinks`) and a `DefinitionList`. Each target/source entry is `views.link(related_object)` plus its title. If the endpoint object is absent, render its ID as plain text and add `need-relation-missing`; never invent a link.

- [ ] **Step 5: Append both directions to every need card**

Refactor `needs.lua` to use `views.ensure_assets`, `views.badge`, and `relations.render_for_card` instead of its duplicate helper implementations. After constructing the existing body, load the graph and append the returned blocks:

```lua
local graph, message = views.load()
if graph then
  for _, block in ipairs(relations.render_for_card(graph, id)) do
    table.insert(body, block)
  end
else
  table.insert(body, views.warning(message))
end
```

Do not append empty outgoing/backlink headings. A card with neither direction remains visually unchanged apart from shared helper refactoring.

- [ ] **Step 6: Register `need-backlinks` with explicit error/empty states**

```lua
local function render_need_backlinks(args, kwargs)
  local id = pandoc.utils.stringify(args[1] or "")
  if id == "" then return views.warning("Missing need ID for need-backlinks.") end
  local graph, warning = graph_or_warning()
  if not graph then return warning end
  if not views.get(graph, id) then
    local message = "Unknown need ID: " .. id
    quarto.log.warning(message)
    return views.warning(message)
  end
  return relations.render_backlinks(graph, id)
end
```

Add `['need-backlinks'] = render_need_backlinks` to the shortcode table without changing existing keys.

- [ ] **Step 7: Add accessible relation styling**

Use existing color tokens and add layout only:

```css
.need-relations, .need-backlinks { margin-top: 1rem; padding-top: .75rem; border-top: 1px solid var(--need-border); }
.need-relations-title, .need-backlinks-title { margin: 0 0 .5rem; font-size: .95rem; }
.need-relation-groups { margin-bottom: 0; }
.need-relation-groups dt { font-weight: 650; }
.need-relation-groups dd { margin-bottom: .4rem; }
.need-relation-missing { text-decoration: underline wavy; }
```

Do not use color as the only directional cue; headings and labels remain text.

- [ ] **Step 8: Run all Lua and three-format tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_lua_data.py tests/test_views_helpers.py tests/test_flow_helpers.py tests/test_quarto_views.py tests/test_extension_sync.py -q
```

Expected: PASS. HTML contains source-aware links; DOCX/PDF contain static labels and IDs; no essential relation content depends on JavaScript.

- [ ] **Step 9: Record the backlinks checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add _extensions/quarto-needs/relations.lua _extensions/quarto-needs/needs.lua _extensions/quarto-needs/shortcodes.lua _extensions/quarto-needs/needs.css tests/fixtures/views tests/test_quarto_views.py
  git commit -m "feat: render need relations and backlinks"
else
  echo "Checkpoint 9 verified; workspace has no Git metadata."
fi
```

---

### Task 10: Synchronize the Aegis showcase, document regeneration, and pass the milestone gate

**Files:**
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Create: `CONTRIBUTING.md`
- Modify: `Makefile`
- Synchronize: `examples/book/_extensions/quarto-needs/*`
- Regenerate: `examples/book/.quarto-needs/needs.json`
- Regenerate: `examples/book/_extensions/quarto-needs/generated-index.lua`
- Modify: `tests/test_example_project.py`

**Interfaces:**
- Produces: current architecture/regeneration documentation, canonical example assets, and a repeatable Milestone 1 acceptance command set.

- [ ] **Step 1: Strengthen the Aegis integration test around visible backlinks**

After rendering HTML, read `requirements/system.html`. `IAM-SYS-001` already has outgoing `derives-from`/`implemented-by`/`verified-by` edges and incoming `derives-from` edges from functional requirements, so it exercises both directions without changing the example graph:

```python
system = (output / "requirements" / "system.html").read_text(encoding="utf-8")
assert "need-relations" in system
assert "Verified by" in functional
assert "Implemented by" in functional
assert "Need backlinks" in system
assert "Source for" in system
assert "IAM-FUN-001" in system
assert "need-ref-missing" not in "\n".join((index, traceability, matrix, functional, system))
```

- [ ] **Step 2: Add exact regeneration and acceptance commands to the docs**

README must contain these commands and explain their outputs:

```bash
make setup
make test
make sync-example
make check-example
make render-example-all
make preview-example
```

Document:

- schema-v1 remains the public Quarto projection;
- `extensions.quartoNeeds.relationCatalog` is additive;
- `generated-index.lua` is still emitted for external compatibility but bundled shortcodes use cached JSON;
- `need-backlinks` syntax, unknown-ID behavior, and empty state;
- HTML cross-page links versus anchor-only DOCX/PDF links;
- approved/passed green, disapproved/rejected/failed red, in-review amber, draft gray, implemented blue, verified teal, critical dark red, high orange, medium blue, low gray; every badge includes text.

`ARCHITECTURE.md` must show this sequence:

```text
QMD files -> DeclarationBatch -> AnalysisResult -> AnalysisSnapshot
                                               -> needs.json v1
                                               -> generated-index.lua
needs.json -> cached Lua indexes -> Pandoc-native cards/views -> HTML/DOCX/PDF
```

`CONTRIBUTING.md` must state the red-green-refactor order, canonical extension location, fixture update policy, no automatic golden rewrites, and full verification commands.

- [ ] **Step 3: Add an all-format Make target**

Update `.PHONY` and add:

```make
render-example-all:
	quarto render examples/book --to html
	quarto render examples/book --to docx
	quarto render examples/book --to pdf
```

Keep `render-example` as the current default-format shortcut. CI continues using the test extra and core suite; the pinned multi-version/unskipped Quarto jobs remain Milestone 4 work.

- [ ] **Step 4: Synchronize canonical extension assets and regenerate the graph twice**

Run:

```bash
make sync-example
sha256sum examples/book/.quarto-needs/needs.json examples/book/_extensions/quarto-needs/generated-index.lua
make sync-example
sha256sum examples/book/.quarto-needs/needs.json examples/book/_extensions/quarto-needs/generated-index.lua
```

Expected: both pairs of SHA-256 values are identical. The sync copies `data.lua` and `relations.lua`; the project-specific generated index remains generated rather than copied from the canonical extension.

- [ ] **Step 5: Validate schema and compatibility against the regenerated Aegis graph**

Run:

```bash
.venv/bin/python -m pytest tests/test_v1_contract.py tests/test_export.py tests/test_extension_sync.py -q
```

Expected: PASS; the new Aegis JSON validates and its legacy projection equals the frozen pre-refactor fixture.

- [ ] **Step 6: Run the complete Python/Lua/render test suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS with no unexpected skip on tools installed in the current environment. Quarto/Chrome/TeX skip guards remain only for environments where those executables truly are absent.

- [ ] **Step 7: Run public CLI smoke tests**

Run:

```bash
.venv/bin/quarto-needs --root examples/book scan
.venv/bin/quarto-needs --root examples/book check
.venv/bin/quarto-needs --root examples/book coverage
.venv/bin/quarto-needs --root examples/book trace IAM-FUN-001
.venv/bin/quarto-needs --root examples/book export --output .quarto-needs/needs-export.json
```

Expected:

- `scan`, `check`, `coverage`, and `export` exit 0;
- check reports zero structural errors;
- coverage retains the six legacy keys;
- trace prints sorted upstream/downstream IDs;
- `needs-export.json` is byte-identical to `needs.json` because both consume the same snapshot and writer.

Verify the last point:

```bash
cmp examples/book/.quarto-needs/needs.json examples/book/.quarto-needs/needs-export.json
```

Expected: no output and exit code 0.

- [ ] **Step 8: Render the Aegis book in all three formats**

Run:

```bash
make render-example-all
```

Expected: HTML, DOCX, and PDF renders exit 0. Generated documents contain need IDs, relation labels, and backlinks; HTML keeps colored text badges and working relative links. No render prints `need-ref-missing`, an unexpanded shortcode, raw Mermaid source, or a missing-graph warning.

- [ ] **Step 9: Verify the preview server is still alive**

Run:

```bash
curl --fail --silent --show-error http://127.0.0.1:8777/ >/dev/null
```

Expected: exit code 0. Do not stop or restart the existing preview process as part of this milestone.

- [ ] **Step 10: Record the Milestone 1 acceptance checkpoint conditionally**

Run:

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add README.md ARCHITECTURE.md CONTRIBUTING.md Makefile examples/book/.quarto-needs/needs.json examples/book/_extensions/quarto-needs tests/test_example_project.py
  git commit -m "docs: complete milestone one acceptance"
else
  echo "Milestone 1 verified; workspace has no Git metadata."
fi
```

Expected: every Milestone 1 acceptance gate is complete. Work on Milestone 2 starts only after this checkpoint, using a separate implementation plan.
