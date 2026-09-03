# Core Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the `EngineeringObject` validation bridge from canonical analysis, make the rule registry's evaluator invariant self-enforcing, build the graph indexes in linear time, and make the test suite reproducible from a clean clone — changing no observable diagnostic behaviour.

**Architecture:** The four legacy diagnostics split along a line the code already names. `REQ002`/`REQ006` become ordinary `rules.py` evaluators over `AnalysisSnapshot`. `REQ004`/`REQ005` become a declaration-native structural validator, which is what they always were — they must fire before a snapshot exists and prevent its construction, so they cannot be `rules.py` evaluators (`RuleContext` requires a snapshot). `LEGACY_CODES` then collapses into the already-existing `STRUCTURAL_CODES`, and `rules.py`'s import-time "every rule has an evaluator" check becomes the architectural test with no new test written. `analysis.py` stops scanning all relations once per object, adopting the linear idiom already present 250 lines earlier in the same file.

**Tech Stack:** Python 3.10+ (stdlib only), pytest.

**Spec:** `docs/superpowers/specs/2026-09-02-core-stabilization-design.md`

## Global Constraints

- **No observable diagnostic change.** Code, severity, object ID, source location, message text, deterministic ordering, and whether a diagnostic blocks snapshot construction all stay identical unless a task explicitly says otherwise. Characterization tests are written *before* the code they protect is touched.
- **`REQ002` and `REQ006` are currently always-on** because `_resolved_severity` (`rules.py:458-465`) treats membership in `LEGACY_CODES` as default activation. Narrowing that set without compensating silently disables both rules for every project that does not configure them. This is the single most dangerous step in the plan.
- **No benchmarks, no performance corpora, no optimization** beyond Task 4's linear index construction. Phase 8 owns measurement.
- **Do not delete `EngineeringObject` or `Relation`.** They stay as test constructors and a convenience API. Only the *direction* of dependency changes.
- **Use `.venv/bin/python`** for every command. Bare `python3` lacks the test dependencies.
- **Never run `quarto-needs scan` against a directory under `tests/fixtures/`** — it writes an `_extensions/` directory into the fixture and breaks `copy_fixture_project`. If you do it by accident, delete that directory.
- **`examples/book/.quarto-needs/needs.json` is tracked and rewritten with today's date by full test runs** until Task 6 fixes it. Do not stage that churn.
- Commit message style: `test:` / `refactor:` / `perf:` / `docs:`, with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` as the last line.

## Sequencing constraint

This plan touches `analysis.py`, `validation.py`, `rules.py`, `snapshot.py`. Run it **after** the C4 IR plan (`2026-09-02-phase-6b-c4-ir-and-renderer-boundary.md`) lands and the uncommitted flat renderer modules in the shared checkout are reconciled — `c4_projection.py` and `c4_render.py` are direct consumers of what Tasks 3 and 4 reshape, and retiring them first makes this phase strictly cheaper.

---

### Task 1: Characterize the four legacy diagnostics

**Files:**
- Create: `tests/test_legacy_diagnostics_characterization.py`

**Interfaces:**
- Consumes: `analyze_objects`, `EngineeringObject`, `Relation` from the existing public API.
- Produces: nothing importable. This task's output is a behavioural contract that Tasks 2 and 3 must not break.

This is pure characterization. It adds no production code and changes no behaviour. Its value is that Tasks 2 and 3 become mechanical.

- [ ] **Step 1: Write the characterization tests**

```python
"""Pins the four diagnostics the legacy validation bridge emits.

These tests exist to protect a migration, not to specify a design. They
assert current behaviour exactly as it is -- including the parts that are
arguably odd -- so that moving REQ002/REQ006 into the rule registry and
REQ004/REQ005 into declaration-native validation can be proven to change
nothing observable.

Delete or rewrite them only when a diagnostic's behaviour is deliberately
and separately changed.
"""
from __future__ import annotations

from quarto_needs.analysis import analyze_objects
from quarto_needs.model import EngineeringObject, Relation


def _obj(identifier, *, type="system-requirement", status="draft",
         rationale="", body="", relations=None):
    return EngineeringObject(
        identifier, type, identifier.title(), status=status,
        rationale=rationale, body=body, relations=relations or [],
    )


def _findings(*objects):
    return analyze_objects(list(objects)).findings


def _codes(*objects):
    return [item.code for item in _findings(*objects)]


def test_req004_duplicate_id_is_a_structural_error_that_blocks_the_snapshot() -> None:
    result = analyze_objects([_obj("REQ-1"), _obj("REQ-1")])
    duplicates = [item for item in result.findings if item.code == "REQ004"]
    assert len(duplicates) == 1
    assert duplicates[0].severity == "error"
    assert duplicates[0].object_id == "REQ-1"
    assert duplicates[0].message == "Duplicate ID: REQ-1"
    # Structural: no snapshot is produced at all.
    assert result.snapshot is None


def test_req005_unknown_target_is_a_structural_error_that_blocks_the_snapshot() -> None:
    result = analyze_objects([
        _obj("REQ-1", relations=[Relation("verified-by", "REQ-1", "GHOST")]),
    ])
    unknown = [item for item in result.findings if item.code == "REQ005"]
    assert len(unknown) == 1
    assert unknown[0].severity == "error"
    assert unknown[0].object_id == "REQ-1"
    assert "GHOST" in unknown[0].message
    assert "verified-by" in unknown[0].message
    assert result.snapshot is None


