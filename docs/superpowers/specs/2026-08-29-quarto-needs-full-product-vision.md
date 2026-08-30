# Quarto-Needs full product vision amendment

**Date:** 2026-08-29  
**Status:** Accepted  
**Amends:** `2026-08-26-quarto-needs-capability-evolution.md`  
**Roadmap:** `docs/ROADMAP.md`

## Decision

The previously deferred capability families are now accepted as part of the long-term Quarto-Needs product vision. Acceptance means the architecture must preserve a credible path to them and the official roadmap may sequence them; it does **not** mean they should be implemented simultaneously or without milestone-level design and review.

The accepted vision includes:

- executable test linkage and machine-produced evidence;
- Git-range diff/impact and pull-request engineering reports;
- suspect traceability and renewed-review semantics;
- a bounded declarative engineering-policy DSL;
- per-type schemas and richer graph constraints;
- safe derived fields and variants;
- Language Server Protocol and a thin VS Code client;
- ReqIF export/import with conformance testing;
- JSON-LD projection and later OSLC Requirements Management federation;
- migration adapters and provenance-preserving external integrations;
- C4-inspired architecture projections derived from the canonical graph;
- an expanded Cytoscape engineering-analysis workbench;
- synthetic scale benchmarks, incremental analysis where justified, and release performance budgets;
- a self-hosted executable engineering model and deliberately broken teaching scenarios.

## Sequencing decision

The implementation sequence is dependency-driven rather than feature-count driven:

1. executable tests and evidence;
2. Git/change/PR intelligence;
3. declarative policy over stable semantics;
4. LSP/editor ergonomics;
5. interchange and federation;
6. architecture/C4 projections;
7. interactive graph-workbench depth;
8. scale and release hardening;
9. continuous evolution of the self-hosted example and teaching scenarios.

Some independent projection/UI work may advance earlier when it does not fork semantics or create an incompatible contract.

## Binding invariants

This amendment does not weaken the existing architectural guardrails:

- Python remains semantic authority.
- Quarto/Lua/browser layers consume projections rather than redefine engineering meaning.
- External formats are adapters, not canonical storage.
- Interactive behavior is progressive enhancement.
- Change and impact remain explainable through explicit graph paths.
- Configuration languages remain bounded and do not execute arbitrary user code.
- External integrations preserve provenance and are read-only by default unless a future write-back contract is designed explicitly.
- New artifact formats are versioned and receive determinism, malformed-input, compatibility, and migration tests.

## Self-hosting consequence

As each capability becomes real, `examples/quarto-needs/` should adopt it as part of the product's own engineering model whenever doing so is truthful. The example is therefore not a frozen demonstration: it is intended to converge on a living, executable specification of Quarto-Needs itself.
