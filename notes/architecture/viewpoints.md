# Viewpoints

Each page in this folder declares, in the table below, who it is for, what question it answers, which notation it uses, where its facts come from, and what should trigger someone to update it. This is the contract that keeps the documentation set from drifting into ad hoc, duplicated pages (see [`ADR-011`](../../examples/quarto-needs/architecture.qmd)).

| Page | Audience | Concern | Notation | Source | Update trigger |
|---|---|---|---|---|---|
| [`context.md`](context.md) | All | Who/what depends on the system and why | C4 Context (text) | `examples/quarto-needs/architecture.qmd` (`SYS-QUARTO-NEEDS`, `ACTOR-*`, `EXT-*`) | New external system, integration, or actor |
| [`solution-strategy.md`](solution-strategy.md) | Maintainer, contributor | Cross-cutting decisions that constrain everything else | Prose + links to ADRs | `notes/ROADMAP.md` guardrails, `ADR-001`/`ADR-002`/`ADR-003` | A guardrail changes or a new one is adopted |
| [`domain-model.md`](domain-model.md) | Contributor, integrator | The conceptual model from authoring to projection | UML class diagram (Mermaid) | `parser.py`, `analysis.py`, `snapshot.py`, `relations.py` | A core dataclass's role in the pipeline changes |
| [`building-blocks.md`](building-blocks.md) | Contributor, architect | Containers and components, and what runs where | C4 Container/Component (generated) | `examples/quarto-needs/architecture.qmd` C4 views | A container or component is added, split, or removed |
| [`runtime/build-and-render.md`](runtime/build-and-render.md) | Contributor, CI/release engineer | What happens during `quarto render` | UML sequence | `tools/quarto_needs_pre_render.py`, `cli.py` | The build lifecycle gains/loses a step |
| [`runtime/editor-and-lsp.md`](runtime/editor-and-lsp.md) | Editor/tooling developer | Unsaved-edit flow through the LSP | UML sequence | `editors/vscode/`, LSP server module | The overlay/diagnostics contract changes |
| [`runtime/federation-and-import.md`](runtime/federation-and-import.md) | Integrator | External data admission and trust | UML activity + state | `external_trust.py`, OSLC/GitHub federation modules | A new external source type or trust state is added |
| [`runtime/baseline-diff-impact.md`](runtime/baseline-diff-impact.md) | Reviewer, CI/release engineer | How change is measured between two states | Data-flow (text) | `baseline.py`, `diff.py`, `impact.py` | The comparison contract (fingerprint, guards) changes |
| [`interfaces/artifact-contracts.md`](interfaces/artifact-contracts.md) | Integrator, contributor | Stable machine-readable contracts | Schema references | `schemas/*.schema.json` | A schema version bumps |
| [`interfaces/extension-points.md`](interfaces/extension-points.md) | Contributor | Where new types/relations/rules/exporters plug in | Prose | `config.py`, `relations.py`, `rules.py` | A new extension mechanism is added |
| [`interfaces/interoperability-boundaries.md`](interfaces/interoperability-boundaries.md) | Integrator | What crosses the trust boundary and how | Prose + state diagram | `external_trust.py`, `oslc-*` modules | A new interoperability adapter is added |
| [`decisions/index.md`](decisions/index.md) | All | Why, not just what | Renders ADR needs | `examples/quarto-needs/architecture.qmd`, `interoperability.qmd` | Never edited directly — a new ADR is authored in the source |
| [`quality-and-risks.md`](quality-and-risks.md) | Reviewer, architect | What can go wrong and how it's mitigated | Risk table | `RISK-*` needs | A new risk is identified or mitigated |
| [`traceability.md`](traceability.md) | Reviewer, architect | End-to-end trace from need to evidence | Flow (text) | `traceability.qmd` in the self-hosted example | A new traceability chain type is introduced |

## Rules

- A page's "Source" column is where facts are verified before the page is edited, not the other way around.
- `generated/` (see [its README](generated/README.md)) never has a Source column entry pointing at itself — everything in it is a projection.
- If a page's concern is now answered by an existing page, delete the duplicate rather than keep both current.