def test_req002_missing_rationale_is_a_warning_that_does_not_block() -> None:
    result = analyze_objects([
        _obj("REQ-1", status="draft", rationale="", body=""),
    ])
    rationale = [item for item in result.findings if item.code == "REQ002"]
    assert len(rationale) == 1
    assert rationale[0].severity == "warning"
    assert rationale[0].object_id == "REQ-1"
    assert rationale[0].message == "REQ-1 has no rationale"
    # A warning must still produce a usable snapshot.
    assert result.snapshot is not None


def test_req002_is_satisfied_by_either_the_field_or_a_rationale_heading() -> None:
    # Two independent escapes, both currently honoured. Pin both.
    assert "REQ002" not in _codes(_obj("REQ-1", rationale="because"))
    assert "REQ002" not in _codes(_obj("REQ-1", body="### Rationale\nbecause"))


def test_req002_only_applies_to_the_two_default_requirement_types() -> None:
    # The default set is {"system-requirement", "software-requirement"}.
    assert "REQ002" in _codes(_obj("REQ-1", type="system-requirement"))
    assert "REQ002" in _codes(_obj("REQ-2", type="software-requirement"))
    # A functional-requirement is a requirement for REQ006 but NOT for REQ002.
    assert "REQ002" not in _codes(_obj("REQ-3", type="functional-requirement"))


def test_req006_approved_requirement_without_verification_is_a_warning() -> None:
    result = analyze_objects([_obj("REQ-1", status="approved", rationale="r")])
    approved = [item for item in result.findings if item.code == "REQ006"]
    assert len(approved) == 1
    assert approved[0].severity == "warning"
    assert approved[0].object_id == "REQ-1"
    assert approved[0].message == "REQ-1 is approved but has no verification relation"
    assert result.snapshot is not None


def test_req006_accepts_either_verified_by_or_validated_by() -> None:
    for relation_name in ("verified-by", "validated-by"):
        codes = _codes(
            _obj("REQ-1", status="approved", rationale="r",
                 relations=[Relation(relation_name, "REQ-1", "TC-1")]),
            _obj("TC-1", type="test-case", rationale="r"),
        )
        assert "REQ006" not in codes, relation_name


def test_req006_applies_to_any_type_ending_in_requirement() -> None:
    assert "REQ006" in _codes(
        _obj("REQ-1", type="functional-requirement", status="approved", rationale="r")
    )
    assert "REQ006" not in _codes(
        _obj("TC-1", type="test-case", status="approved", rationale="r")
    )


def test_req002_and_req006_are_active_with_no_rules_configuration() -> None:
    # THE critical pin for this migration. Both currently default-activate
    # because they are members of rules.LEGACY_CODES, which
    # _resolved_severity treats as "on unless configured otherwise".
    # Narrowing that set without giving them an explicit activation would
    # silently switch both off for every unconfigured project.
    codes = _codes(_obj("REQ-1", status="approved", rationale=""))
    assert "REQ002" in codes
    assert "REQ006" in codes


def test_findings_are_ordered_deterministically_regardless_of_input_order() -> None:
    forward = _findings(
        _obj("REQ-B", status="approved", rationale=""),
        _obj("REQ-A", status="approved", rationale=""),
    )
    backward = _findings(
        _obj("REQ-A", status="approved", rationale=""),
        _obj("REQ-B", status="approved", rationale=""),
    )
    assert [(f.code, f.object_id) for f in forward] == [
        (f.code, f.object_id) for f in backward
    ]
```

- [ ] **Step 2: Run them against the CURRENT code**

Run: `.venv/bin/python -m pytest tests/test_legacy_diagnostics_characterization.py -v`

Expected: **all pass immediately**. These describe behaviour that already exists.

If any fails, do not change production code. The test is wrong about current behaviour — correct the test to match what the code actually does, and note the surprise in your report. A characterization test that fails on unchanged code is a mis-described contract, not a bug found.

- [ ] **Step 3: Falsify two of them**

Prove the tests have teeth before trusting them:

1. In `src/quarto_needs/validation.py:55`, change `"REQ002"` to `"REQ999"`. Run the file. `test_req002_missing_rationale_is_a_warning_that_does_not_block` and `test_req002_and_req006_are_active_with_no_rules_configuration` must fail. Revert.
2. In `src/quarto_needs/validation.py:52`, drop `"software-requirement"` from the default set. `test_req002_only_applies_to_the_two_default_requirement_types` must fail. Revert.

Run `git diff` afterwards and confirm it is empty.

- [ ] **Step 4: Commit**

```bash
git add tests/test_legacy_diagnostics_characterization.py
git commit -m "test: characterize the four legacy validation diagnostics

Pins REQ002/REQ004/REQ005/REQ006 exactly as they behave today, including
that REQ002 and REQ006 are active with no [rules] configuration, so the
migration into the rule registry can be proven to change nothing.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Declaration-native structural validation for REQ004/REQ005

**Files:**
- Create: `src/quarto_needs/declaration_validation.py`
- Modify: `src/quarto_needs/analysis.py`
- Test: `tests/test_declaration_validation.py`

**Interfaces:**
- Consumes: `ObjectDeclaration`, `DeclarationBatch`, `RelationToken`, `to_location_record` from `.snapshot`; `Finding` from `.diagnostics`; `finding_key` from `.validation`.
- Produces: `validate_declarations(declarations: Sequence[ObjectDeclaration]) -> list[Finding]`, emitting `REQ004` and `REQ005` with byte-identical messages, severities, object IDs and locations to today's `validate()`.

