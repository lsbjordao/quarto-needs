# Self-hosted Quarto-Needs engineering case study

This example uses Quarto-Needs to model the engineering of Quarto-Needs itself.

It complements, rather than replaces, `examples/book/` (Aegis IAM):

- **Aegis IAM** demonstrates Quarto-Needs in an external application domain.
- **Engineering Quarto-Needs with Quarto-Needs** demonstrates requirements engineering, architecture decisions, implementation traceability, verification, evidence, risks, and change analysis using the product's own real design.

## Languages

English (`*.qmd`) is the canonical engineering source. Brazilian Portuguese (`*.pt-BR.qmd`) translates presentation text only. The pre-render workflow validates that IDs, types, statuses, attributes, and relations are semantically identical between the two languages.

## Living engineering model

The current case study contains 86 engineering objects. In addition to needs, requirements, ADRs, architecture elements, risks, tests, and evidence, it models 14 real repository files as `source-module` objects.

`source-module` deliberately means a physical implementation artifact, not an architecture component. Each module carries a repository `path`, implementation `language`, architectural `layer`, tags, and one or more canonical `implements` relations back to approved requirements. Regression tests verify that every declared path exists and that every source module participates in implementation traceability.

The learning path is organized around four reusable vertical slices:

1. interactive graph exploration;
2. multilingual engineering;
3. architecture decision management;
4. baseline, diff, and impact analysis.

Each slice can be followed from stakeholder motivation through requirements and architecture into source modules, tests, and evidence.

## Local workflows

From the repository root:

```bash
make check-self-example
make render-self-example
make preview-self-example
```

`render-self-example` uses the same BabelQuarto + output-normalization path as the Aegis showcase, producing canonical English pages and normalized `pt-BR/` pages.

The change-analysis chapter also demonstrates the CLI workflow for creating a baseline and then running structured `diff` and `impact` analysis against later engineering states.

## Intended role

This directory is intended to evolve into the living engineering model of Quarto-Needs. Significant product changes should eventually update the relevant stakeholder need or requirement, ADR, architecture element, source module, verification, and evidence alongside the implementation itself.
