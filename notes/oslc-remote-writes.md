# OSLC remote writes

**Status:** delivered for update, create and delete, with a review-first CLI.
The roadmap kept every POST/PUT/PATCH/DELETE deferred until eight contracts
were explicit; they are stated here, and the three operations are implemented
under them. Only automatic destructive behaviour remains deferred: a delete
is never derived from a diff, only named by a reviewer.

## The eight contracts

1. **Staleness.** A write plan is built from observations with a recorded
   `fetched_at` and ETag. A request is only built while the binding and the
   validator are still the ones the plan reviewed; the plan records the body
   digest and the precondition, and a previous write audit can be supplied so
   an unchanged payload is skipped rather than rewritten.
2. **Conflict.** A `412 Precondition Failed` or `409 Conflict` from the
   provider stops the run at that request. The response is recorded in the
   audit; no automatic merge, retry, or "force" exists.
3. **Authored-file placement.** Remote writes never touch authored files.
   Placement of authored content remains the reviewed import-apply contract;
   this slice only sends what a reviewer already published.
4. **Atomicity.** Atomicity is per request. The provider either accepted or
   rejected one bounded request; there is no attempt to stage a transaction
   across resources.
5. **Rollback.** A remote write cannot be un-written. The contract is
   therefore ordered, stop-on-first-failure, and fully audited: every earlier
   success and the failing request are recorded so the exact state is known
   and a human can decide what to compensate. Nothing is retried automatically.
6. **Optimistic concurrency.** Every request carries `If-Match` with the ETag
   of the cached observation that was reconciled. An observation without an
   ETag produces no request — an unconditional overwrite is outside the
   contract.
7. **Authorization.** The credential is supplied per run, is never stored in
   the project, is never written to the audit or the plan, and rides on the
   request only. Writes require `https` (localhost fixtures excepted).
8. **Audit.** Every application writes an `oslc-write-audit-v1` document —
   including when it stops early — naming each request's URI, canonical ID,
   precondition, body digest and outcome (status, response ETag, or error).
   The audit is written before the failure propagates.

## Slice scope

- `oslc_write.py`: builds a reviewed plan for the three operations.
  **Updates** need a trusted bound observation with an ETag and a payload
  that differs from the recorded audit. **Creates** are only the canonical
  IDs a reviewer names, target an explicit collection URI, carry a
  deterministic advisory `Idempotency-Key`, and refuse an ID that is already
  bound. **Deletes** are only the canonical IDs a reviewer names, need a
  single trusted bound observation with an ETag, and never follow from a
  diff. The payload is conservative: identifier, title, description, object
  type, status, rationale, attributes, canonical ID and graph fingerprint,
  and never `@id`, `@type` or `serviceProvider`.
- `oslc_write_http.py`: one bounded request at a time (`PUT`, `POST`,
  `DELETE`), no redirects followed, request and response byte caps,
  request-only credentials, `https` required.
- `quarto-needs oslc write`: review-first CLI over an observation export and
  an explicit bindings map; `--apply` sends and always writes the audit.
- Remaining: nothing destructive is automatic, and there is no retry or merge
  policy beyond stop-on-first-failure — that is deliberate.