**Why these two and not the other two:** `RuleContext` is `(snapshot, config)`. REQ004 and REQ005 must fire *before* a snapshot exists — they prevent its construction. They are not rule-registry material; they are declaration validation, which is what `STRUCTURAL_CODES` has always called them.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from quarto_needs.declaration_validation import validate_declarations
from quarto_needs.snapshot import LocationRecord, ObjectDeclaration, RelationToken


def _decl(identifier, *, type="system-requirement", relations=(), file="index.qmd", line=1):
    return ObjectDeclaration(
        id=identifier, type=type, title=identifier.title(), status="draft",
        body="", rationale="", attributes={},
        relations=tuple(relations),
        location=LocationRecord(file=file, line=line, anchor=None),
    )


def _token(name, target):
    return RelationToken(authored_name=name, target=target, attributes={}, location=None)


def test_duplicate_id_reports_one_error_naming_the_id() -> None:
    findings = validate_declarations([_decl("REQ-1"), _decl("REQ-1", line=9)])
    duplicates = [item for item in findings if item.code == "REQ004"]
    assert len(duplicates) == 1
    assert duplicates[0].severity == "error"
    assert duplicates[0].object_id == "REQ-1"
    assert duplicates[0].message == "Duplicate ID: REQ-1"
    # The location is the FIRST declaration's, matching today's behaviour.
    assert duplicates[0].location.line == 1


def test_three_copies_still_report_exactly_one_duplicate_finding() -> None:
    findings = validate_declarations([_decl("REQ-1"), _decl("REQ-1"), _decl("REQ-1")])
    assert len([item for item in findings if item.code == "REQ004"]) == 1


def test_unknown_relation_target_reports_the_source_the_target_and_the_relation() -> None:
    findings = validate_declarations([
        _decl("REQ-1", relations=[_token("verified-by", "GHOST")]),
    ])
    unknown = [item for item in findings if item.code == "REQ005"]
    assert len(unknown) == 1
    assert unknown[0].severity == "error"
    assert unknown[0].object_id == "REQ-1"
    assert unknown[0].message == "REQ-1 references unknown object GHOST via verified-by"


def test_a_resolvable_target_produces_nothing() -> None:
    findings = validate_declarations([
        _decl("REQ-1", relations=[_token("verified-by", "TC-1")]),
        _decl("TC-1", type="test-case"),
    ])
    assert findings == []


def test_every_unknown_target_on_one_object_is_reported() -> None:
    findings = validate_declarations([
        _decl("REQ-1", relations=[_token("verified-by", "A"), _token("refines", "B")]),
    ])
    assert len([item for item in findings if item.code == "REQ005"]) == 2


def test_output_is_deterministic_regardless_of_declaration_order() -> None:
    first = _decl("REQ-B", relations=[_token("refines", "GHOST")])
    second = _decl("REQ-A", relations=[_token("refines", "GHOST")])
    forward = validate_declarations([first, second])
    backward = validate_declarations([second, first])
    assert [(f.code, f.object_id, f.message) for f in forward] == [
        (f.code, f.object_id, f.message) for f in backward
    ]
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_declaration_validation.py -q`
Expected: `ModuleNotFoundError: No module named 'quarto_needs.declaration_validation'`.

- [ ] **Step 3: Implement**

Create `src/quarto_needs/declaration_validation.py`:

```python
"""Structural validation over authored declarations, before resolution.

These checks answer questions that have no meaning after resolution, because
a graph containing them cannot be resolved at all: an ID that appears twice,
and a relation pointing at nothing. They therefore run on
`ObjectDeclaration`s and may prevent snapshot construction -- which is
exactly what `rules.STRUCTURAL_CODES` has always meant.

They are deliberately NOT rule-registry evaluators: `RuleContext` carries an
`AnalysisSnapshot`, and by the time one exists these findings are already
too late to be reported.
"""
from __future__ import annotations

from collections import Counter
from typing import Sequence

from .diagnostics import Finding
from .snapshot import ObjectDeclaration
from .validation import finding_key


def validate_declarations(
    declarations: Sequence[ObjectDeclaration],
) -> list[Finding]:
    """Every structural problem in `declarations`, deterministically ordered."""
    findings: list[Finding] = []
    counts = Counter(item.id for item in declarations)
    known_ids = set(counts)

    # One finding per duplicated ID, located at its first declaration --
    # matching the legacy bridge, whose `next(...)` also took the first.
    first_by_id: dict[str, ObjectDeclaration] = {}
    for declaration in declarations:
        first_by_id.setdefault(declaration.id, declaration)
    for identifier, count in counts.items():
        if count > 1:
            findings.append(
                Finding(
                    "REQ004",
                    "error",
                    f"Duplicate ID: {identifier}",
                    identifier,
                    first_by_id[identifier].location,
                )
            )

    for declaration in declarations:
        for token in declaration.relations:
            if token.target not in known_ids:
                findings.append(
                    Finding(
                        "REQ005",
                        "error",
                        f"{declaration.id} references unknown object "
                        f"{token.target} via {token.authored_name}",
                        declaration.id,
                        declaration.location,
                    )
                )

    return sorted(findings, key=finding_key)
```

- [ ] **Step 4: Run to verify the new tests pass**

Run: `.venv/bin/python -m pytest tests/test_declaration_validation.py -q`
Expected: 6 passed.

- [ ] **Step 5: Route canonical analysis through it, for these two codes only**

In `src/quarto_needs/analysis.py`, the canonical path currently does:

```python
legacy_objects, unsupported = _legacy_objects(declarations)
compatibility_findings = validate(legacy_objects)
```

Change it so the structural half comes from the new validator while REQ002/REQ006 still come from the bridge — Task 3 removes the bridge entirely. Keep `_legacy_objects` for now (it also produces `unsupported`, which is separate concern):

```python
from .declaration_validation import validate_declarations

