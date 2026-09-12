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

# Phase 4 — Authoring ergonomics: LSP and VS Code ✅

## 4.1 Language Server Protocol ✅

**Status: implemented.**

The editor-independent `LanguageService` and stdio LSP provide canonical diagnostics, completion, hover, exact definition/references, document/workspace symbols, relation-aware rename, in-memory unsaved-buffer overlays, exact source indexing, localized-presentation handling, and collision-protected `WorkspaceEdit` refactors.

The LSP consumes the same parser, configuration, relation catalog, analyzer, policies, and graph semantics as the CLI.

## 4.2 Thin VS Code client ✅

**Status: implemented, with release validation green in CI.**

Released client:

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
- a committed, real `package-lock.json`, and a CI job that installs from it, type-checks, compiles, exercises the Extension Host through the Python LSP, packages the VSIX and uploads it as an artifact.

Release validation history: the fabricated lockfile was replaced with a real `npm install` output, which surfaced and fixed a genuine `documentSelector`/`LanguageClientOptions` type error that had never been caught; the pipeline then could not run while the account's Actions quota was exhausted, and local Extension Host runs were unreliable inside a nested VS Code session. The Actions pipeline now runs and passes end to end, which closes the gate.

---

# Phase 5 — Interchange, migration, and federation 🚧

## 5.1 ReqIF 1.2 ✅

**Status: functionally implemented and locally validated.**

Implemented and validated capabilities include deterministic ReqIF 1.2 projection, normative XSD validation, independent parser acceptance, stable identity mapping, loss semantics, deterministic XML output, and installed CLI export.

ReqIF import is now delivered as a fifth migration adapter (`quarto-needs migrate reqif <document>`), converging on the same review-first plan → apply → update contracts as the other sources. It closes the round trip: identity recovery prefers an embedded `quarto-needs.canonical-id` over the opaque ReqIF identifier, so a Quarto-Needs export re-imports with canonical IDs, titles, statuses, bodies, rationales, relations and attributes intact. Typed attribute recovery is explicit — enumerations recover their `LONG-NAME`, XHTML is flattened, and every lossy conversion is a plan issue — and conflict policy/provenance reuse the migration update/match contract (source markers, digest-preflighted application). DOCTYPE/ENTITY-bearing and malformed documents are refused.

## 5.2 JSON-LD ✅

**Status: implemented and independently verified — `pytest -q tests/test_export_jsonld.py tests/test_interchange_cli.py` ran locally against a real PyLD (no skip guard) and passed.**

Implemented capabilities include deterministic JSON-LD 1.1 projection, stable object/relation IRIs, embedded context, canonical relation semantics, authored attributes as `@json`, installed CLI export, deterministic writes, and independent PyLD expansion/RDF-N-Quads verification that preserves canonical relation endpoints.

## 5.3 OSLC Requirements Management ✅ (read-only)

**Status: read-only federation is implemented end to end through discovery, bounded query execution, independently provenance-bearing member observations, explicit reconciliation, and a reviewed, non-mutating import plan — all executed locally against the self-hosted example. Remote writes (POST/PUT/PATCH/DELETE) remain the only deliberately deferred slice.**

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
- self-hosted EN/PT-BR requirements, ADRs, implementation modules, tests, and evidence through `TC-019` / `EVD-019`, including the reviewed import-plan module (`SRC-OSLC-IMPORT`);
- eleven representative executable tests in `make evidence-self-example` after the TC-019 slice;
- centralized validation of `[federation.oslc.profiles.*]` inside ordinary `load_config()`, with read-only connectivity kept outside the canonical configuration fingerprint;
- the self-hosted evidence gate re-validated end to end: `_self_hosted_records()`/`_complete_provider_payload()`/`_complete_pytest_payload()` had silently drifted since `TC-014` (missing TC-014 through TC-018, and a missing requirement on TC-005) and are now generated against, and checked to match, `make evidence-self-example`'s real output.

Remaining 5.3 gate:

1. keep canonical import/apply and all POST/PUT/PATCH/DELETE operations deferred until staleness, conflict, authored-file placement, atomicity, rollback, optimistic concurrency, authorization, and audit contracts are explicit.

The terminal artifact for this phase is therefore a reviewable import plan, not automatic mutation.

## 5.4 Migration adapters ✅ (Sphinx-Needs, Doorstop, StrictDoc, OpenFastTrace)

