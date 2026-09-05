# Runtime: federation and import

How external data (OSLC requirements, GitHub issues, Doorstop migrations) is admitted — or not — into the canonical graph.

## Trust state machine

The one genuine state machine in the codebase governs externally federated observations, in `external_trust.py`:

```
unverified → trusted
unverified → rejected
unverified → stale
trusted    → rejected | stale
stale      → trusted | rejected
rejected   → unverified
```

An external observation starts `unverified`. It never becomes part of the canonical engineering graph just by being fetched — trust, staleness, and rejection are explicit, inspectable states, not incidental cache behavior.

## Federation flow (OSLC / GitHub)

1. **Fetch** — a bounded, read-only request against the external provider (no recursive crawling beyond what discovery requires).
2. **Normalize** — provider-specific shapes (OSLC resource shapes, GitHub issue JSON) are normalized into a common observation representation, preserving individual provenance per item.
3. **Reconcile** — external identity is matched (or not) against canonical objects; conflicts are surfaced, not silently resolved.
4. **Admit or hold** — reconciled observations remain external until an explicit action (import/apply) brings them into the canonical graph as real `.need` declarations.

## Import/migration flow (Doorstop and similar)

Import only ever proceeds through a **plan → preflight → write → rescan → rollback-on-failure** sequence:

- A plan is computed first and must pass preflight checks (no unsafe operations, no stale content) before any file is written.
- After writing, the project is rescanned through the normal parse/analyze pipeline — the same one authored content goes through — so imported content is validated exactly like anything else.
- A failed write rolls back rather than leaving the project in a partially migrated state.

## Why this boundary is strict

`RISK-005`/`RISK-012` (federation credentials, stale cache, rate limits/pagination) exist precisely because external systems are outside Quarto-Needs's control. Keeping federation read-only and provenance-bound, and keeping import staged with rollback, means a bad external fetch or a failed migration can never corrupt the canonical graph silently.
