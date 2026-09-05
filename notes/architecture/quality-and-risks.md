# Quality attributes and risks

Engineering risks tracked as `risk`-typed needs in the self-hosted example, and how the architecture addresses each one. This page is a summary; the needs themselves (with `mitigates` relations to functional/non-functional requirements) are canonical.

| Risk | Description | Addressed by |
|---|---|---|
| `RISK-001` | Semantic meaning diverges across core and presentation layers | `ADR-001` (Python as sole semantic authority); Lua/JS never define relation/rule/query meaning |
| `RISK-002` | Public documentation leaks internal source information | `graph_projection.py`'s allowlisted `PublicNode` fields; `ADR-017`'s authored-vs-generated boundary |
| `RISK-003` | Large graph projections overwhelm interactive documentation | `[graph] max-nodes`/`max-edges`/`depth` bounds in configuration |
| `RISK-004` | Translations create a competing engineering model | `localization.py`'s `semantic_signature` parity check — build fails if a `pt-BR` sibling changes IDs, types, statuses, attributes, or relations |
| `RISK-005` | OSLC federation credentials/stale cache | `external_trust.py` trust states; read-only federation, never auto-admitted to the canonical graph |
| `RISK-012` | GitHub federation pagination/rate-limit/traversal | Same read-only, provenance-bound federation model as OSLC |

## Quality goals in tension

- **Determinism vs. expressiveness.** The bounded query language (`queries.py`) intentionally has no general-purpose evaluator, trading some expressiveness for guaranteed reproducibility.
- **Renderer independence vs. Mermaid-specific escaping.** `c4_render.py` still has to know Mermaid's syntax to escape labels safely; this is accepted as presentation-layer detail, not a semantic leak, because the escaping never changes what a projection *means*.
- **Generic cardinality vs. "exactly one parent."** `REQ010`'s `maximum-per-source` catches duplicate `part-of` parents, but its `minimum-per-source` only inspects objects that already have *some* edges — an object with zero parents is invisible to it. This is a known, documented limitation of the generic mechanism (see `notes/ROADMAP.md`, Phase 6), not silently assumed away.
