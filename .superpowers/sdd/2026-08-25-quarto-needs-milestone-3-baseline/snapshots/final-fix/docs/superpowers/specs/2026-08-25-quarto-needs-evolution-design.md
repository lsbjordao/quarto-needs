# Quarto-Needs Governance Platform Evolution Design

## Status

Approved in conversation on 2026-08-25. This document is the umbrella design for five independently verifiable implementation milestones.

## Goal

Evolve Quarto-Needs from a strong traceability showcase into a requirements-governance platform inspired by Sphinx-Needs. The result must combine a deterministic domain core, configurable validation and quality gates, semantic change and impact analysis, richer Quarto views, source-code traceability, interoperable exports, and CI reporting.

The existing Aegis IAM example remains the primary executable demonstration. Every milestone must leave it renderable and useful rather than postponing visible value until the end.

## Product decisions

- Combine three delivery styles: establish a minimal canonical foundation, ship a visible end-to-end improvement immediately, and then deepen each subsystem incrementally.
- Keep Python as the reference authority for relationship semantics, queries, metrics, findings, gates, diffs, and impact. Lua may implement only the contract-tested legacy exact-filter subset needed at Pandoc time; JavaScript presents results and never decides governance outcomes.
- Preserve existing `.need` syntax, current shortcodes, and the schema-v1 shape of `.quarto-needs/needs.json` during this evolution.
- Generate complete Pandoc-native content for HTML, PDF, and DOCX. JavaScript is progressive enhancement and never the sole carrier of essential information.
- Use declarative configuration and a bounded query language. Do not execute user-provided Python, Lua, JavaScript, regular expressions, or arbitrary expressions.
- Keep baselines independent of Git so the core also works with archives and other source-control systems.
- Deliver the scope in five milestones with explicit compatibility, test, documentation, and rendering gates.

## Architecture

```text
QMD adapter ---------+
Comment adapter -----+                         +--> query results
Python AST adapter --+--> SnapshotBuilder ----+--> findings and gates
                                           |  +--> metrics and gaps
                                           |  +--> semantic diff and impact
                                           v
                                  AnalysisSnapshot
                                           |
                    +----------------------+----------------------+
                    |                      |                      |
              Quarto projection        exporters             CI reports
                    |                      |                      |
             Pandoc/Lua + HTML      JSON/CSV/SARIF/       summary/artifacts
               enhancement          JUnit/ReqIF
```

The pipeline returns an `AnalysisResult`. A structurally valid result contains one immutable `AnalysisSnapshot` with ordered object records, authored directed relations enriched with semantic-family metadata, provenance, findings, metrics, gate results, configuration identity, and generator metadata. A structurally invalid result contains the collected declarations and located diagnostics but no graph that consumers can mistake for valid. All Python-side consumers receive this same result; Quarto receives its versioned projection. The CLI must not rescan the project for individual commands or exporters.

Required module boundaries are:

- `analysis.py`: analysis orchestration and `AnalysisSnapshot` construction.
- `config.py`: `.quarto-needs.toml` loading, defaults, validation, and profiles.
- `relations.py`: relation catalog, inverse labels, endpoint constraints, coverage semantics, and impact direction.
- `query.py`: safe query AST, named-query resolution, selection, and deterministic sorting.
- `rules.py`: built-in rule protocol and registry.
- `quality.py`: metrics, gaps, quality gates, and gate reports.
- `snapshot.py`: semantic projection, canonical serialization, fingerprints, and baseline I/O.
- `diff.py`: semantic object and relation comparison.
- `impact.py`: policy-aware traversal with explanatory paths.
- `scanners/`: common source-adapter protocol and QMD/comment/Python implementations.
- `exporters/`: common exporter protocol and format-specific serializers.
- `reporting.py`: text, JSON, and CI-oriented report projections.

The documented CLI commands and shortcode APIs remain compatible. `export_graph()` remains a compatibility wrapper that produces the graph used by the current pre-render and Lua pipeline. Undocumented internal Python imports are not compatibility guarantees.

