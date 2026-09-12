# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Upgrade notes

- **`require-risk-mitigation` now fails on a project with no high or critical risks.** Before, the gate counted zero `REQ013` findings and reported `[PASS]`. It now reports the population it measured: zero high/critical risks is a zero denominator, status `empty`, and an empty population fails unless waived. A project that enabled the gate and carries no high-priority risk therefore turns from green to red on upgrade with no change to its sources.

  This is deliberate and is being kept. `require-risk-mitigation = true` asserts that risk is managed here; a project that has modelled no high-priority risk has not demonstrated that, and "nothing was measured" is not a pass. The asymmetry with coverage scopes is narrower than it looks: both now report *what population they measured*, and both fail on an empty one.

  **If you are affected**, choose deliberately rather than reflexively:
  - model the risks the project actually carries, and give the high/critical ones a mitigation relation — the outcome the gate exists to produce; or
  - set `[gates] allow-empty-scopes = true` if the project is genuinely starting empty. Read the caveat below before you do; or
  - remove `require-risk-mitigation` if the project does not manage risk in this model. An absent gate claims nothing, which is honest; a passing unmeasured gate claims something false.

  Caveat on the waiver: `allow-empty-scopes` is project-wide, not per gate. Setting it to silence the risk gate also waives an empty coverage scope in the same project. `quality --format json` distinguishes the cases (`measurementStatus`) and the CLI prints `[WAIVED]` rather than `[PASS]`, so a waived gate stays visible — but the coarseness is real, and narrowing the waiver to a single gate is not yet possible.

### Added

- Stability tiers. Every command, export format and integration is now classified as stable, preview or experimental in a single registry (`src/quarto_needs/surface.py`), from which `--help`, the runtime warning, the manual's Stability chapter, the README's contract list and the CHANGELOG's release-surface section are all rendered or verified. The command surface was previously declared in six places kept in sync by hand; tests now fail when any of them diverges. Experimental commands (`variant`, `migrate`, `oslc`) print one line to stderr when invoked, suppressible with `QUARTO_NEEDS_SUPPRESS_EXPERIMENTAL_WARNING=1`; stdout is unchanged. No command's behaviour changed.

- A subprocess perturbation harness (`tools/reproducibility.py`) and a required `reproducibility` workflow verify that analysis artifacts and the three fingerprints are byte-identical across hash seeds, time zones, collation locales, working directories, `--root` argument forms, source discovery order, Python 3.10 through 3.14, and Ubuntu, macOS and Windows. Determinism was previously asserted by design principle and exercised only indirectly.

- A release-gate matrix (`notes/release-gates.md`) names the evidence behind each gate, and `benchmarks/budgets.json` plus `make check-performance-budgets` turn the recorded performance evidence into an executable budget check. The budget document is verified in CI without asserting timings; the fresh measurement stays a release-rehearsal step.

- Relation attributes. A relation value may carry inline `name=value` attributes after its targets (`depends-on: CONTAINER-API technology="HTTPS/JSON" label="calls over HTTPS"`); attributes on one value apply to every target on it, and the `-` list form gives targets different attributes. The C4 projections render `label` as the relationship description and `technology` as the relationship technology in Mermaid, PlantUML and Structurizr, with D2 folding it into the edge label, and the public graph projection exposes edge `technology`. A malformed assignment is reported as `QND004` instead of being silently dropped.

- Deployment views. `deployment-node` objects and the `deployed-on`/`deploys` relation extend the C4 projections with a `deployment` level: `need-c4 root="DEPLOY-..." level="deployment"` draws the focus node's boundary with nested deployment nodes and the artifacts deployed on it, from the same bounded selection as every other level. The relation catalog moves to version 5, and the self-hosted case study models its developer workstation with both containers deployed on it.

- Dynamic views. The `interacts-with` relation carries ordered runtime interactions (`order`, `label`, `technology`), and `need-c4 root="SYS-..." level="dynamic"` draws them as a numbered sequence: Mermaid `C4Dynamic` with `RelIndex`, a PlantUML sequence diagram, a Structurizr `dynamic` view referencing model relationships, and a D2 sequence diagram. The relation catalog moves to version 6, and the self-hosted case study records its render scenario as three ordered interactions.

- Migration update matching. Written migration blocks now carry a durable source marker (`source-tool`, `source-project` when the source declares one, and `source-id`), and `migrate <source> --update-plan` matches the current upstream items against those markers without touching authored files: `ready-create` for new items, `ready-update` with the changed fields and a file digest for matched items, `no-change`, and `blocked` for anything needing a decision. A canonical ID that already exists without a source marker is never treated as an implicit update. `--write` is refused with `--update-plan`; applying updates is a separate reviewed step.

- Migration update application. `migrate <source> --update-plan --apply-update --write` applies approved updates in place: every item must be `ready-update` or `no-change` (ready-create items belong to `--apply-plan --write`), each matched file must still carry the digest the plan recorded, every block must be locatable, writes are atomic per file, and a post-write rescan restores every touched file before failing on any structural error. Re-applying a stale plan is refused by its digest; `--apply-update` cannot be combined with `--apply-plan`.

