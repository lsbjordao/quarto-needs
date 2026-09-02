# Quarto-Needs — Core Stabilization Implementation Plan

**Date:** 2026-09-02
**Design:** `docs/superpowers/specs/2026-09-02-core-stabilization-design.md`
**Repository:** `lsbjordao/quarto-needs`
**Base branch:** `main`

---

# Execution rules

This is a stabilization phase.

The implementer MUST prioritize preservation and simplification over capability growth.

Before each task:

1. inspect the current implementation rather than relying on this plan's line numbers;
2. identify the existing tests that pin the behavior being changed;
3. add characterization tests where behavior is not already pinned;
4. observe the relevant test fail for the intended reason when introducing a new contract;
5. make the minimum architectural change;
6. run the focused tests;
7. run the broader regression group;
8. commit the completed task independently when practical.

Do not automatically rewrite golden files to make tests pass.

A changed golden is evidence requiring explanation.

No task may silently expand into:

* new graph UI capability;
* new C4 renderer;
* new C4 level;
* new interchange format;
* new federation source;
* new migration adapter;
* new authoring syntax.

Record discoveries outside scope as follow-up items.

---

# Task 0 — Establish the stabilization baseline

## Purpose

Create a trusted before-state before modifying the semantic pipeline.

## Inspect

At minimum:

```text
src/quarto_needs/model.py
src/quarto_needs/snapshot.py
src/quarto_needs/parser.py
src/quarto_needs/analysis.py
src/quarto_needs/validation.py
src/quarto_needs/relations.py
src/quarto_needs/rules.py
src/quarto_needs/fingerprints.py
src/quarto_needs/graph_projection.py
tests/
examples/quarto-needs/
examples/book/
docs/architecture/
```

## Work

Document:

* current canonical pipeline;
* exact call sites of `EngineeringObject`;
* exact call sites of `validate()`;
* which uses are semantic-core dependencies versus test/convenience APIs;
* which diagnostics originate before snapshot construction;
* which diagnostics originate after snapshot construction.

Capture the current full test result.

Do not modify production semantics in this task.

## Deliverable

Create:

```text
docs/core-stabilization-baseline.md
```

containing the dependency inventory and baseline observations.

## Acceptance

* no production behavior change;
* full existing suite remains green;
* every semantic-core use of `EngineeringObject` is identified.

---

# Task 1 — Characterize validation behavior

## Purpose

Pin existing semantics before removing the legacy bridge.

## Target areas

```text
tests/test_validation.py
tests/test_analysis.py
tests/test_parser.py
tests/test_relations.py
tests/test_rules.py
```

plus any existing integration tests that already cover these contracts.

## Add characterization coverage for

1. duplicate ID;
2. relation target does not exist;
3. unsupported relation;
4. missing rationale;
5. approved requirement without verification;
6. diagnostic ordering;
7. source location propagation;
8. structural errors preventing snapshot creation;
9. warnings not preventing snapshot creation;
10. equivalent findings independent of declaration order.

Where behavior is intentionally odd but currently relied upon, pin it and add a comment explaining that the test exists to protect migration equivalence.

## Important

Do not redesign diagnostics yet.

## Acceptance

The tests define an observable contract sufficient to refactor validation without guessing.

---

# Task 2 — Introduce declaration-native structural validation

## Purpose

Move pre-snapshot validation away from `EngineeringObject`.

## Design

Introduce a declaration-native validation surface.

Exact names may follow repository conventions, but conceptually:

```python
validate_declarations(
    batch: DeclarationBatch,
    config: NeedsConfig,
    relation_catalog: RelationCatalog,
) -> tuple[Finding, ...]
```

Responsibilities should include only checks that do not require a resolved valid graph.

Candidate responsibilities:

* duplicate IDs;
* unknown target IDs;
* unsupported relation names;
* declaration-level structural compatibility.

Do not move graph/governance rules into this function.

## Constraints

* diagnostics remain deterministic;
* structural error codes preserve snapshot-blocking behavior;
* unsupported relation resolution must happen in one clearly defined place;
* no conversion to `EngineeringObject`.

## Refactor

Change canonical `analysis.py` to consume the new declaration-native validator.

At the end of this task it is acceptable for some post-structural compatibility checks still to use the old path if necessary, but the direction of migration must be explicit.

## Falsification

Temporarily break one validation branch and prove the characterization test catches it.

## Acceptance

Duplicate IDs, missing targets, and unsupported relation behavior operate without constructing legacy DTOs.

---

# Task 3 — Make semantic validation snapshot-native

## Purpose

Remove the remaining canonical dependency on `validation.validate(list[EngineeringObject])`.