The implementation adds `needs-envelope-v1.schema.json`, `config.schema.json`, `snapshot.schema.json`, `diff.schema.json`, and `impact.schema.json`. The existing object-only `needs.schema.json` remains available under its current path during migration.

## Canonical model and determinism

An internal `ObjectRecord` retains a stable ID, type, title, body, rationale, status, priority, tags, arbitrary declared attributes, and source locations. The ID is author-assigned for authored objects and deterministically generated from path plus qualified symbol for scanner artifacts. The object does not own relations. Parsed `ObjectDeclaration` values may temporarily carry authored relation tokens, but the snapshot extracts those into its single ordered relation collection and derives incoming/outgoing indexes from that collection. The current `EngineeringObject` remains a legacy compatibility DTO for the parser wrappers and v1 writer.

Each snapshot relation preserves authored source, `authored_name`, target, attributes, and provenance exactly once. It also carries the catalog-derived `catalog_name`, semantic family, and endpoint roles. Inverse names are query and display views, not stored duplicate edges. The schema-v1 compatibility writer emits the catalog's explicit `v1_name` and is the only component allowed to repeat relations both under `objects[].relations` and the top-level `relations` collection. In particular, authored `derived-from` retains that token for diagnostics/diff representation but emits the current normalized `derives-from` token in v1 output.

The builder must sort input paths, objects, locations, relations, attributes, findings, and derived collections deterministically. Two analyses of unchanged semantic input must produce byte-identical canonical JSON when generator-version metadata is held constant.

Duplicate IDs must never be silently overwritten. The snapshot builder preserves all conflicting declarations in structural diagnostics and refuses to produce a valid graph or success result. Malformed blocks and unsupported relation forms likewise produce located structural findings. The only invalid baseline form is the explicitly requested diagnostic artifact defined below; it is never accepted as a normal comparison baseline.

Each object has a content fingerprint over identity and authored semantic fields: type, title, body, rationale, status, priority, tags, and declared attributes. Relations are excluded from that fingerprint. Every relation has an authored fingerprint over source, `authored_name`, target, and attributes, plus a semantic fingerprint over family, endpoint roles/IDs, and attributes. With the same configuration, diff uses semantic fingerprints for graph changes and authored fingerprints to identify representation-only changes. The snapshot records a semantic graph fingerprint over object-content, semantic-relation, and configuration fingerprints, plus a separate representation fingerprint over authored relations. All fingerprints exclude line numbers, output `href` values, generated metrics, and other derived data. Moving an unchanged object is reported as relocation, not semantic modification; adding an edge is reported as a relation change, not an object modification.

## Relation catalog

The catalog is the only place that defines relation behavior. Each entry declares:

- canonical name and direct/inverse display labels;
- allowed source and target types;
- minimum or maximum cardinality where applicable;
- whether it contributes to implementation, verification, evidence, mitigation, or another metric;
- the direction used when propagating impact;
- whether the relation may be exposed in the public web projection.

Initial semantic families include `implements`/`implemented-by`, `verifies`/`verified-by`, and `evidences`/`evidenced-by`. The catalog assigns endpoint roles for every authored alias. For example, `CODE -> implements -> REQ` and the existing `REQ -> implemented-by -> COMPONENT` are preserved in their authored form but both normalize to the implementation family with one requirement role and one implementation-artifact role. Metrics query that semantic family without manufacturing another edge. Changing only alias/orientation while preserving the same endpoint roles is an informational representation change, not a semantic relation addition/removal.

Embedded defaults cover every currently accepted relation key—`derives-from`, `derived-from`, `refines`, `decomposes`, `depends-on`, `conflicts-with`, `constrains`, `implements`, `implemented-by`, `verified-by`, `validated-by`, `mitigates`, `justified-by`, `evidenced-by`, and `references`—plus the new inverse authoring forms `verifies` and `evidences`. Current aliases remain accepted.

Impact direction is explicit rather than inferred from graph orientation. Default catalog entries propagate `derives-from`, `refines`, and `depends-on` from target role to source role; implementation and verification families propagate from requirement role to artifact role; `conflicts-with` propagates both ways; and `mitigates` propagates from risk role to mitigation role. Configuration may override those defaults with `source_to_target`, `target_to_source`, `both`, or `none`.

