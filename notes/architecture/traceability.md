# Traceability

How one change traces end to end, illustrated with the self-hosted example's own vertical slices (see `examples/quarto-needs/implementation.qmd`, "Five vertical slices").

## The canonical chain

```
Stakeholder need -> System/Functional/NFR requirement (derives-from)
Architecture decision -> requirement/risk (addresses), architecture element (applies-to)
Requirement -> component/interface (implemented-by)
Source module -> requirement (implements), component (part-of)
Requirement -> test case (verified-by)
Test case -> evidence (evidenced-by)
Requirement -> risk (mitigates)
```

A decision does not sit *between* a requirement and an architecture element as a mandatory hop — it branches off as rationale: `ADR addresses Requirement/Risk` and, separately, `ADR applies-to ArchitectureElement`.

## Worked example: interactive graph exploration

`STK-001 → SYS-006 → FUN-004 → ADR-004 → COMP-GRAPH → SRC-GRAPH-OUTPUT / SRC-GRAPH-CONTEXT / SRC-GRAPH-EXPLORE → TC-006 / TC-010 → EVD-006 / EVD-010`

Each arrow above is a real, queryable relation in the graph — not a narrative convention. `examples/quarto-needs/implementation.qmd` lists four more such slices (multilingual engineering, decision management, change analysis, margin TOC usability).

## Verifying a chain is real, not aspirational

- `source-module.path` must point at a real repository file (checked by `test_self_hosted_source_modules_point_to_real_repository_files`).
- A `test-case` may carry a `pytest-nodeid`; CI can verify the test exists (`test_self_hosted_pytest_bindings_point_to_real_test_functions`).
- Coverage gates (`[gates]` in `.quarto-needs.toml`) fail the build below configured implementation/verification/evidence thresholds.

## Completeness queries worth running

- Architecture elements without any requirement they implement.
- Decisions without scope (`applies-to`) or without a driver (`addresses`) — flagged by `DEC001`/`DEC002` as warnings, not silently ignored.
- Requirements without verification, or verification without evidence.
