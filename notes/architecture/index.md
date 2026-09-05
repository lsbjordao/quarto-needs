# Architecture documentation

This is the internal architecture documentation for the Quarto-Needs *tool itself* — how the project that implements requirements-as-code is built. It is distinct from two other things that look similar:

- [`examples/quarto-needs/`](../../examples/quarto-needs/) is a self-hosted **case study**: a real Quarto-Needs project that uses the tool to document the tool, and doubles as an integration-test fixture (`tests/test_self_hosted_example.py`). It is the canonical source for the `ADR-*`, `COMP-*`, `SRC-*`, `SYS-*` engineering objects referenced throughout this folder.
- [`docs/src/`](../../docs/src/) is the **user-facing product manual** (syntax, configuration, CLI reference) for people authoring Quarto-Needs projects; rendering it publishes the site into [`docs/`](../../docs/), the GitHub Pages root.

This folder answers a different question: *how is Quarto-Needs itself organized, and why?* It follows an arc42-lite structure indexed by explicit viewpoints (see [`viewpoints.md`](viewpoints.md)) rather than one fixed notation, per [`ADR-011`](../../examples/quarto-needs/architecture.qmd) in the self-hosted case study.

## Reading order

1. [`goals-and-constraints.md`](goals-and-constraints.md) — why the project exists and what must hold true.
2. [`context.md`](context.md) — system boundary and external dependents.
3. [`solution-strategy.md`](solution-strategy.md) — the guardrails behind every other decision.
4. [`domain-model.md`](domain-model.md) — the conceptual model (declaration → resolution → snapshot → projection).
5. [`building-blocks.md`](building-blocks.md) — containers and components.
6. [`runtime/`](runtime/) — the flows that actually execute (build, editing, federation, change analysis).
7. [`interfaces/`](interfaces/) — the contracts other things depend on.
8. [`decisions/`](decisions/index.md) — ADRs, consumed from the self-hosted example, never copied.
9. [`quality-and-risks.md`](quality-and-risks.md) — engineering risks and how they're addressed.
10. [`traceability.md`](traceability.md) — how a change is traced end to end.
11. [`glossary.md`](glossary.md) — terms that are easy to conflate (need vs. object, link vs. relation, component vs. container).

## Source of truth

Every architectural fact in this folder must be traceable to one of: source code, the self-hosted example's engineering graph, or a test. When code and prose disagree, the code (and its tests) win; file an issue or open a PR to correct the prose.