## Configuration and safe queries

The optional project configuration is `.quarto-needs.toml`. Embedded defaults preserve current behavior when the file is absent. Python 3.10 uses the `tomli` backport, declared conditionally in package dependencies; Python 3.11 and newer use `tomllib`. No second configuration syntax is introduced.

Configuration may declare:

- object types, statuses, priorities, and required attributes;
- relation definitions, endpoint rules, cardinality, and inverse labels;
- rule severity overrides;
- named safe queries;
- coverage thresholds and quality gates;
- impact traversal policies;
- scanner roots, include globs, and excludes;
- publication allowlists and redaction rules;
- execution profile: `advisory`, `default`, or `strict`.

The query model is a typed AST with a maximum nesting depth of 10 and at most 100 clauses. Initial operators are `eq`, `in`, `contains`, `exists`, `missing`, `all`, `any`, and `not`. String comparison is Unicode case-folded; `in` compares a scalar against a set, while `contains` performs collection membership or string substring matching. There is no implicit string/number/boolean coercion. Missing attributes are distinct from configured `null` and empty values. Queryable fields are `id`, `title`, `type`, `status`, `priority`, `tags`, and schema-declared `attributes.<name>`. A relation clause declares a catalog relation, `in`, `out`, or `either` direction, and `exists` or `missing`. Field names, relation names, directions, and operators are validated against allowlists. There is no `eval`, arbitrary regular expression, module loading, or free access to Python/Lua data structures.

A named TOML query uses nested inline tables and an optional stable sort, for example:

```toml
[queries.approved-high-unverified]
all = [
  { field = "status", op = "eq", value = "approved" },
  { field = "priority", op = "in", values = ["high", "critical"] },
  { relation = "verified-by", direction = "out", op = "missing" },
]
sort = ["priority:asc", "id:asc"]
```

Sort fields use the same allowlist, priority uses the configured rank, and ID is the implicit final tie-breaker. Unknown fields, type mismatches, invalid directions, excessive depth, and excessive clause counts are configuration errors rather than empty matches.

Relation clauses operate on catalog views relative to the selected object. Consequently, `relation = "verified-by", direction = "out"` matches both an authored `REQ -> verified-by -> TEST` edge and the semantic inverse view of an authored `TEST -> verifies -> REQ` edge.

Python is the reference evaluator. During pre-render it materializes every configured named query as an ordered ID set for Lua. Shortcodes accept named queries but not inline complex ASTs. Existing exact filters (`ids`, `types`/`type`, `status`, `priority`, and `tags`) remain dynamic in Lua and are intersected with the materialized named-query set when both are supplied. Lua implements only this legacy exact-filter/sort subset; shared conformance vectors generated from the Python evaluator must produce identical results in Lua.

## Rules, findings, metrics, and gates

Built-in rules implement a stable protocol and return structured findings with code, severity, message, object ID, precise source location, help text, properties, and a stable fingerprint. Configuration enables or disables rules and changes supported severities without loading executable plugins.

Initial governance coverage includes:

- duplicate IDs and unknown targets;
- required attributes and rationale;
- allowed relation endpoints and cardinality;
- approved requirements without implementation or verification;
- approved or passed tests without evidence;
- high risks without mitigation;
- orphaned objects;
- expired evidence when an expiry attribute is configured.

Metrics distinguish their scope, denominator, and strength. At minimum, reports show both the whole catalog and the `status = approved` requirements scope, with breakdowns by type, status, priority, and named query. The term *baseline* is reserved for a saved snapshot; the default named query for the approved scope is `approved-requirements`.

Coverage is separated into:

- implementation trace coverage: a valid implementation-family relation reaches an existing allowed endpoint;
- effective implementation coverage: that endpoint's status is allowed by policy, excluding `disapproved`, `rejected`, `failed`, and `deprecated` by default;
- verification trace coverage: a valid verification-family relation reaches an existing test endpoint;
- successful verification coverage: at least one related test has configured successful status, `passed` by default;
- evidence coverage: a successfully verified test has at least one allowed, non-expired evidence endpoint.

