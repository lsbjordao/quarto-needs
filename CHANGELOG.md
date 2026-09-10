# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Stability tiers. Every command, export format and integration is now classified as stable, preview or experimental in a single registry (`src/quarto_needs/surface.py`), from which `--help`, the runtime warning, the manual's Stability chapter, the README's contract list and the CHANGELOG's release-surface section are all rendered or verified. The command surface was previously declared in six places kept in sync by hand; tests now fail when any of them diverges. Experimental commands (`variant`, `migrate`, `oslc`) print one line to stderr when invoked, suppressible with `QUARTO_NEEDS_SUPPRESS_EXPERIMENTAL_WARNING=1`; stdout is unchanged. No command's behaviour changed.

- A subprocess perturbation harness (`tools/reproducibility.py`) and a required `reproducibility` workflow verify that analysis artifacts and the three fingerprints are byte-identical across hash seeds, time zones, collation locales, working directories, `--root` argument forms, source discovery order, Python 3.10 through 3.14, and Ubuntu, macOS and Windows. Determinism was previously asserted by design principle and exercised only indirectly.

### Fixed

- Percentage gates passed when their scope was misspelled or matched no requirements because missing scopes passed outright and 0/0 coverage is 100.0. Unknown scopes now fail configuration loading; empty measurements fail unless explicitly waived with `allow-empty-scopes`, and reports distinguish them from measured passes. Risk mitigation also checks that its high/critical-risk population was measured; missing measurements cannot be waived.
- `source_index._sources` built its mapping from an unordered `rglob` walk, so its insertion order followed the filesystem. The public index sorted at its own boundary, so no published artifact varied, but the mapping itself is now ordered at discovery for any future consumer.

## [0.1.1] — 2026-09-09

Initial production release at alpha maturity (classifier `Development Status :: 3 - Alpha`). Publication is gated by clean distribution checks and a TestPyPI installation rehearsal.

### Supported release surface

Classified into stability tiers in a later release; the list below is generated from `src/quarto_needs/surface.py`.

- **Stable**: `scan`, `check`, `coverage`, `trace`, `export`, `quality`, `query`, `baseline`, `baseline create`, `baseline inspect`, `diff`, `impact`, `export --format json|csv|markdown`, Quarto pre-render, Documented non-C4 shortcodes.

- **Preview**: `evidence`, `evidence check`, `suspect --git BASE..HEAD`, `pr-report --git BASE..HEAD`, `github-report --git BASE..HEAD`, `diff --git BASE..HEAD`, `impact --git BASE..HEAD`, `evidence attest`, `lsp`, `export --format sarif|junit|reqif|jsonld`.

- **Experimental**: `variant list|show NAME`, `migrate SOURCE`, `oslc discover|catalog|query`, C4 projections, GitHub Issues adapter, VS Code client.
- The existing `v0.1.0` tag and TestPyPI artifact are preserved; `0.1.1` is the first production release.

### Release validation

- The starter delegates to the installed extension in both local and GitHub-owner layouts, preventing a missing bootstrap entry on public template installation.
- Added `quarto-needs --version`, independent of project configuration, and `make quality` for the strict self-hosted gates.
- Wheel and sdist include schemas, canonical Quarto/Lua assets and translations; clean installations verify asset bytes and core operation without RDF/OSLC dependencies.
- Release verification exercises public extension and starter installation without a source override, tests the production package on Python 3.10–3.14 and attaches verified distributions to a GitHub release.

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

- A repeated `.need` preamble key silently discarded every value but the last, dropping authored relations with no diagnostic and letting a project still validate as fully traced. Repeats are now reported as `QND003` at the offending line; the merge semantics are unchanged.
- `[gates] require-risk-mitigation = true` reported `[PASS]` for every project when rule `REQ013` was left disabled, because the gate counts that rule's findings and `REQ013` is opt-in — a project with unmitigated critical risks passed its own risk gate. The incoherent pair is now rejected at configuration load.
- A `.quarto-needs.toml` that stopped loading while the language server was running silenced it: the error escaped into the dispatch loop's catch-all, which skipped the entire `publishDiagnostics` reply, so the editor kept stale diagnostics with no indication that anything had broken. The server now keeps its last valid snapshot and reports the failure as a `CFG001` diagnostic on the configuration file.
- `quarto-needs --help` presented only the argparse subcommands, hiding the Git-range change reports, `variant`, ReqIF/JSON-LD interchange, `migrate`, `oslc`, and `lsp`. The entry point now lists the commands its outer dispatch layer handles.
- Real `quarto add lsbjordao/quarto-needs` distribution now follows Quarto's owner-scoped `_extensions/lsbjordao/quarto-needs/` layout, including the managed bootstrap and generated Lua index consumed by the active extension.
- The starter template keeps a deliberately unscoped bundled extension with a matching bootstrap path while current Quarto releases retain the upstream scoped-template copy bug.
- README, quickstart, and manual examples now distinguish extension activation from installation, distinguish the optional standalone CLI from rendering, document the review-first migration CLI accurately, include the required OSLC query context, and no longer advertise a nonexistent public GitHub-Issues CLI.
- `documentSelector`/`LanguageClientOptions` type incompatibility surfaced by the first real `npm install` against the committed lockfile (`npm run check` and `npm run compile` now pass).
- Fixture-staleness failures in the earlier teaching tasks were corrected before the release-readiness review.
- The TestPyPI rehearsal now verifies the artifact installed from TestPyPI directly instead of replacing it with a package reinstalled from the repository checkout.
- The repository pre-render helper restores `QUARTO_NEEDS_EXTENSION_DIR` after in-process use, preventing one temporary project from contaminating later scans and renders.
- Release fixtures and self-hosted tests now use the owner-namespaced extension layout where they model `quarto add` installation.

### Security

- Same-origin redirect enforcement and request-only credentials in the OSLC federation transport; bounded timeout/byte/redirect/media limits.
- Content-addressed, schema-scoped persistence cache; atomic, all-or-nothing, rollback-protected apply paths; trusted-publishing (OIDC) release workflow with a TestPyPI rehearsal gate.
- The active extension artifact path is constrained to the current project's `_extensions` tree, preventing the pre-render from writing `generated-index.lua` through an external path or escaped `_extensions` symlink.
- The release workflow refuses to publish the extension/package pair while the GitHub repository is private, because the documented `quarto add owner/repository` distribution must be publicly resolvable.
