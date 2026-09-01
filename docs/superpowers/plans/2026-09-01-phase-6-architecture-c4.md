# Phase 6 — Architecture Model and C4 Projections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formalize `actor`/`external-system`/`system`/`container` as first-class object types alongside the existing `component`/`source-module`, add the `part-of` relation (the missing inverse of `decomposes`), and generate Mermaid C4 Context/Container/Component diagrams (plus a plain Code-level table) from the canonical graph — proven end to end by retrofitting `examples/quarto-needs/`'s own architecture into the new hierarchy.

**Architecture:** A thin Python module (`c4_projection.py`) reuses the existing `select_graph`/`build_projection` machinery (`graph_projection.py`) with a `("part-of", "decomposes", "depends-on")` relation allowlist and `depth=1` from one focus object — zero new selection algorithm. A second new module (`c4_render.py`, mirroring the existing `graph_render.py`) turns that projection into Mermaid C4 syntax (or a plain Markdown table for Code level) as plain text, exactly like the existing `mermaid_source()` does for the general graph view. `graph_output.py` gains a `write_c4_projections()` that pre-renders one JSON file per `system`/`container` object into `.quarto-needs/graphs/`, called from the same CLI step that already writes the general graph views. A new Lua shortcode (`need-c4`, in a new `c4.lua`) is a thin reader: it loads the pre-rendered text and hands it to the *existing* `views.mermaid_inline_svg` helper — no C4-specific logic lives in Lua at all.

