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

