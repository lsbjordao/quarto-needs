# Quarto-Needs Milestone 2 Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver project configuration through `.quarto-needs.toml`, a safe named-query engine with a Python reference evaluator, configurable built-in governance rules, scoped metrics with explicit denominators, quality gates with execution profiles, the `quality` and `query` CLI commands, and precomputed dashboard/inspector views in Quarto — without changing any schema-v1 compatibility surface.

**Architecture:** An optional `.quarto-needs.toml` is parsed into an immutable `NeedsConfig`; embedded defaults reproduce current behavior exactly when the file is absent. A typed query AST (validated against allowlists, depth ≤ 10, ≤ 100 clauses) is compiled from configured named queries and evaluated by Python over `AnalysisSnapshot`. Configurable rules run after structural validation and only add semantic findings; structural codes and snapshot suppression are unchanged. Metrics distinguish scope, denominator, and strength. The build materializes named queries as ordered ID sets and embeds the precomputed report under `extensions.quartoNeeds`, so Lua only intersects legacy filters, reads numbers, and renders Pandoc-native views for HTML, DOCX, and PDF.

**Tech Stack:** Python 3.10+ (stdlib dataclasses/hashlib/datetime; conditional `tomli` dependency on 3.10), pytest, jsonschema (test-only), Quarto/Pandoc Lua, CSS

**Spec:** `docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md`, Milestone 2; sections *Configuration and safe queries*, *Rules, findings, metrics, and gates*, *Quarto experience*, *CLI and failure semantics*

## Global Constraints

- Embedded defaults preserve current behavior byte-for-byte when `.quarto-needs.toml` is absent: same findings, same six legacy metric keys, same v1 payload except additive `extensions.quartoNeeds` content.
- No runtime dependency except the conditional TOML parser: `tomli>=1.1.0; python_version < "3.11"`.
- The query evaluator never calls `eval`, never loads modules, never uses arbitrary regular expressions, and never exposes Python/Lua internals to authors.
- New rule codes are warnings/info by default and activate only through configuration. Structural codes (`QND001`, `QND002`, `REQ004`, `REQ005`, `REQ007`) keep their meanings; they still suppress snapshots and are unaffected by severity overrides.
- `validate()`, `coverage()`, `export_graph()`, `export_lua_index()`, `cli.build(root, quiet=False)`, existing commands, existing shortcodes, legacy filter semantics, and the frozen v1 contract test remain intact. Additive keyword-only parameters are allowed.
- Wall-clock time enters results only through one helper that prefers `SOURCE_DATE_EPOCH` and otherwise uses the current date; every finding/report carries the reference date it used.
- Deterministic ordering everywhere; atomic writes via the existing `_write_atomic_text`; no absolute paths or wall-clock timestamps inside generated artifacts.
- Lua never recomputes coverage or evaluates relation clauses; it reads materialized ID sets and the embedded report projection.
- `_extensions/quarto-needs` stays canonical; `examples/book/_extensions/quarto-needs` is synchronized by the pre-render helper.
- Keep the preview server on `127.0.0.1:8777` alive during implementation; refresh it to final state only at Task 9 acceptance.
- Baselines/diff/impact stay Milestone 3; scanners/exporters/CI artifacts stay Milestone 4; interactive graph/public projection stays Milestone 5.

## File Map

