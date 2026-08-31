# Phase 5.5 — External service adapters

Status: **two slices in. A read-only GitHub issue projection is implemented end to end: external identity, content-digest provenance, normalization into the same observation shape OSLC federation already uses, and a bounded, GET-only HTTP transport that has been run against the real GitHub API. There is still no cache, query/listing, or reconciliation — those are the next slices, built the same incremental way OSLC's own subsystem was.**

Quarto-Needs treats every external service the same way it treats OSLC: as a read-only, provenance-preserving federation boundary around the canonical engineering graph, never a second semantic authority. Every imported object must preserve external identity, origin, digest/version, retrieval policy, and trust state — the same four guardrails `docs/ROADMAP.md` states for this phase, applied here to GitHub issues as the first external source.

## Why this reuses OSLC's identity model instead of a new one

`ExternalResourceIdentity` and `CachePolicy` (`src/quarto_needs/oslc_rm.py`) turned out to already be source-agnostic in practice: their fields (`resource_uri`, `service_provider_uri`, `digest`, `fetched_at`, `trust_state`, `etag`, `last_modified`) and validation (absolute-URI checks, `sha256:`-prefixed digest format, a fixed trust-state enum) encode nothing OSLC- or RDF-specific. `ExternalRequirementObservation` (`src/quarto_needs/oslc_reconcile.py`) is the same story: `identity`, `title`, `description`, `external_identifier`, and a free-form `attributes` bag is exactly the shape a normalized external issue needs too. `src/quarto_needs/github_issues.py` imports and reuses these types directly rather than defining parallel ones — the "one adapter, one contract" principle the migration adapters (Sphinx-Needs/Doorstop/StrictDoc) already established, applied here to federation instead of migration.

What was **not** reused: `oslc_http.py`'s bounded transport (its media-type allowlist and cache-policy wiring are RDF/OSLC-specific) and `oslc_rdf.py`'s JSON-LD/Turtle/RDF-XML normalization (GitHub's REST API returns plain JSON, not RDF). `src/quarto_needs/github_http.py` is instead a small, independent bounded transport for GitHub — same shape of guarantee (bounded bytes/time/redirects, same-origin redirect enforcement, request-only auth headers), different, `application/json`-only media-type check, and it does share `oslc_http.py`'s fully generic `HttpFetchPolicy` dataclass directly. Duplicating the ~150-line transport mechanics rather than reaching into `oslc_http.py`'s underscore-prefixed internals kept an already-shipped, heavily tested subsystem untouched while this one was still new; a shared internal transport module is a reasonable future consolidation once a third HTTP-based adapter makes the shape of "what's truly generic" concrete rather than a two-data-point guess.

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
- `fetch_github_resource(uri, *, fetch_policy, auth_headers, opener)` (`src/quarto_needs/github_http.py`) — bounded, GET-only HTTP: byte limit (declared `Content-Length` and actual bytes read both enforced), timeout, a fixed redirect budget with same-origin enforcement (an `Authorization` header cannot leak to a redirect target on another host), `401`/`403` → `authentication-required`, `404` → `not-found`, and an `application/json`-only media-type check. `auth_headers` is a request-only input (e.g. `{"Authorization": "Bearer <token>"}`) matching OSLC's own "authentication headers are never persisted" contract; it cannot override the transport's own `Accept`/`User-Agent`. Tested exclusively against a fake, injectable opener (no live network call in the committed suite, mirroring OSLC's own "network-free by design where provider behavior is simulated"), with the cross-origin-redirect and byte-limit checks specifically falsified rather than only asserted.
- `fetch_external_github_issue(owner, repo, number, *, fetched_at, ...)` — composes the transport, identity, and parser above into one read-only fetch-and-normalize call. No caching: every call is a fresh network fetch. Run live against `strictdoc-project/strictdoc` on GitHub (issue #3164, and issue #500 to confirm the pull-request rejection fires against a real PR returned by the same endpoint) — real `ETag`/`Last-Modified` and a real digest came back correctly, not just through the fake-opener suite.

## What is intentionally not implemented yet

1. a persistent, content-addressed cache with historical observations, so a repeated fetch does not re-hit the network every time (`oslc_cache.py` is the precedent);
2. conditional requests (`If-None-Match`/`If-Modified-Since`) — there is nothing to condition against without a cache, so this naturally follows slice 1, not before it;
3. listing/query support (e.g. "every open issue with label X") beyond one issue at a time;
4. a reconciliation step binding an external issue to a canonical Quarto-Needs ID (`oslc_reconcile.py` is the precedent — explicit URI-to-canonical-ID bindings only, never heuristic title/identifier matching);
5. an import-plan step producing reviewed create/update/ignore directives (`oslc_import_plan.py` is the precedent);
6. rate-limit handling (GitHub's REST API returns `403`/`429` with `X-RateLimit-*` headers on exhaustion; today that surfaces only as the generic `authentication-required`/`unavailable` errors, not a distinguished, retry-informing one);
7. self-hosted example integration (a modeled requirement/test/evidence slice demonstrating this end to end, the way OSLC has one).

None of that is guessed at here — each is deferred exactly because OSLC took each as its own reviewed, independently tested slice, and there is no reason to expect a GitHub-specific cache/query/reconciliation/import-plan design to be simpler or safe to rush.

## Regression coverage

```text
tests/test_github_issues.py
tests/test_github_http.py
```

`test_github_issues.py` covers: deterministic resource-URI construction and its validation (empty owner/repo, non-positive issue number); identity construction from real payload bytes with a verified `sha256:` digest; normalization of a real-shaped payload (title, body-as-description, state, html_url, updated_at, labels); `null` body and missing `labels` handled without guessing; rejection of a non-integer `number`, empty `title`, unsupported `state`, missing `html_url`/`updated_at`, non-object JSON; and pull-request rejection falsified by removing the check and confirming the test fails for the right reason, not just asserted.

`test_github_http.py` covers: successful fetch with validators returned, `Authorization` header merging and its protection against overriding `Accept`/`User-Agent`, declared- and actual-byte-limit enforcement (both falsified), same-origin redirect following, cross-origin redirect rejection (falsified), redirect-limit enforcement, `401`/`404` handling, unsupported media type, network-unavailable, and non-HTTP URI rejection.

Both were additionally exercised (not part of the committed suite) against real GitHub API traffic: a fetched real issue payload for the parser, and a full `fetch_external_github_issue` run against `strictdoc-project/strictdoc` for the composed transport-through-normalization path.