The legacy `coverage()` wrapper retains its current trace-based keys and behavior. New reports expose the stronger metrics explicitly. The dashboard displays precomputed values only; Lua and JavaScript do not recompute coverage.

Initial quality gates support finding counts, trace/effective implementation percentages, trace/successful verification percentages, evidence coverage, risk mitigation, and regressions relative to a baseline. Default policies require zero structural errors and allow semantic warnings unless configured otherwise. Example-project strict gates require every approved requirement, including every approved high/critical requirement, to have effective implementation and successful verification; passed tests must have active evidence, and high risks must have mitigation.

## Baseline, semantic diff, and impact

`quarto-needs baseline create` writes `baselines/quarto-needs.json` by default as a canonical, versioned snapshot. Baseline creation refuses structurally invalid input unless `--allow-invalid` is explicitly supplied. That option writes a diagnostic artifact marked `valid: false`, preserving declarations and findings for `baseline inspect`; it is never accepted by `diff` or `impact`, because duplicate IDs and other structural failures make graph comparison ambiguous. Git is not required.

Diff results classify:

- added and removed objects;
- semantic modifications by field;
- added and removed relations;
- source relocation without semantic change;
- findings, metrics, and gate regressions.

Automatic rename detection is excluded from the initial release because it is inherently heuristic. A changed ID is reported as removal plus addition.

Impact analysis traverses the union of the before and after graphs so removed nodes and edges remain explainable. Every impacted result includes the originating change, direct or transitive classification, distance, traversed relations, path, and configured priority. The first implementation does not invent an opaque risk score; paths and policy decisions remain auditable.

Snapshots store a configuration fingerprint: SHA-256 over the canonical merged configuration, embedded defaults, relation-catalog version, and rule-set version, excluding the configuration file's path. When fingerprints differ, default `diff` compares authored object content and authored relation tuples only, emits `configuration-changed`, and suppresses semantic-relation, finding, metric, and gate deltas. This prevents a catalog-only family/role change from appearing as a project edge removal/addition. `diff --recompute-with current` re-evaluates the baseline's authored relations through the current catalog so semantic comparison is valid again; the baseline's stored derived results (findings, metrics, gates) are never re-derived, so those deltas stay suppressed until both sides are produced under the same configuration and reference date. `impact` rejects mismatched configuration fingerprints unless the same recomputation option is supplied, ensuring one relation policy governs the entire traversal.

### Milestone 3 design decisions

The following three decisions refine the contract above without altering it. Each was open because this specification did not address it.

**The reference date is a first-class comparison axis.** `reference_date()` is a semantic input, not formatting metadata: evidence expiry (REQ015) and evidence coverage both depend on it, so an unchanged project legitimately reports different coverage on different days. A baseline therefore records the reference date it was computed under, alongside its configuration fingerprint. When the two differ, `diff` emits `reference-date-changed` and suppresses the date-derived deltas — evidence coverage and REQ015 findings — exactly as it does for a changed configuration fingerprint, and `impact` rejects the mismatch. As with a configuration change, `--recompute-with current` re-resolves the baseline's authored relations but cannot re-derive its stored date-derived results, so those deltas stay suppressed until both sides share a reference date. Determinism is consequently defined as byte-identical output for a fixed configuration and a fixed reference date; `SOURCE_DATE_EPOCH` remains the way to fix the latter. Fingerprints continue to exclude the reference date, which is an input to derived data rather than authored content.

This is distinct from the exporter rule on wall-clock timestamps. That rule governs formatting metadata, which is omitted or pinned to `SOURCE_DATE_EPOCH` with a `1970-01-01T00:00:00Z` fallback. The reference date is an analysis input whose value changes results, so it is recorded and compared rather than omitted; a 1970 fallback would make every expiry check meaningless.

**Relocation is keyed on the declaring file.** A relocation record is emitted when an object's declaring file changes, and it carries the file and line before and after. A line-only shift within the same file produces no record: fingerprints already exclude line numbers, and emitting a record for every object below an inserted paragraph would make relocation the loudest and least informative category in the diff. Moving a need between pages is an authored fact; being pushed down three lines is not.

