# Review package

Snapshot range: `task-11-fix1` -> `final-fix`

## Files changed (37)

- `CONTRIBUTING.md`
- `Makefile`
- `README.md`
- `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md`
- `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph.md`
- `docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md`
- `docs/superpowers/specs/2026-08-26-quarto-needs-capability-evolution.md`
- `examples/book/.gitignore`
- `pyproject.toml`
- `schemas/baseline-v1.schema.json`
- `schemas/diff-v1.schema.json`
- `schemas/vendor/sarif-2.1.0/VENDORED.md`
- `schemas/vendor/sarif-2.1.0/sarif-schema.json`
- `src/quarto_needs/analysis.py`
- `src/quarto_needs/cli.py`
- `src/quarto_needs/diff.py`
- `src/quarto_needs/exporters/__init__.py`
- `src/quarto_needs/exporters/csv_export.py`
- `src/quarto_needs/exporters/junit_export.py`
- `src/quarto_needs/exporters/markdown_export.py`
- `src/quarto_needs/exporters/sarif_export.py`
- `src/quarto_needs/impact.py`
- `src/quarto_needs/metrics.py`
- `src/quarto_needs/quality.py`
- `src/quarto_needs/queries.py`
- `src/quarto_needs/snapshot.py`
- `src/quarto_needs/validation.py`
- `tests/test_ci_workflow.py`
- `tests/test_cli.py`
- `tests/test_diff.py`
- `tests/test_example_project.py`
- `tests/test_export_csv.py`
- `tests/test_export_junit.py`
- `tests/test_export_markdown.py`
- `tests/test_export_sarif.py`
- `tests/test_fingerprints.py`
- `tests/test_impact.py`

## Summary

4582 lines added, 130 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/CONTRIBUTING.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/CONTRIBUTING.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/CONTRIBUTING.md	2026-08-26 15:13:55.902196766 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/CONTRIBUTING.md	2026-08-26 21:43:54.152982277 -0300
@@ -1,21 +1,21 @@
 # Contributing
 
 ## Development setup
 
 ```bash
 make setup
 source .venv/bin/activate
 ```
 
 `make setup` creates `.venv` and installs the package together with its
-`test` extra (`pytest`, `jsonschema`). No runtime dependency may be added
+`test` extra (`pytest`, `jsonschema`, `PyYAML`). No runtime dependency may be added
 without a plan that explicitly allocates it.
 
 ## Workflow order
 
 Every change follows strict red-green-refactor: write the failing test
 first, run it to observe the intended failure, then implement the minimum
 production change that turns it green, and only then refactor. A pull
 request that adds production behavior without a persisted test covering it
 is incomplete.
 
@@ -68,20 +68,27 @@
 Run the full gate before opening a PR:
 
 ```bash
 make setup               # install editable package plus test extra
 make test                # full Python, Lua, and render suite
 make sync-example        # synchronize extension assets and rebuild the graph
 make check-example       # validate the regenerated example graph
 make render-example-all  # render the example book to HTML, DOCX, and PDF
 ```
 
+The `quality` CI job generates JSON, CSV, SARIF, JUnit, Markdown, and quality
+report artifacts from the Aegis showcase. Its artifact upload uses
+`if: always()`: a policy failure still leaves the diagnostic outputs available
+for review. Operational failures exit `3` and name the artifact that could not
+be produced. SARIF upload is a separate least-privilege step; workflows must
+never use `pull_request_target` to execute pull-request code.
+
 The example book is governed by `examples/book/.quarto-needs.toml` and runs the
 `strict` profile, so it also has to keep passing its own gates:
 
 ```bash
 .venv/bin/quarto-needs --root examples/book quality --format json
 .venv/bin/quarto-needs --root examples/book query approved-high-unverified
 ```
 
 If Quarto is installed you can also serve the book with live reload:
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md	2026-08-26 14:52:55.992058367 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md	2026-08-26 21:43:54.156982260 -0300
@@ -1,12 +1,17 @@
 # Quarto-Needs Milestone 4A Exporters and CI Implementation Plan
 
+> **Checkpoint (2026-08-26): complete.** CSV, SARIF, JUnit, and Markdown
+> exporters; deterministic CLI integration; strict CI matrix; always-uploaded
+> artifacts; and Aegis acceptance are implemented. The local acceptance run is
+> 235 passed and 29 environment-dependent skips, with no xfails or warnings.
+
 > **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
 
 **Goal:** Deliver the CSV, SARIF, JUnit, and Markdown exporters behind `export --format`, close the exit-code-3 gap carried from the Milestone 3 whole-branch review, and split CI into the spec's `core`/`quarto`/`quality` jobs with preserved artifacts and a step summary.
 
 **Architecture:** Every exporter is a pure function from the existing single-pass analysis products (`AnalysisSnapshot`, `QualityReport`, optionally a loaded baseline plus `DiffReport`/`ImpactReport`) to a deterministic string, written atomically through `export._write_atomic_text`. The CLI remains the only filesystem layer and still analyzes exactly once per invocation. The Markdown summary may load a baseline and run the pure `diff`/`impact` functions over the already-held snapshot; loading a baseline never analyzes.
 
 **Tech Stack:** Python 3.10+, standard-library `csv`/`xml.etree`/`hashlib`/`json`, pytest, `jsonschema` (already a test dependency), `pyyaml` added to the `test` extra only (workflow structural tests); no new runtime dependency.
 
 **Spec:** `docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md` — sections "Exporters", "CI design", "CLI and failure semantics", and the gate under "### Milestone 4".
 
