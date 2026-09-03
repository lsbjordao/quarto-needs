# Architecture View Projections

## Status

Proposed and implemented in the first slice.

## Objective

Expose useful architecture and engineering views from the canonical Quarto-Needs graph without creating a second architecture model or coupling the semantic core to a diagram framework.

## Boundary

```text
canonical typed graph
        -> semantic projection
        -> renderer adapter
        -> Mermaid / Graphviz / PlantUML / Structurizr / D2
```

Python remains the semantic authority. Renderers receive a projection and never reinterpret authored relations.

## First slice

The first slice adds a deterministic Graphviz/DOT adapter for the existing public graph projection. Every default and named-query graph projection may publish a sibling `.dot` artifact under `.quarto-needs/graphs/`. Quarto can render that artifact through its existing Graphviz support or another compatible DOT tool.

DOT is intentionally a generic graph output, not a second C4 model. Node labels carry stable IDs, titles, types, status, and change markers. Edge labels carry relation names and change/path markers. Shapes and colors are restrained and supplementary; the text labels remain the accessible source of meaning.

## Future projections

The next semantic projections should be traceability, lifecycle/state, sequence, deployment, and assurance views. They should only be added when the canonical graph has enough explicit data to support them. ArchiMate and BPMN are separate semantic models, not renderer aliases, and require separate design work.

## Invariants

- Equivalent snapshots produce byte-identical DOT.
- Graphviz output is optional presentation output and never changes the canonical fingerprint.
- Missing Graphviz support does not block JSON projection or Quarto rendering.
- Existing Mermaid, PlantUML, Structurizr, and D2 artifacts remain unchanged.
- All generated artifacts are derived during the normal build path.
