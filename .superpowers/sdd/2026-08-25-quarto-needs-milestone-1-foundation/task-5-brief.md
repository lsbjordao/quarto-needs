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