**Tech Stack:** Python 3 (stdlib only for new code), TOML project config (`.quarto-needs.toml`), Lua (Quarto/Pandoc filter), Mermaid.js (via Quarto's bundled renderer, as already used by `need-graph`).

**Spec:** `docs/superpowers/specs/2026-09-01-phase-6-architecture-c4-design.md`

## Global Constraints

- Python remains the sole semantic authority; Lua only reads pre-computed, pre-rendered artifacts — never re-derives C4 macro mappings or graph selection itself. (Spec, Section 4; confirmed as this project's binding invariant in `docs/superpowers/specs/2026-08-29-quarto-needs-full-product-vision.md`.)
- No new architecture model separate from the existing typed-object/relation graph — every new type/relation is a normal citizen of `relations.py`/`config.py`/`rules.py`, validated the same way every other type already is.
- Every commit: full `pytest` suite green, no GitHub Actions dependency (the user's Actions quota is exhausted — verify everything locally).
- TDD throughout: write the failing test first, watch it fail for the stated reason, write minimal code, watch it pass, then commit in the project's established `feat:`/`test:`/`docs:` message style (or a single `feat:` commit carrying its own test when the two are inseparable, matching this project's own recent commit history).
- **Known, deliberate simplification (flag to the user when this plan is presented, not silently):** the current `.need`-block parser grammar (`parser.py`) has *no* syntax for inline per-relation attributes at all — `RelationToken(key, target, {}, location)` is hardcoded to an empty dict (`parser.py:201`). The approved spec assumed `depends-on: TARGET technology="..." description="..."` could already be authored; it cannot. This plan does **not** add that parser grammar (a separate, riskier, cross-cutting change affecting every relation, not just C4's). `depends-on` interaction arrows in this phase's diagrams therefore show the relation's fixed catalog label ("Depends on"), not a custom technology/description. A follow-on slice can add relation-attribute authoring syntax once there's a second consumer that needs it.
- **Known, deliberate simplification #2:** each C4 view shows interaction edges (`depends-on`) reaching the *focus node only*, not its children — e.g. the Container-level view shows actors/external-systems connected to the system as a whole, not ones connected to a specific container two hops away. This keeps the selection a single `select_graph(seeds=(focus,), depth=1)` call (Spec Section 3's "one generic operation" claim, kept literally true) rather than a two-step per-child expansion. Revisit once the self-hosted retrofit's own content actually has container-specific interaction edges to show.

---

### Task 1: `part-of` relation — the missing inverse of `decomposes`

**Files:**
- Modify: `src/quarto_needs/relations.py` (add one `RelationKind` to `DEFAULT_RELATION_CATALOG`)
- Modify: `tests/test_relations.py`

**Interfaces:**
- Produces: `DEFAULT_RELATION_CATALOG.resolve("part-of")` resolves to a `RelationKind` with its own distinct `v1_name == "part-of"` (NOT shared with `decomposes`), `catalog_name == "part-of"`, `semantic_family == "decomposition"`, `source_role == "part"`, `target_role == "whole"`. `DEFAULT_RELATION_CATALOG.inverse_v1_name("decomposes") == "part-of"` and `.inverse_v1_name("part-of") == "decomposes"` — a genuine inverse-direction pair, mirroring how `implements`/`implemented-by` behave (each keeps its own v1_name specifically so a per-direction `relation_policies` entry can target one direction without also matching the other). This is *not* the `derives-from`/`derived-from` shape (which correctly *do* share a v1_name, because they are same-direction synonyms with identical, non-swapped roles — `decomposes`/`part-of` have swapped roles, so sharing a v1_name would let a policy meant for one direction silently apply to the other; see Task 2's rule, which must handle both authored directions explicitly for exactly this reason).

- [ ] **Step 1: Write the failing tests**

Update the exact-set assertion in `tests/test_relations.py` (currently line 7-17) to include the new name:

```python
def test_default_catalog_covers_legacy_and_decision_authoring_names() -> None:
    expected = {
        "conflicts-with", "constrains", "decomposes", "depends-on",
        "derived-from", "derives-from", "evidenced-by", "evidences",
        "implemented-by", "implements", "justified-by", "mitigates",
        "part-of",
        "references", "refines", "validated-by", "verified-by", "verifies",
        "addresses", "addressed-by", "applies-to", "confirmed-by", "confirms",
        "supersedes", "superseded-by",
    }
    assert set(DEFAULT_RELATION_CATALOG.names) == expected
    assert DEFAULT_RELATION_CATALOG.version == "4"
```

(Version bumps from `"3"` to `"4"` — the catalog's own `version` field changes whenever its entry set changes; confirm this is indeed how prior additions bumped it by checking `git log -p -- src/quarto_needs/relations.py` if in doubt, but every existing decision-relation addition in the current file landed under a single `"3"`, so this is the first bump since decision relations were added — treat `"4"` as correct for this addition.)

Add a new test right after `test_inverse_authoring_forms_share_semantic_families_and_swap_roles` (append to `tests/test_relations.py`):

```python
def test_part_of_is_decomposes_own_missing_inverse() -> None:
    decomposes = DEFAULT_RELATION_CATALOG.resolve("decomposes")
    part_of = DEFAULT_RELATION_CATALOG.resolve("part-of")

    assert decomposes.v1_name == "decomposes"
    assert part_of.v1_name == "part-of"
    assert decomposes.semantic_family == part_of.semantic_family == "decomposition"
    assert (decomposes.source_role, decomposes.target_role) == ("whole", "part")
    assert (part_of.source_role, part_of.target_role) == ("part", "whole")
    assert decomposes.inverse_label == part_of.direct_label
    assert part_of.inverse_label == decomposes.direct_label
    assert DEFAULT_RELATION_CATALOG.inverse_v1_name("decomposes") == "part-of"
    assert DEFAULT_RELATION_CATALOG.inverse_v1_name("part-of") == "decomposes"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_relations.py -v`
Expected: `test_default_catalog_covers_legacy_and_decision_authoring_names` FAILs (missing `"part-of"` from the actual set, version mismatch); `test_part_of_is_decomposes_own_missing_inverse` FAILs with `ValueError: Unknown relation type: part-of` from `resolve()`.

- [ ] **Step 3: Add the relation kind**

In `src/quarto_needs/relations.py`, change the catalog version and add one entry (edit the `DEFAULT_RELATION_CATALOG = RelationCatalog.create(...)` call, currently lines 79-111):

```python
DEFAULT_RELATION_CATALOG = RelationCatalog.create(
    "4",
    (
        RelationKind("derives-from", "derives-from", "derives-from", "derivation", "Derives from", "Source for", "derived", "source", "target_to_source", "target_to_source"),
        RelationKind("derived-from", "derives-from", "derives-from", "derivation", "Derives from", "Source for", "derived", "source", "target_to_source", "target_to_source"),
        RelationKind("refines", "refines", "refines", "refinement", "Refines", "Refined by", "refinement", "subject", "target_to_source", "target_to_source"),
        RelationKind("decomposes", "decomposes", "decomposes", "decomposition", "Decomposes", "Part of", "whole", "part", "none", "source_to_target"),
        RelationKind("part-of", "part-of", "part-of", "decomposition", "Part of", "Decomposes", "part", "whole", "source_to_target", "source_to_target"),
        RelationKind("depends-on", "depends-on", "depends-on", "dependency", "Depends on", "Depended on by", "dependent", "dependency", "target_to_source", "target_to_source"),
```

(Only the two lines shown as new/changed — `"4"` replacing `"3"`, and the new `part-of` line inserted right after `decomposes` — the rest of the tuple is unchanged; do not retype the whole catalog. Note `part-of`'s `catalog_name`/`v1_name` are `"part-of"`, its own distinct value — NOT `"decomposes"` — matching `implements`/`implemented-by`'s pattern of each direction keeping its own v1_name, since `decomposes`/`part-of` have swapped roles rather than being same-direction synonyms like `derives-from`/`derived-from`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_relations.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. (A version-string bump to a shared catalog constant is exactly the kind of change that can surface an unexpected golden-fixture assertion elsewhere — if anything fails here, read the failure before touching test expectations; it likely means some other test hardcodes `"3"` and needs the same intentional bump, not a sign this step is wrong.)

- [ ] **Step 6: Commit**

```bash
git add src/quarto_needs/relations.py tests/test_relations.py
git commit -m "$(cat <<'EOF'
feat: add part-of as decomposes's missing inverse relation

A container/component/source-module can only declare containment
today from the parent's side (decomposes: child, child, ...); nothing
lets a child self-declare part-of: parent. Needed before Phase 6's
architecture hierarchy can be authored from either direction, the
same shape implements/implemented-by already has.
EOF
)"
```

---

### Task 2: ARC001 — layer-adjacency structural rule, plus reusing the existing cardinality mechanism

**Files:**
- Modify: `src/quarto_needs/rules.py`
- Modify: `tests/test_rules.py`
- Modify: `tests/test_baseline.py` (the `RULE_SET_VERSION` pin)

**Interfaces:**
- Consumes: `RuleContext.snapshot.relations` (each a `RelationRecord` with `.v1_name`, `.source`, `.target`), `RuleContext.snapshot.objects_by_id` (maps id → `ObjectRecord` with `.type`), `Finding(code, severity, message, object_id, location, properties)` (`diagnostics.py`), `RULES: Mapping[str, RuleSpec]` registry pattern (`rules.py`).
- Produces: rule code `"ARC001"`, always-error (mirrors `DEC005`'s `supported_severities=("error",)` — a `part-of` layer violation is a structural contradiction, not a tunable style preference). `RULE_SET_VERSION` becomes `"7"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rules.py` (uses the existing `make_config`/`snapshot_with`/`obj`/`Relation` helpers already defined at the top of that file):

```python
def test_arc001_flags_a_part_of_edge_that_skips_a_layer() -> None:
    config = make_config(tmp_path=Path("."), document="")  # placeholder replaced below
```

Replace that placeholder immediately with the real test (the helper needs a real `tmp_path` fixture, not a literal `Path(".")`):

```python
def test_arc001_flags_a_part_of_edge_that_skips_a_layer(tmp_path: Path) -> None:
    config = make_config(tmp_path, "")
    snapshot = snapshot_with(
        obj("SYS-1", type="system"),
        obj(
            "COMP-1",
            type="component",
            relations=[Relation("part-of", "COMP-1", "SYS-1")],
        ),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "ARC001"]
    assert [f.object_id for f in findings] == ["COMP-1"]
    assert findings[0].severity == "error"
    assert findings[0].properties == {
        "sourceType": "component",
        "targetType": "system",
    }


def test_arc001_flags_a_same_layer_part_of_edge(tmp_path: Path) -> None:
    config = make_config(tmp_path, "")
    snapshot = snapshot_with(
        obj("CONTAINER-1", type="container"),
        obj(
            "CONTAINER-2",
            type="container",
            relations=[Relation("part-of", "CONTAINER-2", "CONTAINER-1")],
        ),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "ARC001"]
    assert [f.object_id for f in findings] == ["CONTAINER-2"]


def test_arc001_allows_a_valid_adjacent_layer_part_of_edge(tmp_path: Path) -> None:
    config = make_config(tmp_path, "")
    snapshot = snapshot_with(
        obj("SYS-1", type="system"),
        obj(
            "CONTAINER-1",
            type="container",
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "ARC001"]
    assert findings == []


def test_arc001_ignores_part_of_edges_with_an_unrecognized_layer_type(tmp_path: Path) -> None:
    """A part-of edge outside the fixed C4 layer set (e.g. two unrelated
    custom types someone reuses part-of for) is not this rule's concern —
    it neither passes nor fails a layer check that doesn't apply to it."""
    config = make_config(tmp_path, "")
    snapshot = snapshot_with(
        obj("A", type="widget"),
        obj("B", type="widget", relations=[Relation("part-of", "B", "A")]),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "ARC001"]
    assert findings == []


def test_part_of_max_cardinality_uses_the_existing_generic_policy_mechanism(
    tmp_path: Path,
) -> None:
    """No new cardinality code: part-of's 'at most one parent' half is just
    the existing REQ010 maximum-per-source policy, configured.

    Only the maximum half is exercised here, deliberately: REQ010's
    minimum-per-source check only inspects objects that already have at
    least one edge of the policy's relation (its `counts` dict is built
    solely from existing `snapshot.relations`, so an object with *zero*
    part-of edges never becomes a `counts` key and the minimum check never
    sees it — confirmed by reading `_cardinality` directly, rules.py lines
    140-162, before writing this test). "Exactly one parent" is therefore
    only half-enforced by the existing generic mechanism: a component with
    two parents is caught; a component with none is not. This gap is real
    and pre-existing (not introduced here) — Task 14's docs must name it
    explicitly rather than overselling "exactly one parent" as fully
    enforced.
    """
    config = make_config(
        tmp_path,
        '[relations."part-of"]\nmaximum-per-source = 1\n',
    )
    snapshot = snapshot_with(
        obj("SYS-1", type="system"),
        obj("CONTAINER-1", type="container"),
        obj(
            "DOUBLE-PARENTED",
            type="component",
            relations=[
                Relation("part-of", "DOUBLE-PARENTED", "SYS-1"),
                Relation("part-of", "DOUBLE-PARENTED", "CONTAINER-1"),
            ],
        ),
    )
    findings = [f for f in run_rules(snapshot, config) if f.code == "REQ010"]
    assert [f.object_id for f in findings] == ["DOUBLE-PARENTED"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_rules.py -k arc001 -v`
Expected: all four ARC001 tests FAIL — `run_rules` never yields any `"ARC001"`-coded finding because the rule doesn't exist yet, so `findings` is always `[]`, and the three tests expecting non-empty results fail on the list-equality assertion.

Run: `.venv/bin/python -m pytest tests/test_rules.py -k cardinality_uses_the_existing -v`
Expected: this one may already PASS without any new code — `part-of` resolves through `DEFAULT_RELATION_CATALOG` from Task 1, and REQ010/`_cardinality` already exists and needs no change for this test. Run it and read the actual result; if it already passes, that is the confirmation this test exists to provide (the generic mechanism needs zero new code for the maximum-per-source half), and Step 3 below only needs to add ARC001, not touch `_cardinality`.

- [ ] **Step 3: Implement the ARC001 rule**

Add a private layer-order table and the evaluator function to `src/quarto_needs/rules.py`, placed near the other structural evaluators (e.g. right before `_decision_cycle`):

```python
_C4_LAYER_ORDER = ("system", "container", "component", "source-module")
_C4_LAYER_INDEX = {name: index for index, name in enumerate(_C4_LAYER_ORDER)}


def _architecture_layer_adjacency(ctx: RuleContext) -> Iterable[Finding]:
    """part-of/decomposes must connect a layer to the one exactly above it.

    part-of and decomposes are a genuine inverse-direction pair (like
    implements/implemented-by, not like derives-from/derived-from's same-
    direction synonym pair) — Task 1 gives them distinct v1_names for
    exactly this reason: a per-direction relation_policies entry must be
    able to target one authoring direction without silently also matching
    the other. This rule handles both authored directions explicitly
    rather than assuming only one is ever used: a part-of edge's source is
    the child (deeper layer) and target is the parent (shallower layer); a
    decomposes edge is the reverse. Types outside the fixed C4 layer set
    (actor, external-system, or any project-specific type never meant to
    participate in this hierarchy) are not this rule's concern — they
    simply never match the layer table.
    """
    for edge in ctx.snapshot.relations:
        if edge.authored_name == "part-of":
            child_id, parent_id = edge.source, edge.target
        elif edge.authored_name == "decomposes":
            child_id, parent_id = edge.target, edge.source
        else:
            continue
        child = ctx.snapshot.objects_by_id.get(child_id)
        parent = ctx.snapshot.objects_by_id.get(parent_id)
        if child is None or parent is None:
            continue
        child_index = _C4_LAYER_INDEX.get(child.type)
        parent_index = _C4_LAYER_INDEX.get(parent.type)
        if child_index is None or parent_index is None:
            continue
        if child_index != parent_index + 1:
            yield Finding(
                "ARC001",
                RULES["ARC001"].default_severity,
                f"{child_id} ({child.type}) may not be a child of "
                f"{parent_id} ({parent.type}): part-of/decomposes must "
                "connect a layer to the layer exactly above it "
                f"({' > '.join(_C4_LAYER_ORDER)})",
                child_id,
                edge.provenance[0] if edge.provenance else None,
                {"sourceType": child.type, "targetType": parent.type},
            )
```

Register it in the `RULES` dict (`rules.py`, in the tuple literal — add this entry, keeping the existing entries and their trailing comma untouched):

```python
    RuleSpec("ARC001", "Architecture layer skipped", "part-of must connect adjacent C4 layers (system > container > component > source-module).", "error", supported_severities=("error",), evaluator=_architecture_layer_adjacency),
```

Bump the version constant right after the `RULES` dict:

```python
RULE_SET_VERSION = "7"
```

- [ ] **Step 4: Update the pinned `RULE_SET_VERSION` test**

`tests/test_baseline.py` line 58 already reads `RULE_SET_VERSION` from the module (`assert payload["ruleSetVersion"] == RULE_SET_VERSION`) — it is a live import, not a hardcoded literal, so it needs **no edit**. Confirm this by reading `tests/test_baseline.py` lines 1-60 before assuming; if any *other* test hardcodes the literal string `"6"` instead of importing the constant, fix that one to import `RULE_SET_VERSION` instead of hardcoding — grep first:

```bash
grep -rn '"6"' tests/*.py | grep -i rule
```

Fix any hit the same way (import and compare, don't hardcode the new literal).

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_rules.py -v`
Expected: all pass, including the new ARC001 tests and the cardinality-reuse test.

- [ ] **Step 6: Falsify — confirm ARC001 actually catches what it claims to**

Temporarily comment out the `if source_index != target_index + 1:` check's body (replace `yield Finding(...)` with `pass` and remove the `yield`), rerun:

Run: `.venv/bin/python -m pytest tests/test_rules.py -k "arc001_flags" -v`
Expected: both `test_arc001_flags_*` tests FAIL (no findings produced at all). This confirms the check is load-bearing, not a no-op. Revert the temporary change (restore the real `yield Finding(...)` body) before continuing.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/quarto_needs/rules.py tests/test_rules.py
git commit -m "$(cat <<'EOF'
feat: add ARC001 architecture layer-adjacency rule

part-of's existing allowed_source_types/allowed_target_types policy
mechanism can only check set membership on each side independently,
not that a specific pairing is the adjacent one — it would let
component part-of system slip through, skipping container. ARC001
checks the fixed system>container>component>source-module layer
order directly. The 'exactly one parent' constraint needs no new
code at all: it's the existing REQ010 minimum/maximum-per-source
policy, configured for part-of by a project that wants it (proven
here, not yet configured in the self-hosted example itself).
EOF
)"
```

---

### Task 3: `PublicNode.technology` — a narrow, named pass-through field

**Files:**
- Modify: `src/quarto_needs/graph_projection.py`
- Modify: `tests/test_graph_projection.py`

**Interfaces:**
- Consumes: `ObjectRecord.attributes: Mapping[str, object]` (already exists on every snapshot object).
- Produces: `PublicNode.technology: str | None` — populated from `record.attributes.get("technology")` when that value is a non-empty string, else `None`. Serializes into `to_dict()` only when not `None` (mirrors the existing `change` field's conditional-inclusion pattern at `graph_projection.py:57-58`).

- [ ] **Step 1: Write the failing test**

Find the existing test file's `build_projection` exercise (search `tests/test_graph_projection.py` for a test constructing a snapshot and calling `build_projection`, to match its existing fixture-building style before writing this addition — read the file's first 40 lines to copy its exact `snapshot`/`ObjectRecord` construction helper if one exists there, rather than reinventing one; if the file already has a shared fixture builder, use it verbatim). Append:

```python
def test_public_node_surfaces_a_containers_technology_attribute() -> None:
    snapshot = _snapshot(  # use this file's existing snapshot-building helper
        ObjectRecord(
            id="CONTAINER-1",
            type="container",
            title="Python package",
            status="implemented",
            body="",
            rationale="",
            attributes={"technology": "Python 3.12"},
            locations=(),
        ),
        ObjectRecord(
            id="SYS-1",
            type="system",
            title="Quarto-Needs",
            status="implemented",
            body="",
            rationale="",
            attributes={},
            locations=(),
        ),
    )
    projection = build_projection(
        snapshot, node_ids=("CONTAINER-1", "SYS-1"), view_id="test-view"
    )
    by_id = {node.id: node for node in projection.nodes}
    assert by_id["CONTAINER-1"].technology == "Python 3.12"
    assert by_id["SYS-1"].technology is None
    assert by_id["CONTAINER-1"].to_dict()["technology"] == "Python 3.12"
    assert "technology" not in by_id["SYS-1"].to_dict()
```

(If this file has no existing `_snapshot`/similar helper and every other test builds an `AnalysisSnapshot` directly, construct one directly the same way instead — read the file first; do not introduce a second, inconsistent fixture style.)

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_graph_projection.py -k technology -v`
Expected: FAIL with `AttributeError: 'PublicNode' object has no attribute 'technology'`.

- [ ] **Step 3: Add the field**

In `src/quarto_needs/graph_projection.py`, extend `PublicNode` (currently lines 36-59):

```python
@dataclass(frozen=True, slots=True)
class PublicNode:
    id: str
    title: str
    type: str
    status: str
    priority: str | None
    tags: tuple[str, ...]
    href: str
    change: str | None = None
    technology: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "priority": self.priority,
            "tags": list(self.tags),
            "href": self.href,
        }
        if self.change is not None:
            payload["change"] = self.change
        if self.technology is not None:
            payload["technology"] = self.technology
        return payload
```

Add a small helper and use it in `build_projection` (currently lines 314-339):

```python
def _technology_of(record: ObjectRecord) -> str | None:
    value = record.attributes.get("technology")
    return value if isinstance(value, str) and value.strip() else None
```

```python
    nodes = tuple(
        PublicNode(
            id=record.id,
            title=record.title,
            type=record.type,
            status=record.status,
            priority=record.priority,
            tags=record.tags,
            href=_public_href(record),
            technology=_technology_of(record),
        )
        for record in snapshot.objects
        if record.id in selected
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_graph_projection.py -k technology -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. `technology` defaults to `None` and is omitted from `to_dict()` for every existing object (nothing today has a `"technology"` attribute except the not-yet-written C4 retrofit), so no existing golden JSON fixture should change. If any golden fixture *does* fail here, that fixture was asserting exact key sets from `to_dict()` in a way this additive, default-`None` field should not have touched — investigate before editing the fixture; do not blindly regenerate it.

- [ ] **Step 6: Commit**

```bash
git add src/quarto_needs/graph_projection.py tests/test_graph_projection.py
git commit -m "$(cat <<'EOF'
feat: surface a container's technology attribute on PublicNode

A narrow, named pass-through (not the object's whole attributes
dict, matching this module's deny-by-default field-by-field
construction) — Mermaid's C4 Container()/Component() macros both
take an optional technology label, and nothing in the public
projection carries it yet.
EOF
)"
```

---

### Task 4: `c4_projection.py` — one focus node, one level down

**Files:**
- Create: `src/quarto_needs/c4_projection.py`
- Test: `tests/test_c4_projection.py`

**Interfaces:**
- Consumes: `AnalysisSnapshot` (from `snapshot.py`), `select_graph`/`build_projection`/`GraphProjection` (from `graph_projection.py`, signatures confirmed at `graph_projection.py:249-364`).
- Produces: `class C4ViewError(Exception)`; `def build_c4_view(snapshot: AnalysisSnapshot, *, focus_id: str, level: str, limits: Mapping[str, int] | None = None) -> GraphProjection`. `level` must be one of `"context"`, `"container"`, `"component"`. Later tasks (Lua wiring) call this by exactly this name/signature.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_projection.py`:

```python
from __future__ import annotations

import pytest

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4_projection import C4ViewError, build_c4_view
from quarto_needs.model import EngineeringObject, Relation


def _obj(id: str, *, type: str, relations: list[Relation] | None = None) -> EngineeringObject:
    return EngineeringObject(id, type, id.title(), status="draft", relations=relations or [])


def _snapshot(*objects: EngineeringObject):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None
    return result.snapshot


def test_context_view_shows_the_system_and_its_direct_neighbors_only() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj(
            "CONTAINER-1",
            type="container",
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    node_ids = {node.id for node in projection.nodes}
    assert node_ids == {"SYS-1", "ACTOR-1"}
    assert "CONTAINER-1" not in node_ids


def test_container_view_shows_the_systems_direct_containers() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj(
            "CONTAINER-1",
            type="container",
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
        _obj(
            "COMP-1",
            type="component",
            relations=[Relation("part-of", "COMP-1", "CONTAINER-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    node_ids = {node.id for node in projection.nodes}
    assert node_ids == {"SYS-1", "ACTOR-1", "CONTAINER-1"}
    assert "COMP-1" not in node_ids


def test_component_view_shows_the_containers_direct_components() -> None:
    snapshot = _snapshot(
        _obj("CONTAINER-1", type="container"),
        _obj(
            "COMP-1",
            type="component",
            relations=[Relation("part-of", "COMP-1", "CONTAINER-1")],
        ),
        _obj(
            "SRC-1",
            type="source-module",
            relations=[Relation("part-of", "SRC-1", "COMP-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="CONTAINER-1", level="component")
    node_ids = {node.id for node in projection.nodes}
    assert node_ids == {"CONTAINER-1", "COMP-1"}
    assert "SRC-1" not in node_ids


def test_context_and_container_levels_require_a_system_focus() -> None:
    snapshot = _snapshot(_obj("CONTAINER-1", type="container"))
    with pytest.raises(C4ViewError, match="requires a 'system' focus"):
        build_c4_view(snapshot, focus_id="CONTAINER-1", level="context")
    with pytest.raises(C4ViewError, match="requires a 'system' focus"):
        build_c4_view(snapshot, focus_id="CONTAINER-1", level="container")


def test_component_level_requires_a_container_focus() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"))
    with pytest.raises(C4ViewError, match="requires a 'container' focus"):
        build_c4_view(snapshot, focus_id="SYS-1", level="component")


def test_unknown_focus_id_raises() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"))
    with pytest.raises(C4ViewError, match="MISSING"):
        build_c4_view(snapshot, focus_id="MISSING", level="context")


def test_unsupported_level_raises() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"))
    with pytest.raises(C4ViewError, match="unsupported C4 level"):
        build_c4_view(snapshot, focus_id="SYS-1", level="code")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_c4_projection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quarto_needs.c4_projection'`.

- [ ] **Step 3: Implement**

Create `src/quarto_needs/c4_projection.py`:

```python
"""One C4 view: a focus object plus one level of its part-of/depends-on
neighborhood.

Reuses graph_projection.py's existing bounded selection (select_graph) and
projection builder (build_projection) unchanged — Context, Container, and
Component views are all the same operation (focus + depth 1 over
decomposes/depends-on), differing only in which relations are allowed and
what type the focus must be. No new selection algorithm.
"""
from __future__ import annotations

from typing import Mapping

from .graph_projection import GraphProjection, build_projection, select_graph
from .snapshot import AnalysisSnapshot


class C4ViewError(Exception):
    """Raised when a C4 view is requested for an invalid focus/level pair."""


_LEVEL_FOCUS_TYPE: Mapping[str, str] = {
    "context": "system",
    "container": "system",
    "component": "container",
}

_LEVEL_RELATIONS: Mapping[str, tuple[str, ...]] = {
    "context": ("depends-on",),
    "container": ("part-of", "decomposes", "depends-on"),
    "component": ("part-of", "decomposes", "depends-on"),
}


def build_c4_view(
    snapshot: AnalysisSnapshot,
    *,
    focus_id: str,
    level: str,
    limits: Mapping[str, int] | None = None,
) -> GraphProjection:
    if level not in _LEVEL_FOCUS_TYPE:
        raise C4ViewError(
            f"unsupported C4 level: {level!r} (expected one of "
            f"{', '.join(sorted(_LEVEL_FOCUS_TYPE))})"
        )
    focus = snapshot.objects_by_id.get(focus_id)
    if focus is None:
        raise C4ViewError(f"{focus_id!r} is not a known object")
    expected_type = _LEVEL_FOCUS_TYPE[level]
    if focus.type != expected_type:
        raise C4ViewError(
            f"level={level!r} requires a {expected_type!r} focus, "
            f"but {focus_id!r} is {focus.type!r}"
        )
    relations = _LEVEL_RELATIONS[level]
    selection = select_graph(
        snapshot, seeds=(focus_id,), relations=relations, depth=1, limits=limits
    )
    return build_projection(
        snapshot,
        node_ids=selection.node_ids,
        view_id=f"c4-{level}-{focus_id}",
        mode="c4",
        relations=relations,
        limits=limits,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_c4_projection.py -v`
Expected: all PASS.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/quarto_needs/c4_projection.py tests/test_c4_projection.py
git commit -m "$(cat <<'EOF'
feat: add build_c4_view, one focus node's C4 neighborhood

Context, Container, and Component views are the same operation —
select_graph(seeds=(focus,), depth=1) over decomposes/depends-on —
differing only in the relation allowlist and the focus's required
type. No new selection algorithm; this is a thin, validated wrapper
over the existing graph_projection.py machinery.
EOF
)"
```

---

### Task 5: `c4_render.py` — Mermaid C4 text and the Code-level table

**Files:**
- Create: `src/quarto_needs/c4_render.py`
- Test: `tests/test_c4_render.py`
- Create fixture directory: `tests/fixtures/c4/` (golden `.mmd`/`.md` files, mirroring `tests/fixtures/graph/golden-catalog.mmd`'s role)

**Interfaces:**
- Consumes: `GraphProjection`/`PublicNode`/`PublicEdge` (from `graph_projection.py` — `PublicEdge.relation` holds the `v1_name` string, confirmed at `graph_projection.py:340-351`).
- Produces: `def c4_mermaid_source(projection: GraphProjection, *, focus_id: str, level: str) -> str` (for `level` in `{"context", "container", "component"}`); `def c4_code_table_markdown(projection: GraphProjection, *, focus_id: str) -> str` (Code level — a Markdown table, not Mermaid).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_render.py`:

```python
from __future__ import annotations

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4_projection import build_c4_view
from quarto_needs.c4_render import c4_code_table_markdown, c4_mermaid_source
from quarto_needs.model import EngineeringObject, Relation


def _obj(id: str, *, type: str, title: str | None = None, attributes=None, relations=None):
    return EngineeringObject(
        id, type, title or id.title(), status="draft",
        attributes=attributes or {}, relations=relations or [],
    )


def _snapshot(*objects):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None
    return result.snapshot


def test_context_diagram_shows_the_system_as_an_opaque_box() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "ACTOR-1", type="actor", title="Requirements Engineer",
            relations=[Relation("depends-on", "ACTOR-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="context")
    assert source.splitlines()[0] == "C4Context"
    assert 'System(' in source
    assert 'Person(' in source
    assert 'Rel(' in source
    assert source.endswith("\n")


def test_container_diagram_wraps_containers_in_a_system_boundary() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj(
            "CONTAINER-1", type="container", title="Python package",
            attributes={"technology": "Python 3.12"},
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="container")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="container")
    assert source.splitlines()[0] == "C4Container"
    assert "System_Boundary(" in source
    assert 'Container(' in source
    assert "Python 3.12" in source
    assert source.rstrip("\n").endswith("}")


def test_component_diagram_wraps_components_in_a_container_boundary() -> None:
    snapshot = _snapshot(
        _obj("CONTAINER-1", type="container", title="Python package"),
        _obj(
            "COMP-1", type="component", title="Declaration parser",
            relations=[Relation("part-of", "COMP-1", "CONTAINER-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="CONTAINER-1", level="component")
    source = c4_mermaid_source(projection, focus_id="CONTAINER-1", level="component")
    assert source.splitlines()[0] == "C4Component"
    assert "Container_Boundary(" in source
    assert "Component(" in source


def test_labels_are_escaped_against_mermaid_syntax() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system", title='System "with quotes"'))
    projection = build_c4_view(snapshot, focus_id="SYS-1", level="context")
    source = c4_mermaid_source(projection, focus_id="SYS-1", level="context")
    assert '"' not in source.split("System(", 1)[1].split(")", 1)[0].replace("'", "")


def test_code_level_renders_a_plain_markdown_table_not_mermaid() -> None:
    snapshot = _snapshot(
        _obj("COMP-1", type="component", title="Declaration parser"),
        _obj(
            "SRC-1", type="source-module", title="QMD declaration parser module",
            attributes={"path": "src/quarto_needs/parser.py", "language": "Python"},
            relations=[Relation("part-of", "SRC-1", "COMP-1")],
        ),
    )
    projection = build_c4_view(snapshot, focus_id="COMP-1", level="component")
    # Code level does not go through build_c4_view (its focus is a component,
    # not a container) — it reads the component's own direct children
    # directly from the snapshot instead. See Step 3's implementation.
    table = c4_code_table_markdown(snapshot, focus_id="COMP-1")
    assert table.splitlines()[0].startswith("|")
    assert "C4Component" not in table
    assert "src/quarto_needs/parser.py" in table
    assert "Python" in table
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_c4_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quarto_needs.c4_render'`.

- [ ] **Step 3: Implement**

Create `src/quarto_needs/c4_render.py`:

```python
"""Mermaid C4 diagram and Code-level table rendering.

Mirrors graph_render.py's role (static text rendering of an
already-computed projection) for the C4-specific diagram types. `_ref`/
`_escape` duplicate graph_render.py's private helpers rather than
importing them — the same choice already made for github_issues.py's
_origin duplicating oslc_http.py's rather than reaching into another
module's underscore-prefixed internals.
"""
from __future__ import annotations

from .graph_projection import GraphProjection, PublicEdge, PublicNode
from .snapshot import AnalysisSnapshot

NODE_PREFIX = "c4_"

_MACRO_BY_TYPE = {
    "actor": "Person",
    "external-system": "System_Ext",
    "system": "System",
    "container": "Container",
    "component": "Component",
}
_DIAGRAM_TYPE = {
    "context": "C4Context",
    "container": "C4Container",
    "component": "C4Component",
}
_BOUNDARY_MACRO = {"container": "System_Boundary", "component": "Container_Boundary"}


def _ref(identifier: str) -> str:
    return NODE_PREFIX + identifier.encode("utf-8").hex()


def _escape(value: str) -> str:
    replaced = value.replace("\\", "/").replace('"', "'")
    return replaced.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _macro_call(node: PublicNode) -> str:
    macro = _MACRO_BY_TYPE[node.type]
    args = [_ref(node.id), f'"{_escape(node.title)}"']
    if node.technology:
        args.append(f'"{_escape(node.technology)}"')
    return f"{macro}({', '.join(args)})"


def _is_child_edge(edge: PublicEdge, *, focus_id: str, child_id: str) -> bool:
    """True if `edge` declares `child_id` as a direct child of `focus_id`.

    Handles both authored directions: a `part-of` edge runs child→parent
    (source=child, target=focus — this project's own retrofit authors
    exclusively this direction), a `decomposes` edge runs parent→child
    (source=focus, target=child). Checking only one direction would miss
    every part-of-authored edge, which is exactly what this project's own
    content uses.
    """
    if edge.relation == "part-of":
        return edge.source == child_id and edge.target == focus_id
    if edge.relation == "decomposes":
        return edge.source == focus_id and edge.target == child_id
    return False


def c4_mermaid_source(projection: GraphProjection, *, focus_id: str, level: str) -> str:
    """Deterministic Mermaid C4 source for one focus node's view.

    Node and edge order follows the projection's own canonical order (the
    same determinism guarantee graph_render.py's mermaid_source makes), so
    two renders of an equivalent projection are byte-identical.
    """
    diagram_type = _DIAGRAM_TYPE[level]
    focus = next(node for node in projection.nodes if node.id == focus_id)
    children = [
        node
        for node in projection.nodes
        if node.id != focus_id
        and any(
            _is_child_edge(edge, focus_id=focus_id, child_id=node.id)
            for edge in projection.edges
        )
    ]
    others = [
        node
        for node in projection.nodes
        if node.id != focus_id and node not in children
    ]

    lines = [diagram_type]
    if level == "context":
        lines.append(f"  {_macro_call(focus)}")
        for node in others:
            lines.append(f"  {_macro_call(node)}")
    else:
        boundary_macro = _BOUNDARY_MACRO[level]
        lines.append(
            f'  {boundary_macro}({_ref(focus.id)}, "{_escape(focus.title)}") {{'
        )
        for node in children:
            lines.append(f"    {_macro_call(node)}")
        lines.append("  }")
        for node in others:
            lines.append(f"  {_macro_call(node)}")

    for edge in projection.edges:
        if edge.relation != "depends-on":
            continue
        lines.append(f'  Rel({_ref(edge.source)}, {_ref(edge.target)}, "{_escape(edge.label)}")')

    return "\n".join(lines) + "\n"


def c4_code_table_markdown(snapshot: AnalysisSnapshot, *, focus_id: str) -> str:
    """A plain Markdown table of one component's direct source-module children.

    Code level is not a diagram: Mermaid has no C4-Code diagram type, and
    source-module objects have no interaction arrows to draw (their only
    relation today is `implements`, to a requirement, not to each other).
    """
    children = sorted(
        (
            snapshot.objects_by_id[relation.source]
            for relation in snapshot.relations
            if relation.authored_name == "part-of"
            and relation.target == focus_id
            and relation.source in snapshot.objects_by_id
            and snapshot.objects_by_id[relation.source].type == "source-module"
        ),
        key=lambda record: record.id,
    )
    lines = ["| ID | Path | Language | Implements |", "| --- | --- | --- | --- |"]
    for record in children:
        implements = ", ".join(
            sorted(
                relation.target
                for relation in snapshot.relations
                if relation.v1_name == "implements" and relation.source == record.id
            )
        )
        path = str(record.attributes.get("path", ""))
        language = str(record.attributes.get("language", ""))
        lines.append(f"| {record.id} | {path} | {language} | {implements} |")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_c4_render.py -v`
Expected: all PASS.

- [ ] **Step 5: Falsify the escaping test**

Temporarily change `_escape` to `return value` (no-op), rerun `test_labels_are_escaped_against_mermaid_syntax`:

Run: `.venv/bin/python -m pytest tests/test_c4_render.py -k escaped -v`
Expected: FAILS (raw `"` now reaches the output). Revert `_escape` to its real body.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/quarto_needs/c4_render.py tests/test_c4_render.py
git commit -m "$(cat <<'EOF'
feat: render Mermaid C4 diagrams and a Code-level table

Context/Container/Component levels emit Mermaid C4Context/
C4Container/C4Component syntax; the focus node itself renders as an
opaque box at Context level and as a grouping boundary (System_
Boundary/Container_Boundary) at Container/Component level, matching
how real C4 diagrams always draw the thing being zoomed into.
Code level has no Mermaid C4 diagram type and source-modules carry
no inter-module arrows to draw, so it renders as a plain Markdown
table instead of forcing diagram syntax onto non-diagram content.
EOF
)"
```

---

### Task 6: `write_c4_projections` — auto-derived from every `system`/`container` object

**Files:**
- Modify: `src/quarto_needs/graph_output.py`
- Modify: `src/quarto_needs/cli.py`
- Test: `tests/test_graph_output.py` (or wherever `write_default_projection` is currently tested — check with `grep -rln write_default_projection tests/*.py` and add alongside it)

**Interfaces:**
- Consumes: `build_c4_view`/`C4ViewError` (Task 4), `c4_mermaid_source`/`c4_code_table_markdown` (Task 5).
- Produces: `def write_c4_projections(root: Path, snapshot: AnalysisSnapshot) -> None` — for every object of type `"system"` in the snapshot, writes `.quarto-needs/graphs/c4-context-<id>.json` and `.quarto-needs/graphs/c4-container-<id>.json`; for every object of type `"container"`, writes `.quarto-needs/graphs/c4-component-<id>.json`. Each file has the shape `{"schemaVersion": "c4-view-v1", "kind": "mermaid", "source": "<mermaid text>"}` (or `"kind": "table"` with Markdown `source`, though Code level is per-component, handled in this same function — see Step 3). No manifest file: the id itself is deterministic (`c4-<level>-<object id>`), constructed identically by whoever reads it (Task 7's Lua code), so nothing needs to look one up indirectly.

- [ ] **Step 1: Confirm where `write_default_projection` is tested today**

```bash
grep -rln "write_default_projection" tests/*.py
```

Open that file and read its existing test(s) for `write_default_projection` to match its exact fixture style (a `tmp_path` project, a real `analyze_project`/`load_config` call, then asserting on files under `.quarto-needs/graphs/`). Write the new tests in the same file, following that same style.

- [ ] **Step 2: Write the failing tests**

Append (adapt the snapshot-building/config-loading calls to match exactly what the existing tests in this file already do — do not guess a different fixture style):

```python
def test_write_c4_projections_writes_one_file_per_system_and_container_level(
    tmp_path: Path,
) -> None:
    (tmp_path / "arch.qmd").write_text(
        '::: {.need #SYS-1 type="system" status="draft"}\n## System\n:::\n\n'
        '::: {.need #CONTAINER-1 type="container" status="draft" '
        'part-of="SYS-1" technology="Python"}\n## Container\n:::\n',
        encoding="utf-8",
    )
    result = analyze_project(tmp_path, config=load_config(tmp_path))
    assert result.snapshot is not None

    write_c4_projections(tmp_path, result.snapshot)

    graph_dir = tmp_path / ".quarto-needs" / "graphs"
    context_path = graph_dir / "c4-context-SYS-1.json"
    container_path = graph_dir / "c4-container-SYS-1.json"
    component_path = graph_dir / "c4-component-CONTAINER-1.json"
    assert context_path.is_file()
    assert container_path.is_file()
    assert component_path.is_file()

    context_payload = json.loads(context_path.read_text(encoding="utf-8"))
    assert context_payload["schemaVersion"] == "c4-view-v1"
    assert context_payload["kind"] == "mermaid"
    assert context_payload["source"].splitlines()[0] == "C4Context"

    container_payload = json.loads(container_path.read_text(encoding="utf-8"))
    assert "System_Boundary(" in container_payload["source"]

    component_payload = json.loads(component_path.read_text(encoding="utf-8"))
    assert component_payload["kind"] == "table"
    assert component_payload["source"].splitlines()[0].startswith("|")


def test_write_c4_projections_is_a_no_op_when_there_are_no_systems_or_containers(
    tmp_path: Path,
) -> None:
    (tmp_path / "arch.qmd").write_text(
        '::: {.need #REQ-1 type="functional-requirement" status="draft"}\n## Req\n:::\n',
        encoding="utf-8",
    )
    result = analyze_project(tmp_path, config=load_config(tmp_path))
    assert result.snapshot is not None

    write_c4_projections(tmp_path, result.snapshot)

    graph_dir = tmp_path / ".quarto-needs" / "graphs"
    assert not graph_dir.exists() or list(graph_dir.glob("c4-*.json")) == []
```

Add the necessary imports at the top of the test file if not already present: `import json`, `from quarto_needs.graph_output import write_c4_projections`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_graph_output.py -k c4_projections -v`
Expected: FAIL with `ImportError: cannot import name 'write_c4_projections'`.

- [ ] **Step 4: Implement**

Add to `src/quarto_needs/graph_output.py` (near `write_default_projection`, which it complements but does not replace):

```python
def write_c4_projections(root: Path, snapshot: AnalysisSnapshot) -> None:
    """Pre-render every system's Context/Container view and every
    container's Component view (plus each component's Code-level table).

    Unlike named-query views, C4 views need no project configuration: the
    full set is derived directly from which objects exist as `system`/
    `container`/`component` types, so there is nothing for a project to
    declare and nothing that can drift out of sync with the graph.
    """
    from .c4_projection import C4ViewError, build_c4_view
    from .c4_render import c4_code_table_markdown, c4_mermaid_source

    graph_dir = root / ".quarto-needs" / "graphs"
    for stale in graph_dir.glob("c4-*.json"):
        stale.unlink()

    def _write(view_id: str, kind: str, source: str) -> None:
        graph_dir.mkdir(parents=True, exist_ok=True)
        _atomic_text(
            graph_dir / f"{view_id}.json",
            json.dumps(
                {"schemaVersion": "c4-view-v1", "kind": kind, "source": source},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

    for record in snapshot.objects:
        if record.type == "system":
            for level in ("context", "container"):
                try:
                    projection = build_c4_view(snapshot, focus_id=record.id, level=level)
                except (C4ViewError, GraphLimitExceeded):
                    continue
                source = c4_mermaid_source(projection, focus_id=record.id, level=level)
                _write(f"c4-{level}-{record.id}", "mermaid", source)
        elif record.type == "container":
            try:
                projection = build_c4_view(snapshot, focus_id=record.id, level="component")
            except (C4ViewError, GraphLimitExceeded):
                continue
            source = c4_mermaid_source(projection, focus_id=record.id, level="component")
            _write(f"c4-component-{record.id}", "mermaid", source)
        elif record.type == "component":
            table = c4_code_table_markdown(snapshot, focus_id=record.id)
            _write(f"c4-code-{record.id}", "table", table)
```

Check the existing imports at the top of `graph_output.py` — `json` and `GraphLimitExceeded` (from `.graph_projection`) are almost certainly already imported for `write_default_projection`'s own use; if either is missing, add it (`from .graph_projection import GraphLimitExceeded`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_graph_output.py -k c4_projections -v`
Expected: all PASS.

- [ ] **Step 6: Wire it into the CLI build step**

In `src/quarto_needs/cli.py`, right after the existing call (currently around line 99-101):

```python
        from .graph_output import write_default_projection

        write_default_projection(root, result.snapshot, config)
```

add:

```python
        from .graph_output import write_default_projection

        write_default_projection(root, result.snapshot, config)

        from .graph_output import write_c4_projections

        write_c4_projections(root, result.snapshot)
```

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/quarto_needs/graph_output.py src/quarto_needs/cli.py tests/test_graph_output.py
git commit -m "$(cat <<'EOF'
feat: pre-render C4 views for every system/container/component

Auto-derived, not configured: unlike named queries (arbitrary
field filters, which genuinely need a project to declare them), a
system always gets exactly a Context and a Container view and a
container always gets exactly a Component view — no new config
surface needed. Wired into the same CLI step that already writes
the general graph projections.
EOF
)"
```

---

### Task 7: `need-c4` Lua shortcode — a thin reader, no C4 logic in Lua

**Files:**
- Create: `_extensions/quarto-needs/c4.lua`
- Modify: `_extensions/quarto-needs/shortcodes.lua`

**Interfaces:**
- Consumes: `.quarto-needs/graphs/c4-<level>-<id>.json` (Task 6's output shape: `{"schemaVersion": "c4-view-v1", "kind": "mermaid"|"table", "source": "..."}`), `views.mermaid_inline_svg(source, description, class_name)` (existing, `views.lua:226`), `views.warning(message)` (existing, used throughout `graph.lua` for shortcode misuse).
- Produces: shortcode `{{< need-c4 root="<id>" level="context|container|component|code" >}}`, registered in `shortcodes.lua`'s dispatch table alongside `["need-graph"]=render_need_graph`.

- [ ] **Step 1: Read the existing shortcode registration and warning pattern**

Open `_extensions/quarto-needs/shortcodes.lua` and find the dispatch table (currently ends with a line like `["need-graph"]=render_need_graph,` around line 71) and the `render_need_graph` function (around line 21-27) to copy its exact argument-handling shape (`function(args, kwargs)`).

Open `_extensions/quarto-needs/graph.lua`'s `load_projection` (lines 222-230, already read during planning) to copy its file-path-construction and error-handling pattern exactly:

```lua
local function load_projection(root, view_id)
  local full = pandoc.path.join({root, ".quarto-needs", "graphs", view_id .. ".json"})
  local file = io.open(full, "rb")
  if not file then return nil, nil, "Graph projection not found: " .. full end
  local contents = file:read("*a"); file:close()
  local ok, decoded = pcall(pandoc.json.decode, contents)
  if not ok or type(decoded) ~= "table" then return nil, nil, "Graph projection is not valid JSON: " .. full end
  return decoded, contents
end
```

- [ ] **Step 2: Create `c4.lua`**

```lua
-- The `need-c4` shortcode: Mermaid C4 diagrams and the Code-level table.
--
-- All C4-specific logic (which node is what shape, how a diagram's text is
-- built) lives in Python (c4_render.py) and is pre-rendered to
-- .quarto-needs/graphs/c4-<level>-<id>.json by write_c4_projections. This
-- module only reads that file and hands its text to the existing Mermaid
-- rendering helper — it never interprets a graph projection itself, unlike
-- graph.lua's own need-graph shortcode.
local M = {}

local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local views = dofile(script_dir() .. "views.lua")

local VALID_LEVELS = {context = true, container = true, component = true, code = true}

local function project_dir()
  local ok, directory = pcall(function() return quarto.project.directory end)
  if ok and type(directory) == "string" and directory ~= "" then return directory end
  local input = PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]
  return input and input:match("(.*/)") or "."
end

local function load_c4_view(root, view_id)
  local full = pandoc.path.join({root, ".quarto-needs", "graphs", view_id .. ".json"})
  local file = io.open(full, "rb")
  if not file then return nil, "C4 view not found: " .. full end
  local contents = file:read("*a"); file:close()
  local ok, decoded = pcall(pandoc.json.decode, contents)
  if not ok or type(decoded) ~= "table" or type(decoded.source) ~= "string" then
    return nil, "C4 view is not valid JSON: " .. full
  end
  return decoded
end

function M.render_shortcode(args, kwargs)
  views.ensure_assets()
  local root_id = views.kwarg(kwargs, "root", "")
  local level = views.kwarg(kwargs, "level", "")
  if root_id == "" or level == "" then
    return views.warning(views.tr(
      "need-c4 requires both root and level.",
      "need-c4 requer tanto root quanto level."
    ))
  end
  if not VALID_LEVELS[level] then
    return views.warning(views.tr(
      "need-c4 level must be one of context, container, component, code.",
      "need-c4 level deve ser context, container, component ou code."
    ))
  end

  local root = project_dir()
  local view_id = "c4-" .. level .. "-" .. root_id
  local decoded, message = load_c4_view(root, view_id)
  if not decoded then
    quarto.log.warning(message)
    return views.warning(message)
  end

  if decoded.kind == "table" then
    return pandoc.read(decoded.source, "markdown").blocks
  end

  local description = views.tr("Architecture diagram", "Diagrama de arquitetura")
  local svg = views.mermaid_inline_svg(decoded.source, description, "need-c4-figure")
  if not svg then
    return views.warning(views.tr(
      "need-c4 could not render the diagram.",
      "need-c4 não conseguiu renderizar o diagrama."
    ))
  end
  return svg
end

return M
```

- [ ] **Step 3: Register the shortcode**

In `_extensions/quarto-needs/shortcodes.lua`, add near the top (alongside the other `dofile(...)` module loads, matching whatever pattern `graph.lua` is loaded with there):

```lua
local c4 = dofile(script_dir() .. "c4.lua")
```

(Match the exact `script_dir()`/`dofile` call already used for `graph`/`views` in this file — copy that line's style precisely, do not guess a different loading convention.)

Add a thin wrapper function near `render_need_graph`:

```lua
local function render_need_c4(args, kwargs)
  return c4.render_shortcode(args, kwargs)
end
```

Add it to the dispatch table (the line ending `["need-graph"]=render_need_graph,`):

```lua
["need-table"]=render_need_table,["need-list"]=render_need_list,["need-count"]=render_need_count,["need-matrix"]=render_need_matrix,["need-backlinks"]=render_need_backlinks,["need-inspector"]=render_need_inspector,["need-flow"]=render_need_flow,["need-dashboard"]=render_need_dashboard,["need-graph"]=render_need_graph,["need-c4"]=render_need_c4,
```

- [ ] **Step 4: No automated test yet — that is Task 8**

This task has no independent pytest to run (it is Lua, and this project's Lua shortcodes are tested via real `quarto render` subprocess calls, per `tests/test_quarto_views.py`). Do not skip verification — Task 8 is the verification for this task and the previous one together; they are reviewed as one unit for that reason.

- [ ] **Step 5: Commit**

```bash
git add _extensions/quarto-needs/c4.lua _extensions/quarto-needs/shortcodes.lua
git commit -m "$(cat <<'EOF'
feat: add the need-c4 shortcode

A thin reader: loads the pre-rendered Mermaid/table text
write_c4_projections already wrote to .quarto-needs/graphs/, and
hands it to the existing mermaid_inline_svg helper. No C4-specific
interpretation happens in Lua — that boundary is deliberate (Python
remains the sole semantic authority; Lua only presents).
EOF
)"
```

---

### Task 8: End-to-end verification — a real `quarto render` of a small fixture

**Files:**
- Test: `tests/test_quarto_views.py` (add to this existing file, following its established `subprocess.run(["quarto", "render", ...])` pattern) — check the file's existing fixture-project helper (likely a function building a small `tmp_path` project with a `_quarto.yml`/`.quarto-needs.toml` and copying the `_extensions/quarto-needs/` directory in) and reuse it exactly.

**Interfaces:**
- Consumes: the real `quarto` binary (already required by every other test in this file — no new dependency), `need-c4` (Task 7).

- [ ] **Step 1: Read the existing fixture-project helper**

Open `tests/test_quarto_views.py` fully and identify the helper that builds a renderable fixture project (creates `_quarto.yml`, copies `_extensions/quarto-needs/`, writes a `.qmd`, runs `quarto render`). Copy its exact shape — do not reinvent a parallel one.

- [ ] **Step 2: Write the failing test**

Using that same helper, add a test with a `.qmd` containing:

```qmd
::: {.need #SYS-1 type="system" status="draft"}
## Fixture system
:::

::: {.need #ACTOR-1 type="actor" status="draft" depends-on="SYS-1"}
## Fixture actor
:::

{{< need-c4 root="SYS-1" level="context" >}}
```

(Adapt the object-authoring syntax to whatever this test file's other fixtures already use for attribute/relation authoring — some tests in this project author relations as `depends-on="SYS-1"` inline attributes, others as a `depends-on:` preamble line; match whichever this file's neighbors already do.)

```python
def test_need_c4_renders_a_context_diagram(tmp_path: Path) -> None:
    project = build_fixture_project(  # use this file's actual helper name
        tmp_path,
        {
            "index.qmd": (
                '::: {.need #SYS-1 type="system" status="draft"}\n'
                "## Fixture system\n:::\n\n"
                '::: {.need #ACTOR-1 type="actor" status="draft" '
                'depends-on="SYS-1"}\n## Fixture actor\n:::\n\n'
                '{{< need-c4 root="SYS-1" level="context" >}}\n'
            )
        },
    )
    subprocess.run(["quarto", "render", str(project)], cwd=ROOT, check=True)
    html = (project / "_book" / "index.html").read_text(encoding="utf-8")
    assert "need-c4-figure" in html
    assert "svg" in html.lower()


def test_need_c4_warns_on_an_unknown_root(tmp_path: Path) -> None:
    project = build_fixture_project(
        tmp_path,
        {
            "index.qmd": (
                '::: {.need #SYS-1 type="system" status="draft"}\n'
                "## Fixture system\n:::\n\n"
                '{{< need-c4 root="MISSING" level="context" >}}\n'
            )
        },
    )
    subprocess.run(["quarto", "render", str(project)], cwd=ROOT, check=True)
    html = (project / "_book" / "index.html").read_text(encoding="utf-8")
    assert "C4 view not found" in html or "not found" in html.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -k need_c4 -v`
Expected: FAIL — likely a `KeyError`/render error since the CLI's build step needs to have actually run before Quarto renders (check how this test file's other tests trigger the CLI build step — e.g. do they call `quarto-needs scan`/whatever `cli.py` command reaches Task 6's `write_c4_projections` before invoking `quarto render`, via `subprocess` or a direct Python call? Copy that exact sequencing).

- [ ] **Step 4: Fix whatever the failure actually says**

This step has no pre-written fix, deliberately — the exact failure depends on details only visible once Step 3 runs (fixture project layout, whether the CLI build step needs an explicit invocation before `quarto render`, whether `_extension.yml`'s version needs bumping for the new shortcode to be recognized by whatever compatibility check `data.lua` runs). Diagnose from the actual pytest output and Quarto's own render log (`quarto render` prints Lua errors to stderr; `subprocess.run(..., capture_output=True, text=True)` if the existing helper doesn't already capture it) before changing anything.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -k need_c4 -v`
Expected: both PASS.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass. (This suite includes real `quarto render` calls and will take longer than earlier tasks — that is expected, not a hang; if it genuinely exceeds a few minutes beyond the suite's already-observed ~200s baseline, investigate rather than assuming it is fine.)

- [ ] **Step 7: Commit**

```bash
git add tests/test_quarto_views.py
git commit -m "$(cat <<'EOF'
test: verify need-c4 through a real Quarto render

End-to-end, not mocked: the same subprocess quarto render pattern
this project already uses for every other Lua shortcode. Confirms
the full path — CLI build step writes the C4 view JSON, need-c4
reads it, mermaid_inline_svg renders it into the HTML output — and
that an unknown root warns instead of failing the whole render.
EOF
)"
```

---

### Task 9: Self-hosted config — new types and the `part-of` policy

**Files:**
- Modify: `examples/quarto-needs/.quarto-needs.toml`

**Interfaces:**
- Produces: `[types.actor]`, `[types.external-system]`, `[types.system]`, `[types.container]` sections; `[relations."part-of"]` with `minimum-per-source = 1, maximum-per-source = 1`. (Per Task 2's ruling: `minimum-per-source` only catches an object that already has *some* part-of edges but too few, never an object with zero — configuring it is still correct and harmless, it just isn't complete "exactly one parent" enforcement on its own. Tasks 10-11's own Step 5 `analyze_project` check is what actually catches a hand-authored orphan in this retrofit.)

- [ ] **Step 1: Write the failing test (a real render/check of the example project)**

This task's "test" is the project's own existing self-hosted validation, which already runs as part of `tests/test_self_hosted_example.py` and/or a `quarto-needs check` invocation over `examples/quarto-needs/`. Confirm which test currently exercises `examples/quarto-needs/.quarto-needs.toml` end to end:

```bash
grep -rln "examples/quarto-needs" tests/test_self_hosted_example.py tests/test_example_project.py 2>/dev/null
```

Run whichever of those currently passes, to establish the baseline before editing:

Run: `.venv/bin/python -m pytest tests/test_self_hosted_example.py -q`
Expected: PASS (this is the pre-edit baseline, not a new failing test — Tasks 9-13 are a content retrofit verified by the project's own existing gate tests plus one new object-count assertion added in Task 10).

- [ ] **Step 2: Add the new type declarations**

In `examples/quarto-needs/.quarto-needs.toml`, add after the existing `[types.component]`/`[types.interface]` blocks (matching their exact shape):

```toml
[types.actor]
role = "architecture-element"
allowed-statuses = ["draft", "approved", "deprecated"]

[types.external-system]
role = "architecture-element"
allowed-statuses = ["draft", "approved", "deprecated"]

[types.system]
role = "architecture-element"
allowed-statuses = ["draft", "approved", "deprecated"]

[types.container]
role = "architecture-element"
allowed-statuses = ["draft", "approved", "deprecated"]
required-attributes = ["technology"]
```

(No `id-prefix` is set for these four — unlike `COMP-`/`SRC-`, the retrofit's object IDs are short/descriptive rather than following a strict prefix convention; check whether `id-prefix` is actually *required* by `load_config`'s `_parse_types` — if omitting it errors, add one each: `"ACTOR-"`, `"EXT-"`, `"SYS-"` — wait, `SYS-` is already used by `system-requirement`'s own `id-prefix`; if `id-prefix` turns out to be mandatory, use a distinct one for the new `system` type, e.g. `"ARCSYS-"`, and adjust Task 10's object IDs to match whatever prefix is actually chosen here.)

- [ ] **Step 3: Add the `part-of` relation policy**

Add a new `[relations."part-of"]` block near the other `[relations.*]` entries:

```toml
[relations."part-of"]
allowed-source-types = ["container", "component", "source-module"]
allowed-target-types = ["system", "container", "component"]
minimum-per-source = 1
maximum-per-source = 1
```

- [ ] **Step 4: Run the baseline test again**

Run: `.venv/bin/python -m pytest tests/test_self_hosted_example.py -q`
Expected: still PASSES — these are pure additions (new type sections, one new relation policy on a relation name nothing authors yet); nothing existing should be affected. If anything now fails, read the failure — a config-parsing error (e.g. `id-prefix` turning out mandatory, per Step 2's caveat) is the most likely cause, not a sign the whole approach is wrong.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add examples/quarto-needs/.quarto-needs.toml
git commit -m "$(cat <<'EOF'
feat: register actor/external-system/system/container types

Configures this project's own required-attributes/allowed-statuses
for the four new C4 types, and part-of's minimum/maximum-per-source
cardinality (exactly one parent) via the existing generic relation
policy mechanism ARC001/REQ010 already enforce — no new validation
code, just this project opting into it, per Task 2.
EOF
)"
```

---

### Task 10: Retrofit `architecture.qmd` — system, actor, external-systems, containers

**Files:**
- Modify: `examples/quarto-needs/architecture.qmd`
- Modify: `tests/test_self_hosted_example.py` (extend the object-count/type-coverage assertion this file almost certainly already has, to include the new objects — read the file first to find that assertion before adding to it)

**Interfaces:**
- Produces: new objects `SYS-QUARTO-NEEDS` (system), `ACTOR-ENGINEER` (actor), `EXT-GITHUB`/`EXT-OSLC` (external-system), `CONTAINER-PYTHON-PKG`/`CONTAINER-QUARTO-EXT` (container). The 8 existing `COMP-*` objects each gain a `part-of` attribute pointing at one of the two new containers.

- [ ] **Step 1: Read the current object-count/coverage test**

```bash
grep -n "len(.*declarations\|len(.*objects\|assert.*count" tests/test_self_hosted_example.py | head -20
```

Find whatever test currently asserts a fixed total object count or a fixed type-coverage set for the self-hosted example (this project's own established pattern makes such a count highly likely to exist, since every prior slice this session added to this file updated an analogous assertion). Note its exact current value(s) before editing — you will update them in Step 4, not before.

- [ ] **Step 2: Add the new architecture objects**

In `examples/quarto-needs/architecture.qmd`, add a new section after the file's opening paragraph and before `## Components` (currently line 5):

```qmd
## System and its context

::: {.need #SYS-QUARTO-NEEDS type="system" status="approved" tags="architecture;c4"}
## Quarto-Needs

The engineering-traceability tool this case study documents: a requirements/decisions/risk/test/evidence graph authored in Quarto Markdown, analyzed by a Python core, and presented through a Quarto extension.
:::

::: {.need #ACTOR-ENGINEER type="actor" status="approved" tags="architecture;c4" depends-on="SYS-QUARTO-NEEDS"}
## Requirements engineer

Authors, reviews, and approves engineering objects; reads generated views to understand traceability and coverage.
:::

::: {.need #EXT-GITHUB type="external-system" status="approved" tags="architecture;c4;github" depends-on="SYS-QUARTO-NEEDS"}
## GitHub

Hosts the project's issues, which Quarto-Needs federates as read-only, provenance-bound external observations (see `interoperability.qmd`).
:::

::: {.need #EXT-OSLC type="external-system" status="approved" tags="architecture;c4;oslc" depends-on="SYS-QUARTO-NEEDS"}
## OSLC-compliant requirements management tool

An external OSLC Requirements Management provider Quarto-Needs federates from as a read-only, provenance-bound source (see `interoperability.qmd`).
:::
```

Then, immediately before `## Components` (currently line 5), add the two containers:

```qmd
## Containers

::: {.need #CONTAINER-PYTHON-PKG type="container" status="approved" tags="architecture;c4" technology="Python 3.12" part-of="SYS-QUARTO-NEEDS"}
## Python package

The installable `quarto-needs` library and CLI: parsing, analysis, governance rules, graph projection, baselines, and localization checks.
:::

::: {.need #CONTAINER-QUARTO-EXT type="container" status="approved" tags="architecture;c4" technology="Quarto/Pandoc Lua filters" part-of="SYS-QUARTO-NEEDS"}
## Quarto presentation extension

The `_extensions/quarto-needs/` bundle: build-time Lua filters and the browser-side JavaScript they ship, together as one installed Quarto extension.
:::

```

- [ ] **Step 3: Add `part-of` to each existing `COMP-*` object**

In the same file, add a `part-of` attribute to each of the 8 existing component declarations (their opening `::: {.need #COMP-* ...}` line — append `part-of="CONTAINER-PYTHON-PKG"` or `part-of="CONTAINER-QUARTO-EXT"` to the existing attribute list, do not remove any existing attribute):

- `COMP-PARSER` → `part-of="CONTAINER-PYTHON-PKG"`
- `COMP-ANALYSIS` → `part-of="CONTAINER-PYTHON-PKG"`
- `COMP-RULES` → `part-of="CONTAINER-PYTHON-PKG"`
- `COMP-CLI` → `part-of="CONTAINER-PYTHON-PKG"`
- `COMP-EXTENSION` → `part-of="CONTAINER-QUARTO-EXT"`
- `COMP-GRAPH` → `part-of="CONTAINER-PYTHON-PKG"`
- `COMP-BASELINE` → `part-of="CONTAINER-PYTHON-PKG"`
- `COMP-I18N` → `part-of="CONTAINER-PYTHON-PKG"`

For example, `COMP-PARSER`'s line changes from:

```qmd
::: {.need #COMP-PARSER type="component" status="implemented" tags="python;parser;authoring"}
```

to:

```qmd
::: {.need #COMP-PARSER type="component" status="implemented" tags="python;parser;authoring" part-of="CONTAINER-PYTHON-PKG"}
```

Apply the same edit shape to the other 7.

- [ ] **Step 4: Update the object-count/coverage test**

Using whatever assertion Step 1 found, add the 6 new objects (`SYS-QUARTO-NEEDS`, `ACTOR-ENGINEER`, `EXT-GITHUB`, `EXT-OSLC`, `CONTAINER-PYTHON-PKG`, `CONTAINER-QUARTO-EXT`) to its expected set/count, matching that test's existing style exactly (do not restructure the test, only extend its expected data).

- [ ] **Step 5: Verify locally**

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from pathlib import Path
root = Path('examples/quarto-needs')
result = analyze_project(root, config=load_config(root))
errors = [f for f in result.findings if f.severity == 'error']
print('errors:', [(f.code, f.object_id, f.message) for f in errors])
assert result.snapshot is not None
print('SYS-QUARTO-NEEDS' in result.snapshot.objects_by_id)
"
```

Expected: `errors: []` and `True`. If ARC001 or REQ010 findings appear, the `part-of` wiring has a layer or cardinality mistake — fix the specific object the finding names, do not suppress the rule.

- [ ] **Step 6: Run the self-hosted test and full suite**

Run: `.venv/bin/python -m pytest tests/test_self_hosted_example.py -q`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add examples/quarto-needs/architecture.qmd tests/test_self_hosted_example.py
git commit -m "$(cat <<'EOF'
feat: retrofit architecture.qmd into the C4 hierarchy

Adds SYS-QUARTO-NEEDS as the top-level system, an actor and two
external-systems (GitHub, an OSLC provider) already implied by the
Phase 5/5.5 federation work but never modeled as boxes, and two
containers splitting the 8 existing components by actual deployable
unit: the Python package and the Quarto extension bundle (Lua
filters plus the browser JS they ship together). Every existing
component gains a part-of relation to its container.
EOF
)"
```

---

### Task 11: Retrofit `implementation.qmd` — `part-of` on every source-module

**Files:**
- Modify: `examples/quarto-needs/implementation.qmd`

**Interfaces:**
- Produces: each of the 14 existing `SRC-*` objects gains a `part-of` attribute pointing at its owning `COMP-*`, using the file's own `##`-heading section groupings as the mapping (this link does not exist as a graph edge today — verified during the design's brainstorming phase via `grep -n "part-of\|decomposes" examples/quarto-needs/implementation.qmd`, which returned nothing).

- [ ] **Step 1: Add `part-of` to each `SRC-*` object**

Using the file's own section headings as the mapping (confirmed against each component's own description during planning):

| Source-module | Section heading | `part-of` target |
|---|---|---|
| `SRC-PARSER` | Python semantic core | `COMP-PARSER` |
| `SRC-RELATIONS` | Python semantic core | `COMP-ANALYSIS` |
| `SRC-ANALYSIS` | Python semantic core | `COMP-ANALYSIS` |
| `SRC-RULES` | Python semantic core | `COMP-RULES` |
| `SRC-QUALITY` | Python semantic core | `COMP-RULES` |
| `SRC-QUERIES` | Python semantic core | `COMP-ANALYSIS` |
| `SRC-GRAPH-OUTPUT` | Graph projection and exploration | `COMP-GRAPH` |
| `SRC-GRAPH-PROJECTION` | Graph projection and exploration | `COMP-GRAPH` |
| `SRC-GRAPH-CONTEXT` | Graph projection and exploration | `COMP-GRAPH` |
| `SRC-GRAPH-EXPLORE` | Graph projection and exploration | `COMP-GRAPH` |
| `SRC-MARGIN-SIDEBAR` | Presentation ergonomics | `COMP-EXTENSION` |
| `SRC-BASELINE` | Change analysis | `COMP-BASELINE` |
| `SRC-DIFF` | Change analysis | `COMP-BASELINE` |
| `SRC-IMPACT` | Change analysis | `COMP-BASELINE` |
| `SRC-PRE-RENDER` | Localization and staged rendering | `COMP-I18N` |

For example, `SRC-PARSER`'s opening line changes from:

```qmd
::: {.need #SRC-PARSER type="source-module" status="implemented" path="src/quarto_needs/parser.py" language="Python" layer="semantic-core" tags="parser;authoring;qmd" implements="FUN-001"}
```

to:

```qmd
::: {.need #SRC-PARSER type="source-module" status="implemented" path="src/quarto_needs/parser.py" language="Python" layer="semantic-core" tags="parser;authoring;qmd" implements="FUN-001" part-of="COMP-PARSER"}
```

Apply the same `part-of="<target>"` append to all 14, per the table above. `COMP-CLI` legitimately gets zero `part-of` children (there is no `SRC-CLI` object in this file today — a pre-existing gap, not something this retrofit is scoped to fix).

- [ ] **Step 2: Verify locally**

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from pathlib import Path
root = Path('examples/quarto-needs')
result = analyze_project(root, config=load_config(root))
errors = [f for f in result.findings if f.severity == 'error']
print('errors:', [(f.code, f.object_id, f.message) for f in errors])
"
```

Expected: `errors: []`.

- [ ] **Step 3: Run the self-hosted test and full suite**

Run: `.venv/bin/python -m pytest tests/test_self_hosted_example.py -q`
Expected: PASS.

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add examples/quarto-needs/implementation.qmd
git commit -m "$(cat <<'EOF'
feat: link every source-module to its owning component

part-of closes a link that did not exist as a graph edge before —
which component a given file belongs to was only ever implied by
this document's own section headings and naming convention.
EOF
)"
```

---

### Task 12: Mirror both retrofits into pt-BR

**Files:**
- Modify: `examples/quarto-needs/architecture.pt-BR.qmd`
- Modify: `examples/quarto-needs/implementation.pt-BR.qmd`

**Interfaces:**
- Produces: the same object IDs, types, `part-of`/`depends-on` relations, and `technology`/attribute values as Tasks 10-11 (relations and attributes are canonical, never translated — only `title`/`body` prose differs), with translated Portuguese titles/bodies for the 6 new objects.

- [ ] **Step 1: Add the mirrored objects to `architecture.pt-BR.qmd`**

Insert the same structural section (translated) at the same position (after the opening paragraph, before `## Componentes` — check the pt-BR file's exact current heading text for "Components", already read during planning as `## Componentes` at line 5):

```qmd
## Sistema e seu contexto

::: {.need #SYS-QUARTO-NEEDS type="system" status="approved" tags="architecture;c4"}
## Quarto-Needs

A ferramenta de rastreabilidade de engenharia documentada por este estudo de caso: um grafo de requisitos/decisões/riscos/testes/evidências autorado em Quarto Markdown, analisado por um núcleo em Python, e apresentado por meio de uma extensão do Quarto.
:::

::: {.need #ACTOR-ENGINEER type="actor" status="approved" tags="architecture;c4" depends-on="SYS-QUARTO-NEEDS"}
## Engenheiro de requisitos

Autora, revisa e aprova objetos de engenharia; lê as visões geradas para entender rastreabilidade e cobertura.
:::

::: {.need #EXT-GITHUB type="external-system" status="approved" tags="architecture;c4;github" depends-on="SYS-QUARTO-NEEDS"}
## GitHub

Hospeda as issues do projeto, que o Quarto-Needs federa como observações externas somente leitura e com proveniência (ver `interoperability.qmd`).
:::

::: {.need #EXT-OSLC type="external-system" status="approved" tags="architecture;c4;oslc" depends-on="SYS-QUARTO-NEEDS"}
## Ferramenta de gestão de requisitos compatível com OSLC

Um provedor externo de OSLC Requirements Management do qual o Quarto-Needs federa como fonte somente leitura e com proveniência (ver `interoperability.qmd`).
:::
```

And before `## Componentes`:

```qmd
## Containers

::: {.need #CONTAINER-PYTHON-PKG type="container" status="approved" tags="architecture;c4" technology="Python 3.12" part-of="SYS-QUARTO-NEEDS"}
## Pacote Python

A biblioteca e CLI instaláveis `quarto-needs`: parsing, análise, regras de governança, projeção de grafo, baselines e verificações de localização.
:::

::: {.need #CONTAINER-QUARTO-EXT type="container" status="approved" tags="architecture;c4" technology="Filtros Lua do Quarto/Pandoc" part-of="SYS-QUARTO-NEEDS"}
## Extensão de apresentação do Quarto

O pacote `_extensions/quarto-needs/`: filtros Lua executados em tempo de build e o JavaScript de navegador que eles distribuem, juntos como uma única extensão Quarto instalada.
:::

```

Then add `part-of="CONTAINER-PYTHON-PKG"` or `part-of="CONTAINER-QUARTO-EXT"` to each of the 8 existing `COMP-*` opening lines in this file, using the exact same mapping as Task 10, Step 3.

- [ ] **Step 2: Add `part-of` to `implementation.pt-BR.qmd`**

Add `part-of="<target>"` to each of the 14 `SRC-*` objects in this file, using the exact same mapping table as Task 11, Step 1 (relations are canonical — identical in both languages).

- [ ] **Step 3: Verify EN/pt-BR semantic parity**

Find and run whichever test checks EN/pt-BR parity for this example (very likely in `tests/test_self_hosted_example.py` — search `grep -n "pt.BR\|pt_br\|parity" tests/test_self_hosted_example.py`).

Run: `.venv/bin/python -m pytest tests/test_self_hosted_example.py -q`
Expected: PASS. If it fails, the parity checker (per this project's own established convention, confirmed during Phase 5.5's own review this session) compares `(id, type, status, attributes, relations)` — a mismatch here almost always means a `part-of`/`depends-on`/`technology` value was typed differently between the two files (e.g. a typo, or a relation added to one file but not its sibling) — fix the actual mismatch, do not weaken the check.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add examples/quarto-needs/architecture.pt-BR.qmd examples/quarto-needs/implementation.pt-BR.qmd
git commit -m "$(cat <<'EOF'
docs: mirror the C4 retrofit into pt-BR

Same IDs, types, and relations as the canonical English source
(this project's own established rule: only title/body prose
translates); adds the six new object translations.
EOF
)"
```

---

### Task 13: Embed `need-c4` in the self-hosted example and verify the real render

**Files:**
- Modify: `examples/quarto-needs/architecture.qmd`
- Modify: `examples/quarto-needs/architecture.pt-BR.qmd`

**Interfaces:**
- Produces: three `{{< need-c4 ... >}}` shortcode invocations rendering real diagrams over the retrofitted content.

- [ ] **Step 1: Embed the shortcodes**

At the end of `examples/quarto-needs/architecture.qmd`, after the existing `## Generated architecture views` section (currently lines 277-281), add:

```qmd
## Generated C4 views

{{< need-c4 root="SYS-QUARTO-NEEDS" level="context" >}}

{{< need-c4 root="SYS-QUARTO-NEEDS" level="container" >}}

{{< need-c4 root="CONTAINER-PYTHON-PKG" level="component" >}}
```

Mirror the same section (translated heading) at the end of `architecture.pt-BR.qmd`:

```qmd
## Visões C4 geradas

{{< need-c4 root="SYS-QUARTO-NEEDS" level="context" >}}

{{< need-c4 root="SYS-QUARTO-NEEDS" level="container" >}}

{{< need-c4 root="CONTAINER-PYTHON-PKG" level="component" >}}
```

- [ ] **Step 2: Run the project's own canonical pre-render + real Quarto render**

Check how this project already renders its own book locally for verification (very likely `tools/quarto_needs_pre_render.py` followed by `quarto render`, given `SRC-PRE-RENDER`'s own description: "Synchronizes extension assets, builds the engineering graph, checks localized semantic parity, and emits presentation-only title projections"):

```bash
.venv/bin/python tools/quarto_needs_pre_render.py examples/quarto-needs
cd examples/quarto-needs && quarto render . && cd -
```

(If this exact invocation is wrong, check `tests/test_example_project.py` or the project's `Makefile`/CI config for the actual canonical local-render command this project uses, and use that instead — do not guess further than one attempt before checking.)

- [ ] **Step 3: Confirm the diagrams actually rendered**

```bash
grep -l "need-c4-figure" examples/quarto-needs/_book/architecture.html
```

Expected: the file is found (i.e. the class name from `c4.lua`'s `mermaid_inline_svg` call is present in the rendered HTML output). Open the file in a browser or inspect the surrounding markup to confirm three distinct SVGs appear (not three copies of the same one, not a warning message) — a genuine visual check, not just a substring match, since this is exactly the kind of thing "looks right" only when actually looked at (per this project's own UI-verification discipline).

- [ ] **Step 4: Run the full suite one final time**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add examples/quarto-needs/architecture.qmd examples/quarto-needs/architecture.pt-BR.qmd
git commit -m "$(cat <<'EOF'
feat: embed generated C4 views in the self-hosted example

The first real end-to-end proof: Context and Container views of
SYS-QUARTO-NEEDS, and a Component view of the Python package
container, rendered from the retrofitted architecture graph.
EOF
)"
```

---

### Task 14: Documentation — phase doc and roadmap status

**Files:**
- Create: `docs/phase-6-architecture-c4.md` (mirroring the structure of `docs/phase-5-external-adapters.md`: status line, why-this-design section, what's implemented, what was learned, regression coverage)
- Modify: `docs/ROADMAP.md` (Phase 6 section, currently `⚪` at line 217)

**Interfaces:**
- Produces: ground-truth documentation of what Phase 6 actually delivered, including all three deliberate/discovered limitations (no relation-attribute authoring syntax yet; interaction edges reach the focus node only, not its children; per Task 2's pre-flight ruling, `part-of`'s `minimum-per-source` policy cannot detect an object with *zero* part-of edges, only "some but too few" — "exactly one parent" is therefore enforced against duplicates, not against total absence, by the generic mechanism alone) — these must appear in the doc as explicit, named limitations, not be silently omitted.

- [ ] **Step 1: Write `docs/phase-6-architecture-c4.md`**

Follow `docs/phase-5-external-adapters.md`'s established shape exactly (a status line stating what's delivered; a "why this design" section referencing the reuse of `select_graph`/`build_projection`/`part-of`/`depends-on` rather than new mechanism; a "what is implemented" section listing the new types/relations/rule/modules/shortcode; a "what was learned" section naming all three limitations above, framed as scope decisions/discovered gaps, not omissions; a "what is intentionally not implemented yet" section covering dynamic/deployment C4 views per the roadmap's own explicit sequencing, and the relation-attribute authoring syntax as a named follow-on; a "regression coverage" section listing each new/extended test file with a one-paragraph summary of what it proves, matching the citation style already used in `phase-5-external-adapters.md`'s own regression-coverage section).

- [ ] **Step 2: Update `docs/ROADMAP.md`**

Change the Phase 6 heading (currently line 217) from:

```markdown
# Phase 6 — Architecture model and C4 projections ⚪
```

to:

```markdown
# Phase 6 — Architecture model and C4 projections ✅ (first slice: actor/external-system/system/container types, Context/Container/Component views, self-hosted retrofit)
```

Add a short paragraph after the existing description (currently lines 219-223) pointing at the new doc, matching how Phase 5.5's roadmap entry references `docs/phase-5-external-adapters.md`:

```markdown
See `docs/phase-6-architecture-c4.md` for what is implemented, the two
deliberate first-slice simplifications, and what remains (dynamic/
deployment projections, relation-attribute authoring syntax).
```

- [ ] **Step 3: Run the full suite one final time**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add docs/phase-6-architecture-c4.md docs/ROADMAP.md
git commit -m "$(cat <<'EOF'
docs: record Phase 6's architecture/C4 first slice

Names both deliberate scope simplifications explicitly (no
relation-attribute authoring syntax yet; interaction edges reach
the focus node only, not its children) so they read as scope
decisions in the ground-truth record, not silently-dropped spec
claims.
EOF
)"
```

---

## Self-Review

**Spec coverage:**
- Type vocabulary (actor/external-system/system/container, technology required attribute) — Tasks 9-10. ✓
- `part-of` as `decomposes`'s inverse — Task 1. ✓
- `depends-on` reused for interactions — Tasks 4-5 (fixed catalog label only; the spec's technology/description-via-attributes claim is corrected in Global Constraints, since the parser has no grammar for it — flagged explicitly, not silently dropped). ✓
- "Exactly one parent" via existing `relation_policies` — Task 2 (test) + Task 9 (config). ✓
- ARC001 layer-adjacency — Task 2. ✓
- View computation (one generic focus+depth-1 operation) — Task 4. ✓
- Code view as a plain table, not Mermaid — Task 5. ✓
- Rendering integration — Tasks 5-7, corrected from the spec's "Lua does the type→macro mapping" to "Python pre-renders text, Lua only reads it" (a real simplification discovered during planning, documented in the plan's Architecture section). ✓
- First-slice retrofit — Tasks 9-13. ✓
- Testing strategy (falsification, relation_policies reuse, Lua e2e, self-hosted parity) — present in Tasks 2, 5, 8, 12. ✓
- Open question "exact .qmd file layout" — resolved: extend `architecture.qmd`/`implementation.qmd` in place (Tasks 10-11), not a new file. ✓
- Open question "Lua test pattern" — resolved: `tests/test_quarto_views.py`'s real-`quarto-render` subprocess pattern (Task 8). ✓
- Open question "ARC001 severity" — resolved: always-error, matching `DEC005` (Task 2). ✓

**Placeholder scan:** No "TBD"/"TODO" strings. Two steps (Task 8 Step 4, Task 13 Step 2) deliberately describe "diagnose from the actual output" rather than a fixed fix — this is correct, not a placeholder, because the exact failure depends on runtime specifics (fixture helper names, exact render command) this plan could not observe without executing it; both give a concrete, falsifiable expectation and the exact commands to run.

**Type consistency:** `build_c4_view(snapshot, *, focus_id: str, level: str, limits=None) -> GraphProjection` (Task 4) is called identically in Task 6 (`build_c4_view(snapshot, focus_id=record.id, level=level)`) and referenced identically in Task 5's test file. `c4_mermaid_source(projection, *, focus_id, level)` and `c4_code_table_markdown(snapshot, *, focus_id)` (Task 5) are called with matching signatures in Task 6. The `.quarto-needs/graphs/c4-<level>-<id>.json` naming convention is produced identically in Task 6 and consumed identically in Task 7's Lua code (`"c4-" .. level .. "-" .. root_id`). `PublicNode.technology` (Task 3) is read by `c4_render.py`'s `_macro_call` (Task 5) using the same field name.

Plan complete and saved to `docs/superpowers/plans/2026-09-01-phase-6-architecture-c4.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
