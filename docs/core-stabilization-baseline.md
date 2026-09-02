# Core Stabilization — Baseline Inventory

**Date:** 2026-09-02
**Phase:** `docs/superpowers/specs/2026-09-02-core-stabilization-design.md`
**Status:** before-state record (no production behavior change)

---

# 1. Baseline test result

```text
.venv/bin/python -m pytest -q
959 passed, 1 skipped in 378.32s (0:06:18)
```

Full suite green on the working tree that also carries the (uncommitted)
architecture-view-projections change; the stabilization commits below only
touch files unrelated to that change.

Environment: Linux (Debian), CPython from `.venv` (see `benchmarks/README.md`
for the exact interpreter version recorded later), Quarto at
`/usr/local/bin/quarto`.

---

# 2. Current canonical pipeline

```text
parse_project_declarations(root, files, overlays)      parser.py
        |
        v
DeclarationBatch(declarations, parser findings)        QND001, QND002 emitted here
        |
        v
_analyze_batch(batch, ...)                             analysis.py
        |
        +--> _legacy_objects(declarations)             BRIDGE: ObjectDeclaration -> EngineeringObject
        |        |                                     (also emits REQ007 for unsupported relations)
        |        v
        |    validate(list[EngineeringObject])         validation.py
        |                                             REQ004 duplicate ID      (error,   blocks snapshot)
        |                                             REQ005 unknown target    (error,   blocks snapshot)
        |                                             REQ002 missing rationale (warning)
        |                                             REQ006 approved w/o verification (warning)
        |
        +--> merge findings; gate on STRUCTURAL_ERROR_CODES = {QND001, QND002, REQ004, REQ005, REQ007}
        |        blocked  -> AnalysisResult(declarations, findings, snapshot=None)
        |
        +--> _records(declarations)                    ObjectRecord / RelationRecord
        |        (relation catalog resolved a SECOND time here; deterministic sorts)
        |
        +--> outgoing/incoming indexes                 O(V*E): full relation scan per object
        |
        +--> legacy_coverage metrics                   requirements/approved/implemented/verified
        |
        +--> fingerprints (configuration, semantic graph, representation)
        |
        +--> _materialize_safe_projections             derived fields + variants
        |
        +--> run_rules(snapshot, config)               rules.py  (already snapshot-native)
                REQ008..REQ015, ID001, OBJ001, OBJ002,
                DEC001..DEC006, ARC001,
                + [policies] + [graph constraints]
        |
        v
AnalysisResult(declarations, findings, snapshot)
```

## Diagnostic origin split

| Origin | Codes | Notes |
| --- | --- | --- |
| parser, before batch | QND001 unclosed block, QND002 relation without targets | carry locations |
| legacy bridge, pre-snapshot | REQ004 duplicate ID (first occurrence's location), REQ005 unknown target (owner location, resolved v1 relation name in message), REQ007 unsupported relation (token-or-declaration location), REQ002 missing rationale (no location), REQ006 approved without verification (no location) | REQ002/REQ006 also emitted when the project is structurally blocked |
| rules engine, post-snapshot | REQ008–REQ015, ID001, OBJ001, OBJ002, DEC001–DEC006, ARC001, policy and constraint findings | operate on `AnalysisSnapshot`/records already |

`apply_rule_settings` maps config `[rules]` severity settings onto the legacy
codes (REQ002/REQ004/REQ005/REQ006; REQ004/REQ005 are structural and refuse
disabling/overrides); REQ007 has no `RuleSpec` and passes through untouched.

---

# 3. `EngineeringObject` call sites

| Site | Classification |
| --- | --- |
| `src/quarto_needs/model.py` — definition of `EngineeringObject`, `Relation`, `SourceLocation` | legacy DTO module (keep as compatibility surface) |
| `src/quarto_needs/analysis.py` — `_legacy_objects()` | **semantic-core dependency (the bridge to remove)** |
| `src/quarto_needs/analysis.py` — `analyze_objects(Iterable[EngineeringObject])` + `_declaration()` | convenience API; already adapts legacy → `ObjectDeclaration` → canonical analyzer; direction is legacy-into-canonical (allowed) |
| `src/quarto_needs/parser.py` — `_legacy_object()`, `parse_qmd()`, `parse_project()` | compatibility/test constructors; **no callers in `src/` or `tools/`**; used by `tests/test_parser.py`, `tests/test_adr_date_rendering.py`, `tests/test_example_project.py` |
| `src/quarto_needs/validation.py` — `validate(list[EngineeringObject])` | **semantic-core dependency when called from `analysis.py`**; also called directly by `tests/test_parser.py` and `tests/test_validation.py` |
| `src/quarto_needs/export.py` — `coverage`, `export_lua_index`, `export_graph` signatures | public convenience API; adapts into canonical `analyze_objects` |
| `src/quarto_needs/graph.py` — `RequirementsGraph.build(list[EngineeringObject])` | test/compat surface; only consumer is `tests/test_graph.py` |
| `src/quarto_needs/exporters/jsonld_export.py` — `"@type": "qn:EngineeringObject"` | string literal in the JSON-LD namespace, not the Python type |

`validate()` call sites: `analysis.py:324` (canonical path — to be removed),
`tests/test_parser.py:47`, `tests/test_validation.py` (compat/test usage).

---

# 4. Behavior worth pinning before refactor

* REQ004's location is the **first occurrence in declaration order** (parser
  pre-sorts project declarations, so the project path is order-stable; the
  `analyze_objects` path inherits caller order — pin as-is, do not fix).
* REQ005's message embeds the **resolved v1 relation name** (falls back to the
  authored name when the relation itself is unsupported).
* REQ002/REQ006 currently appear in `result.findings` **even when the snapshot
  is structurally blocked**.
* REQ002's predicate is `not obj.rationale and "### Rationale" not in body`
  (the parser has already extracted `### Rationale`/`### Justificativa` prose
  into `rationale`, so the substring check is the residual guard).
* Snapshot blocked ⇒ `snapshot is None` but declarations and all merged
  findings remain observable.
* Findings are deduplicated and ordered by
  `_analysis_finding_key` (severity, code, id, file, line, anchor,
  canonical properties JSON).
