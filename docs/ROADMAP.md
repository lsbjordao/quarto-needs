# Quarto-Needs roadmap

Quarto-Needs is evolving from a requirements-as-code extension into an executable engineering knowledge graph for Git-based software development.

The roadmap is capability-oriented. It does **not** aim to reproduce another tool's syntax. Every capability must extend the canonical engineering model first; Quarto, the CLI, exporters, CI, editor tooling, and interactive HTML remain projections over that same semantic authority.

## North star

> Quarto-Needs is a requirements, architecture-decision, verification, evidence, change-intelligence, authoring, and engineering-traceability engine built around a typed property graph, with Quarto as its executable documentation interface.

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
- What should an editor complete, diagnose, navigate, or safely refactor?
- How can this model be exchanged with external requirements and architecture tooling?

## Architectural guardrails

These are roadmap constraints, not optional polish.

1. **Python remains the semantic authority.** Lua, JavaScript, TypeScript, CI, and editor clients consume projections; they do not redefine relation, query, rule, impact, evidence, or coverage semantics.
2. **One model, many projections.** CLI, Quarto, exporters, graph views, CI reports, editor tooling, ReqIF, and JSON-LD must derive from the same analysis result.
3. **Requirements as code.** Human-authored engineering intent remains text-first, versionable, diffable, and reviewable in Git.
4. **Evidence is distinct from assertion.** Test declarations describe verification intent; deterministic providers record execution; attestations bind provider results to a concrete engineering state.
5. **Authored data is distinct from computed projections.** Derived fields, variants, suspect state, editor indexes, and reports never masquerade as authored attributes.
6. **Change intelligence is explainable.** Impact always carries explicit paths and policies. No opaque score replaces graph explanation.
7. **Interactive UI is progressive enhancement.** Static HTML, PDF, DOCX, and non-JavaScript users retain equivalent engineering information.
8. **External data is provenance-preserving.** Imports are read-only by default, versioned, digestible, and explicit about trust and origin.
9. **Declarative configuration is bounded.** User-defined policies, queries, constraints, derived fields, and variants never evaluate arbitrary Python/Lua/JavaScript/shell code.
10. **Interchange formats do not become the authoring model.** ReqIF, OSLC, JSON-LD, SARIF, and other formats are adapters around the canonical graph.
11. **Editor integrations remain thin.** LSP clients may present or transport semantics but must not maintain a second parser or rule engine.
12. **Performance is measured.** Scaling claims require synthetic sparse, dense, cyclic, and high-fanout benchmarks.

---

# Phase 1 — Executable verification and machine evidence ✅

**Status: implemented end to end on the current development branch.**

Implemented contracts include:

- reciprocal pytest markers with stable node IDs;
- deterministic `evidence-pytest-v1` provider output;
- provider-neutral `evidence-checks-v1`;
- adapters for JUnit XML, coverage.py JSON, Quarto render, JSON Schema, lint, and type-check results;
- `evidence-envelope-v1` attestations with digest, graph/configuration fingerprints, timestamps, optional source revision, and explicit expiry;
- semantic evidence validation against requirements, test cases, evidence objects, provider compatibility, and graph relations;
- self-hosted executable evidence with six real pytest bindings.

The architecture deliberately separates authored verification intent, deterministic provider output, and provenance-bearing attested proof.

---

# Phase 2 — Git-native change intelligence and pull-request governance ✅

**Status: implemented end to end on the current development branch.**

## 2.1 Git-range analysis ✅

```bash
quarto-needs diff --git BASE..HEAD
quarto-needs impact --git BASE..HEAD
```

Both refs are materialized with `git archive`, analyzed as complete engineering states under a common deterministic reference epoch, and never mutate the working tree. Archive extraction rejects unsafe paths and escaping symlinks.

## 2.2 Suspect traceability ✅

`quarto-needs suspect --git BASE..HEAD` derives review claims from canonical impact witnesses. Suspect state is not persisted as an opaque boolean.

## 2.3 Pull-request engineering report ✅

`pr-report --git` composes diff, impact, suspect claims, findings, gate regressions, changed/affected semantic groups, and explicit paths into stable JSON/Markdown review surfaces.

## 2.4 GitHub projections ✅

`github-report --git` produces step-summary Markdown, escaped workflow annotations, and structured conclusions without making GitHub semantic authority.

## 2.5 Real change tutorial ✅

