# Task 3: Fingerprints and the reference-date-bearing snapshot

> Extracted from `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`. This brief is your complete requirements.
> Use every value in it verbatim.

## Global Constraints (bind every task)

- Do not add a runtime dependency. `referencing` enters the `test` optional dependency group only; it already ships as a `jsonschema` dependency.
- One analysis per command invocation. `baseline create`, `diff`, and `impact` each call `analyze_project` exactly once, matching the Milestone 1 guarantee locked by `tests/test_cli.py`.
- Preserve every existing signature and documented behavior: `parse_qmd`, `parse_project`, `RequirementsGraph.build`, `validate`, `coverage`, `export_graph`, `export_lua_index`, `cli.build`, `build_v1_payload`, `write_build_outputs`, `report_from_snapshot`, `build_quality_report`, and every existing CLI command and shortcode.
- Preserve schema v1 exactly. Fingerprints and baselines are new, separately named and versioned schemas. Nothing in this milestone changes `needs.json` bytes for a project whose configuration and reference date are unchanged.
- Fingerprints exclude line numbers, `href` values, generated metrics, and every other derived value.
- Exit codes are stable: `0` success, `1` validation or policy failure, `2` invalid usage or configuration, `3` operational I/O or serialization failure.
- Generated artifacts are deterministic for a fixed configuration and a fixed reference date, and are written atomically through `export._write_atomic_text`.
- The workspace has no `.git` metadata. Do not initialize Git. Every task ends with a conditional checkpoint that records a commit only when the executor is inside a Git worktree.
- Do not stop or restart the preview server listening on `127.0.0.1:8777`.
- Milestone 3 adds no Quarto shortcode and no `extensions.quartoNeeds` projection for diff or impact. `need-graph` and the interactive graph remain Milestone 5A.

## Task 3

Fingerprints and the reference-date-bearing snapshot

**Files:**
- Create: `src/quarto_needs/fingerprints.py`
- Modify: `src/quarto_needs/snapshot.py`
- Modify: `src/quarto_needs/analysis.py:313-331`
- Create: `tests/test_fingerprints.py`

**Interfaces:**
- Consumes: `NeedsConfig.canonical_document()` and `rules.RULE_SET_VERSION` from Task 2.
- Produces:
  - `fingerprints.object_content_fingerprint(record: ObjectRecord) -> str`
  - `fingerprints.relation_authored_fingerprint(record: RelationRecord) -> str`
  - `fingerprints.relation_semantic_fingerprint(record: RelationRecord) -> str`
  - `fingerprints.configuration_fingerprint(config: NeedsConfig, *, relation_catalog_version: str) -> str`
  - `fingerprints.semantic_graph_fingerprint(objects: Iterable[ObjectRecord], relations: Iterable[RelationRecord], configuration: str) -> str`
  - `fingerprints.representation_fingerprint(relations: Iterable[RelationRecord]) -> str`
  - `AnalysisSnapshot.reference_date: str`, `.configuration_fingerprint: str`, `.semantic_graph_fingerprint: str`, `.representation_fingerprint: str`

- [ ] **Step 1: Write the failing fingerprint tests**

Create `tests/test_fingerprints.py`. The third test is the load-bearing one: an authored alias flip must be a representation change, never a semantic one.