**Baseline creation refuses to overwrite.** `baseline create` fails with exit code 2 when its destination already exists, unless `--force` is supplied. An accidentally overwritten baseline is unrecoverable without version control, which this project does not assume.

## Quarto experience

Python writes the precomputed projection. Lua loads and caches it per Pandoc process, resolves links according to the output format, and creates semantic Pandoc AST. Local JavaScript progressively enhances only HTML.

Need cards retain text-bearing colored badges and gain grouped outgoing relations, grouped backlinks using inverse labels, relevant attributes, provenance, associated findings, and an HTML inspector action. The following shortcodes are added without removing existing ones:

```qmd
{{< need-backlinks IAM-FUN-001 >}}
{{< need-inspector IAM-FUN-001 >}}
{{< need-dashboard query="approved-requirements" >}}
{{< need-graph query="approved-high" >}}
```

The established visual meanings remain stable: approved/passed are green; disapproved/rejected/failed are red; in-review is amber; draft is gray; implemented is blue; verified is teal; critical priority is dark red; high priority is orange; medium is blue; and low is gray. Text is always present, so color is supplemental.

The dashboard presents whole-catalog and approved-requirements coverage, implementation and verification gaps, tests without evidence, unmitigated risks, findings by severity, and distributions by type, status, and priority. Every KPI names its denominator and links to the underlying filtered objects.

The HTML inspector is an accessible keyboard-operated dialog. Its non-JavaScript and PDF/DOCX representation is an ordinary section, list, or table containing the same essential information.

`need-graph` retains a static PNG and accessible edge table for every format. HTML progressively adds a pinned, locally vendored Cytoscape.js bundle with search, zoom, filters, node selection, and inspector integration. The fallback is hidden only after successful initialization. Large queries are capped by configurable node and edge limits and display guidance to narrow the query instead of silently truncating results.

The browser receives only a reduced public projection: ID, title, type, status, priority, allowed tags, resolved links, and publishable relations. Body, local paths, source locations, and undeclared attributes are excluded by default. The existing rendered document remains governed by Quarto content inclusion; this reduced projection specifically prevents the interactive assets from leaking additional graph data.

## Source adapters and annotations

All adapters implement a common interface that returns objects, relations, findings, and provenance in a `ScanBatch`.

The first scanner release includes:

- the existing QMD adapter;
- a generic comment-annotation adapter enabled only for explicit globs;
- a Python `ast` adapter that associates annotations with modules, classes, functions, and tests;
- a file-level fallback when no symbol can be resolved.

The Python AST adapter is authoritative for configured `.py` files. The generic comment adapter skips those files by default; if an author explicitly enables both, the merge key deduplicates identical observations while retaining every source location.

Supported annotations initially include `@implements`, `@verifies`, and `@evidences`. Generated source-object IDs derive from normalized project-relative paths plus qualified symbols, never line numbers. Line numbers are locations only. Duplicate observations preserve all provenance while producing one canonical relation.

The annotation grammar is one directive per standalone comment or docstring line:

```text
@implements IAM-FUN-001, IAM-FUN-002
@verifies IAM-FUN-003
@evidences IAM-TST-001; IAM-TST-002
```

Targets use the same ID grammar as `.need` blocks and are separated by commas or semicolons. Empty targets, unknown verbs, malformed IDs, and unknown referenced objects produce located scanner findings. Inline trailing comments are ignored in the initial release. For Python, a contiguous leading comment immediately before a symbol or a line in that symbol's docstring attaches to the module, class, function, or test; otherwise it attaches to the file fallback. Python source decoding follows `tokenize.open()` and PEP 263; the generic adapter defaults to UTF-8 and reports a located decoding failure.

Renaming a source path or qualified symbol changes the generated ID and is therefore reported as removal plus addition. Automatic code-symbol rename inference is excluded alongside requirement-ID rename inference.

Scanners exclude `.venv`, `_book`, dependency, vendor, cache, and generated directories. They do not follow symlinks outside the project root. Tree-sitter and deep language-specific scanners are deferred until the annotation contracts prove stable.

