# Quarto-Needs roadmap

Quarto-Needs is evolving from a requirements-as-code extension into an executable engineering knowledge graph for Git-based software development.

The roadmap is intentionally capability-oriented. It does **not** aim to reproduce another tool's syntax. Every capability must extend the canonical engineering model first; Quarto, the CLI, exporters, CI, and interactive HTML remain projections over that same semantic authority.

## North star

> Quarto-Needs is a requirements, architecture-decision, verification, evidence, change-intelligence, and engineering-traceability engine built around a typed property graph, with Quarto as its executable documentation interface.

A mature project should be able to answer, from the same canonical model:

- Why does this requirement exist?
- Which architecture decision addresses it?
- Where is it implemented?
- Which executable tests verify it?
- Which machine evidence proves those tests ran successfully?
- What changed between two Git states?
- What engineering objects are affected by that change, and through which path?
- Which links became suspect and require renewed review?
- Which policies or quality gates are currently violated?
- How can this model be exchanged with external requirements and architecture tooling?

## Architectural guardrails

These are roadmap constraints, not optional polish.

1. **Python remains the semantic authority.** Lua and JavaScript consume projections; they do not redefine relation, query, rule, impact, or coverage semantics.
2. **One model, many projections.** CLI, Quarto, exporters, graph views, CI reports, ReqIF, JSON-LD, and editor tooling must derive from the same analysis result.
3. **Requirements as code.** Human-authored engineering intent remains text-first, versionable, diffable, and reviewable in Git.
4. **Evidence is distinct from assertion.** A test declaration describes verification intent; a deterministic provider artifact records what executed; a provenance-bearing attestation binds that provider result to a concrete engineering state.
5. **Change intelligence is explainable.** Impact always carries explicit paths and policies. No opaque score replaces the graph explanation.
6. **Interactive UI is progressive enhancement.** Static HTML, PDF, DOCX, and non-JavaScript users retain equivalent engineering information.
7. **External data is provenance-preserving.** Imports are read-only by default, versioned, digestible, and explicit about trust and origin.
8. **Declarative configuration is bounded.** User-defined policy, queries, derived fields, and variants never evaluate arbitrary Python/Lua/JavaScript.
9. **Interchange formats do not become the authoring model.** ReqIF, OSLC, JSON-LD, SARIF, and other formats are adapters around the canonical graph.
10. **Performance is measured.** Scaling claims require synthetic sparse, dense, cyclic, and high-fanout benchmarks.

---

## Foundation already established

The current architecture already provides the substrate for the roadmap:

- typed engineering objects and configurable type roles;
- canonical relation catalog with direct/inverse labels, semantic families, endpoint roles, impact direction, and traversal direction;
- deterministic canonical snapshots and fingerprints;
- validation, configurable governance, quality gates, and named queries;
- architecture decisions as first-class objects;
- baseline, semantic diff, and union-graph impact analysis;
- JSON, CSV, SARIF, JUnit, and Markdown exporters;
- bounded public graph projections with deny-by-default provenance;
- static and interactive graph views driven by the same projection;
- multilingual presentation with semantic parity validation;
- a self-hosted bilingual engineering model in `examples/quarto-needs/`.

---

# Phase 1 — Executable verification and machine evidence ✅

**Status: implemented end to end on the current development branch.** Phase 1 now closes the gap between authored traceability and executable proof while preserving deterministic provider output separately from volatile provenance/freshness metadata.

## 1.1 pytest requirement linkage ✅

Implemented through the packaged pytest plugin and reciprocal markers:

```python
@pytest.mark.requirement("FUN-004")
@pytest.mark.quarto_need_test_case("TC-010")
def test_graph_exploration_assets():
    ...
```

The plugin records stable pytest node IDs, linked requirement IDs, modeled test-case IDs, and normalized outcomes in deterministic `evidence-pytest-v1` artifacts. Ordinary pytest runs remain side-effect free unless evidence output is explicitly requested.

## 1.2 Test-case binding ✅

Modeled `test-case` objects bind to executable tests through stable `pytest-nodeid` attributes. The verifier proves agreement across both directions:

```text
requirement --verified-by--> TC-xxx
TC-xxx      --binds-to-----> pytest nodeid
pytest marker -------------> same requirement
```

It reports disagreement instead of silently trusting either the authored graph or the executable marker set.

## 1.3 Evidence-provider protocol ✅

A provider-neutral `evidence-checks-v1` contract is implemented alongside the pytest-specific payload. Initial adapters cover:

- pytest execution results;
- JUnit XML;
- coverage.py JSON;
- Quarto render results;
- JSON Schema validation results;
- lint results;
- type-check results.

The generic contract carries deterministic checks with optional `requirements`, `testCases`, and `evidenceObjects` references. Provider adapters normalize results already produced by tools; they do not execute arbitrary external commands or schemas as a hidden side effect.

## 1.4 Evidence verification and freshness ✅

Machine evidence can be matched to modeled `evidence` objects and checked for:

- provider identity and provider compatibility;
- referenced requirement/test/evidence identities;
- executable/check outcome;
- verification and evidence-family graph relations;
- source/Git revision when available;
- configuration, semantic-graph, and representation fingerprints;
- payload digest integrity;
- generation timestamp;
- explicit expiry/freshness.

