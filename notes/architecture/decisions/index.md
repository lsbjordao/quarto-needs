# Architecture decisions

Decisions are `architecture-decision`-typed needs authored in the self-hosted example, not copied here. This page only indexes them; each ADR's full context/drivers/outcome/consequences lives in its `.need` block.

## Where ADRs live

- [`examples/quarto-needs/architecture.qmd`](../../../examples/quarto-needs/architecture.qmd) — `ADR-001`…`ADR-007` (semantic authority, Quarto as interface, typed property graph, projection-driven graphs, localization, named queries, progressive-enhancement TOC), and `ADR-011`…`ADR-018` (viewpoints documentation strategy, architectural roles as types, `part-of` hierarchy, `part-of` reused instead of a new `realized-by` relation, snapshot-derived C4 projections, renderer independence, authored/generated boundary, execution units vs. logical components).
- [`examples/quarto-needs/interoperability.qmd`](../../../examples/quarto-needs/interoperability.qmd) — `ADR-008`…`ADR-010` (OSLC federation trust model, OSLC reconciliation, GitHub federation trust model).

## Reading them

Render the self-hosted example (`quarto render examples/quarto-needs`) and use the generated `architecture-decisions` query view, or read the `.need` blocks directly — both show the same accepted decisions, since the query view is a projection of the same graph (`ADR-006`).

## Adding a new ADR

1. Author it as a new `architecture-decision` need in the relevant `.qmd` file (`architecture.qmd` for core/C4 decisions, `interoperability.qmd` for federation decisions), in both the English source and its `.pt-BR.qmd` sibling with identical IDs/attributes/relations (translated title/body only).
2. Give it `addresses` (at least one driver: a requirement or risk), `applies-to` (at least one architecture element), and, once a test exists, `confirmed-by`.
3. Do not edit an accepted decision retroactively — supersede it with `supersedes`/`superseded-by` instead.
4. Update this index only if the *location* of ADRs changes; do not duplicate ADR content here.