## CLI and failure semantics

Existing `scan`, `check`, `coverage`, `trace`, and `export` commands remain available. New command families are:

```text
quarto-needs quality
quarto-needs query <name>
quarto-needs baseline create
quarto-needs baseline inspect <baseline>
quarto-needs diff <baseline>
quarto-needs impact <baseline>
quarto-needs export --format <json|csv|sarif|junit|markdown|reqif>
```

`scan`, `check`, `coverage`, `trace`, `quality`, `query`, `baseline create`, `baseline inspect`, `diff`, and `impact` all support `--format text|json`. `export` uses the artifact formats shown above. Exit codes are stable:

- `0`: analysis completed and applicable gates passed;
- `1`: validation or policy failure;
- `2`: invalid command usage or configuration;
- `3`: operational I/O, scanner, or serialization failure.

Profiles control semantic enforcement only:

- `advisory`: emits semantic findings and gate failures without returning exit code 1;
- `default`: fails for configuration, parsing, or structural graph errors;
- `strict`: also fails configured semantic gates and regressions.

Invalid configuration, unrecoverable parsing, duplicate IDs, an unusable relation graph, and operational failure stop every profile, including `advisory`. Other findings remain visible in the generated document. CI artifacts are still written when a quality gate returns exit code 1; operational failures return exit code 3 and report which artifacts could not be produced.

## Exporters

Every exporter consumes `AnalysisSnapshot` or a typed report derived from it. Output is deterministic and written atomically. Wall-clock timestamps are omitted; formats requiring a timestamp use `SOURCE_DATE_EPOCH`, falling back to `1970-01-01T00:00:00Z` when the variable is absent.

- JSON preserves the current schema-v1 graph projection for the Quarto adapter and existing consumers. Existing keys and meanings do not change; additive governance data is placed under an `extensions.quartoNeeds` object so tolerant v1 consumers can ignore it. New internal baseline and report schemas are separately named and versioned.
- CSV produces `objects.csv`, `relations.csv`, and `findings.csv`, with spreadsheet-formula injection protection.
- SARIF targets version 2.1.0 and maps stable findings, locations, help, properties, and fingerprints into the GitHub-supported subset.
- JUnit creates one test case per evaluated quality gate and treats warnings according to configured policy.
- Markdown produces a concise CI summary of changes, coverage deltas, failed gates, and high/critical impact.
- ReqIF targets OMG ReqIF 1.2 with deterministic XML IDs, one specification-object type per configured need type, specification relations for graph edges, and a hierarchy based on source file and order.

Initial ReqIF body output is conservative text. Rich XHTML, `.reqifz`, importing, and round-trip synchronization are deferred. The official OMG ReqIF 1.2 XSD set is vendored for tests with its source URL, license notice, and SHA-256 checksums. Generated output must validate with `lxml` and be parsed by a version of the independent StrictDoc `reqif` library pinned in test constraints; tests assert expected specification, object, type, attribute, and relation counts.

## CI design

The GitHub Actions workflow is split into:

1. `core`: Python 3.10, 3.11, 3.12, 3.13, and 3.14, unit tests, CLI tests, schemas, deterministic fixtures, and packaging.
2. `quarto`: pinned Quarto, Chromium, and a pinned TeX environment, running HTML, DOCX, and PDF smoke tests without conditional skips.
3. `quality`: strict gates and JSON, CSV, SARIF, JUnit, and Markdown artifact generation.

Artifacts are uploaded with `if: always()` when they exist. The workflow publishes a step summary and uploads SARIF in a separate least-privilege step. Persistent PR comments are opt-in to avoid spam and write permissions. The workflow must not use `pull_request_target` to execute untrusted pull-request code.

## Error handling and security

Configuration errors, structural graph errors, policy failures, and operational failures remain distinct typed outcomes. User-facing diagnostics include location and remediation when known. No renderer should replace a meaningful error with an empty view.

Security tests cover path normalization, project-root containment, symlink escape, unsafe config constructs, browser projection redaction, HTML/Pandoc escaping, XML entity handling, CSV formula injection, and offline/CSP-compatible assets. Exporters never embed absolute local paths unless explicitly requested for a local diagnostic artifact.

