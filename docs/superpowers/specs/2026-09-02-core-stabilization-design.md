# Quarto-Needs — Core Stabilization Design

**Date:** 2026-09-02
**Status:** Proposed
**Scope:** Semantic-core stabilization before further product expansion
**Target:** pre-1.0 architectural consolidation

This design revises an earlier draft of the same name. The earlier draft's
two central claims were verified against the code and both hold; its
*proportions* did not. What changed, and the evidence that forced each
change, is recorded in §2 so the revision is auditable rather than merely
different.

---

# 1. Motivation

Quarto-Needs has a strong central invariant:

> **One canonical engineering graph, many projections.**

Python is the semantic authority. Quarto/Lua, JavaScript, the CLI, LSP,
VS Code, C4 renderers, ReqIF, JSON-LD, OSLC, migration adapters and CI
projections consume results derived from that authority rather than defining
engineering meaning of their own.

The current risk is not insufficient capability. It is that two transitional
paths in the semantic core have outlived their purpose, and that a small
number of reproducibility defects make the project's own test suite
environment-dependent. Both are cheap to fix now and get more expensive with
every subsystem added on top.

This phase stabilizes the kernel. It does not grow it.

---

# 2. What this revision changes, and the evidence for it

The earlier draft was right about direction and wrong about size. Five
corrections, each with the evidence that forced it:

### 2.1 The legacy validation bridge is 60 lines and 4 diagnostics, not a validation architecture

`src/quarto_needs/validation.py` is 60 lines. `validate()` emits exactly four
codes: `REQ004` (duplicate ID), `REQ005` (unknown relation target), `REQ002`
(missing rationale), `REQ006` (approved without verification).

Decisively: `src/quarto_needs/rules.py:31` already declares

```python
LEGACY_CODES = frozenset({"REQ002", "REQ004", "REQ005", "REQ006"})
```

and the rule registry already holds a `RuleSpec` for each of the four, with
`evaluator=None`. The registry therefore **already owns their severity, their
configuration policy, and their structural flag**. Only their *evaluation*
still runs over `EngineeringObject`.

The migration splits four ways along a line that already exists in the code,
and §2.2 explains why it is not a clean "move all four into `rules.py`".

### 2.2 The four codes do not all belong in the rule registry — and the correct split is already named

`RuleContext` is `(snapshot: AnalysisSnapshot, config: NeedsConfig)`
(`rules.py:23-26`). A `rules.py` evaluator therefore *requires a snapshot*.

But `REQ004` (duplicate ID) and `REQ005` (unknown target) are structural:
they must fire **before** a snapshot exists, and they prevent its
construction. They cannot become ordinary evaluators without inverting the
pipeline.

The repository already names this distinction, one line above the one the
earlier draft focused on — `rules.py:30`:

```python
STRUCTURAL_CODES = frozenset({"REQ004", "REQ005"})
LEGACY_CODES     = frozenset({"REQ002", "REQ004", "REQ005", "REQ006"})
```

So the migration is:

* `REQ002`, `REQ006` → real evaluators in `rules.py`, snapshot-native;
* `REQ004`, `REQ005` → a declaration-native structural validator, which is
  what they always were;
* `LEGACY_CODES` → **collapses into `STRUCTURAL_CODES`**, which already
  contains exactly the two codes that legitimately have no evaluator.

The exemption stops meaning "these are old" and starts meaning "these run
before a snapshot exists" — a permanent architectural category rather than a
migration artifact.

### 2.3 The architectural test the earlier draft wanted is already written, once narrowed

`src/quarto_needs/rules.py:453-455`:

```python
for _spec in RULES.values():
    if _spec.evaluator is None and _spec.code not in LEGACY_CODES:
        raise RuntimeError(f"rule {_spec.code} lacks an evaluator")
```

Narrowing `LEGACY_CODES` to `STRUCTURAL_CODES` in that check makes the
invariant self-enforcing at import time: any *non-structural* rule without an
evaluator crashes the package. No new architecture test is required, and none
should be added.

The earlier draft proposed a "search-based architectural test" in its Task 3
while its own Task 4 warned against grep-based architecture tests. This
resolves that contradiction in favour of the mechanism the repository already
has.

### 2.4 The trap this migration must not fall into

