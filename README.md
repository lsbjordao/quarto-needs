<p align="center">
  <img src="notes/assets/branding/quarto-needs-logo.svg" alt="Quarto-Needs" width="900">
</p>

<p align="center">
  <strong>Requirements as Code · Architecture Decisions · Verification · Evidence · Change Intelligence · Interoperability</strong>
</p>

# Quarto-Needs

Quarto-Needs is a **requirements-as-code and engineering-traceability engine for Quarto**. Engineering objects authored in `.qmd` files become a deterministic typed property graph that drives validation, governance, coverage, change impact, CI artifacts, editor tooling, interchange formats, and Quarto documentation.

> **Status:** pre-1.0 and under active development. The Python core is the semantic authority; Quarto is the executable documentation interface. Rendering, editor, CI, and interoperability layers consume projections of the same canonical model rather than redefining engineering semantics.

## North star

> Quarto-Needs is a requirements, architecture-decision, verification, evidence, change-intelligence, authoring, interoperability, and engineering-traceability engine built around a typed property graph, with Quarto as its executable documentation interface.

A mature project should be able to answer from one model:

- why a requirement exists;
- which decisions address it;
- where it is implemented;
- which tests verify it;
- which evidence proves those tests ran;
- what changed between engineering states;
- what is affected and through which explicit graph path;
- which governance policies fail;
- how the model can be safely navigated/refactored in an editor;
- how requirements can be exchanged or federated without surrendering canonical identity and provenance.

## Architecture

```text
QMD / configuration / code / tests / evidence / editor buffers
                         │
                         ▼
                  Quarto-Needs Core
      parser → analysis → typed graph → rules/query → snapshot
                         │
       ┌─────────────────┼───────────────────────┬──────────────────┐
       ▼                 ▼                       ▼                  ▼
     CLI/CI       machine exports         graph projections    interchange
       │                                         │            ReqIF/JSON-LD
       ▼                                         ▼               OSLC RM
 LanguageService                         Quarto extension
       │                                  HTML/PDF/DOCX
       ▼
   LSP stdio
       │
       ▼
 VS Code / LSP clients
```

The defining constraint is simple: **one canonical engineering graph, many projections**.

## Current capabilities

- configurable typed engineering objects, prefixes, roles, lifecycles, required attributes, and per-type JSON Schemas;
- canonical direct/inverse relation catalog with semantic families, endpoint roles, impact direction, and traversal direction;
- requirements, risks, tests, evidence, architecture elements, and first-class Architecture Decision Records;
- deterministic snapshots and semantic/configuration/representation fingerprints;
- built-in governance rules, bounded declarative policies, graph constraints, named queries, coverage metrics, and quality gates;
- safe derived values and deterministic build variants without creating alternate semantic graphs;
- baselines, semantic diff, relocation detection, explainable union-graph impact analysis, suspect state, and Git-native PR reports;
- GitHub-compatible summaries/annotations, JSON, CSV, SARIF, JUnit, Markdown, ReqIF 1.2, and JSON-LD projections;
- executable pytest bindings, provider-neutral machine checks, evidence attestations, digest/freshness/provenance validation, and reciprocal model↔test verification;
- Quarto cards, cross-references, tables, matrices, dashboards, inspectors, Mermaid flows, and bounded graph views;
- progressive Cytoscape exploration over the published semantic projection;
- bilingual English / Brazilian Portuguese presentation with semantic-parity enforcement;
- dependency-free LSP stdio server with diagnostics, completion, hover, definitions/references, symbols, unsaved-buffer overlays, and relation-aware rename;
- thin multi-root VS Code client delegating language intelligence to the Python LSP;
- ReqIF 1.2 interchange and deterministic JSON-LD 1.1 projection;
- read-only OSLC RM federation foundation with deterministic cache provenance, bounded HTTP GET, network-free RDF normalization, RM service discovery, and Resource Shape orchestration;
- a self-hosted engineering case study in `examples/quarto-needs/` that models Quarto-Needs with Quarto-Needs.

## Repository layout

```text
src/quarto_needs/             Python semantic core, LSP and interoperability
_extensions/quarto-needs/     Quarto filters, shortcodes and browser assets
editors/vscode/               Thin VS Code client for the Python LSP
schemas/                      Versioned artifact schemas
tools/                        Pre-render and release tooling
docs/                         Published manual site (GitHub Pages root) — rendered
docs/src/                     Manual source (.qmd) — the book project
notes/                        Product roadmap, design/architecture notes and branding assets
examples/quarto-needs/        Self-hosted engineering model
tests/                        Regression and integration tests
.github/workflows/            CI workflows
```

