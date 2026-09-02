# Generated architecture projections

This directory is reserved for build-generated architecture artifacts for *this* documentation set (Mermaid/C4 source, traceability exports), mirroring the boundary decided in `ADR-017`: everything here is a projection of the canonical engineering graph in `examples/quarto-needs/`, never a second authored copy.

Nothing is wired up to populate this directory yet — doing so requires a CLI step that runs the existing `c4_projection`/`graph_output` machinery against `examples/quarto-needs/` and writes its output here, analogous to `.quarto-needs/graphs/`. Until that exists, treat the generated C4 views embedded live in [`examples/quarto-needs/architecture.qmd`](../../../examples/quarto-needs/architecture.qmd) as authoritative.

Rule: if a file appears here, it was written by a build step, not by a person. Do not hand-edit anything in this directory.