Vendored Cytoscape.js and ReqIF schema assets record upstream URL, exact version or content hash, license, and notice text in the repository. CI verifies their checksums so the offline build cannot silently drift.

## Testing strategy

- Unit tests cover canonicalization, relation inverses, endpoint validation, safe query semantics, rules, metrics, gates, fingerprints, diff classification, and impact paths.
- Contract tests keep Python, Lua, CLI, and schema interpretations aligned.
- Golden tests assert byte-identical JSON, CSV, SARIF, JUnit, Markdown, and ReqIF output for fixed fixtures.
- CLI integration tests cover single analysis per execution, stdout/stderr separation, exit codes, overwrite behavior, and partial-artifact failure.
- Render tests cover need cards and every shortcode in HTML, DOCX, and PDF; CI provisions every required renderer.
- Chromium tests cover table sorting, dashboard filtering, dialog focus/keyboard behavior, graph fallback, graph initialization, and no-JavaScript operation.
- Security tests cover the cases listed above.
- Synthetic graph benchmarks cover at least 1,000 objects and 5,000 relations. On the standard GitHub-hosted Ubuntu runner, parsing plus core analysis must complete within 5 seconds and use no more than 256 MiB for that fixture. To preserve a readable universal fallback, the interactive/static graph pair defaults to at most 100 nodes and 300 edges per view; exceeding either limit produces a visible narrowing message and no partial graph.

## Milestones and acceptance gates

### Milestone 1: Canonical foundation and visible backlinks

Deliver deterministic analysis, duplicate-safe graph construction, relation catalog, v1-compatible output, cached Lua loading, format-aware links, and outgoing/backlink sections on need cards.

Acceptance requires existing tests plus new determinism, relation, compatibility, and three-format rendering tests.

### Milestone 2: Configuration, queries, rules, and dashboard

Deliver `.quarto-needs.toml`, named queries, configurable built-in rules, structured findings, scoped metrics/gaps, quality reports, inspector, and dashboard.

Acceptance requires query safety/limits, metric denominator checks, profile behavior, accessibility checks, and static fallbacks in HTML without JavaScript, DOCX, and PDF.

### Milestone 3: Baseline, diff, and impact

Deliver canonical baseline files, semantic fingerprints, classified diffs, relocation handling, union-graph impact traversal, explanatory paths, and CLI/report projections.

Acceptance requires stable baseline round trips, no semantic modification for reordered or relocated-only content, an explicit relocation record when the source moves, correct removal impact, and explicit paths for every impact result.

### Milestone 4: Exporters, scanners, and CI

Milestone 4A delivers CSV, SARIF, JUnit, Markdown, strict CI gates, workflow artifacts, and PR step summaries. Milestone 4B then delivers comment/Python scanners and annotation-derived traceability. Each submilestone has its own implementation plan and acceptance run so exporter/CI work can be accepted independently from scanner behavior.

Milestone 4A acceptance requires schema/golden validation, stable exit codes, and artifact preservation on policy failure. Milestone 4B acceptance requires the annotation grammar, safe scanner boundaries, deterministic generated IDs, and natural inverse coverage from annotations.

### Milestone 5: Interactive graph, ReqIF, and hardening

Milestone 5A delivers the local interactive graph, public projection, node inspector integration, and large-graph controls. Milestone 5B delivers ReqIF 1.2. Milestone 5C performs the final security, accessibility, and performance hardening. Each submilestone has an independent implementation plan and acceptance run.

Milestone 5A acceptance requires equivalence of essential information with JavaScript disabled, offline operation, projection-redaction tests, and keyboard navigation. Milestone 5B requires OMG XSD validation and successful parsing/assertions through the pinned StrictDoc `reqif` library. Milestone 5C requires the complete security suite and synthetic-graph budgets.

Every milestone also requires the full existing suite to pass, the Aegis IAM book to render in HTML/DOCX/PDF, generated outputs to remain deterministic, and README/architecture/regeneration instructions to be current.

