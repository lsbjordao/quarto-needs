# Quarto-Needs Milestone 3 Baseline, Diff, and Impact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver canonical baseline files, semantic fingerprints, classified diffs with relocation handling, and union-graph impact traversal with explicit paths, all reachable from a stable CLI.

**Architecture:** Fingerprints are pure functions over the existing immutable `AnalysisSnapshot`. A baseline is that snapshot plus its fingerprints, reference date, and configuration fingerprint, serialized canonically and written atomically. `diff` and `impact` are pure comparisons between a loaded baseline and a current snapshot; two guards — configuration fingerprint and reference date — decide which categories of delta are meaningful before any comparison runs. The CLI is the only layer that touches the filesystem.

**Tech Stack:** Python 3.10+, standard-library dataclasses/hashlib/json, pytest, jsonschema with `referencing` as a test-only dependency

**Spec:** `docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md` — sections "Canonical model and determinism", "Baseline, semantic diff, and impact", "Milestone 3 design decisions", "CLI and failure semantics", and the gate under "### Milestone 3"

## Global Constraints

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

## File Map

| Area | Files | Responsibility after Milestone 3 |
|---|---|---|
| Fingerprints | `src/quarto_needs/fingerprints.py` | Pure SHA-256 fingerprints: object content, relation authored, relation semantic, semantic graph, representation, configuration. |
| Configuration canonicalization | `src/quarto_needs/config.py` | Existing loader plus `NeedsConfig.canonical_document()`, the single canonical form the configuration fingerprint hashes. |
| Rule-set version | `src/quarto_needs/rules.py` | Existing registry plus `RULE_SET_VERSION`. |
| Snapshot | `src/quarto_needs/snapshot.py`, `src/quarto_needs/analysis.py` | `AnalysisSnapshot` gains `reference_date` and the fingerprint fields, populated in the existing single pass. |
| Baseline artifact | `src/quarto_needs/baseline.py`, `schemas/baseline-v1.schema.json` | Baseline dataclass, canonical serialization, atomic write with overwrite refusal, load with validation, and the `valid: false` diagnostic variant. |
| Diff | `src/quarto_needs/diff.py`, `schemas/diff-v1.schema.json` | Guards, object/relation/relocation classification, findings/metrics/gate regressions, typed `DiffReport`. |
| Impact | `src/quarto_needs/impact.py`, `schemas/impact-v1.schema.json` | Union-graph traversal producing explicit paths, distance, and classification. |
| Commands | `src/quarto_needs/cli.py` | `baseline create`, `baseline inspect`, `diff`, `impact`, each with `--format text|json`. |
| Tests | `tests/test_fingerprints.py`, `tests/test_baseline.py`, `tests/test_diff.py`, `tests/test_impact.py`, `tests/test_cli.py`, `tests/test_config.py`, `tests/test_relations.py`, `tests/test_v1_contract.py`, `tests/test_example_project.py` | Unit, golden, round-trip, gate-scenario, and CLI integration coverage. |
| Golden artifact | `examples/book/baselines/quarto-needs.json` | The checked-in Aegis baseline; it must always diff clean against the published book. |
| Docs and packaging | `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `Makefile`, `pyproject.toml` | Baseline/diff/impact reference, pipeline diagram, fixture policy, acceptance targets. |

---

### Task 1: Clear the inherited Milestone 1 debts

The three schema validators this milestone adds must not be built on a
deprecated API, so the migration comes first. The two test probes are
recorded as open debt in the Milestone 1 ledger and are cheap to close
while the same files are open.

**Files:**
- Modify: `tests/test_v1_contract.py:50-62`
- Modify: `tests/test_relations.py`
- Modify: `tests/test_cli.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `tests/test_v1_contract.py::envelope_validator() -> Draft202012Validator` built on `referencing`, reused by Tasks 4, 8, and 10.

- [ ] **Step 1: Add `referencing` to the test extra**

In `pyproject.toml`, add `"referencing"` to the `test` optional dependency list alongside `pytest` and `jsonschema`. Do not add it to runtime dependencies.

- [ ] **Step 2: Run the contract tests and record the deprecation warnings**

Run: `.venv/bin/python -m pytest tests/test_v1_contract.py -q`

Expected: PASS with exactly 2 `jsonschema.RefResolver` `DeprecationWarning` entries. Record the count; Step 4 asserts it reaches zero.

- [ ] **Step 3: Rewrite `envelope_validator` on `referencing`**

Replace the `RefResolver` import and helper in `tests/test_v1_contract.py`:

```python
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


def envelope_validator() -> Draft202012Validator:
    schema = load_json(SCHEMAS / "needs-envelope-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource(
        "https://quarto-needs.dev/schema/needs.schema.json",
        Resource.from_contents(
            load_json(SCHEMAS / "needs.schema.json"),
            default_specification=DRAFT202012,
        ),
    )
    return Draft202012Validator(schema, registry=registry)
```

- [ ] **Step 4: Run the contract tests and verify the warnings are gone**

Run: `.venv/bin/python -m pytest tests/test_v1_contract.py -q -W error::DeprecationWarning`

Expected: PASS with no deprecation warning. Promoting the warning to an error proves the migration rather than merely hiding it.

- [ ] **Step 5: Write the failing `authored_name` boundary test**

The v1 writer must never leak the additive `Relation.authored_name` field. Add to `tests/test_relations.py`:

```python
def test_engineering_object_to_dict_omits_authored_name() -> None:
    """authored_name is additive internal state and must stay out of v1 output."""
    from quarto_needs.model import EngineeringObject, Relation

    obj = EngineeringObject(id="REQ-1", type="functional-requirement", title="T", status="draft")
    obj.relations.append(Relation("derives-from", "REQ-1", "STK-1", {}))
    obj.relations[0].authored_name = "derived-from"

    payload = obj.to_dict()

    assert payload["relations"][0]["type"] == "derives-from"
    assert "authored_name" not in payload["relations"][0]
```

- [ ] **Step 6: Run it**

Run: `.venv/bin/python -m pytest tests/test_relations.py::test_engineering_object_to_dict_omits_authored_name -v`

Expected: PASS. This is a characterization test — the behavior is already correct and this pins it. If it fails, the constructor signature drifted; read `src/quarto_needs/model.py` and adapt the construction, not the assertion.

- [ ] **Step 7: Write the deferred CLI probes**

Add to `tests/test_cli.py`:

```python
@pytest.mark.parametrize("arguments", [["check"], ["coverage"], ["export"], ["trace", "DUP-1"]])
def test_invalid_input_still_runs_exactly_one_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    """A structurally invalid project must not be re-analyzed while reporting."""
    write_duplicate_project(tmp_path)
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    cli.main(["--root", str(tmp_path), *arguments])
    assert calls == 1


def test_trace_orders_ids_case_insensitively_and_survives_cycles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Traversal must terminate on a cycle among non-start nodes and sort
    the reachable set case-insensitively.

    REQ-A (start) --references--> sub-b --references--> SUB-C
                                     ^-------references-------/

    The B<->C subcycle excludes the start node, so a `seen`-set regression
    (dropping the visited check while keeping only the `candidate != start`
    filter) would loop forever bouncing between sub-b and SUB-C. The two
    downstream ids are also cased so that a plain `sorted()` ("SUB-C" before
    "sub-b", since uppercase sorts before lowercase in ASCII) disagrees with
    the casefold-keyed order the CLI is supposed to produce ("sub-b" before
    "SUB-C").
    """
    (tmp_path / "cycle.qmd").write_text(
        "::: {.need #REQ-A type=need status=draft}\n"
        "references: sub-b\n"
        "\n## A\nA body.\n:::\n"
        "\n"
        "::: {.need #sub-b type=need status=draft}\n"
        "references: SUB-C\n"
        "\n## B\nB body.\n:::\n"
        "\n"
        "::: {.need #SUB-C type=need status=draft}\n"
        "references: sub-b\n"
        "\n## C\nC body.\n:::\n",
        encoding="utf-8",
    )

    assert cli.main(["--root", str(tmp_path), "trace", "REQ-A"]) == 0

    output = capsys.readouterr().out
    assert output == (
        "Upstream:\n"
        "Downstream:\n"
        "  sub-b\n"
        "  SUB-C\n"
    )
```

> **Plan correction.** The first version of this probe used a two-node cycle
> `REQ-A <-> req-b`. That test passed for the wrong reason: when one node of
> the cycle is the traversal's start, `_reachable`'s separate
> `candidate != start` filter already excludes the only back-edge, so the
> visited set is never load-bearing and deleting it would not hang the test.
> The subcycle must exclude `start`, and the reachable set needs two
> differently-cased IDs or the casefold sort key goes untested.

- [ ] **Step 8: Run the probes**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "invalid_input_still_runs or survives_cycles"`

Expected: PASS. If the cycle test hangs, traversal lacks a visited set — that is a real defect; fix `cli` traversal to track visited IDs before continuing.

- [ ] **Step 9: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS with **zero** warnings. The two permitted `RefResolver` warnings that every previous milestone carried are now gone.

- [ ] **Step 10: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add pyproject.toml tests/test_v1_contract.py tests/test_relations.py tests/test_cli.py
  git commit -m "chore: clear milestone one test debts"
else
  echo "Checkpoint 1 verified; workspace has no Git metadata."
fi
```

---

### Task 2: Canonical configuration form and rule-set version

