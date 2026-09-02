# Quarto-Needs — Core Stabilization Design

**Date:** 2026-09-02
**Status:** Proposed
**Scope:** Semantic-core stabilization before further product expansion
**Target:** pre-1.0 architectural consolidation
**Repository:** `lsbjordao/quarto-needs`

---

# 1. Motivation

Quarto-Needs has evolved from a Quarto requirements-as-code extension into a broader engineering-traceability platform built around a typed property graph.

The current architecture has a strong central invariant:

> **One canonical engineering graph, many projections.**

The Python core is the semantic authority. Quarto/Lua, JavaScript, the CLI, LSP, VS Code, C4 renderers, ReqIF, JSON-LD, OSLC, migration adapters, CI projections, and interactive graph tooling consume results derived from that authority rather than independently defining engineering meaning.

This direction must be preserved.

The current risk is no longer insufficient capability. The project already spans requirements, decisions, architecture, verification, evidence, governance, change intelligence, editor tooling, interoperability, federation, migration, and interactive visualization.

The next engineering priority is therefore **stabilization of the semantic kernel**, not further horizontal expansion.

This phase must reduce transitional architecture, establish explicit core contracts, measure scaling behavior, remove avoidable algorithmic costs, strengthen compatibility guarantees, and create a minimal external consumer example.

---

# 2. Goals

This phase SHALL:

1. establish an explicit semantic-kernel boundary;
2. remove the semantic core's dependency on the legacy `EngineeringObject` validation bridge;
3. make declaration validation and resolved-model validation operate on the canonical pipeline;
4. preserve current diagnostic semantics unless deliberately documented otherwise;
5. build canonical graph indexes in linear time;
6. measure performance before introducing broader optimization;
7. prevent graph consumers from repeatedly rebuilding information already owned by the snapshot when measurement justifies reuse;
8. define public artifact/schema compatibility rules;
9. verify both the minimum supported Quarto version and the project's current supported Quarto path;
10. introduce a deliberately small onboarding/reference project that does not model Quarto-Needs itself;
11. update architecture documentation to describe the stabilized kernel;
12. retain all existing semantic invariants and projection boundaries.

---

# 3. Non-goals

This phase MUST NOT:

* add new graph-workbench features;
* add new C4 backends;
* add Dynamic or Deployment C4 views;
* add new federation providers;
* add new migration source adapters;
* add new interchange formats;
* redesign the authoring syntax;
* introduce relation-attribute authoring;
* split the project into multiple Python packages merely for architectural aesthetics;
* replace Quarto;
* replace the typed property graph;
* move semantic evaluation to Lua, JavaScript, TypeScript, CI YAML, or renderers;
* introduce a database;
* introduce a graph database;
* optimize code without a reproducible benchmark showing a relevant problem;
* change public artifact schemas casually as a side effect of refactoring.

Any discovery requiring one of these changes must be documented as a follow-on issue rather than folded into this phase.

---

# 4. Architectural invariants

The following are binding constraints.

## 4.1 Python remains the semantic authority

Engineering meaning is resolved in Python.

Presentation and integration layers consume resolved projections.

Lua, JavaScript, TypeScript, renderers, exporters, and external adapters MUST NOT acquire independent implementations of:

* relation meaning;
* impact direction;
* traversal semantics;
* type semantics;
* validation rules;
* query semantics;
* policy semantics;
* change classification.

---

## 4.2 One analysis, many projections

A project analysis produces one canonical resolved engineering state.

Conceptually:

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
   |        |         |         |          |
 diff     tables     views     ReqIF      hover
 impact   graphs              JSON-LD     refs
 rules
```

No projection may establish a competing semantic graph.

---

# 5. Stabilized semantic pipeline

The desired pipeline is:

```text
source text
    |
    v
Parser
    |
    v
DeclarationBatch
    |
    +--> declaration/structural validation
    |
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
    +--> semantic/governance validation
    +--> derived values
    +--> variants
    +--> queries
    +--> fingerprints
    |
    v
projections
```

The transitional path:

```text
ObjectDeclaration
       |
       v
EngineeringObject
       |
       v
legacy validate()
```

must no longer be required by canonical project analysis.

---

# 6. Legacy model strategy

`EngineeringObject`, `Relation`, and related compatibility DTOs currently have historical value and may still be useful to tests, helper APIs, or compatibility surfaces.

This phase MUST NOT delete them merely to achieve conceptual purity.

Instead:

> **The canonical analyzer must cease depending on them.**

After the refactor:

```text
canonical parser/analyzer
        X
        |
        +---- no dependency on EngineeringObject
```

Legacy DTOs may remain temporarily as:

* compatibility helpers;
* test constructors;
* external convenience API;
* adapters into the canonical declaration model.

If retained, their direction of dependency must be:

```text
EngineeringObject
      |
      v