| Area | Files | Responsibility after Milestone 2 |
|---|---|---|
| Configuration | `src/quarto_needs/config.py` | `ConfigurationError`, `NeedsConfig`, `load_config`, embedded defaults, reference-date helper |
| Safe queries | `src/quarto_needs/queries.py` | Query AST, compiler with allowlists/limits, evaluator over snapshots, named-query materialization |
| Governance rules | `src/quarto_needs/rules.py` | Rule registry/protocol, new REQ008–REQ015 built-ins, config-driven activation/severity |
| Scoped metrics | `src/quarto_needs/metrics.py` | Trace/effective/successful/evidence coverage per scope, breakdowns, gap IDs |
| Gates and reports | `src/quarto_needs/quality.py` | Gate evaluation, profile enforcement, report construction/projection |
| Export integration | `src/quarto_needs/export.py` | `extensions.quartoNeeds.queries` + `.report` injection (additive optional parameter) |
| Commands | `src/quarto_needs/cli.py` | `quality`, `query <name>`, `--format text|json`, exit codes 0/1/2/3 |
| Lua adapter | `_extensions/quarto-needs/views.lua`, `shortcodes.lua`, `dashboard.lua`, `inspector.lua`, `needs.css` | `query=` intersection, `need-dashboard`, `need-inspector`, styling |
| Tests | `tests/test_config.py`, `tests/test_queries.py`, `tests/test_rules.py`, `tests/test_metrics.py`, `tests/test_quality.py`, extended CLI/export/Lua/view tests | Unit, conformance-vector, contract, render, accessibility coverage |
| Docs and showcase | `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `examples/book/.quarto-needs.toml`, `examples/book/governance.qmd` | Regeneration instructions and visible showcase |

---

### Task 1: Configuration model and loader

**Files:**
- Create: `src/quarto_needs/config.py`
- Modify: `pyproject.toml`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `ConfigurationError(ValueError)`, `NeedsConfig` (frozen dataclass), `load_config(root) -> NeedsConfig`, `EMBEDDED_DEFAULTS`, `reference_date() -> date`.
- Preserves: nothing reads configuration anywhere else yet; behavior of every existing module is unchanged.

- [ ] **Step 1: Write failing loader/default/error tests**

Cover at least:

```python
def test_missing_file_yields_embedded_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path)
    assert config.profile == "default"
    assert config.rule_settings == {}
    assert config.named_query_sources == {}

