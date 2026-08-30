# Self-hosted Quarto-Needs engineering case study

This example uses Quarto-Needs to model the engineering of Quarto-Needs itself.

It complements, rather than replaces, `examples/book/` (Aegis IAM):

- **Aegis IAM** demonstrates Quarto-Needs in an external application domain.
- **Engineering Quarto-Needs with Quarto-Needs** demonstrates requirements engineering, architecture decisions, verification, evidence, risks, and traceability using the product's own real design.

## Languages

English (`*.qmd`) is the canonical engineering source. Brazilian Portuguese (`*.pt-BR.qmd`) translates presentation text only. The pre-render workflow validates that IDs, types, statuses, attributes, and relations are semantically identical between the two languages.

## Local workflows

From the repository root:

```bash
make check-self-example
make render-self-example
make preview-self-example
```

`render-self-example` uses the same BabelQuarto + output-normalization path as the Aegis showcase, producing canonical English pages and normalized `pt-BR/` pages.

## Intended role

This directory is intended to evolve into the living engineering model of Quarto-Needs. Significant product changes should eventually be able to update the relevant requirement, ADR, component, verification, and evidence alongside the implementation itself.
