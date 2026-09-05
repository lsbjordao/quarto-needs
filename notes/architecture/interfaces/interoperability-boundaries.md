# Interface: interoperability boundaries

What crosses the trust boundary between Quarto-Needs's canonical graph and the outside world, and how.

## The boundary

External data (OSLC RM resources, GitHub issues, Doorstop documents) never joins the canonical `AnalysisSnapshot` automatically. It is fetched, normalized, and reconciled as a separate, provenance-bearing observation model first — see [`runtime/federation-and-import.md`](../runtime/federation-and-import.md) for the flow and the `unverified/trusted/rejected/stale` state machine (`external_trust.py`).

## Interchange formats are adapters, not systems

ReqIF, JSON-LD, SARIF, and evidence envelopes are export/import *formats*, not external systems Quarto-Needs depends on. They read from or write to the canonical snapshot/public projection; they do not carry their own semantics back into the graph. This is why they are not drawn as boxes in [`context.md`](../context.md).

## What is preserved crossing the boundary

- **Identity** — the external system's own identifier for the resource.
- **Origin** — which provider/system the observation came from.
- **Version/digest** — enough to detect that the external resource has changed since it was last observed (staleness).
- **Trust state** — explicit, not implied by presence in a cache.
- **Retrieval policy** — read-only; Quarto-Needs does not write back to OSLC/GitHub as a side effect of federation.

## Reconciliation, not silent merge

When an external observation's identity plausibly matches a canonical object, reconciliation surfaces the match (and any conflicting fields) for a human or an explicit import step to resolve — it does not overwrite canonical attributes as a side effect of fetching.