`evidence-envelope-v1` separates volatile attestation metadata from deterministic provider payloads. `quarto-needs evidence attest` creates the envelope and `quarto-needs evidence check` dispatches by embedded artifact schema. Raw provider payloads remain checkable for backward compatibility.

## 1.5 Self-hosted executable evidence ✅

The self-hosted example now has five real executable bindings covering the principal vertical slices and one additional concrete graph-contract slice:

1. multilingual semantic parity;
2. architecture-decision governance;
3. public graph contract/safety;
4. named graph views;
5. baseline/diff/impact analysis.

`make evidence-self-example` executes the real pytest nodes, writes deterministic provider output, creates a 24-hour attestation bound to the current engineering snapshot, and validates that attestation. `render-self-example` depends on this flow, so stale, incomplete, tampered, expired, or semantically inconsistent evidence blocks the executable case study.

### Phase 1 hardening that remains compatible with the completed architecture

Phase 1 is functionally complete. Later work may still add more provider adapters, signatures/SLSA-style provenance, stronger repository revision discovery outside CI, provider-specific richer details, and additional self-hosted evidence bindings without changing the established payload/envelope separation.

---

# Phase 2 — Git-native change intelligence and pull-request governance

**Status: next major implementation phase.** The existing baseline/diff/impact engine is the semantic substrate; Phase 2 makes Git ranges and pull requests first-class consumers of it.

## 2.1 Git-range analysis

Add native workflows such as:

```bash
quarto-needs diff --git main..HEAD
quarto-needs impact --git main..HEAD
```

The implementation must materialize both engineering states deterministically rather than infer semantic change from textual patches alone.

## 2.2 Suspect traceability

When a requirement, decision, implementation artifact, test, or evidence changes, linked review claims can become **suspect**.

Suspect state must be derived from explicit fingerprint/change rules and carry a witness explaining why re-review is required.

## 2.3 Pull-request engineering report

Generate a PR-oriented report containing, at minimum:

- changed requirements;
- changed ADRs;
- affected architecture elements;
- affected source modules;
- downstream tests;
- stale or missing evidence;
- new/removed findings;
- gate regressions;
- explicit impact paths.

## 2.4 GitHub annotations and checks

Project findings into GitHub-compatible surfaces while keeping GitHub as a consumer, not semantic authority:

- SARIF/code-scanning annotations;
- step summaries;
- optional PR check summary;
- deep links back to the rendered engineering model.

## 2.5 Real change tutorial

The `examples/quarto-needs/` Change chapter should use an actual Quarto-Needs product change as its historical case. The optional margin-TOC collapse feature is a suitable first exemplar because it spans stakeholder concern, functional requirement, design decision, extension assets, tests, and evidence.

---

# Phase 3 — Declarative engineering policy engine

## 3.1 User-defined rules

Generalize the built-in rule protocol into a bounded declarative DSL. Example direction:

```toml
[policies.NFR_REQUIRES_TEST]
scope = "approved-nfr"
assert-relation = "verified-by"
target-role = "verification"
minimum = 1
severity = "error"
```

## 3.2 Type schemas

Support per-type JSON Schema constraints for attributes while preserving the existing type-role, prefix, lifecycle, and required-attribute configuration.

## 3.3 Graph constraints

Add declarative constraints over:

- relation endpoint roles/types;
- cardinality;
- required paths;
- forbidden cycles;
- orphan policies;
- ambiguity/multiple-parent rules;
- review/freshness requirements.

## 3.4 Safe derived fields and variants

Allow bounded derived values and build variants without arbitrary code execution. Derived values must be reproducible and included in the appropriate fingerprints.

---

# Phase 4 — Authoring ergonomics: LSP and VS Code

## 4.1 Language Server Protocol

Implement an LSP over the same parser/configuration/catalog used by the CLI.

Capabilities:

- completion for IDs, types, statuses, relations, and configured attributes;
- diagnostics for unknown IDs, endpoint violations, lifecycle errors, and policy findings;
- hover with engineering metadata and coverage;
- go-to-definition across `.qmd` sources;
- find references/backlinks;
- relation-aware rename/refactor;
- document symbols and workspace symbols.

## 4.2 VS Code extension

Keep the editor thin: the VS Code extension should consume the Quarto-Needs LSP rather than implement a second parser.

Potential enhancements:

- traceability peek;
- graph preview for the focused object;
- quality-gate status;
- baseline/change indicators;
- quick fixes for safe, unambiguous edits.

---

# Phase 5 — Interchange, migration, and federation

## 5.1 ReqIF

Implement ReqIF 1.2 export first, validated against the normative XSD and at least one independent parser. Add import only after identity, rich-text, attribute-definition, relation, and round-trip loss semantics are explicit.

## 5.2 JSON-LD

Expose a versioned JSON-LD projection of the canonical graph to make stable identities, typed objects, and relations available to linked-data tooling without making RDF the internal storage model.

## 5.3 OSLC Requirements Management