The self-hosted Change chapter uses the actual margin-TOC positioning fix and a reproducible semantic-model Git range.

---

# Phase 3 — Declarative engineering policy engine ✅

**Status: implemented end to end on the current development branch.**

## 3.1 User-defined policies ✅

Bounded `[policies.*]` declarations compose safe named-query scopes, canonical relations, target roles, cardinality, and severity. Violations use `POLICY:<NAME>` findings.

## 3.2 Type schemas ✅

Per-type `attribute-schema` uses JSON Schema Draft 2020-12 over canonical authored attributes. Violations emit `OBJ002`. Remote references are rejected and no implicit type coercion is performed.

## 3.3 Graph constraints ✅

Bounded `[constraints.*]` currently implements:

- `required-path`;
- `forbidden-cycle`;
- `connected`;
- `max-relations`.

Violations use `CONSTRAINT:<NAME>` and include explicit witnesses/targets where appropriate.

## 3.4 Safe derived fields and variants ✅

Derived values are stored separately from authored `attributes`. Initial bounded operations are `relation-count` and `path-exists`.

Named variants start from safe queries and may expand over explicit canonical relation sets to bounded depth. Variant membership remains a selection over the one canonical graph and receives a `variantFingerprint` bound to the final semantic graph.

```bash
quarto-needs variant list
quarto-needs variant show assurance-slice
quarto-needs variant show assurance-slice --format json
```

The self-hosted model dogfoods `verification-count`, `has-evidence-path`, and `assurance-slice`.

---

# Phase 4 — Authoring ergonomics: LSP and VS Code 🚧

**Status: Phase 4.1 implemented; Phase 4.2 in active implementation.** Authoring improvements must consume the stable parser/configuration/catalog rather than create editor-specific semantics.

## 4.1 Language Server Protocol ✅

Quarto-Needs now exposes a dependency-free stdio LSP transport over an editor-independent `LanguageService`:

```bash
quarto-needs --root /path/to/project lsp
```

Implemented capabilities:

- diagnostics projected from canonical structural, lifecycle, relation, policy, schema, and graph-constraint findings;
- context-aware completion for configured types, type-specific statuses, relation names, and relation targets filtered by endpoint policy;
- hover with engineering metadata and derived values;
- exact go-to-definition across `.qmd` sources;
- exact semantic references/backlinks;
- relation-aware `prepareRename` and `rename` with collision protection;
- document symbols and workspace symbols;
- full-document open/change/save/close synchronization;
- in-memory unsaved-buffer overlays through the canonical parser/analyzer;
- retention of the last valid semantic graph while transient structural findings are exposed during incomplete edits;
- exact source spans for declarations, relation attributes, scalar/list relation metadata, and `need` shortcodes;
- localized presentation siblings included in identity refactors without becoming a second canonical graph.

The LSP server returns standard `WorkspaceEdit` values for refactors and never writes editor buffers or rename results directly to source files.

## 4.2 VS Code extension 🚧

A first thin multi-root client now lives in `editors/vscode/`.

Implemented foundation:

- `vscode-languageclient` transport only; no parser, relation catalog, rule engine, or graph implementation in TypeScript;
- one language-server process per workspace folder containing `.quarto-needs.toml`;
- `.qmd` document selection for both Quarto and Markdown language IDs;
- configurable `quartoNeeds.server.command` and extra server arguments;
- restart and output-channel commands;
- automatic resynchronization when workspace folders or server configuration change;
- Python regression tests that enforce the thin-client architectural boundary;
- independent CI TypeScript check/compile job.

Next hardening before calling 4.2 complete:

- package-lock/reproducible Node dependency installation;
- VS Code extension-host smoke tests;
- packaging (`vsix`) and installation documentation;
- clearer handling of workspace folders that gain or lose `.quarto-needs.toml` after activation;
- optional UI conveniences only when they can be implemented as LSP/projection consumers rather than new semantics.

Candidate later conveniences include traceability peek, graph preview for the focused object, quality-gate status, baseline/change indicators, and safe quick fixes.

---

# Phase 5 — Interchange, migration, and federation

## 5.1 ReqIF

Implement ReqIF 1.2 export first, validated against the normative XSD and at least one independent parser. Add import only after identity, rich-text, attribute-definition, relation, and round-trip loss semantics are explicit.

## 5.2 JSON-LD

Expose a versioned JSON-LD projection of the canonical graph so stable identities, typed objects, and relations are available to linked-data tooling without making RDF the internal storage model.