@@ -313,24 +318,24 @@
     rows = list(csv.DictReader((tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8").splitlines()))
     assert rows[0]["id"] == "REQ-1"
     assert rows[0]["type"] == "system-requirement"
 
 
 def test_csv_neutralizes_formula_injection(tmp_path: Path) -> None:
     write_project(tmp_path)
     csv_export.write_all(tmp_path / "csv", build(tmp_path))
 
     text = (tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8")
-    cells = {row["title"]: None for row in csv.DictReader(text.splitlines())}
+    cells = {value: None for row in csv.DictReader(text.splitlines()) for value in row.values()}
     dangerous = [value for value in cells if value.startswith(("=", "+", "-", "@", "\t", "\r"))]
     assert not dangerous
-    assert any(value.startswith("'=") for value in cells), "the neutralized title must carry the apostrophe prefix"
+    assert any(value.startswith("'=") for value in cells), "the neutralized cell must carry the apostrophe prefix"
 
 
 def test_csv_is_deterministic(tmp_path: Path, monkeypatch) -> None:
     monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
     write_project(tmp_path)
     first = csv_export.render_objects(build(tmp_path))
     second = csv_export.render_objects(build(tmp_path))
     assert first == second
 ```
 
@@ -365,21 +370,21 @@
 
 Create `tests/test_export_sarif.py`:
 
 ```python
 from __future__ import annotations
 
 import json
 from pathlib import Path
 
 import pytest
-from jsonschema import Draft202012Validator
+from jsonschema import Draft7Validator
 
 from quarto_needs.analysis import analyze_project
 from quarto_needs.config import load_config
 from quarto_needs.exporters import sarif_export
 
 ROOT = Path(__file__).resolve().parents[1]
 SCHEMA = ROOT / "schemas" / "vendor" / "sarif-2.1.0" / "sarif-schema.json"
 
 
 def write_project(root: Path) -> None:
@@ -395,30 +400,30 @@
     )
 
 
 def snapshot_with_findings(root: Path):
     result = analyze_project(root, config=load_config(root))
     return result.declarations and result.findings and result or None
 
 
 def test_sarif_validates_against_the_vendored_schema(tmp_path: Path) -> None:
     schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
-    Draft202012Validator.check_schema(schema)
+    Draft7Validator.check_schema(schema)
 
     (tmp_path / "ok.qmd").write_text(
         "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
     )
     result = analyze_project(tmp_path, config=load_config(tmp_path))
     assert result.snapshot is not None
 
     payload = json.loads(sarif_export.render(result.snapshot))
-    Draft202012Validator(schema).validate(payload)
+    Draft7Validator(schema).validate(payload)
 
 
 def test_sarif_maps_findings_with_locations_and_fingerprints(tmp_path: Path) -> None:
     write_project(tmp_path)
     result = analyze_project(tmp_path, config=load_config(tmp_path))
     assert any(f.code == "REQ004" for f in result.findings)
 
     payload = json.loads(sarif_export.render_from_findings(result.findings))
     result_entry = next(r for r in payload["runs"][0]["results"] if r["ruleId"] == "REQ004")
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph.md	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph.md	2026-08-26 21:43:54.156982260 -0300
@@ -0,0 +1,250 @@
+# Quarto-Needs Milestone 5A Interactive Graph Implementation Plan
+
+**Date:** 2026-08-26  
+**Status:** Ready after Milestone 4B acceptance  
+**Design inputs:** evolution design and capability evolution amendment
+
+## Goal
+
+Deliver an offline-first, accessible `need-graph` experience that uses the same
+query, relation, diff, and impact semantics as the CLI. HTML progressively adds
+interaction; static formats and JavaScript-disabled HTML retain an equivalent
+diagram and edge table.
+
+The differentiating feature is a graph that explains engineering change. A user
+can inspect a need, show its neighborhood, highlight a relation path, overlay a
+baseline diff, and see why an object is impacted without leaving the rendered
+book.
+
+## Non-goals
+
+- Editing requirements or governance state in the browser.
+- Sending the full semantic snapshot to the browser.
+- Fetching CDN assets or remote graph data at render time.
+- Rendering an unbounded project graph and hiding truncated results.
+- Reimplementing query, diff, impact, or relation rules in JavaScript.
+- Replacing the static fallback with a screenshot of the interactive canvas.
+
+## User-facing contract
+
+```qmd
+{{< need-graph
+  query="approved-high"
+  relations="implements,verified-by,evidenced-by"
+  depth="2"
+  layout="hierarchical"
+  baseline="baselines/quarto-needs.json"
+  mode="diff"
+>}}
+```
+
+The minimal invocation remains `{{< need-graph >}}`. Options are validated in
+Python and written into the generated index; Lua never evaluates a query string.
+
+HTML controls include:
+
+- search by ID or title;
+- type, status, priority, tag, relation, and change-state facets;
+- zoom, fit, reset, and keyboard focus controls;
+- one-hop neighborhood expansion inside the already published projection;
+- shortest explanatory path between two visible nodes;
+- an inspector action using the existing inspector component;
+- diff legend and baseline/current toggle when `mode="diff"`;
+- impact origin, direct/transitive status, distance, path, and relation labels
+  when `mode="impact"`.
+
+Control state may be encoded in the URL fragment only when it contains public
+IDs and declared facet values. It never stores titles, attributes, source
+locations, or arbitrary query text.
+
+## Data contracts
+
+### Public projection
+
+Add `schemas/graph-public-v1.schema.json` and a Python model/writer with this
+logical shape:
+
+```json
+{
+  "schemaVersion": "graph-public-v1",
+  "view": {
+    "id": "stable-render-local-id",
+    "layout": "hierarchical",
+    "mode": "catalog",
+    "limits": {"nodes": 100, "edges": 300}
+  },
+  "nodes": [
+    {
+      "id": "REQ-1",
+      "title": "Publishable title",
+      "type": "requirement",
+      "status": "approved",
+      "priority": "high",
+      "tags": ["iam"],
+      "href": "requirements.html#req-1",
+      "change": "modified"
+    }
+  ],
+  "edges": [
+    {
+      "source": "REQ-1",
+      "target": "TC-1",
+      "relation": "verified-by",
+      "label": "verified by",
+      "change": "unchanged",
+      "pathMember": true
+    }
+  ],
+  "impact": []
+}
+```
+
+Only ID, title, type, status, priority, allowed tags, publishable relations, and
+resolved public hrefs are emitted by default. `change` and `impact` are included
+only when their modes are requested. Removed nodes use baseline public fields,
+are visually and textually marked as removed, and never regain fields denied by
+the current publication policy.
+
+### Static equivalence
+
+For every graph instance the renderer emits:
+
+1. a deterministic static graph asset with node labels and a legend;
+2. an accessible table containing source, relation, target, change state, and
+   impact explanation where applicable;
+3. a summary with node/edge counts and any narrowing guidance;
+4. the progressive HTML container and reduced JSON projection.
+
+“Equivalent” means the same selected nodes, relations, change classifications,
+and impact paths. It does not require identical spatial layout.
+
+## Task 1 — Freeze projection and privacy contracts
+
+**Files:** `src/quarto_needs/graph_projection.py`,
+`schemas/graph-public-v1.schema.json`, `tests/test_graph_projection.py`
+
+- Write failing tests for stable ordering, schema validation, allowed fields,
+  unsafe custom attributes, local paths, source locations, bodies, and baseline
+  ghost nodes.
+- Add an adversarial fixture whose denied values are unique search tokens.
+- Implement a small immutable projection model and atomic JSON writer.
+- Falsify every deny assertion by temporarily exposing the field and proving the
+  test fails.
+
+## Task 2 — Add graph view configuration and bounded selection
+
+**Files:** `src/quarto_needs/config.py`, `src/quarto_needs/queries.py`,
+`src/quarto_needs/graph_projection.py`, `tests/test_graph_selection.py`
+
+- Define defaults: 100 nodes, 300 edges, depth 1, catalog mode, deterministic
+  layout seed, and an explicit relation allowlist.
+- Reuse named-query evaluation; do not introduce a browser query evaluator.
+- Return a structured `GraphLimitExceeded` diagnostic containing actual counts,
+  configured limits, and suggested facets.
+- Test sparse, dense, cyclic, disconnected, high-fanout, and empty selections.
+
+## Task 3 — Compose catalog, diff, and impact overlays
+
+**Files:** `src/quarto_needs/graph_projection.py`,
+`tests/test_graph_overlays.py`
+
+- Map the existing `DiffReport` classifications onto nodes and relations.
+- Keep removed objects and relations as baseline ghosts in diff mode.
+- Map existing `ImpactReport` paths without recomputing traversal in the view.
+- Test configuration/reference-date guards and `--recompute-with current`
+  behavior through the existing engines.
+- Assert that projection order remains byte-identical across input permutations.
+
+## Task 4 — Generate the static fallback
+
+**Files:** `src/quarto_needs/graph_render.py`,
+`tests/test_graph_render.py`
+
+- Produce a deterministic graph description and accessible edge-table data.
+- Use a local renderer selected during implementation; pin its version and
+  document its license. Do not add a required network call.
+- Keep text labels, change markers, and relation labels visible without relying
+  on color.
+- Add golden tests plus a semantic assertion that the asset/table/projection
+  contain identical node and edge sets.
+
+## Task 5 — Add the Quarto shortcode and static AST
+
+**Files:** `examples/book/_extensions/quarto-needs/shortcodes.lua`,
+`examples/book/_extensions/quarto-needs/graph.lua`,
+`examples/book/_extensions/quarto-needs/_extension.yml`,
+`tests/test_quarto_graph.py`
+
+- Parse prevalidated view identifiers and options from the generated index.
+- Emit semantic figure, legend, summary, table, narrowing message, and progressive
+  container through Pandoc AST.
+- Ensure HTML without JavaScript, PDF, and DOCX contain the essential graph data.
+- Add malformed/missing projection tests that render a visible diagnostic rather
+  than an empty container.
+
+## Task 6 — Build the local interactive client
+
+**Files:** `examples/book/_extensions/quarto-needs/graph.js`,
+`examples/book/_extensions/quarto-needs/graph.css`, vendored dependency files,
+`tests/test_graph_assets.py`
+
+- Vendor and checksum a pinned Cytoscape.js release and record license metadata.
+- Initialize only after the static fallback and projection validate successfully.
+- Implement search, facets, fit/reset, selection, neighborhood, path highlighting,
+  diff toggle, impact explanation, and inspector integration.
+- Use deterministic node ordering and seed. Persist only safe state in the URL
+  fragment.
+- Hide the canvas from assistive technology when its information is already
+  represented by the synchronized semantic table.
+
+## Task 7 — Accessibility and interaction conformance
+
+**Files:** `tests/test_graph_accessibility.py`, browser-level test fixtures
+
+- Verify complete keyboard operation, visible focus, control names, status
+  announcements, legend text, contrast, reduced motion, and dialog focus return.
+- Verify the fallback remains visible if script loading or initialization fails.
+- Verify filters update the semantic table and announced counts, not only the
+  canvas.
+- Run automated accessibility checks and record a manual keyboard protocol.
+
+## Task 8 — Aegis showcase and author documentation
+
+**Files:** Aegis QMD/configuration, `README.md`, `ARCHITECTURE.md`,
+`CONTRIBUTING.md`
+
+- Add catalog, diff, and impact graph examples with named queries.
+- Include one deliberately large fixture that exercises visible limit guidance.
+- Document privacy projection, offline assets, configuration, static behavior,
+  baseline modes, troubleshooting, and regeneration commands.
+- Keep the default published Aegis book passing its strict quality profile.
+
+## Task 9 — Performance and security gates
+
+**Files:** `tests/test_graph_performance.py`, `tests/test_graph_security.py`, CI
+
+- Benchmark 100/300, 1,000/3,000, dense, cyclic, and high-fanout synthetic graphs.
+  The default interactive cap remains 100/300; larger figures require an explicit
+  project override and still receive a warning.
+- Establish budgets for projection generation, asset size, initialization, facet
+  latency, and memory before optimizing.
+- Test HTML/JSON escaping, malicious titles/IDs/tags, path traversal, unsafe hrefs,
+  prototype-pollution keys, and denied-field token absence.
+- Run the graph without external network access and under a restrictive content
+  security policy.
+
+## Acceptance gate
+
+- Full Python and Lua helper suites pass with no xfails or warnings.
+- Aegis renders cleanly in HTML, PDF, and DOCX.
+- The HTML graph works with network access disabled.
+- Disabling JavaScript preserves the selected nodes, relations, change states,
+  impact paths, legend, and counts.
+- Keyboard-only operation completes search, filtering, selection, path display,
+  and inspector open/close.
+- Adversarial denied values do not occur in any shipped browser asset.
+- Repeated builds with fixed semantic inputs and layout seed are byte-identical.
+- Limits are visible and actionable; no selection is silently truncated.
+- Catalog, diff, and impact graph contents match the corresponding engine
+  reports exactly.
+
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md	2026-08-26 02:28:58.028504270 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md	2026-08-26 21:43:54.160982244 -0300
@@ -383,16 +383,18 @@
 
 ## Deferred work and non-goals
 
 - Arbitrary Python/Lua rule plugins or expression evaluation.
 - Automatic rename detection in semantic diffs.
 - Git as a mandatory baseline provider.
 - Tree-sitter language coverage before scanner contracts stabilize.
 - ReqIF importing, round-trip synchronization, rich XHTML, and `.reqifz` in the initial ReqIF milestone.
 - Client-side mutation of requirements or governance state.
 - Mandatory persistent PR comments or workflows with broad write permissions.
-- Full Sphinx-Needs syntax or feature parity.
+- Full Sphinx-Needs source-syntax emulation. Capability parity and leadership are
+  tracked by the
+  [capability evolution amendment](2026-08-26-quarto-needs-capability-evolution.md).
 
 ## Format references
 
 - [OMG Requirements Interchange Format 1.2 and normative schemas](https://www.omg.org/spec/ReqIF/1.2/)
 - [StrictDoc ReqIF parser](https://github.com/strictdoc-project/reqif)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/specs/2026-08-26-quarto-needs-capability-evolution.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/docs/superpowers/specs/2026-08-26-quarto-needs-capability-evolution.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/specs/2026-08-26-quarto-needs-capability-evolution.md	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/docs/superpowers/specs/2026-08-26-quarto-needs-capability-evolution.md	2026-08-26 21:43:54.160982244 -0300
@@ -0,0 +1,128 @@
+# Quarto-Needs Capability Evolution Amendment
+
+**Date:** 2026-08-26  
+**Status:** Proposed product direction; implementation remains milestone-gated  
+**Amends:** `2026-08-25-quarto-needs-evolution-design.md`
+
+## Decision
+
+Quarto-Needs will pursue **capability parity and eventual capability leadership**
+rather than source-syntax parity with Sphinx-Needs. Existing Sphinx projects may
+later receive a migration adapter, but the primary authoring surface remains
+Quarto-native: fenced `.need` blocks, shortcodes, configuration, Pandoc AST, and
+precomputed deterministic projections.
+
+This distinction matters. Sphinx-Needs has a mature directive, role, filtering,
+layout, service, and builder ecosystem. Reproducing its syntax would couple this
+project to Sphinx's document model and make it harder to exploit Quarto's
+multi-format rendering, executable documents, dashboard support, and Pandoc
+interoperability. Reproducing the useful capabilities behind that syntax keeps
+the model portable and the user experience coherent.
+
+## Capability benchmark
+
+The comparison uses the current Sphinx-Needs documentation and adjacent
+requirements-engineering tools as design inputs, not as compatibility promises.
+
+| Capability | Reference implementations | Quarto-Needs now | Target |
+|---|---|---|---|
+| Typed requirements and configurable relations | [Sphinx-Needs configuration](https://sphinx-needs.readthedocs.io/en/latest/configuration.html), [ReqIF 1.2](https://www.omg.org/spec/ReqIF/1.2/) | Typed objects, relation catalog, inverse links, profiles | Type-specific schemas, inheritance, cardinality, and graph constraints |
+| Lists, tables, charts, flow, sequence, Gantt, architecture and UML views | [Sphinx-Needs directives](https://sphinx-needs.readthedocs.io/en/latest/directives/index.html) | Cards, tables, flow, dashboard and inspector foundations | A coherent view catalog backed by one query engine and one projection |
+| Imports and external services | [needimport](https://sphinx-needs.readthedocs.io/en/latest/directives/needimport.html), [needservice](https://sphinx-needs.readthedocs.io/en/latest/directives/needservice.html) | Local QMD catalog | Cached, provenance-preserving adapters with lock files and explicit trust policy |
+| Declarative schema validation | [Sphinx-Needs schemas](https://sphinx-needs.readthedocs.io/en/latest/schema/) | Built-in rules, structured findings, JSON Schemas for artifacts | Per-type JSON Schema plus relation/network constraints and migration diagnostics |
+| Dynamic values and variants | [Sphinx-Needs dynamic functions](https://sphinx-needs.readthedocs.io/en/latest/dynamic_functions.html) | Named safe queries and deterministic derived metrics | Safe declarative derived fields and build variants; no arbitrary code evaluation |
+| Baseline, semantic diff and impact | IBM DOORS Next change and link workflows, [OpenFastTrace](https://github.com/itsallcode/openfasttrace/blob/main/doc/user_guide.md) | Canonical baseline, classified diff, relocation, union-graph impact paths | Interactive delta overlays, suspect links, review state and signed attestations |
+| Review fingerprints | [Doorstop item reference](https://doorstop.readthedocs.io/en/v1.3/reference/items/) | Authored and semantic fingerprints | Link-level review fingerprints and explicit suspect-state propagation |
+| Deep and transitive coverage | [OpenFastTrace design](https://github.com/itsallcode/openfasttrace/blob/main/doc/spec/design.md) | Scoped metrics and direct/transitive impact | Shallow/deep coverage, cycle/orphan/ambiguity analysis and path witnesses |
+| Source-code traceability | [StrictDoc user guide](https://strictdoc.readthedocs.io/en/stable/stable/docs/strictdoc_01_user_guide.html), [OpenFastTrace](https://github.com/itsallcode/openfasttrace) | Planned QMD, comment and Python scanners | Stable scanner protocol, IDE navigation and language adapters after M4B |
+| Interchange and federation | [ReqIF 1.2](https://www.omg.org/spec/ReqIF/1.2/), [OSLC RM 2.1](https://docs.oasis-open-projects.org/oslc-op/rm/v2.1/requirements-management-spec.html) | Deterministic JSON/CSV/SARIF/JUnit/Markdown | ReqIF export/import, then OSLC/JSON-LD federation with provenance |
+| Authoring and round trip | [StrictDoc](https://github.com/strictdoc-project/strictdoc) | Source-controlled Quarto authoring | Optional structured editor only after lossless write-back and conflict semantics exist |
+
+## What Quarto-Needs should surpass
+
+### One analysis model, many trustworthy projections
+
+All renderers, exporters, graphs, quality gates, diffs, and impact reports must
+consume the same canonical analysis result. A visual view cannot silently apply
+different filtering, relation orientation, or coverage rules from the CLI.
+
+### Explainable change intelligence
+
+The baseline engine is a product differentiator, not merely a regression tool.
+The interactive graph should render added, removed, modified, and relocated
+objects and relations directly, retain removed objects as clearly marked ghosts,
+and explain every impacted node with the exact path and policy that selected it.
+There is no opaque risk score unless its complete formula and inputs are exposed.
+
+### Secure progressive enhancement
+
+Interactive HTML uses a reduced public projection and locally vendored assets.
+Static diagrams and accessible data tables preserve the essential information in
+HTML without JavaScript, PDF, DOCX, EPUB, and other Quarto/Pandoc outputs. The
+browser never receives bodies, paths, source locations, or undeclared attributes
+unless the author explicitly publishes them.
+
+### Determinism as a contract
+
+Canonical order, pinned semantic inputs, stable schemas, atomic writes, and
+byte-identical artifacts are release gates. Layouts with multiple valid graph
+solutions use a stored seed and deterministic tie-breaking. Remote imports are
+resolved through a lock file containing origin, version, content digest, and
+retrieval policy.
+
+### Requirements as linked data
+
+The internal model should gradually align with ReqIF concepts and expose a
+versioned JSON-LD projection without forcing either format on authors. OSLC
+federation follows only after identity, access, cache, provenance, and conflict
+semantics are explicit.
+
+## Product sequence
+
+| Order | Milestone | Outcome |
+|---:|---|---|
+| 1 | 4B — Source adapters | QMD, comment and Python facts enter one provenance-preserving scanner contract |
+| 2 | 5A — Interactive graph | Offline, accessible graph with linked inspector, filters, path explanations and baseline overlays |
+| 3 | 5B — ReqIF export | Standards-valid exchange artifact with semantic conformance fixtures |
+| 4 | 5C — Hardening | Security, accessibility, performance budgets and large-catalog benchmarks |
+| 5 | 6A — Typed model | Type schemas, inheritance, relation cardinality and network constraints |
+| 6 | 6B — Review intelligence | Suspect links, review fingerprints, approvals and optional signed baseline attestations |
+| 7 | 6C — View parity | List/table/matrix/sequence/Gantt/architecture/chart views over the canonical query engine |
+| 8 | 7A — Federation | Locked imports, adapter SDK, service cache, provenance, ReqIF import and OSLC/JSON-LD |
+| 9 | 7B — Developer experience | LSP, navigation, completion and additional scanners after contracts stabilize |
+
+Milestone 4B remains first because the graph must show traceability from authored
+requirements into code and tests, not just duplicate existing document links.
+Milestone 5A is the next user-visible product leap and has its own implementation
+plan. Milestones 6 and 7 are intentionally split so mature Sphinx-Needs features
+can be adopted without turning one release into an unreviewable rewrite.
+
+## Architectural guardrails
+
+- Capability additions extend the canonical object/relation/finding model before
+  they add renderer-specific behavior.
+- Queries, schemas, derived values, and variants use bounded declarative
+  languages. They do not evaluate arbitrary Python, JavaScript, or Lua.
+- External adapters are read-only by default, declare network requirements, use
+  explicit allowlists, and preserve original identity plus provenance.
+- A view declares which projection fields it needs. Projection construction
+  fails closed when a requested field is not publishable.
+- Graph limits produce a visible narrowing prompt; they never silently truncate.
+- New schemas and artifact formats are versioned and receive golden, malformed,
+  determinism, and migration tests.
+- Interactive behavior is supplemental. Keyboard operation and an equivalent
+  non-JavaScript representation are acceptance criteria, not later polish.
+- Performance work is measured on synthetic sparse, dense, cyclic, and high-fanout
+  graphs; no benchmark may depend only on the Aegis example.
+
+## Success measures
+
+- A user can answer “what changed, what is affected, and why?” from either CLI
+  artifacts or the rendered book without conflicting results.
+- The Aegis showcase exercises every supported exporter, scanner, graph mode,
+  policy gate, and interchange format in CI.
+- Public graph assets contain no denied field in adversarial fixtures.
+- The static and interactive views identify the same object and relation sets.
+- Every release reports compatibility, determinism, accessibility, security, and
+  synthetic-graph performance results.
+
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/examples/book/.gitignore .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/examples/book/.gitignore
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/examples/book/.gitignore	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/examples/book/.gitignore	2026-08-26 21:47:22.531955283 -0300
@@ -0,0 +1,2 @@
+/.quarto/
+**/*.quarto_ipynb
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/Makefile .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/Makefile
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/Makefile	2026-08-26 14:14:07.574423864 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/Makefile	2026-08-26 21:43:54.152982277 -0300
@@ -1,14 +1,15 @@
 .PHONY: setup test scan check coverage example preview-example sync-example check-example render-example render-example-all baseline-example diff-example impact-example
 .DEFAULT_GOAL := test
 
 VENV_PYTHON := .venv/bin/python
+AEGIS_REFERENCE_EPOCH = $(shell $(VENV_PYTHON) -c 'import json; from datetime import datetime, timezone; value=json.load(open("examples/book/baselines/quarto-needs.json", encoding="utf-8"))["referenceDate"]; print(int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()))')
 
 .venv/bin/python:
 	python3 -m venv .venv
 
 setup: .venv/bin/python
 	$(VENV_PYTHON) -m pip install -e ".[test]"
 
 test:
 	$(VENV_PYTHON) -m pytest -q
 
@@ -37,14 +38,14 @@
 
 render-example-all:
 	quarto render examples/book --to html
 	quarto render examples/book --to docx
 	quarto render examples/book --to pdf
 
 baseline-example:
 	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book baseline create --force
 
 diff-example:
-	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book diff examples/book/baselines/quarto-needs.json
+	SOURCE_DATE_EPOCH=$(AEGIS_REFERENCE_EPOCH) PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book diff examples/book/baselines/quarto-needs.json
 
 impact-example:
-	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json --recompute-with current
+	SOURCE_DATE_EPOCH=$(AEGIS_REFERENCE_EPOCH) PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/pyproject.toml .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/pyproject.toml
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/pyproject.toml	2026-08-25 16:57:23.887281125 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/pyproject.toml	2026-08-26 21:43:54.164982226 -0300
@@ -18,18 +18,19 @@
 ]
 
 [project.scripts]
 quarto-needs = "quarto_needs.cli:main"
 
 [project.optional-dependencies]
 test = [
   "pytest>=8",
   "jsonschema>=4.23",
   "referencing",
+  "PyYAML>=6",
 ]
 
 [tool.setuptools.packages.find]
 where = ["src"]
 
 [tool.pytest.ini_options]
 testpaths = ["tests"]
 pythonpath = ["src"]
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/README.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/README.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/README.md	2026-08-26 15:14:32.686146959 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/README.md	2026-08-26 21:43:54.156982260 -0300
@@ -370,24 +370,28 @@
 report and every date-sensitive finding carries the reference date it used.
 
 ### Profiles and exit codes
 
 | Profile | Structural failure | Semantic gate failure |
 |---|---|---|
 | `advisory` | 1 | 0 |
 | `default` | 1 | 0 (reported, not enforced) |
 | `strict` | 1 | 1 |
 
-A broken configuration exits 2 from every command.
+Command exit codes are stable across profiles:
 
-- `3`: operational failure — an artifact could not be read or written. The
-  message names the artifact; anything already written is left in place.
+- `0`: the command completed and every enforced policy gate passed;
+- `1`: the project is structurally invalid or an enforced policy gate failed;
+- `2`: invalid usage, configuration, or comparison artifact;
+- `3`: operational failure — an artifact could not be read, written, or
+  serialized. The message names the artifact; anything already written is
+  left in place.
 
 ### Baseline, diff, and impact
 
 `baseline create` snapshots the current graph — objects, authored relations,
 findings, and the projected report — into `baselines/quarto-needs.json`. It
 refuses to overwrite an existing baseline unless `--force` is given, and it
 refuses to write anything for a structurally invalid project unless
 `--allow-invalid` is given. That flag produces a diagnostic artifact marked
 `valid: false`; only `baseline inspect` accepts it. `diff` and `impact`
 reject it outright, because duplicate IDs make it ambiguous which object a
@@ -455,20 +459,41 @@
 quarto-needs query approved-high-unverified          # ordered IDs for a named query
 quarto-needs baseline create                         # snapshot the graph to baselines/quarto-needs.json
 quarto-needs diff baselines/quarto-needs.json         # classify what changed since that snapshot
 quarto-needs impact baselines/quarto-needs.json       # trace what those changes reach
 ```
 
 `quality` writes its `--output` artifact atomically and keeps it even when a
 gate fails, so CI can publish the report that explains the failure. `--root`
 selects the project directory for every command.
 
+## Export formats
+
+`quarto-needs export --format` provides five deterministic CI and interchange
+projections from a single analysis pass:
+
+| Format | Output |
+|---|---|
+| `json` | Canonical v1 graph document; also the default when `--format` is omitted. |
+| `csv` | A directory containing `objects.csv`, `relations.csv`, and `findings.csv`, with spreadsheet-formula neutralization. |
+| `sarif` | SARIF 2.1.0 findings for GitHub code scanning and compatible consumers. |
+| `junit` | One JUnit test case per evaluated quality gate. |
+| `markdown` | A GitHub step summary with changes, coverage deltas, failed gates, impact paths, and finding counts. |
+
+Markdown accepts `--baseline <path>` to classify changes and calculate impact;
+other formats reject that option as invalid usage. For a fixed project,
+configuration, and `SOURCE_DATE_EPOCH`, repeated exports are byte-identical.
+Artifacts are written before the profile verdict is returned, so a strict gate
+failure exits `1` while preserving the report that explains it. I/O or
+serialization failure exits `3` and names the artifact that could not be
+produced.
+
 ## Current validation rules
 
 The rule engine grew from four embedded checks into the configurable catalog
 documented above. Structural, referential, and process validation now share one
 rule protocol, and every rule reports a located, coded finding.
 
 ## Canonical graph
 
 `.quarto-needs/needs.json` contains:
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/baseline-v1.schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/schemas/baseline-v1.schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/baseline-v1.schema.json	2026-08-26 01:09:31.868644198 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/schemas/baseline-v1.schema.json	2026-08-26 17:30:49.638688670 -0300
@@ -46,29 +46,29 @@
           },
           "contentFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
         }
       }
     },
     "relations": {
       "type": "array",
       "items": {
         "type": "object",
         "additionalProperties": false,
-        "required": ["source", "authoredName", "target", "semanticFamily", "sourceRole", "targetRole", "attributes", "authoredFingerprint", "semanticFingerprint"],
+        "required": ["source", "authoredName", "target", "semanticFamily", "sourceRole", "targetRole", "impactDirection", "attributes", "authoredFingerprint", "semanticFingerprint"],
         "properties": {
           "source": {"type": "string"},
           "authoredName": {"type": "string"},
           "target": {"type": "string"},
           "semanticFamily": {"type": "string"},
           "sourceRole": {"type": "string"},
           "targetRole": {"type": "string"},
-          "impactDirection": {"type": "string"},
+          "impactDirection": {"enum": ["source_to_target", "target_to_source", "both", "none"]},
           "attributes": {"type": "object"},
           "authoredFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
           "semanticFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
         }
       }
     },
     "findings": {"type": "array", "items": {"type": "object"}},
     "declarations": {"type": "array", "items": {"type": "object"}},
     "report": {"type": "object"}
   }
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/diff-v1.schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/schemas/diff-v1.schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/diff-v1.schema.json	2026-08-26 10:00:03.963170253 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/schemas/diff-v1.schema.json	2026-08-26 17:32:19.038471200 -0300
@@ -1,68 +1,163 @@
 {
   "$schema": "https://json-schema.org/draft/2020-12/schema",
   "$id": "https://quarto-needs.dev/schema/diff-v1.schema.json",
   "title": "Quarto-Needs diff v1",
   "type": "object",
   "additionalProperties": false,
-  "required": ["schemaVersion", "referenceDate", "recomputed", "notices", "objects", "relations", "findings", "metrics", "gates", "empty"],
+  "required": ["schemaVersion", "referenceDate", "recomputed", "notices", "suppressed", "objects", "relations", "findings", "metrics", "gates", "empty"],
+  "$defs": {
+    "location": {
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "file": {"type": "string"},
+        "line": {"type": "integer"},
+        "anchor": {"type": ["string", "null"]}
+      }
+    },
+    "relationEntry": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["source", "authoredName", "target", "semanticFamily"],
+      "properties": {
+        "source": {"type": "string"},
+        "authoredName": {"type": "string"},
+        "target": {"type": "string"},
+        "semanticFamily": {"type": "string"}
+      }
+    },
+    "findingEntry": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["code", "object_id", "message", "severity"],
+      "properties": {
+        "code": {"type": "string"},
+        "object_id": {"type": ["string", "null"]},
+        "message": {"type": "string"},
+        "severity": {"type": ["string", "null"]}
+      }
+    }
+  },
   "properties": {
     "schemaVersion": {"const": "1"},
     "referenceDate": {
       "type": "object",
       "additionalProperties": false,
       "required": ["baseline", "current"],
       "properties": {"baseline": {"type": "string"}, "current": {"type": "string"}}
     },
     "recomputed": {"type": "boolean"},
     "notices": {
       "type": "array",
       "items": {"enum": ["configuration-changed", "reference-date-changed"]}
     },
+    "suppressed": {
+      "type": "array",
+      "items": {"enum": ["findings", "metrics", "gates"]},
+      "uniqueItems": true
+    },
     "objects": {
       "type": "object",
       "additionalProperties": false,
       "required": ["added", "removed", "modified", "relocated"],
       "properties": {
         "added": {"type": "array", "items": {"type": "string"}},
         "removed": {"type": "array", "items": {"type": "string"}},
         "modified": {
           "type": "array",
           "items": {
             "type": "object",
             "additionalProperties": false,
             "required": ["id", "fields"],
             "properties": {"id": {"type": "string"}, "fields": {"type": "array", "items": {"type": "string"}}}
           }
         },
-        "relocated": {"type": "array", "items": {"type": "object"}}
+        "relocated": {
+          "type": "array",
+          "items": {
+            "type": "object",
+            "additionalProperties": false,
+            "required": ["id", "from", "to"],
+            "comment": "An object declared without a location yields {} on that side.",
+            "properties": {
+              "id": {"type": "string"},
+              "from": {"$ref": "#/$defs/location"},
+              "to": {"$ref": "#/$defs/location"}
+            }
+          }
+        }
       }
     },
     "relations": {
       "type": "object",
       "additionalProperties": false,
       "required": ["added", "removed", "representationChanged"],
       "properties": {
-        "added": {"type": "array", "items": {"type": "object"}},
-        "removed": {"type": "array", "items": {"type": "object"}},
-        "representationChanged": {"type": "array", "items": {"type": "object"}}
+        "added": {"type": "array", "items": {"$ref": "#/$defs/relationEntry"}},
+        "removed": {"type": "array", "items": {"$ref": "#/$defs/relationEntry"}},
+        "representationChanged": {
+          "type": "array",
+          "items": {
+            "allOf": [{"$ref": "#/$defs/relationEntry"}],
+            "type": "object",
+            "additionalProperties": false,
+            "required": ["source", "authoredName", "target", "semanticFamily", "from", "to"],
+            "properties": {
+              "source": {"type": "string"},
+              "authoredName": {"type": "string"},
+              "target": {"type": "string"},
+              "semanticFamily": {"type": "string"},
+              "from": {"type": "string"},
+              "to": {"type": "string"}
+            }
+          }
+        }
       }
     },
     "findings": {
       "type": "object",
       "additionalProperties": false,
       "required": ["added", "removed"],
       "properties": {
-        "added": {"type": "array", "items": {"type": "object"}},
-        "removed": {"type": "array", "items": {"type": "object"}}
+        "added": {"type": "array", "items": {"$ref": "#/$defs/findingEntry"}},
+        "removed": {"type": "array", "items": {"$ref": "#/$defs/findingEntry"}}
+      }
+    },
+    "metrics": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["scope", "strength", "before", "after"],
+        "properties": {
+          "scope": {"type": "string"},
+          "strength": {"type": "string"},
+          "before": {"type": ["number", "null"]},
+          "after": {"type": ["number", "null"]}
+        }
       }
     },
-    "metrics": {"type": "array", "items": {"type": "object"}},
     "gates": {
       "type": "object",
       "additionalProperties": false,
       "required": ["regressed"],
-      "properties": {"regressed": {"type": "array", "items": {"type": "object"}}}
+      "properties": {
+        "regressed": {
+          "type": "array",
+          "items": {
+            "type": "object",
+            "additionalProperties": false,
+            "required": ["name", "scope", "threshold", "actual"],
+            "properties": {
+              "name": {"type": "string"},
+              "scope": {"type": "string"},
+              "threshold": {"type": ["number", "string", "null"]},
+              "actual": {"type": ["number", "string", "null"]}
+            }
+          }
+        }
+      }
     },
     "empty": {"type": "boolean"}
   }
 }
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/vendor/sarif-2.1.0/sarif-schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/schemas/vendor/sarif-2.1.0/sarif-schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/vendor/sarif-2.1.0/sarif-schema.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/schemas/vendor/sarif-2.1.0/sarif-schema.json	2026-08-26 17:23:56.831984356 -0300
@@ -0,0 +1,2882 @@
+{
+  "$schema": "http://json-schema.org/draft-07/schema#",
+  "$id": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
+  "additionalProperties": false,
+  "definitions": {
+    "address": {
+      "description": "A physical or virtual address, or a range of addresses, in an 'addressable region' (memory or a binary file).",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "absoluteAddress": {
+          "description": "The address expressed as a byte offset from the start of the addressable region.",
+          "type": "integer",
+          "minimum": -1,
+          "default": -1
+        },
+        "relativeAddress": {
+          "description": "The address expressed as a byte offset from the absolute address of the top-most parent object.",
+          "type": "integer"
+        },
+        "length": {
+          "description": "The number of bytes in this range of addresses.",
+          "type": "integer"
+        },
+        "kind": {
+          "description": "An open-ended string that identifies the address kind. 'data', 'function', 'header','instruction', 'module', 'page', 'section', 'segment', 'stack', 'stackFrame', 'table' are well-known values.",
+          "type": "string"
+        },
+        "name": {
+          "description": "A name that is associated with the address, e.g., '.text'.",
+          "type": "string"
+        },
+        "fullyQualifiedName": {
+          "description": "A human-readable fully qualified name that is associated with the address.",
+          "type": "string"
+        },
+        "offsetFromParent": {
+          "description": "The byte offset of this address from the absolute or relative address of the parent object.",
+          "type": "integer"
+        },
+        "index": {
+          "description": "The index within run.addresses of the cached object for this address.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "parentIndex": {
+          "description": "The index within run.addresses of the parent object.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the address."
+        }
+      }
+    },
+    "artifact": {
+      "description": "A single artifact. In some cases, this artifact might be nested within another artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A short description of the artifact."
+        },
+        "location": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the artifact."
+        },
+        "parentIndex": {
+          "description": "Identifies the index of the immediate parent of the artifact, if this artifact is nested.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "offset": {
+          "description": "The offset in bytes of the artifact within its containing artifact.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "length": {
+          "description": "The length of the artifact in bytes.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "roles": {
+          "description": "The role or roles played by the artifact in the analysis.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "enum": [
+              "analysisTarget",
+              "attachment",
+              "responseFile",
+              "resultFile",
+              "standardStream",
+              "tracedFile",
+              "unmodified",
+              "modified",
+              "added",
+              "deleted",
+              "renamed",
+              "uncontrolled",
+              "driver",
+              "extension",
+              "translation",
+              "taxonomy",
+              "policy",
+              "referencedOnCommandLine",
+              "memoryContents",
+              "directory",
+              "userSpecifiedConfiguration",
+              "toolSpecifiedConfiguration",
+              "debugOutputFile"
+            ]
+          }
+        },
+        "mimeType": {
+          "description": "The MIME type (RFC 2045) of the artifact.",
+          "type": "string",
+          "pattern": "[^/]+/.+"
+        },
+        "contents": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The contents of the artifact."
+        },
+        "encoding": {
+          "description": "Specifies the encoding for an artifact object that refers to a text file.",
+          "type": "string"
+        },
+        "sourceLanguage": {
+          "description": "Specifies the source language for any artifact object that refers to a text file that contains source code.",
+          "type": "string"
+        },
+        "hashes": {
+          "description": "A dictionary, each of whose keys is the name of a hash function and each of whose values is the hashed value of the artifact produced by the specified hash function.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "lastModifiedTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the artifact was most recently modified. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the artifact."
+        }
+      }
+    },
+    "artifactChange": {
+      "description": "A change to a single artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "artifactLocation": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the artifact to change."
+        },
+        "replacements": {
+          "description": "An array of replacement objects, each of which represents the replacement of a single region in a single artifact specified by 'artifactLocation'.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/replacement"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the change."
+        }
+      },
+      "required": ["artifactLocation", "replacements"]
+    },
+    "artifactContent": {
+      "description": "Represents the contents of an artifact.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "text": {
+          "description": "UTF-8-encoded content from a text artifact.",
+          "type": "string"
+        },
+        "binary": {
+          "description": "MIME Base64-encoded content from a binary artifact, or from a text artifact in its original encoding.",
+          "type": "string"
+        },
+        "rendered": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "An alternate rendered representation of the artifact (e.g., a decompiled representation of a binary region)."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the artifact content."
+        }
+      }
+    },
+    "artifactLocation": {
+      "description": "Specifies the location of an artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "uri": {
+          "description": "A string containing a valid relative or absolute URI.",
+          "type": "string",
+          "format": "uri-reference"
+        },
+        "uriBaseId": {
+          "description": "A string which indirectly specifies the absolute URI with respect to which a relative URI in the \"uri\" property is interpreted.",
+          "type": "string"
+        },
+        "index": {
+          "description": "The index within the run artifacts array of the artifact object associated with the artifact location.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A short description of the artifact location."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the artifact location."
+        }
+      }
+    },
+    "attachment": {
+      "description": "An artifact relevant to a result.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A message describing the role played by the attachment."
+        },
+        "artifactLocation": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the attachment."
+        },
+        "regions": {
+          "description": "An array of regions of interest within the attachment.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/region"
+          }
+        },
+        "rectangles": {
+          "description": "An array of rectangles specifying areas of interest within the image.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/rectangle"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the attachment."
+        }
+      },
+      "required": ["artifactLocation"]
+    },
+    "codeFlow": {
+      "description": "A set of threadFlows which together describe a pattern of code execution relevant to detecting a result.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the code flow."
+        },
+        "threadFlows": {
+          "description": "An array of one or more unique threadFlow objects, each of which describes the progress of a program through a thread of execution.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/threadFlow"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the code flow."
+        }
+      },
+      "required": ["threadFlows"]
+    },
+    "configurationOverride": {
+      "description": "Information about how a specific rule or notification was reconfigured at runtime.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "configuration": {
+          "$ref": "#/definitions/reportingConfiguration",
+          "description": "Specifies how the rule or notification was configured during the scan."
+        },
+        "descriptor": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference used to locate the descriptor whose configuration was overridden."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the configuration override."
+        }
+      },
+      "required": ["configuration", "descriptor"]
+    },
+    "conversion": {
+      "description": "Describes how a converter transformed the output of a static analysis tool from the analysis tool's native output format into the SARIF format.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "tool": {
+          "$ref": "#/definitions/tool",
+          "description": "A tool object that describes the converter."
+        },
+        "invocation": {
+          "$ref": "#/definitions/invocation",
+          "description": "An invocation object that describes the invocation of the converter."
+        },
+        "analysisToolLogFiles": {
+          "description": "The locations of the analysis tool's per-run log files.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/artifactLocation"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the conversion."
+        }
+      },
+      "required": ["tool"]
+    },
+    "edge": {
+      "description": "Represents a directed edge in a graph.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "id": {
+          "description": "A string that uniquely identifies the edge within its graph.",
+          "type": "string"
+        },
+        "label": {
+          "$ref": "#/definitions/message",
+          "description": "A short description of the edge."
+        },
+        "sourceNodeId": {
+          "description": "Identifies the source node (the node at which the edge starts).",
+          "type": "string"
+        },
+        "targetNodeId": {
+          "description": "Identifies the target node (the node at which the edge ends).",
+          "type": "string"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the edge."
+        }
+      },
+      "required": ["id", "sourceNodeId", "targetNodeId"]
+    },
+    "edgeTraversal": {
+      "description": "Represents the traversal of a single edge during a graph traversal.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "edgeId": {
+          "description": "Identifies the edge being traversed.",
+          "type": "string"
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message to display to the user as the edge is traversed."
+        },
+        "finalState": {
+          "description": "The values of relevant expressions after the edge has been traversed.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "stepOverEdgeCount": {
+          "description": "The number of edge traversals necessary to return from a nested graph.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the edge traversal."
+        }
+      },
+      "required": ["edgeId"]
+    },
+    "exception": {
+      "description": "Describes a runtime exception encountered during the execution of an analysis tool.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "kind": {
+          "type": "string",
+          "description": "A string that identifies the kind of exception, for example, the fully qualified type name of an object that was thrown, or the symbolic name of a signal."
+        },
+        "message": {
+          "description": "A message that describes the exception.",
+          "type": "string"
+        },
+        "stack": {
+          "$ref": "#/definitions/stack",
+          "description": "The sequence of function calls leading to the exception."
+        },
+        "innerExceptions": {
+          "description": "An array of exception objects each of which is considered a cause of this exception.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/exception"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the exception."
+        }
+      }
+    },
+    "externalProperties": {
+      "description": "The top-level element of an external property file.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "schema": {
+          "description": "The URI of the JSON schema corresponding to the version of the external property file format.",
+          "type": "string",
+          "format": "uri"
+        },
+        "version": {
+          "description": "The SARIF format version of this external properties object.",
+          "enum": ["2.1.0"]
+        },
+        "guid": {
+          "description": "A stable, unique identifier for this external properties object, in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "runGuid": {
+          "description": "A stable, unique identifier for the run associated with this external properties object, in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "conversion": {
+          "$ref": "#/definitions/conversion",
+          "description": "A conversion object that will be merged with a separate run."
+        },
+        "graphs": {
+          "description": "An array of graph objects that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "default": [],
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/graph"
+          }
+        },
+        "externalizedProperties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information that will be merged with a separate run."
+        },
+        "artifacts": {
+          "description": "An array of artifact objects that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/artifact"
+          }
+        },
+        "invocations": {
+          "description": "Describes the invocation of the analysis tool that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/invocation"
+          }
+        },
+        "logicalLocations": {
+          "description": "An array of logical locations such as namespaces, types or functions that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/logicalLocation"
+          }
+        },
+        "threadFlowLocations": {
+          "description": "An array of threadFlowLocation objects that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/threadFlowLocation"
+          }
+        },
+        "results": {
+          "description": "An array of result objects that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/result"
+          }
+        },
+        "taxonomies": {
+          "description": "Tool taxonomies that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "driver": {
+          "$ref": "#/definitions/toolComponent",
+          "description": "The analysis tool object that will be merged with a separate run."
+        },
+        "extensions": {
+          "description": "Tool extensions that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "policies": {
+          "description": "Tool policies that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "translations": {
+          "description": "Tool translations that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "addresses": {
+          "description": "Addresses that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/address"
+          }
+        },
+        "webRequests": {
+          "description": "Requests that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/webRequest"
+          }
+        },
+        "webResponses": {
+          "description": "Responses that will be merged with a separate run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/webResponse"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the external properties."
+        }
+      }
+    },
+    "externalPropertyFileReference": {
+      "description": "Contains information that enables a SARIF consumer to locate the external property file that contains the value of an externalized property associated with the run.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "location": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the external property file."
+        },
+        "guid": {
+          "description": "A stable, unique identifier for the external property file in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "itemCount": {
+          "description": "A non-negative integer specifying the number of items contained in the external property file.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the external property file."
+        }
+      },
+      "anyOf": [
+        {
+          "required": ["location"]
+        },
+        {
+          "required": ["guid"]
+        }
+      ]
+    },
+    "externalPropertyFileReferences": {
+      "description": "References to external property files that should be inlined with the content of a root log file.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "conversion": {
+          "$ref": "#/definitions/externalPropertyFileReference",
+          "description": "An external property file containing a run.conversion object to be merged with the root log file."
+        },
+        "graphs": {
+          "description": "An array of external property files containing a run.graphs object to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "externalizedProperties": {
+          "$ref": "#/definitions/externalPropertyFileReference",
+          "description": "An external property file containing a run.properties object to be merged with the root log file."
+        },
+        "artifacts": {
+          "description": "An array of external property files containing run.artifacts arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "invocations": {
+          "description": "An array of external property files containing run.invocations arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "logicalLocations": {
+          "description": "An array of external property files containing run.logicalLocations arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "threadFlowLocations": {
+          "description": "An array of external property files containing run.threadFlowLocations arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "results": {
+          "description": "An array of external property files containing run.results arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "taxonomies": {
+          "description": "An array of external property files containing run.taxonomies arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "addresses": {
+          "description": "An array of external property files containing run.addresses arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "driver": {
+          "$ref": "#/definitions/externalPropertyFileReference",
+          "description": "An external property file containing a run.driver object to be merged with the root log file."
+        },
+        "extensions": {
+          "description": "An array of external property files containing run.extensions arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "policies": {
+          "description": "An array of external property files containing run.policies arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "translations": {
+          "description": "An array of external property files containing run.translations arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "webRequests": {
+          "description": "An array of external property files containing run.requests arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "webResponses": {
+          "description": "An array of external property files containing run.responses arrays to be merged with the root log file.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/externalPropertyFileReference"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the external property files."
+        }
+      }
+    },
+    "fix": {
+      "description": "A proposed fix for the problem represented by a result object. A fix specifies a set of artifacts to modify. For each artifact, it specifies a set of bytes to remove, and provides a set of new bytes to replace them.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A message that describes the proposed fix, enabling viewers to present the proposed change to an end user."
+        },
+        "artifactChanges": {
+          "description": "One or more artifact changes that comprise a fix for a result.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/artifactChange"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the fix."
+        }
+      },
+      "required": ["artifactChanges"]
+    },
+    "graph": {
+      "description": "A network of nodes and directed edges that describes some aspect of the structure of the code (for example, a call graph).",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of the graph."
+        },
+        "nodes": {
+          "description": "An array of node objects representing the nodes of the graph.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/node"
+          }
+        },
+        "edges": {
+          "description": "An array of edge objects representing the edges of the graph.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/edge"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the graph."
+        }
+      }
+    },
+    "graphTraversal": {
+      "description": "Represents a path through a graph.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "runGraphIndex": {
+          "description": "The index within the run.graphs to be associated with the result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "resultGraphIndex": {
+          "description": "The index within the result.graphs to be associated with the result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of this graph traversal."
+        },
+        "initialState": {
+          "description": "Values of relevant expressions at the start of the graph traversal that may change during graph traversal.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "immutableState": {
+          "description": "Values of relevant expressions at the start of the graph traversal that remain constant for the graph traversal.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "edgeTraversals": {
+          "description": "The sequences of edges traversed by this graph traversal.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/edgeTraversal"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the graph traversal."
+        }
+      },
+      "oneOf": [
+        {
+          "required": ["runGraphIndex"]
+        },
+        {
+          "required": ["resultGraphIndex"]
+        }
+      ]
+    },
+    "invocation": {
+      "description": "The runtime environment of the analysis tool run.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "commandLine": {
+          "description": "The command line used to invoke the tool.",
+          "type": "string"
+        },
+        "arguments": {
+          "description": "An array of strings, containing in order the command line arguments passed to the tool from the operating system.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "items": {
+            "type": "string"
+          }
+        },
+        "responseFiles": {
+          "description": "The locations of any response files specified on the tool's command line.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/artifactLocation"
+          }
+        },
+        "startTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the invocation started. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "endTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the invocation ended. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "exitCode": {
+          "description": "The process exit code.",
+          "type": "integer"
+        },
+        "ruleConfigurationOverrides": {
+          "description": "An array of configurationOverride objects that describe rules related runtime overrides.",
+          "type": "array",
+          "minItems": 0,
+          "default": [],
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/configurationOverride"
+          }
+        },
+        "notificationConfigurationOverrides": {
+          "description": "An array of configurationOverride objects that describe notifications related runtime overrides.",
+          "type": "array",
+          "minItems": 0,
+          "default": [],
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/configurationOverride"
+          }
+        },
+        "toolExecutionNotifications": {
+          "description": "A list of runtime conditions detected by the tool during the analysis.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/notification"
+          }
+        },
+        "toolConfigurationNotifications": {
+          "description": "A list of conditions detected by the tool that are relevant to the tool's configuration.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/notification"
+          }
+        },
+        "exitCodeDescription": {
+          "description": "The reason for the process exit.",
+          "type": "string"
+        },
+        "exitSignalName": {
+          "description": "The name of the signal that caused the process to exit.",
+          "type": "string"
+        },
+        "exitSignalNumber": {
+          "description": "The numeric value of the signal that caused the process to exit.",
+          "type": "integer"
+        },
+        "processStartFailureMessage": {
+          "description": "The reason given by the operating system that the process failed to start.",
+          "type": "string"
+        },
+        "executionSuccessful": {
+          "description": "Specifies whether the tool's execution completed successfully.",
+          "type": "boolean"
+        },
+        "machine": {
+          "description": "The machine on which the invocation occurred.",
+          "type": "string"
+        },
+        "account": {
+          "description": "The account under which the invocation occurred.",
+          "type": "string"
+        },
+        "processId": {
+          "description": "The id of the process in which the invocation occurred.",
+          "type": "integer"
+        },
+        "executableLocation": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "An absolute URI specifying the location of the executable that was invoked."
+        },
+        "workingDirectory": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The working directory for the invocation."
+        },
+        "environmentVariables": {
+          "description": "The environment variables associated with the analysis tool process, expressed as key/value pairs.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "stdin": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "A file containing the standard input stream to the process that was invoked."
+        },
+        "stdout": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "A file containing the standard output stream from the process that was invoked."
+        },
+        "stderr": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "A file containing the standard error stream from the process that was invoked."
+        },
+        "stdoutStderr": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "A file containing the interleaved standard output and standard error stream from the process that was invoked."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the invocation."
+        }
+      },
+      "required": ["executionSuccessful"]
+    },
+    "location": {
+      "description": "A location within a programming artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "id": {
+          "description": "Value that distinguishes this location from all other locations within a single result object.",
+          "type": "integer",
+          "minimum": -1,
+          "default": -1
+        },
+        "physicalLocation": {
+          "$ref": "#/definitions/physicalLocation",
+          "description": "Identifies the artifact and region."
+        },
+        "logicalLocations": {
+          "description": "The logical locations associated with the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/logicalLocation"
+          }
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the location."
+        },
+        "annotations": {
+          "description": "A set of regions relevant to the location.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/region"
+          }
+        },
+        "relationships": {
+          "description": "An array of objects that describe relationships between this location and others.",
+          "type": "array",
+          "default": [],
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/locationRelationship"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the location."
+        }
+      }
+    },
+    "locationRelationship": {
+      "description": "Information about the relation of one location to another.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "target": {
+          "description": "A reference to the related location.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "kinds": {
+          "description": "A set of distinct strings that categorize the relationship. Well-known kinds include 'includes', 'isIncludedBy' and 'relevant'.",
+          "type": "array",
+          "default": ["relevant"],
+          "uniqueItems": true,
+          "items": {
+            "type": "string"
+          }
+        },
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of the location relationship."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the location relationship."
+        }
+      },
+      "required": ["target"]
+    },
+    "logicalLocation": {
+      "description": "A logical location of a construct that produced a result.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "name": {
+          "description": "Identifies the construct in which the result occurred. For example, this property might contain the name of a class or a method.",
+          "type": "string"
+        },
+        "index": {
+          "description": "The index within the logical locations array.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "fullyQualifiedName": {
+          "description": "The human-readable fully qualified name of the logical location.",
+          "type": "string"
+        },
+        "decoratedName": {
+          "description": "The machine-readable name for the logical location, such as a mangled function name provided by a C++ compiler that encodes calling convention, return type and other details along with the function name.",
+          "type": "string"
+        },
+        "parentIndex": {
+          "description": "Identifies the index of the immediate parent of the construct in which the result was detected. For example, this property might point to a logical location that represents the namespace that holds a type.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "kind": {
+          "description": "The type of construct this logical location component refers to. Should be one of 'function', 'member', 'module', 'namespace', 'parameter', 'resource', 'returnType', 'type', 'variable', 'object', 'array', 'property', 'value', 'element', 'text', 'attribute', 'comment', 'declaration', 'dtd' or 'processingInstruction', if any of those accurately describe the construct.",
+          "type": "string"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the logical location."
+        }
+      }
+    },
+    "message": {
+      "description": "Encapsulates a message intended to be read by the end user.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "text": {
+          "description": "A plain text message string.",
+          "type": "string"
+        },
+        "markdown": {
+          "description": "A Markdown message string.",
+          "type": "string"
+        },
+        "id": {
+          "description": "The identifier for this message.",
+          "type": "string"
+        },
+        "arguments": {
+          "description": "An array of strings to substitute into the message string.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "type": "string"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the message."
+        }
+      },
+      "anyOf": [
+        {
+          "required": ["text"]
+        },
+        {
+          "required": ["id"]
+        }
+      ]
+    },
+    "multiformatMessageString": {
+      "description": "A message string or message format string rendered in multiple formats.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "text": {
+          "description": "A plain text message string or format string.",
+          "type": "string"
+        },
+        "markdown": {
+          "description": "A Markdown message string or format string.",
+          "type": "string"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the message."
+        }
+      },
+      "required": ["text"]
+    },
+    "node": {
+      "description": "Represents a node in a graph.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "id": {
+          "description": "A string that uniquely identifies the node within its graph.",
+          "type": "string"
+        },
+        "label": {
+          "$ref": "#/definitions/message",
+          "description": "A short description of the node."
+        },
+        "location": {
+          "$ref": "#/definitions/location",
+          "description": "A code location associated with the node."
+        },
+        "children": {
+          "description": "Array of child nodes.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/node"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the node."
+        }
+      },
+      "required": ["id"]
+    },
+    "notification": {
+      "description": "Describes a condition relevant to the tool itself, as opposed to being relevant to a target being analyzed by the tool.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "locations": {
+          "description": "The locations relevant to this notification.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/location"
+          }
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message that describes the condition that was encountered."
+        },
+        "level": {
+          "description": "A value specifying the severity level of the notification.",
+          "default": "warning",
+          "enum": ["none", "note", "warning", "error"]
+        },
+        "threadId": {
+          "description": "The thread identifier of the code that generated the notification.",
+          "type": "integer"
+        },
+        "timeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the analysis tool generated the notification.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "exception": {
+          "$ref": "#/definitions/exception",
+          "description": "The runtime exception, if any, relevant to this notification."
+        },
+        "descriptor": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference used to locate the descriptor relevant to this notification."
+        },
+        "associatedRule": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference used to locate the rule descriptor associated with this notification."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the notification."
+        }
+      },
+      "required": ["message"]
+    },
+    "physicalLocation": {
+      "description": "A physical location relevant to a result. Specifies a reference to a programming artifact together with a range of bytes or characters within that artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "address": {
+          "$ref": "#/definitions/address",
+          "description": "The address of the location."
+        },
+        "artifactLocation": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location of the artifact."
+        },
+        "region": {
+          "$ref": "#/definitions/region",
+          "description": "Specifies a portion of the artifact."
+        },
+        "contextRegion": {
+          "$ref": "#/definitions/region",
+          "description": "Specifies a portion of the artifact that encloses the region. Allows a viewer to display additional context around the region."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the physical location."
+        }
+      },
+      "anyOf": [
+        {
+          "required": ["address"]
+        },
+        {
+          "required": ["artifactLocation"]
+        }
+      ]
+    },
+    "propertyBag": {
+      "description": "Key/value pairs that provide additional information about the object.",
+      "type": "object",
+      "additionalProperties": true,
+      "properties": {
+        "tags": {
+          "description": "A set of distinct strings that provide additional information.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "type": "string"
+          }
+        }
+      }
+    },
+    "rectangle": {
+      "description": "An area within an image.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "top": {
+          "description": "The Y coordinate of the top edge of the rectangle, measured in the image's natural units.",
+          "type": "number"
+        },
+        "left": {
+          "description": "The X coordinate of the left edge of the rectangle, measured in the image's natural units.",
+          "type": "number"
+        },
+        "bottom": {
+          "description": "The Y coordinate of the bottom edge of the rectangle, measured in the image's natural units.",
+          "type": "number"
+        },
+        "right": {
+          "description": "The X coordinate of the right edge of the rectangle, measured in the image's natural units.",
+          "type": "number"
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the rectangle."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the rectangle."
+        }
+      }
+    },
+    "region": {
+      "description": "A region within an artifact where a result was detected.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "startLine": {
+          "description": "The line number of the first character in the region.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "startColumn": {
+          "description": "The column number of the first character in the region.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "endLine": {
+          "description": "The line number of the last character in the region.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "endColumn": {
+          "description": "The column number of the character following the end of the region.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "charOffset": {
+          "description": "The zero-based offset from the beginning of the artifact of the first character in the region.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "charLength": {
+          "description": "The length of the region in characters.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "byteOffset": {
+          "description": "The zero-based offset from the beginning of the artifact of the first byte in the region.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "byteLength": {
+          "description": "The length of the region in bytes.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "snippet": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The portion of the artifact contents within the specified region."
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the region."
+        },
+        "sourceLanguage": {
+          "description": "Specifies the source language, if any, of the portion of the artifact specified by the region object.",
+          "type": "string"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the region."
+        }
+      }
+    },
+    "replacement": {
+      "description": "The replacement of a single region of an artifact.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "deletedRegion": {
+          "$ref": "#/definitions/region",
+          "description": "The region of the artifact to delete."
+        },
+        "insertedContent": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The content to insert at the location specified by the 'deletedRegion' property."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the replacement."
+        }
+      },
+      "required": ["deletedRegion"]
+    },
+    "reportingDescriptor": {
+      "description": "Metadata that describes a specific report produced by the tool, as part of the analysis it provides or its runtime reporting.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "id": {
+          "description": "A stable, opaque identifier for the report.",
+          "type": "string"
+        },
+        "deprecatedIds": {
+          "description": "An array of stable, opaque identifiers by which this report was known in some previous version of the analysis tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "type": "string"
+          }
+        },
+        "guid": {
+          "description": "A unique identifier for the reporting descriptor in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "deprecatedGuids": {
+          "description": "An array of unique identifies in the form of a GUID by which this report was known in some previous version of the analysis tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "type": "string",
+            "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+          }
+        },
+        "name": {
+          "description": "A report identifier that is understandable to an end user.",
+          "type": "string"
+        },
+        "deprecatedNames": {
+          "description": "An array of readable identifiers by which this report was known in some previous version of the analysis tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "type": "string"
+          }
+        },
+        "shortDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A concise description of the report. Should be a single sentence that is understandable when visible space is limited to a single line of text."
+        },
+        "fullDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A description of the report. Should, as far as possible, provide details sufficient to enable resolution of any problem indicated by the result."
+        },
+        "messageStrings": {
+          "description": "A set of name/value pairs with arbitrary names. Each value is a multiformatMessageString object, which holds message strings in plain text and (optionally) Markdown format. The strings can include placeholders, which can be used to construct a message in combination with an arbitrary number of additional string arguments.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "defaultConfiguration": {
+          "$ref": "#/definitions/reportingConfiguration",
+          "description": "Default reporting configuration information."
+        },
+        "helpUri": {
+          "description": "A URI where the primary documentation for the report can be found.",
+          "type": "string",
+          "format": "uri"
+        },
+        "help": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "Provides the primary documentation for the report, useful when there is no online documentation."
+        },
+        "relationships": {
+          "description": "An array of objects that describe relationships between this reporting descriptor and others.",
+          "type": "array",
+          "default": [],
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/reportingDescriptorRelationship"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the report."
+        }
+      },
+      "required": ["id"]
+    },
+    "reportingConfiguration": {
+      "description": "Information about a rule or notification that can be configured at runtime.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "enabled": {
+          "description": "Specifies whether the report may be produced during the scan.",
+          "type": "boolean",
+          "default": true
+        },
+        "level": {
+          "description": "Specifies the failure level for the report.",
+          "default": "warning",
+          "enum": ["none", "note", "warning", "error"]
+        },
+        "rank": {
+          "description": "Specifies the relative priority of the report. Used for analysis output only.",
+          "type": "number",
+          "default": -1,
+          "minimum": -1,
+          "maximum": 100
+        },
+        "parameters": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Contains configuration information specific to a report."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the reporting configuration."
+        }
+      }
+    },
+    "reportingDescriptorReference": {
+      "description": "Information about how to locate a relevant reporting descriptor.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "id": {
+          "description": "The id of the descriptor.",
+          "type": "string"
+        },
+        "index": {
+          "description": "The index into an array of descriptors in toolComponent.ruleDescriptors, toolComponent.notificationDescriptors, or toolComponent.taxonomyDescriptors, depending on context.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "guid": {
+          "description": "A guid that uniquely identifies the descriptor.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "toolComponent": {
+          "$ref": "#/definitions/toolComponentReference",
+          "description": "A reference used to locate the toolComponent associated with the descriptor."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the reporting descriptor reference."
+        }
+      },
+      "anyOf": [
+        {
+          "required": ["index"]
+        },
+        {
+          "required": ["guid"]
+        },
+        {
+          "required": ["id"]
+        }
+      ]
+    },
+    "reportingDescriptorRelationship": {
+      "description": "Information about the relation of one reporting descriptor to another.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "target": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference to the related reporting descriptor."
+        },
+        "kinds": {
+          "description": "A set of distinct strings that categorize the relationship. Well-known kinds include 'canPrecede', 'canFollow', 'willPrecede', 'willFollow', 'superset', 'subset', 'equal', 'disjoint', 'relevant', and 'incomparable'.",
+          "type": "array",
+          "default": ["relevant"],
+          "uniqueItems": true,
+          "items": {
+            "type": "string"
+          }
+        },
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of the reporting descriptor relationship."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the reporting descriptor reference."
+        }
+      },
+      "required": ["target"]
+    },
+    "result": {
+      "description": "A result produced by an analysis tool.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "ruleId": {
+          "description": "The stable, unique identifier of the rule, if any, to which this result is relevant.",
+          "type": "string"
+        },
+        "ruleIndex": {
+          "description": "The index within the tool component rules array of the rule object associated with this result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "rule": {
+          "$ref": "#/definitions/reportingDescriptorReference",
+          "description": "A reference used to locate the rule descriptor relevant to this result."
+        },
+        "kind": {
+          "description": "A value that categorizes results by evaluation state.",
+          "default": "fail",
+          "enum": [
+            "notApplicable",
+            "pass",
+            "fail",
+            "review",
+            "open",
+            "informational"
+          ]
+        },
+        "level": {
+          "description": "A value specifying the severity level of the result.",
+          "default": "warning",
+          "enum": ["none", "note", "warning", "error"]
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message that describes the result. The first sentence of the message only will be displayed when visible space is limited."
+        },
+        "analysisTarget": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "Identifies the artifact that the analysis tool was instructed to scan. This need not be the same as the artifact where the result actually occurred."
+        },
+        "locations": {
+          "description": "The set of locations where the result was detected. Specify only one location unless the problem indicated by the result can only be corrected by making a change at every specified location.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/location"
+          }
+        },
+        "guid": {
+          "description": "A stable, unique identifier for the result in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "correlationGuid": {
+          "description": "A stable, unique identifier for the equivalence class of logically identical results to which this result belongs, in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "occurrenceCount": {
+          "description": "A positive integer specifying the number of times this logically unique result was observed in this run.",
+          "type": "integer",
+          "minimum": 1
+        },
+        "partialFingerprints": {
+          "description": "A set of strings that contribute to the stable, unique identity of the result.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "fingerprints": {
+          "description": "A set of strings each of which individually defines a stable, unique identity for the result.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "stacks": {
+          "description": "An array of 'stack' objects relevant to the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/stack"
+          }
+        },
+        "codeFlows": {
+          "description": "An array of 'codeFlow' objects relevant to the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/codeFlow"
+          }
+        },
+        "graphs": {
+          "description": "An array of zero or more unique graph objects associated with the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/graph"
+          }
+        },
+        "graphTraversals": {
+          "description": "An array of one or more unique 'graphTraversal' objects.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/graphTraversal"
+          }
+        },
+        "relatedLocations": {
+          "description": "A set of locations relevant to this result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/location"
+          }
+        },
+        "suppressions": {
+          "description": "A set of suppressions relevant to this result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/suppression"
+          }
+        },
+        "baselineState": {
+          "description": "The state of a result relative to a baseline of a previous run.",
+          "enum": ["new", "unchanged", "updated", "absent"]
+        },
+        "rank": {
+          "description": "A number representing the priority or importance of the result.",
+          "type": "number",
+          "default": -1,
+          "minimum": -1,
+          "maximum": 100
+        },
+        "attachments": {
+          "description": "A set of artifacts relevant to the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/attachment"
+          }
+        },
+        "hostedViewerUri": {
+          "description": "An absolute URI at which the result can be viewed.",
+          "type": "string",
+          "format": "uri"
+        },
+        "workItemUris": {
+          "description": "The URIs of the work items associated with this result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "type": "string",
+            "format": "uri"
+          }
+        },
+        "provenance": {
+          "$ref": "#/definitions/resultProvenance",
+          "description": "Information about how and when the result was detected."
+        },
+        "fixes": {
+          "description": "An array of 'fix' objects, each of which represents a proposed fix to the problem indicated by the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/fix"
+          }
+        },
+        "taxa": {
+          "description": "An array of references to taxonomy reporting descriptors that are applicable to the result.",
+          "type": "array",
+          "default": [],
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/reportingDescriptorReference"
+          }
+        },
+        "webRequest": {
+          "$ref": "#/definitions/webRequest",
+          "description": "A web request associated with this result."
+        },
+        "webResponse": {
+          "$ref": "#/definitions/webResponse",
+          "description": "A web response associated with this result."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the result."
+        }
+      },
+      "required": ["message"]
+    },
+    "resultProvenance": {
+      "description": "Contains information about how and when a result was detected.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "firstDetectionTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the result was first detected. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "lastDetectionTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which the result was most recently detected. See \"Date/time properties\" in the SARIF spec for the required format.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "firstDetectionRunGuid": {
+          "description": "A GUID-valued string equal to the automationDetails.guid property of the run in which the result was first detected.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "lastDetectionRunGuid": {
+          "description": "A GUID-valued string equal to the automationDetails.guid property of the run in which the result was most recently detected.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "invocationIndex": {
+          "description": "The index within the run.invocations array of the invocation object which describes the tool invocation that detected the result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "conversionSources": {
+          "description": "An array of physicalLocation objects which specify the portions of an analysis tool's output that a converter transformed into the result.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/physicalLocation"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the result."
+        }
+      }
+    },
+    "run": {
+      "description": "Describes a single run of an analysis tool, and contains the reported output of that run.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "tool": {
+          "$ref": "#/definitions/tool",
+          "description": "Information about the tool or tool pipeline that generated the results in this run. A run can only contain results produced by a single tool or tool pipeline. A run can aggregate results from multiple log files, as long as context around the tool run (tool command-line arguments and the like) is identical for all aggregated files."
+        },
+        "invocations": {
+          "description": "Describes the invocation of the analysis tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/invocation"
+          }
+        },
+        "conversion": {
+          "$ref": "#/definitions/conversion",
+          "description": "A conversion object that describes how a converter transformed an analysis tool's native reporting format into the SARIF format."
+        },
+        "language": {
+          "description": "The language of the messages emitted into the log file during this run (expressed as an ISO 639-1 two-letter lowercase culture code) and an optional region (expressed as an ISO 3166-1 two-letter uppercase subculture code associated with a country or region). The casing is recommended but not required (in order for this data to conform to RFC5646).",
+          "type": "string",
+          "default": "en-US",
+          "pattern": "^[a-zA-Z]{2}|^[a-zA-Z]{2}-[a-zA-Z]{2}?$"
+        },
+        "versionControlProvenance": {
+          "description": "Specifies the revision in version control of the artifacts that were scanned.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/versionControlDetails"
+          }
+        },
+        "originalUriBaseIds": {
+          "description": "The artifact location specified by each uriBaseId symbol on the machine where the tool originally ran.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/artifactLocation"
+          }
+        },
+        "artifacts": {
+          "description": "An array of artifact objects relevant to the run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/artifact"
+          }
+        },
+        "logicalLocations": {
+          "description": "An array of logical locations such as namespaces, types or functions.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/logicalLocation"
+          }
+        },
+        "graphs": {
+          "description": "An array of zero or more unique graph objects associated with the run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/graph"
+          }
+        },
+        "results": {
+          "description": "The set of results contained in an SARIF log. The results array can be omitted when a run is solely exporting rules metadata. It must be present (but may be empty) if a log file represents an actual scan.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/result"
+          }
+        },
+        "automationDetails": {
+          "$ref": "#/definitions/runAutomationDetails",
+          "description": "Automation details that describe this run."
+        },
+        "runAggregates": {
+          "description": "Automation details that describe the aggregate of runs to which this run belongs.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/runAutomationDetails"
+          }
+        },
+        "baselineGuid": {
+          "description": "The 'guid' property of a previous SARIF 'run' that comprises the baseline that was used to compute result 'baselineState' properties for the run.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "redactionTokens": {
+          "description": "An array of strings used to replace sensitive information in a redaction-aware property.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "type": "string"
+          }
+        },
+        "defaultEncoding": {
+          "description": "Specifies the default encoding for any artifact object that refers to a text file.",
+          "type": "string"
+        },
+        "defaultSourceLanguage": {
+          "description": "Specifies the default source language for any artifact object that refers to a text file that contains source code.",
+          "type": "string"
+        },
+        "newlineSequences": {
+          "description": "An ordered list of character sequences that were treated as line breaks when computing region information for the run.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": true,
+          "default": ["\r\n", "\n"],
+          "items": {
+            "type": "string"
+          }
+        },
+        "columnKind": {
+          "description": "Specifies the unit in which the tool measures columns.",
+          "enum": ["utf16CodeUnits", "unicodeCodePoints"]
+        },
+        "externalPropertyFileReferences": {
+          "$ref": "#/definitions/externalPropertyFileReferences",
+          "description": "References to external property files that should be inlined with the content of a root log file."
+        },
+        "threadFlowLocations": {
+          "description": "An array of threadFlowLocation objects cached at run level.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/threadFlowLocation"
+          }
+        },
+        "taxonomies": {
+          "description": "An array of toolComponent objects relevant to a taxonomy in which results are categorized.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "addresses": {
+          "description": "Addresses associated with this run instance, if any.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/address"
+          }
+        },
+        "translations": {
+          "description": "The set of available translations of the localized data provided by the tool.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "policies": {
+          "description": "Contains configurations that may potentially override both reportingDescriptor.defaultConfiguration (the tool's default severities) and invocation.configurationOverrides (severities established at run-time from the command line).",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "webRequests": {
+          "description": "An array of request objects cached at run level.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/webRequest"
+          }
+        },
+        "webResponses": {
+          "description": "An array of response objects cached at run level.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/webResponse"
+          }
+        },
+        "specialLocations": {
+          "$ref": "#/definitions/specialLocations",
+          "description": "A specialLocations object that defines locations of special significance to SARIF consumers."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the run."
+        }
+      },
+      "required": ["tool"]
+    },
+    "runAutomationDetails": {
+      "description": "Information that describes a run's identity and role within an engineering system process.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "description": {
+          "$ref": "#/definitions/message",
+          "description": "A description of the identity and role played within the engineering system by this object's containing run object."
+        },
+        "id": {
+          "description": "A hierarchical string that uniquely identifies this object's containing run object.",
+          "type": "string"
+        },
+        "guid": {
+          "description": "A stable, unique identifier for this object's containing run object in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "correlationGuid": {
+          "description": "A stable, unique identifier for the equivalence class of runs to which this object's containing run object belongs in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the run automation details."
+        }
+      }
+    },
+    "specialLocations": {
+      "description": "Defines locations of special significance to SARIF consumers.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "displayBase": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "Provides a suggestion to SARIF consumers to display file paths relative to the specified location."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the special locations."
+        }
+      }
+    },
+    "stack": {
+      "description": "A call stack that is relevant to a result.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to this call stack."
+        },
+        "frames": {
+          "description": "An array of stack frames that represents a sequence of calls, rendered in reverse chronological order, that comprise the call stack.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/stackFrame"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the stack."
+        }
+      },
+      "required": ["frames"]
+    },
+    "stackFrame": {
+      "description": "A function call within a stack trace.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "location": {
+          "$ref": "#/definitions/location",
+          "description": "The location to which this stack frame refers."
+        },
+        "module": {
+          "description": "The name of the module that contains the code of this stack frame.",
+          "type": "string"
+        },
+        "threadId": {
+          "description": "The thread identifier of the stack frame.",
+          "type": "integer"
+        },
+        "parameters": {
+          "description": "The parameters of the call that is executing.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": false,
+          "default": [],
+          "items": {
+            "type": "string",
+            "default": []
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the stack frame."
+        }
+      }
+    },
+    "suppression": {
+      "description": "A suppression that is relevant to a result.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "guid": {
+          "description": "A stable, unique identifier for the suppression in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "kind": {
+          "description": "A string that indicates where the suppression is persisted.",
+          "enum": ["inSource", "external"]
+        },
+        "status": {
+          "description": "A string that indicates the review status of the suppression.",
+          "enum": ["accepted", "underReview", "rejected"]
+        },
+        "justification": {
+          "description": "A string representing the justification for the suppression.",
+          "type": "string"
+        },
+        "location": {
+          "$ref": "#/definitions/location",
+          "description": "Identifies the location associated with the suppression."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the suppression."
+        }
+      },
+      "required": ["kind"]
+    },
+    "threadFlow": {
+      "description": "Describes a sequence of code locations that specify a path through a single thread of execution such as an operating system or fiber.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "id": {
+          "description": "An string that uniquely identifies the threadFlow within the codeFlow in which it occurs.",
+          "type": "string"
+        },
+        "message": {
+          "$ref": "#/definitions/message",
+          "description": "A message relevant to the thread flow."
+        },
+        "initialState": {
+          "description": "Values of relevant expressions at the start of the thread flow that may change during thread flow execution.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "immutableState": {
+          "description": "Values of relevant expressions at the start of the thread flow that remain constant.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "locations": {
+          "description": "A temporally ordered array of 'threadFlowLocation' objects, each of which describes a location visited by the tool while producing the result.",
+          "type": "array",
+          "minItems": 1,
+          "uniqueItems": false,
+          "items": {
+            "$ref": "#/definitions/threadFlowLocation"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the thread flow."
+        }
+      },
+      "required": ["locations"]
+    },
+    "threadFlowLocation": {
+      "description": "A location visited by an analysis tool while simulating or monitoring the execution of a program.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "index": {
+          "description": "The index within the run threadFlowLocations array.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "location": {
+          "$ref": "#/definitions/location",
+          "description": "The code location."
+        },
+        "stack": {
+          "$ref": "#/definitions/stack",
+          "description": "The call stack leading to this location."
+        },
+        "kinds": {
+          "description": "A set of distinct strings that categorize the thread flow location. Well-known kinds include 'acquire', 'release', 'enter', 'exit', 'call', 'return', 'branch', 'implicit', 'false', 'true', 'caution', 'danger', 'unknown', 'unreachable', 'taint', 'function', 'handler', 'lock', 'memory', 'resource', 'scope' and 'value'.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "type": "string"
+          }
+        },
+        "taxa": {
+          "description": "An array of references to rule or taxonomy reporting descriptors that are applicable to the thread flow location.",
+          "type": "array",
+          "default": [],
+          "minItems": 0,
+          "uniqueItems": true,
+          "items": {
+            "$ref": "#/definitions/reportingDescriptorReference"
+          }
+        },
+        "module": {
+          "description": "The name of the module that contains the code that is executing.",
+          "type": "string"
+        },
+        "state": {
+          "description": "A dictionary, each of whose keys specifies a variable or expression, the associated value of which represents the variable or expression value. For an annotation of kind 'continuation', for example, this dictionary might hold the current assumed values of a set of global variables.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "nestingLevel": {
+          "description": "An integer representing a containment hierarchy within the thread flow.",
+          "type": "integer",
+          "minimum": 0
+        },
+        "executionOrder": {
+          "description": "An integer representing the temporal order in which execution reached this location.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "executionTimeUtc": {
+          "description": "The Coordinated Universal Time (UTC) date and time at which this location was executed.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "importance": {
+          "description": "Specifies the importance of this location in understanding the code flow in which it occurs. The order from most to least important is \"essential\", \"important\", \"unimportant\". Default: \"important\".",
+          "enum": ["important", "essential", "unimportant"],
+          "default": "important"
+        },
+        "webRequest": {
+          "$ref": "#/definitions/webRequest",
+          "description": "A web request associated with this thread flow location."
+        },
+        "webResponse": {
+          "$ref": "#/definitions/webResponse",
+          "description": "A web response associated with this thread flow location."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the threadflow location."
+        }
+      }
+    },
+    "tool": {
+      "description": "The analysis tool that was run.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "driver": {
+          "$ref": "#/definitions/toolComponent",
+          "description": "The analysis tool that was run."
+        },
+        "extensions": {
+          "description": "Tool extensions that contributed to or reconfigured the analysis tool that was run.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponent"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the tool."
+        }
+      },
+      "required": ["driver"]
+    },
+    "toolComponent": {
+      "description": "A component, such as a plug-in or the driver, of the analysis tool that was run.",
+      "additionalProperties": false,
+      "type": "object",
+      "properties": {
+        "guid": {
+          "description": "A unique identifier for the tool component in the form of a GUID.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "name": {
+          "description": "The name of the tool component.",
+          "type": "string"
+        },
+        "organization": {
+          "description": "The organization or company that produced the tool component.",
+          "type": "string"
+        },
+        "product": {
+          "description": "A product suite to which the tool component belongs.",
+          "type": "string"
+        },
+        "productSuite": {
+          "description": "A localizable string containing the name of the suite of products to which the tool component belongs.",
+          "type": "string"
+        },
+        "shortDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A brief description of the tool component."
+        },
+        "fullDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A comprehensive description of the tool component."
+        },
+        "fullName": {
+          "description": "The name of the tool component along with its version and any other useful identifying information, such as its locale.",
+          "type": "string"
+        },
+        "version": {
+          "description": "The tool component version, in whatever format the component natively provides.",
+          "type": "string"
+        },
+        "semanticVersion": {
+          "description": "The tool component version in the format specified by Semantic Versioning 2.0.",
+          "type": "string"
+        },
+        "dottedQuadFileVersion": {
+          "description": "The binary version of the tool component's primary executable file expressed as four non-negative integers separated by a period (for operating systems that express file versions in this way).",
+          "type": "string",
+          "pattern": "[0-9]+(\\.[0-9]+){3}"
+        },
+        "releaseDateUtc": {
+          "description": "A string specifying the UTC date (and optionally, the time) of the component's release.",
+          "type": "string"
+        },
+        "downloadUri": {
+          "description": "The absolute URI from which the tool component can be downloaded.",
+          "type": "string",
+          "format": "uri"
+        },
+        "informationUri": {
+          "description": "The absolute URI at which information about this version of the tool component can be found.",
+          "type": "string",
+          "format": "uri"
+        },
+        "globalMessageStrings": {
+          "description": "A dictionary, each of whose keys is a resource identifier and each of whose values is a multiformatMessageString object, which holds message strings in plain text and (optionally) Markdown format. The strings can include placeholders, which can be used to construct a message in combination with an arbitrary number of additional string arguments.",
+          "type": "object",
+          "additionalProperties": {
+            "$ref": "#/definitions/multiformatMessageString"
+          }
+        },
+        "notifications": {
+          "description": "An array of reportingDescriptor objects relevant to the notifications related to the configuration and runtime execution of the tool component.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/reportingDescriptor"
+          }
+        },
+        "rules": {
+          "description": "An array of reportingDescriptor objects relevant to the analysis performed by the tool component.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/reportingDescriptor"
+          }
+        },
+        "taxa": {
+          "description": "An array of reportingDescriptor objects relevant to the definitions of both standalone and tool-defined taxonomies.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/reportingDescriptor"
+          }
+        },
+        "locations": {
+          "description": "An array of the artifactLocation objects associated with the tool component.",
+          "type": "array",
+          "minItems": 0,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/artifactLocation"
+          }
+        },
+        "language": {
+          "description": "The language of the messages emitted into the log file during this run (expressed as an ISO 639-1 two-letter lowercase language code) and an optional region (expressed as an ISO 3166-1 two-letter uppercase subculture code associated with a country or region). The casing is recommended but not required (in order for this data to conform to RFC5646).",
+          "type": "string",
+          "default": "en-US",
+          "pattern": "^[a-zA-Z]{2}|^[a-zA-Z]{2}-[a-zA-Z]{2}?$"
+        },
+        "contents": {
+          "description": "The kinds of data contained in this object.",
+          "type": "array",
+          "uniqueItems": true,
+          "default": ["localizedData", "nonLocalizedData"],
+          "items": {
+            "enum": ["localizedData", "nonLocalizedData"]
+          }
+        },
+        "isComprehensive": {
+          "description": "Specifies whether this object contains a complete definition of the localizable and/or non-localizable data for this component, as opposed to including only data that is relevant to the results persisted to this log file.",
+          "type": "boolean",
+          "default": false
+        },
+        "localizedDataSemanticVersion": {
+          "description": "The semantic version of the localized strings defined in this component; maintained by components that provide translations.",
+          "type": "string"
+        },
+        "minimumRequiredLocalizedDataSemanticVersion": {
+          "description": "The minimum value of localizedDataSemanticVersion required in translations consumed by this component; used by components that consume translations.",
+          "type": "string"
+        },
+        "associatedComponent": {
+          "$ref": "#/definitions/toolComponentReference",
+          "description": "The component which is strongly associated with this component. For a translation, this refers to the component which has been translated. For an extension, this is the driver that provides the extension's plugin model."
+        },
+        "translationMetadata": {
+          "$ref": "#/definitions/translationMetadata",
+          "description": "Translation metadata, required for a translation, not populated by other component types."
+        },
+        "supportedTaxonomies": {
+          "description": "An array of toolComponentReference objects to declare the taxonomies supported by the tool component.",
+          "type": "array",
+          "minItems": 0,
+          "uniqueItems": true,
+          "default": [],
+          "items": {
+            "$ref": "#/definitions/toolComponentReference"
+          }
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the tool component."
+        }
+      },
+      "required": ["name"]
+    },
+    "toolComponentReference": {
+      "description": "Identifies a particular toolComponent object, either the driver or an extension.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "name": {
+          "description": "The 'name' property of the referenced toolComponent.",
+          "type": "string"
+        },
+        "index": {
+          "description": "An index into the referenced toolComponent in tool.extensions.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "guid": {
+          "description": "The 'guid' property of the referenced toolComponent.",
+          "type": "string",
+          "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the toolComponentReference."
+        }
+      }
+    },
+    "translationMetadata": {
+      "description": "Provides additional metadata related to translation.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "name": {
+          "description": "The name associated with the translation metadata.",
+          "type": "string"
+        },
+        "fullName": {
+          "description": "The full name associated with the translation metadata.",
+          "type": "string"
+        },
+        "shortDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A brief description of the translation metadata."
+        },
+        "fullDescription": {
+          "$ref": "#/definitions/multiformatMessageString",
+          "description": "A comprehensive description of the translation metadata."
+        },
+        "downloadUri": {
+          "description": "The absolute URI from which the translation metadata can be downloaded.",
+          "type": "string",
+          "format": "uri"
+        },
+        "informationUri": {
+          "description": "The absolute URI from which information related to the translation metadata can be downloaded.",
+          "type": "string",
+          "format": "uri"
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the translation metadata."
+        }
+      },
+      "required": ["name"]
+    },
+    "versionControlDetails": {
+      "description": "Specifies the information necessary to retrieve a desired revision from a version control system.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "repositoryUri": {
+          "description": "The absolute URI of the repository.",
+          "type": "string",
+          "format": "uri"
+        },
+        "revisionId": {
+          "description": "A string that uniquely and permanently identifies the revision within the repository.",
+          "type": "string"
+        },
+        "branch": {
+          "description": "The name of a branch containing the revision.",
+          "type": "string"
+        },
+        "revisionTag": {
+          "description": "A tag that has been applied to the revision.",
+          "type": "string"
+        },
+        "asOfTimeUtc": {
+          "description": "A Coordinated Universal Time (UTC) date and time that can be used to synchronize an enlistment to the state of the repository at that time.",
+          "type": "string",
+          "format": "date-time"
+        },
+        "mappedTo": {
+          "$ref": "#/definitions/artifactLocation",
+          "description": "The location in the local file system to which the root of the repository was mapped at the time of the analysis."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the version control details."
+        }
+      },
+      "required": ["repositoryUri"]
+    },
+    "webRequest": {
+      "description": "Describes an HTTP request.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "index": {
+          "description": "The index within the run.webRequests array of the request object associated with this result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "protocol": {
+          "description": "The request protocol. Example: 'http'.",
+          "type": "string"
+        },
+        "version": {
+          "description": "The request version. Example: '1.1'.",
+          "type": "string"
+        },
+        "target": {
+          "description": "The target of the request.",
+          "type": "string"
+        },
+        "method": {
+          "description": "The HTTP method. Well-known values are 'GET', 'PUT', 'POST', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'.",
+          "type": "string"
+        },
+        "headers": {
+          "description": "The request headers.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "parameters": {
+          "description": "The request parameters.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "body": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The body of the request."
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the request."
+        }
+      }
+    },
+    "webResponse": {
+      "description": "Describes the response to an HTTP request.",
+      "type": "object",
+      "additionalProperties": false,
+      "properties": {
+        "index": {
+          "description": "The index within the run.webResponses array of the response object associated with this result.",
+          "type": "integer",
+          "default": -1,
+          "minimum": -1
+        },
+        "protocol": {
+          "description": "The response protocol. Example: 'http'.",
+          "type": "string"
+        },
+        "version": {
+          "description": "The response version. Example: '1.1'.",
+          "type": "string"
+        },
+        "statusCode": {
+          "description": "The response status code. Example: 451.",
+          "type": "integer"
+        },
+        "reasonPhrase": {
+          "description": "The response reason. Example: 'Not found'.",
+          "type": "string"
+        },
+        "headers": {
+          "description": "The response headers.",
+          "type": "object",
+          "additionalProperties": {
+            "type": "string"
+          }
+        },
+        "body": {
+          "$ref": "#/definitions/artifactContent",
+          "description": "The body of the response."
+        },
+        "noResponseReceived": {
+          "description": "Specifies whether a response was received from the server.",
+          "type": "boolean",
+          "default": false
+        },
+        "properties": {
+          "$ref": "#/definitions/propertyBag",
+          "description": "Key/value pairs that provide additional information about the response."
+        }
+      }
+    }
+  },
+  "description": "Static Analysis Results Format (SARIF) Version 2.1.0 JSON Schema: a standard format for the output of static analysis tools.",
+  "properties": {
+    "$schema": {
+      "description": "The URI of the JSON schema corresponding to the version.",
+      "type": "string",
+      "format": "uri"
+    },
+    "version": {
+      "description": "The SARIF format version of this log file.",
+      "enum": ["2.1.0"]
+    },
+    "runs": {
+      "description": "The set of runs contained in this log file.",
+      "type": "array",
+      "minItems": 0,
+      "uniqueItems": false,
+      "items": {
+        "$ref": "#/definitions/run"
+      }
+    },
+    "inlineExternalProperties": {
+      "description": "References to external property files that share data between runs.",
+      "type": "array",
+      "minItems": 0,
+      "uniqueItems": true,
+      "items": {
+        "$ref": "#/definitions/externalProperties"
+      }
+    },
+    "properties": {
+      "$ref": "#/definitions/propertyBag",
+      "description": "Key/value pairs that provide additional information about the log file."
+    }
+  },
+  "required": ["version", "runs"],
+  "title": "Static Analysis Results Format (SARIF) Version 2.1.0 JSON Schema",
+  "type": "object"
+}
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/vendor/sarif-2.1.0/VENDORED.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/schemas/vendor/sarif-2.1.0/VENDORED.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/vendor/sarif-2.1.0/VENDORED.md	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/schemas/vendor/sarif-2.1.0/VENDORED.md	2026-08-26 17:24:44.595826188 -0300
@@ -0,0 +1,34 @@
+# Vendored: SARIF 2.1.0 JSON Schema
+
+- **Asset:** `sarif-schema.json`
+- **Upstream URL:** https://json.schemastore.org/sarif-2.1.0.json
+- **Canonical source ($id):** https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json
+- **Version:** SARIF 2.1.0 (OASIS Standard; the schema declares `$schema: http://json-schema.org/draft-07/schema#`)
+- **License:** MIT — the OASIS SARIF schema is distributed under the MIT License
+  (see the [sarif-spec repository](https://github.com/oasis-tcs/sarif-spec) and
+  [schemastore](https://www.schemastore.org/)).
+
+  Permission is hereby granted, free of charge, to any person obtaining a copy
+  of this software and associated documentation files (the "Software"), to deal
+  in the Software without restriction, including without limitation the rights
+  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
+  copies of the Software, and to permit persons to whom the Software is
+  furnished to do so, subject to the following conditions:
+
+  The above copyright notice and this permission notice shall be included in
+  all copies or substantial portions of the Software.
+
+  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
+  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
+  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
+  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
+  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
+  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
+  SOFTWARE.
+
+- **Retrieval date:** 2026-08-26
+- **SHA-256** (`sarif-schema.json`):
+  `7c9688f0a1c4a4e1649ecc78521087e664729c1dff56ee8212ff195c7b16132a`
+
+The checksum is verified by `tests/test_export_sarif.py` so an offline build
+cannot drift from the reviewed vendor copy.
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/analysis.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/analysis.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/analysis.py	2026-08-25 21:17:55.010723394 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/analysis.py	2026-08-26 22:29:22.486326988 -0300
@@ -17,34 +17,32 @@
 from .rules import apply_rule_settings, run_rules
 from .snapshot import (
     AnalysisResult,
     AnalysisSnapshot,
     DeclarationBatch,
     LocationRecord,
     ObjectDeclaration,
     ObjectRecord,
     RelationRecord,
     RelationToken,
+    text_key,
     thaw_json,
+    to_location_record,
 )
 from .validation import finding_key, validate
 
 
 STRUCTURAL_ERROR_CODES = frozenset(
     {"QND001", "QND002", "REQ004", "REQ005", "REQ007"}
 )
 
 
-def text_key(value: str) -> tuple[str, str]:
-    return value.casefold(), value
-
-
 def object_key(item: ObjectRecord) -> tuple[object, ...]:
     location = item.locations[0] if item.locations else None
     return (
         *text_key(item.id),
         location.file.casefold() if location else "",
         location.file if location else "",
         location.line if location else 0,
     )
 
 
@@ -118,28 +116,22 @@
         "verified": len(verified),
         "implementation_coverage": (
             round(100 * len(implemented) / total, 1) if total else 100.0
         ),
         "verification_coverage": (
             round(100 * len(verified) / total, 1) if total else 100.0
         ),
     }
 
 
-def _location(source: SourceLocation | None) -> LocationRecord | None:
-    if source is None:
-        return None
-    return LocationRecord(source.file, source.line, source.anchor)
-
-
 def _declaration(item: EngineeringObject) -> ObjectDeclaration:
-    location = _location(item.source)
+    location = to_location_record(item.source)
     return ObjectDeclaration(
         id=item.id,
         type=item.type,
         title=item.title,
         status=item.status,
         body=item.body,
         rationale=item.rationale,
         attributes=item.attributes,
         relations=tuple(
             RelationToken(
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/cli.py	2026-08-26 15:15:36.766060194 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/cli.py	2026-08-26 22:26:03.546989710 -0300
@@ -9,20 +9,21 @@
 from pathlib import Path
 from typing import TextIO
 
 from . import diff as diff_module
 from . import impact as impact_module
 from .analysis import analyze_project
 from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline
 from .config import NeedsConfig, load_config
 from .diagnostics import Finding
 from .export import _write_atomic_text, write_build_outputs, write_v1_graph
+from .exporters import csv_export, junit_export, markdown_export, sarif_export
 from .metrics import render_measure
 from .queries import materialize_queries
 from .quality import QualityReport, build_quality_report, profile_exit_code, report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
 
 class ConfigurationFailure(Exception):
     """Raised when `.quarto-needs.toml` cannot be used."""
 
 
@@ -193,21 +194,26 @@
         _print_quality_text(report)
     return report.exit_code()
 
 
 def _baseline_destination(root: Path, output: str) -> Path:
     candidate = Path(output)
     return candidate if candidate.is_absolute() else root / candidate
 
 
 def _baseline_create(root: Path, args, config: NeedsConfig) -> int:
-    result = analyze_project(root, config=config)
+    try:
+        result = analyze_project(root, config=config)
+    except OSError as error:
+        # Reading the project failed; operational, not validation, failure.
+        print(f"Could not scan {root}: {error}", file=sys.stderr)
+        return 3
     if result.snapshot is None:
         print_findings(result.findings, stream=sys.stderr)
         if not args.allow_invalid:
             return 1
         payload = build_invalid_baseline(result, config)
     else:
         payload = build_baseline(
             result.snapshot, config, queries=materialize_queries(config, result.snapshot)
         )
     destination = _baseline_destination(root, args.output)
@@ -262,21 +268,29 @@
     print(f"  objects: {summary['objects']}")
     print(f"  relations: {summary['relations']}")
     print(f"  findings: {summary['findings']}")
     return 0
 
 
 def _print_diff_text(report) -> None:
     for notice in report.notices:
         print(f"[notice] {notice}: derived deltas suppressed; both sides must share configuration and reference date to compare them")
     if report.is_empty():
-        print("No changes.")
+        if report.suppressed:
+            # Plain "No changes." would claim every category matched,
+            # including the ones this run never compared at all.
+            print(
+                "No changes in the compared categories "
+                f"({', '.join(report.suppressed)} not compared)."
+            )
+        else:
+            print("No changes.")
         return
     for object_id in report.added_objects:
         print(f"+ object {object_id}")
     for object_id in report.removed_objects:
         print(f"- object {object_id}")
     for item in report.modified:
         print(f"~ object {item['id']} ({', '.join(item['fields'])})")
     for item in report.relocated:
         print(f"> object {item['id']} moved {item['from'].get('file')} -> {item['to'].get('file')}")
     for item in report.added_relations:
@@ -294,21 +308,26 @@
     for item in report.gate_regressions:
         print(f"! gate {item['name']} failed (threshold {item['threshold']}, actual {item['actual']})")
 
 
 def _diff(root: Path, args, config: NeedsConfig) -> int:
     try:
         baseline_payload = load_baseline(Path(args.baseline))
     except BaselineError as error:
         print(str(error), file=sys.stderr)
         return 2
-    result = analyze_project(root, config=config)
+    try:
+        result = analyze_project(root, config=config)
+    except OSError as error:
+        # Reading the project failed; operational, not validation, failure.
+        print(f"Could not scan {root}: {error}", file=sys.stderr)
+        return 3
     if result.snapshot is None:
         print_findings(result.findings, stream=sys.stderr)
         return 1
     try:
         report = diff_module.compare(
             baseline_payload,
             result.snapshot,
             config,
             recompute=args.recompute_with == "current",
         )
@@ -321,21 +340,26 @@
         _print_diff_text(report)
     return profile_exit_code(config.profile, False, len(report.gate_regressions))
 
 
 def _impact(root: Path, args, config: NeedsConfig) -> int:
     try:
         baseline_payload = load_baseline(Path(args.baseline))
     except BaselineError as error:
         print(str(error), file=sys.stderr)
         return 2
-    result = analyze_project(root, config=config)
+    try:
+        result = analyze_project(root, config=config)
+    except OSError as error:
+        # Reading the project failed; operational, not validation, failure.
+        print(f"Could not scan {root}: {error}", file=sys.stderr)
+        return 3
     if result.snapshot is None:
         print_findings(result.findings, stream=sys.stderr)
         return 1
     try:
         report = impact_module.analyze(
             baseline_payload,
             result.snapshot,
             config,
             recompute=args.recompute_with == "current",
         )
@@ -362,42 +386,80 @@
 def _export(root: Path, args: argparse.Namespace, config: NeedsConfig | None) -> int:
     effective = config if config is not None else load_config(root)
     if args.baseline is not None and args.format != "markdown":
         # Usage errors are reported before any analysis runs.
         print(
             "usage error: --baseline is only valid with --format markdown "
             f"(got --format {args.format})",
             file=sys.stderr,
         )
         return 2
+    baseline_payload = None
+    if args.baseline is not None:
+        try:
+            baseline_payload = load_baseline(Path(args.baseline))
+        except BaselineError as error:
+            print(str(error), file=sys.stderr)
+            return 2
     result = analyze_project(root, config=effective)
-    if result.snapshot is None:
+    # SARIF is findings-driven: it exports even when a structural failure
+    # left the snapshot None; json/csv still require the snapshot itself.
+    if result.snapshot is None and args.format != "sarif":
         print_findings(result.findings, stream=sys.stderr)
         return 1
+    report = (
+        report_from_snapshot(result.snapshot, effective)
+        if result.snapshot is not None
+        else None
+    )
     output = root / args.output
     try:
         if args.format == "json":
             # Byte-identity with the pre-task v1 projection holds by
             # construction: the default format keeps the existing writer.
             write_v1_graph(output, result.snapshot)
+        elif args.format == "csv":
+            # The csv format's --output names a directory (created on
+            # demand) receiving objects/relations/findings.csv, each
+            # written atomically through export._write_atomic_text.
+            csv_export.write_all(output, result.snapshot)
+        elif args.format == "sarif":
+            # Single-file findings export written atomically; a structurally
+            # invalid project still produces its artifact, then fails policy.
+            sarif_export.write(output, result.findings)
+        elif args.format == "junit":
+            if report is None:
+                print("JUnit export requires a valid snapshot.", file=sys.stderr)
+                return 1
+            junit_export.write(output, report)
         else:
-            # TODO(milestone-4a-writers): Tasks 3-6 replace this raise with
-            # the csv/sarif/junit/markdown writers, each routing its writes
-            # through _write_atomic_text like the json path above.
-            raise NotImplementedError(
-                f"--format {args.format} writer lands with the milestone-4a exporter tasks"
+            if args.format != "markdown" or result.snapshot is None:
+                print("Markdown export requires a valid snapshot.", file=sys.stderr)
+                return 1
+            markdown_export.write(
+                output,
+                result.snapshot,
+                effective,
+                baseline=baseline_payload,
             )
+    except (diff_module.DiffError, impact_module.ImpactError) as error:
+        print(str(error), file=sys.stderr)
+        return 2
     except OSError as error:
         print(f"Could not write {output}: {error}", file=sys.stderr)
         return 3
+    if result.snapshot is None:
+        # The SARIF artifact is on disk; the structural findings still fail.
+        print_findings(result.findings, stream=sys.stderr)
+        return 1
     # The artifact is on disk before the policy verdict leaves the process.
-    report = report_from_snapshot(result.snapshot, effective)
+    assert report is not None
     return profile_exit_code(effective.profile, False, report.gate_failures())
 
 
 def main(argv: list[str] | None = None) -> int:
     parser = argparse.ArgumentParser(prog="quarto-needs", description="Requirements-as-code engine for Quarto")
     parser.add_argument("--root", help="Project root (default: current directory)")
     sub = parser.add_subparsers(dest="command", required=True)
     sub.add_parser("scan", help="Parse project and write .quarto-needs/needs.json")
     sub.add_parser("check", help="Validate the requirements graph")
     sub.add_parser("coverage", help="Print coverage metrics")
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/diff.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/diff.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/diff.py	2026-08-26 10:09:28.715101693 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/diff.py	2026-08-26 17:29:52.306841236 -0300
@@ -1,55 +1,69 @@
 """Classified comparison between a baseline and the current snapshot.
 
 Two guards run before any comparison. A changed configuration or a changed
 reference date means the derived numbers were produced under different rules,
 so reporting their deltas as project changes would be a lie; the diff says so
-and suppresses them instead.
+and suppresses them instead. It says so under `--recompute-with current` too:
+recomputation re-resolves authored relations but cannot re-derive stored
+findings, metrics, or gates, so the suppression is just as real there. The
+suppressed categories are named in `suppressed`, so `empty` is never readable
+as "every category was compared and matched".
 """
 from __future__ import annotations
 
 from dataclasses import dataclass
 from typing import Mapping, Sequence
 
 from . import fingerprints
 from .config import NeedsConfig
 from .quality import report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
 SCHEMA_VERSION = "1"
 
 OBJECT_FIELDS = ("type", "title", "status", "body", "rationale", "attributes")
 
+# Categories whose deltas are derived from the baseline's stored results and
+# are therefore not compared at all when either guard fires.
+SUPPRESSIBLE_CATEGORIES = ("findings", "metrics", "gates")
+
 
 class DiffError(Exception):
     """The two sides cannot be compared."""
 
 
 @dataclass(frozen=True, slots=True)
 class DiffReport:
     baseline_reference_date: str
     current_reference_date: str
     recomputed: bool
     notices: tuple[str, ...]
+    suppressed: tuple[str, ...]
     added_objects: tuple[str, ...]
     removed_objects: tuple[str, ...]
     modified: tuple[Mapping[str, object], ...]
     relocated: tuple[Mapping[str, object], ...]
     added_relations: tuple[Mapping[str, object], ...]
     removed_relations: tuple[Mapping[str, object], ...]
     representation_changes: tuple[Mapping[str, object], ...]
     findings_added: tuple[Mapping[str, object], ...]
     findings_removed: tuple[Mapping[str, object], ...]
     metric_deltas: tuple[Mapping[str, object], ...]
     gate_regressions: tuple[Mapping[str, object], ...]
 
     def is_empty(self) -> bool:
+        """True when every *compared* category matched.
+
+        Suppressed categories are not compared at all, so they cannot
+        contribute; `suppressed` names them and must be read alongside this.
+        """
         return not (
             self.added_objects
             or self.removed_objects
             or self.modified
             or self.relocated
             or self.added_relations
             or self.removed_relations
             or self.representation_changes
             or self.findings_added
             or self.findings_removed
@@ -59,20 +73,21 @@
 
     def to_dict(self) -> dict[str, object]:
         return {
             "schemaVersion": SCHEMA_VERSION,
             "referenceDate": {
                 "baseline": self.baseline_reference_date,
                 "current": self.current_reference_date,
             },
             "recomputed": self.recomputed,
             "notices": list(self.notices),
+            "suppressed": list(self.suppressed),
             "objects": {
                 "added": list(self.added_objects),
                 "removed": list(self.removed_objects),
                 "modified": [dict(item) for item in self.modified],
                 "relocated": [dict(item) for item in self.relocated],
             },
             "relations": {
                 "added": [dict(item) for item in self.added_relations],
                 "removed": [dict(item) for item in self.removed_relations],
                 "representationChanged": [dict(item) for item in self.representation_changes],
@@ -246,26 +261,29 @@
     for item in after.get("gates", []):
         name = str(item["name"])
         was = before_gates.get(name)
         if item.get("passed") is False and (was is None or was.get("passed") is not False):
             regressions.append(
                 {"name": name, "scope": item.get("scope"), "threshold": item.get("threshold"), "actual": item.get("actual")}
             )
     return tuple(regressions)
 
 
-def _recomputed_relations(stored: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
+def recomputed_relations(stored: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
     """Re-resolve stored relations through the *current* catalog.
 
     `--recompute-with current` must compare both sides under one policy, so the
     baseline's authored names are resolved again rather than trusting the
-    families and roles that were canonical when it was written.
+    families and roles that were canonical when it was written. The impact
+    direction is re-resolved with them: `impact` traverses this list, and a
+    stored direction from an older catalog would otherwise steer half the
+    traversal under the policy the flag exists to leave behind.
     """
     from .relations import DEFAULT_RELATION_CATALOG
     from .snapshot import RelationRecord
 
     recomputed: list[dict[str, object]] = []
     for item in stored:
         authored = str(item["authoredName"])
         try:
             kind = DEFAULT_RELATION_CATALOG.resolve(authored)
         except ValueError:
@@ -285,20 +303,21 @@
             impact_direction=kind.impact_direction,
             attributes=item.get("attributes") or {},
             provenance=(),
         )
         recomputed.append(
             {
                 "source": record.source,
                 "authoredName": record.authored_name,
                 "target": record.target,
                 "semanticFamily": record.semantic_family,
+                "impactDirection": record.impact_direction,
                 "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
                 "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
             }
         )
     return recomputed
 
 
 def compare(
     baseline_payload: Mapping[str, object],
     snapshot: AnalysisSnapshot,
@@ -309,72 +328,90 @@
     if not baseline_payload.get("valid", False):
         raise DiffError(
             "This baseline is a diagnostic artifact (valid: false) and cannot be compared; "
             "use `baseline inspect` to read it"
         )
 
     current_configuration = snapshot.configuration_fingerprint
     baseline_configuration = str(baseline_payload.get("configurationFingerprint", ""))
     baseline_date = str(baseline_payload.get("referenceDate", ""))
 
-    notices: list[str] = []
     configuration_differs = baseline_configuration != current_configuration
     date_differs = baseline_date != snapshot.reference_date
-    if not recompute:
-        if configuration_differs:
-            notices.append("configuration-changed")
-        if date_differs:
-            notices.append("reference-date-changed")
-
-    added, removed, modified, relocated = _classify_objects(
-        _baseline_objects(baseline_payload),
-        {record.id: _current_object(record) for record in snapshot.objects},
-    )
-
-    baseline_relations = list(baseline_payload.get("relations", []))
-    if recompute:
-        baseline_relations = _recomputed_relations(baseline_relations)
-    # A catalog change can move families and roles, so semantic fingerprints
-    # from the two sides stop being comparable. Fall back to authored tuples,
-    # which is exactly what the spec prescribes for this case.
-    relation_key = (
-        "authoredFingerprint" if "configuration-changed" in notices else "semanticFingerprint"
-    )
-    added_relations, removed_relations, representation = _classify_relations(
-        baseline_relations, _current_relations(snapshot), key=relation_key
-    )
+    # The notice is emitted in both modes: `--recompute-with current` clears
+    # the *relation* guard, not the derived one, and a silent suppression is
+    # indistinguishable from a clean comparison. `recomputed` tells the two
+    # cases apart for any consumer that needs to.
+    notices: list[str] = []
+    if configuration_differs:
+        notices.append("configuration-changed")
+    if date_differs:
+        notices.append("reference-date-changed")
+
+    try:
+        added, removed, modified, relocated = _classify_objects(
+            _baseline_objects(baseline_payload),
+            {record.id: _current_object(record) for record in snapshot.objects},
+        )
 
-    # Derived results are stored in the baseline, never re-derived, so they are
-    # comparable only when both sides were produced under the same rules and
-    # the same reference date. `recompute` re-resolves authored relations
-    # through the current catalog; it cannot make stored findings, metrics, or
-    # gates comparable, so their deltas stay suppressed silently there.
-    derived_suppressed = configuration_differs or date_differs
-    if derived_suppressed:
-        findings_added: tuple[dict[str, object], ...] = ()
-        findings_removed: tuple[dict[str, object], ...] = ()
-        metric_deltas: tuple[dict[str, object], ...] = ()
-        gate_regressions: tuple[dict[str, object], ...] = ()
-    else:
-        current_report = report_from_snapshot(snapshot, config).to_dict()
-        baseline_report = baseline_payload.get("report", {})
-        findings_added, findings_removed = _classify_findings(
-            baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
+        baseline_relations = list(baseline_payload.get("relations", []))
+        if recompute:
+            baseline_relations = recomputed_relations(baseline_relations)
+        # A catalog change can move families and roles, so semantic fingerprints
+        # from the two sides stop being comparable. Fall back to authored tuples,
+        # which is exactly what the spec prescribes for this case. Recomputation
+        # re-resolves both sides through one catalog, so it restores semantic
+        # comparison; the key therefore tracks the guard, not the notice.
+        relation_key = (
+            "authoredFingerprint"
+            if configuration_differs and not recompute
+            else "semanticFingerprint"
+        )
+        added_relations, removed_relations, representation = _classify_relations(
+            baseline_relations, _current_relations(snapshot), key=relation_key
         )
-        metric_deltas = _classify_metrics(baseline_report, current_report)
-        gate_regressions = _classify_gates(baseline_report, current_report)
+
+        # Derived results are stored in the baseline, never re-derived, so they
+        # are comparable only when both sides were produced under the same rules
+        # and the same reference date. `recompute` re-resolves authored
+        # relations through the current catalog; it cannot make stored findings,
+        # metrics, or gates comparable, so their deltas stay suppressed there
+        # too — announced, not silently.
+        derived_suppressed = configuration_differs or date_differs
+        if derived_suppressed:
+            findings_added: tuple[dict[str, object], ...] = ()
+            findings_removed: tuple[dict[str, object], ...] = ()
+            metric_deltas: tuple[dict[str, object], ...] = ()
+            gate_regressions: tuple[dict[str, object], ...] = ()
+        else:
+            current_report = report_from_snapshot(snapshot, config).to_dict()
+            baseline_report = baseline_payload.get("report", {})
+            findings_added, findings_removed = _classify_findings(
+                baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
+            )
+            metric_deltas = _classify_metrics(baseline_report, current_report)
+            gate_regressions = _classify_gates(baseline_report, current_report)
+    except KeyError as error:
+        # A tampered or truncated artifact can declare schemaVersion "1" and
+        # still omit a key every comparison needs; load_baseline does not
+        # schema-validate, so this is the last line of defense before a raw
+        # traceback reaches the CLI.
+        raise DiffError(
+            f"This baseline is missing required key {error}; it cannot be compared"
+        ) from error
 
     return DiffReport(
         baseline_reference_date=baseline_date,
         current_reference_date=snapshot.reference_date,
         recomputed=recompute,
         notices=tuple(notices),
+        suppressed=SUPPRESSIBLE_CATEGORIES if derived_suppressed else (),
         added_objects=added,
         removed_objects=removed,
         modified=modified,
         relocated=relocated,
         added_relations=added_relations,
         removed_relations=removed_relations,
         representation_changes=representation,
         findings_added=findings_added,
         findings_removed=findings_removed,
         metric_deltas=metric_deltas,
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/csv_export.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/csv_export.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/csv_export.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/csv_export.py	2026-08-26 15:52:02.611662565 -0300
@@ -0,0 +1,117 @@
+from __future__ import annotations
+
+import csv
+import io
+from pathlib import Path
+
+from ..diagnostics import Finding
+from ..export import _write_atomic_text
+from ..snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord
+
+OBJECT_COLUMNS = (
+    "id",
+    "type",
+    "title",
+    "status",
+    "priority",
+    "tags",
+    "body",
+    "rationale",
+)
+RELATION_COLUMNS = ("source", "authored_name", "target", "semantic_family")
+FINDING_COLUMNS = ("code", "severity", "object_id", "message", "file", "line")
+
+# A cell whose text starts with one of these characters would be interpreted
+# as a formula by spreadsheet applications (CSV injection), so it is prefixed
+# with an apostrophe, which spreadsheets render as literal text.
+_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
+
+
+def _neutralize(value: object) -> str:
+    text = str(value)
+    if text.startswith(_DANGEROUS_PREFIXES):
+        return f"'{text}"
+    return text
+
+
+def _row_key(row: dict[str, str], columns: tuple[str, ...]) -> tuple[str, ...]:
+    # Case-insensitive by the leading (identifying) field, then by each
+    # remaining field, with the raw spelling breaking casefold ties.
+    return tuple(
+        part
+        for column in columns
+        for part in (row[column].casefold(), row[column])
+    )
+
+
+def _render(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
+    buffer = io.StringIO(newline="")
+    writer = csv.writer(buffer, lineterminator="\r\n")
+    writer.writerow(columns)
+    for row in sorted(rows, key=lambda item: _row_key(item, columns)):
+        writer.writerow([_neutralize(row[column]) for column in columns])
+    return buffer.getvalue()
+
+
+def _object_row(item: ObjectRecord) -> dict[str, str]:
+    return {
+        "id": item.id,
+        "type": item.type,
+        "title": item.title,
+        "status": item.status,
+        "priority": item.priority or "",
+        "tags": ";".join(item.tags),
+        "body": item.body,
+        "rationale": item.rationale,
+    }
+
+
+def _relation_row(item: RelationRecord) -> dict[str, str]:
+    return {
+        "source": item.source,
+        "authored_name": item.authored_name,
+        "target": item.target,
+        "semantic_family": item.semantic_family,
+    }
+
+
+def _finding_row(item: Finding) -> dict[str, str]:
+    location = item.location
+    return {
+        "code": item.code,
+        "severity": item.severity,
+        "object_id": item.object_id or "",
+        "message": item.message,
+        "file": location.file if location is not None else "",
+        "line": str(location.line) if location is not None else "",
+    }
+
+
+def render_objects(snapshot: AnalysisSnapshot) -> str:
+    return _render(OBJECT_COLUMNS, [_object_row(item) for item in snapshot.objects])
+
+
+def render_relations(snapshot: AnalysisSnapshot) -> str:
+    return _render(
+        RELATION_COLUMNS, [_relation_row(item) for item in snapshot.relations]
+    )
+
+
+def render_findings(snapshot: AnalysisSnapshot) -> str:
+    return _render(
+        FINDING_COLUMNS, [_finding_row(item) for item in snapshot.findings]
+    )
+
+
+def write_all(directory: Path, snapshot: AnalysisSnapshot) -> tuple[Path, ...]:
+    rendered = {
+        "findings.csv": render_findings(snapshot),
+        "objects.csv": render_objects(snapshot),
+        "relations.csv": render_relations(snapshot),
+    }
+    written: list[Path] = []
+    for name in sorted(rendered):
+        path = Path(directory) / name
+        _write_atomic_text(path, rendered[name])
+        written.append(path)
+    return tuple(written)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/__init__.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/__init__.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/__init__.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/__init__.py	2026-08-26 15:52:02.591662627 -0300
@@ -0,0 +1 @@
+"""Deterministic artifact exporters for the canonical analysis snapshot."""
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/junit_export.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/junit_export.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/junit_export.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/junit_export.py	2026-08-26 21:43:54.164982226 -0300
@@ -0,0 +1,64 @@
+"""Deterministic JUnit projection of evaluated quality gates."""
+
+from __future__ import annotations
+
+import xml.etree.ElementTree as ET
+from pathlib import Path
+
+from ..export import _write_atomic_text
+from ..quality import QualityReport
+
+
+def _display(value: object) -> str:
+    return "not evaluated" if value is None else str(value)
+
+
+def render(report: QualityReport) -> str:
+    gates = sorted(report.gates, key=lambda gate: (gate.name.casefold(), gate.name))
+    failures = sum(1 for gate in gates if not gate.passed)
+
+    suites = ET.Element(
+        "testsuites",
+        {"name": "quarto-needs", "tests": str(len(gates)), "failures": str(failures)},
+    )
+    suite = ET.SubElement(
+        suites,
+        "testsuite",
+        {
+            "name": "quarto-needs.gates",
+            "tests": str(len(gates)),
+            "failures": str(failures),
+        },
+    )
+    properties = ET.SubElement(suite, "properties")
+    for name, value in (
+        ("errors", report.findings_by_severity.get("error", 0)),
+        ("warnings", report.findings_by_severity.get("warning", 0)),
+        ("profile", report.profile),
+        ("reference-date", report.reference_date),
+    ):
+        ET.SubElement(properties, "property", {"name": name, "value": str(value)})
+
+    for gate in gates:
+        case = ET.SubElement(
+            suite,
+            "testcase",
+            {"classname": "quarto-needs.gates", "name": gate.name},
+        )
+        if not gate.passed:
+            message = (
+                f"threshold {_display(gate.threshold)}, actual {_display(gate.actual)}"
+            )
+            failure = ET.SubElement(case, "failure", {"message": message})
+            failure.text = (
+                f"Gate {gate.name} failed in scope {gate.scope}: {message}."
+            )
+
+    ET.indent(suites, space="  ")
+    return ET.tostring(suites, encoding="unicode", short_empty_elements=True) + "\n"
+
+
+def write(path: Path, report: QualityReport) -> Path:
+    destination = Path(path)
+    _write_atomic_text(destination, render(report))
+    return destination
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/markdown_export.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/markdown_export.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/markdown_export.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/markdown_export.py	2026-08-26 21:43:54.164982226 -0300
@@ -0,0 +1,137 @@
+"""Deterministic, GitHub-friendly CI summary exporter."""
+
+from __future__ import annotations
+
+from collections.abc import Mapping
+from pathlib import Path
+
+from .. import diff as diff_module
+from .. import impact as impact_module
+from ..config import NeedsConfig
+from ..export import _write_atomic_text
+from ..quality import report_from_snapshot
+from ..snapshot import AnalysisSnapshot
+
+_NO_BASELINE = "No baseline was supplied; change classification is unavailable."
+
+
+def _cell(value: object) -> str:
+    return str(value).replace("|", "\\|").replace("\n", " ")
+
+
+def _table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> list[str]:
+    lines = [
+        "| " + " | ".join(headers) + " |",
+        "| " + " | ".join("---" for _ in headers) + " |",
+    ]
+    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
+    return lines
+
+
+def _changes(report: diff_module.DiffReport) -> list[str]:
+    rows: list[tuple[object, ...]] = []
+    rows.extend(("added", object_id, "") for object_id in report.added_objects)
+    rows.extend(("removed", object_id, "") for object_id in report.removed_objects)
+    rows.extend(
+        ("modified", item["id"], ", ".join(item["fields"])) for item in report.modified
+    )
+    rows.extend(
+        (
+            "relocated",
+            item["id"],
+            f"{item['from'].get('file', 'unknown')} → {item['to'].get('file', 'unknown')}",
+        )
+        for item in report.relocated
+    )
+    rows.extend(
+        ("relation added", item["source"], f"{item['authoredName']} → {item['target']}")
+        for item in report.added_relations
+    )
+    rows.extend(
+        ("relation removed", item["source"], f"{item['authoredName']} → {item['target']}")
+        for item in report.removed_relations
+    )
+    return _table(("Change", "ID", "Details"), rows) if rows else ["No authored changes."]
+
+
+def _coverage(report: diff_module.DiffReport) -> list[str]:
+    rows = [
+        (item["scope"], item["strength"], item["before"], item["after"])
+        for item in report.metric_deltas
+    ]
+    if rows:
+        return _table(("Scope", "Strength", "Before", "After"), rows)
+    if "metrics" in report.suppressed:
+        return ["Coverage deltas were suppressed because comparison axes differ."]
+    return ["No coverage deltas."]
+
+
+def _failed_gates(snapshot: AnalysisSnapshot, config: NeedsConfig) -> list[str]:
+    report = report_from_snapshot(snapshot, config)
+    failed = [gate for gate in report.gates if not gate.passed]
+    rows = [(gate.name, gate.scope, gate.threshold, gate.actual) for gate in failed]
+    return _table(("Gate", "Scope", "Threshold", "Actual"), rows) if rows else ["All gates passed."]
+
+
+def _impact(report: impact_module.ImpactReport) -> list[str]:
+    rows = [
+        (
+            item["id"],
+            item["priority"],
+            item["distance"],
+            " → ".join(item["path"]),
+        )
+        for item in report.impacted
+        if str(item.get("priority") or "").casefold() in {"high", "critical"}
+    ]
+    return _table(("ID", "Priority", "Distance", "Path"), rows) if rows else [
+        "No high or critical impact."
+    ]
+
+
+def render(
+    snapshot: AnalysisSnapshot,
+    config: NeedsConfig,
+    *,
+    baseline: Mapping[str, object] | None = None,
+) -> str:
+    quality = report_from_snapshot(snapshot, config)
+    diff_report = None
+    impact_report = None
+    if baseline is not None:
+        diff_report = diff_module.compare(baseline, snapshot, config, recompute=True)
+        impact_report = impact_module.analyze(baseline, snapshot, config, recompute=True)
+
+    lines = ["# Quarto-Needs CI summary", "", "## Changes", ""]
+    lines.extend(_changes(diff_report) if diff_report is not None else [_NO_BASELINE])
+    lines.extend(["", "## Coverage deltas", ""])
+    lines.extend(_coverage(diff_report) if diff_report is not None else [_NO_BASELINE])
+    lines.extend(["", "## Failed gates", ""])
+    lines.extend(_failed_gates(snapshot, config))
+    lines.extend(["", "## High and critical impact", ""])
+    lines.extend(_impact(impact_report) if impact_report is not None else [_NO_BASELINE])
+    lines.extend(
+        [
+            "",
+            "## Findings",
+            "",
+            (
+                f"Errors: {quality.findings_by_severity.get('error', 0)}; "
+                f"warnings: {quality.findings_by_severity.get('warning', 0)}."
+            ),
+            "",
+        ]
+    )
+    return "\n".join(lines)
+
+
+def write(
+    path: Path,
+    snapshot: AnalysisSnapshot,
+    config: NeedsConfig,
+    *,
+    baseline: Mapping[str, object] | None = None,
+) -> Path:
+    destination = Path(path)
+    _write_atomic_text(destination, render(snapshot, config, baseline=baseline))
+    return destination
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/sarif_export.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/sarif_export.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/exporters/sarif_export.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/exporters/sarif_export.py	2026-08-26 17:25:22.923699645 -0300
@@ -0,0 +1,120 @@
+"""SARIF 2.1.0 exporter.
+
+SARIF consumes findings, not the snapshot: a structurally invalid project
+(no snapshot) still exports its findings, so `render_from_findings` is the
+load-bearing producer and `render`/`write` are conveniences around it.
+"""
+
+from __future__ import annotations
+
+import json
+from collections.abc import Sequence
+from pathlib import Path
+
+import quarto_needs
+
+from ..diagnostics import Finding
+from ..export import _write_atomic_text
+from ..rules import RULES
+from ..snapshot import AnalysisSnapshot
+
+# The $id of the vendored schema (schemas/vendor/sarif-2.1.0/sarif-schema.json).
+SCHEMA_URI = (
+    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
+    "master/Schemata/sarif-schema-2.1.0.json"
+)
+SARIF_VERSION = "2.1.0"
+TOOL_NAME = "quarto-needs"
+AUTOMATION_ID = "quarto-needs/export"
+
+# Finding severities map onto the SARIF level enum (none/note/warning/error).
+_LEVEL_BY_SEVERITY = {
+    "error": "error",
+    "warning": "warning",
+    "info": "note",
+}
+
+
+def _sort_key(finding: Finding) -> tuple[str, str, str]:
+    # Deterministic output: results ordered by code, object_id, message.
+    return (finding.code, finding.object_id or "", finding.message)
+
+
+def _rule_descriptor(code: str) -> dict[str, object]:
+    spec = RULES.get(code)
+    descriptor: dict[str, object] = {
+        "id": code,
+        # Fall back to the bare code when the finding is not in the registry.
+        "shortDescription": {"text": spec.title if spec is not None else code},
+    }
+    if spec is not None:
+        descriptor["fullDescription"] = {"text": spec.help}
+    return descriptor
+
+
+def _result(finding: Finding) -> dict[str, object]:
+    result: dict[str, object] = {
+        "ruleId": finding.code,
+        "level": _LEVEL_BY_SEVERITY.get(finding.severity, "note"),
+        "message": {"text": finding.message},
+        # The finding's existing stable identity hash, independent of
+        # severity overrides, serves as the primary-location line hash.
+        "fingerprints": {"primaryLocationLineHash": finding.fingerprint},
+    }
+    if finding.location is not None:
+        # location.file is already the project-relative POSIX path.
+        result["locations"] = [
+            {
+                "physicalLocation": {
+                    "artifactLocation": {"uri": finding.location.file},
+                    "region": {"startLine": finding.location.line},
+                }
+            }
+        ]
+    return result
+
+
+def build_payload(findings: Sequence[Finding]) -> dict[str, object]:
+    ordered = sorted(findings, key=_sort_key)
+    return {
+        "$schema": SCHEMA_URI,
+        "version": SARIF_VERSION,
+        "runs": [
+            {
+                "tool": {
+                    "driver": {
+                        "name": TOOL_NAME,
+                        "version": quarto_needs.__version__,
+                        "rules": [
+                            _rule_descriptor(code)
+                            for code in sorted({finding.code for finding in ordered})
+                        ],
+                    }
+                },
+                "automationDetails": {"id": AUTOMATION_ID},
+                "results": [_result(finding) for finding in ordered],
+            }
+        ],
+    }
+
+
+def render_from_findings(findings: Sequence[Finding]) -> str:
+    return (
+        json.dumps(
+            build_payload(findings),
+            ensure_ascii=False,
+            indent=2,
+            sort_keys=True,
+        )
+        + "\n"
+    )
+
+
+def render(snapshot: AnalysisSnapshot) -> str:
+    return render_from_findings(snapshot.findings)
+
+
+def write(path: Path, findings: Sequence[Finding]) -> Path:
+    destination = Path(path)
+    _write_atomic_text(destination, render_from_findings(findings))
+    return destination
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/impact.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/impact.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/impact.py	2026-08-26 11:15:26.013708733 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/impact.py	2026-08-26 17:30:13.366784835 -0300
@@ -34,35 +34,40 @@
             "impacted": [dict(item) for item in self.impacted],
         }
 
 
 def _union_edges(
     baseline_relations: Sequence[Mapping[str, object]], snapshot: AnalysisSnapshot
 ) -> dict[str, list[tuple[str, str]]]:
     """Adjacency keyed by source, following each relation's impact direction.
 
     `both` yields an edge in each direction; `none` yields none at all.
+
+    `impactDirection` is read, never defaulted. Defaulting an absent key to
+    `none` deletes the edge from the union graph without saying so, which is
+    precisely the silence this traversal exists to avoid; the schema requires
+    the key and the caller turns its absence into an `ImpactError`.
     """
     adjacency: dict[str, list[tuple[str, str]]] = {}
 
     def add(source: str, target: str, name: str, direction: str) -> None:
         if direction in {"source_to_target", "both"}:
             adjacency.setdefault(source, []).append((target, name))
         if direction in {"target_to_source", "both"}:
             adjacency.setdefault(target, []).append((source, name))
 
     for item in baseline_relations:
         add(
             str(item["source"]),
             str(item["target"]),
             str(item["authoredName"]),
-            str(item.get("impactDirection", "none")),
+            str(item["impactDirection"]),
         )
     for record in snapshot.relations:
         add(record.source, record.target, record.authored_name, record.impact_direction)
 
     for key in adjacency:
         adjacency[key] = sorted(set(adjacency[key]))
     return adjacency
 
 
 def _origins(report: diff_module.DiffReport) -> tuple[dict[str, object], ...]:
@@ -115,24 +120,42 @@
             raise ImpactError(
                 "The baseline was produced under a different configuration; "
                 "pass --recompute-with current so one relation policy governs the traversal"
             )
         if str(baseline_payload.get("referenceDate", "")) != snapshot.reference_date:
             raise ImpactError(
                 "The baseline was produced under a different reference date; "
                 "pass --recompute-with current to traverse under the current date"
             )
 
-    report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
-    origins = _origins(report)
-    adjacency = _union_edges(baseline_payload.get("relations", []), snapshot)
-    baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
+    try:
+        report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
+    except diff_module.DiffError as error:
+        raise ImpactError(str(error)) from error
+
+    try:
+        origins = _origins(report)
+        stored_relations = list(baseline_payload.get("relations", []))
+        # An edge present only in the baseline is propagated with its stored
+        # direction otherwise, so a catalog whose impact direction moved would
+        # steer part of the traversal under the policy `--recompute-with
+        # current` exists to leave behind. Recomputing them here is what makes
+        # one relation policy govern the entire traversal.
+        adjacency = _union_edges(
+            diff_module.recomputed_relations(stored_relations) if recompute else stored_relations,
+            snapshot,
+        )
+        baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
+    except KeyError as error:
+        raise ImpactError(
+            f"This baseline is missing required key {error}; it cannot be traversed"
+        ) from error
     origin_ids = {str(item["id"]) for item in origins}
 
     impacted: dict[tuple[str, str], dict[str, object]] = {}
     for origin in origins:
         start = str(origin["id"])
         queue: deque[tuple[str, tuple[str, ...], tuple[str, ...]]] = deque([(start, (start,), ())])
         visited = {start}
         while queue:
             current, path, relations = queue.popleft()
             distance = len(path) - 1
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/metrics.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/metrics.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/metrics.py	2026-08-25 13:42:01.042814646 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/metrics.py	2026-08-26 22:29:43.354257681 -0300
@@ -3,21 +3,21 @@
 from dataclasses import dataclass
 from typing import Mapping
 
 from .config import NeedsConfig, parse_iso_date, reference_date
 from .queries import (
     DEFAULT_QUERY_NAME,
     DEFAULT_QUERY_SOURCE,
     compile_query,
     evaluate as evaluate_query,
 )
-from .snapshot import AnalysisSnapshot, ObjectRecord
+from .snapshot import AnalysisSnapshot, ObjectRecord, text_key
 
 
 IMPLEMENTATION_FAMILY = "implementation"
 VERIFICATION_FAMILY = "verification"
 EVIDENCE_FAMILY = "evidence"
 
 CATALOG_SCOPE = "catalog"
 
 COVERAGE_STRENGTHS = (
     "implementation-trace",
@@ -67,24 +67,20 @@
 @dataclass(frozen=True, slots=True)
 class ReportMetrics:
     scopes: Mapping[str, ScopeMetrics]
 
     def to_dict(self) -> dict[str, object]:
         return {
             "scopes": {name: self.scopes[name].to_dict() for name in sorted(self.scopes)}
         }
 
 
-def _text_key(value: str) -> tuple[str, str]:
-    return value.casefold(), value
-
-
 def _requirement_ids(snapshot: AnalysisSnapshot) -> set[str]:
     return {item.id for item in snapshot.objects if item.type.endswith("requirement")}
 
 
 def _priority_of(record: ObjectRecord) -> str:
     value = record.attributes.get("priority")
     if value is None or str(value).strip() == "":
         return "unspecified"
     return str(value).casefold()
 
@@ -176,37 +172,37 @@
         "implementation-trace": len(impl_trace),
         "implementation-effective": len(impl_effective),
         "verification-trace": len(ver_trace),
         "verification-successful": len(ver_successful),
         "evidence": len(evidence_ok),
     }
     gaps = {
         "implementation-effective": tuple(
             sorted(
                 (item.id for item in records if item.id not in impl_effective),
-                key=_text_key,
+                key=text_key,
             )
         ),
         "verification-successful": tuple(
             sorted(
                 (item.id for item in records if item.id not in ver_successful),
-                key=_text_key,
+                key=text_key,
             )
         ),
         "evidence": tuple(
             sorted(
                 (
                     item.id
                     for item in records
                     if item.id in ver_successful and item.id not in evidence_ok
                 ),
-                key=_text_key,
+                key=text_key,
             )
         ),
     }
     return ScopeMetrics(
         name=name,
         denominator=denominator,
         breakdowns={
             "type": type_counts,
             "status": status_counts,
             "priority": priority_counts,
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/quality.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/quality.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/quality.py	2026-08-25 15:18:07.834006236 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/quality.py	2026-08-26 22:30:07.774176579 -0300
@@ -1,13 +1,14 @@
 from __future__ import annotations
 
 from dataclasses import dataclass
+from pathlib import Path
 from typing import Mapping, Sequence
 
 from .analysis import analyze_project
 from .config import Gates, NeedsConfig, load_config, reference_date
 from .diagnostics import Finding
 from .metrics import COVERAGE_STRENGTHS, CoverageMeasure, ScopeMetrics, compute_report_metrics
 from .queries import materialize_queries
 
 
 STRUCTURAL_CODES = frozenset({"QND001", "QND002", "REQ004", "REQ005", "REQ007"})
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/queries.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/queries.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/queries.py	2026-08-25 12:47:17.914522868 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/queries.py	2026-08-26 22:25:33.699092389 -0300
@@ -76,21 +76,21 @@
     root: Clause
     sort: tuple[tuple[str, str], ...]
 
 
 def _is_scalar(value: object) -> bool:
     return value is None or isinstance(value, (str, int, float, bool))
 
 
 def _scalar_eq(left: object, right: object) -> bool:
     if isinstance(left, bool) or isinstance(right, bool):
-        return isinstance(left, bool) and isinstance(right, bool) and left is right
+        return isinstance(left, bool) and isinstance(right, bool) and left == right
     if left is None or right is None:
         return left is None and right is None
     if isinstance(left, (int, float)) and isinstance(right, (int, float)):
         return left == right
     if isinstance(left, str) and isinstance(right, str):
         return left.casefold() == right.casefold()
     return False
 
 
 def _validate_field(field: object) -> str:
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/snapshot.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/snapshot.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/snapshot.py	2026-08-25 21:17:41.730756974 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/snapshot.py	2026-08-26 22:29:08.406373751 -0300
@@ -1,24 +1,29 @@
 from __future__ import annotations
 
 import math
 from collections.abc import Mapping
 from dataclasses import dataclass
 from types import MappingProxyType
 from typing import TYPE_CHECKING
 
 if TYPE_CHECKING:
     from .diagnostics import Finding
+    from .model import SourceLocation
 
 JsonScalar = str | int | float | bool | None
 
 
+def text_key(value: str) -> tuple[str, str]:
+    return value.casefold(), value
+
+
 def freeze_json(value: object) -> object:
     if value is None or isinstance(value, (str, int, bool)):
         return value
     if isinstance(value, float):
         if not math.isfinite(value):
             raise TypeError("JSON numbers must be finite")
         return value
     if isinstance(value, (list, tuple)):
         return tuple(freeze_json(item) for item in value)
     if isinstance(value, dict):
@@ -46,20 +51,26 @@
     return frozen
 
 
 @dataclass(frozen=True, slots=True)
 class LocationRecord:
     file: str
     line: int
     anchor: str | None = None
 
 
+def to_location_record(source: SourceLocation | None) -> LocationRecord | None:
+    if source is None:
+        return None
+    return LocationRecord(source.file, source.line, source.anchor)
+
+
 @dataclass(frozen=True, slots=True)
 class RelationToken:
     authored_name: str
     target: str
     attributes: Mapping[str, object]
     location: LocationRecord | None
 
     def __post_init__(self) -> None:
         object.__setattr__(self, "attributes", _freeze_mapping(self.attributes))
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/validation.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/validation.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/validation.py	2026-08-25 09:43:05.669091477 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/src/quarto_needs/validation.py	2026-08-26 22:30:47.326045218 -0300
@@ -1,28 +1,22 @@
 from __future__ import annotations
 
 from collections import Counter
 
 from .diagnostics import Finding
 from .model import EngineeringObject, SourceLocation
-from .snapshot import LocationRecord
+from .snapshot import LocationRecord, to_location_record
 
 
 SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
 
 
-def _location_record(source: SourceLocation | None) -> LocationRecord | None:
-    if source is None:
-        return None
-    return LocationRecord(source.file, source.line, source.anchor)
-
-
 def finding_key(item: Finding) -> tuple[object, ...]:
     location = item.location
     return (
         SEVERITY_ORDER.get(item.severity, 99),
         item.code,
         (item.object_id or "").casefold(),
         item.object_id or "",
         location.file.casefold() if location else "",
         location.file if location else "",
         location.line if location else 0,
@@ -35,31 +29,31 @@
     counts = Counter(o.id for o in objects)
     known_ids = set(counts)
     for need_id, count in counts.items():
         if count > 1:
             source = next(obj.source for obj in objects if obj.id == need_id)
             findings.append(Finding(
                 "REQ004",
                 "error",
                 f"Duplicate ID: {need_id}",
                 need_id,
-                _location_record(source),
+                to_location_record(source),
             ))
 
     for obj in objects:
         for rel in obj.relations:
             if rel.target not in known_ids:
                 findings.append(Finding(
                     "REQ005", "error",
                     f"{obj.id} references unknown object {rel.target} via {rel.type}",
                     obj.id,
-                    _location_record(obj.source),
+                    to_location_record(obj.source),
                 ))
 
     require_rationale_for = require_rationale_for or {"system-requirement", "software-requirement"}
     for obj in objects:
         if obj.type in require_rationale_for and not obj.rationale and "### Rationale" not in obj.body:
             findings.append(Finding("REQ002", "warning", f"{obj.id} has no rationale", obj.id))
         if obj.status == "approved" and obj.type.endswith("requirement"):
             has_verification = any(r.type in {"verified-by", "validated-by"} for r in obj.relations)
             if not has_verification:
                 findings.append(Finding("REQ006", "warning", f"{obj.id} is approved but has no verification relation", obj.id))
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_ci_workflow.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_ci_workflow.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_ci_workflow.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_ci_workflow.py	2026-08-26 21:43:54.164982226 -0300
@@ -0,0 +1,52 @@
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
+
+yaml = pytest.importorskip("yaml")
+
+WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
+
+
+def parsed() -> dict:
+    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
+
+
+def test_workflow_has_the_three_specified_jobs() -> None:
+    jobs = parsed()["jobs"]
+    assert {"core", "quarto", "quality"} <= set(jobs)
+
+
+def test_core_runs_the_python_matrix() -> None:
+    matrix = parsed()["jobs"]["core"]["strategy"]["matrix"]["python-version"]
+    assert ["3.10", "3.11", "3.12", "3.13", "3.14"] == matrix
+
+
+def test_artifacts_upload_always_and_sarif_is_least_privilege() -> None:
+    text = WORKFLOW.read_text(encoding="utf-8")
+    assert "if: always()" in text
+    assert "pull_request_target" not in text
+    quality = parsed()["jobs"]["quality"]
+    assert quality["permissions"] == {"contents": "read", "security-events": "write"}
+    steps = quality["steps"]
+    upload_steps = [step for step in steps if "upload-artifact" in str(step.get("uses", ""))]
+    assert upload_steps, "quality must upload artifacts"
+    assert any("github/codeql-action/upload-sarif" in str(step.get("uses", "")) for step in steps)
+
+
+def test_quality_generates_every_export_format_and_summary() -> None:
+    run_steps = [str(step.get("run", "")) for step in parsed()["jobs"]["quality"]["steps"]]
+    joined = "\n".join(run_steps)
+    for name in ("json", "csv", "sarif", "junit", "markdown"):
+        assert f"--format {name}" in joined, name
+    assert "$GITHUB_STEP_SUMMARY" in joined
+
+
+def test_quarto_is_pinned_to_a_stable_release() -> None:
+    steps = parsed()["jobs"]["quarto"]["steps"]
+    install = next(step for step in steps if step.get("name") == "Install project and test dependencies")
+    setup = next(step for step in steps if "quarto-actions/setup" in str(step.get("uses", "")))
+    assert install["run"] == "make setup"
+    assert setup["uses"] == "quarto-dev/quarto-actions/setup@v2"
+    assert setup["with"]["version"] == "1.10.18"
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_cli.py	2026-08-26 15:16:01.302026971 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_cli.py	2026-08-26 21:43:54.168982210 -0300
@@ -697,29 +697,58 @@
     assert cli.main(["--root", str(tmp_path), "diff", destination, "--format", "json"]) == 0
 
     payload = json.loads(capsys.readouterr().out)
     assert payload["empty"] is True
     assert payload["notices"] == []
 
 
 def test_diff_validates_against_the_diff_schema(tmp_path: Path, capsys) -> None:
     from jsonschema import Draft202012Validator
 
-    write_valid_project(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n',
+        encoding="utf-8",
+    )
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
+        "verified-by: TC-1\n"
+        "\n## Authenticate\nThe service shall authenticate.\n"
+        "\n### Rationale\nProtect data.\n"
+        ":::\n\n"
+        "::: {.need #TC-1 type=test-case status=passed}\n"
+        "\n## Login\nSigns in.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
     cli.main(["--root", str(tmp_path), "baseline", "create"])
     capsys.readouterr()  # flush the create command's text output before the JSON run
+    source = tmp_path / "needs.qmd"
+    moved = tmp_path / "moved.qmd"
+    moved.write_text(
+        source.read_text(encoding="utf-8")
+        .replace("verified-by: TC-1\n", "")
+        .replace("The service shall authenticate.", "The service shall authenticate administrators."),
+        encoding="utf-8",
+    )
+    source.unlink()
     cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json"])
     payload = json.loads(capsys.readouterr().out)
 
     schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "diff-v1.schema.json").read_text(encoding="utf-8"))
     Draft202012Validator.check_schema(schema)
     Draft202012Validator(schema).validate(payload)
+    assert payload["objects"]["modified"]
+    assert payload["objects"]["relocated"]
+    assert payload["relations"]["removed"]
+    assert payload["findings"]["added"]
+    assert payload["metrics"]
+    assert payload["gates"]["regressed"]
 
 
 def test_diff_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
     calls = 0
     real_analyze = cli.analyze_project
 
     def counted(root: Path, **kwargs: object):
         nonlocal calls
@@ -740,37 +769,64 @@
 
     assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")]) == 2
     assert "diagnostic artifact" in capsys.readouterr().err
 
 
 def test_diff_reports_a_missing_baseline_as_usage_error(tmp_path: Path) -> None:
     write_valid_project(tmp_path)
     assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "absent.json")]) == 2
 
 
-def test_diff_recompute_with_current_clears_notices(tmp_path: Path, capsys) -> None:
+def test_diff_recompute_with_current_keeps_suppression_visible(tmp_path: Path, capsys) -> None:
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
     capsys.readouterr()  # flush the create command's text output before the JSON run
     destination = tmp_path / "baselines" / "quarto-needs.json"
     payload = json.loads(destination.read_text(encoding="utf-8"))
     payload["referenceDate"] = "1999-01-01"
     destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
 
     cli.main(["--root", str(tmp_path), "diff", str(destination), "--format", "json"])
     assert "reference-date-changed" in json.loads(capsys.readouterr().out)["notices"]
 
     cli.main([
         "--root", str(tmp_path), "diff", str(destination),
         "--recompute-with", "current", "--format", "json",
     ])
-    assert json.loads(capsys.readouterr().out)["notices"] == []
+    recomputed = json.loads(capsys.readouterr().out)
+    assert recomputed["notices"] == ["reference-date-changed"]
+    assert recomputed["suppressed"] == ["findings", "metrics", "gates"]
+    assert recomputed["empty"] is True
+
+
+def test_diff_strict_profile_exits_one_on_a_gate_regression(tmp_path: Path, capsys) -> None:
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n',
+        encoding="utf-8",
+    )
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
+        "verified-by: TC-1\n\n## Requirement\nBody.\n:::\n\n"
+        "::: {.need #TC-1 type=test-case status=passed}\n\n## Test\nPasses.\n:::\n",
+        encoding="utf-8",
+    )
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()
+    baseline_path = tmp_path / "baselines" / "quarto-needs.json"
+    source = tmp_path / "needs.qmd"
+    source.write_text(
+        source.read_text(encoding="utf-8").replace("verified-by: TC-1\n", ""),
+        encoding="utf-8",
+    )
+
+    assert cli.main(["--root", str(tmp_path), "diff", str(baseline_path)]) == 1
+    assert "! gate min-verification-trace failed" in capsys.readouterr().out
 
 
 def test_impact_validates_against_the_impact_schema(tmp_path: Path, capsys) -> None:
     from jsonschema import Draft202012Validator
 
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
     capsys.readouterr()  # flush the create command's text output before the JSON run
     (tmp_path / "needs.qmd").write_text(
         (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace("First body.", "Changed body."),
@@ -865,22 +921,20 @@
     write_valid_project(tmp_path)
     first = tmp_path / "a.json"
     second = tmp_path / "b.json"
     assert cli.main(["--root", str(tmp_path), "export", "--output", str(first)]) == 0
     assert cli.main(["--root", str(tmp_path), "export", "--format", "json", "--output", str(second)]) == 0
 
     assert first.read_bytes() == second.read_bytes()
     assert len(hashlib.sha256(first.read_bytes()).hexdigest()) == 64
 
 
-# TODO(milestone-4a-writers): remove this xfail when Tasks 3-6 land the writers.
-@pytest.mark.xfail(strict=True, reason="csv/sarif/junit writers land in Tasks 3-6")
 def test_export_runs_exactly_one_analysis_per_format(
     tmp_path: Path, monkeypatch: pytest.MonkeyPatch
 ) -> None:
     write_valid_project(tmp_path)
     calls = 0
     real_analyze = cli.analyze_project
 
     def counted(root: Path, **kwargs: object):
         nonlocal calls
         calls += 1
@@ -899,22 +953,20 @@
 
 def test_export_rejects_baseline_for_non_markdown_formats(tmp_path: Path, capsys) -> None:
     write_valid_project(tmp_path)
     assert cli.main([
         "--root", str(tmp_path), "export", "--format", "sarif",
         "--output", str(tmp_path / "out.sarif"), "--baseline", str(tmp_path / "none.json"),
     ]) == 2
     assert "markdown" in capsys.readouterr().err
 
 
-# TODO(milestone-4a-writers): remove this xfail when Task 6 lands the markdown writer.
-@pytest.mark.xfail(strict=True, reason="markdown writer lands in Task 6")
 def test_export_preserves_artifacts_on_policy_failure(tmp_path: Path) -> None:
     """A failing strict gate still writes the artifact, then exits 1."""
     # An approved requirement with no verification makes the verification gate
     # fail with a non-zero denominator (an empty scope passes vacuously).
     (tmp_path / "needs.qmd").write_text(
         "::: {.need #REQ-1 type=system-requirement status=approved}\n"
         "\n## Authenticate\nBody.\n"
         ":::\n",
         encoding="utf-8",
     )
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_diff.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_diff.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_diff.py	2026-08-26 09:40:42.266829023 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_diff.py	2026-08-26 21:43:54.168982210 -0300
@@ -154,35 +154,37 @@
     before = {**before, "referenceDate": "1999-01-01"}
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     assert "reference-date-changed" in report.notices
     assert report.metric_deltas == ()
     assert report.findings_added == ()
 
 
-def test_recompute_clears_the_guards(tmp_path: Path) -> None:
+def test_recompute_keeps_suppressed_categories_visible(tmp_path: Path) -> None:
     write(tmp_path)
     before = baseline_of(tmp_path)
     before = {**before, "referenceDate": "1999-01-01"}
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config, recompute=True)
 
-    assert report.notices == ()
+    assert report.notices == ("reference-date-changed",)
+    assert report.suppressed == ("findings", "metrics", "gates")
+    assert report.is_empty()
     assert report.recomputed is True
 
 
 def test_recompute_does_not_manufacture_derived_deltas_from_a_config_change(tmp_path: Path) -> None:
     """The baseline stores its derived results; they cannot be re-derived, so a
-    config-only change must stay silent even under recompute.
+    config-only change must not manufacture derived deltas under recompute.
 
     REQ-2 is approved but unverified, so verification coverage is 1 of 2 (50%).
     The baseline is taken under the default configuration (no verification
     gate); only then does the configuration grow a 100.0 threshold. Authored
     content never moves — any derived delta is manufactured by the config edit.
     """
     write(tmp_path)
     (tmp_path / "extra.qmd").write_text(
         "::: {.need #REQ-2 type=system-requirement status=approved priority=low}\n"
         "\n## Second\nSecond body.\n"
@@ -191,21 +193,22 @@
         encoding="utf-8",
     )
     before = baseline_of(tmp_path)
     (tmp_path / ".quarto-needs.toml").write_text(
         "[gates]\nmin-verification-trace = 100.0\n", encoding="utf-8"
     )
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config, recompute=True)
 
-    assert report.notices == ()
+    assert report.notices == ("configuration-changed",)
+    assert report.suppressed == ("findings", "metrics", "gates")
     assert report.modified == ()
     assert report.gate_regressions == ()
     assert report.metric_deltas == ()
     assert report.findings_added == ()
 
 
 def test_configuration_change_still_compares_authored_relations(tmp_path: Path) -> None:
     """Authored comparison keeps running; only the derived deltas stop."""
     write(tmp_path)
     before = baseline_of(tmp_path)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_example_project.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_example_project.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_example_project.py	2026-08-26 15:11:45.458373391 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_example_project.py	2026-08-26 21:43:54.168982210 -0300
@@ -259,42 +259,47 @@
 def test_aegis_baseline_validates_against_the_baseline_schema():
     import json as _json
     from jsonschema import Draft202012Validator
 
     schema = _json.loads((ROOT / "schemas" / "baseline-v1.schema.json").read_text(encoding="utf-8"))
     payload = _json.loads((ROOT / "examples/book/baselines/quarto-needs.json").read_text(encoding="utf-8"))
     Draft202012Validator.check_schema(schema)
     Draft202012Validator(schema).validate(payload)
 
 
-def test_aegis_impact_explains_a_removed_verification(tmp_path: Path):
-    """Removing an edge in a copy of the book must reach the requirement."""
+def test_aegis_impact_explains_a_removed_verification(tmp_path: Path, capsys):
+    """Removing a verification edge must retain its explicit impact path."""
+    import json as _json
     import shutil as _shutil
     from quarto_needs import cli
 
     project = tmp_path / "book"
     _shutil.copytree(ROOT / "examples/book", project, ignore=_shutil.ignore_patterns("_book", ".quarto"))
     baseline_path = project / "baselines" / "quarto-needs.json"
 
     system = project / "requirements" / "system.qmd"
     system.write_text(
         system.read_text(encoding="utf-8").replace('verified-by="IAM-TC-001"', "", 1),
         encoding="utf-8",
     )
 
     # The checked-in baseline predates the run day, and impact (per spec)
     # rejects a reference-date mismatch; the documented escape hatch keeps the
     # showcase runnable on any date.
     assert cli.main([
         "--root", str(project), "impact", str(baseline_path),
         "--recompute-with", "current", "--format", "json",
     ]) == 0
+    payload = _json.loads(capsys.readouterr().out)
+    test_case = next(item for item in payload["impacted"] if item["id"] == "IAM-TC-001")
+    assert test_case["origin"] == "IAM-SYS-001"
+    assert test_case["path"] == ["IAM-SYS-001", "IAM-TC-001"]
 
 
 def test_aegis_quality_report_projects_passing_gates():
     """The projected report the dashboard reads must agree with the CLI verdict."""
     import json as _json
 
     graph = _json.loads(
         (ROOT / "examples/book/.quarto-needs/needs.json").read_text(encoding="utf-8")
     )
     report = graph["extensions"]["quartoNeeds"]["report"]
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_export_csv.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_export_csv.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_export_csv.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_export_csv.py	2026-08-26 15:51:40.775730428 -0300
@@ -0,0 +1,58 @@
+from __future__ import annotations
+
+import csv
+from pathlib import Path
+
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+from quarto_needs.exporters import csv_export
+
+
+def write_project(root: Path) -> None:
+    (root / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
+        "verified-by: TC-1\n"
+        "rationale: Protect data.\n"
+        "\n## Authenticate\nThe service shall authenticate.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #TC-1 type=test-case status=passed}\n"
+        "\n## Login\n=SUM(A1:A9) starts a formula when pasted into a spreadsheet\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+
+def build(root: Path):
+    result = analyze_project(root, config=load_config(root))
+    assert result.snapshot is not None
+    return result.snapshot
+
+
+def test_csv_writes_three_files_with_expected_headers(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    written = csv_export.write_all(tmp_path / "csv", build(tmp_path))
+
+    assert [path.name for path in written] == ["findings.csv", "objects.csv", "relations.csv"]
+    rows = list(csv.DictReader((tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8").splitlines()))
+    assert rows[0]["id"] == "REQ-1"
+    assert rows[0]["type"] == "system-requirement"
+
+
+def test_csv_neutralizes_formula_injection(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    csv_export.write_all(tmp_path / "csv", build(tmp_path))
+
+    text = (tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8")
+    cells = {value: None for row in csv.DictReader(text.splitlines()) for value in row.values()}
+    dangerous = [value for value in cells if value.startswith(("=", "+", "-", "@", "\t", "\r"))]
+    assert not dangerous
+    assert any(value.startswith("'=") for value in cells), "the neutralized cell must carry the apostrophe prefix"
+
+
+def test_csv_is_deterministic(tmp_path: Path, monkeypatch) -> None:
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
+    write_project(tmp_path)
+    first = csv_export.render_objects(build(tmp_path))
+    second = csv_export.render_objects(build(tmp_path))
+    assert first == second
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_export_junit.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_export_junit.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_export_junit.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_export_junit.py	2026-08-26 21:43:54.168982210 -0300
@@ -0,0 +1,79 @@
+from __future__ import annotations
+
+import xml.etree.ElementTree as ET
+from pathlib import Path
+
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+from quarto_needs.exporters import junit_export
+from quarto_needs.quality import report_from_snapshot
+
+
+def write_project(root: Path) -> None:
+    (root / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
+        "verified-by: TC-1\n"
+        "\n## Authenticate\nBody.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #REQ-2 type=system-requirement status=approved}\n"
+        "\n## Second\nBody.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #TC-1 type=test-case status=passed}\n"
+        "\n## Login\nSigns in.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+
+def report_for(root: Path):
+    config = load_config(root)
+    result = analyze_project(root, config=config)
+    assert result.snapshot is not None
+    return report_from_snapshot(result.snapshot, config)
+
+
+def test_junit_has_one_testcase_per_gate_and_failures_name_the_gate(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n', encoding="utf-8"
+    )
+    report = report_for(tmp_path)
+
+    root = ET.fromstring(junit_export.render(report))
+    assert root.tag == "testsuites"
+    suite = root.find("testsuite")
+    assert suite is not None
+    names = [case.attrib["name"] for case in suite.findall("testcase")]
+    assert names == sorted(g["name"] for g in report.to_dict()["gates"])
+
+    failed = {
+        case.attrib["name"]
+        for case in suite.iter("testcase")
+        if case.find("failure") is not None
+    }
+    expected = {g["name"] for g in report.to_dict()["gates"] if g["passed"] is False}
+    assert failed == expected
+
+
+def test_junit_properties_carry_warning_counts_and_output_is_deterministic(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    report = report_for(tmp_path)
+
+    first = junit_export.render(report)
+    root = ET.fromstring(first)
+    properties = {p.attrib["name"]: p.attrib["value"] for p in root.iter("property")}
+    assert properties["warnings"] == str(report.findings_by_severity.get("warning", 0))
+    assert properties["profile"] == report.profile
+
+    assert junit_export.render(report) == first
+
+
+def test_junit_writer_uses_the_atomic_text_path(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    report = report_for(tmp_path)
+    destination = tmp_path / "nested" / "quality.xml"
+
+    assert junit_export.write(destination, report) == destination
+    assert destination.read_text(encoding="utf-8") == junit_export.render(report)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_export_markdown.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_export_markdown.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_export_markdown.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_export_markdown.py	2026-08-26 21:43:54.168982210 -0300
@@ -0,0 +1,97 @@
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
+
+from quarto_needs import baseline as baseline_module
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+from quarto_needs.exporters import markdown_export
+
+
+def write_project(root: Path) -> None:
+    (root / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
+        "verified-by: TC-1\n"
+        "\n## Authenticate\nThe service shall authenticate.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #TC-1 type=test-case status=passed priority=high}\n"
+        "\n## Login\nSigns in.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+
+def built(root: Path):
+    config = load_config(root)
+    result = analyze_project(root, config=config)
+    assert result.snapshot is not None
+    return result.snapshot, config
+
+
+def test_summary_without_a_baseline_says_so_and_lists_failed_gates(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[gates]\nmin-evidence = 100.0\n', encoding="utf-8"
+    )
+    snapshot, config = built(tmp_path)
+
+    text = markdown_export.render(snapshot, config)
+
+    assert "## Changes" in text and "No baseline was supplied" in text
+    assert "## Failed gates" in text and "min-evidence" in text
+    assert "## High and critical impact" in text
+
+
+def test_summary_with_a_baseline_reports_changes_and_impact(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
+    write_project(tmp_path)
+    snapshot, config = built(tmp_path)
+    payload = baseline_module.build_baseline(snapshot, config)
+
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
+        "verified-by: TC-1\n"
+        "\n## Authenticate\nThe service shall authenticate every administrator.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #TC-1 type=test-case status=passed priority=high}\n"
+        "\n## Login\nSigns in.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+    snapshot, config = built(tmp_path)
+
+    text = markdown_export.render(snapshot, config, baseline=payload)
+
+    assert "REQ-1" in text and "body" in text
+    assert "TC-1" in text
+    assert "## Coverage deltas" in text
+
+
+def test_summary_escapes_markdown_table_cells(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    snapshot, config = built(tmp_path)
+    payload = baseline_module.build_baseline(snapshot, config)
+    (tmp_path / "needs.qmd").write_text(
+        (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace(
+            "The service shall authenticate.", "Changed | with a table delimiter."
+        ),
+        encoding="utf-8",
+    )
+    snapshot, config = built(tmp_path)
+
+    text = markdown_export.render(snapshot, config, baseline=payload)
+    assert "REQ-1" in text
+    assert "| modified | REQ-1 | body |" in text
+
+
+def test_summary_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
+    write_project(tmp_path)
+    snapshot, config = built(tmp_path)
+    assert markdown_export.render(snapshot, config) == markdown_export.render(snapshot, config)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_export_sarif.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_export_sarif.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_export_sarif.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_export_sarif.py	2026-08-26 17:24:57.459783717 -0300
@@ -0,0 +1,77 @@
+from __future__ import annotations
+
+import hashlib
+import json
+from pathlib import Path
+
+import pytest
+from jsonschema import Draft7Validator
+
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+from quarto_needs.exporters import sarif_export
+
+
+ROOT = Path(__file__).resolve().parents[1]
+SCHEMA = ROOT / "schemas" / "vendor" / "sarif-2.1.0" / "sarif-schema.json"
+
+# Locked in schemas/vendor/sarif-2.1.0/VENDORED.md so an offline build cannot
+# drift from the reviewed vendor copy.
+VENDORED_SHA256 = "7c9688f0a1c4a4e1649ecc78521087e664729c1dff56ee8212ff195c7b16132a"
+
+
+def write_project(root: Path) -> None:
+    (root / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
+        "verified-by: TC-1\n"
+        "\n## Authenticate\nBody.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #DUP type=need status=draft}\n\n## A\nA.\n:::\n"
+        "\n::: {.need #DUP type=need status=draft}\n\n## B\nB.\n:::\n",
+        encoding="utf-8",
+    )
+
+
+def snapshot_with_findings(root: Path):
+    result = analyze_project(root, config=load_config(root))
+    return result.declarations and result.findings and result or None
+
+
+def test_sarif_validates_against_the_vendored_schema(tmp_path: Path) -> None:
+    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
+    Draft7Validator.check_schema(schema)
+
+    (tmp_path / "ok.qmd").write_text(
+        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+    result = analyze_project(tmp_path, config=load_config(tmp_path))
+    assert result.snapshot is not None
+
+    payload = json.loads(sarif_export.render(result.snapshot))
+    Draft7Validator(schema).validate(payload)
+
+
+def test_sarif_maps_findings_with_locations_and_fingerprints(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    result = analyze_project(tmp_path, config=load_config(tmp_path))
+    assert any(f.code == "REQ004" for f in result.findings)
+
+    payload = json.loads(sarif_export.render_from_findings(result.findings))
+    result_entry = next(r for r in payload["runs"][0]["results"] if r["ruleId"] == "REQ004")
+
+    assert result_entry["fingerprints"]["primaryLocationLineHash"]
+    assert result_entry["locations"][0]["physicalLocation"]["region"]["startLine"] > 0
+    assert payload["runs"][0]["tool"]["driver"]["rules"], "rule metadata must be present"
+
+
+def test_sarif_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
+    write_project(tmp_path)
+    result = analyze_project(tmp_path, config=load_config(tmp_path))
+    assert sarif_export.render_from_findings(result.findings) == sarif_export.render_from_findings(result.findings)
+
+
+def test_vendored_sarif_schema_checksum_is_locked() -> None:
+    """The vendored SARIF schema must match the SHA-256 recorded in VENDORED.md."""
+    assert hashlib.sha256(SCHEMA.read_bytes()).hexdigest() == VENDORED_SHA256
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_fingerprints.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_fingerprints.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_fingerprints.py	2026-08-26 00:49:44.521332899 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_fingerprints.py	2026-08-26 21:43:54.172982192 -0300
@@ -1,12 +1,14 @@
 from __future__ import annotations
 
+from types import SimpleNamespace
+
 from quarto_needs import fingerprints
 from quarto_needs.config import embedded_defaults
 from quarto_needs.snapshot import LocationRecord, ObjectRecord, RelationRecord
 
 
 def make_object(**overrides: object) -> ObjectRecord:
     base = dict(
         id="REQ-1",
         type="functional-requirement",
         title="Authenticate",
@@ -49,28 +51,48 @@
 def test_object_fingerprint_changes_with_every_authored_field() -> None:
     """Each field the spec names must actually participate."""
     original = fingerprints.object_content_fingerprint(make_object())
     for field, value in (
         ("id", "REQ-2"),
         ("type", "system-requirement"),
         ("title", "Other"),
         ("status", "draft"),
         ("body", "Different body."),
         ("rationale", "Different rationale."),
-        # Vary priority and tags separately so each computed property is proven
-        # to participate on its own.
         ("attributes", {"priority": "low", "tags": "security"}),
         ("attributes", {"priority": "high", "tags": "authentication"}),
     ):
         assert fingerprints.object_content_fingerprint(make_object(**{field: value})) != original, field
 
 
+def test_object_fingerprint_includes_priority_and_tags_as_named_fields() -> None:
+    """The derived fields participate even when the attributes payload is equal."""
+    record = make_object()
+    common = {
+        "id": record.id,
+        "type": record.type,
+        "title": record.title,
+        "status": record.status,
+        "body": record.body,
+        "rationale": record.rationale,
+        "attributes": record.attributes,
+    }
+    original = SimpleNamespace(**common, priority="high", tags=("security",))
+    changed_priority = SimpleNamespace(**common, priority="low", tags=("security",))
+    changed_tags = SimpleNamespace(**common, priority="high", tags=("authentication",))
+
+    assert fingerprints.object_content_fingerprint(original) != \
+        fingerprints.object_content_fingerprint(changed_priority)
+    assert fingerprints.object_content_fingerprint(original) != \
+        fingerprints.object_content_fingerprint(changed_tags)
+
+
 def test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation() -> None:
     """REQ -verified-by-> TC and TC -verifies-> REQ are one semantic edge."""
     forward = make_relation()
     inverse = make_relation(
         source="TC-1",
         authored_name="verifies",
         catalog_name="verifies",
         v1_name="verifies",
         target="REQ-1",
         source_role="test",
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_impact.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_impact.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_impact.py	2026-08-26 11:08:49.858273901 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/final-fix/tests/test_impact.py	2026-08-26 21:43:54.172982192 -0300
@@ -139,41 +139,61 @@
     assert changes.get("REQ-1") == "relation-removed"
     doc = next(item for item in report.impacted if item["id"] == "DOC-1")
     assert doc["classification"] == "direct"
     assert doc["relations"] == ["conflicts-with"]
 
 
 def test_impact_rejects_a_configuration_mismatch_without_recompute(tmp_path: Path) -> None:
     """One relation policy must govern the whole traversal."""
     write(tmp_path)
     before = baseline_of(tmp_path)
+    before = {
+        **before,
+        "relations": [
+            {**item, "impactDirection": "none"}
+            if item["authoredName"] == "verified-by"
+            else item
+            for item in before["relations"]
+        ],
+    }
+    text = (tmp_path / "chain.qmd").read_text(encoding="utf-8")
+    (tmp_path / "chain.qmd").write_text(
+        text.replace("verified-by: TC-1\n", ""), encoding="utf-8"
+    )
     (tmp_path / ".quarto-needs.toml").write_text(
         'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
     )
     snapshot, config = snapshot_of(tmp_path)
 
     with pytest.raises(impact.ImpactError):
         impact.analyze(before, snapshot, config)
 
-    assert impact.analyze(before, snapshot, config, recompute=True) is not None
+    report = impact.analyze(before, snapshot, config, recompute=True)
+    test_case = next(item for item in report.impacted if item["id"] == "TC-1")
+    assert test_case["path"] == ["REQ-1", "TC-1"]
+    assert test_case["relations"] == ["verified-by"]
 
 
 def test_impact_rejects_a_reference_date_mismatch_without_recompute(tmp_path: Path) -> None:
     """The reference date is a comparison axis for impact too (spec: impact
     rejects the mismatch)."""
     write(tmp_path)
     before = baseline_of(tmp_path)
     before = {**before, "referenceDate": "1999-01-01"}
+    write(tmp_path, body="The service shall authenticate every administrator.")
     snapshot, config = snapshot_of(tmp_path)
 
     with pytest.raises(impact.ImpactError):
         impact.analyze(before, snapshot, config)
 
-    assert impact.analyze(before, snapshot, config, recompute=True) is not None
+    report = impact.analyze(before, snapshot, config, recompute=True)
+    test_case = next(item for item in report.impacted if item["id"] == "TC-1")
+    assert test_case["path"] == ["REQ-1", "TC-1"]
+    assert test_case["change"] == "modified"
 
 
 def test_impact_rejects_a_diagnostic_baseline(tmp_path: Path) -> None:
     write(tmp_path)
     snapshot, config = snapshot_of(tmp_path)
 
     with pytest.raises(impact.ImpactError):
         impact.analyze({"schemaVersion": "1", "valid": False}, snapshot, config)
```
