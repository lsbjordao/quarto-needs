# Goals and constraints

## Why Quarto-Needs exists

Quarto-Needs turns Quarto Markdown into a requirements/decisions/risk/test/evidence engineering graph, so that traceability lives in the same Git repository, review workflow, and text format as the artifacts it traces (see `docs/ROADMAP.md`'s north star statement).

## Quality goals (ordered)

1. **Determinism.** The same inputs (declarations + configuration) always analyze to the same `AnalysisSnapshot`. Baselines, diffs, and impact reports depend on this.
2. **Single semantic authority.** Python is the only layer allowed to define what a relation, rule, or query means (`ADR-001`). Lua, JavaScript, the LSP, and exporters consume projections.
3. **Text-first, Git-native authoring.** Every engineering fact is diffable, reviewable, and versionable as plain text (`ADR-002`).
4. **Renderer independence.** The canonical model must not assume any one presentation (`ADR-013`); Mermaid, the interactive Cytoscape view, and future renderers are alternatives over the same projection.
5. **Provenance-preserving interoperability.** Data admitted from OSLC/GitHub carries origin, trust state, and retrieval policy; it never silently joins the canonical graph (`external_trust.py`).

## Constraints

- **No arbitrary code execution from configuration.** `.quarto-needs.toml` is declarative; it cannot execute Python, Lua, JavaScript, or shell code (`docs/ROADMAP.md` guardrail 9).
- **Lua/JavaScript never redefine semantics.** They read pre-rendered JSON/text projections and do not evaluate relation meaning, query expressions, or C4 layer rules themselves.
- **Backward-compatible schema evolution.** `schemas/*.schema.json` are versioned; breaking changes bump the schema version rather than silently changing shape.
- **Localization is presentation-only.** `*.pt-BR.qmd` siblings may translate title/body text but must keep identical IDs, types, statuses, attributes, and relations as the canonical English source (`localization.py`, `ADR-005`).

## Non-goals

- Quarto-Needs does not aim to reproduce another requirements tool's syntax (`docs/ROADMAP.md`).
- It does not implement a generic state-machine engine for arbitrary `need` lifecycles — allowed statuses are configurable per type, but transitions are not modeled.
- Enterprise architecture frameworks (ArchiMate, TOGAF) are out of scope for this documentation set; C4/UML are used selectively, per concern, not as a mandated house style.
