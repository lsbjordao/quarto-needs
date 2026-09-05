# Glossary

Terms that are easy to conflate across this documentation set.

**Need vs. object vs. engineering object**
: A `.need` fenced div is authored syntax. Once parsed and resolved it becomes an `ObjectDeclaration`, then an `ObjectRecord` inside the snapshot. "Need," "object," and "engineering object" are used loosely as synonyms in prose; `ObjectRecord` is the precise term in code.

**Type vs. role**
: A *type* (`system-requirement`, `component`, `architecture-decision`, ...) is project-declared configuration. A *role* (`requirement`, `architecture-element`, `decision`, `verification`, `evidence`, `risk`) is the fixed vocabulary `TypePolicy.role` maps a type onto, and is what rules/relations actually key off of (`ADR-012`).

**Link vs. relation**
: A *relation* is an authored, typed, directional edge (`RelationToken`/`RelationRecord`) with catalog semantics (family, inverse, impact/traversal direction). A *link* is not a first-class concept — it is whatever a client derives from IDs, relations, `href`, or incoming/outgoing indexes for navigation.

**Component vs. container vs. system**
: `system`/`container` are deployable/executable units. `component` is a logical decomposition inside a container. Do not read "component" in this codebase as a synonym for "unit of deployment" (`ADR-018`).

**`part-of` vs. `decomposes`**
: Genuine inverses of the same containment relation, authored from opposite ends: `part-of` is child-authored (child says "I belong to this parent"); `decomposes` is parent-authored (parent says "this is one of my parts"). Both are handled everywhere containment is checked (`ARC001`, C4 boundary grouping, the Code-level table).

**Realized-by (not a relation in this codebase)**
: A separate `realized-by`/`realizes` relation between architecture elements and implementation artifacts was considered and rejected (`ADR-014`) — `part-of` already expresses "this source module sits inside/realizes this component," consistently with every other C4 layer.

**Authored vs. generated**
: Authored artifacts are `.qmd` declarations, `.quarto-needs.toml`, and Markdown prose — reviewed and versioned as source. Generated artifacts (`.quarto-needs/needs.json`, `.quarto-needs/graphs/*.json`, `generated-index.lua`, everything under `notes/architecture/generated/`) are rebuilt on every run and never hand-edited (`ADR-017`).

**Baseline vs. snapshot**
: An `AnalysisSnapshot` is the current, in-memory canonical graph. A baseline is a previously *captured* snapshot payload, persisted with a configuration fingerprint and reference date, used as the "before" side of a `diff`/`impact` comparison.

**Trust state (external data)**
: `unverified`, `trusted`, `rejected`, `stale` — the lifecycle of an externally federated observation (OSLC, GitHub) before/after it may influence the canonical graph. See `external_trust.py`. This is the one genuine state machine in the codebase; it is not a general pattern for `need` lifecycles.