- ReqIF 1.2 import. `quarto-needs migrate reqif <document>` parses a ReqIF document into the shared migration plan, reusing the same review-first apply and update contracts as every other adapter. Identity recovery prefers an embedded `quarto-needs.canonical-id` value over the opaque ReqIF identifier, so a Quarto-Needs ReqIF export re-imports with canonical IDs, titles, statuses, bodies, rationales, relations and attributes intact. Typed values are recovered explicitly — enumerations by `LONG-NAME`, XHTML flattened — and every lossy conversion is a plan issue rather than a silent change. DOCTYPE/ENTITY-bearing and oversized documents are refused.

- OSLC remote writes, first slice. The eight contracts the roadmap required before any POST/PUT/PATCH/DELETE are stated in `notes/oslc-remote-writes.md`, and the update operation is delivered under them: a reviewed `oslc-write-plan-v1` builds one `PUT` per trusted, bound observation that carries an ETag — an observation without one is skipped, never overwritten unconditionally — a bounded transport sends one request at a time with request-only credentials and no redirects, a `412`/`409` stops the run, and an `oslc-write-audit-v1` records every outcome before the failure propagates. A previous audit makes unchanged payloads skippable. Remote create/delete and the CLI pipeline remain the next slice.

- OSLC remote writes: create, delete and the review-first CLI. `quarto-needs oslc write` builds the plan from an observation export and sends nothing without `--apply`; `--create` targets an explicit `--collection-uri`, refuses an already-bound ID and carries a deterministic advisory `Idempotency-Key`; `--delete` must be named explicitly and requires a single trusted bound observation with an ETag. Applying reads the bearer token from the environment and writes `oslc-write-audit-v1` — including the create `Location` — before any failure propagates. Nothing destructive is ever derived from a diff.

- Stale-evidence teaching fixture. `examples/broken/stale-evidence/` carries an evidence envelope whose payload is intact, whose provider still agrees and which has expired nothing, and `quarto-needs evidence check` still refuses it with `EVD203` because its semantic-graph fingerprint predates a model change — expiry is a date, staleness is a binding.

### Changed

- README opens with real coverage and traceability screenshots, an executable authoring example, tested quickstart commands and dynamic CI/PyPI badges; capabilities are summarized after the demonstration.
- `tools/capture-screenshots.py` renders the self-hosted case study and the README example, serves them locally and captures their actual browser output with an isolated Playwright toolchain.

### Fixed

- Percentage gates passed when their scope was misspelled or matched no requirements because missing scopes passed outright and 0/0 coverage is 100.0. Unknown scopes now fail configuration loading; empty measurements fail unless explicitly waived with `allow-empty-scopes`, and reports distinguish them from measured passes. Risk mitigation also checks that its high/critical-risk population was measured; missing measurements cannot be waived.
- `source_index._sources` built its mapping from an unordered `rglob` walk, so its insertion order followed the filesystem. The public index sorted at its own boundary, so no published artifact varied, but the mapping itself is now ordered at discovery for any future consumer.
- The interactive graph embedded projected JSON into `<script type="application/json">` without HTML-significant escaping, so a title containing the literal sequence `</script>` closed the element early and the remainder was parsed as markup. Both the graph data and the overlay payloads now escape `<`, `>`, `&` and the Unicode line separators at the embedding boundary; a real-render regression test uses a hostile title and asserts the payload round-trips without breaking out.
- Migration update application refused a reviewed plan that mixed updates with newly added upstream items: `--apply-update --write` now applies the plan's `ready-create` items too (appending each new block to its reviewed destination), under the same all-or-nothing, per-file atomic, digest/create-preflighted and rollback contracts. A sync no longer dead-ends between the update path and the first-migration create path, and re-running it finds everything `no-change`.

## [0.1.1] — 2026-09-09

Initial production release at alpha maturity (classifier `Development Status :: 3 - Alpha`). Publication is gated by clean distribution checks and a TestPyPI installation rehearsal.

### Supported release surface

Classified into stability tiers in a later release; the list below is generated from `src/quarto_needs/surface.py`.

- **Stable**: `scan`, `check`, `coverage`, `trace`, `export`, `quality`, `query`, `baseline`, `baseline create`, `baseline inspect`, `diff`, `impact`, `export --format json|csv|markdown`, Quarto pre-render, Documented non-C4 shortcodes.

- **Preview**: `evidence`, `evidence check`, `suspect --git BASE..HEAD`, `pr-report --git BASE..HEAD`, `github-report --git BASE..HEAD`, `diff --git BASE..HEAD`, `impact --git BASE..HEAD`, `evidence attest`, `lsp`, `export --format sarif|junit|reqif|jsonld`.

- **Experimental**: `variant list|show NAME`, `migrate SOURCE`, `oslc discover|catalog|query|write`, C4 projections, GitHub Issues adapter, VS Code client.
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
