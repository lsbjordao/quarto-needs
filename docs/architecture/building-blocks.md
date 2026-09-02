# Building blocks

Containers and components as modeled in the self-hosted example. This page is prose; the authoritative, always-current diagrams are the generated C4 Container/Component views embedded in [`examples/quarto-needs/architecture.qmd`](../../examples/quarto-needs/architecture.qmd) (`ADR-015` — never hand-copy those diagrams here).

## Containers (deployable/executable units)

- **Python package** (`CONTAINER-PYTHON-PKG`, Python 3.12) — the installable `quarto-needs` library and CLI: parsing, analysis, governance rules, graph projection, baselines, localization checks.
- **Quarto presentation extension** (`CONTAINER-QUARTO-EXT`, Quarto/Pandoc Lua filters) — the `_extensions/quarto-needs/` bundle: build-time Lua filters and the browser-side JavaScript they ship.

The Python core is a shared library consumed by both the CLI and (separately) an LSP server — it is not itself a third container; representing it as one would be an artificial abstraction (`ADR-012`).

## Components (logical decomposition, inside a container)

Inside `CONTAINER-PYTHON-PKG`:

| Component | Responsibility |
|---|---|
| `COMP-PARSER` | Reads QMD declarations into structured declaration batches with source locations |
| `COMP-ANALYSIS` | Builds the canonical graph, resolves relation semantics, produces immutable snapshots |
| `COMP-RULES` | Evaluates structural, requirement, decision, risk, and evidence governance |
| `COMP-CLI` | Exposes scan/check/coverage/baseline/diff/impact workflows |
| `COMP-GRAPH` | Publishes bounded public graph projections; Cytoscape-based exploration |
| `COMP-BASELINE` | Captures reproducible states; computes changes and impact paths |
| `COMP-I18N` | Validates translated sources against the canonical graph; emits localized title projections |

Inside `CONTAINER-QUARTO-EXT`:

| Component | Responsibility |
|---|---|
| `COMP-EXTENSION` | Turns the resolved model into cards, tables, matrices, dashboards, diagrams, progressive HTML |

## Execution units vs. logical components (`ADR-018`)

`system`/`container` represent deployable/executable units; `component` is the logical decomposition inside a container. The C4 projection enforces this: `build_c4_view` requires a `system` focus for Context/Container and a `container` focus for Component, so a logical component can never itself become a container boundary. `ARC001`'s fixed layer order (`system > container > component > source-module`) enforces the same separation structurally, over the `part-of` relation (`ADR-013`).
