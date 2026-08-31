# Quarto-Needs roadmap

Quarto-Needs is evolving from a requirements-as-code extension into an executable engineering knowledge graph for Git-based software development.

The roadmap is capability-oriented. It does **not** aim to reproduce another tool's syntax. Every capability must extend the canonical engineering model first; Quarto, the CLI, exporters, CI, editor tooling, and interactive HTML remain projections over that same semantic authority.

## North star

> Quarto-Needs is a requirements, architecture-decision, verification, evidence, change-intelligence, authoring, interoperability, and engineering-traceability engine built around a typed property graph, with Quarto as its executable documentation interface.

A mature project should answer, from the same canonical model: why a requirement exists; which decisions address it; where it is implemented; which tests verify it; which machine evidence proves those tests ran; what changed between Git states; what is impacted and through which path; what became suspect; which policies fail; how the model is authored safely in an editor; and how it is exchanged with external engineering tools.

## Architectural guardrails

1. **Python remains the semantic authority.** Lua, JavaScript, TypeScript, CI, editor clients, and interchange adapters consume projections rather than redefine semantics.
2. **One model, many projections.** CLI, Quarto, exporters, graph views, CI reports, LSP, ReqIF, JSON-LD, and future C4 views derive from the same analysis result.
3. **Requirements as code.** Human-authored intent remains text-first, versionable, diffable, and reviewable in Git.
4. **Evidence is distinct from assertion.** Verification intent, provider results, and attestations remain separate concepts.
5. **Authored data is distinct from computed projections.** Derived fields, variants, suspect state, indexes, and reports never masquerade as authored attributes.
6. **Change intelligence is explainable.** Impact carries explicit graph paths and policies rather than opaque scores.
7. **Interactive UI is progressive enhancement.** Static HTML, PDF, DOCX, and non-JavaScript users retain engineering information.
8. **External data is provenance-preserving.** Imports and federation preserve identity, origin, version/digest, trust, and retrieval policy.
9. **Declarative configuration is bounded.** User configuration does not execute arbitrary Python, Lua, JavaScript, or shell code.
10. **Interchange formats do not become the authoring model.** ReqIF, OSLC, JSON-LD, SARIF, and related formats remain adapters.
11. **Editor integrations remain thin.** Clients transport and present canonical semantics; they do not maintain a second parser or rule engine.
12. **Performance claims require measurement.** Scaling work is driven by reproducible benchmarks.

---

# Phase 1 — Executable verification and machine evidence ✅

**Status: implemented end to end.**

Delivered capabilities include reciprocal pytest bindings, deterministic provider evidence, provider-neutral check results, JUnit/coverage/Quarto/JSON-Schema/lint/type-check adapters, provenance-bearing `evidence-envelope-v1` attestations, graph/configuration fingerprints, source revision, timestamps, explicit expiry/freshness, and semantic evidence validation.

The self-hosted model exercises real executable bindings. EVD108/EVD109 protect the reciprocal contract between modeled test cases, requirements, and executable tests.

---

# Phase 2 — Git-native change intelligence and pull-request governance ✅

**Status: implemented end to end.**

Implemented capabilities include complete Git-state materialization, baseline/diff/impact analysis, suspect traceability, explicit impact witnesses, pull-request engineering reports, GitHub-oriented projections, deterministic annotations, and a real-change tutorial.

Git ranges are analyzed as complete engineering states; semantics are never inferred only from textual patches.

---

# Phase 3 — Declarative engineering policy engine ✅

**Status: implemented end to end.**

Implemented capabilities include bounded named policies, type-specific JSON Schema validation, graph constraints (`required-path`, `forbidden-cycle`, `connected`, `max-relations`), safe derived values, named variants, deterministic variant fingerprints, and explainable policy/constraint findings.

---

# Phase 4 — Authoring ergonomics: LSP and VS Code 🚧

## 4.1 Language Server Protocol ✅

**Status: implemented.**

The editor-independent `LanguageService` and stdio LSP provide canonical diagnostics, completion, hover, exact definition/references, document/workspace symbols, relation-aware rename, in-memory unsaved-buffer overlays, exact source indexing, localized-presentation handling, and collision-protected `WorkspaceEdit` refactors.

The LSP consumes the same parser, configuration, relation catalog, analyzer, policies, and graph semantics as the CLI.

## 4.2 Thin VS Code client 🟡

**Status: functionally implemented; release validation remains open.**

Already implemented:

- `vscode-languageclient` transport only; no TypeScript semantic fork;
- one server process per configured workspace folder;
- Quarto/Markdown `.qmd` document selection;
- configurable server executable/arguments;
- restart/output-channel commands;
- workspace/config synchronization;
- watcher-based start/stop when `.quarto-needs.toml` appears or disappears;
- architectural tests enforcing the thin-client boundary;
- Extension Host smoke fixture using `@vscode/test-electron`;
- VSIX packaging using `@vscode/vsce`;
- installation/package metadata;
- CI steps for install, type-check, compile, Extension Host smoke, VSIX packaging, and artifact upload.