`_resolved_severity` (`rules.py:458-465`) uses `LEGACY_CODES` for a *second*
purpose: a code in that set activates by default with no configuration. So
`REQ002` and `REQ006` are currently always-on.

Collapsing the set without compensating would silently switch both rules off
for every project that does not configure them — a severe, quiet behaviour
regression that no existing test may catch. Their `RuleSpec`s must gain an
explicit always-true `auto_activates` (or equivalent) in the same commit, and
a characterization test must pin "REQ002/REQ006 fire on a project with no
`[rules]` configuration" **before** the set is touched.

### 2.5 The O(V·E) index build is an internal inconsistency, not a design decision

`src/quarto_needs/analysis.py:344-352` builds both indexes with a full
relation scan per object. The correct linear idiom already exists 250 lines
earlier in the same file, at `analysis.py:96-100`:

```python
outgoing = {item.id: [] for item in objects}
for relation in relations:
    outgoing.setdefault(relation.source, []).append(relation)
```

This is a one-commit correction that makes the file agree with itself, not a
task requiring measurement to justify.

### 2.6 Benchmarks are Phase 8, and belong there

The earlier draft's benchmark tasks specified corpora of 100 / 1,000 /
10,000 / 50,000 objects. `docs/ROADMAP.md`'s Phase 8 already specifies
"synthetic sparse/dense/cyclic/high-fanout corpora around 100, 1,000, 10,000,
and 50,000+ objects" and the same measurement surface. Restating a planned
milestone inside a stabilization phase inflates the phase and blurs the
roadmap.

Benchmarks are therefore **out of scope here** and stay in Phase 8, where
§2.5's fix will already have landed.

The consequence is deliberate: this phase performs **no measurement-driven
optimization at all**. The only performance change it makes is the one that
needs no benchmark to justify — making a file consistent with itself.

---

# 3. Goals

This phase SHALL:

1. remove the semantic core's dependency on the `EngineeringObject`
   validation bridge, preserving all four diagnostics' observable behaviour;
2. narrow the rule registry's evaluator exemption from `LEGACY_CODES` to
   `STRUCTURAL_CODES`, so its existing import-time check enforces the
   invariant for every non-structural rule, without changing which rules are
   active by default;
3. build the canonical graph indexes in linear time;
4. make the test suite reproducible from a clean clone;
5. remove generated, date-dependent content from tracked files;
6. define and test public artifact/schema compatibility rules;
7. add a small onboarding example that does not model Quarto-Needs itself;
8. update architecture documentation to describe the stabilized kernel;
9. retain every existing semantic invariant and projection boundary.

---

# 4. Non-goals

This phase MUST NOT:

* add benchmarks or performance corpora (Phase 8 owns those);
* perform any optimization other than §2.5's linear index construction;
* add graph-workbench features, C4 backends, C4 levels, federation
  providers, migration adapters, or interchange formats;
* redesign authoring syntax or add relation-attribute authoring;
* split the project into multiple Python packages;
* introduce a database or graph database;
* move semantic evaluation into Lua, JavaScript, TypeScript, CI YAML, or
  renderers;
* change public artifact schemas as a side effect of refactoring;
* delete `EngineeringObject` / `Relation` merely for conceptual purity.

Any discovery requiring one of these is recorded as a follow-on issue rather
than folded into this phase.

---

# 5. Architectural invariants

## 5.1 Python remains the semantic authority

Presentation and integration layers consume resolved projections. They MUST
NOT acquire independent implementations of relation meaning, impact
direction, traversal semantics, type semantics, validation rules, query
semantics, policy semantics, or change classification.

## 5.2 One analysis, many projections

```text
QMD / overlays / configuration
            |
            v
     DeclarationBatch
            |
            v
      canonical analysis
            |
            v
     AnalysisSnapshot
            |
   +--------+---------+---------+----------+
   |        |         |         |          |
  CLI     Quarto     C4      exporters    LSP
```

No projection may establish a competing semantic graph.

---

# 6. Target semantic pipeline

```text
source text -> Parser -> DeclarationBatch
                              |
                              +--> declaration/structural validation
                              v
                          Resolution
                              |
                              v
              ObjectRecord + RelationRecord
                              |
                              v
                   indexed immutable graph
                              |
                              v
                       AnalysisSnapshot
                              |
                              +--> rule evaluation (all rules, one registry)
                              +--> derived values / variants / queries
                              +--> fingerprints
                              v
                          projections
```