The manual is authored in `docs/src/` and rendered into `docs/`; the docs site is the GitHub Pages root. Design and product documentation that is not part of the manual lives under [`notes/`](notes/). For the end-user path, start with the published [`docs/`](docs/index.html) (the manual) or the standalone [`notes/quickstart.md`](notes/quickstart.md).

Quick start for Quarto projects (zero-install extension):

```bash
# Add the extension to your Quarto project
quarto add lsbjordao/quarto-needs

# Render your book or document (provisions the paired engine automatically)
quarto render
```

Contributor setup:

```bash
make setup
source .venv/bin/activate
make test
```

Analyze a project:

```bash
quarto-needs scan
quarto-needs check
quarto-needs quality
quarto-needs coverage
quarto-needs trace SYS-REQ-042
```

Compare engineering states:

```bash
quarto-needs baseline create
quarto-needs diff baselines/quarto-needs.json
quarto-needs impact baselines/quarto-needs.json

quarto-needs diff --git main..HEAD
quarto-needs impact --git main..HEAD
quarto-needs suspect --git main..HEAD
quarto-needs pr-report --git main..HEAD
```

Export interchange formats:

```bash
quarto-needs export --format reqif
quarto-needs export --format jsonld
```

Migrate from existing tools:

```bash
quarto-needs migrate sphinx-needs docs/needs.json --output requirements.qmd
quarto-needs migrate doorstop ./reqs --output requirements.qmd
quarto-needs migrate strictdoc ./docs --output requirements.qmd
quarto-needs migrate openfasttrace ./trace.xml --output requirements.qmd
```

Discover a configured OSLC RM Service Provider through the bounded read-only adapter:

```bash
pip install 'quarto-needs[oslc]'

quarto-needs oslc discover \
  https://provider.example/oslc/sp/requirements \
  --format json
```

Bearer credentials are supplied by **environment-variable name**, never embedded in configuration or command output:

```bash
export MY_OSLC_TOKEN='...'
quarto-needs oslc discover \
  https://provider.example/oslc/sp/requirements \
  --bearer-token-env MY_OSLC_TOKEN
```

Federate external GitHub issues:

```bash
export GITHUB_TOKEN='...'
quarto-needs github fetch \
  --repo owner/repo \
  --bearer-token-env GITHUB_TOKEN
```

Start the language server directly when integrating another editor:

```bash
quarto-needs --root /path/to/project lsp
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

Cross-reference objects with:

```qmd
{{< need SYS-REQ-042 >}}
{{< need SYS-REQ-042 title=true >}}
```

Generated views are projections of the canonical graph:

```qmd
{{< need-table types="functional-requirement;non-functional-requirement" status="approved" >}}
{{< need-matrix rows="functional-requirement" columns="test-case" relation="verified-by" >}}
{{< need-flow root="STK-001" depth="4" relations="derives-from;implemented-by;verified-by" >}}
{{< need-dashboard >}}
{{< need-inspector SYS-001 >}}
{{< need-graph view="graph-exploration" >}}
{{< need-c4 root="SYS-QUARTO-NEEDS" level="context" backend="mermaid" >}}
{{< adr-table status="accepted" tags="security" >}}
{{< adr-count status="accepted" >}}
```

For a clickable tag index, author a chapter (say `tags.qmd`) containing `{{< need-tags >}}`: it renders a chip for every tag plus one table of all objects. Configure `quarto-needs: tags-page: tags` (locale-suffixed keys like `tags-page-pt-br` for translations) and every tag badge anywhere in the site becomes a link into that chapter with the filter already applied via `?tag=<slug>`.

## Executable evidence

Verification intent, machine execution output, and provenance-bearing evidence remain distinct. A modeled test case can bind to a real pytest node while the executable test carries reciprocal requirement/test-case markers:

```python
@pytest.mark.requirement("FUN-004")
@pytest.mark.quarto_need_test_case("TC-010")
def test_graph_exploration_assets():
    ...