Remaining release gates:

1. generate and commit a real npm `package-lock.json` rather than fabricating one;
2. obtain at least one real successful Actions execution of the TypeScript/Extension Host/VSIX pipeline.

Current GitHub Actions runs terminate before checkout with no job steps for both the Python matrix and VS Code job. That infrastructure condition is therefore not treated as a repository test failure or as successful release evidence.

---

# Phase 5 — Interchange, migration, and federation 🚧

## 5.1 ReqIF 1.2 ✅

**Status: functionally implemented and locally validated.** See `docs/phase-5-reqif.md` for the detailed contract.

Implemented and validated capabilities include deterministic ReqIF 1.2 projection, normative XSD validation, independent parser acceptance, stable identity mapping, loss semantics, deterministic XML output, and installed CLI export.

ReqIF import remains intentionally deferred until conflict policy, typed attribute recovery, provenance handling, and round-trip guarantees are designed explicitly.

## 5.2 JSON-LD 🟡

**Status: functionally implemented; independent processor execution remains an acceptance gate.** See `docs/phase-5-jsonld.md`.

Implemented capabilities include deterministic JSON-LD 1.1 projection, stable object/relation IRIs, embedded context, canonical relation semantics, authored attributes as `@json`, installed CLI export, deterministic writes, and independent PyLD/RDF verification hooks.

## 5.3 OSLC Requirements Management 🟡

**Status: read-only federation is implemented through discovery, query execution, independently provenance-bearing member observations, explicit reconciliation, and reviewed import planning; remote writes remain deferred.** See `docs/phase-5-oslc.md`.

Implemented capabilities include:

- conservative canonical requirement projection into OSLC RM resources;
- external URI identity and per-representation SHA-256 provenance;
- deterministic content-addressed cache with historical observations;
- explicit fresh/stale policy and offline fallback;
- bounded GET-only HTTP with timeout/byte/redirect/media limits;
- same-origin redirect enforcement and request-only credentials;
- network-free JSON-LD/Turtle/RDF/XML normalization with source and expanded-node budgets;
- RM Service / Query Capability discovery;
- OSLC Core Resource Shape parsing;
- named federation profiles inside `.quarto-needs.toml`;
- deterministic `oslc discover` CLI;
- bounded one-level Service Provider Catalog inspection;
- explicit Query Capability execution with member limits and query-response provenance;
- independently fetched query-member observations with per-resource digest, retrieval time, validators, and trust state;
- explicit URI-to-canonical-ID reconciliation with no heuristic identity merge;
- deterministic `oslc-reconciliation-v1`;
- deterministic, non-mutating `oslc-import-plan-v1` with explicit create/update/ignore/review directives;
- self-hosted EN/PT-BR requirements, ADRs, implementation modules, tests, and evidence through `TC-018` / `EVD-018`;
- ten representative executable tests in `make evidence-self-example` after the TC-018 slice;
- centralized validation of `[federation.oslc.profiles.*]` inside ordinary `load_config()`, with read-only connectivity kept outside the canonical configuration fingerprint.

Remaining 5.3 gates:

1. validate the current self-hosted evidence gate after every newly promoted OSLC test-case;
2. promote the import-plan regression into modeled `TC-019` / `EVD-019` only after local execution confirms it;
3. keep canonical import/apply and all POST/PUT/PATCH/DELETE operations deferred until staleness, conflict, authored-file placement, atomicity, rollback, optimistic concurrency, authorization, and audit contracts are explicit.

The terminal artifact for this phase is therefore a reviewable import plan, not automatic mutation.

## 5.4 Migration adapters ✅ (Sphinx-Needs)

**Status: the Sphinx-Needs adapter is implemented end to end — deterministic plan, reviewable non-mutating apply plan with a `.need` block content preview, and a create-only, atomic, rollback-protected `--write` step. Additional source adapters remain future work.** See `docs/phase-5-migration.md`.

Implemented capabilities include:

- Sphinx-Needs `needs.json` ingestion without executing a Sphinx project or arbitrary Python;
- deterministic source-version selection with explicit ambiguity failure;
- support for object-keyed and array need representations;
- source-ID recovery and duplicate-ID rejection;
- explicit source-type → Quarto-Needs-type mappings;
- explicit Sphinx link-field → canonical relation mappings;
- backlink exclusion as computed/inverse source data rather than duplicate authored authority;
- preservation of unmapped links and source-specific extra fields;
- explicit diagnostics for unmapped types, unmapped link fields, conditional links, and external targets;
- deterministic `sphinx-needs-migration-plan-v1`;
- installed `quarto-needs migrate sphinx-needs ...` CLI;
- ready-plan vs unresolved-plan exit semantics;
- regression coverage for parser, mappings, deterministic serialization, and CLI behavior;
- deterministic, non-mutating `migration-apply-plan-v1` covering destination-file selection/collision policy, canonical-ID collision checks against the current project, type/status validation against `.quarto-needs.toml`, and canonical relation/endpoint resolution;
- a source-provenance envelope (tool/project/version/source ID) carried through every apply-plan item;
- installed `quarto-needs migrate sphinx-needs ... --apply-plan` CLI producing a reviewable text/JSON diff, with ready/review-required/blocked status per item and matching exit-code semantics;
- deterministic, escaped rendering of each ready candidate into authored `.need` block text (`content_preview`), refusing to render (and blocking the item) whenever source content cannot round-trip through the grammar, verified against the real parser rather than the renderer's own assumptions; exposed in the CLI via `--show-content`;
- `quarto-needs migrate sphinx-needs ... --apply-plan --write`: create-only (an existing destination file refuses the whole write), atomic per file, all-or-nothing across files with real rollback (verified by forcing an OS-level failure on a later file and confirming an earlier one is deleted), post-write `scan`/`check` re-verification that rolls back on any new structural failure or error finding (verified by injecting a synthetic error), and a refusal-based idempotence contract — a rerun is refused, not silently duplicated, because the canonical IDs it would create already exist.

Next 5.4 slices:

1. add additional source-specific adapters such as StrictDoc, Doorstop, and OpenFastTrace, converging only at the shared migration-plan/apply-plan/write contracts;
2. an update/match identity contract, if migrating a *changed* upstream source onto an already-migrated project ever becomes a requirement — today an existing canonical ID is always a create-time collision, never an implicit update.

Sphinx-Needs remains one inspiration for Quarto-Needs as well as a supported migration source; compatibility claims are limited to the explicitly implemented adapter behavior.

## 5.5 External service adapters ⚪

Read-only/cacheable adapters may target GitHub issues or lifecycle-management systems. Every imported object must preserve external identity, origin, digest/version, retrieval policy, and trust state.

---

# Phase 6 — Architecture model and C4 projections ⚪

C4-like views must be **projections of the same engineering graph**, not a second architecture database.

Planned work includes actors/people, external systems, system boundaries, hierarchical software-system/container/component/code roles, interfaces/interactions, and generated System Context, Container, Component, and Code views. Dynamic/deployment projections follow only after the static hierarchy is stable.

Every architecture projection remains traceable to requirements, decisions, risks, implementation, tests, and evidence.

---

# Phase 7 — Interactive graph workbench ⚪

Extend Cytoscape from visualization into bounded engineering analysis: shortest paths, baseline/current comparison, affected-only views, semantic clustering, breadcrumbs, deep-linkable state, saved exploration state, fullscreen mode, SVG/PNG export, mini-map, keyboard navigation, and accessibility.

Interactive operations must consume published canonical semantics and bounded projections.

---

# Phase 8 — Scale, performance, compatibility, and release hardening ⚪

Maintain synthetic sparse/dense/cyclic/high-fanout corpora around 100, 1,000, 10,000, and 50,000+ objects where practical. Measure parsing, analysis, policies, queries, baseline/diff/impact, evidence, LSP latency, graph projection, export, and Quarto rendering.

Caching/incrementality is introduced only when benchmarks identify a real bottleneck. Release gates cover schema compatibility, determinism, migrations, accessibility, projection security, performance budgets, supported Python/Quarto versions, editor compatibility, interoperability, and self-hosted example health.

---

# Phase 9 — Teaching, self-hosting, and failure scenarios ⚪

`examples/quarto-needs/` increasingly acts as the official engineering model of Quarto-Needs itself. Significant features should update requirements/decisions/implementation/tests/evidence in the same change.

Target vertical slice:

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
deterministic provider result
    ↓
attestation + provenance/freshness
    ↓
Git change / review state
    ↓
editor navigation / safe refactor
    ↓
interchange / federation / migration projection
```

Deliberately broken teaching fixtures should cover missing evidence, invalid relations, orphan requirements, overdue decisions, localization drift, stale implementations/evidence, suspect-after-change, interchange loss, migration loss, and editor/refactor failures without contaminating the canonical self-hosted model.

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
Thin VS Code client 🟡 release validation
          ↓
ReqIF 1.2 ✅ → JSON-LD 🟡 → OSLC RM 🟡 → Sphinx-Needs migration ✅
          ↓
Broader migration / external federation
          ↓
Architecture / C4 projections
          ↓
Graph workbench
          ↓
Scale + compatibility + release hardening
```

C4 projection work may advance earlier when it only consumes already-modeled architecture roles, but it must never fork the canonical model.

# Definition of success

Quarto-Needs reaches its intended shape when an engineering change can be authored, reviewed, executed, evidenced, compared, explained, navigated, safely refactored, visualized, published, federated, migrated, and exchanged without any layer inventing a second interpretation of the project.