canonical declarations / analyzer
```

and never:

```text
canonical declarations
      |
      v
EngineeringObject
      |
      v
semantic validation
```

A later deprecation decision can be made independently.

---

# 7. Validation architecture

Current validation responsibilities must be classified before moving code.

At minimum, distinguish:

## 7.1 Declaration/structural validation

Validation that can operate before a valid snapshot exists.

Examples include:

* duplicate canonical IDs;
* unresolved relation targets;
* malformed declarations;
* unsupported relation names;
* structurally impossible declarations;
* configuration/type compatibility needed before resolution.

These rules operate on declarations and relation tokens.

They are allowed to prevent snapshot construction.

---

## 7.2 Resolved semantic/governance validation

Validation that requires or benefits from the resolved graph.

Examples include:

* approved requirement without verification;
* missing rationale policies;
* graph constraints;
* cardinality;
* architecture adjacency;
* decision governance;
* evidence governance;
* path-based requirements;
* lifecycle rules.

These rules SHOULD operate on `AnalysisSnapshot`, `ObjectRecord`, and `RelationRecord`, not on transitional mutable DTOs.

---

## 7.3 Diagnostic compatibility

Refactoring validation MUST preserve, unless intentionally changed:

* diagnostic code;
* severity;
* object ID;
* source location;
* deterministic ordering;
* diagnostic message where the message is already effectively public/tested;
* whether the diagnostic prevents snapshot construction.

Characterization tests SHALL be added before replacing the bridge.

---

# 8. Semantic kernel boundary

For this phase, the semantic kernel is conceptually composed of:

```text
parsing declarations
        +
configuration semantics
        +
type/relation catalog
        +
resolution
        +
canonical records
        +
canonical graph indexes
        +
structural validation
        +
semantic validation infrastructure
        +