## 5.3 OSLC Requirements Management

Add OSLC RM federation only after authentication, caching, provenance, identity, conflict, and offline behavior have explicit contracts.

## 5.4 Migration adapters

Provide optional import/migration paths for established docs-as-code ecosystems, including Sphinx-Needs, while keeping Quarto-native authoring as the primary interface.

## 5.5 External service adapters

Read-only, cacheable adapters may target systems such as GitHub issues or lifecycle-management services. Every imported object must preserve origin, stable external identity, digest/version, retrieval policy, and trust status.

---

# Phase 6 — Architecture model and C4 projections

The goal is not to maintain a second architecture model. C4-like views should be **projections of the same engineering graph**.

Planned work:

- actors/people, external systems, system boundaries, and interactions;
- hierarchical architecture roles corresponding to software systems, containers/subsystems, components, interfaces, and code/source modules;
- generated System Context, Container/subsystem, Component, and Code views;
- dynamic/deployment projections only after the static hierarchy is stable.

Every view must remain traceable back to requirements, decisions, risks, tests, and evidence.

---

# Phase 7 — Interactive graph workbench

Extend Cytoscape from visualization into a controlled engineering-analysis workbench.

Planned capabilities include:

- shortest path between two objects;
- baseline/current visual comparison;
- show-only-affected mode;
- clustering by semantic role, layer, component, or configured attribute;
- exploration breadcrumbs;
- deep-linkable focus/view/filter state;
- saved exploration state;
- fullscreen exploration;
- SVG/PNG export;
- mini-map for large projections;
- richer keyboard navigation and accessibility.

All interactive operations must consume published relation semantics and bounded projections.

---

# Phase 8 — Scale, performance, compatibility, and release hardening

## 8.1 Synthetic benchmark corpus

Maintain projects around 100, 1,000, 10,000, and 50,000+ objects where practical, across sparse, dense, cyclic, and high-fanout graph shapes.

Measure parsing, analysis, rule/policy evaluation, queries, baseline/diff/impact, source indexing/LSP latency, graph projection, export, and Quarto render cost.

## 8.2 Incremental analysis

Introduce caching/incrementality only when benchmarks demonstrate a real bottleneck. Cache keys must include every semantic input and remain safe under configuration/catalog changes.

## 8.3 Release gates

Every release should report or test schema compatibility, deterministic outputs, migration behavior, accessibility, public-projection security, performance budgets, supported Python/Quarto versions, editor-client compatibility, and self-hosted example health.

---

# Phase 9 — Teaching, examples, and failure scenarios

## 9.1 Self-hosted model

`examples/quarto-needs/` should increasingly be the official engineering model of Quarto-Needs itself. Significant product changes should update the relevant engineering objects in the same pull request as code and tests.

The target vertical slice is:

```text
stakeholder need
    ↓
requirement
    ↓
architecture decision
    ↓
architecture element
    ↓
source module
    ↓
modeled test
    ↓
executable test / machine check
    ↓
deterministic provider evidence
    ↓
attestation + provenance/freshness
    ↓
Git change / review state
    ↓
editor navigation / safe refactor
```

## 9.2 Quality attributes

Expand claims only when verification exists. Candidate attributes include determinism, reproducibility, security, accessibility, performance, scalability, maintainability, portability, installability, backward compatibility, interoperability, and usability.

## 9.3 Deliberately broken scenarios

Keep the canonical model clean and create separate teaching fixtures for missing verification/evidence, invalid relations, orphan requirements, overdue ADRs, localization semantic drift, stale source modules, suspect-after-change, and editor/refactor failures.

---

# Dependency order

```text
Executable tests + evidence ✅
          ↓
Git / PR change intelligence ✅
          ↓
Declarative policy + schemas + constraints + variants ✅
          ↓
LSP semantic authoring ✅
          ↓
Thin VS Code client 🚧
          ↓
ReqIF / JSON-LD / OSLC interchange
          ↓
Architecture/C4 projections
          ↓
Graph workbench + scale hardening
```

C4 projection work can advance earlier where it only uses already-modeled architecture roles, but it must not fork the canonical model.

# Definition of success

Quarto-Needs reaches its intended shape when an engineering change can be authored, reviewed, executed, evidenced, compared, explained, navigated, safely refactored, visualized, and exchanged without any layer inventing a second interpretation of the project.
