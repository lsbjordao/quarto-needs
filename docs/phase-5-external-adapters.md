# Phase 5.5 — External service adapters

Status: **first slice only. A read-only, network-free GitHub issue projection is implemented: external identity, content-digest provenance, and normalization of a fetched issue payload into the same observation shape OSLC federation already uses. There is no bounded HTTP transport, cache, query, or reconciliation yet — those are the next slices, built the same incremental way OSLC's own subsystem was.**

Quarto-Needs treats every external service the same way it treats OSLC: as a read-only, provenance-preserving federation boundary around the canonical engineering graph, never a second semantic authority. Every imported object must preserve external identity, origin, digest/version, retrieval policy, and trust state — the same four guardrails `docs/ROADMAP.md` states for this phase, applied here to GitHub issues as the first external source.

## Why this reuses OSLC's identity model instead of a new one

`ExternalResourceIdentity` and `CachePolicy` (`src/quarto_needs/oslc_rm.py`) turned out to already be source-agnostic in practice: their fields (`resource_uri`, `service_provider_uri`, `digest`, `fetched_at`, `trust_state`, `etag`, `last_modified`) and validation (absolute-URI checks, `sha256:`-prefixed digest format, a fixed trust-state enum) encode nothing OSLC- or RDF-specific. `ExternalRequirementObservation` (`src/quarto_needs/oslc_reconcile.py`) is the same story: `identity`, `title`, `description`, `external_identifier`, and a free-form `attributes` bag is exactly the shape a normalized external issue needs too. `src/quarto_needs/github_issues.py` imports and reuses these types directly rather than defining parallel ones — the "one adapter, one contract" principle the migration adapters (Sphinx-Needs/Doorstop/StrictDoc) already established, applied here to federation instead of migration.

What was **not** reused: `oslc_http.py`'s bounded transport (its media-type allowlist and cache-policy wiring are RDF/OSLC-specific) and `oslc_rdf.py`'s JSON-LD/Turtle/RDF-XML normalization (GitHub's REST API returns plain JSON, not RDF). Those would need their own generalization pass, deferred until an actual GitHub HTTP transport slice makes the question concrete rather than speculative.

## What is implemented

- `github_issue_resource_uri(owner, repo, number)` — the deterministic GitHub REST API URL identifying one issue (`https://api.github.com/repos/{owner}/{repo}/issues/{number}`), used as `ExternalResourceIdentity.resource_uri`.
- `build_github_issue_identity(owner, repo, number, *, payload_bytes, fetched_at, trust_state="unverified", etag=None, last_modified=None)` — builds the identity from the *exact bytes actually fetched* (the digest is over `payload_bytes`, never a re-serialization of parsed fields), matching how OSLC's own provenance model works.
- `parse_external_github_issue(payload, *, identity)` — normalizes a raw GitHub issue JSON payload into an `ExternalRequirementObservation`. Validated against a real payload fetched live from `strictdoc-project/strictdoc`'s issue tracker, not only synthetic fixtures:
  - `number` (must be a real `int`, not a numeric string) → `external_identifier` (data only — never promoted into a canonical ID by this parser, the same non-negotiable boundary OSLC's own reconciliation enforces);
  - `title` (required, non-empty) → `title`;
  - `body` (`null` treated as empty) → `description`;
  - `state` (must be `"open"` or `"closed"`; anything else is rejected rather than guessed) → `attributes["state"]`;
  - `html_url`, `updated_at` (both required) → `attributes["htmlUrl"]` / `attributes["updatedAt"]`;
  - `labels` (a list of label objects; `name` extracted, sorted, deduplication left to the caller) → `attributes["labels"]`;
  - a payload carrying a `pull_request` key is rejected outright (`GitHubIssueError`) — GitHub's issues endpoint returns pull requests too, and treating one as a requirement-shaped issue would misrepresent a fundamentally different artifact.

## What is intentionally not implemented yet

1. bounded, GET-only HTTP transport to actually fetch an issue (byte/time/redirect limits, conditional requests using `etag`/`last_modified`, same-origin redirect enforcement) — `oslc_http.py` is the precedent to generalize or parallel, not yet decided;
2. a persistent, content-addressed cache with historical observations (`oslc_cache.py` is the precedent);
3. listing/query support (e.g. "every open issue with label X") beyond one issue at a time;
4. a reconciliation step binding an external issue to a canonical Quarto-Needs ID (`oslc_reconcile.py` is the precedent — explicit URI-to-canonical-ID bindings only, never heuristic title/identifier matching);
5. an import-plan step producing reviewed create/update/ignore directives (`oslc_import_plan.py` is the precedent);
6. any authentication handling (a real fetch will need a token; none of this slice touches credentials);
7. self-hosted example integration (a modeled requirement/test/evidence slice demonstrating this end to end, the way OSLC has one).

None of that is guessed at here — each is deferred exactly because OSLC took each as its own reviewed, independently tested slice, and there is no reason to expect a GitHub-specific transport/cache/query/reconciliation/import-plan design to be simpler or safe to rush.

## Regression coverage

```text
tests/test_github_issues.py
```

Covers: deterministic resource-URI construction and its validation (empty owner/repo, non-positive issue number); identity construction from real payload bytes with a verified `sha256:` digest; normalization of a real-shaped payload (title, body-as-description, state, html_url, updated_at, labels); `null` body and missing `labels` handled without guessing; rejection of a non-integer `number`, empty `title`, unsupported `state`, missing `html_url`/`updated_at`; and pull-request rejection falsified by removing the check and confirming the test fails for the right reason, not just asserted. Additionally exercised (not part of the committed suite) against a real issue payload fetched live from `strictdoc-project/strictdoc` on GitHub.
