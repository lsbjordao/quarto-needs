# Quarto-Needs

Quarto-Needs is a **requirements-as-code and engineering-traceability engine for Quarto**. It turns engineering objects authored in `.qmd` files into a deterministic typed property graph, applies validation and governance, computes coverage and change impact, and projects the same engineering model into Quarto documentation, CLI reports, CI artifacts, and interactive graph views.

> **Status:** pre-1.0 and under active development. The architecture is already substantially beyond the original MVP: the Python core is the semantic authority and Quarto is the executable documentation interface.

## North star

> Quarto-Needs is a requirements, architecture-decision, verification, evidence, change-intelligence, and engineering-traceability engine built around a typed property graph, with Quarto as its executable documentation interface.

The goal is not only to publish requirements. A mature Quarto-Needs project should be able to answer:

- why a requirement exists;
- which decisions address it;
- where it is implemented;
- which tests verify it;
- which evidence supports the verification claim;
- what changed between two engineering states;
- what is affected by a change and through which explicit path;
- which governance policies or quality gates are violated.

## Architecture

```text
QMD / configuration / code / tests / evidence
                    │
                    ▼
             Quarto-Needs Core
 parser → analysis → typed graph → rules/query → snapshot
                    │
        ┌───────────┼───────────────┐
        ▼           ▼               ▼
      CLI/CI   machine exports   graph projections
                                    │
                                    ▼
                              Quarto extension
                              HTML/PDF/DOCX
```

The canonical model is a property graph of typed engineering objects and typed relations. Python owns relation semantics, validation, queries, coverage, fingerprints, baseline/diff/impact, evidence validation, and public projections. Lua and JavaScript consume those projections and do not redefine engineering meaning.

## Current capabilities

- configurable engineering object types, prefixes, roles, lifecycles, and required attributes;
- canonical relation catalog with direct/inverse labels, semantic families, endpoint roles, impact direction, and traversal direction;
- requirements, risks, tests, evidence, architecture elements, and first-class Architecture Decision Records;
- deterministic canonical snapshots and fingerprints;
- structural validation, configurable rules, named queries, coverage metrics, and quality gates;
- baselines, semantic diff, relocation detection, and explainable union-graph impact analysis;
- JSON, CSV, SARIF, JUnit, and Markdown exporters;
- an opt-in pytest integration with reciprocal requirement/test-case markers and deterministic `evidence-pytest-v1` output;
- a provider-neutral `evidence-checks-v1` contract with adapters for JUnit XML, coverage.py JSON, Quarto render results, JSON Schema validations, lint, and type-check results;
- provider-neutral evidence attestations with SHA-256 payload digests, graph/configuration fingerprints, optional Git revision, generation time, explicit expiry, and `quarto-needs evidence attest` / `evidence check` workflows;
- semantic evidence validation against modeled requirements, test cases, and evidence objects, including provider compatibility and reciprocal verification/evidence relations;
- Quarto cards, cross-references, tables, lists, matrices, dashboards, inspectors, Mermaid flows, and graph views;
- bounded public graph projections with deny-by-default provenance;
- progressive interactive Cytoscape exploration with semantic traversal, filters, root paths, collapse/expand, and edge inspection;
- optional collapsible Quarto margin TOC through the extension;
- bilingual English / Brazilian Portuguese presentation with semantic-parity validation;
- a self-hosted executable engineering case study in `examples/quarto-needs/`.

## Repository layout

```text
src/quarto_needs/              Python semantic core
_extensions/quarto-needs/     Quarto filters, shortcodes and browser assets
schemas/                       Versioned artifact schemas
tools/                         Pre-render and release tooling
docs/manual/                   Quarto-Needs manual
docs/ROADMAP.md                Accepted product roadmap
examples/book/                 Aegis IAM external-domain showcase
examples/quarto-needs/         Self-hosted engineering model
tests/                         Regression and integration tests
.github/workflows/             CI workflows
```

## Quick start

For an end-user path, start with [`docs/quickstart.md`](docs/quickstart.md).

For contributor development:

```bash
make setup
source .venv/bin/activate
make test
```

Build and validate a project:

```bash
quarto-needs scan
quarto-needs check
quarto-needs quality
quarto-needs coverage
quarto-needs trace SYS-REQ-042
```

Create and compare an engineering baseline:

```bash
quarto-needs baseline create
quarto-needs diff baselines/quarto-needs.json
quarto-needs impact baselines/quarto-needs.json
```

Generate deterministic pytest evidence, attest it against the current engineering state, and validate the attestation:

```bash
pytest --quarto-needs-evidence=.quarto-needs/evidence/pytest-provider.json
quarto-needs evidence attest \
  .quarto-needs/evidence/pytest-provider.json \
  --output .quarto-needs/evidence/pytest.json \
  --expires-hours 24
quarto-needs evidence check .quarto-needs/evidence/pytest.json
```

Raw provider payloads remain directly checkable for backward-compatible or local workflows, but attestations are the preferred CI/review artifact when freshness and provenance matter.

Preview the self-hosted case study:

```bash
make check-self-example
make evidence-self-example
make render-self-example
make preview-self-example
```

## Authoring syntax

Quarto-Needs uses Quarto/Pandoc-native fenced divs:

```qmd
::: {.need #SYS-REQ-042 type="system-requirement" status="approved" priority="high" derives-from="STK-NEED-003" verified-by="TC-AUTH-012"}
## Authentication

The system shall authenticate the user before allowing access to private data.

### Rationale
Authentication protects private data from unauthorized access.
:::
```

The relation direction is semantic: the system requirement **derives from** the stakeholder need. Presentation or traversal may read the engineering process in the opposite direction, but the canonical stored relation remains authoritative.

Cross-reference an object with:

```qmd
{{< need SYS-REQ-042 >}}
{{< need SYS-REQ-042 title=true >}}
```

## Executable verification and machine evidence

Quarto-Needs separates verification intent, provider output, and attested proof. A modeled `test-case` may bind to a stable pytest node ID while the executable test carries reciprocal markers:

```python
@pytest.mark.requirement("FUN-004")
@pytest.mark.quarto_need_test_case("TC-010")
def test_graph_exploration_assets():
    ...
```

The pytest plugin emits deterministic `evidence-pytest-v1` output. A second provider-neutral contract, `evidence-checks-v1`, normalizes machine checks from JUnit XML, coverage.py, Quarto render, JSON Schema, lint, and type-check tooling. Generic checks can explicitly reference modeled `requirements`, `testCases`, and `evidenceObjects`.

Volatile provenance is deliberately kept out of deterministic provider payloads. `quarto-needs evidence attest` wraps either supported payload in `evidence-envelope-v1`, recording:

- the provider and provider version;
- a SHA-256 digest of the embedded provider payload;
- the current configuration, semantic-graph, and representation fingerprints;
- generation time;
- optional source/Git revision;
- optional explicit expiry.

`quarto-needs evidence check` dispatches by artifact schema and validates both the envelope and provider semantics. For pytest it verifies executable outcome, modeled test-case identity, `pytest-nodeid`, reciprocal requirement↔test claims, and completeness of modeled executable bindings. For generic checks it verifies outcomes, referenced requirements/test cases/evidence objects, verification/evidence relations, and provider compatibility declared by modeled evidence objects. Attested artifacts additionally fail on digest tampering, graph/configuration drift, revision mismatch when a current revision is available, future timestamps, or expiry.

See [`docs/manual/executable-evidence.qmd`](docs/manual/executable-evidence.qmd) and [`docs/manual/evidence-providers.qmd`](docs/manual/evidence-providers.qmd).

## Generated views

The Quarto extension consumes the canonical graph and precomputed projections. Common views include:

```qmd
{{< need-table types="functional-requirement;non-functional-requirement" status="approved" >}}
{{< need-list tags="authentication" >}}
{{< need-count types="system-requirement" status="approved" >}}
{{< need-matrix rows="functional-requirement" columns="test-case" relation="verified-by" >}}
{{< need-flow root="STK-001" depth="4" relations="derives-from;implemented-by;verified-by" >}}
{{< need-backlinks SYS-001 >}}
{{< need-dashboard >}}
{{< need-inspector SYS-001 >}}
{{< need-graph view="graph-exploration" >}}
```

Named queries are evaluated by Python and materialized for presentation clients. Browser code does not implement a second query language.

## Configuration

Governed projects use `.quarto-needs.toml`. A compact example:

```toml
profile = "strict"

[types.functional-requirement]
id-prefix = "FUN-"
role = "requirement"
required-attributes = ["priority", "tags"]
allowed-statuses = ["draft", "in-review", "approved", "deprecated"]

[relations."verified-by"]
allowed-source-types = ["functional-requirement"]
allowed-target-types = ["test-case"]
minimum-per-source = 1

[queries.approved-high]
all = [
  { field = "type", op = "eq", value = "functional-requirement" },
  { field = "status", op = "eq", value = "approved" },
  { field = "priority", op = "in", values = ["high", "critical"] },
]

[gates]
scope = "approved-requirements"
max-errors = 0
min-implementation-trace = 100.0
min-verification-successful = 100.0
min-evidence = 100.0
```

Configuration is declarative and bounded. Unknown keys and malformed values fail fast rather than being silently ignored.

## Baseline, diff, and impact