deterministic fingerprints
```

The following are consumers or higher-level subsystems rather than kernel identity:

```text
governance profiles / quality reporting
change intelligence
graph projections
C4 projections
Quarto rendering
interactive HTML
LSP transport
VS Code
ReqIF
JSON-LD
OSLC
GitHub adapters
migration adapters
```

This is an architectural dependency boundary, not a requirement to create new top-level Python packages during this phase.

---

# 9. Canonical graph indexes

`AnalysisSnapshot` already exposes:

* `objects_by_id`;
* `outgoing`;
* `incoming`.

Their construction SHALL be linear in the size of the resolved graph.

Target complexity:

```text
objects_by_id: O(V)
outgoing:      O(V + E)
incoming:      O(V + E)
```

The analyzer MUST NOT build outgoing/incoming indexes by scanning the full relation set once for every object.

Index values must remain deterministic and immutable.

Ordering inside indexes must follow the same deterministic relation ordering used by the canonical snapshot.

---

# 10. Derived adjacency and traversal indexes

No new general graph-index subsystem should be introduced speculatively.

First benchmark real consumers.

If `graph_projection.py`, impact analysis, policies, or traversal code repeatedly reconstruct adjacency from all relations and measurement demonstrates material cost, introduce one narrowly defined reusable representation.

Possible form:

```text
snapshot adjacency by canonical relation
or
snapshot adjacency by semantic family
```

but only after profiling demonstrates the need.

The system MUST avoid turning `AnalysisSnapshot` into an unbounded cache of every conceivable graph view.

---

# 11. Performance contract

This phase introduces reproducible benchmarks.

The purpose is not to promise arbitrary industrial scale before evidence exists.

The benchmark suite SHALL measure at least:

```text
100 objects
1,000 objects
10,000 objects
50,000 objects
```

with deterministic synthetic relation distributions.

At minimum measure:

* declaration-to-snapshot analysis;
* graph index construction;
* common graph neighborhood projection;
* validation/rule execution;
* snapshot fingerprint computation where separable.

Record:

* wall-clock duration;
* object count;
* relation count;
* relevant environment metadata.

Performance tests MUST NOT become flaky normal CI gates based on tight timing thresholds.

They SHOULD instead provide:

1. deterministic benchmark generation;
2. manually runnable measurement command;
3. a lightweight regression/property test proving algorithmic construction where possible;
4. documented baseline observations.

Optimization SHALL follow measurement, not precede it.

---

# 12. Public contract stabilization

Quarto-Needs already emits several externally consumable artifacts.

This phase SHALL explicitly classify contracts into:

## Stable/versioned public contracts

Examples:

* canonical exported needs/snapshot schema;
* public graph projection schema;
* baseline format;
* diff/impact formats where published as machine contracts;
* ReqIF projection contract;
* JSON-LD namespace/context;
* evidence envelopes;
* migration-plan schemas where externally consumed.

## Internal generated artifacts

Artifacts not promised as stable external APIs.

Every public artifact SHALL have:

* explicit schema/version identifier;
* compatibility policy;
* documented rule for additive changes;
* documented rule for breaking changes;
* test coverage for required fields and deterministic serialization.

A schema version MUST change for a breaking contract change.

Adding a Python field MUST NOT automatically expose it publicly.

Allowlist-based projections remain preferred.

---

# 13. Quarto compatibility

The extension currently declares a minimum Quarto version.

That claim must be tested.

CI SHALL distinguish:

```text
minimum-supported Quarto
current/pinned integration Quarto
```

At least the core extension/render smoke path must run against the declared minimum.

The richer full-document integration path may remain pinned to the project's current primary Quarto version when newer rendering facilities are deliberately required.

If the declared minimum cannot actually execute the supported extension path, either:

* compatibility must be fixed; or
* `quarto-required` must be increased explicitly.

The project MUST NOT claim an untested compatibility range.

---

# 14. Minimal external example

Add a deliberately small project whose purpose is onboarding and architectural falsification.

Suggested location:

```text
examples/minimal/
```

Characteristics:

* approximately 15–30 engineering objects;
* one stakeholder need;
* a small requirement hierarchy;
* one ADR;
* one architecture chain;
* one implementation artifact;
* two or three test cases;
* evidence;
* at least one generated table;
* one traceability matrix;
* one bounded graph;
* one C4 view if naturally justified;
* no federation;
* no migration;
* no large dashboard;
* no attempt to demonstrate every Quarto-Needs capability.

The project SHALL answer:

> Can a new user understand the core model without first understanding the Quarto-Needs codebase?

It also provides a non-self-hosted integration fixture independent of the larger Aegis showcase.

---

# 15. Architecture documentation updates

At completion, architecture documentation SHALL clearly distinguish:

```text
authoring model
declaration model
resolved semantic model
governance
change intelligence
projections
adapters
```

`docs/architecture/domain-model.md` should reflect the canonical pipeline after the legacy validation bridge is removed.

`docs/architecture/building-blocks.md` should make the semantic-kernel boundary understandable without pretending each conceptual subsystem is independently deployable.

An ADR should be added only if a genuinely new durable architectural decision is made during implementation.

Do not create ADRs merely to record refactoring mechanics.

---

# 16. Testing strategy

This phase requires characterization before modification.

Tests should cover:

## Semantic equivalence

Given equivalent declarations before and after the refactor:

* same snapshot objects;
* same canonical relations;
* same fingerprints;
* same findings;
* same query results;
* same quality results;
* same diff/impact behavior.

## Structural failure

Projects with:

* duplicate IDs;
* missing targets;
* unsupported relations;
* invalid architecture containment;

must retain expected failure behavior.

## Determinism

Input ordering permutations MUST NOT change:

* canonical object ordering;
* canonical relation ordering;
* indexes;
* fingerprints;
* public artifacts.

## Projection independence

Refactoring the kernel MUST NOT require semantic changes in:

* Lua;
* JavaScript;
* TypeScript;
* C4 renderer adapters.

If such changes appear necessary, stop and verify whether semantics are leaking across the boundary.

---

# 17. Acceptance criteria

This phase is complete when all of the following hold.

1. `analyze_project()` no longer converts canonical declarations to `EngineeringObject` in order to validate them.
2. Canonical validation operates directly on declarations and/or resolved snapshot records.
3. Current externally meaningful diagnostic behavior is characterization-tested and preserved.
4. Snapshot indexes are built in O(V + E) rather than O(VE).
5. A reproducible benchmark suite exists and has recorded baseline observations.
6. No optimization beyond proven bottlenecks was introduced.
7. Public artifact/schema compatibility rules are documented and tested.
8. The declared minimum Quarto version is exercised by CI or deliberately raised.
9. A minimal non-self-hosted example renders and passes its checks.
10. Existing Aegis and self-hosted examples continue to pass.
11. Existing C4, graph, LSP, evidence, change-intelligence, interoperability, and migration tests remain green.
12. Architecture documentation reflects the stabilized model.
13. No feature listed under Non-goals was added.
14. The final implementation report identifies any remaining transitional API and explains why it was retained.

---

# 18. Success criterion

The phase succeeds if a maintainer can point to one small, explicit semantic kernel and say:

> This is where a Quarto-Needs engineering model becomes canonical.

Everything else should either govern that canonical model, compare it, project it, render it, edit it, or exchange it.

The stabilization is not intended to make Quarto-Needs smaller in capability.

It is intended to make its growing capability surface depend on a smaller, clearer, better measured, and more stable center.