This umbrella specification fixes the shared contracts for all five milestones. Implementation planning is deliberately decomposed: the next plan covers Milestone 1 in detail, and each later milestone or named submilestone receives its own plan after the previous acceptance gate passes. Those plans may refine task order but may not change this approved architecture without a documented design amendment.

## Aegis IAM showcase expansion

The example will demonstrate all new capabilities rather than merely mention them. It gains:

- a checked-in semantic baseline and a documented changed-state scenario;
- direct and transitive impact examples;
- named queries for approved, high-priority, unverified, evidence, and risk views;
- configurable passing and intentionally failing gate fixtures, with the default published book passing;
- annotated sample application code and tests;
- dashboard, inspector, backlinks, and interactive/static graph pages;
- a dedicated integrations page with exact commands, plus build-generated JSON, CSV, SARIF, JUnit, Markdown, and ReqIF artifacts exercised by fixtures;
- clear regeneration instructions for development, preview, all formats, baselines, reports, and CI-equivalent checks.

Intentional disapproved, rejected, failed, draft, and in-review objects remain so every badge state is visible. The `status = approved` requirements scope must remain fully traced; saved baselines are separate lifecycle artifacts.

## Compatibility and migration

- Current `.need` blocks and shortcode calls require no migration.
- Current exact filtering semantics remain supported.
- `.quarto-needs/needs.json` retains its existing schema-v1 keys and relation duplication where required by current consumers; the compatibility writer validates consistency, and new governance fields are namespaced under `extensions.quartoNeeds`.
- New baseline, diff, impact, SARIF, JUnit, and ReqIF documents use their own explicit schema or format versions.
- Deprecations, if introduced later, produce findings for at least one release before removal.

Before the first internal refactor, tests freeze a representative current Aegis v1 payload and add an envelope schema describing the actual top-level document. Compatibility means preserved required keys, value types, relation orientation, legacy name normalization (including `derived-from` to `derives-from`), backlink meaning, `href` behavior, and legacy coverage keys; it does not preserve the old nondeterministic byte order. Additive `extensions.quartoNeeds` data is optional in the v1 envelope.

| Existing surface | Compatibility guarantee |
|---|---|
| `.need` authoring syntax | Existing valid blocks parse without edits. |
| `parse_qmd(path, root=None)` | Signature and `list[EngineeringObject]` return remain; valid-object fields retain meaning. |
| `parse_project(root, files=None)` | Signature and return remain; output becomes deterministically ordered. |
| `RequirementsGraph.build(objects)` | Valid unique-ID inputs retain behavior; duplicate IDs raise a located `DuplicateIdError` instead of overwriting. |
| `validate(objects, require_rationale_for=None)` | Signature, list return, and existing rule codes remain; `Finding.to_dict()` receives additive fields. |
| `coverage(objects)` | Existing keys and trace-based calculations remain as a deprecated compatibility projection. |
| `export_graph(path, objects, findings)` | Signature, `None` return, and v1 envelope remain; output becomes deterministic and atomic. |
| `export_lua_index(path, objects)` | Signature and generated lookup semantics remain. |
| `cli.build(root, quiet=False)` | Signature and integer result remain; implementation performs one analysis pass. |
| Existing CLI commands and shortcodes | Names and existing options remain; additive output and options are allowed. |

## Deferred work and non-goals

- Arbitrary Python/Lua rule plugins or expression evaluation.
- Automatic rename detection in semantic diffs.
- Git as a mandatory baseline provider.
- Tree-sitter language coverage before scanner contracts stabilize.
- ReqIF importing, round-trip synchronization, rich XHTML, and `.reqifz` in the initial ReqIF milestone.
- Client-side mutation of requirements or governance state.
- Mandatory persistent PR comments or workflows with broad write permissions.
- Full Sphinx-Needs source-syntax emulation. Capability parity and leadership are
  tracked by the
  [capability evolution amendment](2026-08-26-quarto-needs-capability-evolution.md).

## Format references

- [OMG Requirements Interchange Format 1.2 and normative schemas](https://www.omg.org/spec/ReqIF/1.2/)
- [StrictDoc ReqIF parser](https://github.com/strictdoc-project/reqif)
