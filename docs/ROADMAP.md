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

Implemented and validated capabilities include:

- deterministic ReqIF 1.2 projection from the canonical `AnalysisSnapshot`;
- normative ReqIF 1.2 XSD validation using the official OMG schema;
- independent parsing through the test-only Python `reqif` implementation;
- explicit distinction between ReqIF specification revision `1.2` and the normative `REQ-IF-VERSION` header value `1.0`;
- deterministic XML-ID-safe ReqIF identifiers with authored Quarto-Needs IDs retained as explicit canonical attributes;
- documented identity mapping, attribute mapping, relation mapping, and loss semantics;
- deterministic byte output and XML escaping;
- installed CLI support through `export --format reqif` with `.quarto-needs/requirements.reqif` as the default output.

ReqIF import remains intentionally deferred until conflict policy, typed attribute recovery, provenance handling, and round-trip guarantees are designed explicitly.

Repository-level CI confirmation remains blocked by the external Actions runner condition, but local normative and independent-parser acceptance gates have passed.

## 5.2 JSON-LD 🟡

**Status: functionally implemented; independent processor execution pending local validation.** See `docs/phase-5-jsonld.md`.

Implemented capabilities include:

- deterministic JSON-LD 1.1 projection from the canonical `AnalysisSnapshot`;
- one graph node plus typed engineering-object and relation nodes;
- stable object IRIs and deterministic relation IRIs;
- versioned public vocabulary namespace `urn:quarto-needs:v1:` with an explicit breaking-change policy;
- embedded context with no remote-context runtime dependency;
- canonical relation name, authored name, semantic family, roles, impact direction, source, and target preservation;
- authored attributes represented as JSON-LD 1.1 `@json` values;
- installed CLI support through `export --format jsonld` with `.quarto-needs/graph.jsonld` as the default output;
- deterministic output and atomic writes;
- test-only independent JSON-LD 1.1 processing through PyLD;
- RDF/N-Quads verification that canonical relation endpoints survive projection.

Remaining 5.2 acceptance gate: execute `tests/test_export_jsonld.py` and `tests/test_interchange_cli.py` successfully in a real local environment with refreshed test dependencies. If those pass, 5.2 is complete independently of the still-broken Actions runner.

## 5.3 OSLC Requirements Management ⚪

Federation begins only after authentication, caching, provenance, identity, conflict, offline behavior, and trust boundaries have explicit contracts.

The first OSLC slice should be **read-only and projection-first**: define canonical resource identity, local-to-external URI mapping, provenance/trust metadata, shape discovery, cache/digest policy, and failure behavior before adding network writes or synchronization.

## 5.4 Migration adapters ⚪

Provide optional import/migration paths for established requirements/docs-as-code ecosystems, including **Sphinx-Needs as one of the inspirations and migration sources**, while retaining Quarto-native authoring as the primary interface.

Migration adapters must preserve original identity/provenance and emit explicit diagnostics for information that cannot be represented canonically.

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
interchange projection
```

Deliberately broken teaching fixtures should cover missing evidence, invalid relations, orphan requirements, overdue decisions, localization drift, stale implementations/evidence, suspect-after-change, interchange loss, and editor/refactor failures without contaminating the canonical self-hosted model.

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
ReqIF 1.2 ✅ → JSON-LD 🟡 → OSLC / migration / federation
          ↓
Architecture / C4 projections
          ↓
Graph workbench
          ↓
Scale + compatibility + release hardening
```

C4 projection work may advance earlier when it only consumes already-modeled architecture roles, but it must never fork the canonical model.

# Definition of success

Quarto-Needs reaches its intended shape when an engineering change can be authored, reviewed, executed, evidenced, compared, explained, navigated, safely refactored, visualized, published, and exchanged without any layer inventing a second interpretation of the project.
