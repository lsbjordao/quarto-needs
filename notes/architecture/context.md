# System context

Quarto-Needs is a local-first toolchain: a Python semantic core plus a Quarto/Pandoc presentation adapter, consumed by CLI, editor, and CI surfaces. This page mirrors the C4 Context view already generated in the self-hosted example (`{{< need-c4 root="SYS-QUARTO-NEEDS" level="context" >}}` in [`examples/quarto-needs/architecture.qmd`](../../examples/quarto-needs/architecture.qmd)); render that project to see the live diagram — this page exists so the boundary is legible without a build.

## Actors

- **Requirements engineer** (`ACTOR-ENGINEER`) — authors, reviews, and approves engineering objects; reads generated views for traceability and coverage.

## The system

- **Quarto-Needs** (`SYS-QUARTO-NEEDS`) — the engineering-traceability tool: a requirements/decisions/risk/test/evidence graph authored in Quarto Markdown, analyzed by a Python core, presented through a Quarto extension.

## External systems

- **GitHub** (`EXT-GITHUB`) — hosts the project's own repository and issues; issues are federated as read-only, provenance-bound external observations (see [`interfaces/interoperability-boundaries.md`](interfaces/interoperability-boundaries.md)).
- **OSLC-compliant requirements management tool** (`EXT-OSLC`) — an external OSLC RM provider federated the same way.
- **Quarto/Pandoc** — the rendering runtime Quarto-Needs plugs into as a Lua-filter extension; not itself modeled as a `need` because it is a build dependency, not a data source or sink.
- **Git** — the versioning substrate every authored artifact and baseline lives in; also not modeled as a `need` for the same reason.
- **CI** — runs `quarto-needs check`/`coverage`/`diff`/`impact` as part of pull-request gating.

## What is deliberately not a box here

Interoperability *formats* (ReqIF, JSON-LD, SARIF) are not drawn as external systems — they are adapters, not systems Quarto-Needs depends on or is depended on by. See [`interfaces/artifact-contracts.md`](interfaces/artifact-contracts.md).