**Files:**
- Modify: `src/quarto_needs/config.py`
- Modify: `src/quarto_needs/rules.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `NeedsConfig.canonical_document() -> dict[str, object]` and `rules.RULE_SET_VERSION: str`, both consumed by `fingerprints.configuration_fingerprint` in Task 3.

- [ ] **Step 1: Write the failing canonicalization tests**

Add to `tests/test_config.py`:

```python
def test_canonical_document_is_order_independent(tmp_path: Path) -> None:
    """Two spellings of the same policy must canonicalize identically."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / ".quarto-needs.toml").write_text(
        'profile = "strict"\n'
        '[types.functional-requirement]\nrequired-attributes = ["priority", "tags"]\n'
        '[types.test-case]\nrequired-attributes = ["tags"]\n',
        encoding="utf-8",
    )
    (second / ".quarto-needs.toml").write_text(
        'profile = "strict"\n'
        '[types.test-case]\nrequired-attributes = ["tags"]\n'
        '[types.functional-requirement]\nrequired-attributes = ["priority", "tags"]\n',
        encoding="utf-8",
    )

    # Compare the serialized form: dict equality ignores key order, so it would
    # hold even with every sorted() call deleted.
    assert json.dumps(load_config(first).canonical_document()) == json.dumps(
        load_config(second).canonical_document()
    )


def test_canonical_document_excludes_presence_and_path(tmp_path: Path) -> None:
    """Presence controls artifact projection, not graph semantics."""
    (tmp_path / ".quarto-needs.toml").write_text("", encoding="utf-8")

    from_file = load_config(tmp_path).canonical_document()
    embedded = embedded_defaults().canonical_document()

    assert from_file == embedded
    assert "present" not in from_file
    assert not any("quarto-needs.toml" in str(value) for value in from_file.values())


def test_canonical_document_reflects_every_policy_section(tmp_path: Path) -> None:
    """A change in any supported section must change the canonical document."""
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "advisory"\n'
        '[types.functional-requirement]\nrequired-attributes = ["priority"]\n'
        '[relations."verified-by"]\nallowed-target-types = ["test-case"]\n'
        '[governance]\ntest-types = ["test-case"]\n'
        '[rules.REQ011]\nenabled = true\n'
        '[queries.q]\nall = [{ field = "status", op = "eq", value = "approved" }]\n'
        '[gates]\nmax-errors = 3\n',
        encoding="utf-8",
    )

    document = load_config(tmp_path).canonical_document()

    assert document["profile"] == "advisory"
    assert document["types"]["functional-requirement"]["required-attributes"] == ["priority"]
    assert document["relations"]["verified-by"]["allowed-target-types"] == ["test-case"]
    assert document["governance"]["test-types"] == ["test-case"]
    assert document["rules"]["REQ011"]["enabled"] is True
    assert "q" in document["queries"]
    assert document["gates"]["max-errors"] == 3
```

```python
def test_canonical_document_rejects_a_non_json_query_value(tmp_path: Path) -> None:
    """A bare TOML date must fail as configuration, not as a raw TypeError."""
    (tmp_path / ".quarto-needs.toml").write_text(
        '[queries.q]\nall = [{ field = "status", op = "eq", value = 2026-01-01 }]\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        load_config(tmp_path).canonical_document()
```

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py -q -k canonical_document`

Expected: FAIL with `AttributeError: 'NeedsConfig' object has no attribute 'canonical_document'`.

- [ ] **Step 3: Implement `canonical_document`**

Add as a method on `NeedsConfig` in `src/quarto_needs/config.py`. Every container is converted to a plain, sorted, JSON-safe structure so the fingerprint hashes one spelling per policy:

```python
    def canonical_document(self) -> dict[str, object]:
        """The single canonical form the configuration fingerprint hashes.

        Excludes `present`, which controls artifact projection rather than
        graph semantics. The configuration file's path is never stored on this
        object, so there is nothing to exclude there.
        """
        # tomllib turns a bare `2026-01-01` into a `date`, which `freeze_json`
        # rejects. Query grammar validation only runs later, in
        # `materialize_queries`, so without this the fingerprint would raise an
        # uncontrolled TypeError instead of the documented exit code 2.
        try:
            queries = {
                name: thaw_json(freeze_json(dict(source)))
                for name, source in sorted(self.named_query_sources.items())
            }
        except TypeError as error:
            raise _fail(
                f"[queries] contains a value that is not valid JSON: {error}"
            ) from error
        return {
            "profile": self.profile,
            "types": {
                name: {"required-attributes": list(self.required_attributes[name])}
                for name in sorted(self.required_attributes)
            },
            "relations": {
                name: {
                    "allowed-source-types": list(policy.allowed_source_types),
                    "allowed-target-types": list(policy.allowed_target_types),
                    "minimum-per-source": policy.minimum_per_source,
                    "maximum-per-source": policy.maximum_per_source,
                }
                for name, policy in sorted(self.relation_policies.items())
            },
            "governance": {
                "test-types": list(self.test_types),
                "risk-types": list(self.risk_types),
                "successful-test-statuses": list(self.successful_test_statuses),
                "ineffective-endpoint-statuses": list(self.ineffective_endpoint_statuses),
                "expiry-attribute": self.expiry_attribute,
            },
            "rules": {
                code: {"enabled": setting.enabled, "severity": setting.severity}
                for code, setting in sorted(self.rule_settings.items())
            },
            "queries": queries,
            "gates": {
                "scope": self.gates.scope,
                "max-errors": self.gates.max_errors,
                "require-risk-mitigation": self.gates.require_risk_mitigation,
                "min-implementation-trace": self.gates.min_implementation_trace,
                "min-implementation-effective": self.gates.min_implementation_effective,
                "min-verification-trace": self.gates.min_verification_trace,
                "min-verification-successful": self.gates.min_verification_successful,
                "min-evidence": self.gates.min_evidence,
            },
        }
```

Add `from .snapshot import freeze_json, thaw_json` to the imports. `freeze_json` sorts nested query mappings deterministically; `thaw_json` returns plain JSON containers.

- [ ] **Step 4: Add the rule-set version**

In `src/quarto_needs/rules.py`, next to the `RULES` registry:

```python
# Bumped whenever a rule is added, removed, or its default severity changes.
# The configuration fingerprint includes it so a rule-catalog change is never
# mistaken for a project change.
RULE_SET_VERSION = "1"
```

Add `"RULE_SET_VERSION"` to that module's `__all__` if one exists; otherwise no export change is needed.

- [ ] **Step 5: Run the config tests**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 7: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/config.py src/quarto_needs/rules.py tests/test_config.py
  git commit -m "feat: add canonical configuration document and rule set version"
else
  echo "Checkpoint 2 verified; workspace has no Git metadata."
fi
```

---

### Task 3: Fingerprints and the reference-date-bearing snapshot

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
        ("id", "REQ-2"),
        ("type", "system-requirement"),
        ("title", "Other"),
        ("status", "draft"),
        ("body", "Different body."),
        ("rationale", "Different rationale."),
        # Vary priority and tags separately so each computed property is proven
        # to participate on its own.
        ("attributes", {"priority": "low", "tags": "security"}),
        ("attributes", {"priority": "high", "tags": "authentication"}),
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
    assert fingerprints.relation_semantic_fingerprint(make_relation(source="REQ-2")) != original
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

---

### Task 4: Baseline artifact — schema, serialization, and load

**Files:**
- Create: `src/quarto_needs/baseline.py`
- Create: `schemas/baseline-v1.schema.json`
- Create: `tests/test_baseline.py`

**Interfaces:**
- Consumes: every fingerprint helper and snapshot field from Task 3; `quality.report_from_snapshot` from Milestone 2; `export._write_atomic_text`.
- Produces:
  - `baseline.BaselineError(Exception)`
  - `baseline.build_baseline(snapshot: AnalysisSnapshot, config: NeedsConfig, *, queries: Mapping[str, Sequence[str]] | None = None) -> dict[str, object]`
  - `baseline.build_invalid_baseline(result: AnalysisResult, config: NeedsConfig) -> dict[str, object]`
  - `baseline.render_baseline(payload: dict[str, object]) -> str`
  - `baseline.write_baseline(path: Path, payload: dict[str, object], *, force: bool = False) -> None`
  - `baseline.load_baseline(path: Path) -> dict[str, object]`

- [ ] **Step 1: Write the baseline JSON Schema**

Create `schemas/baseline-v1.schema.json`. It is a separate, separately versioned schema — it never references the v1 graph schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schema/baseline-v1.schema.json",
  "title": "Quarto-Needs baseline v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "generator", "relationCatalogVersion", "ruleSetVersion", "referenceDate", "configurationFingerprint", "valid"],
  "properties": {
    "schemaVersion": {"const": "1"},
    "generator": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "version"],
      "properties": {"name": {"type": "string"}, "version": {"type": "string"}}
    },
    "relationCatalogVersion": {"type": "string"},
    "ruleSetVersion": {"type": "string"},
    "referenceDate": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
    "configurationFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "semanticGraphFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "representationFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "valid": {"type": "boolean"},
    "objects": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "type", "title", "status", "body", "rationale", "attributes", "location", "contentFingerprint"],
        "properties": {
          "id": {"type": "string"},
          "type": {"type": "string"},
          "title": {"type": "string"},
          "status": {"type": "string"},
          "body": {"type": "string"},
          "rationale": {"type": "string"},
          "attributes": {"type": "object"},
          "location": {
            "type": ["object", "null"],
            "additionalProperties": false,
            "required": ["file", "line"],
            "properties": {
              "file": {"type": "string"},
              "line": {"type": "integer"},
              "anchor": {"type": ["string", "null"]}
            }
          },
          "contentFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        }
      }
    },
    "relations": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["source", "authoredName", "target", "semanticFamily", "sourceRole", "targetRole", "attributes", "authoredFingerprint", "semanticFingerprint"],
        "properties": {
          "source": {"type": "string"},
          "authoredName": {"type": "string"},
          "target": {"type": "string"},
          "semanticFamily": {"type": "string"},
          "sourceRole": {"type": "string"},
          "targetRole": {"type": "string"},
          "impactDirection": {"type": "string"},
          "attributes": {"type": "object"},
          "authoredFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
          "semanticFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        }
      }
    },
    "findings": {"type": "array", "items": {"type": "object"}},
    "declarations": {"type": "array", "items": {"type": "object"}},
    "report": {"type": "object"}
  }
}
```

- [ ] **Step 2: Write the failing baseline tests**

Create `tests/test_baseline.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs import baseline
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "baseline-v1.schema.json"


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=functional-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "rationale: Protect data.\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n## Login test\nSigns a user in.\n"
        ":::\n",
        encoding="utf-8",
    )


def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def build(root: Path) -> dict[str, object]:
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return baseline.build_baseline(result.snapshot, config)


def test_baseline_validates_against_its_schema(tmp_path: Path) -> None:
    write_project(tmp_path)
    validator().validate(build(tmp_path))


def test_baseline_carries_both_comparison_axes(tmp_path: Path) -> None:
    """Configuration and reference date are what make a round trip stable."""
    write_project(tmp_path)
    payload = build(tmp_path)

    assert payload["valid"] is True
    assert len(payload["configurationFingerprint"]) == 64
    assert payload["referenceDate"]
    assert payload["ruleSetVersion"] == "1"


def test_baseline_stores_authored_content_not_only_fingerprints(tmp_path: Path) -> None:
    """Diff reports modifications by field, which needs the field values."""
    write_project(tmp_path)
    payload = build(tmp_path)

    requirement = next(item for item in payload["objects"] if item["id"] == "REQ-1")
    assert requirement["title"] == "Authenticate"
    assert requirement["rationale"].startswith("Protect")
    assert requirement["attributes"]["priority"] == "high"
    assert requirement["location"]["file"] == "needs.qmd"


def test_baseline_render_is_byte_stable(tmp_path: Path) -> None:
    write_project(tmp_path)

    assert baseline.render_baseline(build(tmp_path)) == baseline.render_baseline(build(tmp_path))


def test_write_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    """An overwritten baseline is unrecoverable without version control."""
    write_project(tmp_path)
    payload = build(tmp_path)
    destination = tmp_path / "baselines" / "quarto-needs.json"
    baseline.write_baseline(destination, payload)
    sentinel = destination.read_text(encoding="utf-8")

    with pytest.raises(baseline.BaselineError):
        baseline.write_baseline(destination, payload)

    assert destination.read_text(encoding="utf-8") == sentinel
    baseline.write_baseline(destination, payload, force=True)


def test_load_round_trips_and_rejects_malformed_input(tmp_path: Path) -> None:
    write_project(tmp_path)
    payload = build(tmp_path)
    destination = tmp_path / "b.json"
    baseline.write_baseline(destination, payload)

    assert baseline.load_baseline(destination) == payload

    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(baseline.BaselineError):
        baseline.load_baseline(broken)

    wrong_version = tmp_path / "v2.json"
    wrong_version.write_text(json.dumps({"schemaVersion": "2"}), encoding="utf-8")
    with pytest.raises(baseline.BaselineError):
        baseline.load_baseline(wrong_version)


def test_invalid_baseline_preserves_declarations_and_findings(tmp_path: Path) -> None:
    """The diagnostic artifact exists so `inspect` can explain the failure."""
    (tmp_path / "dup.qmd").write_text(
        "::: {.need #D-1 type=need status=draft}\n\n## A\nA.\n:::\n"
        "\n::: {.need #D-1 type=need status=draft}\n\n## B\nB.\n:::\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is None

    payload = baseline.build_invalid_baseline(result, config)

    validator().validate(payload)
    assert payload["valid"] is False
    assert payload["declarations"]
    assert any(finding["code"] == "REQ004" for finding in payload["findings"])
    assert "objects" not in payload
    assert "semanticGraphFingerprint" not in payload
```

- [ ] **Step 3: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_baseline.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'quarto_needs.baseline'`.

- [ ] **Step 4: Implement `baseline.py`**

```python
"""The baseline artifact: a canonical snapshot plus its comparison axes.