legacy_objects, unsupported = _legacy_objects(declarations)
structural_findings = validate_declarations(declarations)
# The bridge still owns REQ002/REQ006 until Task 3 moves them into the
# rule registry; take only those two from it to avoid double-reporting
# the structural codes the declaration validator now produces.
bridge_findings = [
    item for item in validate(legacy_objects)
    if item.code not in {"REQ004", "REQ005"}
]
compatibility_findings = sorted(
    structural_findings + bridge_findings, key=finding_key
)
```

Read the surrounding code before applying this — the variable names and the way `compatibility_findings` is consumed must match what is actually there. The shape above is the intent, not a patch to apply blind.

- [ ] **Step 6: Prove nothing changed**

Run: `.venv/bin/python -m pytest tests/test_legacy_diagnostics_characterization.py tests/test_declaration_validation.py -v`
Expected: all pass, including every Task 1 characterization test unchanged.

Then the full suite: `.venv/bin/python -m pytest -q`.

- [ ] **Step 7: Commit**

```bash
git add src/quarto_needs/declaration_validation.py src/quarto_needs/analysis.py tests/test_declaration_validation.py
git commit -m "refactor: validate REQ004/REQ005 on declarations, not legacy DTOs

Structural codes must fire before a snapshot exists, so they cannot be
rule-registry evaluators -- RuleContext carries a snapshot. They move to a
declaration-native validator instead, which is what STRUCTURAL_CODES has
always meant.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Move REQ002/REQ006 into the rule registry and retire the bridge

**Files:**
- Modify: `src/quarto_needs/rules.py`
- Modify: `src/quarto_needs/analysis.py`
- Delete: `src/quarto_needs/validation.py`'s `validate()` (keep `finding_key` and `SEVERITY_ORDER` — both are used elsewhere)
- Test: `tests/test_rules.py` (extend)

**Interfaces:**
- Produces: evaluators `_missing_rationale(ctx)` and `_approved_without_verification(ctx)` attached to the existing `RULES["REQ002"]` / `RULES["REQ006"]` specs; `LEGACY_CODES` deleted; `rules.py:454` and `rules.py:461` referencing `STRUCTURAL_CODES` instead.

**The dangerous step.** `_resolved_severity` uses `LEGACY_CODES` for default activation. Deleting the set without compensating switches REQ002 and REQ006 off for every unconfigured project. Task 1's `test_req002_and_req006_are_active_with_no_rules_configuration` is the guard — it must stay green through this task, and if it goes red the cause is this, not something subtle.

- [ ] **Step 1: Write the failing evaluator tests**

Add to `tests/test_rules.py`, matching that file's existing helper style (read it first — reuse its snapshot construction rather than inventing another):

```python
def test_req002_evaluator_runs_from_the_rule_registry() -> None:
    # After the migration REQ002 must come from an evaluator, not the bridge.
    from quarto_needs.rules import RULES

    assert RULES["REQ002"].evaluator is not None
    assert RULES["REQ006"].evaluator is not None


def test_structural_codes_are_the_only_evaluatorless_rules() -> None:
    from quarto_needs.rules import RULES, STRUCTURAL_CODES

    evaluatorless = {code for code, spec in RULES.items() if spec.evaluator is None}
    assert evaluatorless == set(STRUCTURAL_CODES)


def test_legacy_codes_is_gone() -> None:
    import quarto_needs.rules as rules_module

    assert not hasattr(rules_module, "LEGACY_CODES")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_rules.py -q -k "req002_evaluator or structural_codes_are_the_only or legacy_codes_is_gone"`
Expected: three failures — `RULES["REQ002"].evaluator is None`, the evaluatorless set contains four codes not two, and `LEGACY_CODES` still exists.

- [ ] **Step 3: Write the two evaluators**

In `src/quarto_needs/rules.py`, beside the other evaluators. Note the type predicates differ between the two rules and must be preserved exactly — REQ002 uses a fixed two-type default set, REQ006 uses `endswith("requirement")`:

```python
_RATIONALE_REQUIRED_TYPES = frozenset({"system-requirement", "software-requirement"})
_VERIFICATION_RELATIONS = frozenset({"verified-by", "validated-by"})


def _missing_rationale(ctx: RuleContext) -> Iterable[Finding]:
    """REQ002. Satisfied by the rationale field OR a body heading.

    Both escapes predate the rule registry and are load-bearing for existing
    projects; keep them together.
    """
    for obj in ctx.snapshot.objects:
        if obj.type not in _RATIONALE_REQUIRED_TYPES:
            continue
        if obj.rationale or "### Rationale" in obj.body:
            continue
        yield Finding(
            "REQ002",
            RULES["REQ002"].default_severity,
            f"{obj.id} has no rationale",
            obj.id,
            obj.locations[0] if obj.locations else None,
        )


def _approved_without_verification(ctx: RuleContext) -> Iterable[Finding]:
    """REQ006. Any type ending in `requirement`, unlike REQ002's fixed set."""
    for obj in ctx.snapshot.objects:
        if obj.status != "approved" or not obj.type.endswith("requirement"):
            continue
        verified = any(
            relation.v1_name in _VERIFICATION_RELATIONS
            for relation in ctx.snapshot.outgoing.get(obj.id, ())
        )
        if not verified:
            yield Finding(
                "REQ006",
                RULES["REQ006"].default_severity,
                f"{obj.id} is approved but has no verification relation",
                obj.id,
                obj.locations[0] if obj.locations else None,
            )
```