A baseline captures the authored engineering state, configuration fingerprint, semantic graph fingerprint, findings, and derived report surfaces. `diff` classifies changes such as added/removed objects, modified fields, relation changes, and relocation. `impact` traverses the **union of baseline and current graphs**, so removed objects and links remain explainable.

Impact results carry explicit paths and distance. Quarto-Needs deliberately avoids an opaque risk score when the graph path itself is the more auditable explanation.

## Interchange and CI

Current exporters include:

| Format | Purpose |
|---|---|
| JSON | Canonical graph projection |
| CSV | Objects, relations, and findings for tabular consumers |
| SARIF | Findings for code-scanning compatible tooling |
| JUnit | Quality gates represented as test cases |
| Markdown | Human-readable CI / pull-request summary |

Machine evidence additionally uses versioned pytest, generic-check, and attestation schemas. ReqIF, JSON-LD, OSLC federation, Git-native PR intelligence, LSP/editor tooling, C4-derived architecture views, and deeper graph-workbench capabilities remain on the accepted roadmap.

See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Self-hosted engineering model

`examples/quarto-needs/` uses Quarto-Needs to model Quarto-Needs itself. It connects stakeholder needs, system and functional/non-functional requirements, ADRs, components/interfaces, risks, real source modules, modeled tests, executable pytest tests, and evidence. English is canonical and Brazilian Portuguese is presentation-only localization over the same semantic model.

Five representative modeled test cases bind to real pytest functions and are executed by `make evidence-self-example`: architecture-decision governance, multilingual semantic parity, public graph safety, named graph views, and baseline/diff/impact. The target first writes deterministic provider output, then creates a 24-hour attestation bound to the current engineering snapshot, and finally validates that attestation. `render-self-example` depends on this complete flow.

The target is increasingly complete executable traceability:

```text
stakeholder need
       ↓
requirement
       ↓
architecture decision
       ↓
architecture element
       ↓
real source module
       ↓
modeled test-case
       ↓
executable test / machine check
       ↓
deterministic provider evidence
       ↓
attestation + provenance/freshness
       ↓
Git change / review state
```

The Aegis IAM showcase remains separately available in `examples/book/` as proof that Quarto-Needs also works outside its own development domain.

## Inspirations and related work

Quarto-Needs has its own Quarto/Pandoc-native architecture, but it is informed by several mature ideas and ecosystems:

- **Sphinx-Needs** — one of the original inspirations for treating requirements and engineering objects as first-class documentation entities with typed links, generated views, filtering, and validation. Quarto-Needs intentionally pursues capability inspiration rather than Sphinx syntax compatibility.
- **Requirements as Code / Docs as Code** — text-first, Git-versioned, reviewable engineering artifacts as the primary workflow.
- **Architecture Decision Records (ADRs)** — durable architectural rationale represented explicitly instead of being hidden in prose or commit history.
- **C4 model** — inspiration for hierarchical architecture projections such as system context, container/subsystem, component, and code views; Quarto-Needs aims to derive such views from the same engineering graph rather than maintain a parallel architecture model.
- **ReqIF** — inspiration and future interchange boundary for structured requirements exchange.
- **OSLC Requirements Management** — future direction for standards-based federation once identity, provenance, caching, authentication, and conflict semantics are explicit.
- **StrictDoc, Doorstop, and OpenFastTrace** — useful reference points for requirements-as-code, source traceability, review state, and transitive traceability capabilities.
- **SARIF and JUnit** — established machine-consumable formats that inform current CI/export and evidence integration.

These projects and standards are references, not compatibility claims. Quarto-Needs' defining constraint is that all capabilities remain projections of one deterministic semantic engineering graph.

## Design principles

- Requirements as Code
- Documentation as interface
- Traceability as a typed property graph
- Single semantic source of truth
- Architecture decisions as first-class objects
- Verification distinct from evidence
- Deterministic provider output distinct from provenance-bearing attestation
- Explainable change intelligence
- Deterministic artifacts and reproducible analysis
- Progressive enhancement for interactive views
- Extensible types, relations, queries, and policy
- Renderer-independent semantic core
- Git/CI-first workflows
- Interoperability without surrendering the canonical model

## Roadmap

The full accepted roadmap is maintained in [`docs/ROADMAP.md`](docs/ROADMAP.md). **Phase 1 — executable verification and machine evidence — is now implemented end to end**: pytest linkage, modeled test-case binding, provider-neutral machine checks, provider adapters, semantic evidence-object validation, attestation, provenance/fingerprint binding, freshness/expiry, and a self-hosted executable flow are all present. The next major product block is **Phase 2: Git-native change intelligence and pull-request governance**.

## License

MIT