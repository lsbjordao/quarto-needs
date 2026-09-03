# Architecture View Projections Plan

## Goal

Extend Quarto-Needs beyond C4 without creating renderer-specific architecture models.

## Completed slice

- Add a deterministic `graphviz_render.dot_source` adapter over `GraphProjection`.
- Publish `.dot` siblings for the default and named graph views.
- Keep JSON as the browser-facing contract and DOT as optional interchange output.
- Preserve Mermaid, PlantUML, Structurizr, and D2 artifacts unchanged.
- Validate escaping, determinism, Graphviz syntax, stale-file cleanup, and integration.

## Next slices

1. Traceability projection: requirement -> architecture element -> source module -> test/evidence, with HTML/table/CSV/DOT outputs.
2. Lifecycle/state projection: derive state transitions only from explicit status/trust/evidence facts already present in the snapshot.
3. Sequence projection: add only after the model can represent ordered interactions without inferring execution order from arbitrary relation order.
4. Deployment projection: introduce deployment concepts only when environment/node/instance semantics are explicit in the canonical model.
5. ArchiMate, BPMN, and threat-modeling integrations: separate domain models, each requiring an independent semantic contract before implementation.

## Guardrails

- Python remains the semantic authority.
- Renderers consume projections and do not define semantics.
- Generated outputs remain optional and deterministic.
- Missing renderer tooling never invalidates the canonical graph.
- Every projection must have an accessible text/table representation.
