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

**Status: implemented end to end on the current development branch.** Phase 1 closes the gap between authored traceability and executable proof while preserving deterministic provider output separately from volatile provenance/freshness metadata.

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

The self-hosted example now has six real executable bindings covering multilingual parity, architecture-decision governance, public graph safety, named views, baseline/change intelligence, and the margin-TOC engineering slice.

`make evidence-self-example` executes the real pytest nodes, writes deterministic provider output, creates a 24-hour attestation bound to the current engineering snapshot, and validates that attestation. `render-self-example` depends on this flow, so stale, incomplete, tampered, expired, or semantically inconsistent evidence blocks the executable case study.

### Phase 1 hardening that remains compatible with the completed architecture

Phase 1 is functionally complete. Later work may still add more provider adapters, signatures/SLSA-style provenance, stronger repository revision discovery outside CI, provider-specific richer details, and additional self-hosted evidence bindings without changing the established payload/envelope separation.

---

# Phase 2 — Git-native change intelligence and pull-request governance ✅

**Status: implemented end to end on the current development branch.** Git ranges and pull requests are now first-class consumers of the canonical baseline/diff/impact engine.

## 2.1 Git-range analysis ✅

Implemented commands:

```bash
quarto-needs diff --git BASE..HEAD
quarto-needs impact --git BASE..HEAD
```

Both refs are materialized with `git archive`, analyzed as complete engineering states, and evaluated under the head commit's deterministic reference epoch. The working tree is never mutated. Archive extraction rejects unsafe paths and symlinks escaping the materialized tree.

## 2.2 Suspect traceability ✅

`quarto-needs suspect --git BASE..HEAD` derives suspect review claims from the canonical impact report. Claims include origin, change classification, semantic role, distance, explicit path, relation sequence, and a human-readable witness. Suspect state is never persisted as an opaque boolean.

## 2.3 Pull-request engineering report ✅

`quarto-needs pr-report --git BASE..HEAD` composes canonical diff, impact, and suspect reports and groups changed/affected requirements, decisions, architecture elements, source modules, tests, evidence, findings, gate regressions, and explicit impact paths.

Stable JSON and Markdown projections are available for automation and review.

## 2.4 GitHub annotations and checks ✅

`quarto-needs github-report --git BASE..HEAD` projects the canonical report into GitHub-compatible step-summary Markdown, safely escaped workflow annotations, and a structured check conclusion. GitHub remains a consumer: no GitHub API call exists in the semantic core.

The PR quality workflow fetches complete history, creates the Git-native report, appends the summary to `$GITHUB_STEP_SUMMARY`, and emits annotations with least-privilege permissions.

## 2.5 Real change tutorial ✅

The self-hosted Change chapter uses the real margin-TOC positioning fix as the historical product change and a reproducible semantic-model Git range for `diff`, `impact`, `suspect`, `pr-report`, and `github-report` demonstrations.

The complete modeled slice is:

```text
SYS-002 → FUN-009 → ADR-007 → COMP-EXTENSION → SRC-MARGIN-SIDEBAR → TC-014 → EVD-014
```

---

# Phase 3 — Declarative engineering policy engine ✅

**Status: implemented end to end on the current development branch.** Phase 3 adds bounded project-defined engineering semantics without arbitrary code execution. Policies, schemas, constraints, derived fields, and variants are canonical configuration inputs and therefore participate in reproducibility/fingerprint contracts.

## 3.1 User-defined rules ✅

A bounded `[policies.*]` DSL composes named-query scopes, canonical relation semantics, target roles, minimum cardinality, and severity:

```toml
[policies.NFR_REQUIRES_TEST]
scope = "approved-nfr"
assert-relation = "verified-by"
target-role = "verification"
minimum = 1
severity = "error"
```

Violations are normal findings with codes `POLICY:<NAME>`. Direct and inverse relation authoring resolve through the canonical relation catalog. Unknown keys, relations, invalid cardinalities, unsupported severities, and invalid scopes fail deterministically.

## 3.2 Type schemas ✅

Per-type `attribute-schema` supports JSON Schema Draft 2020-12 over the canonical authored attribute representation. Schema violations emit deterministic `OBJ002` findings and can participate in ordinary rule severity configuration.

Remote `$ref` values are rejected; local `#...` references are accepted. Quarto-Needs does not perform implicit type coercion solely to satisfy a schema.

## 3.3 Graph constraints ✅

A bounded `[constraints.*]` DSL implements graph invariants that go beyond the simple endpoint/cardinality rules already available under `[relations]`:

- `required-path`;
- `forbidden-cycle`;
- `connected`;
- `max-relations`.

Violations use `CONSTRAINT:<NAME>` findings. Constraints consume canonical relation/inverse semantics and safe named-query scopes. The self-hosted model requires every approved requirement to reach evidence through `verified-by → evidenced-by`.

## 3.4 Safe derived fields and variants ✅

Derived values are stored separately from authored `attributes`. The first bounded operations are:

- `relation-count`;
- `path-exists`.

Definitions are part of the canonical configuration fingerprint; materialized values participate in the semantic graph fingerprint when present.

Named build variants start from a safe query and may expand over an explicit canonical relation set to a bounded depth. Membership remains a projection over the one canonical graph and receives a `variantFingerprint` bound to the final semantic graph.

CLI projection:

```bash
quarto-needs variant list
quarto-needs variant show assurance-slice
quarto-needs variant show assurance-slice --format json
```

The self-hosted model dogfoods `verification-count`, `has-evidence-path`, and `assurance-slice`.

---

# Phase 4 — Authoring ergonomics: LSP and VS Code

**Status: next major implementation phase.** Phase 4 should improve authoring without creating a second parser or semantic engine.

## 4.1 Language Server Protocol

Implement an LSP over the same parser/configuration/catalog used by the CLI.

Capabilities:

- completion for IDs, types, statuses, relations, and configured attributes;
- diagnostics for unknown IDs, endpoint violations, lifecycle errors, policies, schemas, and graph constraints;
- hover with engineering metadata, derived values, and coverage;
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
Git / PR change intelligence ✅
          ↓
Declarative policy + schemas + constraints + variants ✅
          ↓
LSP authoring over stable semantics ← next
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
