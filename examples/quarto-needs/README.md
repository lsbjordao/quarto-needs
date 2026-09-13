# Self-hosted Quarto-Needs engineering case study

This example uses Quarto-Needs to model the engineering of Quarto-Needs itself.

The case study demonstrates requirements engineering, architecture decisions, implementation traceability, executable verification, machine evidence, risks, and change analysis using the product's own real design.

## Languages

English (`*.qmd`) is the canonical engineering source. Brazilian Portuguese (`*.pt-BR.qmd`) translates presentation text only. The pre-render workflow validates that IDs, types, statuses, attributes, and relations are semantically identical between the two languages.

## Living engineering model

The current case study contains 183 engineering objects. In addition to needs, requirements, ADRs, architecture elements, risks, tests, and evidence, it models 28 real repository files as `source-module` objects.

`source-module` deliberately means a physical implementation artifact, not an architecture component. Each module carries a repository `path`, implementation `language`, architectural `layer`, tags, and one or more canonical `implements` relations back to approved requirements. Regression tests verify that every declared path exists and that every source module participates in implementation traceability.

Twenty-three representative modeled test cases are now bound to real pytest functions through `pytest-nodeid`, spanning decision governance (`TC-004`), localization parity (`TC-005`), public graph safety (`TC-006`), named graph views (`TC-009`), change impact (`TC-011`), margin-TOC usability (`TC-014`), OSLC federation (`TC-015`…`TC-019`), GitHub issues (`TC-020`…`TC-024`), and extension-first distribution (`TC-025`…`TC-031`).

The corresponding pytest tests carry reciprocal `@pytest.mark.requirement(...)` and `@pytest.mark.quarto_need_test_case(...)` markers. This makes the linkage independently checkable from both the engineering model and the executable suite.

## Machine evidence

Generate the self-hosted pytest evidence artifact with:

```bash
make evidence-self-example
```

The target:

1. executes the twenty-three pytest tests bound to the self-hosted model;
2. writes `examples/quarto-needs/.quarto-needs/evidence/pytest.json`;
3. runs `quarto-needs evidence check` against the current engineering graph.

The semantic evidence check fails when an executable test is not successful, a modeled/executable node ID differs, an unknown requirement or test-case is referenced, a requirement is not actually verified by the claimed test-case, or a modeled pytest binding is missing from the artifact.

`render-self-example` depends on `evidence-self-example`, so stale executable bindings block the self-hosted book before rendering.

## Rendered output and publication

The Quarto project declares `output-dir: _book`, so local rendering produces `examples/quarto-needs/_book/`.

That directory is **generated output** and is intentionally ignored by Git. Its absence from the repository is therefore expected; the authored case study remains in the `.qmd` sources.

CI renders both the multilingual manual and this self-hosted case study, assembles them into one immutable `pages-site/` tree, validates the expected English, pt-BR, Failure Gallery, and case-study entry points, and uploads the complete tree as a build artifact. On pushes to `main`, the same tree is uploaded as the GitHub Pages artifact and deployed through the `github-pages` environment. Generated HTML is never committed or pushed back to `main`.

Published case study: **https://lsbjordao.github.io/quarto-needs/examples/quarto-needs/**

## View coverage

The case study exercises every registered Quarto-Needs shortcode, so it doubles as a rendered reference for the view layer:

| Shortcode | Where |
|---|---|
| `need`, `need-count`, `need-list`, `need-table` | `index.qmd` and most chapters |
| `need-graph` | `traceability.qmd` and every domain chapter |
| `need-matrix`, `need-inspector`, `need-backlinks` | `traceability.qmd` |
| `need-dashboard` | `verification.qmd` |
| `adr-table`, `adr-count` | `architecture.qmd` |
| `need-c4` | `architecture.qmd`, all four backends |
| `need-flow` | `interoperability.qmd` |
| `need-tags` | `tags.qmd` |

## Learning path

The example is organized around six reusable vertical slices (two more, covering OSLC federation and GitHub issues federation, are traced in `interoperability.qmd`):

1. interactive graph exploration;
2. multilingual engineering;
3. architecture decision management;
4. baseline, diff, and impact analysis;
5. margin-TOC usability;
6. extension-first distribution.

Each slice can be followed from stakeholder motivation through requirements and architecture into source modules, modeled verification, and evidence. The target evolution extends those slices further into executable tests, machine evidence, and change/review state.

## Local workflows

From the repository root:

```bash
make setup
make check-self-example
make evidence-self-example
make render-self-example
make preview-self-example
```

`make setup` should be rerun after pytest-plugin metadata changes so the local editable installation has the current entry points.

`render-self-example` generates and validates executable evidence before using the BabelQuarto + output-normalization path, producing canonical English pages and normalized `pt-BR/` pages.

The change-analysis chapter also demonstrates the CLI workflow for creating a baseline and then running structured `diff` and `impact` analysis against later engineering states.

## Intended role

This directory is intended to evolve into the living executable engineering model of Quarto-Needs. Significant product changes should increasingly update the relevant stakeholder need or requirement, ADR, architecture element, source module, executable verification, machine evidence, and change/review state alongside the implementation itself.