## Classify existing checks

Move rules according to meaning.

For example:

```text
duplicate ID                  -> declaration structural validation
unknown target                -> declaration structural validation

missing rationale             -> resolved semantic/governance validation
approved without verification -> resolved semantic/governance validation
```

Do not mechanically reproduce the old function structure.

Use the canonical model.

Possible shape:

```python
validate_snapshot(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
) -> tuple[Finding, ...]
```

or integrate appropriate rules with the project's existing rule infrastructure if that creates less duplication.

## Key rule

The semantic validator MUST use:

```text
ObjectRecord
RelationRecord
AnalysisSnapshot
```

rather than recreate `EngineeringObject`.

## Remove canonical bridge

After this task, canonical `analyze_project()` / `_analyze_batch()` must not call `_legacy_objects()` as part of semantic analysis.

If `_legacy_objects()` becomes unused by the canonical path, remove it or move it behind an explicit compatibility helper.

## Compatibility

`analyze_objects(Iterable[EngineeringObject])` may remain as a convenience API, but it must adapt:

```text
EngineeringObject
      ->
ObjectDeclaration
      ->
canonical analyzer
```

It must not create an alternate analysis implementation.

## Acceptance

Search-based architectural test:

The canonical analysis implementation contains no dependency requiring resolved declarations to be converted back into `EngineeringObject`.

All characterization tests pass unchanged unless an explicitly approved diagnostic cleanup has been documented.

---

# Task 4 — Formalize the semantic-kernel contract

## Purpose

Make the architectural boundary executable rather than prose-only.

## Work

Add focused architecture/contract tests that pin important dependency rules.

Examples of invariants worth testing:

1. canonical analysis is declaration/snapshot-native;
2. graph projections consume `AnalysisSnapshot`;
3. C4 projections consume graph/snapshot projections rather than parser internals;
4. browser assets do not define canonical relation classification;
5. public projections are allowlist based;
6. `EngineeringObject` is not imported by the canonical analysis path except an explicitly named compatibility entry point if retained.

Avoid brittle tests that merely grep arbitrary strings when a module-import or AST-based assertion would express the real architecture better.

## Documentation

Update:

```text
docs/architecture/domain-model.md
docs/architecture/solution-strategy.md
docs/architecture/building-blocks.md
```

only enough to represent the now-real stabilized boundary.

## Acceptance

The architecture tests would fail if a future change reintroduced the legacy semantic bridge.

---

# Task 5 — Rebuild canonical graph indexes in linear time

## Purpose

Remove the O(VE) outgoing/incoming construction pattern.

## Current behavior to replace

Avoid:

```python
for obj in objects:
    outgoing[obj.id] = tuple(
        relation for relation in relations
        if relation.source == obj.id
    )
```

and the equivalent incoming scan.

## Desired construction

Conceptually:

```python
outgoing_lists = {object_id: [] for object_id in objects_by_id}
incoming_lists = {object_id: [] for object_id in objects_by_id}

for relation in relations:
    outgoing_lists[relation.source].append(relation)
    incoming_lists[relation.target].append(relation)
```

Then freeze once.

Preserve deterministic relation ordering.

## Tests

Prove:

* objects with zero outgoing relations get an empty tuple;
* objects with zero incoming relations get an empty tuple;
* ordering is deterministic;
* indexes contain exactly the canonical relation objects;
* input permutation does not alter snapshot output.

Where practical, add a construction test that prevents accidental reintroduction of one-full-edge-scan-per-object without depending on wall-clock timing.

## Acceptance

Index construction is O(V + E).

No public artifact changes.

---

# Task 6 — Establish reproducible performance benchmarks

## Purpose

Measure before undertaking broader optimization.

## Create

Suggested location:

```text
benchmarks/
    README.md
    generate_model.py
    benchmark_analysis.py
```

or use an equivalent structure consistent with the repository.

Do not add a heavy benchmark framework unless justified.

The built-in Python timing facilities are sufficient if they produce reproducible results.

## Dataset sizes

At least:

```text
100 objects
1,000 objects
10,000 objects
50,000 objects
```

Generate deterministic graphs using a fixed seed and deterministic object IDs.

Include realistic mixtures of:

* requirements;
* implementation artifacts;
* tests;
* architecture nodes;
* relations from several semantic families.

Avoid pathological complete graphs unless specifically benchmarking a worst case.

## Measure

At minimum:

* analysis to snapshot;
* index construction if separable;
* representative bounded `select_graph`;
* representative validation/rules;
* fingerprints.

## Output

Human-readable table plus machine-readable JSON is preferred.

Example:

```text
size   edges    analyze_ms   projection_ms
100    250      ...
1000   2500     ...
...
```

## Documentation

Record:

* environment;
* Python version;
* measurement method;
* limitations;
* baseline observation date.

## CI

Do not create hard millisecond thresholds in ordinary CI.

A small deterministic smoke benchmark may run in CI only to prove the benchmark code works.

## Acceptance

The repository has a repeatable answer to:

> How does Quarto-Needs analysis scale today?

---

# Task 7 — Profile repeated graph derivation

## Purpose

Determine whether additional snapshot indexing is actually warranted.

## Inspect

At minimum:

```text
graph_projection.py
impact.py
suspect.py
policy.py
queries.py
rules.py
```

Look for repeated construction of:

* undirected adjacency;
* relation-family adjacency;
* relation-name adjacency;
* object maps already present on the snapshot.

## Measurement

Use the benchmark fixture introduced in Task 6.

Measure representative graph operations before making changes.

## Decision

### If repeated derivation is insignificant

Do nothing.

Document:

> measured; optimization not justified.

This is a valid and preferred outcome.

### If materially significant

Introduce the smallest reusable canonical index that removes demonstrated repeated work.

Do NOT add:

* transitive closure caches;
* all-pairs paths;
* arbitrary query caches;
* generic graph database abstractions.

## Acceptance

Every optimization introduced in this task cites a benchmark demonstrating its reason to exist.

---

# Task 8 — Define and enforce public schema compatibility policy

## Purpose

Make pre-1.0 evolution deliberate rather than accidental.

## Inventory

List all versioned/machine-consumable formats under:

```text
schemas/
```

and formats emitted in code with explicit `schemaVersion` or equivalent.

Classify each:

```text
public-versioned
internal-generated
test-fixture-only
```

## Document

Create:

```text
docs/schema-compatibility.md
```

Cover:

* additive compatible change;
* breaking change;
* version bump rule;
* deprecated field handling;
* deterministic serialization;
* unknown-field policy where relevant;
* distinction between Python internal fields and public projection fields.

## Tests

Ensure key public projections are constructed by explicit allowlists.

Add contract tests protecting against accidental exposure of a newly added internal attribute.

The public graph projection already follows this design; preserve and generalize the policy rather than replacing it.

## Acceptance

A contributor can determine whether a proposed artifact change requires a schema version bump.

---

# Task 9 — Verify the Quarto compatibility claim

## Purpose

Ensure declared extension compatibility matches tested compatibility.

## Inspect

```text
_extensions/quarto-needs/_extension.yml
.github/workflows/ci.yml
Makefile
Quarto rendering tests
```

## CI design

Introduce a minimum-version smoke path.

Conceptually:

```text
Quarto minimum supported
    -> install/sync extension
    -> scan/check
    -> render representative fixture

Quarto current integration version
    -> existing comprehensive render matrix
```

Do not unnecessarily duplicate expensive PDF/DOCX/multilingual jobs for every Quarto version.

The minimum job only needs to prove the supported extension path.

## Failure handling

If the declared minimum cannot execute the supported product contract:

1. determine whether this is accidental use of a newer API;
2. fix compatibility if straightforward and desirable;
3. otherwise deliberately raise `quarto-required`.

Never weaken the test merely to preserve the old version declaration.

## Acceptance

The extension's minimum Quarto claim has executable evidence.

---

# Task 10 — Add a minimal non-self-hosted example

## Purpose

Falsify the assumption that the product is understandable only through its own architecture or the larger Aegis showcase.

## Create

```text
examples/minimal/
```

Keep it deliberately small.

Suggested model:

```text
STK-001
   |
   v
REQ-001 -----> ADR-001
   |
   +---------> COMP-001
   |
   +---------> TC-001 -----> EVD-001
   |
   +---------> TC-002 -----> EVD-002
```

Include a small architecture hierarchy only if it naturally fits the example.

## Demonstrate

Only the core workflow:

```bash
quarto-needs scan
quarto-needs check
quarto-needs trace ...
quarto render
```

Use:

* need cards;
* a table;
* a matrix;
* one graph;
* optionally one C4 view.

Do not demonstrate federation, migration, or every exporter.

## Documentation

Give the example a short README explaining the engineering story rather than listing features.

## Test

Add a focused integration test ensuring:

* analysis succeeds;
* expected IDs/relations exist;
* quality gate is appropriate;
* Quarto render succeeds where the environment provides Quarto.

## Acceptance

A reader can understand the canonical Quarto-Needs workflow from this example without knowing the Quarto-Needs implementation.

---

# Task 11 — Consolidate legacy compatibility surfaces

## Purpose