def test_full_document_parses_every_section(tmp_path: Path) -> None:
    source = tmp_path / ".quarto-needs.toml"
    source.write_text(
        'profile = "strict"\n'
        "[types.functional-requirement]\n"
        'required-attributes = ["priority"]\n'
        "[relations.\"verified-by\"]\n"
        'allowed-source-types = ["functional-requirement"]\n'
        "minimum-per-source = 1\n"
        "[governance]\n"
        'test-types = ["test-case"]\n'
        '[rules.REQ006]\nseverity = "error"\n'
        "[queries.approved-high-unverified]\n"
        'all = [{ field = "status", op = "eq", value = "approved" }]\n'
        '[gates]\nmax-errors = 0\n',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.profile == "strict"
    assert config.required_attributes["functional-requirement"] == ("priority",)
    assert config.relation_policies["verified-by"].minimum_per_source == 1
    assert config.test_types == ("test-case",)
    assert config.rule_settings["REQ006"].severity == "error"
    assert "approved-high-unverified" in config.named_query_sources
    assert config.gates.max_errors == 0

def test_unknown_keys_and_bad_values_are_configuration_errors(tmp_path: Path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text('profle = "strict"\n', encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(tmp_path)
```

Also cover: invalid profile name; unknown rule code in `[rules.*]`; unsupported severity for a rule; non-table sections; malformed inline clause tables surface as `ConfigurationError` (deeper AST validation lands in Task 2 but parse failures must already be located).

- [ ] **Step 2: Run focused tests and verify the module is absent**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement the frozen configuration**

`config.py` public shape:

```python
KNOWN_TOP_LEVEL_KEYS = (
    "profile", "types", "relations", "governance", "rules", "queries", "gates",
)

@dataclass(frozen=True, slots=True)
class RelationPolicy:
    allowed_source_types: tuple[str, ...] = ()
    allowed_target_types: tuple[str, ...] = ()
    minimum_per_source: int | None = None
    maximum_per_source: int | None = None

@dataclass(frozen=True, slots=True)
class RuleSetting:
    enabled: bool = True
    severity: str | None = None   # must be in the rule's supported severities

@dataclass(frozen=True, slots=True)
class Gates:
    max_errors: int = 0
    min_implementation_trace: float | None = None
    min_implementation_effective: float | None = None
    min_verification_trace: float | None = None
    min_verification_successful: float | None = None
    min_evidence: float | None = None
    require_risk_mitigation: bool = False
    scope: str = "approved-requirements"

@dataclass(frozen=True, slots=True)
class NeedsConfig:
    profile: str                                   # advisory | default | strict
    required_attributes: Mapping[str, tuple[str, ...]]
    relation_policies: Mapping[str, RelationPolicy]  # keyed by catalog/v1 name
    test_types: tuple[str, ...]                    # default ("test-case",)
    risk_types: tuple[str, ...]                    # default ("risk",)
    ineffective_endpoint_statuses: tuple[str, ...] # default below
    successful_test_statuses: tuple[str, ...]      # default ("passed",)
    expiry_attribute: str                          # default "expires"; "" disables
    rule_settings: Mapping[str, RuleSetting]
    named_query_sources: Mapping[str, Mapping[str, object]]
    gates: Gates
```

Defaults: profile `"default"`; `ineffective_endpoint_statuses = ("disapproved","rejected","failed","deprecated")`. Unknown top-level keys, unknown profiles, unknown rule codes (the code list arrives in Task 3 — until then accept exactly `REQ002`,`REQ004`,`REQ005`,`REQ006`,`REQ008`–`REQ015`), severities outside `error|warning|info`, negative cardinalities, and thresholds outside 0–100 raise `ConfigurationError` with the offending key in the message. Every mapping key is normalized to its casefolded form for lookup but preserved verbatim for display. Provide `reference_date()` returning `date.fromtimestamp(SOURCE_DATE_EPOCH)` when the variable holds a valid integer epoch, else `date.today()`.

Add to `pyproject.toml`:

```toml
dependencies = [
  "tomli>=1.1.0; python_version < '3.11'",
]
```

and import with `sys.version_info >= (3, 11) ? tomllib : tomli`.

- [ ] **Step 4: Run focused tests and full regressions**

Run:

```bash
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest tests/test_config.py -q
.venv/bin/python -m pytest -q
```

Expected: PASS; full suite unchanged (85 passed baseline).

---

### Task 2: Safe query AST, compiler, and reference evaluator

**Files:**
- Create: `src/quarto_needs/queries.py`
- Create: `tests/test_queries.py`

**Interfaces:**
- Produces: `compile_query(name, raw) -> Query`, `evaluate(query, snapshot) -> tuple[ObjectRecord, ...]`, `materialize_queries(config, snapshot) -> Mapping[str, tuple[str, ...]]`, `DEFAULT_QUERY_NAME = "approved-requirements"`, `QueryError(ConfigurationError)`.
- Consumes: `AnalysisSnapshot.objects/outgoing/incoming/objects_by_id`, `NeedsConfig`.

- [ ] **Step 1: Write failing safety/semantics/conformance tests**

Required cases:

1. **Operators**: `eq` casefolds strings and compares numbers/booleans exactly; `in` needs scalar-vs-set (`values=`); `contains` does collection membership and substring matching; `exists`/`missing` distinguish absent attributes from `null` and empty string.
2. **Fields**: allowlist `id,title,type,status,priority,tags,attributes.<name>`; unknown field → `QueryError`; `tags` matches casefolded membership on the object's tag tuple.
3. **Combinators**: `all`, `any`, `not`; nesting beyond depth 10 or more than 100 clauses total → `QueryError` naming the limit.
4. **Relation clauses**: `{relation="verified-by", direction="out", op="missing"}` matches an approved requirement with no outgoing `verified-by` **and** one whose tester authored `verifies` incoming (semantic inverse view); `direction` allowlist `in|out|either`; unknown catalog relation → `QueryError`. Build the inverse map from `DEFAULT_RELATION_CATALOG` by `(semantic_family, swapped roles)`; families without an inverse entry (e.g. `references`) match nothing in the inverted direction.
5. **Sort**: `sort = ["priority:asc", "id:asc"]` orders critical→high→medium→low→unspecified then ID casefolded; implicit final tiebreaker is ID; invalid field/direction → `QueryError`.
6. **Default query**: `approved-requirements` returns objects whose type contains `requirement` and whose status equals `approved`, sorted by priority rank then ID.
7. **Conformance vectors**: write `tests/fixtures/query-conformance.json` — a list of `{name, query, expected_ids}` cases evaluated against `tests/fixtures/canonical` plus a synthetic snapshot built inline. This file becomes the shared oracle for the Lua-side test in Task 7 (Lua only ever receives materialized sets, so the vectors pin what Python emits).

- [ ] **Step 2: Run focused tests and verify the module is absent**

Run: `.venv/bin/python -m pytest tests/test_queries.py -q`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement immutable AST and evaluation**

```python
@dataclass(frozen=True, slots=True)
class FieldClause:
    field: str            # allowlisted
    op: str               # eq | in | contains | exists | missing
    value: object = None  # eq/contains payload or scalar
    values: tuple[object, ...] = ()

@dataclass(frozen=True, slots=True)
class RelationClause:
    relation: str         # catalog/v1 name
    direction: str        # out | in | either
    op: str               # exists | missing

@dataclass(frozen=True, slots=True)
class AllClause: children: tuple["Clause", ...]
@dataclass(frozen=True, slots=True)
class AnyClause: children: tuple["Clause", ...]
@dataclass(frozen=True, slots=True)
class NotClause: child: "Clause"

Clause = FieldClause | RelationClause | AllClause | AnyClause | NotClause

@dataclass(frozen=True, slots=True)
class Query:
    name: str
    root: Clause
    sort: tuple[tuple[str, str], ...]   # (field, asc|desc)
```

`compile_query` validates while building (no two-phase type coercion): clause tables must carry either `field` or `relation`; combinators take lists (`any`, `all`) or a single table (`not`); counting clauses as it walks enforces depth ≤ 10 and count ≤ 100. String comparison casefolds via `str.casefold()`; there is no coercion between strings, numbers, booleans, or null. Evaluation resolves fields against `ObjectRecord` (`id/title/type/status/priority/tags` properties and `attributes`), and relation clauses against semantic adjacency derived from `snapshot.outgoing/incoming` filtered by `v1_name`, expanded with the inverse-view map. Results are deduplicated and ordered by the query's sort keys; `materialize_queries` compiles every configured named query plus the default and returns ordered ID tuples. Compilation errors raise `QueryError` (a `ConfigurationError` subclass) so both Tasks 5–6 surface exit code 2.

- [ ] **Step 4: Run focused tests, conformance generation check, and regressions**

Run:

```bash
.venv/bin/python -m pytest tests/test_queries.py -q
.venv/bin/python -m pytest -q
```

Expected: PASS; the conformance fixture is checked in and read-only afterwards.

---

### Task 3: Structured rule protocol and configurable governance rules

**Files:**
- Create: `src/quarto_needs/rules.py`
- Modify: `src/quarto_needs/diagnostics.py`
- Modify: `src/quarto_needs/analysis.py`
- Modify: `src/quarto_needs/validation.py`
- Create: `tests/test_rules.py`

**Interfaces:**
- Produces: `RuleSpec`, `RULES` registry, `run_rules(snapshot, config) -> tuple[Finding, ...]`, `Finding.fingerprint` property.
- Preserves: `validate()` signature/behavior (legacy four rules); structural suppression set; `analyze_project(root, files=None)` gains keyword-only `config: NeedsConfig | None = None` where `None` means *embedded defaults* (legacy rules only).

- [ ] **Step 1: Write failing protocol/rule/pipeline tests**

Required cases:

1. `Finding.fingerprint` is a stable SHA-256 hex string over `(code, object_id or "", message)`; equal inputs give equal fingerprints regardless of severity override.
2. Registry: each `RuleSpec` declares `code`, `title`, `help`, `default_severity`, `supported_severities`, and a pure `evaluate(ctx)`; codes are exactly REQ002, REQ004–REQ006 (legacy adapters) and REQ008–REQ015.
3. New rules fire only when enabled by config:
   - `REQ008 required-attribute-missing`: configured per-type required attribute absent or empty → warning;
   - `REQ009 relation-endpoint-not-allowed`: relation policy restricts endpoint types and the actual opposite endpoint type (or existence!) violates it → warning; dangling targets are already REQ005 and are skipped here;
   - `REQ010 relation-cardinality-violation`: per-source count of a policy-keyed relation below `minimum-per-source` or above `maximum-per-source` → warning;
   - `REQ011 approved-without-implementation`: approved requirement without implementation-family edge reaching an existing object → warning;
   - `REQ012 test-without-evidence`: object whose type is in `test_types` and status in `{approved} ∪ successful_test_statuses` without evidence-family edge → warning;
   - `REQ013 high-risk-without-mitigation`: object whose type is in `risk_types` and priority casefolds to `high`/`critical` without incoming mitigation-family edge → error-capable warning default;
   - `REQ014 orphaned-object`: no incoming and no outgoing edges → info;
   - `REQ015 expired-evidence`: evidence-family endpoint carrying the configured expiry attribute with an ISO date before `reference_date()` → warning; unparseable dates produce the same finding with `properties.reason = "unparseable"`.
4. Overrides: disabling REQ006 removes its findings; raising REQ013 to `error` changes severity only; unsupported severity → `ConfigurationError` at compile time of settings (tested via `run_rules` raising).
5. Pipeline: `analyze_project(canonical_fixture)` with no config file produces byte-identical findings to today (regression guard on the golden export tests); with a temp `.quarto-needs.toml` enabling all rules, new codes appear among `result.snapshot.findings` without affecting validity.

- [ ] **Step 2: Run focused tests and verify failures**

Run: `.venv/bin/python -m pytest tests/test_rules.py -q`
Expected: FAIL on missing module/API.

- [ ] **Step 3: Implement the registry and wire it into analysis**

`rules.py` evaluates against the built snapshot context (objects, outgoing/incoming indexes, config, reference date). Family helpers reuse `RelationRecord.semantic_family` (`implementation`, `verification`, `evidence`, `mitigation`). Legacy rules REQ002/REQ004/REQ005/REQ006 remain implemented in `validation.py`; the registry wraps them as adapters so severity overrides can re-map their severities *after* `validate()` runs (structural REQ004/REQ005 severities are pinned and never overridable).

In `analysis._analyze_batch`, after the structural gate and before constructing the snapshot: if `config` supplies any rule settings (or explicitly enables rules), run `run_rules` over a preliminary index build and merge those findings into the snapshot findings. With embedded defaults the merge is empty, keeping the frozen-contract projections identical. `analyze_project`/`analyze_objects` gain keyword-only `config=None` parameters threaded through.

Add `fingerprint` to `Finding` in `diagnostics.py` (computed lazily, not serialized into v1 `validation[]` — the envelope schema allows extra properties, but keeping output unchanged is safer; expose it in quality reports instead).

- [ ] **Step 4: Run focused tests, golden contracts, and regressions**

Run:

```bash
.venv/bin/python -m pytest tests/test_rules.py tests/test_analysis.py tests/test_export.py tests/test_v1_contract.py -q
.venv/bin/python -m pytest -q
```

Expected: PASS; golden fixtures untouched.

---

### Task 4: Scoped metrics with denominators and strong coverage

**Files:**
- Create: `src/quarto_needs/metrics.py`
- Create: `tests/test_metrics.py`

**Interfaces:**
- Produces: `compute_report_metrics(snapshot, config) -> ReportMetrics` with `to_dict()`; scope entries for `catalog` and `approved-requirements` (plus any configured named query used as a gate/dashboard scope).
- Preserves: `snapshot.metrics` keeps exactly the six legacy keys; `coverage()` untouched.

- [ ] **Step 1: Write failing denominator/strength tests**

Required cases (build small synthetic snapshots):

1. **Denominator discipline**: every percentage names its denominator; an empty denominator renders as `100.0` trace-free only when there is nothing to trace (mirror legacy convention) and `0` counts otherwise; totals always accompany percentages.
2. **Strength separation**: a requirement with an implementation edge to a `rejected` artifact counts for trace but not effective implementation coverage; verification to a failed test counts for trace but not successful; evidence requires a successfully verified test whose evidence endpoint exists, is allowed (not expired), and non-expired.
3. **Scopes**: catalog vs `approved-requirements` differ; breakdowns by type/status/priority and per-named-query membership counts are present with deterministic key order.
4. **Gaps**: gap ID lists (unimplemented/unverified/uncovered evidence) are sorted with `text_key` semantics and referenced by the dashboard later.
5. Expiry interacts with `reference_date()` via `SOURCE_DATE_EPOCH` in tests.

- [ ] **Step 2: Run focused tests and verify the module is absent**

Run: `.venv/bin/python -m pytest tests/test_metrics.py -q`
Expected: FAIL on missing module.

- [ ] **Step 3: Implement metrics computation**

Structure:

```python
@dataclass(frozen=True, slots=True)
class CoverageMeasure:
    covered: int
    total: int
    @property
    def percent(self) -> float: ...

@dataclass(frozen=True, slots=True)
class ScopeMetrics:
    name: str
    denominator: int
    breakdowns: Mapping[str, Mapping[str, int]]     # type/status/priority
    coverage: Mapping[str, CoverageMeasure]          # five strengths
    gaps: Mapping[str, tuple[str, ...]]

def compute_report_metrics(snapshot, config, queries: Mapping[str, tuple[str, ...]] | None = None) -> ReportMetrics
```

Implementation walks `snapshot.objects/outgoing/incoming` once per scope; family/status policies come from config (`ineffective_endpoint_statuses`, `successful_test_statuses`, `expiry_attribute`, `reference_date()`). Output dicts use `sort_keys`-stable plain types so JSON embedding is deterministic.

- [ ] **Step 4: Run focused tests and regressions**

Run:

```bash
.venv/bin/python -m pytest tests/test_metrics.py tests/test_analysis.py tests/test_cli.py -q
.venv/bin/python -m pytest -q
```

Expected: PASS; legacy metric surfaces unchanged.

---

### Task 5: Gates, profiles, quality reports, and the `quality` command

**Files:**
- Create: `src/quarto_needs/quality.py`
- Modify: `src/quarto_needs/cli.py`
- Create: `tests/test_quality.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Produces: `QualityReport` with `to_dict()`, `evaluate_gates(report_metrics, findings, gates) -> tuple[GateResult, ...]`, `profile_exit_code(profile, structural_errors, gate_failures) -> int`, `build_quality_report(root, config) -> QualityReport`.
- CLI: `quarto-needs quality [--format text|json] [--output PATH]`; exit `0` pass, `1` policy failure (artifacts still written), `2` configuration/usage error, `3` operational failure.

- [ ] **Step 1: Write failing profile/gate/CLI tests**

Required cases:

1. Gate evaluation covers: max error count; the four coverage percentages; evidence coverage; risk mitigation toggle; each result records threshold, actual, denominator, and pass/fail; disabled gates (None) never fail.
2. Profiles: `advisory` returns 0 despite failing semantic gates (findings still listed); `default` returns 1 only for structural errors/config; `strict` returns 1 when any configured gate fails. Invalid config → 2 everywhere; simulate operational failure (unwritable output directory) → 3.
3. CLI text format prints scopes, coverage lines with denominators, gaps summary, findings by severity, and gate table; JSON format round-trips `report.to_dict()`; `--output` writes the JSON atomically and still writes it when gates fail (exit 1), verifying the CI-artifact guarantee.
4. `scan`/`check` keep their current exit semantics under all three profiles.

- [ ] **Step 2: Run focused tests and verify the command is absent**

Run: `.venv/bin/python -m pytest tests/test_quality.py tests/test_cli.py -q`
Expected: FAIL on missing module/subcommand.

- [ ] **Step 3: Implement reports and command wiring**

`quality.py` composes `analyze_project(root, config=config)`, `materialize_queries`, `compute_report_metrics`, rule findings (already merged into the snapshot), and gate evaluation into:

```python
{
  "schemaVersion": "1",
  "generator": {"name": ..., "version": ...},
  "profile": ...,
  "referenceDate": "YYYY-MM-DD",
  "configuration": {"path": ".quarto-needs.toml", "present": bool},
  "scopes": {...},                     # from ReportMetrics.to_dict()
  "findings": {"counts": {...}, "bySeverity": {...}},
  "gates": [{"name":..., "scope":..., "threshold":..., "actual":..., "passed":...}],
}
```

CLI `quality` loads config (invalid → print + return 2), builds the report, optionally writes `--output` atomically, prints text/JSON, then maps profile + gate results to the exit code. Shared config loading appears once in `main` so `scan/check/coverage/trace/export` also fail fast with exit 2 on broken configuration files.

- [ ] **Step 4: Run focused tests and regressions**

Run:

```bash
.venv/bin/python -m pytest tests/test_quality.py tests/test_cli.py -q
.venv/bin/python -m pytest -q
```

Expected: PASS.

---

### Task 6: `query` command and named-query materialization in the graph

**Files:**
- Modify: `src/quarto_needs/cli.py`
- Modify: `src/quarto_needs/export.py`
- Modify: `tools/quarto_needs_pre_render.py` (no behavioral change; verified)
- Modify: `tests/test_cli.py`
- Modify: `tests/test_export.py`

**Interfaces:**
- Produces: `quarto-needs query <name> [--format text|json]`; `build_v1_payload(snapshot, *, extra_extensions=None)`; `write_build_outputs(..., extra_extensions=None)`.
- Preserves: default calls produce identical bytes (contract/golden tests prove it).

- [ ] **Step 1: Write failing command/materialization tests**

Required cases:

1. `query approved-high-unverified --format json` prints `{"name": ..., "ids": [...]}` in materialized order; text prints one ID per line; unknown name → exit 2 listing available names; invalid config → exit 2.
2. `build()` with a configured project writes `extensions.quartoNeeds.queries` as `{name: [ordered ids]}` including the default `approved-requirements`; without a config file the key is absent (byte-identical output).
3. `extra_extensions` merging conflicts (attempting to overwrite `generator`) raise `ValueError`.
4. Golden/contract tests still pass with default arguments.

- [ ] **Step 2: Run focused tests and verify failures**

Run: `.venv/bin/python -m pytest tests/test_cli.py tests/test_export.py -q`
Expected: FAIL on missing subcommand/parameter.

- [ ] **Step 3: Implement**

`cli.build` computes `extra = {"quartoNeeds": {"queries": materialized}}` when a config file with named queries exists and passes it through `write_build_outputs` into `build_v1_payload`, which deep-merges under `extensions.quartoNeeds` without disturbing `generator`/`relationCatalog*`. The `query` command shares the analysis pass pattern (one `analyze_project` per invocation).

- [ ] **Step 4: Run focused tests, contracts, and sync determinism**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_export.py tests/test_v1_contract.py tests/test_extension_sync.py -q
.venv/bin/python -m pytest -q
```

Expected: PASS; `make sync-example` twice leaves example outputs byte-identical (no config file in the example yet).

---

### Task 7: Lua query intersection and the dashboard shortcode

**Files:**
- Create: `_extensions/quarto-needs/dashboard.lua`
- Modify: `_extensions/quarto-needs/views.lua`
- Modify: `_extensions/quarto-needs/shortcodes.lua`
- Modify: `_extensions/quarto-needs/needs.css`
- Create: `tests/test_dashboard.lua` harness additions in `tests/test_quarto_views.py` (Python-driven)
- Modify: `tests/fixtures/views/.quarto-needs/needs.json`
- Modify: `tests/fixtures/views/index.qmd`

**Interfaces:**
- Produces: `views.apply_named_query(objects, kwargs, graph)`, `{{< need-dashboard query="..." >}}`, `{{< need-count query="approved-requirements" >}}` (and `need-table`/`need-list` parity).
- Static guarantee: dashboards render identically useful content in HTML, DOCX, and PDF with zero JavaScript.

- [ ] **Step 1: Write failing HTML/three-format assertions**

Fixture updates: add `extensions.quartoNeeds.queries` (e.g. `approved-requirements` containing `REQ-APPROVED`) and a minimal `report` projection mirroring Task 5's schema. Index gains:

```qmd
{{< need-dashboard >}}
{{< need-count query="approved-requirements" >}}
{{< need-table query="approved-requirements" columns="id;status" >}}
```

Assertions: dashboard shows whole-catalog and approved-scope coverage numbers with denominators; unknown `query="nope"` renders `Unknown query: nope` warning class and logs; DOCX/PDF contain the same labels/numbers statically; `need-count` respects the named query (renders `1`); legacy filters intersect (adding `status="draft"` to a named query yields the empty state).

- [ ] **Step 2: Run view tests and verify failures**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -q`
Expected: FAIL on new assertions; existing ones green.

- [ ] **Step 3: Implement intersection and dashboard rendering**

`views.filter` keeps legacy behavior; a new `views.select(graph, kwargs)` resolves `query=` first (warning + empty set when unknown), then applies legacy filters as intersection. Table/list/count/matrix/flow switch to `views.select`. `dashboard.lua` reads `graph.extensions.quartoNeeds.report` and renders: KPI table (coverage rows with `value% (covered/total)`), gap bullet lists linking member IDs via `views.link`, distributions by type/status/priority as plain tables, findings-by-severity counts. Numbers come from the projection only; missing report renders `Dashboard report unavailable.` as `need-view-empty`. CSS adds layout-only classes (`need-dashboard`, `need-kpi-*`) using existing color tokens; no color-only meaning.

- [ ] **Step 4: Run Lua, view, three-format, and extension-sync tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_quarto_views.py tests/test_views_helpers.py tests/test_extension_sync.py -q
.venv/bin/python -m pytest -q
```

Expected: PASS.

---

### Task 8: Inspector shortcode with static accessible fallback

**Files:**
- Create: `_extensions/quarto-needs/inspector.lua`
- Modify: `_extensions/quarto-needs/shortcodes.lua`
- Modify: `_extensions/quarto-needs/needs.css`
- Modify: `tests/fixtures/views/index.qmd`
- Modify: `tests/test_quarto_views.py`

**Interfaces:**
- Produces: `{{< need-inspector ID >}}` — heading, badges, declared attributes, provenance (file:line), both relation directions (reusing `relations.lua` groups), and associated findings for that ID.
- Accessibility: keyboard-operable without JavaScript (native headings/lists; no dialog, no focus trap needed since content is inline), labelled region with reserved view id.

- [ ] **Step 1: Write failing static/accessibility assertions**

Index gains `{{< need-inspector REQ-APPROVED >}}` and `{{< need-inspector UNKNOWN-ID >}}`. Assert HTML: section has `role="region"`, an `aria-labelledby` pointing at the rendered heading id, contains provenance `index.qmd`, attribute values, both relation group labels; unknown ID yields the standard `Unknown need ID: UNKNOWN-ID` warning. DOCX text and PDF text contain the same labels and values.

- [ ] **Step 2: Run view tests and verify failures**

Run: `.venv/bin/python -m pytest tests/test_quarto_views.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`inspector.render(graph, id)` composes existing primitives (`views.badge`, `relations.render_for_card`, findings filtered from `graph.validation` by `object_id`, attributes as a definition list, provenance paragraph). Everything is ordinary blocks — no Raw HTML, no JS — so DOCX/PDF keep essential information. CSS provides borders/spacing only.

- [ ] **Step 4: Run full Lua/render suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

---

### Task 9: Showcase, documentation, and milestone acceptance

**Files:**
- Create: `examples/book/.quarto-needs.toml`
- Create: `examples/book/governance.qmd`
- Modify: `README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `Makefile`
- Modify: `tests/test_example_project.py`

- [ ] **Step 1: Configure and exercise the Aegis book**

`examples/book/.quarto-needs.toml` enables the governance rules appropriate to the example, declares named queries (`approved-high-unverified`, `evidence-gaps`, plus the implicit default), and strict-profile gates that the published book passes. `governance.qmd` demonstrates `need-dashboard`, `need-inspector`, named-query tables/counts, and documents the gate/profile model. The example test asserts: dashboard/inspector markup in `governance.html`; `quality --format json` exit 0; `query approved-high-unverified` exits 0; strict `quality` passes; three-format render contains the new sections; `need-ref-missing` absent everywhere.

- [ ] **Step 2: Document**

README: configuration reference (every supported key), query grammar and limits, rule catalog REQ002–REQ015 with severities, metrics/gates semantics with denominators, profile/exit-code table, new commands and shortcodes. ARCHITECTURE: pipeline diagram gains `config -> queries/rules/metrics -> report projection -> Lua views`. CONTRIBUTING: fixture policy for the conformance vector and goldens.

- [ ] **Step 3: Acceptance run**

```bash
make setup && make test
make sync-example && make sync-example   # SHA-256 pairs identical
make check-example
.venv/bin/quarto-needs --root examples/book quality --format json
.venv/bin/quarto-needs --root examples/book query approved-high-unverified
make render-example-all                  # html/docx/pdf exit 0
curl --fail --silent http://127.0.0.1:8777/ >/dev/null   # preview alive; refresh to final state
.venv/bin/python -m pytest -q
```

Expected: everything passes; no unexpected skips; generated artifacts deterministic; docs current. Record results in the SDD ledger.
