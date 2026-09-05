# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — unreleased

Initial release at alpha maturity (classifier `Development Status :: 3 - Alpha`). The release-validation gates tied to GitHub Actions are still open; see [the roadmap](notes/ROADMAP.md) for the exact status.

### Added

- Requirements-as-code engine: `.need` block grammar, typed relation catalog, declaration-native validation, and bounded executable policies.
- Git-native change intelligence: canonical baselines, `baseline`/`diff`/`impact`/`suspect --git` over a per-state typed property graph.
- Quarto extension contributing the project pre-render and provisioning `quarto-needs==<extension version>` into a project-local, interpreter-scoped managed runtime; project-local bootstrap on the self-hosted example and the quickstart.
- CLI (`quarto-needs`): `scan`, `check`, `coverage`, `trace`, `export` (canonical JSON, CSV, SARIF, JUnit, Markdown), `quality`, `query`, `evidence` (`check`/`attest`), `baseline` (`create`/`inspect`), `diff`, `impact`, standalone LSP (`lsp`), and a pytest plugin entry point.
- Interchange: deterministic ReqIF 1.2 export with normative XSD validation and embedded projection-loss notes; deterministic JSON-LD 1.1 export verified through real PyLD expansion/RDF-N-Quads; OSLC RM read-only federation (`oslc discover`) with bounded GET-only transport, content-addressed provenance cache, explicit reconciliation, and a deterministic, non-mutating `oslc-import-plan-v1`.
- Migration adapters for Sphinx-Needs, Doorstop, StrictDoc, and OpenFastTrace, with a reviewable `--apply-plan` and a create-only, atomic, rollback-protected `--write` step.
- External service adapters: GitHub issues projection with content-digest provenance, trust-state transitions, and a reviewed import-apply step.
- Architecture model and C4 projections; interactive graph workbench with an overlay artifact (catalog/changes/impact modes, shortest path, deep links, PNG export, keyboard navigation).
- Language Server Protocol with canonical diagnostics, completion, hover, definition/references, symbols, relation-aware rename, and collision-protected workspace refactors; thin VS Code client (type-check, compile, and VSIX packaging verified against the committed lockfile).
- Reproducible benchmark suite (five graph topologies to 50k objects, every kernel stage linear); documented minimum Quarto 1.6.0 floor verified against a real binary.
- Self-hosted multilingual (EN/PT-BR) manual, engineering example, and attested evidence artifact.

### Fixed

- `documentSelector`/`LanguageClientOptions` type incompatibility surfaced by the first real `npm install` against the committed lockfile (`npm run check` and `npm run compile` now pass).
- Fixture-staleness failures in the earlier teaching tasks; the full test suite is green.

### Security

- Same-origin redirect enforcement and request-only credentials in the OSLC federation transport; bounded timeout/byte/redirect/media limits.
- Content-addressed, schema-scoped persistence cache; atomic, all-or-nothing, rollback-protected apply paths; trusted-publishing (OIDC) release workflow with a TestPyPI rehearsal gate.