```python
from __future__ import annotations

from quarto_needs import fingerprints
from quarto_needs.config import embedded_defaults
from quarto_needs.snapshot import LocationRecord, ObjectRecord, RelationRecord


def make_object(**overrides: object) -> ObjectRecord:
    base = dict(
        id="REQ-1",
        type="functional-requirement",
        title="Authenticate",
        status="approved",
        body="The service shall authenticate.",
        rationale="Protect data.",
        attributes={"priority": "high", "tags": "security"},
        locations=(LocationRecord("a.qmd", 10, "REQ-1"),),
    )
    base.update(overrides)
    return ObjectRecord(**base)


def make_relation(**overrides: object) -> RelationRecord:
    base = dict(
        source="REQ-1",
        authored_name="verified-by",
        catalog_name="verified-by",
        v1_name="verified-by",
        target="TC-1",
        semantic_family="verification",
        source_role="requirement",
        target_role="test",
        impact_direction="source_to_target",
        attributes={},
        provenance=(LocationRecord("a.qmd", 12, None),),
    )
    base.update(overrides)
    return RelationRecord(**base)


def test_object_fingerprint_ignores_line_numbers_and_file() -> None:
    """Provenance is not authored semantics; moving a need must not modify it."""
    moved = make_object(locations=(LocationRecord("b.qmd", 900, "REQ-1"),))

    assert fingerprints.object_content_fingerprint(make_object()) == \
        fingerprints.object_content_fingerprint(moved)


def test_object_fingerprint_changes_with_every_authored_field() -> None:
    """Each field the spec names must actually participate."""
    original = fingerprints.object_content_fingerprint(make_object())
    for field, value in (
        ("type", "system-requirement"),
        ("title", "Other"),
        ("status", "draft"),
        ("body", "Different body."),
        ("rationale", "Different rationale."),
        ("attributes", {"priority": "low", "tags": "security"}),
    ):
        assert fingerprints.object_content_fingerprint(make_object(**{field: value})) != original, field


def test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation() -> None:
    """REQ -verified-by-> TC and TC -verifies-> REQ are one semantic edge."""
    forward = make_relation()
    inverse = make_relation(
        source="TC-1",
        authored_name="verifies",
        catalog_name="verifies",
        v1_name="verifies",
        target="REQ-1",
        source_role="test",
        target_role="requirement",
        impact_direction="target_to_source",
    )

    assert fingerprints.relation_semantic_fingerprint(forward) == \
        fingerprints.relation_semantic_fingerprint(inverse)
    assert fingerprints.relation_authored_fingerprint(forward) != \
        fingerprints.relation_authored_fingerprint(inverse)


def test_semantic_relation_fingerprint_changes_with_family_and_endpoints() -> None:
    original = fingerprints.relation_semantic_fingerprint(make_relation())

    assert fingerprints.relation_semantic_fingerprint(make_relation(semantic_family="evidence")) != original
    assert fingerprints.relation_semantic_fingerprint(make_relation(target="TC-2")) != original
    assert fingerprints.relation_semantic_fingerprint(make_relation(attributes={"note": "x"})) != original


def test_graph_fingerprint_is_order_independent_and_configuration_sensitive() -> None:
    """Reordering declarations is not a change; changing policy is."""
    objects = [make_object(), make_object(id="REQ-2")]
    relations = [make_relation(), make_relation(target="TC-2")]
    configuration = fingerprints.configuration_fingerprint(
        embedded_defaults(), relation_catalog_version="1"
    )

    forward = fingerprints.semantic_graph_fingerprint(objects, relations, configuration)
    reversed_order = fingerprints.semantic_graph_fingerprint(
        list(reversed(objects)), list(reversed(relations)), configuration
    )
    other_configuration = fingerprints.semantic_graph_fingerprint(
        objects, relations, configuration="different"
    )

    assert forward == reversed_order
    assert forward != other_configuration


def test_configuration_fingerprint_tracks_catalog_and_rule_set_versions() -> None:
    """A catalog-only change must be visible as a configuration change."""
    config = embedded_defaults()

    assert fingerprints.configuration_fingerprint(config, relation_catalog_version="1") != \
        fingerprints.configuration_fingerprint(config, relation_catalog_version="2")
```

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_fingerprints.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'quarto_needs.fingerprints'`.

- [ ] **Step 3: Implement `fingerprints.py`**

```python
"""Pure content fingerprints over the canonical snapshot records.

Every fingerprint excludes line numbers, `href` values, generated metrics,
and any other derived data, so provenance changes and rendering changes can
never masquerade as semantic ones.
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .config import NeedsConfig
from .rules import RULE_SET_VERSION
from .snapshot import ObjectRecord, RelationRecord, thaw_json


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def object_content_fingerprint(record: ObjectRecord) -> str:
    return _digest(
        {
            "id": record.id,
            "type": record.type,
            "title": record.title,
            "body": record.body,
            "rationale": record.rationale,
            "status": record.status,
            "priority": record.priority,
            "tags": list(record.tags),
            "attributes": thaw_json(record.attributes),
        }
    )


def relation_authored_fingerprint(record: RelationRecord) -> str:
    return _digest(
        {
            "source": record.source,
            "authored_name": record.authored_name,
            "target": record.target,
            "attributes": thaw_json(record.attributes),
        }
    )


def relation_semantic_fingerprint(record: RelationRecord) -> str:
    """Identity of the edge itself, independent of which end authored it.

    Endpoints are sorted by role, so an alias flip that preserves the roles
    yields the same fingerprint and is classified as representation-only.
    """
    endpoints = sorted(
        (
            {"id": record.source, "role": record.source_role},
            {"id": record.target, "role": record.target_role},
        ),
        key=lambda item: (item["role"], item["id"]),
    )
    return _digest(
        {
            "family": record.semantic_family,
            "endpoints": endpoints,
            "attributes": thaw_json(record.attributes),
        }
    )


def configuration_fingerprint(
    config: NeedsConfig, *, relation_catalog_version: str
) -> str:
    return _digest(
        {
            "configuration": config.canonical_document(),
            "relationCatalogVersion": relation_catalog_version,
            "ruleSetVersion": RULE_SET_VERSION,
        }
    )


def semantic_graph_fingerprint(
    objects: Iterable[ObjectRecord],
    relations: Iterable[RelationRecord],
    configuration: str,
) -> str:
    return _digest(
        {
            "objects": sorted(object_content_fingerprint(item) for item in objects),
            "relations": sorted(relation_semantic_fingerprint(item) for item in relations),
            "configuration": configuration,
        }
    )


def representation_fingerprint(relations: Iterable[RelationRecord]) -> str:
    return _digest(sorted(relation_authored_fingerprint(item) for item in relations))
```

- [ ] **Step 4: Run the fingerprint tests**

Run: `.venv/bin/python -m pytest tests/test_fingerprints.py -q`

Expected: PASS.

- [ ] **Step 5: Write the failing snapshot-field test**

Add to `tests/test_snapshot.py`:

```python
def test_snapshot_records_reference_date_and_fingerprints(tmp_path: Path) -> None:
    """Baselines need every comparison axis from the snapshot itself."""
    from quarto_needs.analysis import analyze_project
    from quarto_needs.config import reference_date

    (tmp_path / "a.qmd").write_text(
        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
    )

    snapshot = analyze_project(tmp_path).snapshot

    assert snapshot is not None
    assert snapshot.reference_date == reference_date().isoformat()
    assert len(snapshot.configuration_fingerprint) == 64
    assert len(snapshot.semantic_graph_fingerprint) == 64
    assert len(snapshot.representation_fingerprint) == 64
```

- [ ] **Step 6: Run it and verify it fails**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py -q -k reference_date_and_fingerprints`

Expected: FAIL with `AttributeError: 'AnalysisSnapshot' object has no attribute 'reference_date'`.

- [ ] **Step 7: Add the snapshot fields**

In `src/quarto_needs/snapshot.py`, append these fields to `AnalysisSnapshot` after `relation_catalog_version`. They have defaults so every existing direct construction in tests keeps working:

```python
    reference_date: str = ""
    configuration_fingerprint: str = ""
    semantic_graph_fingerprint: str = ""
    representation_fingerprint: str = ""
```

- [ ] **Step 8: Populate them in the existing single pass**

In `src/quarto_needs/analysis.py`, the fingerprints must be computed from the **final** snapshot, after rule findings are merged, because a rule finding does not change content but the draft/final split would otherwise leave the fields stale. Replace the `draft`/`snapshot` block at lines 313-331:

```python
    configuration = fingerprints.configuration_fingerprint(
        effective_config, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
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
        reference_date=reference_date().isoformat(),
        configuration_fingerprint=configuration,
        semantic_graph_fingerprint=fingerprints.semantic_graph_fingerprint(
            objects, relations, configuration
        ),
        representation_fingerprint=fingerprints.representation_fingerprint(relations),
    )
    rule_findings = run_rules(draft, effective_config)
    snapshot = (
        replace(draft, findings=_merge_findings(findings, rule_findings))
        if rule_findings
        else draft
    )
    return AnalysisResult(declarations, snapshot.findings, snapshot)
```

Add `from . import fingerprints` and `from .config import reference_date` to the imports (keep the existing `config` imports intact).

- [ ] **Step 9: Run the snapshot and analysis tests**

Run: `.venv/bin/python -m pytest tests/test_snapshot.py tests/test_analysis.py -q`

Expected: PASS.

- [ ] **Step 10: Verify `needs.json` bytes did not move**

Run:

```bash
sha256sum examples/book/.quarto-needs/needs.json
make sync-example >/dev/null 2>&1
sha256sum examples/book/.quarto-needs/needs.json
```

Expected: identical hashes. Fingerprints live in the snapshot only; nothing in this task may reach the v1 projection.

- [ ] **Step 11: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 12: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/fingerprints.py src/quarto_needs/snapshot.py src/quarto_needs/analysis.py tests/test_fingerprints.py tests/test_snapshot.py
  git commit -m "feat: add semantic fingerprints to the snapshot"
else
  echo "Checkpoint 3 verified; workspace has no Git metadata."
fi
```
