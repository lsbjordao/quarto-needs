# Generated architecture projections

This directory is reserved for build-generated architecture artifacts for *this* documentation set (Mermaid/C4 source, traceability exports), mirroring the boundary decided in `ADR-017`: everything here is a projection of the canonical engineering graph in `examples/quarto-needs/`, never a second authored copy.

The default and named graph views are also published as deterministic
Graphviz/DOT siblings under `.quarto-needs/graphs/`. The JSON files drive the
Quarto graph view; DOT is an optional text interchange artifact for Graphviz-
compatible renderers. Missing Graphviz tooling does not prevent JSON
projection generation. The generated C4 views embedded live in
[`examples/quarto-needs/architecture.qmd`](../../../examples/quarto-needs/architecture.qmd)
remain authoritative for architecture diagrams.

Rule: if a file appears here, it was written by a build step, not by a person. Do not hand-edit anything in this directory.