The transitional path

```text
ObjectDeclaration -> EngineeringObject -> legacy validate()
```

must no longer exist in canonical analysis.

---

# 7. Legacy model strategy

`EngineeringObject` and `Relation` keep genuine value as test constructors
and as a convenience API. This phase MUST NOT delete them.

The requirement is directional:

```text
EngineeringObject -> canonical declarations -> analyzer      (allowed)
canonical declarations -> EngineeringObject -> validation    (forbidden)
```

`analyze_objects(Iterable[EngineeringObject])` may remain, provided it adapts
into the canonical pipeline rather than implementing a second analysis.

---

# 8. Validation architecture

Two categories, distinguished by whether a resolved graph is required.

**Declaration/structural** — can run before a valid snapshot exists, and may
prevent snapshot construction: duplicate canonical IDs (`REQ004`), unresolved
relation targets (`REQ005`), unsupported relation names, malformed
declarations.

**Resolved semantic/governance** — requires or benefits from the resolved
graph: missing rationale (`REQ002`), approved-without-verification (`REQ006`),
graph constraints, cardinality, architecture adjacency, decision and evidence
governance, lifecycle rules.

The second category is already `rules.py`'s job. The first category's two
codes are structural (`rules.py:30`, `STRUCTURAL_CODES`) and must retain
their snapshot-blocking behaviour.

## 8.1 Diagnostic compatibility

Refactoring MUST preserve, unless a change is documented and approved:
diagnostic code, severity, object ID, source location, deterministic
ordering, message text where already effectively public, and whether the
diagnostic prevents snapshot construction.

Characterization tests SHALL be written **before** the bridge is touched.

---

# 9. Canonical graph indexes

`objects_by_id`, `outgoing` and `incoming` SHALL be built as:

```text
objects_by_id: O(V)
outgoing:      O(V + E)
incoming:      O(V + E)
```

Values stay deterministic and immutable, ordered by the same canonical
relation ordering the snapshot already uses.

No new index is introduced. This phase corrects the construction of the three
that exist and adds nothing — an unbounded cache of every conceivable graph
view is exactly what a stabilization phase must not produce.

---

# 10. Reproducibility

Two defects observed while provisioning a clean worktree on 2026-09-02. Both
are kernel-reproducibility problems and both are in scope.

**10.1 A clean clone cannot run its own test suite.**

`tests/fixtures/views/.quarto-needs/needs.json` is gitignored, and
`copy_fixture_project` (`tests/test_quarto_views.py`) copies it into the
temporary project *without re-scanning*. It is not reproducible by running
`quarto-needs scan` against the fixture, because the fixture has no
`.quarto-needs.toml`, so `cli.build` writes no `extensions.quartoNeeds.report`
block. Ten tests across `test_quarto_views.py` and `test_views_helpers.py`
fail on a fresh checkout.

The fixture's generated state SHALL become reproducible — by giving the
fixture the configuration its tests actually require, by generating the
artifact in a session-scoped test fixture, or by tracking it deliberately as
a checked-in fixture. Any of the three is acceptable. A test suite that only
passes on a machine which has already run it is not.

**10.2 A tracked artifact embeds the current date.**

`examples/book/.quarto-needs/needs.json` is tracked and carries
`referenceDate`. Every test run on a new day rewrites it, dirtying the working
tree and inviting an accidental commit of unrelated churn.

Either the reference date is pinned deterministically for that example, or the
artifact stops being tracked. Determinism is already a stated project
property; a tracked file that changes with the calendar contradicts it.

---

# 11. Public contract stabilization

Artifacts SHALL be classified as **public-versioned**, **internal-generated**,
or **test-fixture-only**.

Every public artifact SHALL have an explicit schema/version identifier, a
documented compatibility policy covering additive and breaking changes, and
test coverage for required fields and deterministic serialization.

A breaking contract change MUST bump the schema version. Adding a Python field
MUST NOT automatically expose it publicly — allowlist-based projection (the
pattern `graph_projection.py` already uses, and documents in its module
docstring as "deny by default") remains required.