```

The pytest plugin emits deterministic provider output. `evidence-envelope-v1` then records SHA-256 digest, graph/configuration fingerprints, generation time, optional Git revision, and explicit expiry. `quarto-needs evidence check` validates both artifact integrity and semantic agreement with the current engineering graph.

See [`docs/src/executable-evidence.qmd`](docs/src/executable-evidence.qmd) and [`docs/src/evidence-providers.qmd`](docs/src/evidence-providers.qmd).

## Interoperability philosophy

Interchange formats are adapters, not authoring models.

**ReqIF 1.2** provides structured requirements exchange. **JSON-LD 1.1** exposes the engineering graph as Linked Data while preserving canonical relation metadata. **OSLC RM** is being implemented as a federation boundary: external identity, observed bytes/digest, retrieval time, trust, cache freshness, transport limits, RDF normalization, and Resource Shapes remain explicit before any remote import or synchronization is allowed.

The first OSLC path is intentionally read-only. It uses GET-only bounded HTTP, same-origin redirects, conditional retrieval, content-addressed cache blobs, network-free JSON-LD/Turtle/RDFXML normalization, and deterministic RM discovery. POST/PUT/PATCH/DELETE remain deferred until conflict, concurrency, authorization, and audit contracts exist.

Interchange status and acceptance records live in [`notes/ROADMAP.md`](notes/ROADMAP.md).

## Self-hosted engineering model

`examples/quarto-needs/` models the project itself: stakeholder needs → requirements → ADRs → architecture → real source modules → modeled test cases → executable tests → evidence. The OSLC milestone adds a complete federation slice from `STK-006` through `TC-015` / `EVD-015`, with English canonical content and a semantic-equivalent Brazilian Portuguese presentation.

This keeps major features traceable as engineering changes rather than leaving architecture and validation implicit in implementation code.

## Inspirations and related work

Quarto-Needs has its own Quarto/Pandoc-native architecture, but it is informed by mature ideas and ecosystems:

- **Sphinx-Needs** — **one of the original inspirations** for first-class typed engineering objects, links, generated views, filtering, and validation. Quarto-Needs pursues capability inspiration, not Sphinx syntax compatibility.
- **Requirements as Code / Docs as Code** — text-first, Git-versioned, reviewable engineering artifacts.
- **Architecture Decision Records (ADRs)** — explicit and durable architectural rationale.
- **C4 model** — inspiration for future architecture projections derived from the same engineering graph rather than maintained as a parallel model.
- **ReqIF** — structured requirements interchange.
- **OSLC Requirements Management** — standards-based federation with explicit identity, provenance, caching, trust, and failure behavior.
- **StrictDoc, Doorstop, and OpenFastTrace** — reference points for requirements-as-code, traceability, review state, and transitive links.
- **Language Server Protocol** — editor interoperability without editor-specific semantic forks.
- **SARIF and JUnit** — established machine-consumable CI/reporting formats.

These are references and inspirations, not compatibility claims.

## Design principles

- Requirements as Code
- documentation as interface
- traceability as a typed property graph
- one semantic source of truth
- architecture decisions as first-class objects
- verification distinct from evidence
- authored data distinct from computed projections
- explainable change intelligence
- deterministic and reproducible artifacts
- bounded declarative policy
- progressive enhancement for interactive views
- renderer-independent semantic core
- thin editor clients
- Git/CI-first workflows
- interoperability without surrendering the canonical model

## Roadmap

<p align="center">
  <a href="notes/ROADMAP.md">
    <img src="notes/assets/branding/quarto-needs-roadmap-infographic.svg" alt="Quarto-Needs engineering evolution roadmap" width="1000">
  </a>
</p>

The infographic is a **visual presentation snapshot**. [`notes/ROADMAP.md`](notes/ROADMAP.md) is the authoritative, continuously updated roadmap.

Current status: **Phases 1, 2, 3 and 4.1 are implemented. Phase 4.2 (thin VS Code client) is functionally implemented: its TypeScript build gates — type-check, compile, and VSIX packaging — pass locally against the real committed lockfile, while the Actions/Extension-Host release gate remains open for the infrastructure reason below. Phase 5.1 ReqIF is implemented and locally validated; Phase 5.2 JSON-LD is implemented and independently verified against a real PyLD; Phase 5.3 OSLC RM read-only federation is complete end to end, with remote writes deliberately deferred; Phase 5.4 migration adapters (Sphinx-Needs, Doorstop, StrictDoc, OpenFastTrace) and Phase 5.5 external service adapters (GitHub issues, with trust transitions and a reviewed apply step) are implemented. Phases 6 and 7 (architecture model/C4 projections and the interactive graph workbench) are delivered; Phase 8 has delivered its first two slices and the extension-first distribution slice (declaration-native validation, linear-time indexes, reproducible benchmarks to 50k objects, minimum-Quarto verification, and TestPyPI rehearsal for both the CLI and bootstrap paths), with the remaining measurement and release gates open; Phase 9's teaching slices (broken gallery, suspect-after-change, interchange-loss and editor-refactor) are delivered.**

GitHub Actions currently terminates the Python-matrix and VS Code jobs before checkout (`steps: null`). That infrastructure condition is neither treated as a repository test failure nor as successful execution evidence, and the CI release gates cannot close until the account's Actions quota resets.

## Branding

The logo, symbol, extension icon, palette, and visual-roadmap assets live under [`notes/assets/branding/`](notes/assets/branding/). See [`notes/branding.md`](notes/branding.md) for the visual semantics and palette.

## License

MIT