**Status: four adapters are implemented end to end on one shared contract — deterministic plan, reviewable non-mutating apply plan with a `.need` block content preview, and a create-only, atomic, rollback-protected `--write` step. Additional source adapters remain future work.**

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
- `quarto-needs migrate sphinx-needs ... --apply-plan --write`: create-only (an existing destination file refuses the whole write), atomic per file, all-or-nothing across files with real rollback (verified by forcing an OS-level failure on a later file and confirming an earlier one is deleted), post-write `scan`/`check` re-verification that rolls back on any new structural failure or error finding (verified by injecting a synthetic error), and a refusal-based idempotence contract — a rerun is refused, not silently duplicated, because the canonical IDs it would create already exist;
- a second adapter, `quarto-needs migrate doorstop ...`, converging on that exact same apply-plan/render/write implementation without changing it: reads nested `.doorstop.yml` document trees (prefix-keyed type/relation mapping, since Doorstop items have no per-item type or status field), preserves `active`/`derived`/`normative`/`ref`/`level` as extras, and emits explicit `TYPE_UNMAPPED`/`RELATION_UNMAPPED`/`EXTERNAL_LINK_TARGET` diagnostics plus fail-closed duplicate-UID rejection, each with its own default artifact paths independent of Sphinx-Needs';
- the shared migration-plan artifact's `tool`/`schema` are now parameters (`SphinxNeedsMigrationPlan.tool`/`.schema`, defaulting to the original Sphinx-Needs values) rather than a hardcoded literal, so a second adapter's provenance is never mislabeled;
- a third adapter, `quarto-needs migrate strictdoc ...`, parsing StrictDoc's own `.sdoc` grammar (`[TAG]` blocks, `>>>`/`<<<` multi-line fields, `RELATIONS:` lists) across multiple files with globally-unique, cross-file UID resolution, TAG-keyed type mapping, relation-TYPE-keyed relation mapping, `RATIONALE` folded into content as a `### Rationale` subsection, and non-UID (`TYPE: File`) relations preserved rather than misresolved — validated against StrictDoc's own real, self-hosted `.sdoc` documentation, which surfaced and drove the handling of `[GRAMMAR]`-block and file-relation edge cases that synthetic fixtures alone had not covered.

Next 5.4 slices:

1. add further source-specific adapters, converging only at the shared migration-plan/apply-plan/write contracts (as Doorstop, StrictDoc, and OpenFastTrace did, with no change to that shared code);
2. update/match identity: **delivered** — every written block carries a durable source marker (`source-tool`, optional `source-project`, `source-id`), and `migrate <source> --update-plan` matches a changed upstream source onto those markers, classifying each item as `ready-create`, `ready-update` (with its changed fields and a file digest), `no-change` or `blocked`, and never treating an existing canonical ID without a marker as an implicit update. Applying updates is `--apply-update --write`: all-or-nothing, digest-preflighted, atomic per file, rolled back on any post-write failure, and stale re-applies are refused by the digest.

Sphinx-Needs, Doorstop, StrictDoc, and OpenFastTrace remain supported migration sources and inspirations for Quarto-Needs; compatibility claims are limited to the explicitly implemented adapter behavior for each.

## 5.5 External service adapters ✅ (ten slices plus trust transitions, apply step, and retry policy)

**Status: complete — the read-only GitHub issue projection is implemented end to end: external identity, content-digest provenance, normalization into the same observation shape OSLC federation already uses, a bounded GET-only HTTP transport with rate-limit exhaustion distinguished from auth failures, a persistent content-addressed cache, conditional requests, bounded issue-list discovery, bounded multi-page traversal of that discovery, search-API discovery on the same bounded contract, reconciliation + import planning through OSLC's own source-agnostic contracts (zero new reconciliation code — proven, not assumed), explicit reviewer trust-state transitions over a closed allowlist, an apply step that writes accepted plans into authored files with all-or-nothing preflight and post-write rollback, a caller-side rate-limit retry policy honoring the server's own Retry-After/reset facts, and a fully traced self-hosted example slice with five real pytest bindings in the attested evidence artifact — all run against the real GitHub API including a real HTTP 304, a real list-then-fetch handoff, and a real two-page traversal across GitHub's rewritten Link targets.**

