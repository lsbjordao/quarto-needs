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

