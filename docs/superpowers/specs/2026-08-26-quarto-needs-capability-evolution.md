# Quarto-Needs Capability Evolution Amendment

**Date:** 2026-08-26  
**Status:** Accepted in part — the decision and the architectural guardrails are
binding; the milestone sequence is committed only through the adoption arc below.
Milestones beyond it are candidate directions, re-evaluated once the tool has real users.  
**Amends:** `2026-08-25-quarto-needs-evolution-design.md`

## Decision

Quarto-Needs will pursue **capability parity and eventual capability leadership**
rather than source-syntax parity with Sphinx-Needs. Existing Sphinx projects may
later receive a migration adapter, but the primary authoring surface remains
Quarto-native: fenced `.need` blocks, shortcodes, configuration, Pandoc AST, and
precomputed deterministic projections.

This distinction matters. Sphinx-Needs has a mature directive, role, filtering,
layout, service, and builder ecosystem. Reproducing its syntax would couple this
project to Sphinx's document model and make it harder to exploit Quarto's
multi-format rendering, executable documents, dashboard support, and Pandoc
interoperability. Reproducing the useful capabilities behind that syntax keeps
the model portable and the user experience coherent.

## Capability benchmark

The comparison uses the current Sphinx-Needs documentation and adjacent
requirements-engineering tools as design inputs, not as compatibility promises.