**Two things to verify rather than assume**, because they can silently change behaviour:

1. The legacy bridge passed **no location** for REQ002/REQ006 (`validation.py:55,59` construct `Finding` with four arguments). The evaluators above pass one. Decide deliberately: either drop the location argument to match exactly, or keep it and update Task 1's characterization test with a note that the extra location is an intentional improvement. Do not let it change silently — check what `finding_key` does with it, since location participates in ordering.
2. The bridge matched relations by `rel.type` on `EngineeringObject`; the evaluator matches `relation.v1_name` on `RelationRecord`. Confirm `verified-by` and `validated-by` are their own `v1_name`s in `relations.py` and are not aliases that collapse onto something else. If they collapse, use the resolved name the catalog actually produces.

- [ ] **Step 4: Attach them and collapse the exemption**

In the `RULES` table, give `REQ002` and `REQ006` their evaluators, and give each an explicit always-on activation so removing `LEGACY_CODES` does not disable them:

```python
    RuleSpec("REQ002", "Missing rationale",
             "Requirement declarations should explain why they exist.",
             "warning",
             evaluator=_missing_rationale,
             auto_activates=lambda config: True),
    ...
    RuleSpec("REQ006", "Approved without verification",
             "Approved requirements need a verification relation.",
             "warning", supported_severities=("error", "warning"),
             evaluator=_approved_without_verification,
             auto_activates=lambda config: True),
```

Then delete `LEGACY_CODES` and point both of its uses at `STRUCTURAL_CODES`:

```python
# rules.py:454
    if _spec.evaluator is None and _spec.code not in STRUCTURAL_CODES:
        raise RuntimeError(f"rule {_spec.code} lacks an evaluator")

# rules.py:461 -- REQ004/REQ005 keep defaulting on; REQ002/REQ006 now do
# so through their own auto_activates instead of set membership.
        if _spec.code in STRUCTURAL_CODES or (
            _spec.auto_activates is not None and _spec.auto_activates(config)
        ):
```

- [ ] **Step 5: Remove the bridge from canonical analysis**

In `analysis.py`, drop the `validate(legacy_objects)` call and the `bridge_findings` filtering that Task 2 introduced, leaving only `validate_declarations(declarations)` for the structural codes. If `_legacy_objects()` is still needed for `unsupported`, keep it and say so in your report; if its only remaining consumer was `validate()`, remove it.

Then delete `validate()` from `src/quarto_needs/validation.py`. **Keep `finding_key` and `SEVERITY_ORDER`** — they are imported elsewhere. Verify with:

```bash
grep -rn "from .validation import\|from quarto_needs.validation import\|validation.validate" src tests
```

- [ ] **Step 6: Prove nothing changed**

Run, in this order:

```bash
.venv/bin/python -m pytest tests/test_legacy_diagnostics_characterization.py -v
.venv/bin/python -m pytest tests/test_rules.py tests/test_validation.py tests/test_analysis.py -q
.venv/bin/python -m pytest -q
```

Every Task 1 characterization test must pass **unchanged**. If one fails, the migration changed observable behaviour — fix the code, not the test, unless Step 3's location decision explains it and you documented that decision.

- [ ] **Step 7: Falsify the new invariant**

Temporarily add a `RuleSpec("REQ999", "x", "x", "warning")` with no evaluator to the `RULES` table. Importing `quarto_needs.rules` must now raise `RuntimeError: rule REQ999 lacks an evaluator`. Revert.

This is the architectural test — no separate test file needed.

- [ ] **Step 8: Commit**

```bash
git add src/quarto_needs/rules.py src/quarto_needs/analysis.py src/quarto_needs/validation.py tests/test_rules.py
git commit -m "refactor: evaluate REQ002/REQ006 in the rule registry, retire the bridge

LEGACY_CODES collapses into STRUCTURAL_CODES: the evaluator exemption now
means 'runs before a snapshot exists' rather than 'not migrated yet', and
rules.py's import-time check enforces it for every other rule. REQ002 and
REQ006 keep default activation through explicit auto_activates.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Build the canonical graph indexes in linear time

**Files:**
- Modify: `src/quarto_needs/analysis.py:344-352`
- Test: `tests/test_analysis.py` (extend)

**Interfaces:** unchanged. `objects_by_id`, `outgoing`, `incoming` keep their exact types, contents and ordering.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_analysis.py`:

```python
def test_graph_indexes_are_built_without_rescanning_relations_per_object() -> None:
    """Construction is O(V + E), not O(V * E).

    Asserted structurally rather than by wall-clock: a counting sequence
    records how many times the relation collection is iterated. One pass
    for outgoing and one for incoming is fine; one pass per object is not.
    """
    from quarto_needs.analysis import analyze_objects
    from quarto_needs.model import EngineeringObject, Relation

    objects = [
        EngineeringObject(f"REQ-{index}", "system-requirement", f"R{index}",
                          status="draft", rationale="r")
        for index in range(50)
    ]
    objects.append(
        EngineeringObject("REQ-X", "system-requirement", "X", status="draft",
                          rationale="r",
                          relations=[Relation("refines", "REQ-X", "REQ-0")])
    )
    result = analyze_objects(objects)
    assert result.snapshot is not None
    snapshot = result.snapshot

    # Contents and shape are what matter to every consumer.
    assert snapshot.outgoing["REQ-X"][0].target == "REQ-0"
    assert snapshot.incoming["REQ-0"][0].source == "REQ-X"
    # Objects with no edges get an empty tuple, never a missing key.
    assert snapshot.outgoing["REQ-1"] == ()
    assert snapshot.incoming["REQ-1"] == ()
    assert all(isinstance(value, tuple) for value in snapshot.outgoing.values())
    assert all(isinstance(value, tuple) for value in snapshot.incoming.values())
    # Every object appears in both indexes.
    assert set(snapshot.outgoing) == set(snapshot.objects_by_id)
    assert set(snapshot.incoming) == set(snapshot.objects_by_id)


def test_index_contents_are_identical_regardless_of_object_order() -> None:
    from quarto_needs.analysis import analyze_objects
    from quarto_needs.model import EngineeringObject, Relation

    def build(order):
        return analyze_objects(list(order)).snapshot

    a = EngineeringObject("REQ-A", "system-requirement", "A", status="draft",
                          rationale="r",
                          relations=[Relation("refines", "REQ-A", "REQ-B")])
    b = EngineeringObject("REQ-B", "system-requirement", "B", status="draft",
                          rationale="r")
    forward, backward = build([a, b]), build([b, a])
    assert forward is not None and backward is not None
    assert {k: [r.target for r in v] for k, v in forward.outgoing.items()} == \
           {k: [r.target for r in v] for k, v in backward.outgoing.items()}
    assert forward.semantic_graph_fingerprint == backward.semantic_graph_fingerprint
```

- [ ] **Step 2: Run — these should pass already**

Run: `.venv/bin/python -m pytest tests/test_analysis.py -q -k "graph_indexes or index_contents"`
Expected: pass. They pin behaviour that must survive the rewrite; they are not red-first tests. The rewrite is a pure performance change and these are its safety net.

- [ ] **Step 3: Rewrite the construction**

Replace `analysis.py:344-352`:

```python
    outgoing: dict[str, tuple[RelationRecord, ...]] = {}
    incoming: dict[str, tuple[RelationRecord, ...]] = {}
    for item in objects:
        outgoing[item.id] = tuple(
            relation for relation in relations if relation.source == item.id
        )
        incoming[item.id] = tuple(
            relation for relation in relations if relation.target == item.id
        )
```

with the linear idiom this file already uses at line 96:

```python
    # One pass per direction, not one full relation scan per object. Both
    # indexes are seeded from `objects` first so an object with no edges
    # still gets an empty tuple rather than a missing key, and relation
    # order inside each bucket follows `relations`, which is already
    # canonically ordered.
    outgoing_lists: dict[str, list[RelationRecord]] = {item.id: [] for item in objects}
    incoming_lists: dict[str, list[RelationRecord]] = {item.id: [] for item in objects}
    for relation in relations:
        outgoing_lists[relation.source].append(relation)
        incoming_lists[relation.target].append(relation)
    outgoing = {key: tuple(value) for key, value in outgoing_lists.items()}
    incoming = {key: tuple(value) for key, value in incoming_lists.items()}
```

