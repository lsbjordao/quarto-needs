# Solution strategy

The strategy is a small set of guardrails (from `docs/ROADMAP.md`) that every other architectural decision must be consistent with. This page explains *why* those guardrails hold, not just what they say.

## Python is the sole semantic authority (`ADR-001`)

The product has a Python analysis core, Lua rendering filters, and JavaScript interaction. If each layer independently defined what a relation or rule means, equivalent views could disagree. Resolving semantics once, in Python, and publishing the result as a projection (`needs.json`, public graph JSON, C4 view JSON) means every consumer reads an already-decided answer instead of re-deriving one.

## One model, many projections

`cli.build` loads configuration once, analyzes once, and materializes every named query, quality report, and C4 view from that single `AnalysisSnapshot`. Nothing downstream — Lua shortcodes, the CLI, exporters — has its own evaluator. This is why a `query=` filter in a Quarto page and a `quarto-needs coverage` CLI number can never silently disagree.

The same discipline applies inside the core: validation runs on the canonical model only — declaration tokens before the snapshot exists (`validate_declarations`), snapshot records after it (`run_rules`) — never on legacy compatibility DTOs. The dependency direction for the retained `EngineeringObject` convenience APIs is one-way, legacy-into-canonical (`model.to_declaration`), and `tests/test_semantic_kernel_contract.py` fails if a canonical module starts importing the legacy model again.

## Text-first authoring, typed property graph as the model (`ADR-003`)

Engineering objects and relations are declared as ordinary Quarto Markdown (`.need` fenced divs); the model behind them is a typed property graph (nodes = `ObjectRecord`, edges = `RelationRecord`), not a fixed object hierarchy. See [`domain-model.md`](domain-model.md).

## Architectural roles are configuration, not a Python enum (`ADR-012`)

`system`/`container`/`component`/`actor`/`external-system` are entries under `[types.*]`, validated the same way as any project-specific type. This keeps one project's architectural vocabulary from being hardcoded into the core, and lets C4 support depend on a project actually declaring the types it needs.

## Generated projections are derived, never hand-authored (`ADR-015`)

C4 views, the public graph JSON, and the Lua lookup index are all computed from the snapshot on every build and are never edited by hand. See [`generated/README.md`](generated/README.md) and `ADR-017`'s authored-vs-generated boundary.

## Renderer independence (`ADR-016`)

Mermaid text, the Code-level Markdown table, and the interactive Cytoscape exploration view are three renderers over the same `graph_projection.py` output. None of them defines relation semantics; adding a fourth renderer should never require touching `analysis.py` or `relations.py`.