Add OSLC RM federation only after authentication, caching, provenance, identity, conflict, and offline behavior have explicit contracts.

## 5.4 Migration adapters

Provide optional import/migration paths for established docs-as-code ecosystems, including Sphinx-Needs, while keeping Quarto-native authoring as the primary interface.

## 5.5 External service adapters

Read-only, cacheable adapters may target systems such as GitHub issues or other lifecycle-management services. Every imported object must preserve origin, stable external identity, digest/version, retrieval policy, and trust status.

---

# Phase 6 — Architecture model and C4 projections

The goal is not to maintain a second architecture model. C4-like views should be **projections of the same engineering graph**.

## 6.1 Context elements

Allow projects to model actors/people, external systems, system boundaries, and interactions using configurable types and relations.

## 6.2 Hierarchical architecture roles

Support or document role patterns corresponding to:

- software system;
- container/subsystem/application/data store;
- component;
- interface;
- code/source module.

## 6.3 Generated views

Provide semantic views inspired by the C4 hierarchy:

- System Context;
- Container/subsystem;
- Component;
- Code/implementation.

Each view remains query/projection driven and must be traceable back to requirements, decisions, risks, tests, and evidence.

## 6.4 Dynamic and deployment views

Consider dynamic and deployment projections only after the static architecture hierarchy is stable and useful.

---

# Phase 7 — Interactive graph workbench

Extend the Cytoscape view from visualization into a controlled engineering-analysis workbench.

Planned capabilities:

- shortest path between two objects;
- baseline/current visual comparison;
- show-only-affected mode;
- clustering by type, semantic role, layer, component, or configured attribute;
- exploration breadcrumbs;
- deep-linkable focused object/view/filter state;
- saved/restored exploration state;
- fullscreen exploration;
- SVG/PNG export;
- mini-map for large projections;
- richer keyboard navigation and accessibility;
- configurable layout presets without changing graph semantics.

All interactive operations must consume published relation semantics and bounded projections.

---

# Phase 8 — Scale, performance, compatibility, and release hardening

## 8.1 Synthetic benchmark corpus

Maintain benchmark projects with approximately:

- 100 objects;
- 1,000 objects;
- 10,000 objects;
- 50,000+ objects where practical;

across sparse, dense, cyclic, and high-fanout graph shapes.

Measure:

- parsing;
- canonical analysis;
- rule evaluation;
- named queries;
- baseline/diff/impact;
- public graph projection;
- export;
- Quarto render cost.

## 8.2 Incremental analysis

Introduce caching/incrementality only when benchmarks demonstrate a real bottleneck. Cache keys must include all semantic inputs and remain safe under configuration/catalog changes.

## 8.3 Release gates

Every release should report or test:

- schema compatibility;
- deterministic outputs;
- migration behavior;
- accessibility;
- public-projection security;
- performance budgets;
- supported Python/Quarto versions;
- self-hosted example health.

---

# Phase 9 — Teaching, examples, and failure scenarios

## 9.1 Self-hosted example as the living engineering model

`examples/quarto-needs/` should increasingly become the official engineering model of Quarto-Needs itself. Significant product changes should update the relevant engineering objects in the same pull request as code and tests.

The target vertical slice is:

```text
stakeholder need
    ↓ motivates/refines
requirement
    ↓ addressed by
architecture decision
    ↓ scoped to
architecture element
    ↓ implemented in
source module
    ↓ verified by
executable test / machine check
    ↓ demonstrated by
deterministic provider evidence
    ↓ attested against
engineering snapshot + source revision + freshness
    ↓ associated with
Git change / review state
```

The stored canonical relation direction remains authoritative even when a pedagogical diagram reads in the opposite process direction.

## 9.2 Quality attributes

Expand the model only when verification is available for the attribute being claimed. Candidate quality attributes include:

- determinism;
- reproducibility;
- security;
- accessibility;
- performance;
- scalability;
- maintainability;
- portability;
- installability;
- backward compatibility;
- interoperability;
- usability.

## 9.3 Deliberately broken scenario projects

Keep the canonical self-hosted model clean and create separate teaching fixtures such as:

```text
examples/quarto-needs-scenarios/
├── missing-verification/
├── missing-evidence/
├── invalid-relation/
├── orphan-requirement/
├── overdue-adr/
├── localization-semantic-drift/
├── stale-source-module/
└── suspect-after-change/
```

Each scenario should explain the defect, diagnostic, graph consequence, and correction.

---

# Dependency order

The phases are deliberately ordered because later capabilities depend on earlier contracts:

```text
Executable tests + evidence ✅
          ↓
Git / PR change intelligence ← next
          ↓
Declarative policy over real evidence/change
          ↓
LSP authoring over stable semantics
          ↓
ReqIF / JSON-LD / OSLC interchange
          ↓
Architecture/C4 projections
          ↓
Graph workbench + scale hardening
```

C4 projection work can advance earlier where it only uses already-modeled architecture roles, but it must not fork the canonical model.

# Definition of success

Quarto-Needs reaches its intended shape when an engineering change can be authored, reviewed, executed, evidenced, compared, explained, visualized, and exchanged without any layer inventing a second interpretation of the project.