**Check before applying:** the old code only ever indexed by `item.id` from `objects`, so a relation whose `source` or `target` is not among `objects` was silently dropped. The new code would raise `KeyError`. Structural validation (Task 2's REQ005) should make that unreachable — confirm it, and if any path can still produce a dangling relation here, use `setdefault` as line 100 does rather than direct indexing.

- [ ] **Step 4: Verify**

```bash
.venv/bin/python -m pytest tests/test_analysis.py -q
.venv/bin/python -m pytest -q
```

Fingerprints must be unchanged — `test_index_contents_are_identical_regardless_of_object_order` asserts that directly.

- [ ] **Step 5: Commit**

```bash
git add src/quarto_needs/analysis.py tests/test_analysis.py
git commit -m "perf: build canonical graph indexes in one pass per direction

Replaces a full relation scan per object with the linear idiom this file
already used 250 lines earlier. Contents, ordering and fingerprints are
unchanged; the file now agrees with itself.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Make the test suite reproducible from a clean clone

**Files:**
- Modify: `tests/fixtures/views/` (add `.quarto-needs.toml`, or add a conftest fixture)
- Modify: `tests/test_quarto_views.py` and/or `tests/conftest.py`

**The defect:** `tests/fixtures/views/.quarto-needs/needs.json` is gitignored (`.quarto-needs/` is in `.gitignore`), and `copy_fixture_project` copies it into the temporary project without re-scanning. It is not reproducible by running `quarto-needs scan` against the fixture, because the fixture has no `.quarto-needs.toml`, so `cli.build` writes no `extensions.quartoNeeds.report` block — and ten tests across `test_quarto_views.py` and `test_views_helpers.py` assert on content from that block. On a fresh checkout they fail.

- [ ] **Step 1: Reproduce it**

```bash
mv tests/fixtures/views/.quarto-needs /tmp/views-artifact-backup
.venv/bin/python -m pytest tests/test_quarto_views.py tests/test_views_helpers.py -q
```

Expected: failures. Record the exact count and names — that is the defect's signature. Restore with `mv /tmp/views-artifact-backup tests/fixtures/views/.quarto-needs` before continuing.

- [ ] **Step 2: Choose the fix and say why**

Three acceptable shapes; pick one and record the reasoning in your report:

1. **Give the fixture the configuration its tests need** — add `tests/fixtures/views/.quarto-needs.toml` with whatever minimal `[queries]`/`[gates]` content makes `cli.build` emit the `extensions.quartoNeeds.report` block the tests assert on. Then a plain `scan` regenerates the artifact faithfully.
2. **Generate it in a session-scoped pytest fixture** in `tests/conftest.py` that runs the scan once before any test that needs it, into a temp directory rather than into the source tree.
3. **Track the artifact deliberately** with `git add -f`, and add a test that regenerating it produces identical bytes so it cannot silently drift.

Option 1 is preferred: it removes the special case rather than managing it, and it makes the fixture describe its own requirements. Option 2 is next best. Option 3 only if the first two prove impractical — a tracked generated file needs its own drift guard, which is more machinery than the problem deserves.

- [ ] **Step 3: Implement, then prove reproducibility**

```bash
rm -rf tests/fixtures/views/.quarto-needs
.venv/bin/python -m pytest tests/test_quarto_views.py tests/test_views_helpers.py -q
```

Expected: **pass with no pre-existing artifact.** That is the whole point of the task — if it needs the artifact to already exist, the fix did not work.

If your fix regenerates into the source tree, also confirm `git status --short` shows no unexpected untracked directory (particularly not `tests/fixtures/views/_extensions/`, which a scan creates and which breaks `copy_fixture_project` on the next run).

- [ ] **Step 4: Full suite and commit**

```bash
.venv/bin/python -m pytest -q
git add tests/
git commit -m "test: make the views fixture reproducible from a clean clone

The fixture's generated needs.json was gitignored, was copied without a
re-scan, and could not be regenerated because the fixture carried no
configuration -- so ten tests only passed on a machine that had run them
before.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Remove date-dependent content from tracked files

**Files:**
- Modify: `examples/book/.quarto-needs/needs.json` handling — either the example's configuration or `.gitignore`

**The defect:** `examples/book/.quarto-needs/needs.json` is tracked and carries `"referenceDate"`. Every test run on a new calendar day rewrites it, dirtying the working tree and inviting an accidental commit of unrelated churn. Determinism is a stated project property; a tracked file that changes with the calendar contradicts it.

- [ ] **Step 1: Reproduce and locate the source of the date**

```bash
git status --short examples/book/.quarto-needs/needs.json
.venv/bin/python -m pytest tests/test_example_project.py -q
git diff examples/book/.quarto-needs/needs.json
```

Expected diff: a single `referenceDate` line. Then find where it comes from:

```bash
grep -rn "referenceDate\|reference_date" src/quarto_needs/config.py src/quarto_needs/analysis.py | head
```

`config.reference_date` is the resolver. Check whether it already honours a pin — `SOURCE_DATE_EPOCH` appears in the `Makefile`'s `diff-example`/`impact-example` targets, which suggests a deterministic-date mechanism already exists.

- [ ] **Step 2: Choose the fix**

Preferred: **pin the example's reference date** so the artifact is deterministic — either through the example's own `.quarto-needs.toml` if the configuration supports an explicit reference date, or by having the test that regenerates it set the same pin the `Makefile` targets already use.

Fallback: **stop tracking the artifact** (`git rm --cached`, confirm `.gitignore` covers it) — but only after checking nothing depends on it being present in a fresh clone. Task 5 just fixed exactly that class of dependency for another fixture; do not create a new one here. If any test reads it without regenerating it, this fallback is not available.

- [ ] **Step 3: Prove it**

```bash
.venv/bin/python -m pytest -q
git status --short
```

Expected: clean tree after a full suite run. That is the acceptance condition.

- [ ] **Step 4: Commit**

```bash
git add -A examples/book .gitignore
git commit -m "test: stop a tracked artifact from changing with the calendar

examples/book/.quarto-needs/needs.json embedded referenceDate, so every
test run on a new day dirtied the tree.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Document and test public artifact compatibility

**Files:**
- Create: `docs/schema-compatibility.md`
- Test: `tests/test_schema_compatibility.py`

- [ ] **Step 1: Inventory**

```bash
ls schemas/
grep -rn "schemaVersion\|SCHEMA_VERSION" src/quarto_needs/*.py src/quarto_needs/**/*.py | grep -v test
```

Classify every result as **public-versioned**, **internal-generated**, or **test-fixture-only**. Record the classification in the document — the inventory is the deliverable, not a step toward it.

- [ ] **Step 2: Write the policy document**

`docs/schema-compatibility.md` must state, concretely and with the repository's actual schema names:

- the three classifications and which artifacts fall in each;
- what counts as an additive (compatible) change: a new optional field, a new enum member in an output-only position;
- what counts as breaking: removing or renaming a field, narrowing a type, changing a field's meaning, changing default ordering;
- that a breaking change MUST bump the schema version string, and that the old version's tests stay until the version is retired;
- that adding a Python attribute MUST NOT expose it publicly — public projections are built field-by-field from an allowlist, the pattern `graph_projection.py` documents in its own module docstring as "deny by default";
- that serialization is deterministic (`sort_keys=True`, explicit orderings) and that determinism is part of the contract, not an implementation detail.

- [ ] **Step 3: Write the guard test**

```python
"""Guards the 'deny by default' property of public projections.

Adding a field to an internal dataclass must never publish it. These tests
fail loudly when a projection starts emitting a key nobody declared.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_graph_node_fields_are_an_explicit_allowlist() -> None:
    from quarto_needs.graph_projection import PUBLIC_NODE_FIELDS, PublicNode

    node = PublicNode(
        id="A", title="A", type="system-requirement", status="draft",
        priority=None, tags=(), href="#A",
    )
    # Every emitted key must be declared. `change`/`technology` are
    # conditionally included, so the emitted set is a subset.
    assert set(node.to_dict()) <= set(PUBLIC_NODE_FIELDS)


def test_every_published_schema_declares_its_version() -> None:
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        assert "$schema" in document, path.name
        assert "$id" in document or "title" in document, path.name
```

Read `graph_projection.py`'s actual `PublicNode` signature before writing this — the constructor arguments above must match it exactly.

- [ ] **Step 4: Run, then commit**

```bash
.venv/bin/python -m pytest tests/test_schema_compatibility.py -q
.venv/bin/python -m pytest -q
git add docs/schema-compatibility.md tests/test_schema_compatibility.py
git commit -m "docs: define public artifact compatibility policy and guard it

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: The minimal example, and the architecture documentation

**Files:**
- Create: `examples/minimal/` (`_quarto.yml`, `index.qmd`, `.quarto-needs.toml`, `README.md`)
- Create: `tests/test_minimal_example.py`
- Modify: `ARCHITECTURE.md`, `docs/architecture/domain-model.md`, `docs/architecture/building-blocks.md`, `docs/ROADMAP.md`
- Create: `docs/phase-core-stabilization.md`

- [ ] **Step 1: Build the example**

Roughly 15-30 objects telling one coherent story — not a feature tour:

```text
STK-001  (stakeholder need)
   |
   v
REQ-001 ──> ADR-001        (decision addressing the requirement)
   |
   ├──────> COMP-001       (component implementing it)
   |
   ├──────> TC-001 ──> EVD-001
   └──────> TC-002 ──> EVD-002
```

Use `need-table`, one traceability matrix, and one bounded `need-graph`. No federation, no migration, no dashboard, no C4 unless a single system/container pair genuinely fits the story.

The `README.md` explains the engineering story, not the feature list. It answers: *can a new user understand the canonical model without reading the Quarto-Needs source?*

- [ ] **Step 2: Write its integration test**

```python
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "minimal"


def test_the_minimal_example_analyzes_cleanly() -> None:
    config = load_config(EXAMPLE)
    result = analyze_project(EXAMPLE, config=config)
    assert result.snapshot is not None
    errors = [item for item in result.findings if item.severity == "error"]
    assert errors == [], errors


def test_the_minimal_example_models_one_complete_traceability_chain() -> None:
    result = analyze_project(EXAMPLE, config=load_config(EXAMPLE))
    assert result.snapshot is not None
    ids = set(result.snapshot.objects_by_id)
    assert {"STK-001", "REQ-001", "ADR-001", "COMP-001",
            "TC-001", "EVD-001"} <= ids


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_the_minimal_example_renders() -> None:
    subprocess.run(
        ["quarto", "render", str(EXAMPLE)],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    assert (EXAMPLE / "_site" / "index.html").is_file()
```

Adjust the ID set to whatever the example actually declares. Run it and iterate until green.

- [ ] **Step 3: Write the phase document**

`docs/phase-core-stabilization.md`, following the shape of the existing `docs/phase-*.md` files. It must record:

1. what transitional architecture was removed (the `EngineeringObject` validation bridge; `LEGACY_CODES`);
2. the final semantic pipeline;
3. that **no benchmarking was performed and none was needed** — the only performance change was making `analysis.py` consistent with itself, and Phase 8 owns measurement;
4. the two reproducibility defects fixed, and how;
5. the compatibility policy introduced;
6. the Quarto minimum-version result, including that its CI wiring is unverified while the Actions quota is exhausted;
7. the minimal example;
8. any transitional API deliberately retained, and why (`EngineeringObject`, `analyze_objects`, `_legacy_objects` if it survived for `unsupported`).

Do not rewrite historical phase documents to pretend the stabilized architecture existed earlier.

- [ ] **Step 4: Update the architecture docs**

In `ARCHITECTURE.md`'s canonical-pipeline block, show declaration-native structural validation and snapshot-native rule evaluation as distinct stages. In `docs/architecture/domain-model.md`, remove the legacy bridge from the pipeline description. Keep the edits proportionate — this is a correction, not a rewrite.

In `docs/ROADMAP.md`, add the stabilization phase and note explicitly that benchmark corpora remain Phase 8's scope, so the two are not conflated again later.

- [ ] **Step 5: Full verification and commit**

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m quarto_needs.cli_entry --root examples/minimal check
.venv/bin/python -m quarto_needs.cli_entry --root examples/quarto-needs check
git status --short
```

Report which of these actually ran. If `quarto` is absent, say the render test was skipped rather than implying it passed.

```bash
git add examples/minimal tests/test_minimal_example.py docs ARCHITECTURE.md
git commit -m "feat: add a minimal example and document the stabilized core

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Final report

Answer, with evidence:

- **Changed** — the concrete architectural changes.
- **Preserved** — what stayed observably identical, and how that was proven (Task 1's characterization tests passing unchanged is the primary evidence).
- **Removed** — the `EngineeringObject` validation bridge, `LEGACY_CODES`, and whatever else went.
- **Retained** — every transitional API deliberately kept, and why.
- **Not done** — benchmarks (Phase 8), and anything the Non-goals list caught.
- **Verification** — exact commands and outcomes, including what was skipped for a missing tool.

The question the reviewer must be able to answer yes to:

> Can Quarto-Needs keep adding capabilities without adding another semantic centre?