Read-only/cacheable adapters may target GitHub issues or lifecycle-management systems. Every imported object must preserve external identity, origin, digest/version, retrieval policy, and trust state.

Implemented capabilities include:

- `github_issue_resource_uri`/`build_github_issue_identity`, reusing OSLC's `ExternalResourceIdentity`/`content_digest` directly rather than a parallel identity model — those turned out to already be source-agnostic;
- `parse_external_github_issue`, normalizing a fetched issue payload into OSLC's own `ExternalRequirementObservation` shape, validated against a real payload fetched live from a public GitHub repository, not only synthetic fixtures;
- explicit pull-request rejection (GitHub's issues endpoint also returns pull requests) and explicit, non-guessed handling of `state`, `null` bodies, and missing labels;
- `fetch_github_resource` (`github_http.py`): a bounded, GET-only HTTP transport (byte/time/redirect limits, same-origin redirect enforcement so an `Authorization` header cannot leak cross-host, request-only auth headers, `application/json`-only media type) — an independent, small implementation rather than reusing `oslc_http.py`'s RDF-media-type-specific one, sharing only the fully generic `HttpFetchPolicy` dataclass; tested against a fake, injectable opener with the cross-origin-redirect and byte-limit checks falsified, not just asserted;
- `oslc_cache.py`'s persistence functions gained an optional `schema` parameter (default preserves the original hardcoded OSLC behavior for every existing caller) instead of forking a parallel cache implementation — its one OSLC-specific coupling was a single hardcoded schema-string constant, the same class of fix already applied once this phase to `SphinxNeedsMigrationPlan.tool`/`.schema`; a new test proves a cache root written under one schema is never silently read or overwritten under another;
- conditional requests: `fetch_github_resource` gained `if_none_match`/`if_modified_since` parameters and returns `payload=None` on a `304` (never media-type/byte-checking a bodyless response); `fetch_external_github_issue` builds those headers from a stale cache entry's own validators and, on `304`, reuses the cached body under a refreshed identity (new `fetched_at`, same digest) instead of re-downloading — verified with a real HTTP 304 from GitHub itself, not only the fake-opener suite;
- `fetch_external_github_issue`, composing transport + identity + parser + the now-shared cache + conditional requests into one read-only fetch-and-normalize call (`cache_root` opt-in; a fresh hit skips the network entirely), run live against a real GitHub issue, a real pull request (confirming PR-rejection fires for real), a real two-call cache run measuring ~0.4s live / 0.0s cache hit, and a real conditional-request round trip receiving an actual `304`;
- `fetch_external_github_issue_list`, one bounded GET-only page of `GET /repos/{owner}/{repo}/issues` returning discovered issue/pull-request numbers (explicitly separated, neither mixed in nor silently dropped) plus the list response's own digest — deliberately discovery-only, never promoting a list entry's inline data into an `ExternalRequirementObservation`, the same query-then-independently-observe boundary `oslc_query.py`'s own design note argues for around inline query-container data; run live against a real 5-issue page (3 issues / 2 pull requests) with one discovered number handed off to a real full-observation fetch;
- `fetch_external_github_issue_list_pages`, bounded multi-page traversal of that same list following GitHub's own `Link: rel="next"` target up to an explicit `max_pages` budget (default 1 — no traversal unless asked), reporting `truncated` honestly when the budget runs out while a next page still exists, and rejecting a cross-origin next URL rather than following it; GitHub legitimately rewrites `/repos/{owner}/{repo}` to `/repositories/{id}` (plus an `after=` cursor) in its Link targets, so the traversal validates origin, never path. A present-but-malformed Link header raises rather than silently reading as "no next page". The list endpoint's own filters (`labels`, `since`, `sort`, `direction`) joined `state` as explicit URI parameters. Run live against `strictdoc-project/strictdoc`: a real two-page traversal (8 issues / 2 pull requests, page 2 served from the rewritten `/repositories/263988764` path), honest truncation at `max_pages=1`, one page-2-discovered number fetched as a full observation, and a live `labels=["documentation"]` filter.

- reconciliation + import planning for GitHub observations — the slice that needed no new code: `reconcile_external_requirements`/`build_oslc_import_plan` turned out to be fully source-agnostic (their inputs are exactly the `ExternalRequirementObservation`s the GitHub parser already produces), so instead of mirroring them, the reuse was proven and pinned by `tests/test_github_reconcile.py` — an issue number stays data even when it equals a canonical ID (falsified by injecting an identifier-matching heuristic), bindings must use the adapter's API URIs (an HTML-URL key is rejected loudly, never silently unbound), and all five import-plan dispositions (ready-create/blocked/ready-update/review-required/ignored) behave identically for GitHub observations, each carrying the observation's own digest/fetched-at provenance; live-checked with a real issue (#2067) planned through the unchanged contracts;

- rate-limit classification: `github_http.py` now raises `GitHubRateLimitError` (code `rate-limited`, a `GitHubTransportError` subclass so existing handlers keep working) for a `403` with `X-RateLimit-Remaining: 0` or any `429`, carrying the server's retry facts (`retry_after_seconds` from `Retry-After`, `rate_limit_reset_epoch` from `X-RateLimit-Reset`) without ever sleeping on its own; a `403` without exhaustion keeps the `authentication-required` classification, both branches are falsified, and live checks confirmed normal requests are untouched and the real `/rate_limit` endpoint's semantics match what the error reports (a real exhaustion was deliberately not triggered — it would burn the shared-IP hourly quota);

- self-hosted example integration: the GitHub adapter is modeled as a complete chain in `examples/quarto-needs` — `STK-007 → SYS-008 → FUN-014…017 / NFR-007 → ADR-010 → COMP-GHISSUES / IF-006 / SRC-GITHUB-HTTP / SRC-GITHUB-ISSUES → TC-020…024 → EVD-020…024` (with `RISK-012` covering unbounded pagination, silent truncation, and rate-limit blindness, and `FUN-017` implementing against `COMP-OSLC` to record the reconciliation reuse in the model itself) — where the five test cases bind to real pytest nodeids with matching markers, all five joined `make evidence-self-example` (now attesting 16 linked tests; the evidence check's marker↔model cross-validation caught one real `verified-by` omission during authoring), and the pt-BR page mirrors all objects with identical semantic signatures;

- search-API discovery: `fetch_external_github_issue_search`/`_search_pages` — the same bounded discovery contract on `GET /search/issues`'s different envelope (`total_count`, `incomplete_results`, `items` reusing the list parser's issue/pull-request separation), scoping left to the caller's explicit qualifier string, the multi-page traversal being the *same machine* as the list's (extracted into one shared bounded loop rather than a fork), a conservative `incomplete_results` union across pages, and GitHub's separate search rate-limit class raising the same distinguished error; falsified on envelope validation and on the union flag; live-checked with a real query (`total_count=81`), a real two-page truncated traversal, and a discovered-number handoff;

- explicit trust-state transitions: `external_trust.py` — `apply_trust_decision` turns an immutable, substantive reviewer decision (`action`/`decided_by`/`reason`/`decided_at`) into a new observation plus an auditable record, over a closed allowlist of `(from, action) → to` transitions; the input is never mutated, the observed-bytes digest and retrieval provenance carry over unchanged (a trust decision is about the reviewer's judgement, not the remote representation), and a rejected observation must pass an explicit `reset` before it can be trusted again — trust can never directly follow rejection; the transitioned state flows into reconciliation unchanged (rejected blocks, reset unbinds, trust matches); falsified by bypassing the allowlist;

- an apply step (`import_apply.py`): the first write path downstream of the reviewed plan, inheriting the migration apply's safety contracts and adding updates — every applicable item is preflighted against a fresh scan (created IDs must not exist yet; update `from` values must still match the authored file, and the plan's target file must be where the object is authored), writes are atomic per file with the project re-scanned afterwards and rolled back on any error finding, a second apply refuses idempotently, and non-applicable dispositions (blocked/review-required/ignored/no-change) are reported as skipped with the plan's own reason, never half-applied;

- a caller-side rate-limit retry policy (`github_retry.py`): the transport's retry facts become a decision — `Retry-After` wins, then `X-RateLimit-Reset` when the caller supplies a clock, then bounded exponential backoff; `max_attempts` counts total attempts including the first, and giving up re-raises the server's own error with its facts intact; only rate limits are ever retried — other failures propagate immediately as facts to act on.

Phase 5.5's planned scope is complete; the next milestone is Phase 6.

---

# Phase 6 — Architecture model and C4 projections ✅ (first slice: actor/external-system/system/container types, Context/Container/Component views, self-hosted retrofit; second slice: deployment nodes, Deployment views, relation attributes, self-hosted retrofit; third slice: dynamic views and ordered interactions, self-hosted retrofit)

C4-like views must be **projections of the same engineering graph**, not a second architecture database.

Planned work includes actors/people, external systems, system boundaries, hierarchical software-system/container/component/code roles, interfaces/interactions, and generated System Context, Container, Component, and Code views. Dynamic/deployment projections follow only after the static hierarchy is stable.

Every architecture projection remains traceable to requirements, decisions, risks, implementation, tests, and evidence.

The delivered first slice covers the C4 semantic model and Context/Container views with a self-hosted retrofit; its two deliberate simplifications are known limitations of the generic mechanism, not silent gaps — interaction edges reach only the focus node, never its children two hops away, and the generic cardinality rule rejects duplicate parents without ever guaranteeing an orphan-free model. The second slice adds deployment nodes (`deployed-on`/`deploys`), Deployment views across the renderer boundary, the relation-attribute authoring syntax (`depends-on: TARGET technology="..."`), and the self-hosted retrofit. The third slice adds dynamic views: the `interacts-with` relation with an authored `order`, rendered as a numbered sequence across all four backends, with the self-hosted render scenario modeled as three ordered interactions. Phase 6's planned scope is complete.

---

# Phase 7 — Interactive graph workbench ✅ (twelve slices: overlay annotation artifact, Catalog/Changes/Impact switcher, shortest path, deep-linking, breadcrumbs, fullscreen, PNG export, mini-map, keyboard navigation, Changes-mode table, impact popups, named-query overlays)

Extend Cytoscape from visualization into bounded engineering analysis: shortest paths, baseline/current comparison, affected-only views, semantic clustering, breadcrumbs, deep-linkable state, saved exploration state, fullscreen mode, SVG/PNG export, mini-map, keyboard navigation, and accessibility.

Interactive operations must consume published canonical semantics and bounded projections.

Baseline comparison is interactive through a pre-rendered overlay annotation artifact applied in place by the browser. Delivered across twelve slices: the overlay artifact with a Catalog/Changes/Impact mode switcher plus an affected-only toggle; two-node semantic shortest path as a client-side generalization of the path-to-root algorithm; deep-linkable saved exploration state; node attributes in the static table; breadcrumbs; fullscreen mode; PNG export (SVG export was dropped because every released `cytoscape-svg` is GPLv3, conflicting with the MIT license); an MIT-licensed mini-map; linear keyboard traversal; Changes-mode rows (including ghost rows for removed nodes/edges); impact-popup Distance/Origin/Classification/Path rows; and overlays for named-query views through an explicit `[graph] overlay-queries` allowlist.

---

# Phase 8 — Scale, performance, compatibility, and release hardening ✅ (first slice: semantic-core stabilization — declaration-native validation, linear-time indexes, reproducible benchmarks, schema compatibility policy, minimum-Quarto verification, minimal example; release-gate matrix in [`notes/release-gates.md`](release-gates.md))

Maintain synthetic sparse/dense/cyclic/high-fanout corpora around 100, 1,000, 10,000, and 50,000+ objects where practical. Measure parsing, analysis, policies, queries, baseline/diff/impact, evidence, LSP latency, graph projection, export, and Quarto rendering.

Caching/incrementality is introduced only when benchmarks identify a real bottleneck. Release gates cover schema compatibility, determinism, migrations, accessibility, projection security, performance budgets, supported Python/Quarto versions, editor compatibility, interoperability, and self-hosted example health.

The first slice is delivered by the core-stabilization phase: the canonical
analyzer no longer routes validation through legacy DTOs, snapshot indexes
are built in O(V+E), a reproducible benchmark suite records linear scaling
to 50k objects, one measured duplication was removed from the impact path,
public schema compatibility is documented and contract-tested, and CI
verifies the declared minimum Quarto (1.6.0).

The second slice completes the phase's measurement mandate. The corpus
generator now emits four topologies beside the pinned `mixed` one —
`sparse`, `dense`, `cyclic`, and `high-fanout` — sharing an identical object
inventory so a measured difference is attributable to graph structure alone,
and the harness measures queries, baseline construction, diff, impact
(against a baseline with a real changed set, not an identical one) and
export beside the kernel stages. Measured to 50k objects across all five
shapes: every stage is linear in graph size, and the one shape-sensitive
result is neighborhood selection, which costs ≈3× more on `high-fanout` than
on `mixed` at *fewer* edges — in-degree concentration, not edge count,
drives bounded selection. Per the phase rule, that is a documented
characteristic and not a bottleneck, so **no caching or incrementality is
introduced**. See `benchmarks/README.md`. LSP latency
(`benchmark_lsp.py`) and Quarto rendering (`benchmark_render.py`) are
measured, and the release gates are inventoried in
[`notes/release-gates.md`](release-gates.md), with performance budgets
executable through `make check-performance-budgets`.

The third slice (Phase 8B) makes distribution extension-first: the active
Quarto extension contributes the project pre-render itself and provisions
`quarto-needs==<extension version>` into a project-local, interpreter-scoped
managed runtime through a standard-library bootstrap — atomic, lock-protected,
offline after the first render — and then invokes the same canonical pre-render
service as the CLI. The contract is rendered by real Quarto (clean first
render, offline second render, spaces-in-path, version-skew isolation,
runtime corruption, concurrent provisioning, and a Quarto-floor gate), the
release workflow rehearses both the CLI and the bootstrap path against
TestPyPI before a production publish that waits on the `pypi` environment's
required reviewer; the first release through that gate, `v0.1.1`, was
published on 2026-09-11 and verified rendering through the extension on
Python 3.10–3.14, the quickstart and a starter template describe the
zero-install path, and the self-hosted model records the slice end to end
with 23 attested tests. The nine pre-existing
fixture-staleness test failures noted when the earlier tasks landed are
resolved; the full suite is green. The declared Quarto 1.6.0 floor has been
verified against a real 1.6.0 binary (contributed pre-render, relative
`quarto run`, provisioning, and a spaces-in-path project), the installed-user
gate now covers DOCX and PDF rendering through the managed runtime, and the
build/twine checks have a local `make check-release-build` path.

---

# Phase 9 — Teaching, self-hosting, and failure scenarios 🚧 (first slice: the broken gallery — ten executable failure fixtures; second slice: suspect-after-change; third slice: interchange-loss and editor-refactor)

`examples/quarto-needs/` increasingly acts as the official engineering model of Quarto-Needs itself. Significant features should update requirements/decisions/implementation/tests/evidence in the same change.

The first slice is `examples/broken/`: ten deliberately failing, fully
self-contained projects whose diagnostics are asserted by
`tests/test_teaching_fixtures.py` — missing evidence, invalid relations
(ghost target, duplicate ID), the relation-typo trap, orphan requirements,
overdue decisions, expired evidence, localization drift, migration
loss, interchange loss, and editor/refactor failures — each one teaching a
different severity relationship to publication.

The second slice is `suspect-after-change`, the one gallery member with no
checked-in directory: a project's `verified-by` edge can stay structurally
valid while the requirement behind it changes meaning, and only comparing
two engineering states catches that. Built dynamically as a two-commit Git
history in `tests/test_teaching_fixtures.py`, reusing the same `suspect
--git` path `test_git_range.py` already exercises, with a copy-paste
reproduction recipe in `examples/broken/README.md`.

The third slice is `interchange-loss` and `editor-refactor`. Both
interchange projections (ReqIF and JSON-LD) now document, inside the
export, exactly which authored details stay behind — source provenance, and
in ReqIF the typed structure of attribute cells — surfaced through
`PROJECTION-NOTE` entries and the `quartoNeedsProjectionNotes` member, so a
consumer reads the loss instead of discovering it. The editor fixture pins
that an LSP rename colliding with an existing ID is refused with the same
canonical diagnostic the engine uses everywhere else.

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
Thin VS Code client ✅
          ↓
ReqIF 1.2 ✅ → JSON-LD ✅ → OSLC RM ✅ (read-only) → Sphinx-Needs/Doorstop/StrictDoc migration ✅
          ↓
Broader migration / external federation
          ↓
Architecture / C4 projections
          ↓
Graph workbench
          ↓
Scale + compatibility + release hardening ✅
```

C4 projection work may advance earlier when it only consumes already-modeled architecture roles, but it must never fork the canonical model.

# Definition of success

Quarto-Needs reaches its intended shape when an engineering change can be authored, reviewed, executed, evidenced, compared, explained, navigated, safely refactored, visualized, published, federated, migrated, and exchanged without any layer inventing a second interpretation of the project.
