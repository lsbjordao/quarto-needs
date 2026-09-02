# Runtime: build and render

What happens during `quarto render`, end to end (see `ARCHITECTURE.md`'s "Build lifecycle" for the authoritative step list; this page explains *why* the steps are ordered this way).

## Sequence

1. **Extension asset sync** — every canonical runtime asset is synchronized from `_extensions/quarto-needs` into the project-local extension, deliberately excluding the generated `generated-index.lua` (a project's own generated index must never be overwritten by the shared template).
2. **Scan** project `.qmd` files.
3. **Parse** `.need` blocks into `ObjectDeclaration`s (`parser.py`).
4. **Analyze** — build the graph, resolve relation semantics, produce the immutable `AnalysisSnapshot` (`analysis.py`).
5. **Validate** — structural/referential/process rules run against the snapshot (`rules.py`); localized siblings are checked for semantic parity (`localization.py`).
6. **Write** `.quarto-needs/needs.json` and the project-specific `generated-index.lua`.
7. **Render** — Quarto/Pandoc runs; Lua filters read `needs.json` and the generated index to emit `need-table`/`need-list`/`need-count`/`need-matrix`/`need-flow`/`need-graph`/`need-c4` shortcodes as static HTML/DOCX/PDF content.
8. **Progressive enhancement** — where the output format is HTML, JavaScript (Cytoscape exploration, margin TOC control) enhances the static output without which it remains fully readable.

## Why this order matters

Steps 3–6 happen entirely in Python, once, before Quarto/Pandoc ever runs. This is what makes `ADR-001` (Python as sole semantic authority) actually true at runtime rather than just in principle: Lua in step 7 has no relation catalog, no rule evaluator, and no query language of its own — it is handed an already-resolved answer.

## Failure modes

- A structural/referential finding with `severity="error"` stops the snapshot from being produced at all (`AnalysisResult.snapshot is None`); the build fails before Quarto/Pandoc runs.
- A localization parity violation raises during step 5, before any rendering occurs, so a translated file can never silently reach print with different semantics than its canonical sibling.