Finish the semantic-core migration without unnecessarily breaking convenience APIs.

## Inspect remaining uses

Search for:

```text
EngineeringObject
Relation
SourceLocation
validate(
_legacy_objects
```

Classify each remaining use.

## For each use choose explicitly

### Keep

When it is a useful compatibility/test construction API.

Document that it adapts into the canonical pipeline.

### Replace

When a canonical internal module still uses it unnecessarily.

### Remove

When it is dead transitional code.

Do not delete a public-ish API merely because no current internal caller exists without checking documentation/tests/examples first.

## Acceptance

No unexplained transitional semantic bridge remains.

---

# Task 12 — Regression and architectural verification

Run focused and full verification.

At minimum:

```bash
python -m pytest -q
```

plus the repository's established checks for:

```text
self-hosted example
Aegis example
minimal example
multilingual semantic parity
Quarto render
installed consumer path
VS Code/LSP tests where available
ReqIF
JSON-LD
OSLC
migration adapters
graph projections
C4 projections/renderers
diff/impact/suspect
evidence
```

Respect environment limitations.

Do not report an unavailable external runner as a passing gate.

## Required regression assertions

The stabilization must not change meaning for existing fixtures.

Compare where practical:

* canonical snapshot;
* semantic fingerprint;
* representation fingerprint;
* findings;
* graph projection;
* C4 projection;
* baseline diff result.

---

# Task 13 — Final architecture documentation

Update the architecture documentation after implementation rather than before it.

At minimum review:

```text
ARCHITECTURE.md
docs/architecture/index.md
docs/architecture/domain-model.md
docs/architecture/building-blocks.md
docs/architecture/solution-strategy.md
docs/architecture/quality-and-risks.md
docs/ROADMAP.md
```

Add a short phase document:

```text
docs/phase-core-stabilization.md
```

Include:

1. what transitional architecture was removed;
2. the final semantic pipeline;
3. measured performance observations;
4. optimizations adopted;
5. optimizations deliberately rejected after measurement;
6. compatibility policy introduced;
7. Quarto compatibility result;
8. minimal-example result;
9. remaining known limitations.

Do not rewrite historical phase documents to pretend the stabilized architecture existed earlier.

---

# Task 14 — Final review package

Before declaring the phase complete, perform an independent review focused on architectural regression.

The reviewer should actively look for:

* a hidden second semantic model;
* duplicated validation;
* relation semantics moving into presentation;
* accidental schema changes;
* behavior changes disguised as refactoring;
* new caches without measured justification;
* mutable data escaping into `AnalysisSnapshot`;
* dependence on object ordering;
* legacy compatibility types still controlling canonical behavior;
* performance improvements that trade away determinism;
* feature creep.

Any finding should receive a fix round followed by re-review.

---

# Definition of Done

The work is complete only when:

* canonical analysis does not route through `EngineeringObject` for validation;
* structural validation is declaration-native;
* semantic validation is snapshot-native;
* existing diagnostics remain compatibly observable;
* indexes are linear-time constructed;
* benchmarks exist and have been executed;
* further graph optimization is measurement-driven;
* public schema compatibility is documented and guarded;
* the minimum Quarto compatibility claim is actually exercised;
* `examples/minimal/` exists and passes;
* existing examples remain green;
* architecture docs reflect the actual implementation;
* no new unrelated product capability was introduced.

---

# Suggested commit sequence

Prefer reviewable commits along these boundaries:

```text
test: characterize core validation behavior
refactor: add declaration-native structural validation
refactor: make semantic validation snapshot-native
test: enforce semantic-kernel boundaries
perf: build canonical graph indexes in linear time
test: add reproducible core benchmarks
perf: reuse measured graph indexes if justified
docs: define public schema compatibility
ci: verify minimum supported Quarto
feat: add minimal Quarto-Needs example
refactor: retire remaining legacy core bridges
docs: document stabilized semantic core
```

The exact number of commits may change when two steps are inseparable, but avoid one giant stabilization commit.

---

# Final implementation report

At the end, report:

## Changed

Concrete architectural changes.

## Preserved

Semantics deliberately kept identical.

## Performance

Before/after measurements for representative dataset sizes.

## Compatibility

Current results for Python, Quarto, artifacts, and examples.

## Removed transitional paths

Especially any `EngineeringObject`-based semantic bridge.

## Retained transitional paths

Anything deliberately retained and why.

## Deferred

Issues discovered but excluded by this phase's non-goals.

## Verification

Exact commands and outcomes.

The final question the reviewer must answer is:

> Can Quarto-Needs continue adding capabilities without adding another semantic center?

The answer must be demonstrably yes.