---

# 12. Quarto compatibility

`_extensions/quarto-needs/_extension.yml` declares a minimum Quarto version.
That claim SHOULD be exercised rather than asserted.

**Constraint of record:** this project's GitHub Actions quota is exhausted, so
CI-based verification cannot be validated as part of this phase. The phase
SHALL therefore deliver the minimum-version smoke *path* as a locally runnable
target, and document that its CI wiring is unverified until quota returns.

The project MUST NOT claim an untested compatibility range. If the declared
minimum cannot be exercised at all, `quarto-required` is raised instead.

---

# 13. Minimal external example

`examples/minimal/` — roughly 15-30 objects: one stakeholder need, a small
requirement hierarchy, one ADR, one architecture chain, one implementation
artifact, two or three test cases, evidence, one generated table, one
traceability matrix, one bounded graph.

No federation, no migration, no dashboard, no attempt to demonstrate every
capability. It answers one question:

> Can a new user understand the core model without first understanding the
> Quarto-Needs codebase?

It also provides a non-self-hosted integration fixture independent of the
larger showcase.

---

# 14. Testing strategy

**Semantic equivalence.** For equivalent declarations before and after: same
snapshot objects, same canonical relations, same fingerprints, same findings,
same query results, same quality results, same diff/impact behaviour.

**Structural failure.** Duplicate IDs, missing targets, unsupported relations
and invalid architecture containment retain their failure behaviour, including
whether they block snapshot construction.

**Determinism.** Input ordering permutations MUST NOT change canonical object
ordering, canonical relation ordering, indexes, fingerprints, or public
artifacts.

**Projection independence.** Kernel refactoring MUST NOT require semantic
changes in Lua, JavaScript, TypeScript, or C4 renderer adapters. If such a
change appears necessary, stop — semantics are leaking across the boundary.

---

# 15. Acceptance criteria

1. `analyze_project()` no longer converts canonical declarations to
   `EngineeringObject` in order to validate them.
2. All four legacy codes are evaluated by the rule registry against
   `ObjectRecord` / `AnalysisSnapshot`.
3. `LEGACY_CODES` is collapsed into `STRUCTURAL_CODES`, so `rules.py`'s
   import-time check rejects any *non-structural* rule lacking an evaluator
   unaided; `REQ002`/`REQ006` keep default activation via an explicit
   `auto_activates`, pinned by a test written before the change.
4. The four diagnostics' observable behaviour is characterization-tested and
   preserved.
5. Snapshot indexes are built in O(V + E).
6. No other optimization was introduced, and no benchmark was added.
7. The test suite passes from a clean clone with no pre-existing generated
   state.
8. No tracked artifact changes as a function of the current date.
9. Public artifact compatibility rules are documented and tested.
10. A minimal non-self-hosted example renders and passes its checks.
11. Existing examples, C4, graph, LSP, evidence, change-intelligence,
    interoperability and migration tests remain green.
12. Architecture documentation reflects the stabilized model.
13. No feature listed under Non-goals was added.
14. The final report names any remaining transitional API and why it stayed.

---

# 16. Sequencing constraint

This phase touches `analysis.py`, `validation.py`, `rules.py` and
`snapshot.py`. Two other efforts touch overlapping ground as of 2026-09-02:

* the C4 IR plan (`2026-09-02-phase-6b-c4-ir-and-renderer-boundary.md`),
  which retires `c4_projection.py` / `c4_render.py` — both direct consumers of
  the snapshot this phase reshapes;
* uncommitted flat renderer modules in the shared checkout
  (`c4_structurizr.py`, `c4_plantuml.py`, `c4_d2.py`) which modify
  `graph_output.py`.

Stabilization SHOULD run **after** those land and reconcile. It is
substantially cheaper once the legacy C4 modules are gone, because they are
consumers of exactly what §9 and §8 change.

---

# 17. Success criterion

A maintainer can point at one small, explicit semantic kernel and say:

> This is where a Quarto-Needs engineering model becomes canonical.

Everything else governs that model, compares it, projects it, renders it,
edits it, or exchanges it.

The stabilization does not make Quarto-Needs smaller in capability. It makes
its growing capability surface depend on a smaller, clearer, more stable
centre.
