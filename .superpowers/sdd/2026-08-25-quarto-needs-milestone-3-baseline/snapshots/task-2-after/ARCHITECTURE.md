# Architecture

Quarto-Needs follows a ports-and-adapters style architecture. The requirements graph is canonical; Quarto is one authoring/rendering adapter.

```text
                    Quarto authoring
                         .qmd
                           |
                           v
                    Parser / adapters
                           |
                           v
+--------------------------------------------------+
|                Quarto-Needs Core                 |
|                                                  |
|  EngineeringObject -> Relation -> Property Graph|
|            |             |             |         |
|        validation      queries       metrics     |
+--------------------------------------------------+
          |                  |                 |
          v                  v                 v
     needs.json          Quarto UI        exporters
                                              |
                                      JSON/CSV/ReqIF
```

## Canonical model

Every traceable item is an `EngineeringObject`. Relations are first-class typed edges. The model is deliberately renderer-independent.

## Canonical pipeline

```text
QMD files -> DeclarationBatch -> AnalysisResult -> AnalysisSnapshot
                                               -> needs.json v1
                                               -> generated-index.lua

.quarto-needs.toml -> config -> queries / rules / metrics -> report projection
                                                          -> materialized query ID sets

needs.json -> cached Lua indexes -> Pandoc-native cards/views -> HTML/DOCX/PDF
```

Python owns everything up to and including the two generated artifacts;
Lua only reads the projected `needs.json`.

Configuration is a second input to the same single analysis pass, never a
second pass. `cli.build` loads the configuration once, analyzes once, then
materializes the named queries and the quality report from that one snapshot
and writes both under `extensions.quartoNeeds`. The dashboard and every
`query=` filter therefore read numbers and ID sets that Python already decided;
Lua has no evaluator of its own and cannot drift from the CLI verdict.

## Build lifecycle

1. Synchronize every canonical extension runtime asset from
   `_extensions/quarto-needs` into the project-local extension. The generated
   `generated-index.lua` is deliberately excluded from this copy.
2. Scan project `.qmd` files.
3. Parse `.need` blocks into engineering objects.
4. Build the requirements graph.
5. Run structural/referential/process validation.
6. Write `.quarto-needs/needs.json`.
7. Generate the project-specific Lua lookup index used by Quarto shortcodes.
8. Let Quarto/Pandoc render the documentation.

## Generated-view adapter

The pre-render graph is the boundary between the Python core and the Quarto
presentation adapter. Lua reads `.quarto-needs/needs.json` and exposes the
`need-table`, `need-list`, `need-count`, `need-matrix`, and `need-flow`
shortcodes. Each uses the same exact, case-insensitive filter semantics:
alternatives in a field (`ids`, `types`/`type`, `status`, `priority`, or
`tags`) are OR-ed and separate fields are AND-ed. The adapter never evaluates
author-supplied Python or Lua expressions.

Generated tables and need cards render semantic, text-bearing status and
priority badges. HTML may add search and sorting progressively; the graph
views themselves remain static Pandoc output suitable for HTML, PDF, and
DOCX.

## MVP boundaries

The initial parser intentionally supports a narrow syntax. The roadmap is to add schema-driven types/attributes/relations, graph queries, generated matrices/diagrams, source-code scanners, semantic diffs and ReqIF without moving domain logic into Lua.