A baseline stores authored content, not only fingerprints, because `diff`
reports semantic modifications by field and cannot name a field it never saw.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import quarto_needs

from . import fingerprints
from .analysis import AnalysisResult
from .config import NeedsConfig
from .export import _write_atomic_text
from .quality import report_from_snapshot
from .relations import DEFAULT_RELATION_CATALOG
from .rules import RULE_SET_VERSION
from .snapshot import AnalysisSnapshot, LocationRecord, thaw_json

SCHEMA_VERSION = "1"
DEFAULT_BASELINE_PATH = Path("baselines") / "quarto-needs.json"


class BaselineError(Exception):
    """A baseline could not be written, read, or trusted."""


def _location(location: LocationRecord | None) -> dict[str, object] | None:
    if location is None:
        return None
    return {"file": location.file, "line": location.line, "anchor": location.anchor}


def _header(reference_date: str, configuration: str) -> dict[str, object]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generator": {"name": "quarto-needs", "version": quarto_needs.__version__},
        "relationCatalogVersion": DEFAULT_RELATION_CATALOG.version,
        "ruleSetVersion": RULE_SET_VERSION,
        "referenceDate": reference_date,
        "configurationFingerprint": configuration,
    }


def build_baseline(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    queries: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    payload = _header(snapshot.reference_date, snapshot.configuration_fingerprint)
    payload["semanticGraphFingerprint"] = snapshot.semantic_graph_fingerprint
    payload["representationFingerprint"] = snapshot.representation_fingerprint
    payload["valid"] = True
    payload["objects"] = [
        {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "status": item.status,
            "body": item.body,
            "rationale": item.rationale,
            "attributes": thaw_json(item.attributes),
            "location": _location(item.locations[0] if item.locations else None),
            "contentFingerprint": fingerprints.object_content_fingerprint(item),
        }
        for item in snapshot.objects
    ]
    payload["relations"] = [
        {
            "source": item.source,
            "authoredName": item.authored_name,
            "target": item.target,
            "semanticFamily": item.semantic_family,
            "sourceRole": item.source_role,
            "targetRole": item.target_role,
            "impactDirection": item.impact_direction,
            "attributes": thaw_json(item.attributes),
            "authoredFingerprint": fingerprints.relation_authored_fingerprint(item),
            "semanticFingerprint": fingerprints.relation_semantic_fingerprint(item),
        }
        for item in snapshot.relations
    ]
    payload["findings"] = [finding.to_dict() for finding in snapshot.findings]
    payload["report"] = report_from_snapshot(snapshot, config, queries=queries).to_dict()
    return payload


def build_invalid_baseline(result: AnalysisResult, config: NeedsConfig) -> dict[str, object]:
    """The explicitly requested diagnostic artifact.

    It is never accepted by `diff` or `impact`: structural failures make graph
    comparison ambiguous. It exists so `baseline inspect` can explain why.
    """
    from .config import reference_date

    configuration = fingerprints.configuration_fingerprint(
        config, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    payload = _header(reference_date().isoformat(), configuration)
    payload["valid"] = False
    payload["declarations"] = [
        {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "status": item.status,
            "location": _location(item.location),
        }
        for item in result.declarations
    ]
    payload["findings"] = [finding.to_dict() for finding in result.findings]
    return payload


def render_baseline(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_baseline(path: Path, payload: dict[str, object], *, force: bool = False) -> None:
    path = Path(path)
    if path.exists() and not force:
        raise BaselineError(f"{path} already exists; pass --force to overwrite it")
    _write_atomic_text(path, render_baseline(payload))


def load_baseline(path: Path) -> dict[str, object]:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise BaselineError(f"Could not read {path}: {error}") from error
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise BaselineError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise BaselineError(f"{path} is not a baseline document")
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise BaselineError(
            f"{path} declares baseline schema {payload.get('schemaVersion')!r}; "
            f"this build reads {SCHEMA_VERSION!r}"
        )
    return payload
```

- [ ] **Step 5: Run the baseline tests**

Run: `.venv/bin/python -m pytest tests/test_baseline.py -q`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 7: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/baseline.py schemas/baseline-v1.schema.json tests/test_baseline.py
  git commit -m "feat: add the canonical baseline artifact"
else
  echo "Checkpoint 4 verified; workspace has no Git metadata."
fi
```

---

### Task 5: `baseline create` and `baseline inspect`

**Files:**
- Modify: `src/quarto_needs/cli.py:186-205`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: every `baseline` function from Task 4.
- Produces: `cli.main(["baseline", "create", ...])` and `cli.main(["baseline", "inspect", <path>])`, both honoring `--format text|json`.

- [ ] **Step 1: Write the failing CLI tests**

Add to `tests/test_cli.py`:

```python
def test_baseline_create_writes_the_default_path_with_one_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_valid_project(tmp_path)
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
    assert calls == 1

    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["schemaVersion"] == "1"


def test_baseline_create_refuses_to_clobber(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
    destination = tmp_path / "baselines" / "quarto-needs.json"
    sentinel = destination.read_text(encoding="utf-8")

    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 2
    assert destination.read_text(encoding="utf-8") == sentinel
    assert "--force" in capsys.readouterr().err

    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--force"]) == 0


def test_baseline_create_refuses_invalid_input_without_the_flag(
    tmp_path: Path, capsys
) -> None:
    """Structural failure must not silently become a comparison baseline."""
    write_duplicate_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 1
    assert not (tmp_path / "baselines" / "quarto-needs.json").exists()
    assert "REQ004" in capsys.readouterr().err


def test_baseline_create_allow_invalid_writes_a_diagnostic_artifact(tmp_path: Path) -> None:
    write_duplicate_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"]) == 0

    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
    assert payload["valid"] is False
    assert payload["declarations"]


def test_baseline_inspect_reports_both_variants(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    destination = str(tmp_path / "baselines" / "quarto-needs.json")

    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination, "--format", "json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["valid"] is True
    assert summary["objects"] == 3
    assert summary["referenceDate"]

    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination]) == 0
    assert "objects" in capsys.readouterr().out


def test_baseline_inspect_reports_a_missing_file_as_usage_error(tmp_path: Path) -> None:
    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", str(tmp_path / "nope.json")]) == 2
```

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k baseline`

Expected: FAIL with `SystemExit: 2` from argparse — the `baseline` command does not exist.

- [ ] **Step 3: Register the nested subcommand**

In `main`, after the `query` parser block and before `args = parser.parse_args(argv)`:

```python
    baseline_parser = sub.add_parser("baseline", help="Create or inspect a canonical baseline")
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_command", required=True)
    baseline_create = baseline_sub.add_parser("create", help="Write a baseline for the current graph")
    baseline_create.add_argument("--output", default=str(DEFAULT_BASELINE_PATH))
    baseline_create.add_argument("--force", action="store_true", help="Overwrite an existing baseline")
    baseline_create.add_argument(
        "--allow-invalid",
        action="store_true",
        help="Write a diagnostic artifact for a structurally invalid project",
    )
    baseline_create.add_argument("--format", choices=("text", "json"), default="text")
    baseline_inspect = baseline_sub.add_parser("inspect", help="Summarize an existing baseline")
    baseline_inspect.add_argument("baseline")
    baseline_inspect.add_argument("--format", choices=("text", "json"), default="text")
```

Add to the imports: `from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline`.

- [ ] **Step 4: Implement the two handlers**

Add above `main`:

```python
def _baseline_destination(root: Path, output: str) -> Path:
    candidate = Path(output)
    return candidate if candidate.is_absolute() else root / candidate


def _baseline_create(root: Path, args, config: NeedsConfig) -> int:
    result = analyze_project(root, config=config)
    if result.snapshot is None:
        print_findings(result.findings, stream=sys.stderr)
        if not args.allow_invalid:
            return 1
        payload = build_invalid_baseline(result, config)
    else:
        payload = build_baseline(
            result.snapshot, config, queries=materialize_queries(config, result.snapshot)
        )
    destination = _baseline_destination(root, args.output)
    try:
        write_baseline(destination, payload, force=args.force)
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Could not write baseline: {error}", file=sys.stderr)
        return 3
    if args.format == "json":
        print(json.dumps({"path": str(destination), "valid": payload["valid"]}, indent=2, sort_keys=True))
    else:
        state = "valid" if payload["valid"] else "diagnostic (valid: false)"
        print(f"Wrote {state} baseline to {destination}")
    return 0


def _baseline_summary(payload: dict[str, object]) -> dict[str, object]:
    return {
        "valid": payload["valid"],
        "referenceDate": payload["referenceDate"],
        "configurationFingerprint": payload["configurationFingerprint"],
        "semanticGraphFingerprint": payload.get("semanticGraphFingerprint"),
        "objects": len(payload.get("objects", payload.get("declarations", []))),
        "relations": len(payload.get("relations", [])),
        "findings": len(payload.get("findings", [])),
    }


def _baseline_inspect(args) -> int:
    try:
        payload = load_baseline(Path(args.baseline))
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    summary = _baseline_summary(payload)
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    print(f"Baseline {args.baseline}")
    print(f"  valid: {summary['valid']}")
    print(f"  reference date: {summary['referenceDate']}")
    print(f"  objects: {summary['objects']}")
    print(f"  relations: {summary['relations']}")
    print(f"  findings: {summary['findings']}")
    return 0
```

- [ ] **Step 5: Route the command**

In `main`, next to the existing `quality` and `query` dispatch:

```python
    if args.command == "baseline":
        if args.baseline_command == "inspect":
            return _baseline_inspect(args)
        return _baseline_create(root, args, config)
```

Place it **before** the shared `result = analyze_project(root, config=config)` line, so `baseline` never analyzes twice and `inspect` never analyzes at all.

- [ ] **Step 6: Run the CLI tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`

Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 8: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/cli.py tests/test_cli.py
  git commit -m "feat: add baseline create and inspect commands"
else
  echo "Checkpoint 5 verified; workspace has no Git metadata."
fi
```

---

### Task 6: Diff engine — guards, objects, relations, relocation

**Files:**
- Create: `src/quarto_needs/diff.py`
- Create: `tests/test_diff.py`

**Interfaces:**
- Consumes: `baseline.load_baseline` output shape from Task 4; fingerprint helpers from Task 3.
- Produces:
  - `diff.DiffReport` dataclass with `.to_dict()`
  - `diff.compare(baseline_payload: dict[str, object], snapshot: AnalysisSnapshot, config: NeedsConfig, *, recompute: bool = False) -> DiffReport`
  - `diff.DiffError(Exception)`

- [ ] **Step 1: Write the failing structural tests**

Create `tests/test_diff.py`. The first three tests are the acceptance gate in miniature.

```python
from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs import baseline, diff
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

REQUIREMENT = (
    "::: {{.need #REQ-1 type=system-requirement status=approved priority=high}}\n"
    "verified-by: TC-1\n"
    "\n## Authenticate\n{body}\n"
    "\n### Rationale\nProtect data.\n"
    ":::\n"
)
TEST_CASE = "::: {.need #TC-1 type=test-case status=passed}\n\n## Login\nSigns in.\n:::\n"


def write(root: Path, *, body: str = "The service shall authenticate.", order: str = "requirement-first", file: str = "needs.qmd") -> None:
    for existing in root.glob("*.qmd"):
        existing.unlink()
    blocks = [REQUIREMENT.format(body=body), TEST_CASE]
    if order != "requirement-first":
        blocks.reverse()
    (root / file).write_text("\n".join(blocks), encoding="utf-8")


def snapshot_of(root: Path):
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return result.snapshot, config


def baseline_of(root: Path) -> dict[str, object]:
    snapshot, config = snapshot_of(root)
    return baseline.build_baseline(snapshot, config)


def test_identical_input_produces_an_empty_diff(tmp_path: Path) -> None:
    """The round-trip guarantee the milestone gate names."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert report.is_empty()
    assert report.notices == ()


def test_reordering_declarations_is_not_a_change(tmp_path: Path) -> None:
    """Swapping two blocks in a file changes nothing semantic."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, order="test-first")
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert report.modified == ()
    assert report.relocated == ()
    assert report.is_empty()


def test_moving_a_need_to_another_file_is_relocation_only(tmp_path: Path) -> None:
    """File change is a relocation record; content is untouched."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, file="moved.qmd")
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert report.modified == ()
    assert {item["id"] for item in report.relocated} == {"REQ-1", "TC-1"}
    moved = next(item for item in report.relocated if item["id"] == "REQ-1")
    assert moved["from"]["file"] == "needs.qmd"
    assert moved["to"]["file"] == "moved.qmd"
    assert "line" in moved["from"] and "line" in moved["to"]


def test_editing_a_body_is_a_modification_named_by_field(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, body="The service shall authenticate every administrator.")
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert [item["id"] for item in report.modified] == ["REQ-1"]
    assert report.modified[0]["fields"] == ["body"]
    assert report.relocated == ()


def test_added_and_removed_objects_are_classified(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / "extra.qmd").write_text(
        "::: {.need #REQ-2 type=functional-requirement status=draft}\n\n## Second\nBody.\n:::\n",
        encoding="utf-8",
    )
    (tmp_path / "needs.qmd").write_text(
        REQUIREMENT.format(body="The service shall authenticate.").replace("verified-by: TC-1\n", ""),
        encoding="utf-8",
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert report.added_objects == ("REQ-2",)
    assert report.removed_objects == ("TC-1",)


def test_a_changed_id_is_removal_plus_addition(tmp_path: Path) -> None:
    """Rename detection is deliberately excluded; it is inherently heuristic."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / "needs.qmd").write_text(
        REQUIREMENT.format(body="The service shall authenticate.").replace("#REQ-1", "#REQ-9")
        + "\n" + TEST_CASE,
        encoding="utf-8",
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert "REQ-9" in report.added_objects
    assert "REQ-1" in report.removed_objects
    assert report.modified == ()
```

- [ ] **Step 2: Write the failing guard tests**

Append to `tests/test_diff.py`:

```python
def test_configuration_change_suppresses_derived_deltas(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert "configuration-changed" in report.notices
    assert report.findings_added == ()
    assert report.gate_regressions == ()


def test_reference_date_change_suppresses_date_derived_deltas(tmp_path: Path) -> None:
    """Evidence coverage and REQ015 depend on the date, not on authored content."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    before = {**before, "referenceDate": "1999-01-01"}
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert "reference-date-changed" in report.notices
    assert report.metric_deltas == ()
    assert report.findings_added == ()


def test_recompute_clears_the_guards(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    before = {**before, "referenceDate": "1999-01-01"}
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config, recompute=True)

    assert report.notices == ()
    assert report.recomputed is True


def test_recompute_does_not_manufacture_derived_deltas_from_a_config_change(tmp_path: Path) -> None:
    """The baseline stores its derived results; they cannot be re-derived, so a
    config-only change must stay silent even under recompute.

    REQ-2 is approved but unverified, so verification coverage is 1 of 2 (50%).
    The baseline is taken under the default configuration (no verification
    gate); only then does the configuration grow a 100.0 threshold. Authored
    content never moves — any derived delta is manufactured by the config edit.
    """
    write(tmp_path)
    (tmp_path / "extra.qmd").write_text(
        "::: {.need #REQ-2 type=system-requirement status=approved priority=low}\n"
        "\n## Second\nSecond body.\n"
        "\n### Rationale\nSecond why.\n"
        ":::\n",
        encoding="utf-8",
    )
    before = baseline_of(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        "[gates]\nmin-verification-trace = 100.0\n", encoding="utf-8"
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config, recompute=True)

    assert report.notices == ()
    assert report.modified == ()
    assert report.gate_regressions == ()
    assert report.metric_deltas == ()
    assert report.findings_added == ()


def test_configuration_change_still_compares_authored_relations(tmp_path: Path) -> None:
    """Authored comparison keeps running; only the derived deltas stop."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text('profile = "strict"\n', encoding="utf-8")
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert "configuration-changed" in report.notices
    assert report.added_relations == ()
    assert report.removed_relations == ()
    assert report.representation_changes == ()
    assert report.modified == ()


def test_recompute_reresolves_baseline_relations_through_the_catalog(tmp_path: Path) -> None:
    """Stored families are not trusted; authored names are resolved again."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    poisoned = {
        **before,
        "relations": [
            {**item, "semanticFamily": "bogus", "semanticFingerprint": "0" * 64}
            for item in before["relations"]
        ],
    }
    snapshot, config = snapshot_of(tmp_path)

    assert diff.compare(poisoned, snapshot, config).added_relations != ()
    assert diff.compare(poisoned, snapshot, config, recompute=True).added_relations == ()


def test_an_invalid_baseline_is_never_comparable(tmp_path: Path) -> None:
    write(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    with pytest.raises(diff.DiffError):
        diff.compare({"schemaVersion": "1", "valid": False}, snapshot, config)
```

- [ ] **Step 3: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_diff.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'quarto_needs.diff'`.

- [ ] **Step 4: Implement the report and the guards**

Create `src/quarto_needs/diff.py`:

```python
"""Classified comparison between a baseline and the current snapshot.

Two guards run before any comparison. A changed configuration or a changed
reference date means the derived numbers were produced under different rules,
so reporting their deltas as project changes would be a lie; the diff says so
and suppresses them instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from . import fingerprints
from .config import NeedsConfig
from .quality import report_from_snapshot
from .snapshot import AnalysisSnapshot

SCHEMA_VERSION = "1"

OBJECT_FIELDS = ("type", "title", "status", "body", "rationale", "attributes")


class DiffError(Exception):
    """The two sides cannot be compared."""


@dataclass(frozen=True, slots=True)
class DiffReport:
    baseline_reference_date: str
    current_reference_date: str
    recomputed: bool
    notices: tuple[str, ...]
    added_objects: tuple[str, ...]
    removed_objects: tuple[str, ...]
    modified: tuple[Mapping[str, object], ...]
    relocated: tuple[Mapping[str, object], ...]
    added_relations: tuple[Mapping[str, object], ...]
    removed_relations: tuple[Mapping[str, object], ...]
    representation_changes: tuple[Mapping[str, object], ...]
    findings_added: tuple[Mapping[str, object], ...]
    findings_removed: tuple[Mapping[str, object], ...]
    metric_deltas: tuple[Mapping[str, object], ...]
    gate_regressions: tuple[Mapping[str, object], ...]

    def is_empty(self) -> bool:
        return not (
            self.added_objects
            or self.removed_objects
            or self.modified
            or self.relocated
            or self.added_relations
            or self.removed_relations
            or self.representation_changes
            or self.findings_added
            or self.findings_removed
            or self.metric_deltas
            or self.gate_regressions
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "referenceDate": {
                "baseline": self.baseline_reference_date,
                "current": self.current_reference_date,
            },
            "recomputed": self.recomputed,
            "notices": list(self.notices),
            "objects": {
                "added": list(self.added_objects),
                "removed": list(self.removed_objects),
                "modified": [dict(item) for item in self.modified],
                "relocated": [dict(item) for item in self.relocated],
            },
            "relations": {
                "added": [dict(item) for item in self.added_relations],
                "removed": [dict(item) for item in self.removed_relations],
                "representationChanged": [dict(item) for item in self.representation_changes],
            },
            "findings": {
                "added": [dict(item) for item in self.findings_added],
                "removed": [dict(item) for item in self.findings_removed],
            },
            "metrics": [dict(item) for item in self.metric_deltas],
            "gates": {"regressed": [dict(item) for item in self.gate_regressions]},
            "empty": self.is_empty(),
        }
```

- [ ] **Step 5: Implement object and relocation classification**

Append to `diff.py`:

```python
def _baseline_objects(payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    return {str(item["id"]): item for item in payload.get("objects", [])}


def _current_object(record) -> dict[str, object]:
    from .snapshot import thaw_json

    return {
        "id": record.id,
        "type": record.type,
        "title": record.title,
        "status": record.status,
        "body": record.body,
        "rationale": record.rationale,
        "attributes": thaw_json(record.attributes),
        "location": (
            {
                "file": record.locations[0].file,
                "line": record.locations[0].line,
                "anchor": record.locations[0].anchor,
            }
            if record.locations
            else None
        ),
        "contentFingerprint": fingerprints.object_content_fingerprint(record),
    }


def _classify_objects(
    before: Mapping[str, Mapping[str, object]], after: Mapping[str, Mapping[str, object]]
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    added = tuple(sorted(set(after) - set(before), key=lambda item: (item.casefold(), item)))
    removed = tuple(sorted(set(before) - set(after), key=lambda item: (item.casefold(), item)))
    modified: list[dict[str, object]] = []
    relocated: list[dict[str, object]] = []
    for object_id in sorted(set(before) & set(after), key=lambda item: (item.casefold(), item)):
        old, new = before[object_id], after[object_id]
        if old["contentFingerprint"] != new["contentFingerprint"]:
            fields = [name for name in OBJECT_FIELDS if old.get(name) != new.get(name)]
            modified.append({"id": object_id, "fields": fields})
        old_location = old.get("location") or {}
        new_location = new.get("location") or {}
        # Relocation is keyed on the declaring file. A line-only shift is not a
        # record: fingerprints already ignore line numbers, and one inserted
        # paragraph would otherwise relocate every object below it.
        if old_location.get("file") != new_location.get("file"):
            relocated.append({"id": object_id, "from": old_location, "to": new_location})
    return added, removed, tuple(modified), tuple(relocated)
```

- [ ] **Step 6: Implement relation classification**

Append to `diff.py`:

```python
def _relation_entry(item: Mapping[str, object]) -> dict[str, object]:
    return {
        "source": item["source"],
        "authoredName": item["authoredName"],
        "target": item["target"],
        "semanticFamily": item["semanticFamily"],
    }


def _current_relations(snapshot: AnalysisSnapshot) -> list[dict[str, object]]:
    return [
        {
            "source": record.source,
            "authoredName": record.authored_name,
            "target": record.target,
            "semanticFamily": record.semantic_family,
            "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
            "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
        }
        for record in snapshot.relations
    ]


def _classify_relations(
    before: Sequence[Mapping[str, object]],
    after: Sequence[Mapping[str, object]],
    *,
    key: str = "semanticFingerprint",
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    """Classify by `key`.

    Semantic fingerprints are the default. When the configuration changed, the
    caller keys on `authoredFingerprint` instead: a catalog change can move
    families and roles, so semantic fingerprints from the two sides are not
    comparable, and the spec requires authored tuples in that case.
    """
    before_semantic = {str(item[key]): item for item in before}
    after_semantic = {str(item[key]): item for item in after}
    added = tuple(
        _relation_entry(after_semantic[key])
        for key in sorted(set(after_semantic) - set(before_semantic))
    )
    removed = tuple(
        _relation_entry(before_semantic[key])
        for key in sorted(set(before_semantic) - set(after_semantic))
    )
    # Same edge, different authored spelling: informational, never a graph change.
    representation = tuple(
        {
            **_relation_entry(after_semantic[key]),
            "from": before_semantic[key]["authoredName"],
            "to": after_semantic[key]["authoredName"],
        }
        for key in sorted(set(before_semantic) & set(after_semantic))
        if before_semantic[key]["authoredFingerprint"] != after_semantic[key]["authoredFingerprint"]
    )
    return added, removed, representation
```

- [ ] **Step 7: Run the structural tests**

Run: `.venv/bin/python -m pytest tests/test_diff.py -q -k "identical or reordering or moving or editing or added_and_removed or changed_id"`

Expected: FAIL — `compare` does not exist yet. Task 7 adds it. Confirm the failure is `AttributeError: module 'quarto_needs.diff' has no attribute 'compare'` and not an error inside the helpers.

- [ ] **Step 8: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/diff.py tests/test_diff.py
  git commit -m "feat: add diff classification helpers"
else
  echo "Checkpoint 6 verified; workspace has no Git metadata."
fi
```

---

### Task 7: Diff engine — findings, metrics, gates, and `compare`

**Files:**
- Modify: `src/quarto_needs/diff.py`
- Modify: `tests/test_diff.py`

**Interfaces:**
- Consumes: the helpers and `DiffReport` from Task 6.
- Produces: `diff.compare(baseline_payload, snapshot, config, *, recompute=False) -> DiffReport`, consumed by Task 8.

- [ ] **Step 1: Write the failing derived-delta tests**

Append to `tests/test_diff.py`:

```python
def test_new_findings_are_reported_when_the_configuration_is_stable(tmp_path: Path) -> None:
    """A warning that appears with no policy change is a real regression."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    # Drop the rationale: REQ002 fires, and nothing about the policy moved.
    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        ":::\n" + "\n" + TEST_CASE,
        encoding="utf-8",
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    assert any(item["code"] == "REQ002" for item in report.findings_added)
    assert report.notices == ()


def test_metric_deltas_name_the_scope_and_strength(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    # Remove the verification edge: verification coverage drops.
    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        "\n### Rationale\nProtect data.\n"
        ":::\n" + "\n" + TEST_CASE,
        encoding="utf-8",
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    verification = [
        item for item in report.metric_deltas
        if item["scope"] == "approved-requirements" and item["strength"] == "verification-trace"
    ]
    assert verification
    assert verification[0]["before"] > verification[0]["after"]


def test_report_dict_is_json_safe_and_flags_emptiness(tmp_path: Path) -> None:
    import json as _json

    write(tmp_path)
    before = baseline_of(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    payload = diff.compare(before, snapshot, config).to_dict()

    assert payload["empty"] is True
    assert payload["schemaVersion"] == "1"
    _json.dumps(payload)
```

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_diff.py -q`

Expected: FAIL with `AttributeError: module 'quarto_needs.diff' has no attribute 'compare'`.

- [ ] **Step 3: Implement the derived-delta helpers**

Append to `diff.py`:

```python
def _finding_key(item: Mapping[str, object]) -> tuple[str, str, str]:
    return (str(item.get("code")), str(item.get("object_id") or ""), str(item.get("message")))


def _classify_findings(
    before: Sequence[Mapping[str, object]], after: Sequence[Mapping[str, object]]
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    before_keys = {_finding_key(item): item for item in before}
    after_keys = {_finding_key(item): item for item in after}
    added = tuple(
        {"code": key[0], "object_id": key[1] or None, "message": key[2], "severity": after_keys[key].get("severity")}
        for key in sorted(set(after_keys) - set(before_keys))
    )
    removed = tuple(
        {"code": key[0], "object_id": key[1] or None, "message": key[2], "severity": before_keys[key].get("severity")}
        for key in sorted(set(before_keys) - set(after_keys))
    )
    return added, removed


def _classify_metrics(
    before: Mapping[str, object], after: Mapping[str, object]
) -> tuple[dict[str, object], ...]:
    deltas: list[dict[str, object]] = []
    before_scopes = before.get("scopes", {}) if isinstance(before, Mapping) else {}
    after_scopes = after.get("scopes", {})
    for scope in sorted(set(before_scopes) | set(after_scopes)):
        old_coverage = (before_scopes.get(scope) or {}).get("coverage", {})
        new_coverage = (after_scopes.get(scope) or {}).get("coverage", {})
        for strength in sorted(set(old_coverage) | set(new_coverage)):
            old_percent = (old_coverage.get(strength) or {}).get("percent")
            new_percent = (new_coverage.get(strength) or {}).get("percent")
            if old_percent != new_percent:
                deltas.append(
                    {"scope": scope, "strength": strength, "before": old_percent, "after": new_percent}
                )
    return tuple(deltas)


def _classify_gates(
    before: Mapping[str, object], after: Mapping[str, object]
) -> tuple[dict[str, object], ...]:
    """Only pass -> fail is a regression; fail -> pass is progress, not a delta."""
    before_gates = {
        str(item["name"]): item for item in (before.get("gates", []) if isinstance(before, Mapping) else [])
    }
    regressions: list[dict[str, object]] = []
    for item in after.get("gates", []):
        name = str(item["name"])
        was = before_gates.get(name)
        if item.get("passed") is False and (was is None or was.get("passed") is not False):
            regressions.append(
                {"name": name, "scope": item.get("scope"), "threshold": item.get("threshold"), "actual": item.get("actual")}
            )
    return tuple(regressions)
```

- [ ] **Step 4: Implement `compare` with both guards**

Append to `diff.py`:

```python
def _recomputed_relations(stored: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Re-resolve stored relations through the *current* catalog.

    `--recompute-with current` must compare both sides under one policy, so the
    baseline's authored names are resolved again rather than trusting the
    families and roles that were canonical when it was written.
    """
    from .relations import DEFAULT_RELATION_CATALOG
    from .snapshot import RelationRecord

    recomputed: list[dict[str, object]] = []
    for item in stored:
        authored = str(item["authoredName"])
        try:
            kind = DEFAULT_RELATION_CATALOG.resolve(authored)
        except ValueError:
            # An authored name the current catalog no longer knows cannot be
            # re-resolved; keep it verbatim so it surfaces as a real change.
            recomputed.append(dict(item))
            continue
        record = RelationRecord(
            source=str(item["source"]),
            authored_name=authored,
            catalog_name=kind.catalog_name,
            v1_name=kind.v1_name,
            target=str(item["target"]),
            semantic_family=kind.semantic_family,
            source_role=kind.source_role,
            target_role=kind.target_role,
            impact_direction=kind.impact_direction,
            attributes=item.get("attributes") or {},
            provenance=(),
        )
        recomputed.append(
            {
                "source": record.source,
                "authoredName": record.authored_name,
                "target": record.target,
                "semanticFamily": record.semantic_family,
                "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
                "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
            }
        )
    return recomputed


def compare(
    baseline_payload: Mapping[str, object],
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    recompute: bool = False,
) -> DiffReport:
    if not baseline_payload.get("valid", False):
        raise DiffError(
            "This baseline is a diagnostic artifact (valid: false) and cannot be compared; "
            "use `baseline inspect` to read it"
        )

    current_configuration = snapshot.configuration_fingerprint
    baseline_configuration = str(baseline_payload.get("configurationFingerprint", ""))
    baseline_date = str(baseline_payload.get("referenceDate", ""))

    notices: list[str] = []
    configuration_differs = baseline_configuration != current_configuration
    date_differs = baseline_date != snapshot.reference_date
    if not recompute:
        if configuration_differs:
            notices.append("configuration-changed")
        if date_differs:
            notices.append("reference-date-changed")

    added, removed, modified, relocated = _classify_objects(
        _baseline_objects(baseline_payload),
        {record.id: _current_object(record) for record in snapshot.objects},
    )

    baseline_relations = list(baseline_payload.get("relations", []))
    if recompute:
        baseline_relations = _recomputed_relations(baseline_relations)
    # A catalog change can move families and roles, so semantic fingerprints
    # from the two sides stop being comparable. Fall back to authored tuples,
    # which is exactly what the spec prescribes for this case.
    relation_key = (
        "authoredFingerprint" if "configuration-changed" in notices else "semanticFingerprint"
    )
    added_relations, removed_relations, representation = _classify_relations(
        baseline_relations, _current_relations(snapshot), key=relation_key
    )

    # Derived results are stored in the baseline, never re-derived, so they are
    # comparable only when both sides were produced under the same rules and
    # the same reference date. `recompute` re-resolves authored relations
    # through the current catalog; it cannot make stored findings, metrics, or
    # gates comparable, so their deltas stay suppressed silently there.
    derived_suppressed = configuration_differs or date_differs
    if derived_suppressed:
        findings_added: tuple[dict[str, object], ...] = ()
        findings_removed: tuple[dict[str, object], ...] = ()
        metric_deltas: tuple[dict[str, object], ...] = ()
        gate_regressions: tuple[dict[str, object], ...] = ()
    else:
        current_report = report_from_snapshot(snapshot, config).to_dict()
        baseline_report = baseline_payload.get("report", {})
        findings_added, findings_removed = _classify_findings(
            baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
        )
        metric_deltas = _classify_metrics(baseline_report, current_report)
        gate_regressions = _classify_gates(baseline_report, current_report)

    return DiffReport(
        baseline_reference_date=baseline_date,
        current_reference_date=snapshot.reference_date,
        recomputed=recompute,
        notices=tuple(notices),
        added_objects=added,
        removed_objects=removed,
        modified=modified,
        relocated=relocated,
        added_relations=added_relations,
        removed_relations=removed_relations,
        representation_changes=representation,
        findings_added=findings_added,
        findings_removed=findings_removed,
        metric_deltas=metric_deltas,
        gate_regressions=gate_regressions,
    )
```

Note the deliberate asymmetry: a configuration change still reports **authored** object and relation changes, exactly as the spec requires ("default `diff` compares authored object content and authored relation tuples only"). Only the derived categories are suppressed.

- [ ] **Step 5: Run the diff tests**

Run: `.venv/bin/python -m pytest tests/test_diff.py -q`

Expected: PASS, all sixteen.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 7: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/diff.py tests/test_diff.py
  git commit -m "feat: complete the semantic diff engine"
else
  echo "Checkpoint 7 verified; workspace has no Git metadata."
fi
```

---

### Task 8: `diff` command and its schema

**Files:**
- Modify: `src/quarto_needs/cli.py`
- Create: `schemas/diff-v1.schema.json`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `diff.compare` from Task 7, `baseline.load_baseline` from Task 4.
- Produces: `cli.main(["diff", <path>, "--format", "json", "--recompute-with", "current"])`.

- [ ] **Step 1: Write the diff JSON Schema**

Create `schemas/diff-v1.schema.json` matching `DiffReport.to_dict()` exactly:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schema/diff-v1.schema.json",
  "title": "Quarto-Needs diff v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "referenceDate", "recomputed", "notices", "objects", "relations", "findings", "metrics", "gates", "empty"],
  "properties": {
    "schemaVersion": {"const": "1"},
    "referenceDate": {
      "type": "object",
      "additionalProperties": false,
      "required": ["baseline", "current"],
      "properties": {"baseline": {"type": "string"}, "current": {"type": "string"}}
    },
    "recomputed": {"type": "boolean"},
    "notices": {
      "type": "array",
      "items": {"enum": ["configuration-changed", "reference-date-changed"]}
    },
    "objects": {
      "type": "object",
      "additionalProperties": false,
      "required": ["added", "removed", "modified", "relocated"],
      "properties": {
        "added": {"type": "array", "items": {"type": "string"}},
        "removed": {"type": "array", "items": {"type": "string"}},
        "modified": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["id", "fields"],
            "properties": {"id": {"type": "string"}, "fields": {"type": "array", "items": {"type": "string"}}}
          }
        },
        "relocated": {"type": "array", "items": {"type": "object"}}
      }
    },
    "relations": {
      "type": "object",
      "additionalProperties": false,
      "required": ["added", "removed", "representationChanged"],
      "properties": {
        "added": {"type": "array", "items": {"type": "object"}},
        "removed": {"type": "array", "items": {"type": "object"}},
        "representationChanged": {"type": "array", "items": {"type": "object"}}
      }
    },
    "findings": {
      "type": "object",
      "additionalProperties": false,
      "required": ["added", "removed"],
      "properties": {
        "added": {"type": "array", "items": {"type": "object"}},
        "removed": {"type": "array", "items": {"type": "object"}}
      }
    },
    "metrics": {"type": "array", "items": {"type": "object"}},
    "gates": {
      "type": "object",
      "additionalProperties": false,
      "required": ["regressed"],
      "properties": {"regressed": {"type": "array", "items": {"type": "object"}}}
    },
    "empty": {"type": "boolean"}
  }
}
```

- [ ] **Step 2: Write the failing CLI tests**

Add to `tests/test_cli.py`:

```python
def test_diff_against_an_unchanged_project_is_empty_and_exits_zero(
    tmp_path: Path, capsys
) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    destination = str(tmp_path / "baselines" / "quarto-needs.json")

    assert cli.main(["--root", str(tmp_path), "diff", destination, "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["empty"] is True
    assert payload["notices"] == []


def test_diff_validates_against_the_diff_schema(tmp_path: Path, capsys) -> None:
    from jsonschema import Draft202012Validator

    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "diff-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_diff_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")])
    assert calls == 1


def test_diff_rejects_a_diagnostic_baseline(tmp_path: Path, capsys) -> None:
    write_duplicate_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"])
    (tmp_path / "duplicates.qmd").unlink()
    write_valid_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")]) == 2
    assert "diagnostic artifact" in capsys.readouterr().err


def test_diff_reports_a_missing_baseline_as_usage_error(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "absent.json")]) == 2


def test_diff_recompute_with_current_clears_notices(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    destination = tmp_path / "baselines" / "quarto-needs.json"
    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload["referenceDate"] = "1999-01-01"
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cli.main(["--root", str(tmp_path), "diff", str(destination), "--format", "json"])
    assert "reference-date-changed" in json.loads(capsys.readouterr().out)["notices"]

    cli.main([
        "--root", str(tmp_path), "diff", str(destination),
        "--recompute-with", "current", "--format", "json",
    ])
    assert json.loads(capsys.readouterr().out)["notices"] == []
```

- [ ] **Step 3: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k diff`

Expected: FAIL with `SystemExit: 2` — the `diff` command does not exist.

- [ ] **Step 4: Register the command**

In `main`, after the `baseline` parser block:

```python
    diff_parser = sub.add_parser("diff", help="Compare a baseline against the current graph")
    diff_parser.add_argument("baseline")
    diff_parser.add_argument("--format", choices=("text", "json"), default="text")
    diff_parser.add_argument(
        "--recompute-with",
        choices=("current",),
        dest="recompute_with",
        help="Re-resolve the baseline's relations under the current configuration and reference date",
    )
```

Add `from . import diff as diff_module` to the imports.

- [ ] **Step 5: Implement the handler**

Add above `main`:

```python
def _print_diff_text(report) -> None:
    for notice in report.notices:
        print(f"[notice] {notice}: derived deltas suppressed; both sides must share configuration and reference date to compare them")
    if report.is_empty():
        print("No changes.")
        return
    for object_id in report.added_objects:
        print(f"+ object {object_id}")
    for object_id in report.removed_objects:
        print(f"- object {object_id}")
    for item in report.modified:
        print(f"~ object {item['id']} ({', '.join(item['fields'])})")
    for item in report.relocated:
        print(f"> object {item['id']} moved {item['from'].get('file')} -> {item['to'].get('file')}")
    for item in report.added_relations:
        print(f"+ relation {item['source']} {item['authoredName']} {item['target']}")
    for item in report.removed_relations:
        print(f"- relation {item['source']} {item['authoredName']} {item['target']}")
    for item in report.representation_changes:
        print(f"= relation {item['source']} -> {item['target']} respelled {item['from']} -> {item['to']}")
    for item in report.findings_added:
        print(f"+ finding {item['code']} {item['object_id'] or ''}".rstrip())
    for item in report.findings_removed:
        print(f"- finding {item['code']} {item['object_id'] or ''}".rstrip())
    for item in report.metric_deltas:
        print(f"~ metric {item['scope']}/{item['strength']} {item['before']} -> {item['after']}")
    for item in report.gate_regressions:
        print(f"! gate {item['name']} failed (threshold {item['threshold']}, actual {item['actual']})")


def _diff(root: Path, args, config: NeedsConfig) -> int:
    try:
        baseline_payload = load_baseline(Path(args.baseline))
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    result = analyze_project(root, config=config)
    if result.snapshot is None:
        print_findings(result.findings, stream=sys.stderr)
        return 1
    try:
        report = diff_module.compare(
            baseline_payload,
            result.snapshot,
            config,
            recompute=args.recompute_with == "current",
        )
    except diff_module.DiffError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        _print_diff_text(report)
    return profile_exit_code(config.profile, False, len(report.gate_regressions))
```

Add `profile_exit_code` to the existing `from .quality import ...` line.

- [ ] **Step 6: Route the command**

In `main`, alongside the `baseline` dispatch and before the shared analysis line:

```python
    if args.command == "diff":
        return _diff(root, args, config)
```

- [ ] **Step 7: Run the CLI tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`

Expected: PASS.

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 9: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/cli.py schemas/diff-v1.schema.json tests/test_cli.py
  git commit -m "feat: add the diff command"
else
  echo "Checkpoint 8 verified; workspace has no Git metadata."
fi
```

---

### Task 9: Impact traversal over the union graph

**Files:**
- Create: `src/quarto_needs/impact.py`
- Create: `tests/test_impact.py`

**Interfaces:**
- Consumes: `diff.compare` from Task 7 (origins come from the classified diff); baseline relations from Task 4.
- Produces:
  - `impact.ImpactReport` dataclass with `.to_dict()`
  - `impact.analyze(baseline_payload, snapshot, config, *, recompute: bool = False) -> ImpactReport`
  - `impact.ImpactError(Exception)`

- [ ] **Step 1: Write the failing traversal tests**

Create `tests/test_impact.py`. The removal test is the acceptance gate: a removed node must still be explainable, which is why the traversal runs over the union of both graphs.

```python
from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs import baseline, impact
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

CHAIN = """::: {{.need #STK-1 type=stakeholder-need status=approved priority=high}}

## Stakeholder
Needs secure access.
:::

::: {{.need #REQ-1 type=functional-requirement status=approved priority=high}}
derives-from: STK-1
verified-by: TC-1
conflicts-with: DOC-1

## Authenticate
{body}

### Rationale
Protect data.
:::

::: {{.need #DOC-1 type=need status=draft}}

## Manual
Login manual.
:::

::: {{.need #TC-1 type=test-case status=passed}}

## Login
Signs in.
:::
"""


def write(root: Path, *, body: str = "The service shall authenticate.", keep_test: bool = True) -> None:
    text = CHAIN.format(body=body)
    if not keep_test:
        text = text.split("::: {.need #TC-1", 1)[0].replace("verified-by: TC-1\n", "")
    (root / "chain.qmd").write_text(text, encoding="utf-8")


def snapshot_of(root: Path):
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return result.snapshot, config


def baseline_of(root: Path) -> dict[str, object]:
    snapshot, config = snapshot_of(root)
    return baseline.build_baseline(snapshot, config)


def test_no_change_produces_no_impact(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    assert report.origins == ()
    assert report.impacted == ()


def test_editing_a_requirement_impacts_its_verification(tmp_path: Path) -> None:
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, body="The service shall authenticate every administrator.")
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    assert [item["id"] for item in report.origins] == ["REQ-1"]
    impacted = {item["id"]: item for item in report.impacted}
    assert "TC-1" in impacted
    assert impacted["TC-1"]["classification"] == "direct"
    assert impacted["TC-1"]["distance"] == 1
    assert impacted["TC-1"]["path"] == ["REQ-1", "TC-1"]
    assert impacted["TC-1"]["relations"] == ["verified-by"]


def test_every_impacted_result_carries_an_explicit_path(tmp_path: Path) -> None:
    """The gate forbids an opaque score; a path is the audit trail."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, body="Changed.")
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    assert report.impacted
    for item in report.impacted:
        assert item["path"][0] == item["origin"]
        assert item["path"][-1] == item["id"]
        assert len(item["path"]) == item["distance"] + 1
        assert item["classification"] in {"direct", "transitive"}
        assert "priority" in item


def test_removing_a_node_still_explains_its_neighbors(tmp_path: Path) -> None:
    """Union traversal is why a removed node and its removed edges stay explainable.

    `verified-by` propagates from requirement to test, so the removed test case
    cannot reach the requirement it verified; the removal surfaces instead as
    two origins — the removed node and the requirement that lost the edge.
    """
    write(tmp_path)
    before = baseline_of(tmp_path)
    write(tmp_path, keep_test=False)
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    changes = {item["id"]: item["change"] for item in report.origins}
    assert changes.get("TC-1") == "removed"
    assert changes.get("REQ-1") == "relation-removed"


def test_removal_reaches_neighbors_through_baseline_only_edges(tmp_path: Path) -> None:
    """A dropped `conflicts-with` still propagates: the edge exists only in the
    baseline, so without the union adjacency DOC-1 would be unreachable."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    text = (tmp_path / "chain.qmd").read_text(encoding="utf-8").replace("conflicts-with: DOC-1\n", "")
    (tmp_path / "chain.qmd").write_text(text, encoding="utf-8")
    snapshot, config = snapshot_of(tmp_path)

    report = impact.analyze(before, snapshot, config)

    changes = {item["id"]: item["change"] for item in report.origins}
    assert changes.get("REQ-1") == "relation-removed"
    doc = next(item for item in report.impacted if item["id"] == "DOC-1")
    assert doc["classification"] == "direct"
    assert doc["relations"] == ["conflicts-with"]


def test_impact_rejects_a_configuration_mismatch_without_recompute(tmp_path: Path) -> None:
    """One relation policy must govern the whole traversal."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
    )
    snapshot, config = snapshot_of(tmp_path)

    with pytest.raises(impact.ImpactError):
        impact.analyze(before, snapshot, config)

    assert impact.analyze(before, snapshot, config, recompute=True) is not None


def test_impact_rejects_a_reference_date_mismatch_without_recompute(tmp_path: Path) -> None:
    """The reference date is a comparison axis for impact too (spec: impact
    rejects the mismatch)."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    before = {**before, "referenceDate": "1999-01-01"}
    snapshot, config = snapshot_of(tmp_path)

    with pytest.raises(impact.ImpactError):
        impact.analyze(before, snapshot, config)

    assert impact.analyze(before, snapshot, config, recompute=True) is not None


def test_impact_rejects_a_diagnostic_baseline(tmp_path: Path) -> None:
    write(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    with pytest.raises(impact.ImpactError):
        impact.analyze({"schemaVersion": "1", "valid": False}, snapshot, config)
```

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_impact.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'quarto_needs.impact'`.

- [ ] **Step 3: Implement `impact.py`**

```python
"""Union-graph impact traversal with explicit, auditable paths.

The traversal runs over the union of the baseline and current graphs so a
removed node or edge remains explainable. There is deliberately no risk score:
the output is the path that produced each result.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Mapping, Sequence

from . import diff as diff_module
from .config import NeedsConfig
from .snapshot import AnalysisSnapshot

SCHEMA_VERSION = "1"
MAX_DISTANCE = 10


class ImpactError(Exception):
    """The two graphs cannot be traversed together."""


@dataclass(frozen=True, slots=True)
class ImpactReport:
    origins: tuple[Mapping[str, object], ...]
    impacted: tuple[Mapping[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "origins": [dict(item) for item in self.origins],
            "impacted": [dict(item) for item in self.impacted],
        }


def _union_edges(
    baseline_relations: Sequence[Mapping[str, object]], snapshot: AnalysisSnapshot
) -> dict[str, list[tuple[str, str]]]:
    """Adjacency keyed by source, following each relation's impact direction.

    `both` yields an edge in each direction; `none` yields none at all.
    """
    adjacency: dict[str, list[tuple[str, str]]] = {}

    def add(source: str, target: str, name: str, direction: str) -> None:
        if direction in {"source_to_target", "both"}:
            adjacency.setdefault(source, []).append((target, name))
        if direction in {"target_to_source", "both"}:
            adjacency.setdefault(target, []).append((source, name))

    for item in baseline_relations:
        add(
            str(item["source"]),
            str(item["target"]),
            str(item["authoredName"]),
            str(item.get("impactDirection", "none")),
        )
    for record in snapshot.relations:
        add(record.source, record.target, record.authored_name, record.impact_direction)

    for key in adjacency:
        adjacency[key] = sorted(set(adjacency[key]))
    return adjacency


def _origins(report: diff_module.DiffReport) -> tuple[dict[str, object], ...]:
    origins: list[dict[str, object]] = []
    for object_id in report.added_objects:
        origins.append({"id": object_id, "change": "added"})
    for object_id in report.removed_objects:
        origins.append({"id": object_id, "change": "removed"})
    for item in report.modified:
        origins.append({"id": str(item["id"]), "change": "modified", "fields": list(item["fields"])})
    for item in report.added_relations:
        origins.append({"id": str(item["source"]), "change": "relation-added"})
    for item in report.removed_relations:
        origins.append({"id": str(item["source"]), "change": "relation-removed"})
    seen: dict[str, dict[str, object]] = {}
    for origin in origins:
        seen.setdefault(str(origin["id"]), origin)
    return tuple(seen[key] for key in sorted(seen, key=lambda item: (item.casefold(), item)))


def _priority(
    object_id: str, snapshot: AnalysisSnapshot, baseline_objects: Mapping[str, Mapping[str, object]]
) -> str | None:
    record = snapshot.objects_by_id.get(object_id)
    if record is not None:
        return record.priority
    stored = baseline_objects.get(object_id)
    if stored is None:
        return None
    attributes = stored.get("attributes") or {}
    value = attributes.get("priority")
    return str(value) if value not in (None, "") else None


def analyze(
    baseline_payload: Mapping[str, object],
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    recompute: bool = False,
) -> ImpactReport:
    if not baseline_payload.get("valid", False):
        raise ImpactError(
            "This baseline is a diagnostic artifact (valid: false) and cannot be traversed"
        )
    if not recompute:
        if str(
            baseline_payload.get("configurationFingerprint", "")
        ) != snapshot.configuration_fingerprint:
            raise ImpactError(
                "The baseline was produced under a different configuration; "
                "pass --recompute-with current so one relation policy governs the traversal"
            )
        if str(baseline_payload.get("referenceDate", "")) != snapshot.reference_date:
            raise ImpactError(
                "The baseline was produced under a different reference date; "
                "pass --recompute-with current to traverse under the current date"
            )

    report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
    origins = _origins(report)
    adjacency = _union_edges(baseline_payload.get("relations", []), snapshot)
    baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
    origin_ids = {str(item["id"]) for item in origins}

    impacted: dict[tuple[str, str], dict[str, object]] = {}
    for origin in origins:
        start = str(origin["id"])
        queue: deque[tuple[str, tuple[str, ...], tuple[str, ...]]] = deque([(start, (start,), ())])
        visited = {start}
        while queue:
            current, path, relations = queue.popleft()
            distance = len(path) - 1
            if distance >= MAX_DISTANCE:
                continue
            for neighbor, relation_name in adjacency.get(current, []):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                next_path = path + (neighbor,)
                next_relations = relations + (relation_name,)
                key = (start, neighbor)
                if neighbor not in origin_ids and key not in impacted:
                    impacted[key] = {
                        "id": neighbor,
                        "origin": start,
                        "change": origin["change"],
                        "classification": "direct" if len(next_path) == 2 else "transitive",
                        "distance": len(next_path) - 1,
                        "relations": list(next_relations),
                        "path": list(next_path),
                        "priority": _priority(neighbor, snapshot, baseline_objects),
                    }
                queue.append((neighbor, next_path, next_relations))

    ordered = tuple(
        impacted[key]
        for key in sorted(impacted, key=lambda item: (item[0].casefold(), item[0], item[1].casefold(), item[1]))
    )
    return ImpactReport(origins=origins, impacted=ordered)
```

The breadth-first queue guarantees the first path found to a node is the shortest, so `distance` and `path` always agree.

- [ ] **Step 4: Run the impact tests**

Run: `.venv/bin/python -m pytest tests/test_impact.py -q`

Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 6: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/impact.py tests/test_impact.py
  git commit -m "feat: add union graph impact traversal"
else
  echo "Checkpoint 9 verified; workspace has no Git metadata."
fi
```

---

### Task 10: `impact` command and its schema

**Files:**
- Modify: `src/quarto_needs/cli.py`
- Create: `schemas/impact-v1.schema.json`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `impact.analyze` from Task 9.
- Produces: `cli.main(["impact", <path>, "--format", "json", "--recompute-with", "current"])`.

- [ ] **Step 1: Write the impact JSON Schema**

Create `schemas/impact-v1.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schema/impact-v1.schema.json",
  "title": "Quarto-Needs impact v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "origins", "impacted"],
  "properties": {
    "schemaVersion": {"const": "1"},
    "origins": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "change"],
        "properties": {
          "id": {"type": "string"},
          "change": {"enum": ["added", "removed", "modified", "relation-added", "relation-removed"]},
          "fields": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "impacted": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "origin", "change", "classification", "distance", "relations", "path", "priority"],
        "properties": {
          "id": {"type": "string"},
          "origin": {"type": "string"},
          "change": {"type": "string"},
          "classification": {"enum": ["direct", "transitive"]},
          "distance": {"type": "integer", "minimum": 1},
          "relations": {"type": "array", "items": {"type": "string"}, "minItems": 1},
          "path": {"type": "array", "items": {"type": "string"}, "minItems": 2},
          "priority": {"type": ["string", "null"]}
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing CLI tests**

Add to `tests/test_cli.py`:

```python
def test_impact_validates_against_the_impact_schema(tmp_path: Path, capsys) -> None:
    from jsonschema import Draft202012Validator

    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    (tmp_path / "needs.qmd").write_text(
        (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace("First body.", "Changed body."),
        encoding="utf-8",
    )

    assert cli.main([
        "--root", str(tmp_path), "impact",
        str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)

    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "impact-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    assert payload["origins"]


def test_impact_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    cli.main(["--root", str(tmp_path), "impact", str(tmp_path / "baselines" / "quarto-needs.json")])
    assert calls == 1


def test_impact_rejects_a_configuration_mismatch(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
    )

    destination = str(tmp_path / "baselines" / "quarto-needs.json")
    assert cli.main(["--root", str(tmp_path), "impact", destination]) == 2
    assert "--recompute-with" in capsys.readouterr().err

    assert cli.main(["--root", str(tmp_path), "impact", destination, "--recompute-with", "current"]) == 0
```

- [ ] **Step 3: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k impact`

Expected: FAIL with `SystemExit: 2` — the `impact` command does not exist.

- [ ] **Step 4: Register the command**

In `main`, after the `diff` parser block:

```python
    impact_parser = sub.add_parser("impact", help="Explain what a baseline's changes reach")
    impact_parser.add_argument("baseline")
    impact_parser.add_argument("--format", choices=("text", "json"), default="text")
    impact_parser.add_argument(
        "--recompute-with",
        choices=("current",),
        dest="recompute_with",
        help="Re-resolve the baseline's relations under the current configuration and reference date",
    )
```

Add `from . import impact as impact_module` to the imports.

- [ ] **Step 5: Implement the handler**

Add above `main`:

```python
def _impact(root: Path, args, config: NeedsConfig) -> int:
    try:
        baseline_payload = load_baseline(Path(args.baseline))
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    result = analyze_project(root, config=config)
    if result.snapshot is None:
        print_findings(result.findings, stream=sys.stderr)
        return 1
    try:
        report = impact_module.analyze(
            baseline_payload,
            result.snapshot,
            config,
            recompute=args.recompute_with == "current",
        )
    except impact_module.ImpactError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0
    if not report.origins:
        print("No changes to propagate.")
        return 0
    for origin in report.origins:
        print(f"origin {origin['id']} ({origin['change']})")
    for item in report.impacted:
        print(
            f"  {item['classification']} d={item['distance']} {item['id']}"
            f" via {' -> '.join(item['path'])}"
            f" [{', '.join(item['relations'])}]"
        )
    return 0
```

- [ ] **Step 6: Route the command**

In `main`, next to the `diff` dispatch:

```python
    if args.command == "impact":
        return _impact(root, args, config)
```

- [ ] **Step 7: Run the CLI tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`

Expected: PASS.

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 9: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/cli.py schemas/impact-v1.schema.json tests/test_cli.py
  git commit -m "feat: add the impact command"
else
  echo "Checkpoint 10 verified; workspace has no Git metadata."
fi
```

---

### Task 11: Showcase, documentation, and milestone acceptance

**Files:**
- Create: `examples/book/baselines/quarto-needs.json`
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `CONTRIBUTING.md`
- Modify: `Makefile`
- Modify: `tests/test_example_project.py`

**Interfaces:**
- Consumes: every command from Tasks 5, 8, and 10.
- Produces: the Milestone 3 acceptance command set and a checked-in Aegis baseline.

- [ ] **Step 1: Write the failing showcase tests**

Add to `tests/test_example_project.py`:

```python
def test_aegis_baseline_round_trips_to_an_empty_diff():
    """The gate: a checked-in baseline must still describe the published book."""
    import json as _json
    from quarto_needs import cli

    root = ROOT / "examples/book"
    baseline_path = root / "baselines" / "quarto-needs.json"
    assert baseline_path.is_file(), "run `make baseline-example` to create it"

    payload = _json.loads(baseline_path.read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["schemaVersion"] == "1"

    assert cli.main(["--root", str(root), "diff", str(baseline_path)]) == 0


def test_aegis_baseline_validates_against_the_baseline_schema():
    import json as _json
    from jsonschema import Draft202012Validator

    schema = _json.loads((ROOT / "schemas" / "baseline-v1.schema.json").read_text(encoding="utf-8"))
    payload = _json.loads((ROOT / "examples/book/baselines/quarto-needs.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_aegis_impact_explains_a_removed_verification(tmp_path: Path):
    """Removing an edge in a copy of the book must reach the requirement."""
    import json as _json
    import shutil as _shutil
    from quarto_needs import cli

    project = tmp_path / "book"
    _shutil.copytree(ROOT / "examples/book", project, ignore=_shutil.ignore_patterns("_book", ".quarto"))
    baseline_path = project / "baselines" / "quarto-needs.json"

    system = project / "requirements" / "system.qmd"
    system.write_text(
        system.read_text(encoding="utf-8").replace('verified-by="IAM-TC-001"', "", 1),
        encoding="utf-8",
    )

    # The checked-in baseline predates the run day, and impact (per spec)
    # rejects a reference-date mismatch; the documented escape hatch keeps the
    # showcase runnable on any date.
    assert cli.main([
        "--root", str(project), "impact", str(baseline_path),
        "--recompute-with", "current", "--format", "json",
    ]) == 0
```

Note: this last test reads the JSON only to prove the command exits 0 on a real project; asserting exact reachability is already covered by `tests/test_impact.py`.

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_example_project.py -q -k baseline`

Expected: FAIL — `examples/book/baselines/quarto-needs.json` does not exist yet.

- [ ] **Step 3: Add the Make targets**

In `Makefile`, extend `.PHONY` with `baseline-example diff-example impact-example` and append:

```make
baseline-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book baseline create --force

diff-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book diff examples/book/baselines/quarto-needs.json

impact-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json --recompute-with current
```

- [ ] **Step 4: Create the checked-in baseline**

Run:

```bash
make sync-example
make baseline-example
make diff-example
```

Expected: `baseline create` exits 0, and `diff-example` prints `No changes.` and exits 0. If the diff is non-empty immediately after creation, a fingerprint is reading derived data — stop and fix Task 3 rather than regenerating.

- [ ] **Step 5: Run the showcase tests**

Run: `.venv/bin/python -m pytest tests/test_example_project.py -q`

Expected: PASS.

- [ ] **Step 6: Document the commands in the README**

Extend the `## Commands` block with the three new entries and add a `### Baseline, diff, and impact` section after the configuration reference. It must state:

- `baseline create` writes `baselines/quarto-needs.json`, refuses to overwrite without `--force`, and refuses a structurally invalid project unless `--allow-invalid` is given;
- `--allow-invalid` produces a diagnostic artifact marked `valid: false` that only `baseline inspect` accepts — `diff` and `impact` reject it, because duplicate IDs make comparison ambiguous;
- `diff` classifies added/removed objects, modifications by field, added/removed relations, relocation, and findings/metrics/gate regressions; a changed ID is reported as a removal plus an addition because rename detection is heuristic and deliberately excluded;
- **relocation is keyed on the declaring file** — a line-only shift produces no record;
- an authored alias flip (`verified-by` to `verifies`) that preserves endpoint roles is a representation change, never a relation addition or removal;
- the two guards: a changed configuration fingerprint or reference date emits `configuration-changed` / `reference-date-changed` and suppresses derived deltas; `--recompute-with current` re-resolves the baseline's authored relations through the current catalog so semantic comparison is valid again, while derived deltas stay suppressed until both sides are produced under the same configuration and reference date;
- `impact` traverses the union of both graphs so removed nodes stay explainable, follows each relation's catalog `impactDirection`, and gives every result an explicit path, distance, classification, and priority — there is no risk score;
- determinism means byte-identical output for a fixed configuration **and** a fixed reference date; `SOURCE_DATE_EPOCH` fixes the latter.

- [ ] **Step 7: Update the pipeline diagram**

In `ARCHITECTURE.md`, extend the canonical pipeline block:

```text
AnalysisSnapshot -> fingerprints -> baselines/quarto-needs.json
                                          |
        current AnalysisSnapshot ---------+--> diff  -> DiffReport   -> text|json
                                          +--> impact -> ImpactReport -> text|json
```

Add a paragraph stating that `diff` and `impact` are pure functions over two snapshots, that the CLI is the only layer touching the filesystem, and that the configuration fingerprint and reference date are the two guards deciding which categories of delta are meaningful.

- [ ] **Step 8: Document the fixture and baseline policy**

In `CONTRIBUTING.md`, extend the fixture policy: `examples/book/baselines/quarto-needs.json` is a checked-in baseline that must always diff clean against the published book. Regenerate it with `make baseline-example` only when a deliberate change to the showcase is approved, and inspect the resulting diff before committing the new bytes. Never regenerate it to silence a failing test.

- [ ] **Step 9: Acceptance run**

Run each command and record its output:

```bash
make setup && make test
make sync-example && make sync-example   # SHA-256 pairs identical
make check-example
.venv/bin/python -m quarto_needs.cli --root examples/book quality --format json
.venv/bin/python -m quarto_needs.cli --root examples/book query approved-high-unverified
make baseline-example && make diff-example && make impact-example
make render-example-all
curl --fail --silent --show-error http://127.0.0.1:8777/ >/dev/null
.venv/bin/python -m pytest -q
```

Expected:

- the full suite passes with **zero** warnings;
- two consecutive `make sync-example` runs leave `examples/book/.quarto-needs/needs.json` and `generated-index.lua` byte-identical;
- `diff-example` prints `No changes.` and exits 0;
- `impact-example` prints `No changes to propagate.` and exits 0;
- `make render-example-all` exits 0 for HTML, DOCX, and PDF, and the rendered book contains no `need-ref-missing`, no unexpanded `{{<`, and no raw Mermaid source;
- the preview server answers and is neither stopped nor restarted.

Each render of the book rebuilds `_book`, so re-render HTML afterwards to leave the usual state on disk:

```bash
quarto render examples/book --to html
```

- [ ] **Step 10: Record the Milestone 3 acceptance checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add README.md ARCHITECTURE.md CONTRIBUTING.md Makefile \
    examples/book/baselines/quarto-needs.json tests/test_example_project.py
  git commit -m "docs: complete milestone three acceptance"
else
  echo "Milestone 3 verified; workspace has no Git metadata."
fi
```

Expected: every Milestone 3 acceptance gate is complete. Milestone 4A starts only after this checkpoint, with its own implementation plan.