| Capability | Reference implementations | Quarto-Needs now | Target |
|---|---|---|---|
| Typed requirements and configurable relations | [Sphinx-Needs configuration](https://sphinx-needs.readthedocs.io/en/latest/configuration.html), [ReqIF 1.2](https://www.omg.org/spec/ReqIF/1.2/) | Typed objects, relation catalog, inverse links, profiles | Type-specific schemas, inheritance, cardinality, and graph constraints |
| Lists, tables, charts, flow, sequence, Gantt, architecture and UML views | [Sphinx-Needs directives](https://sphinx-needs.readthedocs.io/en/latest/directives/index.html) | Cards, tables, flow, dashboard and inspector foundations | A coherent view catalog backed by one query engine and one projection |
| Imports and external services | [needimport](https://sphinx-needs.readthedocs.io/en/latest/directives/needimport.html), [needservice](https://sphinx-needs.readthedocs.io/en/latest/directives/needservice.html) | Local QMD catalog | Cached, provenance-preserving adapters with lock files and explicit trust policy |
| Declarative schema validation | [Sphinx-Needs schemas](https://sphinx-needs.readthedocs.io/en/latest/schema/) | Built-in rules, structured findings, JSON Schemas for artifacts | Per-type JSON Schema plus relation/network constraints and migration diagnostics |
| Dynamic values and variants | [Sphinx-Needs dynamic functions](https://sphinx-needs.readthedocs.io/en/latest/dynamic_functions.html) | Named safe queries and deterministic derived metrics | Safe declarative derived fields and build variants; no arbitrary code evaluation |
| Baseline, semantic diff and impact | IBM DOORS Next change and link workflows, [OpenFastTrace](https://github.com/itsallcode/openfasttrace/blob/main/doc/user_guide.md) | Canonical baseline, classified diff, relocation, union-graph impact paths | Interactive delta overlays, suspect links, review state and signed attestations |
| Review fingerprints | [Doorstop item reference](https://doorstop.readthedocs.io/en/v1.3/reference/items/) | Authored and semantic fingerprints | Link-level review fingerprints and explicit suspect-state propagation |
| Deep and transitive coverage | [OpenFastTrace design](https://github.com/itsallcode/openfasttrace/blob/main/doc/spec/design.md) | Scoped metrics and direct/transitive impact | Shallow/deep coverage, cycle/orphan/ambiguity analysis and path witnesses |
| Source-code traceability | [StrictDoc user guide](https://strictdoc.readthedocs.io/en/stable/stable/docs/strictdoc_01_user_guide.html), [OpenFastTrace](https://github.com/itsallcode/openfasttrace) | Planned QMD, comment and Python scanners | Stable scanner protocol, IDE navigation and language adapters after M4B |
| Interchange and federation | [ReqIF 1.2](https://www.omg.org/spec/ReqIF/1.2/), [OSLC RM 2.1](https://docs.oasis-open-projects.org/oslc-op/rm/v2.1/requirements-management-spec.html) | Deterministic JSON/CSV/SARIF/JUnit/Markdown | ReqIF export/import, then OSLC/JSON-LD federation with provenance |
| Authoring and round trip | [StrictDoc](https://github.com/strictdoc-project/strictdoc) | Source-controlled Quarto authoring | Optional structured editor only after lossless write-back and conflict semantics exist |

## What Quarto-Needs should surpass

### One analysis model, many trustworthy projections

All renderers, exporters, graphs, quality gates, diffs, and impact reports must
consume the same canonical analysis result. A visual view cannot silently apply
different filtering, relation orientation, or coverage rules from the CLI.

### Explainable change intelligence

The baseline engine is a product differentiator, not merely a regression tool.
The interactive graph should render added, removed, modified, and relocated
objects and relations directly, retain removed objects as clearly marked ghosts,
and explain every impacted node with the exact path and policy that selected it.
There is no opaque risk score unless its complete formula and inputs are exposed.

### Secure progressive enhancement

Interactive HTML uses a reduced public projection and locally vendored assets.
Static diagrams and accessible data tables preserve the essential information in
HTML without JavaScript, PDF, DOCX, EPUB, and other Quarto/Pandoc outputs. The
browser never receives bodies, paths, source locations, or undeclared attributes
unless the author explicitly publishes them.

### Determinism as a contract

Canonical order, pinned semantic inputs, stable schemas, atomic writes, and
byte-identical artifacts are release gates. Layouts with multiple valid graph
solutions use a stored seed and deterministic tie-breaking. Remote imports are
resolved through a lock file containing origin, version, content digest, and
retrieval policy.

### Requirements as linked data

The internal model should gradually align with ReqIF concepts and expose a
versioned JSON-LD projection without forcing either format on authors. OSLC
federation follows only after identity, access, cache, provenance, and conflict
semantics are explicit.

## Product sequence

Quarto-Needs is a community tool with no users yet. That single fact orders this
roadmap: the question is not "which capabilities match Sphinx-Needs" but "why
would someone try this, succeed with it, and stay". Capability leadership is a
consequence of adoption, not a path to it.

### Committed: the adoption arc

| Order | Milestone | Why it earns its place |
|---:|---|---|
| 1 | 4A — Exporters and CI | In flight. Makes results consumable by tooling people already run. |
| 2 | **4D — Distribution** | *New.* `quarto add`, a published package, and a quickstart that works in five minutes. Nobody can install this today; every capability below is unreachable until they can. |
| 3 | 4B — Source adapters | Requirements reaching real code and tests. This is what separates an engineering tool from a document tool, and it is the gap against OpenFastTrace and StrictDoc. |
| 4 | 5A — Interactive graph | The visible leap. It is what gets shown, shared, and remembered — and it makes the Milestone 3 change intelligence legible instead of theoretical. |
| 5 | 6C — View parity | Lists, tables, matrices, and charts over the one query engine. The daily-work bar a Sphinx-Needs user measures against. |

Then stop and reassess with real usage. Every choice after this point is better
informed by one user than by any competitive benchmark.

### Candidate, not committed

6A typed model, 6B review intelligence with signed attestations, 5B ReqIF, 7A
federation and OSLC, 7B language-server tooling.

These are deliberately deferred rather than dropped. Their common trait is that
they answer enterprise procurement questions — interchange formats, federation,
attestation — that no community user has asked yet. Two of them also depend on
conformance to specifications this project does not control (the OMG ReqIF 1.2
XSD plus an independent parser accepting the output; OSLC RM 2.1), which is where
schedules built on optimism usually fail.

5C hardening is not a milestone here. Security, accessibility, and performance
budgets are release gates that apply continuously — the guardrails below already
state that keyboard operation and non-JavaScript equivalence are acceptance
criteria, not later polish.

### What protects the deferred work

Deferring scope risks foreclosing it. The protection is the first guardrail
below — capability additions extend the canonical object/relation/finding model
before they add renderer-specific behavior — not a commitment to build
everything. A sound canonical model keeps 6A and 7A reachable; a long roadmap
does not.

## Architectural guardrails

- Capability additions extend the canonical object/relation/finding model before
  they add renderer-specific behavior.
- Queries, schemas, derived values, and variants use bounded declarative
  languages. They do not evaluate arbitrary Python, JavaScript, or Lua.
- External adapters are read-only by default, declare network requirements, use
  explicit allowlists, and preserve original identity plus provenance.
- A view declares which projection fields it needs. Projection construction
  fails closed when a requested field is not publishable.
- Graph limits produce a visible narrowing prompt; they never silently truncate.
- New schemas and artifact formats are versioned and receive golden, malformed,
  determinism, and migration tests.
- Interactive behavior is supplemental. Keyboard operation and an equivalent
  non-JavaScript representation are acceptance criteria, not later polish.
- Performance work is measured on synthetic sparse, dense, cyclic, and high-fanout
  graphs; no benchmark may depend only on the Aegis example.

## Success measures

- A user can answer “what changed, what is affected, and why?” from either CLI
  artifacts or the rendered book without conflicting results.
- The Aegis showcase exercises every supported exporter, scanner, graph mode,
  policy gate, and interchange format in CI.
- Public graph assets contain no denied field in adversarial fixtures.
- The static and interactive views identify the same object and relation sets.
- Every release reports compatibility, determinism, accessibility, security, and
  synthetic-graph performance results.

