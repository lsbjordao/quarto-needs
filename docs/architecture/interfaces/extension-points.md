# Interface: extension points

Where a project (or a future core contribution) plugs new behavior in, without touching the semantic core's invariants.

## New object types

Declared under `[types.<name>]` in `.quarto-needs.toml`: `id-prefix`, `role`, `allowed-statuses`, `required-attributes`, and an optional JSON Schema `attribute-schema`. Validated by `config.py`; no Python code change required for a new type (`ADR-012`).

## New relation policies

Per-relation constraints (`allowed-source-types`, `allowed-target-types`, `minimum-per-source`, `maximum-per-source`) are declared under `[relations."<name>"]`. The relation's *meaning* (family, inverse, direction) is fixed by the core `RelationCatalog` in `relations.py`; a project constrains how an existing relation may be used, it does not invent new relation semantics through configuration.

## New rules

Structural/governance rules live in `rules.py` as `RuleSpec` entries with an evaluator function; each carries a stable code (`REQ0xx`, `DEC0xx`, `ARC0xx`), a default severity, and, where relevant, an `auto_activates` predicate keyed off configuration (e.g., `REQ010` only activates when relation policies are declared).

## New queries

Named, declarative queries (`[queries.<name>]` in configuration) compile through the bounded AST in `queries.py` — never a general-purpose expression language — and can be consumed by both `need-table`/`need-graph` shortcodes and CLI coverage output.

## New exporters

Exporters (CSV, JUnit, SARIF, ReqIF, JSON-LD) each read the same `AnalysisSnapshot`/public projection and are one-directional: they format an already-resolved graph, they do not participate in resolving it.

## What is *not* an extension point

Lua and JavaScript do not get a mechanism for defining new relation semantics, rule logic, or query evaluation — by design (`ADR-001`). A presentation-layer feature that seems to need one is a signal the underlying projection is missing a field, not that Lua/JS should compute it.
