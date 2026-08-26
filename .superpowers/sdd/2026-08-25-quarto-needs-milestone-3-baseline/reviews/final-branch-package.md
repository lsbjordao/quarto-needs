# Review package

Snapshot range: `task-1-before` -> `task-11-fix1`

## Files changed (32)

- `ARCHITECTURE.md`
- `CONTRIBUTING.md`
- `Makefile`
- `README.md`
- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md`
- `docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md`
- `examples/book/.quarto-needs/needs.json`
- `examples/book/baselines/quarto-needs.json`
- `pyproject.toml`
- `schemas/baseline-v1.schema.json`
- `schemas/diff-v1.schema.json`
- `schemas/impact-v1.schema.json`
- `src/quarto_needs/analysis.py`
- `src/quarto_needs/baseline.py`
- `src/quarto_needs/cli.py`
- `src/quarto_needs/config.py`
- `src/quarto_needs/diff.py`
- `src/quarto_needs/fingerprints.py`
- `src/quarto_needs/impact.py`
- `src/quarto_needs/rules.py`
- `src/quarto_needs/snapshot.py`
- `tests/test_baseline.py`
- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_diff.py`
- `tests/test_example_project.py`
- `tests/test_fingerprints.py`
- `tests/test_impact.py`
- `tests/test_relations.py`
- `tests/test_snapshot.py`
- `tests/test_v1_contract.py`

## Summary

6844 lines added, 93 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/ARCHITECTURE.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/ARCHITECTURE.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/ARCHITECTURE.md	2026-08-25 15:21:19.825548047 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/ARCHITECTURE.md	2026-08-26 13:14:15.442375470 -0300
@@ -32,25 +32,40 @@
 
 ```text
 QMD files -> DeclarationBatch -> AnalysisResult -> AnalysisSnapshot
                                                -> needs.json v1
                                                -> generated-index.lua
 
 .quarto-needs.toml -> config -> queries / rules / metrics -> report projection
                                                           -> materialized query ID sets
 
 needs.json -> cached Lua indexes -> Pandoc-native cards/views -> HTML/DOCX/PDF
+
+AnalysisSnapshot -> fingerprints -> baselines/quarto-needs.json
+                                          |
+        current AnalysisSnapshot ---------+--> diff  -> DiffReport   -> text|json
+                                          +--> impact -> ImpactReport -> text|json
 ```
 
 Python owns everything up to and including the two generated artifacts;
 Lua only reads the projected `needs.json`.
 
+`diff` and `impact` are pure functions over two snapshots — the baseline's
+stored payload and the current `AnalysisSnapshot` — and return a report
+value; neither touches the filesystem or Quarto. The CLI is the only layer
+that reads a baseline file, writes one, or prints a report. Comparing two
+snapshots is only meaningful when they were produced under the same rules,
+which is why every baseline carries a configuration fingerprint and a
+reference date: those two values are the guards that decide, before any
+object or relation is inspected, which categories of delta the comparison
+is even allowed to report.
+
 Configuration is a second input to the same single analysis pass, never a
 second pass. `cli.build` loads the configuration once, analyzes once, then
 materializes the named queries and the quality report from that one snapshot
 and writes both under `extensions.quartoNeeds`. The dashboard and every
 `query=` filter therefore read numbers and ID sets that Python already decided;
 Lua has no evaluator of its own and cannot drift from the CLI verdict.
 
 ## Build lifecycle
 
 1. Synchronize every canonical extension runtime asset from
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/CONTRIBUTING.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/CONTRIBUTING.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/CONTRIBUTING.md	2026-08-25 15:21:19.825548047 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/CONTRIBUTING.md	2026-08-26 15:13:55.902196766 -0300
@@ -41,20 +41,34 @@
   vector: a frozen list of query sources with their expected ordered results.
   It is the single oracle both the Python evaluator and any future non-Python
   consumer must agree with. Add cases to it when adding grammar; never edit an
   existing expectation to make a failing evaluator pass.
 - `tests/fixtures/views/.quarto-needs/needs.json` is authored by hand, not
   generated. It carries the `extensions.quartoNeeds` projections (relation
   catalog, materialized queries, quality report) that the Lua views read, so
   keep it consistent with what `cli.build` would emit for the same project.
 - Tests must never rewrite a golden or fixture as a side effect of
   running. A mismatch is a failure to investigate, not a file to refresh.
+- `examples/book/baselines/quarto-needs.json` is a checked-in baseline of
+  the Aegis showcase. It must always diff clean against the published book.
+  `tests/test_example_project.py` pins `SOURCE_DATE_EPOCH` to the baseline's
+  own stored `referenceDate` and asserts the JSON diff payload has
+  `"empty": true` and `"notices": []` — exit code alone is not enough,
+  because `diff`'s exit code reflects only gate regressions and stays 0
+  even when an object or relation actually changed. The separate,
+  human-run check is `make diff-example`, which must print `No changes.`.
+  Regenerate the baseline with `make baseline-example` only when a
+  deliberate change to the showcase has been approved, and inspect the
+  resulting `make diff-example` output before committing the new bytes.
+  Never regenerate it just to silence a failing test: a non-empty diff
+  against an unchanged book means a fingerprint is leaking derived data, not
+  that the baseline is stale.
 
 ## Verification commands
 
 Run the full gate before opening a PR:
 
 ```bash
 make setup               # install editable package plus test extra
 make test                # full Python, Lua, and render suite
 make sync-example        # synchronize extension assets and rebuild the graph
 make check-example       # validate the regenerated example graph
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-25 16:49:49.608611780 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-26 14:12:28.914752077 -0300
@@ -67,30 +67,31 @@
 
 Expected: PASS with exactly 2 `jsonschema.RefResolver` `DeprecationWarning` entries. Record the count; Step 4 asserts it reaches zero.
 
 - [ ] **Step 3: Rewrite `envelope_validator` on `referencing`**
 
 Replace the `RefResolver` import and helper in `tests/test_v1_contract.py`:
 
 ```python
 from jsonschema import Draft202012Validator
 from referencing import Registry, Resource
+from referencing.jsonschema import DRAFT202012
 
 
 def envelope_validator() -> Draft202012Validator:
     schema = load_json(SCHEMAS / "needs-envelope-v1.schema.json")
     Draft202012Validator.check_schema(schema)
     registry = Registry().with_resource(
         "https://quarto-needs.dev/schema/needs.schema.json",
         Resource.from_contents(
             load_json(SCHEMAS / "needs.schema.json"),
-            default_specification=Draft202012Validator.META_SCHEMA,
+            default_specification=DRAFT202012,
         ),
     )
     return Draft202012Validator(schema, registry=registry)
 ```
 
 - [ ] **Step 4: Run the contract tests and verify the warnings are gone**
 
 Run: `.venv/bin/python -m pytest tests/test_v1_contract.py -q -W error::DeprecationWarning`
 
 Expected: PASS with no deprecation warning. Promoting the warning to an error proves the migration rather than merely hiding it.
@@ -141,38 +142,68 @@
 
     monkeypatch.setattr(cli, "analyze_project", counted)
 
     cli.main(["--root", str(tmp_path), *arguments])
     assert calls == 1
 
 
 def test_trace_orders_ids_case_insensitively_and_survives_cycles(
     tmp_path: Path, capsys: pytest.CaptureFixture[str]
 ) -> None:
-    """Traversal must terminate on a cycle and sort deterministically."""
+    """Traversal must terminate on a cycle among non-start nodes and sort
+    the reachable set case-insensitively.
+
+    REQ-A (start) --references--> sub-b --references--> SUB-C
+                                     ^-------references-------/
+
+    The B<->C subcycle excludes the start node, so a `seen`-set regression
+    (dropping the visited check while keeping only the `candidate != start`
+    filter) would loop forever bouncing between sub-b and SUB-C. The two
+    downstream ids are also cased so that a plain `sorted()` ("SUB-C" before
+    "sub-b", since uppercase sorts before lowercase in ASCII) disagrees with
+    the casefold-keyed order the CLI is supposed to produce ("sub-b" before
+    "SUB-C").
+    """
     (tmp_path / "cycle.qmd").write_text(
-        "::: {.need #req-b type=need status=draft}\n"
-        "references: REQ-A\n"
+        "::: {.need #REQ-A type=need status=draft}\n"
+        "references: sub-b\n"
+        "\n## A\nA body.\n:::\n"
+        "\n"
+        "::: {.need #sub-b type=need status=draft}\n"
+        "references: SUB-C\n"
         "\n## B\nB body.\n:::\n"
         "\n"
-        "::: {.need #REQ-A type=need status=draft}\n"
-        "references: req-b\n"
-        "\n## A\nA body.\n:::\n",
+        "::: {.need #SUB-C type=need status=draft}\n"
+        "references: sub-b\n"
+        "\n## C\nC body.\n:::\n",
         encoding="utf-8",
     )
 
     assert cli.main(["--root", str(tmp_path), "trace", "REQ-A"]) == 0
 
     output = capsys.readouterr().out
-    assert "req-b" in output
+    assert output == (
+        "Upstream:\n"
+        "Downstream:\n"
+        "  sub-b\n"
+        "  SUB-C\n"
+    )
 ```
 
+> **Plan correction.** The first version of this probe used a two-node cycle
+> `REQ-A <-> req-b`. That test passed for the wrong reason: when one node of
+> the cycle is the traversal's start, `_reachable`'s separate
+> `candidate != start` filter already excludes the only back-edge, so the
+> visited set is never load-bearing and deleting it would not hang the test.
+> The subcycle must exclude `start`, and the reachable set needs two
+> differently-cased IDs or the casefold sort key goes untested.
+
 - [ ] **Step 8: Run the probes**
 
 Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k "invalid_input_still_runs or survives_cycles"`
 
 Expected: PASS. If the cycle test hangs, traversal lacks a visited set — that is a real defect; fix `cli` traversal to track visited IDs before continuing.
 
 - [ ] **Step 9: Run the full suite**
 
 Run: `.venv/bin/python -m pytest -q`
 
@@ -218,74 +249,106 @@
         '[types.test-case]\nrequired-attributes = ["tags"]\n',
         encoding="utf-8",
     )
     (second / ".quarto-needs.toml").write_text(
         'profile = "strict"\n'
         '[types.test-case]\nrequired-attributes = ["tags"]\n'
         '[types.functional-requirement]\nrequired-attributes = ["priority", "tags"]\n',
         encoding="utf-8",
     )
 
-    assert load_config(first).canonical_document() == load_config(second).canonical_document()
+    # Compare the serialized form: dict equality ignores key order, so it would
+    # hold even with every sorted() call deleted.
+    assert json.dumps(load_config(first).canonical_document()) == json.dumps(
+        load_config(second).canonical_document()
+    )
 
 
 def test_canonical_document_excludes_presence_and_path(tmp_path: Path) -> None:
     """Presence controls artifact projection, not graph semantics."""
     (tmp_path / ".quarto-needs.toml").write_text("", encoding="utf-8")
 
     from_file = load_config(tmp_path).canonical_document()
     embedded = embedded_defaults().canonical_document()
 
     assert from_file == embedded
     assert "present" not in from_file
     assert not any("quarto-needs.toml" in str(value) for value in from_file.values())
 
 
 def test_canonical_document_reflects_every_policy_section(tmp_path: Path) -> None:
     """A change in any supported section must change the canonical document."""
     (tmp_path / ".quarto-needs.toml").write_text(
         'profile = "advisory"\n'
+        '[types.functional-requirement]\nrequired-attributes = ["priority"]\n'
         '[relations."verified-by"]\nallowed-target-types = ["test-case"]\n'
         '[governance]\ntest-types = ["test-case"]\n'
         '[rules.REQ011]\nenabled = true\n'
         '[queries.q]\nall = [{ field = "status", op = "eq", value = "approved" }]\n'
         '[gates]\nmax-errors = 3\n',
         encoding="utf-8",
     )
 
     document = load_config(tmp_path).canonical_document()
 
     assert document["profile"] == "advisory"
+    assert document["types"]["functional-requirement"]["required-attributes"] == ["priority"]
     assert document["relations"]["verified-by"]["allowed-target-types"] == ["test-case"]
     assert document["governance"]["test-types"] == ["test-case"]
     assert document["rules"]["REQ011"]["enabled"] is True
     assert "q" in document["queries"]
     assert document["gates"]["max-errors"] == 3
 ```
 
+```python
+def test_canonical_document_rejects_a_non_json_query_value(tmp_path: Path) -> None:
+    """A bare TOML date must fail as configuration, not as a raw TypeError."""
+    (tmp_path / ".quarto-needs.toml").write_text(
+        '[queries.q]\nall = [{ field = "status", op = "eq", value = 2026-01-01 }]\n',
+        encoding="utf-8",
+    )
+
+    with pytest.raises(ConfigurationError):
+        load_config(tmp_path).canonical_document()
+```
+
 - [ ] **Step 2: Run them and verify they fail**
 
 Run: `.venv/bin/python -m pytest tests/test_config.py -q -k canonical_document`
 
 Expected: FAIL with `AttributeError: 'NeedsConfig' object has no attribute 'canonical_document'`.
 
 - [ ] **Step 3: Implement `canonical_document`**
 
 Add as a method on `NeedsConfig` in `src/quarto_needs/config.py`. Every container is converted to a plain, sorted, JSON-safe structure so the fingerprint hashes one spelling per policy:
 
 ```python
     def canonical_document(self) -> dict[str, object]:
         """The single canonical form the configuration fingerprint hashes.
 
-        Excludes `present` and the file path: presence controls artifact
-        projection, not graph semantics, and the path is environment-specific.
+        Excludes `present`, which controls artifact projection rather than
+        graph semantics. The configuration file's path is never stored on this
+        object, so there is nothing to exclude there.
         """
+        # tomllib turns a bare `2026-01-01` into a `date`, which `freeze_json`
+        # rejects. Query grammar validation only runs later, in
+        # `materialize_queries`, so without this the fingerprint would raise an
+        # uncontrolled TypeError instead of the documented exit code 2.
+        try:
+            queries = {
+                name: thaw_json(freeze_json(dict(source)))
+                for name, source in sorted(self.named_query_sources.items())
+            }
+        except TypeError as error:
+            raise _fail(
+                f"[queries] contains a value that is not valid JSON: {error}"
+            ) from error
         return {
             "profile": self.profile,
             "types": {
                 name: {"required-attributes": list(self.required_attributes[name])}
                 for name in sorted(self.required_attributes)
             },
             "relations": {
                 name: {
                     "allowed-source-types": list(policy.allowed_source_types),
                     "allowed-target-types": list(policy.allowed_target_types),
@@ -298,24 +361,21 @@
                 "test-types": list(self.test_types),
                 "risk-types": list(self.risk_types),
                 "successful-test-statuses": list(self.successful_test_statuses),
                 "ineffective-endpoint-statuses": list(self.ineffective_endpoint_statuses),
                 "expiry-attribute": self.expiry_attribute,
             },
             "rules": {
                 code: {"enabled": setting.enabled, "severity": setting.severity}
                 for code, setting in sorted(self.rule_settings.items())
             },
-            "queries": {
-                name: thaw_json(freeze_json(dict(source)))
-                for name, source in sorted(self.named_query_sources.items())
-            },
+            "queries": queries,
             "gates": {
                 "scope": self.gates.scope,
                 "max-errors": self.gates.max_errors,
                 "require-risk-mitigation": self.gates.require_risk_mitigation,
                 "min-implementation-trace": self.gates.min_implementation_trace,
                 "min-implementation-effective": self.gates.min_implementation_effective,
                 "min-verification-trace": self.gates.min_verification_trace,
                 "min-verification-successful": self.gates.min_verification_successful,
                 "min-evidence": self.gates.min_evidence,
             },
@@ -431,26 +491,30 @@
     moved = make_object(locations=(LocationRecord("b.qmd", 900, "REQ-1"),))
 
     assert fingerprints.object_content_fingerprint(make_object()) == \
         fingerprints.object_content_fingerprint(moved)
 
 
 def test_object_fingerprint_changes_with_every_authored_field() -> None:
     """Each field the spec names must actually participate."""
     original = fingerprints.object_content_fingerprint(make_object())
     for field, value in (
+        ("id", "REQ-2"),
         ("type", "system-requirement"),
         ("title", "Other"),
         ("status", "draft"),
         ("body", "Different body."),
         ("rationale", "Different rationale."),
+        # Vary priority and tags separately so each computed property is proven
+        # to participate on its own.
         ("attributes", {"priority": "low", "tags": "security"}),
+        ("attributes", {"priority": "high", "tags": "authentication"}),
     ):
         assert fingerprints.object_content_fingerprint(make_object(**{field: value})) != original, field
 
 
 def test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation() -> None:
     """REQ -verified-by-> TC and TC -verifies-> REQ are one semantic edge."""
     forward = make_relation()
     inverse = make_relation(
         source="TC-1",
         authored_name="verifies",
@@ -466,20 +530,21 @@
         fingerprints.relation_semantic_fingerprint(inverse)
     assert fingerprints.relation_authored_fingerprint(forward) != \
         fingerprints.relation_authored_fingerprint(inverse)
 
 
 def test_semantic_relation_fingerprint_changes_with_family_and_endpoints() -> None:
     original = fingerprints.relation_semantic_fingerprint(make_relation())
 
     assert fingerprints.relation_semantic_fingerprint(make_relation(semantic_family="evidence")) != original
     assert fingerprints.relation_semantic_fingerprint(make_relation(target="TC-2")) != original
+    assert fingerprints.relation_semantic_fingerprint(make_relation(source="REQ-2")) != original
     assert fingerprints.relation_semantic_fingerprint(make_relation(attributes={"note": "x"})) != original
 
 
 def test_graph_fingerprint_is_order_independent_and_configuration_sensitive() -> None:
     """Reordering declarations is not a change; changing policy is."""
     objects = [make_object(), make_object(id="REQ-2")]
     relations = [make_relation(), make_relation(target="TC-2")]
     configuration = fingerprints.configuration_fingerprint(
         embedded_defaults(), relation_catalog_version="1"
     )
@@ -853,22 +918,22 @@
 from quarto_needs.config import load_config
 
 ROOT = Path(__file__).resolve().parents[1]
 SCHEMA = ROOT / "schemas" / "baseline-v1.schema.json"
 
 
 def write_project(root: Path) -> None:
     (root / "needs.qmd").write_text(
         "::: {.need #REQ-1 type=functional-requirement status=approved priority=high}\n"
         "verified-by: TC-1\n"
+        "rationale: Protect data.\n"
         "\n## Authenticate\nThe service shall authenticate.\n"
-        "\n### Rationale\nProtect data.\n"
         ":::\n"
         "\n"
         "::: {.need #TC-1 type=test-case status=passed}\n"
         "\n## Login test\nSigns a user in.\n"
         ":::\n",
         encoding="utf-8",
     )
 
 
 def validator() -> Draft202012Validator:
@@ -1223,20 +1288,21 @@
     assert cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"]) == 0
 
     payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
     assert payload["valid"] is False
     assert payload["declarations"]
 
 
 def test_baseline_inspect_reports_both_variants(tmp_path: Path, capsys) -> None:
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     destination = str(tmp_path / "baselines" / "quarto-needs.json")
 
     assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination, "--format", "json"]) == 0
     summary = json.loads(capsys.readouterr().out)
     assert summary["valid"] is True
     assert summary["objects"] == 3
     assert summary["referenceDate"]
 
     assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination]) == 0
     assert "objects" in capsys.readouterr().out
@@ -1404,21 +1470,21 @@
 
 from pathlib import Path
 
 import pytest
 
 from quarto_needs import baseline, diff
 from quarto_needs.analysis import analyze_project
 from quarto_needs.config import load_config
 
 REQUIREMENT = (
-    "::: {{.need #REQ-1 type=functional-requirement status=approved priority=high}}\n"
+    "::: {{.need #REQ-1 type=system-requirement status=approved priority=high}}\n"
     "verified-by: TC-1\n"
     "\n## Authenticate\n{body}\n"
     "\n### Rationale\nProtect data.\n"
     ":::\n"
 )
 TEST_CASE = "::: {.need #TC-1 type=test-case status=passed}\n\n## Login\nSigns in.\n:::\n"
 
 
 def write(root: Path, *, body: str = "The service shall authenticate.", order: str = "requirement-first", file: str = "needs.qmd") -> None:
     for existing in root.glob("*.qmd"):
@@ -1497,35 +1563,38 @@
     assert report.relocated == ()
 
 
 def test_added_and_removed_objects_are_classified(tmp_path: Path) -> None:
     write(tmp_path)
     before = baseline_of(tmp_path)
     (tmp_path / "extra.qmd").write_text(
         "::: {.need #REQ-2 type=functional-requirement status=draft}\n\n## Second\nBody.\n:::\n",
         encoding="utf-8",
     )
-    (tmp_path / "needs.qmd").write_text(REQUIREMENT.format(body="The service shall authenticate."), encoding="utf-8")
+    (tmp_path / "needs.qmd").write_text(
+        REQUIREMENT.format(body="The service shall authenticate.").replace("verified-by: TC-1\n", ""),
+        encoding="utf-8",
+    )
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     assert report.added_objects == ("REQ-2",)
     assert report.removed_objects == ("TC-1",)
 
 
 def test_a_changed_id_is_removal_plus_addition(tmp_path: Path) -> None:
     """Rename detection is deliberately excluded; it is inherently heuristic."""
     write(tmp_path)
     before = baseline_of(tmp_path)
     (tmp_path / "needs.qmd").write_text(
-        REQUIREMENT.format(body="The service shall authenticate.").replace("#REQ-1", "#REQ-9").replace("verified-by: TC-1", "verified-by: TC-1")
+        REQUIREMENT.format(body="The service shall authenticate.").replace("#REQ-1", "#REQ-9")
         + "\n" + TEST_CASE,
         encoding="utf-8",
     )
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     assert "REQ-9" in report.added_objects
     assert "REQ-1" in report.removed_objects
     assert report.modified == ()
@@ -1570,20 +1639,52 @@
     before = baseline_of(tmp_path)
     before = {**before, "referenceDate": "1999-01-01"}
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config, recompute=True)
 
     assert report.notices == ()
     assert report.recomputed is True
 
 
+def test_recompute_does_not_manufacture_derived_deltas_from_a_config_change(tmp_path: Path) -> None:
+    """The baseline stores its derived results; they cannot be re-derived, so a
+    config-only change must stay silent even under recompute.
+
+    REQ-2 is approved but unverified, so verification coverage is 1 of 2 (50%).
+    The baseline is taken under the default configuration (no verification
+    gate); only then does the configuration grow a 100.0 threshold. Authored
+    content never moves — any derived delta is manufactured by the config edit.
+    """
+    write(tmp_path)
+    (tmp_path / "extra.qmd").write_text(
+        "::: {.need #REQ-2 type=system-requirement status=approved priority=low}\n"
+        "\n## Second\nSecond body.\n"
+        "\n### Rationale\nSecond why.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        "[gates]\nmin-verification-trace = 100.0\n", encoding="utf-8"
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config, recompute=True)
+
+    assert report.notices == ()
+    assert report.modified == ()
+    assert report.gate_regressions == ()
+    assert report.metric_deltas == ()
+    assert report.findings_added == ()
+
+
 def test_configuration_change_still_compares_authored_relations(tmp_path: Path) -> None:
     """Authored comparison keeps running; only the derived deltas stop."""
     write(tmp_path)
     before = baseline_of(tmp_path)
     (tmp_path / ".quarto-needs.toml").write_text('profile = "strict"\n', encoding="utf-8")
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     assert "configuration-changed" in report.notices
@@ -1870,40 +1971,40 @@
 
 Append to `tests/test_diff.py`:
 
 ```python
 def test_new_findings_are_reported_when_the_configuration_is_stable(tmp_path: Path) -> None:
     """A warning that appears with no policy change is a real regression."""
     write(tmp_path)
     before = baseline_of(tmp_path)
     # Drop the rationale: REQ002 fires, and nothing about the policy moved.
     (tmp_path / "needs.qmd").write_text(
-        "::: {.need #REQ-1 type=functional-requirement status=approved priority=high}\n"
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
         "verified-by: TC-1\n"
         "\n## Authenticate\nThe service shall authenticate.\n"
         ":::\n" + "\n" + TEST_CASE,
         encoding="utf-8",
     )
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     assert any(item["code"] == "REQ002" for item in report.findings_added)
     assert report.notices == ()
 
 
 def test_metric_deltas_name_the_scope_and_strength(tmp_path: Path) -> None:
     write(tmp_path)
     before = baseline_of(tmp_path)
     # Remove the verification edge: verification coverage drops.
     (tmp_path / "needs.qmd").write_text(
-        "::: {.need #REQ-1 type=functional-requirement status=approved priority=high}\n"
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
         "\n## Authenticate\nThe service shall authenticate.\n"
         "\n### Rationale\nProtect data.\n"
         ":::\n" + "\n" + TEST_CASE,
         encoding="utf-8",
     )
     snapshot, config = snapshot_of(tmp_path)
 
     report = diff.compare(before, snapshot, config)
 
     verification = [
@@ -2058,48 +2159,52 @@
         raise DiffError(
             "This baseline is a diagnostic artifact (valid: false) and cannot be compared; "
             "use `baseline inspect` to read it"
         )
 
     current_configuration = snapshot.configuration_fingerprint
     baseline_configuration = str(baseline_payload.get("configurationFingerprint", ""))
     baseline_date = str(baseline_payload.get("referenceDate", ""))
 
     notices: list[str] = []
+    configuration_differs = baseline_configuration != current_configuration
+    date_differs = baseline_date != snapshot.reference_date
     if not recompute:
-        if baseline_configuration != current_configuration:
+        if configuration_differs:
             notices.append("configuration-changed")
-        if baseline_date != snapshot.reference_date:
+        if date_differs:
             notices.append("reference-date-changed")
 
     added, removed, modified, relocated = _classify_objects(
         _baseline_objects(baseline_payload),
         {record.id: _current_object(record) for record in snapshot.objects},
     )
 
     baseline_relations = list(baseline_payload.get("relations", []))
     if recompute:
         baseline_relations = _recomputed_relations(baseline_relations)
     # A catalog change can move families and roles, so semantic fingerprints
     # from the two sides stop being comparable. Fall back to authored tuples,
     # which is exactly what the spec prescribes for this case.
     relation_key = (
         "authoredFingerprint" if "configuration-changed" in notices else "semanticFingerprint"
     )
     added_relations, removed_relations, representation = _classify_relations(
         baseline_relations, _current_relations(snapshot), key=relation_key
     )
 
-    # Derived results were computed under different rules or a different date,
-    # so their deltas describe the inputs, not the project. Suppress them and
-    # say why; `--recompute-with current` is the way to get them back.
-    derived_suppressed = bool(notices)
+    # Derived results are stored in the baseline, never re-derived, so they are
+    # comparable only when both sides were produced under the same rules and
+    # the same reference date. `recompute` re-resolves authored relations
+    # through the current catalog; it cannot make stored findings, metrics, or
+    # gates comparable, so their deltas stay suppressed silently there.
+    derived_suppressed = configuration_differs or date_differs
     if derived_suppressed:
         findings_added: tuple[dict[str, object], ...] = ()
         findings_removed: tuple[dict[str, object], ...] = ()
         metric_deltas: tuple[dict[str, object], ...] = ()
         gate_regressions: tuple[dict[str, object], ...] = ()
     else:
         current_report = report_from_snapshot(snapshot, config).to_dict()
         baseline_report = baseline_payload.get("report", {})
         findings_added, findings_removed = _classify_findings(
             baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
@@ -2242,34 +2347,36 @@
 - [ ] **Step 2: Write the failing CLI tests**
 
 Add to `tests/test_cli.py`:
 
 ```python
 def test_diff_against_an_unchanged_project_is_empty_and_exits_zero(
     tmp_path: Path, capsys
 ) -> None:
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     destination = str(tmp_path / "baselines" / "quarto-needs.json")
 
     assert cli.main(["--root", str(tmp_path), "diff", destination, "--format", "json"]) == 0
 
     payload = json.loads(capsys.readouterr().out)
     assert payload["empty"] is True
     assert payload["notices"] == []
 
 
 def test_diff_validates_against_the_diff_schema(tmp_path: Path, capsys) -> None:
     from jsonschema import Draft202012Validator
 
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json"])
     payload = json.loads(capsys.readouterr().out)
 
     schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "diff-v1.schema.json").read_text(encoding="utf-8"))
     Draft202012Validator.check_schema(schema)
     Draft202012Validator(schema).validate(payload)
 
 
 def test_diff_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
     write_valid_project(tmp_path)
@@ -2299,20 +2406,21 @@
 
 
 def test_diff_reports_a_missing_baseline_as_usage_error(tmp_path: Path) -> None:
     write_valid_project(tmp_path)
     assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "absent.json")]) == 2
 
 
 def test_diff_recompute_with_current_clears_notices(tmp_path: Path, capsys) -> None:
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     destination = tmp_path / "baselines" / "quarto-needs.json"
     payload = json.loads(destination.read_text(encoding="utf-8"))
     payload["referenceDate"] = "1999-01-01"
     destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
 
     cli.main(["--root", str(tmp_path), "diff", str(destination), "--format", "json"])
     assert "reference-date-changed" in json.loads(capsys.readouterr().out)["notices"]
 
     cli.main([
         "--root", str(tmp_path), "diff", str(destination),
@@ -2332,34 +2440,34 @@
 In `main`, after the `baseline` parser block:
 
 ```python
     diff_parser = sub.add_parser("diff", help="Compare a baseline against the current graph")
     diff_parser.add_argument("baseline")
     diff_parser.add_argument("--format", choices=("text", "json"), default="text")
     diff_parser.add_argument(
         "--recompute-with",
         choices=("current",),
         dest="recompute_with",
-        help="Re-evaluate both sides under the current configuration and reference date",
+        help="Re-resolve the baseline's relations under the current configuration and reference date",
     )
 ```
 
 Add `from . import diff as diff_module` to the imports.
 
 - [ ] **Step 5: Implement the handler**
 
 Add above `main`:
 
 ```python
 def _print_diff_text(report) -> None:
     for notice in report.notices:
-        print(f"[notice] {notice}: derived deltas suppressed; pass --recompute-with current to compare them")
+        print(f"[notice] {notice}: derived deltas suppressed; both sides must share configuration and reference date to compare them")
     if report.is_empty():
         print("No changes.")
         return
     for object_id in report.added_objects:
         print(f"+ object {object_id}")
     for object_id in report.removed_objects:
         print(f"- object {object_id}")
     for item in report.modified:
         print(f"~ object {item['id']} ({', '.join(item['fields'])})")
     for item in report.relocated:
@@ -2473,28 +2581,35 @@
 
 CHAIN = """::: {{.need #STK-1 type=stakeholder-need status=approved priority=high}}
 
 ## Stakeholder
 Needs secure access.
 :::
 
 ::: {{.need #REQ-1 type=functional-requirement status=approved priority=high}}
 derives-from: STK-1
 verified-by: TC-1
+conflicts-with: DOC-1
 
 ## Authenticate
 {body}
 
 ### Rationale
 Protect data.
 :::
 
+::: {{.need #DOC-1 type=need status=draft}}
+
+## Manual
+Login manual.
+:::
+
 ::: {{.need #TC-1 type=test-case status=passed}}
 
 ## Login
 Signs in.
 :::
 """
 
 
 def write(root: Path, *, body: str = "The service shall authenticate.", keep_test: bool = True) -> None:
     text = CHAIN.format(body=body)
@@ -2555,48 +2670,85 @@
     assert report.impacted
     for item in report.impacted:
         assert item["path"][0] == item["origin"]
         assert item["path"][-1] == item["id"]
         assert len(item["path"]) == item["distance"] + 1
         assert item["classification"] in {"direct", "transitive"}
         assert "priority" in item
 
 
 def test_removing_a_node_still_explains_its_neighbors(tmp_path: Path) -> None:
-    """Union traversal is why a removed edge remains explainable."""
+    """Union traversal is why a removed node and its removed edges stay explainable.
+
+    `verified-by` propagates from requirement to test, so the removed test case
+    cannot reach the requirement it verified; the removal surfaces instead as
+    two origins — the removed node and the requirement that lost the edge.
+    """
     write(tmp_path)
     before = baseline_of(tmp_path)
     write(tmp_path, keep_test=False)
     snapshot, config = snapshot_of(tmp_path)
 
     report = impact.analyze(before, snapshot, config)
 
-    assert any(item["id"] == "TC-1" and item["change"] == "removed" for item in report.origins)
-    impacted = {item["id"] for item in report.impacted}
-    assert "REQ-1" in impacted
+    changes = {item["id"]: item["change"] for item in report.origins}
+    assert changes.get("TC-1") == "removed"
+    assert changes.get("REQ-1") == "relation-removed"
+
+
+def test_removal_reaches_neighbors_through_baseline_only_edges(tmp_path: Path) -> None:
+    """A dropped `conflicts-with` still propagates: the edge exists only in the
+    baseline, so without the union adjacency DOC-1 would be unreachable."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    text = (tmp_path / "chain.qmd").read_text(encoding="utf-8").replace("conflicts-with: DOC-1\n", "")
+    (tmp_path / "chain.qmd").write_text(text, encoding="utf-8")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    changes = {item["id"]: item["change"] for item in report.origins}
+    assert changes.get("REQ-1") == "relation-removed"
+    doc = next(item for item in report.impacted if item["id"] == "DOC-1")
+    assert doc["classification"] == "direct"
+    assert doc["relations"] == ["conflicts-with"]
 
 
 def test_impact_rejects_a_configuration_mismatch_without_recompute(tmp_path: Path) -> None:
     """One relation policy must govern the whole traversal."""
     write(tmp_path)
     before = baseline_of(tmp_path)
     (tmp_path / ".quarto-needs.toml").write_text(
         'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
     )
     snapshot, config = snapshot_of(tmp_path)
 
     with pytest.raises(impact.ImpactError):
         impact.analyze(before, snapshot, config)
 
     assert impact.analyze(before, snapshot, config, recompute=True) is not None
 
 
+def test_impact_rejects_a_reference_date_mismatch_without_recompute(tmp_path: Path) -> None:
+    """The reference date is a comparison axis for impact too (spec: impact
+    rejects the mismatch)."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    before = {**before, "referenceDate": "1999-01-01"}
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(impact.ImpactError):
+        impact.analyze(before, snapshot, config)
+
+    assert impact.analyze(before, snapshot, config, recompute=True) is not None
+
+
 def test_impact_rejects_a_diagnostic_baseline(tmp_path: Path) -> None:
     write(tmp_path)
     snapshot, config = snapshot_of(tmp_path)
 
     with pytest.raises(impact.ImpactError):
         impact.analyze({"schemaVersion": "1", "valid": False}, snapshot, config)
 ```
 
 - [ ] **Step 2: Run them and verify they fail**
 
@@ -2710,27 +2862,33 @@
     baseline_payload: Mapping[str, object],
     snapshot: AnalysisSnapshot,
     config: NeedsConfig,
     *,
     recompute: bool = False,
 ) -> ImpactReport:
     if not baseline_payload.get("valid", False):
         raise ImpactError(
             "This baseline is a diagnostic artifact (valid: false) and cannot be traversed"
         )
-    if not recompute and str(
-        baseline_payload.get("configurationFingerprint", "")
-    ) != snapshot.configuration_fingerprint:
-        raise ImpactError(
-            "The baseline was produced under a different configuration; "
-            "pass --recompute-with current so one relation policy governs the traversal"
-        )
+    if not recompute:
+        if str(
+            baseline_payload.get("configurationFingerprint", "")
+        ) != snapshot.configuration_fingerprint:
+            raise ImpactError(
+                "The baseline was produced under a different configuration; "
+                "pass --recompute-with current so one relation policy governs the traversal"
+            )
+        if str(baseline_payload.get("referenceDate", "")) != snapshot.reference_date:
+            raise ImpactError(
+                "The baseline was produced under a different reference date; "
+                "pass --recompute-with current to traverse under the current date"
+            )
 
     report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
     origins = _origins(report)
     adjacency = _union_edges(baseline_payload.get("relations", []), snapshot)
     baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
     origin_ids = {str(item["id"]) for item in origins}
 
     impacted: dict[tuple[str, str], dict[str, object]] = {}
     for origin in origins:
         start = str(origin["id"])
@@ -2858,20 +3016,21 @@
 - [ ] **Step 2: Write the failing CLI tests**
 
 Add to `tests/test_cli.py`:
 
 ```python
 def test_impact_validates_against_the_impact_schema(tmp_path: Path, capsys) -> None:
     from jsonschema import Draft202012Validator
 
     write_valid_project(tmp_path)
     cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
     (tmp_path / "needs.qmd").write_text(
         (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace("First body.", "Changed body."),
         encoding="utf-8",
     )
 
     assert cli.main([
         "--root", str(tmp_path), "impact",
         str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json",
     ]) == 0
     payload = json.loads(capsys.readouterr().out)
@@ -2924,21 +3083,21 @@
 In `main`, after the `diff` parser block:
 
 ```python
     impact_parser = sub.add_parser("impact", help="Explain what a baseline's changes reach")
     impact_parser.add_argument("baseline")
     impact_parser.add_argument("--format", choices=("text", "json"), default="text")
     impact_parser.add_argument(
         "--recompute-with",
         choices=("current",),
         dest="recompute_with",
-        help="Re-evaluate both sides under the current configuration and reference date",
+        help="Re-resolve the baseline's relations under the current configuration and reference date",
     )
 ```
 
 Add `from . import impact as impact_module` to the imports.
 
 - [ ] **Step 5: Implement the handler**
 
 Add above `main`:
 
 ```python
@@ -3063,25 +3222,31 @@
     import json as _json
     import shutil as _shutil
     from quarto_needs import cli
 
     project = tmp_path / "book"
     _shutil.copytree(ROOT / "examples/book", project, ignore=_shutil.ignore_patterns("_book", ".quarto"))
     baseline_path = project / "baselines" / "quarto-needs.json"
 
     system = project / "requirements" / "system.qmd"
     system.write_text(
-        system.read_text(encoding="utf-8").replace("verified-by: IAM-TC-001", "", 1),
+        system.read_text(encoding="utf-8").replace('verified-by="IAM-TC-001"', "", 1),
         encoding="utf-8",
     )
 
-    assert cli.main(["--root", str(project), "impact", str(baseline_path), "--format", "json"]) == 0
+    # The checked-in baseline predates the run day, and impact (per spec)
+    # rejects a reference-date mismatch; the documented escape hatch keeps the
+    # showcase runnable on any date.
+    assert cli.main([
+        "--root", str(project), "impact", str(baseline_path),
+        "--recompute-with", "current", "--format", "json",
+    ]) == 0
 ```
 
 Note: this last test reads the JSON only to prove the command exits 0 on a real project; asserting exact reachability is already covered by `tests/test_impact.py`.
 
 - [ ] **Step 2: Run them and verify they fail**
 
 Run: `.venv/bin/python -m pytest tests/test_example_project.py -q -k baseline`
 
 Expected: FAIL — `examples/book/baselines/quarto-needs.json` does not exist yet.
 
@@ -3090,21 +3255,21 @@
 In `Makefile`, extend `.PHONY` with `baseline-example diff-example impact-example` and append:
 
 ```make
 baseline-example:
 	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book baseline create --force
 
 diff-example:
 	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book diff examples/book/baselines/quarto-needs.json
 
 impact-example:
-	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json
+	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json --recompute-with current
 ```
 
 - [ ] **Step 4: Create the checked-in baseline**
 
 Run:
 
 ```bash
 make sync-example
 make baseline-example
 make diff-example
@@ -3120,21 +3285,21 @@
 
 - [ ] **Step 6: Document the commands in the README**
 
 Extend the `## Commands` block with the three new entries and add a `### Baseline, diff, and impact` section after the configuration reference. It must state:
 
 - `baseline create` writes `baselines/quarto-needs.json`, refuses to overwrite without `--force`, and refuses a structurally invalid project unless `--allow-invalid` is given;
 - `--allow-invalid` produces a diagnostic artifact marked `valid: false` that only `baseline inspect` accepts — `diff` and `impact` reject it, because duplicate IDs make comparison ambiguous;
 - `diff` classifies added/removed objects, modifications by field, added/removed relations, relocation, and findings/metrics/gate regressions; a changed ID is reported as a removal plus an addition because rename detection is heuristic and deliberately excluded;
 - **relocation is keyed on the declaring file** — a line-only shift produces no record;
 - an authored alias flip (`verified-by` to `verifies`) that preserves endpoint roles is a representation change, never a relation addition or removal;
-- the two guards: a changed configuration fingerprint or reference date emits `configuration-changed` / `reference-date-changed` and suppresses derived deltas, and `--recompute-with current` re-evaluates both sides;
+- the two guards: a changed configuration fingerprint or reference date emits `configuration-changed` / `reference-date-changed` and suppresses derived deltas; `--recompute-with current` re-resolves the baseline's authored relations through the current catalog so semantic comparison is valid again, while derived deltas stay suppressed until both sides are produced under the same configuration and reference date;
 - `impact` traverses the union of both graphs so removed nodes stay explainable, follows each relation's catalog `impactDirection`, and gives every result an explicit path, distance, classification, and priority — there is no risk score;
 - determinism means byte-identical output for a fixed configuration **and** a fixed reference date; `SOURCE_DATE_EPOCH` fixes the latter.
 
 - [ ] **Step 7: Update the pipeline diagram**
 
 In `ARCHITECTURE.md`, extend the canonical pipeline block:
 
 ```text
 AnalysisSnapshot -> fingerprints -> baselines/quarto-needs.json
                                           |
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md	2026-08-26 14:52:55.992058367 -0300
@@ -0,0 +1,764 @@
+# Quarto-Needs Milestone 4A Exporters and CI Implementation Plan
+
+> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
+
+**Goal:** Deliver the CSV, SARIF, JUnit, and Markdown exporters behind `export --format`, close the exit-code-3 gap carried from the Milestone 3 whole-branch review, and split CI into the spec's `core`/`quarto`/`quality` jobs with preserved artifacts and a step summary.
+
+**Architecture:** Every exporter is a pure function from the existing single-pass analysis products (`AnalysisSnapshot`, `QualityReport`, optionally a loaded baseline plus `DiffReport`/`ImpactReport`) to a deterministic string, written atomically through `export._write_atomic_text`. The CLI remains the only filesystem layer and still analyzes exactly once per invocation. The Markdown summary may load a baseline and run the pure `diff`/`impact` functions over the already-held snapshot; loading a baseline never analyzes.
+
+**Tech Stack:** Python 3.10+, standard-library `csv`/`xml.etree`/`hashlib`/`json`, pytest, `jsonschema` (already a test dependency), `pyyaml` added to the `test` extra only (workflow structural tests); no new runtime dependency.
+
+**Spec:** `docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md` — sections "Exporters", "CI design", "CLI and failure semantics", and the gate under "### Milestone 4".
+
+## Global Constraints
+
+- Do not add a runtime dependency. `pyyaml` enters the `test` optional dependency group only.
+- One analysis per command invocation. `export` in every format calls `analyze_project` exactly once; loading a baseline for the Markdown summary never analyzes.
+- `export --format json` (and `export` with no `--format`) must stay byte-identical to the current v1 projection for an unchanged project; a golden hash test locks this.
+- Exit codes are stable: `0` gates passed; `1` validation or policy failure; `2` invalid usage or configuration; `3` operational I/O or serialization failure. Export artifacts are still written when policy returns exit 1; operational failures return 3 and name the artifact that could not be produced.
+- Exporter output is deterministic for a fixed project, configuration, and reference date: sorted rows/entries, no wall-clock timestamps; any timestamp comes from `SOURCE_DATE_EPOCH` with a `1970-01-01T00:00:00Z` fallback.
+- All generated files are written atomically through `export._write_atomic_text`; CSV's three files are written to a directory created on demand.
+- Preserve every existing signature and documented behavior, including the v1 JSON schema and `extensions.quartoNeeds` projection.
+- The workspace has no `.git` metadata. Do not initialize Git. Every task ends with a conditional checkpoint that records a commit only when the executor is inside a Git worktree.
+- Do not stop or restart the preview server listening on `127.0.0.1:8777`.
+- Vendored assets (the SARIF 2.1.0 JSON Schema) record upstream URL, version, license notice, and SHA-256 checksum in a `VENDORED.md` next to the asset; a test verifies the checksum so an offline build cannot drift.
+
+## File Map
+
+| Area | Files | Responsibility after Milestone 4A |
+|---|---|---|
+| Exit-code hardening | `src/quarto_needs/cli.py`, `README.md` | `scan`/`export` write failures become exit 3; exit-code table documents 3; impact's rejection semantics documented. |
+| Exporter plumbing | `src/quarto_needs/cli.py` | `export --format <json\|csv\|sarif\|junit\|markdown>`, optional `--baseline`, artifacts preserved on policy failure. |
+| CSV | `src/quarto_needs/exporters/__init__.py`, `src/quarto_needs/exporters/csv_export.py`, `tests/test_export_csv.py` | `objects.csv`, `relations.csv`, `findings.csv` with formula-injection protection. |
+| SARIF | `src/quarto_needs/exporters/sarif_export.py`, `schemas/vendor/sarif-2.1.0/sarif-schema.json`, `schemas/vendor/sarif-2.1.0/VENDORED.md`, `tests/test_export_sarif.py` | Findings as SARIF 2.1.0 (GitHub-supported subset), schema-validated. |
+| JUnit | `src/quarto_needs/exporters/junit_export.py`, `tests/test_export_junit.py` | One test case per evaluated quality gate; warnings per policy. |
+| Markdown | `src/quarto_needs/exporters/markdown_export.py`, `tests/test_export_markdown.py` | CI summary: changes, coverage deltas, failed gates, high/critical impact. |
+| Export integration | `tests/test_cli.py` | Format dispatch, one-analysis, exit codes, artifact preservation, JSON byte-identity. |
+| CI | `.github/workflows/ci.yml`, `tests/test_ci_workflow.py` | `core` matrix (3.10–3.14), `quarto` render smoke, `quality` artifacts with `if: always()` uploads, step summary, least-privilege SARIF step. |
+| Docs | `README.md`, `CONTRIBUTING.md` | Export format reference, exit-code table, CI artifact policy. |
+| Tests | `tests/test_export_csv.py`, `tests/test_export_sarif.py`, `tests/test_export_junit.py`, `tests/test_export_markdown.py`, `tests/test_cli.py`, `tests/test_ci_workflow.py` | Unit, golden byte-identity, schema validation, CLI integration, workflow structure. |
+
+---
+
+### Task 1: Close the exit-code-3 gap (carried from Milestone 3)
+
+The whole-branch review verified that `scan` on a read-only root and `export --output`
+into an unwritable directory raise raw `PermissionError` tracebacks and exit 1,
+while the spec reserves exit 3 for operational I/O failure. The README exit-code
+table also lacks code 3, and impact's config/date rejection is undocumented.
+
+**Files:**
+- Modify: `src/quarto_needs/cli.py`
+- Modify: `README.md`
+- Test: `tests/test_cli.py`
+
+**Interfaces:**
+- Produces: `scan`/`export` (and, once later tasks land, every exporter path) mapping `OSError` during artifact writes to exit 3 with a one-line stderr message naming the artifact.
+
+- [ ] **Step 1: Write the failing tests**
+
+Add to `tests/test_cli.py`:
+
+```python
+def test_scan_on_an_unwritable_root_is_operational_failure(tmp_path: Path, capsys) -> None:
+    """Read-only scan targets are exit 3, not a traceback."""
+    import os
+
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+    target = tmp_path / "locked"
+    target.mkdir()
+    (target / "needs.qmd").write_text(
+        "::: {.need #REQ-2 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+    os.chmod(target, 0o500)
+
+    try:
+        assert cli.main(["--root", str(target), "scan"]) == 3
+        assert "Could not" in capsys.readouterr().err
+    finally:
+        os.chmod(target, 0o700)
+
+
+def test_export_to_an_unwritable_directory_is_operational_failure(tmp_path: Path, capsys) -> None:
+    """A failed artifact write exits 3 and names the artifact."""
+    import os
+
+    write_valid_project(tmp_path)
+    locked = tmp_path / "locked"
+    locked.mkdir()
+    os.chmod(locked, 0o500)
+
+    try:
+        destination = locked / "sub" / "needs.json"
+        assert cli.main(["--root", str(tmp_path), "export", "--output", str(destination)]) == 3
+        assert str(destination) in capsys.readouterr().err
+    finally:
+        os.chmod(locked, 0o700)
+```
+
+> Note: `scan` reads `.qmd` files; making the ROOT unwritable also blocks reading
+> on some platforms. The test above relies on directory-read remaining possible
+> with mode 0o500 while creation/writes fail. If on this platform reading also
+> fails, keep the export test (which is the load-bearing one) and replace the
+> scan probe with a monkeypatched `Path.write_text`/`Path.mkdir` raising
+> `PermissionError` — record whichever variant you shipped in the report.
+
+- [ ] **Step 2: Run them and verify they fail**
+
+Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k operational_failure`
+
+Expected: FAIL — the commands currently raise `PermissionError` (test error) or exit 1.
+
+- [ ] **Step 3: Implement the guards**
+
+In `cli.py`, wrap the `scan` path collection and the `export` write in
+`try/except OSError` handlers that print
+`Could not write <path>: <error>` (or `Could not scan <root>: <error>` for scan)
+to stderr and return 3. Do not catch `ConfigurationError` or validation paths.
+
+- [ ] **Step 4: Document exit code 3 and impact's guards in the README**
+
+In the exit-code list after code 2, add:
+
+```markdown
+- `3`: operational failure — an artifact could not be read or written. The
+  message names the artifact; anything already written is left in place.
+```
+
+In the `### Baseline, diff, and impact` section's impact paragraph, append one
+sentence: "`impact` refuses a baseline whose configuration fingerprint or
+reference date differs from the current run unless `--recompute-with current`
+is supplied, so one policy always governs a traversal; under that flag, derived
+deltas remain suppressed, exactly as in `diff`."
+
+- [ ] **Step 5: Run the CLI tests and the full suite**
+
+Run: `.venv/bin/python -m pytest tests/test_cli.py -q` then `.venv/bin/python -m pytest -q`
+
+Expected: PASS with zero warnings (241 + new tests).
+
+- [ ] **Step 6: Record the checkpoint conditionally**
+
+```bash
+if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
+  git add src/quarto_needs/cli.py README.md tests/test_cli.py
+  git commit -m "fix: map scan and export write failures to exit code 3"
+else
+  echo "Checkpoint 1 verified; workspace has no Git metadata."
+fi
+```
+
+---
+
+### Task 2: `export --format` plumbing and policy-failure artifact preservation
+
+**Files:**
+- Modify: `src/quarto_needs/cli.py`
+- Test: `tests/test_cli.py`
+
+**Interfaces:**
+- Produces: `export --format <json|csv|sarif|junit|markdown>` (default `json`), `export --baseline <path>` (Markdown only; rejected for other formats with exit 2), and the guarantee that artifacts are written before the profile exit code is returned.
+
+- [ ] **Step 1: Write the failing tests**
+
+Add to `tests/test_cli.py`:
+
+```python
+def test_export_default_format_is_byte_identical_to_the_v1_projection(tmp_path: Path) -> None:
+    """No --format must mean today's json output, byte for byte."""
+    import hashlib
+
+    write_valid_project(tmp_path)
+    first = tmp_path / "a.json"
+    second = tmp_path / "b.json"
+    assert cli.main(["--root", str(tmp_path), "export", "--output", str(first)]) == 0
+    assert cli.main(["--root", str(tmp_path), "export", "--format", "json", "--output", str(second)]) == 0
+
+    assert first.read_bytes() == second.read_bytes()
+    assert len(hashlib.sha256(first.read_bytes()).hexdigest()) == 64
+
+
+def test_export_runs_exactly_one_analysis_per_format(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    write_valid_project(tmp_path)
+    calls = 0
+    real_analyze = cli.analyze_project
+
+    def counted(root: Path, **kwargs: object):
+        nonlocal calls
+        calls += 1
+        return real_analyze(root, **kwargs)
+
+    monkeypatch.setattr(cli, "analyze_project", counted)
+
+    for name in ("json", "csv", "sarif", "junit", "markdown"):
+        destination = tmp_path / "out" / name
+        assert cli.main([
+            "--root", str(tmp_path), "export", "--format", name,
+            "--output", str(destination / "artifact"),
+        ]) in (0, 1), name
+    assert calls == 5
+
+
+def test_export_rejects_baseline_for_non_markdown_formats(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    assert cli.main([
+        "--root", str(tmp_path), "export", "--format", "sarif",
+        "--output", str(tmp_path / "out.sarif"), "--baseline", str(tmp_path / "none.json"),
+    ]) == 2
+    assert "markdown" in capsys.readouterr().err
+
+
+def test_export_preserves_artifacts_on_policy_failure(tmp_path: Path) -> None:
+    """A failing strict gate still writes the artifact, then exits 1."""
+    # An approved requirement with no verification makes the verification gate
+    # fail with a non-zero denominator (an empty scope passes vacuously).
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
+        "\n## Authenticate\nBody.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n', encoding="utf-8"
+    )
+    destination = tmp_path / "artifacts" / "report.md"
+
+    assert cli.main(["--root", str(tmp_path), "export", "--format", "markdown", "--output", str(destination)]) == 1
+    assert destination.is_file()
+```
+
+- [ ] **Step 2: Run them and verify they fail**
+
+Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k export`
+
+Expected: FAIL — `--format`/`--baseline` do not exist (argparse exit 2 via SystemExit) and the policy-failure path is absent.
+
+- [ ] **Step 3: Implement the plumbing**
+
+Extend the `export` parser:
+
+```python
+    export.add_argument("--format", choices=("json", "csv", "sarif", "junit", "markdown"), default="json")
+    export.add_argument("--baseline", help="Baseline for the Markdown change summary (markdown format only)")
+```
+
+Replace the `export` dispatch block with a `_export(root, args, config)` handler that: analyzes once; dispatches per format to a writer module (Tasks 3–6 land the writers; until then a temporary `raise NotImplementedError` for non-json formats is acceptable ONLY within this task's branch — final acceptance requires all five); writes through `_write_atomic_text`; returns `profile_exit_code(config.profile, False, failed_gate_count)` where the gate count comes from `report_from_snapshot(snapshot, config)` reusing the snapshot (no second analysis). `--baseline` with a non-markdown format prints a usage error and returns 2 before analysis.
+
+- [ ] **Step 4: Run the CLI tests**
+
+Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k export`
+
+Expected: the byte-identity, one-analysis, and baseline-rejection tests PASS. The per-format loop and policy-failure tests may remain blocked until Tasks 3–6 land — if so, mark them `xfail(strict=True)` with a `# TODO(milestone-4a-writers)` note and record that in the report; Tasks 3–6 remove the marks.
+
+- [ ] **Step 5: Run the full suite and record the checkpoint conditionally**
+
+---
+
+### Task 3: CSV exporter
+
+**Files:**
+- Create: `src/quarto_needs/exporters/__init__.py`
+- Create: `src/quarto_needs/exporters/csv_export.py`
+- Create: `tests/test_export_csv.py`
+
+**Interfaces:**
+- Consumes: `AnalysisSnapshot`, `export._write_atomic_text`.
+- Produces: `csv_export.render_objects(snapshot) -> str`, `render_relations(snapshot) -> str`, `render_findings(snapshot) -> str`, and `csv_export.write_all(directory: Path, snapshot) -> tuple[Path, ...]`.
+
+- [ ] **Step 1: Write the failing tests**
+
+Create `tests/test_export_csv.py`:
+
+```python
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
+    cells = {row["title"]: None for row in csv.DictReader(text.splitlines())}
+    dangerous = [value for value in cells if value.startswith(("=", "+", "-", "@", "\t", "\r"))]
+    assert not dangerous
+    assert any(value.startswith("'=") for value in cells), "the neutralized title must carry the apostrophe prefix"
+
+
+def test_csv_is_deterministic(tmp_path: Path, monkeypatch) -> None:
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
+    write_project(tmp_path)
+    first = csv_export.render_objects(build(tmp_path))
+    second = csv_export.render_objects(build(tmp_path))
+    assert first == second
+```
+
+- [ ] **Step 2: Run them and verify they fail** — `ModuleNotFoundError: No module named 'quarto_needs.exporters'`.
+
+- [ ] **Step 3: Implement `csv_export.py`**
+
+Deterministic ordering (case-insensitive by id, then by field), fixed column sets (`objects`: id, type, title, status, priority, tags, body, rationale; `relations`: source, authored_name, target, semantic_family; `findings`: code, severity, object_id, message, file, line), `\r\n` line endings per RFC 4180 via `csv.writer` over `io.StringIO`, and a `_neutralize(value)` helper that prefixes `'` when a stringified cell starts with `=`, `+`, `-`, `@`, tab, or carriage return. `write_all` creates the directory and writes atomically, returning the three paths sorted.
+
+- [ ] **Step 4: Run the CSV tests** — Expected: PASS.
+- [ ] **Step 5: Full suite; remove Task 2's xfail for csv if present; conditional checkpoint.**
+
+---
+
+### Task 4: SARIF exporter
+
+**Files:**
+- Create: `src/quarto_needs/exporters/sarif_export.py`
+- Create: `schemas/vendor/sarif-2.1.0/sarif-schema.json`
+- Create: `schemas/vendor/sarif-2.1.0/VENDORED.md`
+- Create: `tests/test_export_sarif.py`
+
+**Interfaces:**
+- Consumes: `AnalysisSnapshot`, `rules.RULES` registry, the vendored schema.
+- Produces: `sarif_export.render(snapshot) -> str`, `sarif_export.write(path, snapshot) -> Path`.
+
+- [ ] **Step 1: Vendor the SARIF 2.1.0 schema**
+
+Download `https://json.schemastore.org/sarif-2.1.0.json` (or the equivalent official `sarif-2.1.0` JSON Schema from the OASIS repository) into `schemas/vendor/sarif-2.1.0/sarif-schema.json`; record in `VENDORED.md` the upstream URL, version, license (MIT), retrieval date, and the SHA-256 of the vendored file. If the workstation is offline, copy the schema from the locally installed `jsonschema` bundles if present, else STOP and report.
+
+- [ ] **Step 2: Write the failing tests**
+
+Create `tests/test_export_sarif.py`:
+
+```python
+from __future__ import annotations
+
+import json
+from pathlib import Path
+
+import pytest
+from jsonschema import Draft202012Validator
+
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+from quarto_needs.exporters import sarif_export
+
+ROOT = Path(__file__).resolve().parents[1]
+SCHEMA = ROOT / "schemas" / "vendor" / "sarif-2.1.0" / "sarif-schema.json"
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
+    Draft202012Validator.check_schema(schema)
+
+    (tmp_path / "ok.qmd").write_text(
+        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+    result = analyze_project(tmp_path, config=load_config(tmp_path))
+    assert result.snapshot is not None
+
+    payload = json.loads(sarif_export.render(result.snapshot))
+    Draft202012Validator(schema).validate(payload)
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
+```
+
+> Interface note: SARIF consumes **findings**, not the snapshot alone — the
+> load-bearing producer is `render_from_findings(findings: Sequence[Finding]) -> str`
+> (plus a `render(snapshot)` convenience that forwards `snapshot.findings`).
+> Findings from a structurally invalid project (snapshot is None) must still
+> export; that is why the producer is findings-based.
+
+- [ ] **Step 3: Run them and verify they fail** — `ModuleNotFoundError`.
+- [ ] **Step 4: Implement `sarif_export.py`**
+
+`$schema` pinned to the vendored URI, `version: "2.1.0"`, one run; `tool.driver` name `quarto-needs` with the package version and one `reportingDescriptor` per distinct finding code (from `rules.RULES` for help/text, falling back to the code); one `result` per finding with `level` mapped error→error / warning→warning / info→note, `message.text`, `locations[0].physicalLocation` (`artifactLocation.uri` as the project-relative file, `region.startLine`), and `fingerprints.primaryLocationLineHash` from the finding's existing stable identity hash; results sorted by (code, object_id, message) for determinism; `automationDetails.id` fixed, no timestamps.
+
+- [ ] **Step 5: Run the SARIF tests; full suite; remove Task 2's xfail for sarif; conditional checkpoint.**
+
+---
+
+### Task 5: JUnit exporter
+
+**Files:**
+- Create: `src/quarto_needs/exporters/junit_export.py`
+- Create: `tests/test_export_junit.py`
+
+**Interfaces:**
+- Consumes: `QualityReport` (from `quality.report_from_snapshot`).
+- Produces: `junit_export.render(report: QualityReport) -> str`, `junit_export.write(path, report) -> Path`.
+
+- [ ] **Step 1: Write the failing tests**
+
+Create `tests/test_export_junit.py`:
+
+```python
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
+        ":::\n",
+        encoding="utf-8",
+    )
+
+
+def report_for(root: Path):
+    result = analyze_project(root, config=load_config(root))
+    assert result.snapshot is not None
+    return report_from_snapshot(result.snapshot, load_config(root))
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
+    names = [case.attrib["name"] for case in suite.findall("testcase")]
+    assert names == sorted(g["name"] for g in report.to_dict()["gates"])
+
+    failed = {case.attrib["name"] for case in suite.iter("testcase") if case.find("failure") is not None}
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
+    assert "warnings" in properties
+
+    assert junit_export.render(report) == first
+```
+
+- [ ] **Step 2: Run them and verify they fail** — `ModuleNotFoundError`.
+- [ ] **Step 3: Implement `junit_export.py`**
+
+`xml.etree.ElementTree` with fixed attribute order guaranteed by constructing
+elements in a fixed sequence and serializing with `ET.tostring(..., encoding="unicode")`
+plus a trailing newline; one `testsuites`/`testsuite` pair; `tests`/`failures`
+counts derived; one `testcase` per gate (classname `quarto-needs.gates`), a
+`<failure message="threshold X, actual Y">` child for failed gates; `properties`
+carrying `errors`, `warnings`, and `profile`; gates sorted by name. XML entity
+handling comes from the stdlib serializer — never build markup by string
+concatenation.
+
+- [ ] **Step 4: Run the JUnit tests; full suite; remove Task 2's xfail for junit; conditional checkpoint.**
+
+---
+
+### Task 6: Markdown CI summary exporter
+
+**Files:**
+- Create: `src/quarto_needs/exporters/markdown_export.py`
+- Create: `tests/test_export_markdown.py`
+
+**Interfaces:**
+- Consumes: `AnalysisSnapshot`, `NeedsConfig`, `QualityReport`, optional baseline payload via `diff.compare` and `impact.analyze`.
+- Produces: `markdown_export.render(snapshot, config, *, baseline: Mapping[str, object] | None = None) -> str`, `markdown_export.write(path, snapshot, config, *, baseline=None) -> Path`.
+
+- [ ] **Step 1: Write the failing tests**
+
+Create `tests/test_export_markdown.py`:
+
+```python
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
+        "::: {.need #TC-1 type=test-case status=passed}\n"
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
+        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n', encoding="utf-8"
+    )
+    snapshot, config = built(tmp_path)
+
+    text = markdown_export.render(snapshot, config)
+
+    assert "## Changes" in text and "No baseline was supplied" in text
+    assert "## Failed gates" in text and "min-verification-trace" in text
+    assert "## High and critical impact" in text
+
+
+def test_summary_with_a_baseline_reports_changes_and_impact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
+        "::: {.need #TC-1 type=test-case status=passed}\n"
+        "\n## Login\nSigns in.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+    snapshot, config = built(tmp_path)
+
+    text = markdown_export.render(snapshot, config, baseline=payload)
+
+    assert "REQ-1" in text and "body" in text
+    assert "TC-1" in text  # impacted via verified-by
+    assert "## Coverage deltas" in text
+
+
+def test_summary_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
+    write_project(tmp_path)
+    snapshot, config = built(tmp_path)
+    assert markdown_export.render(snapshot, config) == markdown_export.render(snapshot, config)
+```
+
+- [ ] **Step 2: Run them and verify they fail** — `ModuleNotFoundError`.
+- [ ] **Step 3: Implement `markdown_export.py`**
+
+Sections in fixed order: `# Quarto-Needs CI summary`; `## Changes` (from
+`diff.compare(baseline, snapshot, config)` — added/removed objects, modified
+by field, relocated; without a baseline, the sentence "No baseline was
+supplied; change classification is unavailable."); `## Coverage deltas`
+(metric deltas table scope/strength before→after, or "No coverage deltas.");
+`## Failed gates` (name, threshold, actual — or "All gates passed.");
+`## High and critical impact` (impacted entries whose `priority` is `high`
+or `critical`, with path and distance; without a baseline the same
+no-baseline sentence). When a baseline is supplied, run `diff.compare(...,
+recompute=True)` and `impact.analyze(..., recompute=True)` so one policy
+governs and date mismatches cannot refuse the summary. End with a
+`## Findings` counts line (errors/warnings).
+
+- [ ] **Step 4: Run the Markdown tests; full suite; remove Task 2's xfail for markdown; conditional checkpoint.**
+
+---
+
+### Task 7: CI workflow split and milestone acceptance
+
+**Files:**
+- Modify: `.github/workflows/ci.yml`
+- Create: `tests/test_ci_workflow.py`
+- Modify: `README.md`, `CONTRIBUTING.md`
+
+**Interfaces:**
+- Produces: the three-job workflow (`core`, `quarto`, `quality`) with `if: always()` artifact uploads, a step summary, and a least-privilege SARIF upload; structural tests pinning the contract.
+
+- [ ] **Step 1: Write the failing structural tests**
+
+Create `tests/test_ci_workflow.py`:
+
+```python
+from __future__ import annotations
+
+from pathlib import Path
+
+import yaml
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
+    quality = parsed()["jobs"]["quality"]["steps"]
+    upload_steps = [step for step in quality if "upload-artifact" in str(step.get("uses", ""))]
+    assert upload_steps, "quality must upload artifacts"
+    assert any("github/codeql-action/upload-sarif" in str(step.get("uses", "")) for step in quality)
+
+
+def test_quality_generates_every_export_format() -> None:
+    run_steps = [str(step.get("run", "")) for step in parsed()["jobs"]["quality"]["steps"]]
+    joined = "\n".join(run_steps)
+    for name in ("json", "csv", "sarif", "junit", "markdown"):
+        assert f"--format {name}" in joined, name
+```
+
+- [ ] **Step 2: Run them and verify they fail** — the current single-job workflow has no `core`/`quarto`/`quality`.
+
+- [ ] **Step 3: Add `pyyaml` to the test extra and rewrite the workflow**
+
+`pyproject.toml`: add `"pyyaml"` to the `test` optional list; run `make setup`.
+Rewrite `.github/workflows/ci.yml`:
+
+- `core`: matrix `["3.10", "3.11", "3.12", "3.13", "3.14"]` on `ubuntu-latest`, `pip install -e ".[test]"`, `pytest -q`, plus `quarto-needs scan`/`check` on the example book with `PYTHONPATH=src`.
+- `quarto`: `needs: core`, pinned Quarto (`quarto-dev/quarto-actions/setup@v0` with a pinned version), `make sync-example`, `make render-example-all`, `make check-example`.
+- `quality`: `needs: core`, strict profile run over `examples/book` generating all five export formats into `artifacts/`, `quarto-needs quality --format json --output artifacts/quality.json`, artifact upload with `if: always()`, `$GITHUB_STEP_SUMMARY` append from the markdown export, and a separate `github/codeql-action/upload-sarif@v3` step with `permissions: contents: read` / `security-events: write` scoped to that step's job.
+- No `pull_request_target` anywhere; `on: [push, pull_request]`.
+
+- [ ] **Step 4: Run the structural tests** — Expected: PASS.
+
+- [ ] **Step 5: Document in README/CONTRIBUTING**
+
+README: an `## Export formats` subsection under the export command listing the
+five formats, their outputs (three CSV files in a directory; single SARIF,
+JUnit, Markdown documents), determinism guarantee, and the exit-1-with-artifacts
+behavior. CONTRIBUTING: CI artifact policy — artifacts are uploaded `if:
+always()`; a failed gate run still produces them; operational failures exit 3
+and name the missing artifact.
+
+- [ ] **Step 6: Acceptance run**
+
+```bash
+make setup && make test
+PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/book export --format csv --output /tmp/m4a/csv
+PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/book export --format sarif --output /tmp/m4a/out.sarif
+PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/book export --format junit --output /tmp/m4a/out.xml
+PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/book export --format markdown --output /tmp/m4a/out.md --baseline examples/book/baselines/quarto-needs.json
+make diff-example
+.venv/bin/python -m pytest -q
+```
+
+Expected: every export exits 0; `diff-example` still prints `No changes.`;
+full suite passes with zero warnings; repeated markdown/sarif/junit runs with
+`SOURCE_DATE_EPOCH` pinned are byte-identical.
+
+- [ ] **Step 7: Record the Milestone 4A checkpoint conditionally**
+
+```bash
+if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
+  git add -A
+  git commit -m "feat: complete milestone four a exporters and ci"
+else
+  echo "Milestone 4A verified; workspace has no Git metadata."
+fi
+```
+
+Expected: every Milestone 4A acceptance gate is complete. Milestone 4B starts only after this checkpoint, with its own implementation plan.
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md	2026-08-25 16:24:03.641108789 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md	2026-08-26 02:28:58.028504270 -0300
@@ -163,27 +163,27 @@
 - added and removed objects;
 - semantic modifications by field;
 - added and removed relations;
 - source relocation without semantic change;
 - findings, metrics, and gate regressions.
 
 Automatic rename detection is excluded from the initial release because it is inherently heuristic. A changed ID is reported as removal plus addition.
 
 Impact analysis traverses the union of the before and after graphs so removed nodes and edges remain explainable. Every impacted result includes the originating change, direct or transitive classification, distance, traversed relations, path, and configured priority. The first implementation does not invent an opaque risk score; paths and policy decisions remain auditable.
 
-Snapshots store a configuration fingerprint: SHA-256 over the canonical merged configuration, embedded defaults, relation-catalog version, and rule-set version, excluding the configuration file's path. When fingerprints differ, default `diff` compares authored object content and authored relation tuples only, emits `configuration-changed`, and suppresses semantic-relation, finding, metric, and gate deltas. This prevents a catalog-only family/role change from appearing as a project edge removal/addition. `diff --recompute-with current` re-evaluates both snapshots under the current configuration before comparing semantic and derived results. `impact` rejects mismatched configuration fingerprints unless the same recomputation option is supplied, ensuring one relation policy governs the entire traversal.
+Snapshots store a configuration fingerprint: SHA-256 over the canonical merged configuration, embedded defaults, relation-catalog version, and rule-set version, excluding the configuration file's path. When fingerprints differ, default `diff` compares authored object content and authored relation tuples only, emits `configuration-changed`, and suppresses semantic-relation, finding, metric, and gate deltas. This prevents a catalog-only family/role change from appearing as a project edge removal/addition. `diff --recompute-with current` re-evaluates the baseline's authored relations through the current catalog so semantic comparison is valid again; the baseline's stored derived results (findings, metrics, gates) are never re-derived, so those deltas stay suppressed until both sides are produced under the same configuration and reference date. `impact` rejects mismatched configuration fingerprints unless the same recomputation option is supplied, ensuring one relation policy governs the entire traversal.
 
 ### Milestone 3 design decisions
 
 The following three decisions refine the contract above without altering it. Each was open because this specification did not address it.
 
-**The reference date is a first-class comparison axis.** `reference_date()` is a semantic input, not formatting metadata: evidence expiry (REQ015) and evidence coverage both depend on it, so an unchanged project legitimately reports different coverage on different days. A baseline therefore records the reference date it was computed under, alongside its configuration fingerprint. When the two differ, `diff` emits `reference-date-changed` and suppresses the date-derived deltas — evidence coverage and REQ015 findings — exactly as it does for a changed configuration fingerprint, and `impact` rejects the mismatch. `diff --recompute-with current` re-evaluates both snapshots under the current reference date. Determinism is consequently defined as byte-identical output for a fixed configuration and a fixed reference date; `SOURCE_DATE_EPOCH` remains the way to fix the latter. Fingerprints continue to exclude the reference date, which is an input to derived data rather than authored content.
+**The reference date is a first-class comparison axis.** `reference_date()` is a semantic input, not formatting metadata: evidence expiry (REQ015) and evidence coverage both depend on it, so an unchanged project legitimately reports different coverage on different days. A baseline therefore records the reference date it was computed under, alongside its configuration fingerprint. When the two differ, `diff` emits `reference-date-changed` and suppresses the date-derived deltas — evidence coverage and REQ015 findings — exactly as it does for a changed configuration fingerprint, and `impact` rejects the mismatch. As with a configuration change, `--recompute-with current` re-resolves the baseline's authored relations but cannot re-derive its stored date-derived results, so those deltas stay suppressed until both sides share a reference date. Determinism is consequently defined as byte-identical output for a fixed configuration and a fixed reference date; `SOURCE_DATE_EPOCH` remains the way to fix the latter. Fingerprints continue to exclude the reference date, which is an input to derived data rather than authored content.
 
 This is distinct from the exporter rule on wall-clock timestamps. That rule governs formatting metadata, which is omitted or pinned to `SOURCE_DATE_EPOCH` with a `1970-01-01T00:00:00Z` fallback. The reference date is an analysis input whose value changes results, so it is recorded and compared rather than omitted; a 1970 fallback would make every expiry check meaningless.
 
 **Relocation is keyed on the declaring file.** A relocation record is emitted when an object's declaring file changes, and it carries the file and line before and after. A line-only shift within the same file produces no record: fingerprints already exclude line numbers, and emitting a record for every object below an inserted paragraph would make relocation the loudest and least informative category in the diff. Moving a need between pages is an authored fact; being pushed down three lines is not.
 
 **Baseline creation refuses to overwrite.** `baseline create` fails with exit code 2 when its destination already exists, unless `--force` is supplied. An accidentally overwritten baseline is unrecoverable without version control, which this project does not assume.
 
 ## Quarto experience
 
 Python writes the precomputed projection. Lua loads and caches it per Pandoc process, resolves links according to the output format, and creates semantic Pandoc AST. Local JavaScript progressively enhances only HTML.
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/examples/book/baselines/quarto-needs.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/examples/book/baselines/quarto-needs.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/examples/book/baselines/quarto-needs.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/examples/book/baselines/quarto-needs.json	2026-08-26 15:22:15.752953410 -0300
@@ -0,0 +1,3107 @@
+{
+  "configurationFingerprint": "c60ad972e64baadc4e7c454cc023c6209b9dd4aa09e93cf80f714a5be52444a0",
+  "findings": [],
+  "generator": {
+    "name": "quarto-needs",
+    "version": "0.1.0"
+  },
+  "objects": [
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;security"
+      },
+      "body": "Valida credenciais, MFA e sessões para os canais do Aegis IAM.",
+      "contentFingerprint": "75e4cfc44c938a3179a001f787841701376057ff5d7931ac288ed8f69f78c509",
+      "id": "IAM-COMP-001",
+      "location": {
+        "anchor": "IAM-COMP-001",
+        "file": "architecture/components.qmd",
+        "line": 6
+      },
+      "rationale": "",
+      "status": "implemented",
+      "title": "Serviço de autenticação",
+      "type": "component"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;policy"
+      },
+      "body": "Avalia políticas por atributo e retorna decisões de permitir ou negar.",
+      "contentFingerprint": "0f1f5efb643b87dee51e363f6c1a9526b2b66d170071c24cfb4864910174191a",
+      "id": "IAM-COMP-002",
+      "location": {
+        "anchor": "IAM-COMP-002",
+        "file": "architecture/components.qmd",
+        "line": 12
+      },
+      "rationale": "",
+      "status": "implemented",
+      "title": "Motor de políticas",
+      "type": "component"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;provisioning"
+      },
+      "body": "Consome eventos de pessoas e executa mudanças controladas em contas e grupos.",
+      "contentFingerprint": "b32df7fdc3b48ba186cfc0ace3c8e250b41aa5255bcef06f4b9ca9213cc8b5f6",
+      "id": "IAM-COMP-003",
+      "location": {
+        "anchor": "IAM-COMP-003",
+        "file": "architecture/components.qmd",
+        "line": 18
+      },
+      "rationale": "",
+      "status": "implemented",
+      "title": "Orquestrador de ciclo de vida",
+      "type": "component"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;compliance"
+      },
+      "body": "Armazena eventos com integridade verificável e consulta controlada.",
+      "contentFingerprint": "b53f421931892521086927f39a1d4eea0bab825f0a1768f46cb87e3bc7db8868",
+      "id": "IAM-COMP-004",
+      "location": {
+        "anchor": "IAM-COMP-004",
+        "file": "architecture/components.qmd",
+        "line": 24
+      },
+      "rationale": "",
+      "status": "implemented",
+      "title": "Cofre de auditoria",
+      "type": "component"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "body": "Coordena prova de identidade, aprovação e emissão segura de nova credencial.",
+      "contentFingerprint": "185c61581a7916212c1c93f29a92129a6b17e638511aecc84ff17be56081dce0",
+      "id": "IAM-COMP-005",
+      "location": {
+        "anchor": "IAM-COMP-005",
+        "file": "architecture/components.qmd",
+        "line": 30
+      },
+      "rationale": "",
+      "status": "implemented",
+      "title": "Serviço de recuperação",
+      "type": "component"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "experience;accessibility"
+      },
+      "body": "Oferece telas acessíveis para login, consentimento e administração de conta.",
+      "contentFingerprint": "bec5e62dbc975956cfb3b684b7110e541970ea59a08d1ee90f578d655002919b",
+      "id": "IAM-COMP-006",
+      "location": {
+        "anchor": "IAM-COMP-006",
+        "file": "architecture/components.qmd",
+        "line": 36
+      },
+      "rationale": "",
+      "status": "implemented",
+      "title": "Portal de identidade",
+      "type": "component"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;ci"
+      },
+      "body": "Execução automatizada do cenário de credencial válida no ambiente de integração.",
+      "contentFingerprint": "3470ea6e402582fca62e89b790d16afc229602998e97cd122611b529f71eaa64",
+      "id": "IAM-EVD-001",
+      "location": {
+        "anchor": "IAM-EVD-001",
+        "file": "verification/evidence.qmd",
+        "line": 5
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de autenticação 2026-08-25",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "mfa;ci"
+      },
+      "body": "Execução automatizada do bloqueio sem segundo fator.",
+      "contentFingerprint": "4d83aa696fba651c034c10e13bccb527a296eed1cd6959c7f51a6462f43324dc",
+      "id": "IAM-EVD-002",
+      "location": {
+        "anchor": "IAM-EVD-002",
+        "file": "verification/evidence.qmd",
+        "line": 11
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de MFA administrativo",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "session;ci"
+      },
+      "body": "Execução automatizada de suspensão e invalidação de tokens.",
+      "contentFingerprint": "acab1ecc94b17d7fcbb41ad86dce826c82310de41c3a1684ff25105a383ae9ae",
+      "id": "IAM-EVD-003",
+      "location": {
+        "anchor": "IAM-EVD-003",
+        "file": "verification/evidence.qmd",
+        "line": 17
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de revogação de sessão",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;ci"
+      },
+      "body": "Execução automatizada de decisão contextual de acesso.",
+      "contentFingerprint": "86ba3e37a50a5bc3f7cc9fd32f90d450b98ac45aeab3c37e7eaa1d5699cd5a3a",
+      "id": "IAM-EVD-004",
+      "location": {
+        "anchor": "IAM-EVD-004",
+        "file": "verification/evidence.qmd",
+        "line": 23
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de política por atributo",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "least-privilege;ci"
+      },
+      "body": "Execução automatizada de uma solicitação sem regra permissiva.",
+      "contentFingerprint": "136b7787dbd14e1abe498abc27bbb13c9aababcf6dd190c73dbd0502456cae2f",
+      "id": "IAM-EVD-005",
+      "location": {
+        "anchor": "IAM-EVD-005",
+        "file": "verification/evidence.qmd",
+        "line": 29
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de negação padrão",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "performance;load"
+      },
+      "body": "Resultado do teste de carga para o objetivo de resposta de autorização.",
+      "contentFingerprint": "4dd84d8afcf41f27250185a6289342e534ddaef0083ec347f90ed43e1565db66",
+      "id": "IAM-EVD-006",
+      "location": {
+        "anchor": "IAM-EVD-006",
+        "file": "verification/evidence.qmd",
+        "line": 35
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de carga da autorização",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;ci"
+      },
+      "body": "Execução automatizada que registra a conta criada a partir de um evento válido de RH.",
+      "contentFingerprint": "f7e9620ea36706bf80ac870179bc53b1b4601f609b37e2d45e06475869e6559b",
+      "id": "IAM-EVD-007",
+      "location": {
+        "anchor": "IAM-EVD-007",
+        "file": "verification/evidence.qmd",
+        "line": 41
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de provisão por admissão",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;offboarding"
+      },
+      "body": "Execução automatizada que confirma suspensão da conta e invalidação das sessões.",
+      "contentFingerprint": "88d7358d6a1e978f9e20bfcdab6ca0a9a9f02dfaa84d36a33f8b7d3a73fe32a1",
+      "id": "IAM-EVD-008",
+      "location": {
+        "anchor": "IAM-EVD-008",
+        "file": "verification/evidence.qmd",
+        "line": 47
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de suspensão por desligamento",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "lifecycle;review"
+      },
+      "body": "Execução automatizada que comprova a criação de tarefa para o responsável pelo recurso.",
+      "contentFingerprint": "e7bf792bd4b4241b187bbaadadaf1d43af0d9a46050014fccb2a7f29ad780aaa",
+      "id": "IAM-EVD-009",
+      "location": {
+        "anchor": "IAM-EVD-009",
+        "file": "verification/evidence.qmd",
+        "line": 53
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de campanha de revisão",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;integrity"
+      },
+      "body": "Execução automatizada que valida correlação e integridade de uma decisão registrada.",
+      "contentFingerprint": "65c1ef0bcc0cb92e1cdb0b5a3e8d700efd533a6be3d90307f4f7e1004157cdda",
+      "id": "IAM-EVD-010",
+      "location": {
+        "anchor": "IAM-EVD-010",
+        "file": "verification/evidence.qmd",
+        "line": 59
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de evento de autorização",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "audit;retention"
+      },
+      "body": "Resultado de consulta ordenada em eventos preservados no período de retenção configurado.",
+      "contentFingerprint": "ca86c38adb22c7bcc1506ac94114f1b45414442972fbb9c5384f241a01f6f0d7",
+      "id": "IAM-EVD-011",
+      "location": {
+        "anchor": "IAM-EVD-011",
+        "file": "verification/evidence.qmd",
+        "line": 65
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de consulta e retenção",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "body": "Execução automatizada que registra a prova adicional de identidade antes da redefinição.",
+      "contentFingerprint": "949fec212269f277d378ef13305a20f682151a1683406d5ec6a629e6919e6728",
+      "id": "IAM-EVD-012",
+      "location": {
+        "anchor": "IAM-EVD-012",
+        "file": "verification/evidence.qmd",
+        "line": 71
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de recuperação reforçada",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "accessibility;portal"
+      },
+      "body": "Resultado de teste automatizado e manual de teclado, foco e nomes acessíveis.",
+      "contentFingerprint": "fef717a56d0cb817b0d2bc5d615de1d087c3a8aa45f889c41c25ed93c41d0f82",
+      "id": "IAM-EVD-013",
+      "location": {
+        "anchor": "IAM-EVD-013",
+        "file": "verification/evidence.qmd",
+        "line": 77
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de acessibilidade do portal",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "availability;failover"
+      },
+      "body": "Resultado do exercício de failover e monitoramento mensal do serviço de autenticação.",
+      "contentFingerprint": "b94b286c772d8a9625c934b685dd0cfd61dbd4f370db41d7e646a11cdab68b0f",
+      "id": "IAM-EVD-014",
+      "location": {
+        "anchor": "IAM-EVD-014",
+        "file": "verification/evidence.qmd",
+        "line": 83
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de disponibilidade da autenticação",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;compliance"
+      },
+      "body": "Resultado da inspeção que confirma a ausência de atributos pessoais desnecessários.",
+      "contentFingerprint": "748242a44502370ce246827b923475682b08b1c3ce5da24926505d8838a05e73",
+      "id": "IAM-EVD-015",
+      "location": {
+        "anchor": "IAM-EVD-015",
+        "file": "verification/evidence.qmd",
+        "line": 89
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de minimização de dados",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "security;encryption"
+      },
+      "body": "Resultado da verificação de TLS e criptografia de segredos em armazenamento.",
+      "contentFingerprint": "40617e8a9e56d3aa89ad9af5cbdd5c61a2428442ffe7faae5b4dee12ea211b30",
+      "id": "IAM-EVD-016",
+      "location": {
+        "anchor": "IAM-EVD-016",
+        "file": "verification/evidence.qmd",
+        "line": 95
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de criptografia de credenciais",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;oidc"
+      },
+      "body": "Resultado da integração de descoberta e troca de token com a aplicação consumidora.",
+      "contentFingerprint": "37d25fce5abce7b42ae3f536fc246c8b19ac4ea54f9322689c0bc45a606129de",
+      "id": "IAM-EVD-017",
+      "location": {
+        "anchor": "IAM-EVD-017",
+        "file": "verification/evidence.qmd",
+        "line": 101
+      },
+      "rationale": "",
+      "status": "verified",
+      "title": "Relatório de interoperabilidade OIDC",
+      "type": "evidence"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;security"
+      },
+      "body": "O serviço deve validar credenciais contra o diretório corporativo antes de criar sessão.\n\n### Rationale\n\nGarante que a sessão represente uma identidade corporativa conhecida.",
+      "contentFingerprint": "d4889fa0e62db4370972b8d8bc2e3923460e4e6f2348217f0603fb518af46f63",
+      "id": "IAM-FUN-001",
+      "location": {
+        "anchor": "IAM-FUN-001",
+        "file": "requirements/functional.qmd",
+        "line": 6
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Validar credenciais corporativas",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;mfa;security"
+      },
+      "body": "O serviço deve exigir um segundo fator para papéis privilegiados.\n\n### Rationale\n\nReduz a eficácia de credenciais capturadas por phishing.",
+      "contentFingerprint": "db25523989dafcfc5e133641c2cb67f0c86b9d1d1c23569710a5a03b7bb39867",
+      "id": "IAM-FUN-002",
+      "location": {
+        "anchor": "IAM-FUN-002",
+        "file": "requirements/functional.qmd",
+        "line": 16
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Exigir MFA para acesso privilegiado",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;session"
+      },
+      "body": "O serviço deve revogar sessões quando a conta for suspensa ou o risco subir.\n\n### Rationale\n\nLimita a janela de abuso após um evento de risco.",
+      "contentFingerprint": "e98954b41c43e18aa9bc9cfb30352f94c08216bc7ebc473b78be0c11fc68930d",
+      "id": "IAM-FUN-003",
+      "location": {
+        "anchor": "IAM-FUN-003",
+        "file": "requirements/functional.qmd",
+        "line": 26
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Revogar sessões após mudança de risco",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;policy"
+      },
+      "body": "O motor deve avaliar sujeito, recurso, ação e contexto na decisão de acesso.\n\n### Rationale\n\nPermite aplicar políticas consistentes independentemente da aplicação consumidora.",
+      "contentFingerprint": "5d9b5c06ca8a4586beb9a412613b22b7fdef9472e3b23dd155cf9d1b820e0c21",
+      "id": "IAM-FUN-004",
+      "location": {
+        "anchor": "IAM-FUN-004",
+        "file": "requirements/functional.qmd",
+        "line": 36
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Avaliar políticas por atributo",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;least-privilege"
+      },
+      "body": "O motor deve negar solicitações que não correspondam a uma regra permissiva.\n\n### Rationale\n\nEvita escalada de privilégio causada por política ausente ou excessivamente ampla.",
+      "contentFingerprint": "12455671e513dc8cc3a23ba142e70e84df9c22d5fa747880c30f56754bcd318b",
+      "id": "IAM-FUN-005",
+      "location": {
+        "anchor": "IAM-FUN-005",
+        "file": "requirements/functional.qmd",
+        "line": 46
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Aplicar menor privilégio por padrão",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "authorization;delegation"
+      },
+      "body": "O sistema deve limitar e registrar delegações de acesso com data de expiração.\n\n### Rationale\n\nMantém delegações excepcionais temporárias e responsabilizáveis.",
+      "contentFingerprint": "84e23f44b25987ac652740352805b6f3d17f887c895357b271d35d17d95fe918",
+      "id": "IAM-FUN-006",
+      "location": {
+        "anchor": "IAM-FUN-006",
+        "file": "requirements/functional.qmd",
+        "line": 56
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Registrar delegação temporária",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;provisioning"
+      },
+      "body": "O orquestrador deve criar conta após receber evento válido de admissão.\n\n### Rationale\n\nReduz trabalho manual e garante que o acesso comece com dados de origem confiável.",
+      "contentFingerprint": "bf357bedddc7aa0fe9615d122edbf66c86db53a84ad03fecac2d1c28bcf6b0f0",
+      "id": "IAM-FUN-007",
+      "location": {
+        "anchor": "IAM-FUN-007",
+        "file": "requirements/functional.qmd",
+        "line": 66
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Provisionar conta por evento de admissão",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;offboarding"
+      },
+      "body": "O orquestrador deve suspender a conta e remover sessões após evento de desligamento.\n\n### Rationale\n\nEvita que identidades desligadas mantenham acesso operacional.",
+      "contentFingerprint": "1dd237697c377a523f35c5cf0623be77d1b9dd986f11debf9cce3f4a0a2db3b2",
+      "id": "IAM-FUN-008",
+      "location": {
+        "anchor": "IAM-FUN-008",
+        "file": "requirements/functional.qmd",
+        "line": 76
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Suspender conta no desligamento",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "lifecycle;review"
+      },
+      "body": "O sistema deve abrir campanhas de revisão para responsáveis por recursos.\n\n### Rationale\n\nRevisões periódicas removem privilégios que deixaram de ser necessários.",
+      "contentFingerprint": "14ab1bf7731aac5c1b3bec4fa5a61f46972f33616cb69726645a584ef1ac2ec8",
+      "id": "IAM-FUN-009",
+      "location": {
+        "anchor": "IAM-FUN-009",
+        "file": "requirements/functional.qmd",
+        "line": 86
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Solicitar revisão periódica de acesso",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;security"
+      },
+      "body": "O sistema deve registrar política aplicada, sujeito, recurso, resultado e correlação.\n\n### Rationale\n\nPermite explicar e investigar decisões de autorização.",
+      "contentFingerprint": "71c3840ecce12fe70768ad966a3d98aa990c4e2dee8add0f3c20b306183514cf",
+      "id": "IAM-FUN-010",
+      "location": {
+        "anchor": "IAM-FUN-010",
+        "file": "requirements/functional.qmd",
+        "line": 96
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Registrar decisão de autorização",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "audit;retention"
+      },
+      "body": "Auditores devem consultar eventos de uma conta em ordem temporal e com filtros.\n\n### Rationale\n\nReduz o tempo necessário para investigar uma identidade específica.",
+      "contentFingerprint": "5ceea9a3694ec39bdd8e3f8942d4060c6e916ef5eea7790b7dcff97e821031fa",
+      "id": "IAM-FUN-011",
+      "location": {
+        "anchor": "IAM-FUN-011",
+        "file": "requirements/functional.qmd",
+        "line": 106
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Consultar trilha de auditoria por conta",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "body": "O fluxo deve exigir prova de posse e validação adicional para uma conta de alto risco.\n\n### Rationale\n\nEvita que a recuperação de conta seja explorada como tomada de acesso.",
+      "contentFingerprint": "fbef73d7475627b9df07c1e27d895cc8f670c9835246e50775f72c56ffad88d6",
+      "id": "IAM-FUN-012",
+      "location": {
+        "anchor": "IAM-FUN-012",
+        "file": "requirements/functional.qmd",
+        "line": 116
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Recuperar conta com verificação reforçada",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "recovery;support"
+      },
+      "body": "O produto deve permitir recuperação assistida com aprovação de segundo operador.",
+      "contentFingerprint": "0373301f55c36de6eefeb8425bf82d5834f4e23272d067506666ee090822790d",
+      "id": "IAM-FUN-013",
+      "location": {
+        "anchor": "IAM-FUN-013",
+        "file": "requirements/functional.qmd",
+        "line": 126
+      },
+      "rationale": "",
+      "status": "in-review",
+      "title": "Delegar recuperação ao suporte supervisionado",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;scim"
+      },
+      "body": "O produto poderá sincronizar grupos autorizados a partir de provedor externo.",
+      "contentFingerprint": "1c2b88a861b0567cf9a7502bdae897230e1997a89d41d889938a177ee317125c",
+      "id": "IAM-FUN-014",
+      "location": {
+        "anchor": "IAM-FUN-014",
+        "file": "requirements/functional.qmd",
+        "line": 132
+      },
+      "rationale": "",
+      "status": "draft",
+      "title": "Provisionar grupos via SCIM",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "low",
+        "tags": "authentication;password"
+      },
+      "body": "A proposta permitiria uma senha comum para equipes temporárias; foi reprovada por\neliminar responsabilização individual.",
+      "contentFingerprint": "cb53fc66c70192043e6e294a57413127fa870e5bb1e59cbf30d59313a9952ddc",
+      "id": "IAM-FUN-015",
+      "location": {
+        "anchor": "IAM-FUN-015",
+        "file": "requirements/functional.qmd",
+        "line": 138
+      },
+      "rationale": "",
+      "status": "disapproved",
+      "title": "Permitir senha compartilhada por equipe",
+      "type": "functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "integration;oidc"
+      },
+      "body": "Interface de federação para emissão de tokens e descoberta de metadados.",
+      "contentFingerprint": "1c0392e276738a5e13a282e9afae73b760f6211eced24775ebdeb6e1a22e1f79",
+      "id": "IAM-IF-001",
+      "location": {
+        "anchor": "IAM-IF-001",
+        "file": "architecture/components.qmd",
+        "line": 42
+      },
+      "rationale": "",
+      "status": "implemented",
+      "title": "API OpenID Connect",
+      "type": "interface"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;scim"
+      },
+      "body": "Interface para sincronizar usuários e grupos a partir de sistemas de origem.",
+      "contentFingerprint": "b5455055eef8f159d23af8443f244fb30a61f83a3d75e924935b2cde3011f0da",
+      "id": "IAM-IF-002",
+      "location": {
+        "anchor": "IAM-IF-002",
+        "file": "architecture/components.qmd",
+        "line": 48
+      },
+      "rationale": "",
+      "status": "implemented",
+      "title": "API SCIM de provisão",
+      "type": "interface"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;events"
+      },
+      "body": "Interface de eventos assinados entregue ao cofre e ao monitoramento de segurança.",
+      "contentFingerprint": "b178c54035b233ae76d670495492e253533ad66eaff36fd52cf8bf54c6ad0db5",
+      "id": "IAM-IF-003",
+      "location": {
+        "anchor": "IAM-IF-003",
+        "file": "architecture/components.qmd",
+        "line": 54
+      },
+      "rationale": "",
+      "status": "implemented",
+      "title": "Fluxo de eventos de auditoria",
+      "type": "interface"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "security;encryption"
+      },
+      "body": "Credenciais e segredos devem usar criptografia aprovada durante transporte e armazenamento.\n\n### Rationale\n\nProtege segredos contra interceptação e exposição em armazenamento persistente.",
+      "contentFingerprint": "41a2fa225d20fa79e38fcc0b96ef587cfb6726e244a35b79f4911dfd4bfffba2",
+      "id": "IAM-NFR-001",
+      "location": {
+        "anchor": "IAM-NFR-001",
+        "file": "requirements/non-functional.qmd",
+        "line": 6
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Proteger credenciais em trânsito e repouso",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "security;availability"
+      },
+      "body": "O serviço de autenticação deve atingir disponibilidade mensal de 99,95%.\n\n### Rationale\n\nIdentidade indisponível bloqueia o trabalho de todos os sistemas consumidores.",
+      "contentFingerprint": "05d9dc0b99aec35ddf9629cf75a2a62fe9088d7ddee82a83a7e23d9dc5481cec",
+      "id": "IAM-NFR-002",
+      "location": {
+        "anchor": "IAM-NFR-002",
+        "file": "requirements/non-functional.qmd",
+        "line": 16
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Manter autenticação disponível",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;compliance"
+      },
+      "body": "Eventos de auditoria devem conter somente dados pessoais necessários à finalidade.\n\n### Rationale\n\nMinimiza o impacto de um acesso indevido ou vazamento do repositório de logs.",
+      "contentFingerprint": "4d01a49a9c21ebb4f41c77c55345ffc595068103fb5fabadf254ea7c50df616f",
+      "id": "IAM-NFR-003",
+      "location": {
+        "anchor": "IAM-NFR-003",
+        "file": "requirements/non-functional.qmd",
+        "line": 26
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Minimizar dados pessoais em eventos",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "performance;authorization"
+      },
+      "body": "O percentil 95 das decisões de autorização deve ser inferior a 200 ms sob carga nominal.\n\n### Rationale\n\nDecisões lentas degradam a experiência e estimulam contornos inseguros.",
+      "contentFingerprint": "5af2d645ac140018c1fc59774fad966a0513f9cb427573ced2e560512b4cb6aa",
+      "id": "IAM-NFR-004",
+      "location": {
+        "anchor": "IAM-NFR-004",
+        "file": "requirements/non-functional.qmd",
+        "line": 36
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Responder decisão de acesso em até 200 ms",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "security;logging"
+      },
+      "body": "O armazenamento de auditoria deve detectar alteração ou remoção de eventos.\n\n### Rationale\n\nUma trilha adulterável não sustenta investigação nem comprovação de conformidade.",
+      "contentFingerprint": "b7355bb414216082fe63462dce207721f353d57948d0f35023bb5d34b1554a8d",
+      "id": "IAM-NFR-005",
+      "location": {
+        "anchor": "IAM-NFR-005",
+        "file": "requirements/non-functional.qmd",
+        "line": 46
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Preservar integridade de auditoria",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "usability;accessibility"
+      },
+      "body": "As telas de autenticação devem atender critérios de acessibilidade de nível AA.\n\n### Rationale\n\nTodos os usuários precisam concluir autenticação sem depender de um único modo de interação.",
+      "contentFingerprint": "093e88268168512cfceca52f737cad87d6d5af6a359fe74d0d09ff2056ddfeb5",
+      "id": "IAM-NFR-006",
+      "location": {
+        "anchor": "IAM-NFR-006",
+        "file": "requirements/non-functional.qmd",
+        "line": 56
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Oferecer autenticação acessível",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "compliance;retention"
+      },
+      "body": "Evidências de acesso devem permanecer disponíveis durante o prazo de retenção definido.\n\n### Rationale\n\nAtende obrigações de auditoria e permite investigar fatos ocorridos no passado.",
+      "contentFingerprint": "9af01cdeb1f63f5aff0360c5e7683a8927bd59b1e9adb50ca60be48fc936540e",
+      "id": "IAM-NFR-007",
+      "location": {
+        "anchor": "IAM-NFR-007",
+        "file": "requirements/non-functional.qmd",
+        "line": 66
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Reter evidências pelo prazo regulatório",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "resilience;recovery"
+      },
+      "body": "O serviço deve restaurar a recuperação de conta dentro do objetivo de quatro horas.\n\n### Rationale\n\nLimita o período em que usuários legítimos ficam sem um caminho seguro de retorno.",
+      "contentFingerprint": "3eca7999d570c929eea16110cc04ec57ed26cae050b6760d92c9ca76de1458ae",
+      "id": "IAM-NFR-008",
+      "location": {
+        "anchor": "IAM-NFR-008",
+        "file": "requirements/non-functional.qmd",
+        "line": 76
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Restaurar fluxo de recuperação em até quatro horas",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "observability;operations"
+      },
+      "body": "O produto deve publicar métricas de latência, erros e bloqueios para operações.",
+      "contentFingerprint": "b9bb2429b6f23aad3c19316b21bcc1c58b8d7856c54cc626c20d32de6e7e2c6d",
+      "id": "IAM-NFR-009",
+      "location": {
+        "anchor": "IAM-NFR-009",
+        "file": "requirements/non-functional.qmd",
+        "line": 86
+      },
+      "rationale": "",
+      "status": "in-review",
+      "title": "Expor métricas operacionais de identidade",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "low",
+        "tags": "sustainability;operations"
+      },
+      "body": "O produto poderá medir consumo energético por transação de autenticação.",
+      "contentFingerprint": "f7ff3439c2e2cdb2daf1522f78de8cb43894d17966860537372b606e93c07dd2",
+      "id": "IAM-NFR-010",
+      "location": {
+        "anchor": "IAM-NFR-010",
+        "file": "requirements/non-functional.qmd",
+        "line": 92
+      },
+      "rationale": "",
+      "status": "draft",
+      "title": "Medir consumo energético por autenticação",
+      "type": "non-functional-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "security;account-takeover"
+      },
+      "body": "Uma credencial capturada pode permitir acesso indevido sem um segundo fator resistente.",
+      "contentFingerprint": "52f684b828a7b3e11f4b51594647f0b385581b947a8564108c8e746d7495d154",
+      "id": "IAM-RISK-001",
+      "location": {
+        "anchor": "IAM-RISK-001",
+        "file": "risks/security.qmd",
+        "line": 6
+      },
+      "rationale": "",
+      "status": "in-review",
+      "title": "Tomada de conta por phishing",
+      "type": "risk"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "security;privilege-escalation"
+      },
+      "body": "Uma política ampla ou ausente pode conceder acesso além da necessidade de trabalho.",
+      "contentFingerprint": "1a4be55c2f93d1a5195193d2a7a94d8dcfc0e517add3c938ce528c44f9cb4083",
+      "id": "IAM-RISK-002",
+      "location": {
+        "anchor": "IAM-RISK-002",
+        "file": "risks/security.qmd",
+        "line": 12
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Escalada de privilégio por política permissiva",
+      "type": "risk"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;audit"
+      },
+      "body": "Eventos excessivamente detalhados podem expor identificadores e atributos pessoais.",
+      "contentFingerprint": "b1e21795087f6bdd7ff94218d070dc3b1e3a5f2b363e1c7e87f1e6833ff4771b",
+      "id": "IAM-RISK-003",
+      "location": {
+        "anchor": "IAM-RISK-003",
+        "file": "risks/security.qmd",
+        "line": 18
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Vazamento de dados pessoais em logs",
+      "type": "risk"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "availability;recovery"
+      },
+      "body": "Uma falha prolongada pode impedir usuários legítimos de recuperar acesso crítico.",
+      "contentFingerprint": "d9805b49e84f8a8ba719204e1eb874a24b1e7ebf3691c6188718fef87615e8c6",
+      "id": "IAM-RISK-004",
+      "location": {
+        "anchor": "IAM-RISK-004",
+        "file": "risks/security.qmd",
+        "line": 24
+      },
+      "rationale": "",
+      "status": "draft",
+      "title": "Indisponibilidade durante recuperação de conta",
+      "type": "risk"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "security;authentication"
+      },
+      "body": "A CISO precisa de autenticação resistente a phishing para contas privilegiadas.",
+      "contentFingerprint": "2481c03c641f16217c8e7ecda8ffc565be759110644155da6c2d61242a8d0e88",
+      "id": "IAM-STK-001",
+      "location": {
+        "anchor": "IAM-STK-001",
+        "file": "context/stakeholders.qmd",
+        "line": 5
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Diretora de segurança precisa reduzir invasões de conta",
+      "type": "stakeholder-need"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;compliance"
+      },
+      "body": "O DPO precisa de evidências de consentimento, retenção e acesso mínimo.",
+      "contentFingerprint": "06c7f21a535601843bfb70a13a34ee3b1b7d8d15ed8efccaa3a002aa5826eb01",
+      "id": "IAM-STK-002",
+      "location": {
+        "anchor": "IAM-STK-002",
+        "file": "context/stakeholders.qmd",
+        "line": 11
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Encarregado de dados precisa controlar exposição de dados pessoais",
+      "type": "stakeholder-need"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "operations;availability"
+      },
+      "body": "A central de suporte precisa restaurar contas sem criar um atalho para fraude.",
+      "contentFingerprint": "f0d907197380fd76120fe9b9c892dbd6364b868063f7a6f01d43b8af4818e4b7",
+      "id": "IAM-STK-003",
+      "location": {
+        "anchor": "IAM-STK-003",
+        "file": "context/stakeholders.qmd",
+        "line": 17
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Operações precisam recuperar acesso com segurança",
+      "type": "stakeholder-need"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "developer;integration"
+      },
+      "body": "Times internos precisam de uma interface padronizada para login e autorização.",
+      "contentFingerprint": "de6a9f583919902a5e6387c413218428185bdf9a6c965c6e2602f58fb1bf2a0b",
+      "id": "IAM-STK-004",
+      "location": {
+        "anchor": "IAM-STK-004",
+        "file": "context/stakeholders.qmd",
+        "line": 23
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Equipes de produto precisam integrar aplicações rapidamente",
+      "type": "stakeholder-need"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "audit;governance"
+      },
+      "body": "Auditores precisam reconstruir quem autorizou cada privilégio e quando.",
+      "contentFingerprint": "1d4b9d413936bc3a95aa93f6fc0bc9002dd64b6bc850af3c40101c4591a98b12",
+      "id": "IAM-STK-005",
+      "location": {
+        "anchor": "IAM-STK-005",
+        "file": "context/stakeholders.qmd",
+        "line": 29
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Auditoria precisa de rastreabilidade de decisões de acesso",
+      "type": "stakeholder-need"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;security"
+      },
+      "body": "O Aegis IAM deve autenticar a identidade antes de emitir uma sessão utilizável.\n\n### Rationale\n\nEvita que recursos protegidos sejam expostos a solicitantes anônimos.",
+      "contentFingerprint": "c2f816ad67824a263984be7dcf772a09f9df5763f26a7fafb8552408b45ec4a1",
+      "id": "IAM-SYS-001",
+      "location": {
+        "anchor": "IAM-SYS-001",
+        "file": "requirements/system.qmd",
+        "line": 5
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Autenticar identidades antes de emitir sessão",
+      "type": "system-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;least-privilege"
+      },
+      "body": "O sistema deve decidir acesso por políticas centralizadas e atributos confiáveis.\n\n### Rationale\n\nCentralizar a decisão reduz divergências entre aplicações consumidoras.",
+      "contentFingerprint": "ffae6d0e1d4a7b00ec1731c49b269db8955ba8b6799b65c370ad2dccae994372",
+      "id": "IAM-SYS-002",
+      "location": {
+        "anchor": "IAM-SYS-002",
+        "file": "requirements/system.qmd",
+        "line": 15
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Decidir acesso por política central",
+      "type": "system-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;provisioning"
+      },
+      "body": "O sistema deve provisionar, alterar, suspender e encerrar contas de forma auditável.\n\n### Rationale\n\nContas órfãs e privilégios persistentes são riscos operacionais relevantes.",
+      "contentFingerprint": "ef92075c93901c90f6714298fb633bbac897c002135395efe98c8accd4d97b98",
+      "id": "IAM-SYS-003",
+      "location": {
+        "anchor": "IAM-SYS-003",
+        "file": "requirements/system.qmd",
+        "line": 25
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Gerir o ciclo de vida de contas",
+      "type": "system-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;compliance"
+      },
+      "body": "O sistema deve registrar eventos de autenticação, autorização e administração.\n\n### Rationale\n\nRegistros íntegros sustentam investigação, conformidade e responsabilização.",
+      "contentFingerprint": "e375d4ac92dbe73bfedc23f91dd03846478c2f40606b6f2ae33883478f942d25",
+      "id": "IAM-SYS-004",
+      "location": {
+        "anchor": "IAM-SYS-004",
+        "file": "requirements/system.qmd",
+        "line": 35
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Registrar eventos de identidade imutáveis",
+      "type": "system-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "body": "O sistema deve recuperar acesso somente após validação de identidade proporcional ao risco.\n\n### Rationale\n\nO processo de recuperação não pode se tornar uma via de tomada de conta.",
+      "contentFingerprint": "ea653e6bc8d47ba96e5900a94155b8e974576b0645af2774edeaf5e7b73991dd",
+      "id": "IAM-SYS-005",
+      "location": {
+        "anchor": "IAM-SYS-005",
+        "file": "requirements/system.qmd",
+        "line": 45
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Recuperar acesso com prova de identidade",
+      "type": "system-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;standards"
+      },
+      "body": "O sistema deve oferecer protocolos abertos de federação e provisão.\n\n### Rationale\n\nProtocolos padronizados diminuem o custo e o risco das integrações.",
+      "contentFingerprint": "2140139b5c81d8d461950fc833e06565b02300302c46ffa61d4d9e785979ec96",
+      "id": "IAM-SYS-006",
+      "location": {
+        "anchor": "IAM-SYS-006",
+        "file": "requirements/system.qmd",
+        "line": 55
+      },
+      "rationale": "",
+      "status": "approved",
+      "title": "Expor integração de identidade padronizada",
+      "type": "system-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "analytics;governance"
+      },
+      "body": "O sistema deve priorizar para revisão acessos com padrão anômalo.\n\n### Rationale\n\nA análise de anomalias pode antecipar abuso de privilégios.",
+      "contentFingerprint": "a1aee198bb51502e1ae5a741be1f2f7c8406c745a9b1ad76ab4bafdd74278268",
+      "id": "IAM-SYS-007",
+      "location": {
+        "anchor": "IAM-SYS-007",
+        "file": "requirements/system.qmd",
+        "line": 65
+      },
+      "rationale": "",
+      "status": "in-review",
+      "title": "Detectar anomalias de privilégio",
+      "type": "system-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "low",
+        "tags": "experience;mobile"
+      },
+      "body": "O sistema poderá oferecer uma credencial móvel para acesso presencial.\n\n### Rationale\n\nA necessidade depende de avaliação conjunta de segurança física e privacidade.",
+      "contentFingerprint": "42193bec4322f6cb086a244b71e6a2bdb7f512d2f07a03d1f9bfe26d24825aa8",
+      "id": "IAM-SYS-008",
+      "location": {
+        "anchor": "IAM-SYS-008",
+        "file": "requirements/system.qmd",
+        "line": 75
+      },
+      "rationale": "",
+      "status": "draft",
+      "title": "Oferecer credencial móvel corporativa",
+      "type": "system-requirement"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authentication;regression"
+      },
+      "body": "Verifica criação de sessão somente para credencial corporativa válida.",
+      "contentFingerprint": "050984e3e16a0d72461d58cacdcac4d33e97b2805731880c69261b29eda757f6",
+      "id": "IAM-TC-001",
+      "location": {
+        "anchor": "IAM-TC-001",
+        "file": "verification/test-cases.qmd",
+        "line": 6
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Autenticação com credencial válida",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "mfa;security"
+      },
+      "body": "Verifica bloqueio de papel privilegiado quando o segundo fator não é satisfeito.",
+      "contentFingerprint": "86c0346700ce86df14a74b0ec07ac5dd1ec091dd49f0bd0a091640fa0ec9756c",
+      "id": "IAM-TC-002",
+      "location": {
+        "anchor": "IAM-TC-002",
+        "file": "verification/test-cases.qmd",
+        "line": 12
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "MFA obrigatório para administrador",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "session;security"
+      },
+      "body": "Verifica invalidação de tokens após suspensão de conta.",
+      "contentFingerprint": "80d64f05d0ce9ddafa1e52b6158fe38891187cbeb093dd71214a10fa087d021f",
+      "id": "IAM-TC-003",
+      "location": {
+        "anchor": "IAM-TC-003",
+        "file": "verification/test-cases.qmd",
+        "line": 18
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Revogação de sessão suspensa",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;policy"
+      },
+      "body": "Verifica avaliação de sujeito, recurso, ação e contexto em uma política.",
+      "contentFingerprint": "b33d61446ddc77add1aa0d92bfaacf7ee85f323310fcf2043a5043e7092daa3d",
+      "id": "IAM-TC-004",
+      "location": {
+        "anchor": "IAM-TC-004",
+        "file": "verification/test-cases.qmd",
+        "line": 24
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Decisão por atributo",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "authorization;least-privilege"
+      },
+      "body": "Verifica que uma solicitação sem regra permissiva é negada.",
+      "contentFingerprint": "3b762589fea62b4fcdb5be890a55231970a4f8c2b5b362c36650e2f961436405",
+      "id": "IAM-TC-005",
+      "location": {
+        "anchor": "IAM-TC-005",
+        "file": "verification/test-cases.qmd",
+        "line": 30
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Negação sem regra permissiva",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;performance"
+      },
+      "body": "Verifica a resposta de autorização dentro do objetivo sob carga nominal.",
+      "contentFingerprint": "d12dff496e31c21a24c33111bbf90e5147996b0e17e3ca01e31637753425dcfc",
+      "id": "IAM-TC-006",
+      "location": {
+        "anchor": "IAM-TC-006",
+        "file": "verification/test-cases.qmd",
+        "line": 36
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Latência da decisão de acesso",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;provisioning"
+      },
+      "body": "Verifica criação de conta após evento de admissão válido.",
+      "contentFingerprint": "95c3def8d3f70a2d61600054b8ee298957a2115a04fce3be296a0c7ecadea080",
+      "id": "IAM-TC-007",
+      "location": {
+        "anchor": "IAM-TC-007",
+        "file": "verification/test-cases.qmd",
+        "line": 42
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Criação por evento de admissão",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "lifecycle;offboarding"
+      },
+      "body": "Verifica suspensão e encerramento de sessão após desligamento.",
+      "contentFingerprint": "c1ea9a47ed19e990c72a827e697eb570aad83e0fa81c0a19d6c4659aa3b97dc6",
+      "id": "IAM-TC-008",
+      "location": {
+        "anchor": "IAM-TC-008",
+        "file": "verification/test-cases.qmd",
+        "line": 48
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Suspensão por desligamento",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "lifecycle;review"
+      },
+      "body": "Verifica abertura de tarefa de revisão para o responsável adequado.",
+      "contentFingerprint": "b643c8ed0a484db4a19b4f8c368f56d18202521b263dfe6618be53f57b17266c",
+      "id": "IAM-TC-009",
+      "location": {
+        "anchor": "IAM-TC-009",
+        "file": "verification/test-cases.qmd",
+        "line": 54
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Campanha de revisão de acesso",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "audit;security"
+      },
+      "body": "Verifica correlação e integridade do evento da decisão de acesso.",
+      "contentFingerprint": "ea09d778a910e6abbab0c32ae038fafcc4038448718647fad55fb0ff326bb777",
+      "id": "IAM-TC-010",
+      "location": {
+        "anchor": "IAM-TC-010",
+        "file": "verification/test-cases.qmd",
+        "line": 60
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Registro de decisão de autorização",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "audit;retention"
+      },
+      "body": "Verifica consulta ordenada e disponibilidade da evidência retida.",
+      "contentFingerprint": "57f6405aab65540f867b44801f83ae6e014d56cda3561c444ce9b93a89728836",
+      "id": "IAM-TC-011",
+      "location": {
+        "anchor": "IAM-TC-011",
+        "file": "verification/test-cases.qmd",
+        "line": 66
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Consulta e retenção de trilha",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "recovery;security"
+      },
+      "body": "Verifica prova adicional de identidade antes da redefinição de credencial.",
+      "contentFingerprint": "82557b425e4661965588e2ac82cf8310dfbf2db06b811429e56c52c116826c6b",
+      "id": "IAM-TC-012",
+      "location": {
+        "anchor": "IAM-TC-012",
+        "file": "verification/test-cases.qmd",
+        "line": 72
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Recuperação reforçada",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "accessibility;portal"
+      },
+      "body": "Verifica navegação por teclado, foco visível e nomes acessíveis no portal.",
+      "contentFingerprint": "98e609e1b9c3941c7d8c98a8f104a1650ce3b4f935ed38f22cc9e35fae179892",
+      "id": "IAM-TC-013",
+      "location": {
+        "anchor": "IAM-TC-013",
+        "file": "verification/test-cases.qmd",
+        "line": 78
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Acessibilidade da autenticação",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "availability;resilience"
+      },
+      "body": "Verifica o objetivo mensal em exercício de monitoramento e failover.",
+      "contentFingerprint": "d262b8b8276badf594ba97c6af15086b61c2637cb2dd9c4647d805b2701ae6a4",
+      "id": "IAM-TC-014",
+      "location": {
+        "anchor": "IAM-TC-014",
+        "file": "verification/test-cases.qmd",
+        "line": 84
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Disponibilidade de autenticação",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "privacy;compliance"
+      },
+      "body": "Verifica ausência de atributos pessoais não necessários no evento de auditoria.",
+      "contentFingerprint": "a9eba8c9d8c916b159373463288df5f9467b5af794955a3527f815ed40b5148d",
+      "id": "IAM-TC-015",
+      "location": {
+        "anchor": "IAM-TC-015",
+        "file": "verification/test-cases.qmd",
+        "line": 90
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Minimização de evento pessoal",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "high",
+        "tags": "security;encryption"
+      },
+      "body": "Verifica TLS aprovado em trânsito e criptografia de segredos no armazenamento.",
+      "contentFingerprint": "9abeb4d72e6568e0bccb9d2a540827332234a8a561ffddcf00775ed6d17ea728",
+      "id": "IAM-TC-016",
+      "location": {
+        "anchor": "IAM-TC-016",
+        "file": "verification/test-cases.qmd",
+        "line": 96
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Criptografia de credenciais e segredos",
+      "type": "test-case"
+    },
+    {
+      "attributes": {
+        "priority": "medium",
+        "tags": "integration;oidc"
+      },
+      "body": "Verifica descoberta, emissão e validação de token OIDC com uma aplicação consumidora.",
+      "contentFingerprint": "fcad436fd69cc79a6af05f88df1aeba0359848c5309a7dd68e50fe4b292108af",
+      "id": "IAM-TC-017",
+      "location": {
+        "anchor": "IAM-TC-017",
+        "file": "verification/test-cases.qmd",
+        "line": 102
+      },
+      "rationale": "",
+      "status": "passed",
+      "title": "Federação OpenID Connect",
+      "type": "test-case"
+    }
+  ],
+  "referenceDate": "2026-08-26",
+  "relationCatalogVersion": "1",
+  "relations": [
+    {
+      "attributes": {},
+      "authoredFingerprint": "7c28ef3852347ee703a6a1be5e8d20e4a0295be23c72ec95a62747fd737764e5",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "64391849d4a81b6b81a2c08f1afaed724724db866a94c72c2d415fc60aa372da",
+      "source": "IAM-FUN-001",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-001",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b51676525fce13a76c5260a352b7e6ec93bdb66219f14544a5ab73af05a55dd2",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "bd4c9f5cd87e8dd37fd72ee8d789492261297024edcb079af80616f56ffc1ded",
+      "source": "IAM-FUN-001",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-001",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "48958065ffe9cc032af0889755354f68ef7ea89c8c288680395cfae67813a77c",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "021872ffc3a53dbe74ed2d996de555ed398cf9989435ab2c5735db48057b8544",
+      "source": "IAM-FUN-001",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-001",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "87ba6564478dfa1b94cf61f614bf54990c14c3d26c32cf3976b4cf26effff63f",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "8c33162e9280e9c9f5078fbaed18b31763025472db41c025250b98fe7e353cad",
+      "source": "IAM-FUN-002",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-001",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "de29811eed813290bce9b8af0d2e5936c683c325b014df20224c663a204cdcb4",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "a8ea9e2de03ea0b5dd05473ebe2bc9afdd20dc1b67a23c0065eb603b72051f1b",
+      "source": "IAM-FUN-002",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-001",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "c628a2959c07abda2765b9b75a079e9f2c5ae08eb4cd2acbb76d59e2efb573f3",
+      "authoredName": "mitigates",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "mitigation",
+      "semanticFingerprint": "6cb832f6f1d4c02d9edd3ae646e63adbe11309579a6a2d9b2a3f954b209838a2",
+      "source": "IAM-FUN-002",
+      "sourceRole": "mitigation",
+      "target": "IAM-RISK-001",
+      "targetRole": "risk"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "365af92c99ef527ddd3457783a8e435b814a9370c15627fb88b48b2ba3ca3eb5",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "92c02386493c8921b8353016dcaeac5263f9c61f85e3b74aec564730c75a81f9",
+      "source": "IAM-FUN-002",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-002",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "9594cbf305bfdf1dc84300cde68b53bb8a4c6f8670d3b8d0791d5e833dcfb0ac",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "e9c139fec9bab2c906f43c16ae46a8bbd5fef9709bc9d710b48a7d49d66cc7d9",
+      "source": "IAM-FUN-003",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-001",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "4039bf07a0734a4d7d3558dd55168edd075d84bc4efa19648f70fb59adc4cdb1",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "97db74aba37e37fbec2d70235674792da40ea79a0bd8fd6883110ca901cbb311",
+      "source": "IAM-FUN-003",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-001",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "d59cbc8d0399c143518996cdb36eabe5748f0effdac03ee2cc0850cf449b9878",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "6d92ec4a11a709b41f2c5a3659b3b8afbbcf7fc53e2579f948de41b3aacf5240",
+      "source": "IAM-FUN-003",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-003",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "c3d823760204d2f86f466351e8abcc6d41d71786d6c4f2d7b70b56f23cc6b68d",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "d66ff6428c7a5cbd2c580fd87af03e91345ed22cfda5dfe725e77bc2722c5702",
+      "source": "IAM-FUN-004",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-002",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "cc8073604a828dd838e11a8bcc64bb0b3b2d500b6834c9b668c954bac7577e51",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "fbe0db1c502dcd108a2a4e4733b77e423050fd8764b278c11f81c42a5f2ea68b",
+      "source": "IAM-FUN-004",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-002",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "e977ed1d6c8828124a92b8f8d88186a442d25af19bb7f1bc7a8e56e254e4c258",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "1a270851fa41204023bf9c475f84d6313ebde8f10a9bfc0024218e6279049952",
+      "source": "IAM-FUN-004",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-004",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "4aa7c5a6c15d5490c4e269eaa9aa4754dde9fa8a02377e90626a83a101b00d53",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "f1be751145232b1eb71c13b44bc35e932e13bf70593a8dcb437c0dfd3f7d25df",
+      "source": "IAM-FUN-005",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-002",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "0692536f575b44ca0ae947ec92f2b707c6af7a9afffdf143cdc66286c6b45af0",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "c2d55b5ad8884696c5a07f1cdc7353a642ce64ac7f92f450693212d56333c45e",
+      "source": "IAM-FUN-005",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-002",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "988e388fafb8a0bac3b182217d584758c74a65db05cae1bda14f74af184d75de",
+      "authoredName": "mitigates",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "mitigation",
+      "semanticFingerprint": "2b8cba3f86549442418dad3216c46b9bc193c19792e6da7e6f37df9334974eaa",
+      "source": "IAM-FUN-005",
+      "sourceRole": "mitigation",
+      "target": "IAM-RISK-002",
+      "targetRole": "risk"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "eed962bf1202a544fb0afd40ee7b6dee0ccebee4d31fa68d2b02685aefdc3e86",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "511ec66ef1104b4308c41f68fb7b0f5bb371822d14a11e4d59f1ef6f45f74982",
+      "source": "IAM-FUN-005",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-005",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "7f90aa04a7f76bc63829e0c499487d604f37409549b3b19641355bc88fb65f6a",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "4f226032f4724697446b556e50d8a6d013cb468914a9db9498f8ae7f7743de48",
+      "source": "IAM-FUN-006",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-002",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "ff659a8bb1517ae18a7117e13c050248371b3f69b6e84fc0098e1a6a4b4850b1",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "31f8a9a5a5e26e0600e822e4bca7f8ec06399a1c202bb7811bb95576caa9018e",
+      "source": "IAM-FUN-006",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-002",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b21626266ae55519170c62c5d2b3dc04339ddb6e7ff4a56d186b4cbb38a2aa5e",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "6bb19f65606e90116876a94671c07d243963a22699cc43b96492badc9e5a99e3",
+      "source": "IAM-FUN-006",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-006",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "dab025c6c118ac96b05509d2b9c3de44961f14b668de7df2dfd80586c447d140",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "def763f8ecdffb7845d194c42c5613e4362bb92f659b79a38977a4d84b43fdc9",
+      "source": "IAM-FUN-007",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-003",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "f323b642e7bc02faca07499d76eff031ccf5119427a0c3f2ed0cf95b5b612711",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "2d2822fb45532de43257fe7256ae1c63146b8844ff87e9828a2a4d9f3208a44f",
+      "source": "IAM-FUN-007",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-003",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "6c1d069fa2712735a739bd0b225c1636821f4e4f3c3dc187d92b748183740f2d",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "8c358e2bf0ed21399d9c986a4f6f9d0295d25d09a306dcacf4a89a5177034718",
+      "source": "IAM-FUN-007",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-007",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "f05de1510062d589ee67f7c6fb14bcf60437855dd4a82bfd095ec631bbc8c4db",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "3e3a41d050a4faf5b952cb2873d5a23c05434524ac9599420610e3ff9cc3242e",
+      "source": "IAM-FUN-008",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-003",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "41aefb68335ebe06a369bca9b017988739329302bb1373a009f120551e49b637",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "26b818423f5ac56e143378135bccaeb3624a570aedd2e9ab5ef474e5e94d58f0",
+      "source": "IAM-FUN-008",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-003",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "98182c3ec4240f1b272c781cdd117d6e80a711e2a178e680fe256987d84ecbbb",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "c95676e69382240ab3929a76a603bba9b58f51b0528c8b1b361c21fa8878fd86",
+      "source": "IAM-FUN-008",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-008",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "fd1fc7ea1368cedb1dae110d32326e73f48b8a414948101b033d00d96478ae3a",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "1dc52b63917b907146ea65400968c4c4f61ab428759371b1a20ff1673e4076d6",
+      "source": "IAM-FUN-009",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-003",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "690efae2de7157086c499635c3ca4c546694a4190b0bc8b7a02df21301c2b66e",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "a5a92c5aa60f0950a15d38365595395f23206654bc0bc71c415c0889cec13501",
+      "source": "IAM-FUN-009",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-003",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b191ab7ebf815446f70a265d5c232b528e30af5ae73f8fe0adebd369121730c8",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "7c6d2047530d1c00d5327d49f0180758837acb3ae73afcc9198c04e77c268793",
+      "source": "IAM-FUN-009",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-009",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "54578800908e665500afe6c55d7a6d6ebe889577541eb989e70b54c218fc6d44",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "7e609d77893986df44a35961e2758a355bca9a80be5980e26ac4d732abc4da2a",
+      "source": "IAM-FUN-010",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-004",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "9b079ef3d238565c21e29ae3aead54fd77148d016d2296c50c7be55eeaee6d47",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "d8378857ee39de408ab086b7543e89f9d71868a57b0f37a791ad9e4b966ebda3",
+      "source": "IAM-FUN-010",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-004",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "60af9cd5ab444eafee269ab1bc6e7c7bc9697776e83e94cf80ea333e20b7c2ca",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "592940e1f6c52afe8748dfc70b620a9133e6c3ccc75c13353030f01ba71c34ca",
+      "source": "IAM-FUN-010",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-010",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b6f15b330a1f3f516caf82ba89f9e412ac4a0e2a387606ff3c412770ca6a4c2d",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "76fe805337c80e0016ba02dc7bb71e8b32f162914749bd1e70850fc515a3c53c",
+      "source": "IAM-FUN-011",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-004",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "e6d530354c982963419664d2b884d7bdc3c71188208e5519c8aeb55c176ff5ad",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "612d196fe9e027f698e9879389e2366b770e745acf58be375b1d7ecde71150ab",
+      "source": "IAM-FUN-011",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-004",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "f4bb70d2db1914864b9f58e13efb4104969a0780b3de903fa2d5870027e1499c",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "7dde5fa3012cbfa090c970994ecaedafeeb0f659254feea09d9b87f5949282df",
+      "source": "IAM-FUN-011",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-011",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "8819487c368c280cdc649f98bce3454a900a2d480c463e57aae7a13cd14bec8c",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "6f78b22e12dbb9f7f367ac84b690c3ad0a0df4b6cca8bbb60f06a604da1a917e",
+      "source": "IAM-FUN-012",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-005",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "519854ebf3f2e4d3cfc77d7092c0c2d9ef6a631946e0e94cd1e2a2be7c597a33",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "9a9437b1d170ea7a3f77a81b668ecc6637aacae67fe7da0a7bdfd104499d6a46",
+      "source": "IAM-FUN-012",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-005",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "8b7b14bf6a9aa6462203f8018bfbcaeaac187219024e639881f00d91ff14ceb8",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "99635ce1e652b5ba2d87240183a7ed9207f9dae873100a7f9d5f33e374fc1371",
+      "source": "IAM-FUN-012",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-012",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "7de24c726f2cd771677882123a9ce50392e142bd39c58e71476a742a90ac0d95",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "b9debe9c5f5135019568d40aebf7dd3275a1ca18277643127f077c9d7b44a79c",
+      "source": "IAM-FUN-013",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-005",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "e355e8e7928de40909064c9cab8bb73bcdabb7267b6528f8a6c4affd8f79e514",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "93a40c9a45ba725ae959039987a41b83db1e8f0778ad6fc1d2fad1fefc73ed17",
+      "source": "IAM-FUN-014",
+      "sourceRole": "derived",
+      "target": "IAM-SYS-006",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "a48e83c191fcf510717a7a4339c2a9a4975fb5aa5d182c4603611ab730107c55",
+      "authoredName": "conflicts-with",
+      "impactDirection": "both",
+      "semanticFamily": "conflict",
+      "semanticFingerprint": "0de8ce26cce7ab01f351c87f4e74582bfeba7daa5f4d3b3d2157d9786b15a2d9",
+      "source": "IAM-FUN-015",
+      "sourceRole": "subject",
+      "target": "IAM-SYS-001",
+      "targetRole": "subject"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "4261ddfddc6094f449e5ccda3c15647c51b0018946a61a29348113fa0afbd663",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "6b224c187b8351d6984a90c88a969fffa8e59dc41113131e2cf787a90d09266b",
+      "source": "IAM-NFR-001",
+      "sourceRole": "derived",
+      "target": "IAM-STK-001",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b7260a331773e44ad051fd33f3264d166192c1130054b2ec2bd56f4fb0df3dca",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "81bd21ca5a54a76dce39c687b4a4597d812f0f4d17445e0b176247305b69aa81",
+      "source": "IAM-NFR-001",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-001",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b3e3439adab38f1396682bcea8fa7f617e70569c32a4d4b5a03eaa25111d2e07",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "b506124a73cd7176a8e18db7e3188299f20847f060db6221215a88b2ce8baf44",
+      "source": "IAM-NFR-001",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-016",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "c7fedbf889ff139654917cabf0e7be1f01ecf117a3c1a37946ede3a8e5b5d597",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "aa1e4891c446c0bab68ea8875b9626cbd11dee8b0afb242a682d4ec1de5b48fa",
+      "source": "IAM-NFR-002",
+      "sourceRole": "derived",
+      "target": "IAM-STK-003",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "6e5f7875e2fa739dbb783a0eec76aa27f9fa853f95a07c94f01576c6b1c29de8",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "c2867afadd1c4d3e8db27ff32064f40da7bbd063096f799ff3fa52e11fb709e4",
+      "source": "IAM-NFR-002",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-001",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "53c4f5f7937d087aa5147c205a7a52e5b7ad785fe922b0bd14c7aaea6c4478dc",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "80a1c84c0c506f6ef3b03026148247ea4d2e7600be3c24e40588cc15c3f651f9",
+      "source": "IAM-NFR-002",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-014",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "a2e1c6f4f4f33e0df15e5ae0de21a62c7e038f6ca70817cf5725ff0f3fa13cc2",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "c61880dd0678efc9ef1833f10830d701a787966bd71ba06a7d367e95afd311de",
+      "source": "IAM-NFR-003",
+      "sourceRole": "derived",
+      "target": "IAM-STK-002",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "9097b4dcd09bada0ce3982ba7cc92490d0781fcde6fdd24ff79f975f4b580216",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "f3ec79efd57422008c47954abe1f367fa75d76f6b8053304d585b90dd024a915",
+      "source": "IAM-NFR-003",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-004",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "8d3760684c7fb5e28817de16e6888e441e6c6865ca8fdfca1c06aae63b485276",
+      "authoredName": "mitigates",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "mitigation",
+      "semanticFingerprint": "e8068e0f27fd6faaae311b7ade4b2e48f52c12ba4dd0fd1ea74e29daa9e99dae",
+      "source": "IAM-NFR-003",
+      "sourceRole": "mitigation",
+      "target": "IAM-RISK-003",
+      "targetRole": "risk"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "ebd9396c8a96c7458622e1996d281d32afd44958832a25f9f193527d2998f2cf",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "2ef383b4eab407ff221949c1722d3227dae9c8a0a174df41f5a6cdfa8a13b19a",
+      "source": "IAM-NFR-003",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-015",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b23552bd8ed655a06287b67d83ab2bf873ff154755b4cc2a2d909d1012b8ba6f",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "cbd79a3f3d59991ca3dda5dd6ec09103c3c2c7fec1f8d71b7927be3aefd21ccc",
+      "source": "IAM-NFR-004",
+      "sourceRole": "derived",
+      "target": "IAM-STK-004",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "3606b84e375d98e8d67d8c2f16e3dbb9f64be4c7763717054a329d13f2107d07",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "06b01b4e4d60d69a04a1282ae6416ce178d39092cff1266c9aa78b3ab6dd2e07",
+      "source": "IAM-NFR-004",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-002",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "f5981515a83e8fddbce10f7a63de6f0c2ef6ba569e5b126c2db5450a1ced79d4",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "cc48c701a92405ed1833acdd2fd45bb584f6c9639f907ccb74d5d4b4c559171b",
+      "source": "IAM-NFR-004",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-006",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "283939cbe47cb5ce1edb67c6ee0c046098c2858e44eb74a7b12fd7fd62b9aac3",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "76f8fa6fc4a9500fe47c3477a6af8c39a52abc7ae1aa0944e7913ded776f1e57",
+      "source": "IAM-NFR-005",
+      "sourceRole": "derived",
+      "target": "IAM-STK-005",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "4ca2619162ff73b681964d15c54a020413c3419d4ee2d2ae5bbcffad442a2512",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "cdee3394d39af04fd0e2fad20a621f28310dbfd64bd467e5aa89966711457065",
+      "source": "IAM-NFR-005",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-004",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "49b8f45b6c1d4e4d8b820f1fe397928d78bcf6d466cc688928082c9c7c993501",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "ff4238081933d8aa2a81fce3044e77b7086fc740653141f16852158e23ec063c",
+      "source": "IAM-NFR-005",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-010",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "7f15686ba5b49a8771cc1834d9ec5bc308c736c6ce6317244ab116d3c5bf9614",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "e3bd255eb1a1633e86bff28edebb0ff56d025bd9a5b3209955e73764e65b7c78",
+      "source": "IAM-NFR-006",
+      "sourceRole": "derived",
+      "target": "IAM-STK-004",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "8ad0e270ebf7c6575bcaba9e8b1c59a512fb67bbed8ed5dfc0779117abfc7709",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "e6585a224d48a941be9e3c4cd79871b68eb92eff9eb3aec8f90f5418d2ddc8f1",
+      "source": "IAM-NFR-006",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-006",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "74ec1b95abd15f9a48098c99772c0d1b65002c3bbd3b9e43fb77af77c600646b",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "8a96ec4ecef080e8ab7b55c817f610e27a87027bacbfd8e14bf41bf15487076a",
+      "source": "IAM-NFR-006",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-013",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "21e55622661eb4f1c7abab6c52821ab9f819fbb1fcfca37e85550d5961583e2d",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "3b699e1505e288712ef328ce080935b5a48e04a1f71569103ea73c03e63625b6",
+      "source": "IAM-NFR-007",
+      "sourceRole": "derived",
+      "target": "IAM-STK-002",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "c66ad97dcc85fb3a0f53083136995f0e6353e087d61e7b634cc854434a9ba9db",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "0212b602e0edce32d90245408d49984afd57a67fce5a8c4b58d96fe8ed90eb00",
+      "source": "IAM-NFR-007",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-004",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "f04cdfb28ab7902a444669693f2b7a097918356e38e347148e9301e5a0a897e1",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "4dff685a3b5032765bbe44491678c605017ccdb8b2a4690928c88bccbcf93967",
+      "source": "IAM-NFR-007",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-011",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b1453b9b76f4411d64f71b11618e3868ee862763a1541e633b1cf2a9c25fecb7",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "c3d1cce7f6fa83c833cfc71a37b783147150e1dbf754424c995a933e05ac77f9",
+      "source": "IAM-NFR-008",
+      "sourceRole": "derived",
+      "target": "IAM-STK-003",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "07c208424289ff1539849e260955daf063c1397237a3df2db8387e85ac8653cd",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "a648c2ae1e894aa6e5d6ebdfe3d90b091e933e600e87412df64159a6065af2b4",
+      "source": "IAM-NFR-008",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-005",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "bf07fb4c6051fb8c58494ffe84a03025ebb552e198c7159b94fbf29c5c83f14d",
+      "authoredName": "mitigates",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "mitigation",
+      "semanticFingerprint": "66edb0d7804a2cb85144730c46edc4d7e7759d0a62525f2da1ae016529c023b0",
+      "source": "IAM-NFR-008",
+      "sourceRole": "mitigation",
+      "target": "IAM-RISK-004",
+      "targetRole": "risk"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "911de33f9cdd444c5bf7a700122da5c2eccaefddd0d6941d27bc5e1c3482a7c3",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "d254fad5ac1a1256a54980090a7919335655f9b150552cfc62fa8d11e0f3c34e",
+      "source": "IAM-NFR-008",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-012",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "40f8a3be07398e349707df2f3f69943d12be84b0e4213dce62285a7f68ff002e",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "b78d1989ba2f248dad985543bbf09f2421aa908af79d8f420baf4850700488b5",
+      "source": "IAM-NFR-009",
+      "sourceRole": "derived",
+      "target": "IAM-STK-003",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "74864b0036ab2d4d3826e93ffd648674234dd9253fd5f1399c3f5082f0799b87",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "3344f42b2cb56b91ac99e20aeeb6bbd0641698bdba095fdf876cdb42fd329bc2",
+      "source": "IAM-NFR-010",
+      "sourceRole": "derived",
+      "target": "IAM-STK-004",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "d55f2c2b7ff785f3cabfc95cf89137cc71b755120c928e4fedea8fc1ede1809d",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "7905c2a2fd6bc206a2d2ddadae2477c7cf9db0a30dc750d1ffa21ebdd44a3e20",
+      "source": "IAM-SYS-001",
+      "sourceRole": "derived",
+      "target": "IAM-STK-001",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "8f7b4bff42e83839c483f7ee424dfd47dd8ad6f772cd4cee35902c5bb984e61f",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "a6fae75c50e8dd01695775a91de7526872844599d4dcd4fa3e32575b1c7898e2",
+      "source": "IAM-SYS-001",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-001",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "55a42b6208a90d209bc91e29ed92d5be23fe2bc7b1d33e3f8bbfd7d2f7ba1a5b",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "4813bccd9410133ae29dd812882fa3b488fb4057080058f35b34f7b06d8f93e9",
+      "source": "IAM-SYS-001",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-001",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "f1217963fca8a07b26bf10d25ba851c533cc7a42185472e565fea71c64c787d9",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "ca90b2d4d713a842819831050589ec0c9eb2b5c964d5318af9ef9194918dd443",
+      "source": "IAM-SYS-002",
+      "sourceRole": "derived",
+      "target": "IAM-STK-002",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "73da95d6b6a4b61ae46a52a4d0f8c0a38754c8e20ee9500b0db1eebdfa53e0e4",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "a19777a2d65f8746af77d4a394ab741e09e7d5827a7e35afcbe8f6d3a206f79f",
+      "source": "IAM-SYS-002",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-002",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "498206056c599dda03cf77b0d1c549b5971b9c9c169c1bec23173d6e746d96b3",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "8f5eed328a6b9b305a1ddb5bdbd22cde420bd1a795780189793ff1017338b9b0",
+      "source": "IAM-SYS-002",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-004",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "dd43578319046a124137a7619e072410e9e595735ddae9cc508b1a27c8b630b9",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "e17f5800db043af046713f8ff8cdfcd21029300ba3f9a7cfe3a8f71239610cd1",
+      "source": "IAM-SYS-003",
+      "sourceRole": "derived",
+      "target": "IAM-STK-003",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "e49dc546e0d60c5861c5a32ceab3b135bbfb715616c2c449a1335974ae95365c",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "6f45da1ff0c564054d728104e8dc0900e79bef6fba229830ce285ca9bd70a41a",
+      "source": "IAM-SYS-003",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-003",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "c444aa54af89176ed4e94cfc90aa615a9bdadcc1a5e54a982d6e97dcba688326",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "72f0620fbd53b3ffe537138a948c299eb3e4579cffc55c07a01c6645ad190842",
+      "source": "IAM-SYS-003",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-007",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "8dab95bd72aa71cb5ee1c0f9b5e04367d771a372a36b18fb57574b7ce3027ebb",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "8900484b1fa764a5759c374dc48b48cb605f20e3c228b02b52e3e291f293ef3e",
+      "source": "IAM-SYS-004",
+      "sourceRole": "derived",
+      "target": "IAM-STK-005",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "a048248b0df0b49804f81e944901a0f375c0c0bb7597191a966b4fea8a40ceef",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "5c7253419c22727de2546d2325a712e5aa9e5ecd6cdb0ff80cbf57f6f9161f24",
+      "source": "IAM-SYS-004",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-004",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "dee93959f5692c40474a06dda916b3f2ec3467e68bb9a333c64d6c8380dd85c0",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "a94de166c439f9236d6885ad186462c40621d4377b85f70f72f2b59e425590df",
+      "source": "IAM-SYS-004",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-010",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "22b2b6a08242bf895fd58311981c7c100ded30f043f86ec4d4fff69043a9e95b",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "b3d6025bfae171667e44c72f05515d9d9c2b461c8203a149e9af41651c4d0f5f",
+      "source": "IAM-SYS-005",
+      "sourceRole": "derived",
+      "target": "IAM-STK-003",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "e3725c168041a742e487c9fc606760432c833e233c9962985725bc543e756c7b",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "65668abfd3796cfab3ba7c224996c12101c158e013f47c9e8426008bea95b11b",
+      "source": "IAM-SYS-005",
+      "sourceRole": "requirement",
+      "target": "IAM-COMP-005",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b6c5bf5f90287457ce0efe0729f34b77e2789e24d5cb618ff0b9e32f96b45447",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "f4d6866b00369e16f18f882218b960c815b74e96ae86df4e0c41b381b6201c09",
+      "source": "IAM-SYS-005",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-012",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "fee666c34f84fbf996e7db369a1e8a13eaefd7c14e90f4ce827037b79642ae46",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "dc9bb8458a7dfd7b1d54c09b668cbb7f640e66e499df7860a118ba477cb567a6",
+      "source": "IAM-SYS-006",
+      "sourceRole": "derived",
+      "target": "IAM-STK-004",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "40c703a3c31e28889f984eb9c69d5ccb522ae8555535694d66f117c26fe7459f",
+      "authoredName": "implemented-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "implementation",
+      "semanticFingerprint": "7fc1d4e9a94f35414d9f58c7690b027d6575e92e685bb0eea96873b604bc9ea9",
+      "source": "IAM-SYS-006",
+      "sourceRole": "requirement",
+      "target": "IAM-IF-001",
+      "targetRole": "implementation-artifact"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "dd34d931e7e48f344aa409c8645453187614cd3beaa21d096c84658427688a09",
+      "authoredName": "verified-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "verification",
+      "semanticFingerprint": "b56152d9a5b1bf02a63cc8b33ab1346b9a6e22287f5ce3bd5f906bc9ce69a0f8",
+      "source": "IAM-SYS-006",
+      "sourceRole": "requirement",
+      "target": "IAM-TC-017",
+      "targetRole": "test"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "ae35a213e011537845a99bcd4ca4fa443b6b6fc9cbadcb756f997547268213e1",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "78bc998ac92a4b9ba5eef4fb731556f8e424cc8bf0002531d1da346692bc96a9",
+      "source": "IAM-SYS-007",
+      "sourceRole": "derived",
+      "target": "IAM-STK-005",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "b0eabcf00f1a0b6f35eff96cda40b462f13ae75b773f840ca1ef5cc9baaccfb3",
+      "authoredName": "derives-from",
+      "impactDirection": "target_to_source",
+      "semanticFamily": "derivation",
+      "semanticFingerprint": "9b6e5c29e1b268c32e1feb09294cc91941cc6a0cf49c4b11e50103fb7468aad9",
+      "source": "IAM-SYS-008",
+      "sourceRole": "derived",
+      "target": "IAM-STK-004",
+      "targetRole": "source"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "0684e0b44783035b2e1cfbd4b4404cd9e2679d0b93db95c799690ef35c26e7c8",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "5e0372391fd85ee87a00e3099990458e72bd30a9adff43d5ee002a4744fc49d8",
+      "source": "IAM-TC-001",
+      "sourceRole": "test",
+      "target": "IAM-EVD-001",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "549ca309e84e43efb53da800ef5bc0ec8c7c9bf483908e53eee381b9e4ee613f",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "9a498cfd85f25ae175ec7123b75c954d4972ce99a2f0dd1790c5a88cbf1ed4ed",
+      "source": "IAM-TC-002",
+      "sourceRole": "test",
+      "target": "IAM-EVD-002",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "72427cb848f8ebdda132a81b78d69cae78ebeeac2e432f0c79c39430c96c9ca3",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "5d30a39db7a9795b16fc483ec920424dccba4e6d0a3a03174fb660d7755a2414",
+      "source": "IAM-TC-003",
+      "sourceRole": "test",
+      "target": "IAM-EVD-003",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "88700ac95cfcce94ad3bf69762ab90a8a4a419a59d42f8d5260361e544fdf73a",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "f1b073b51f43377a60801e2edbdce893c23bf972020061f9f0757e2b93944ed7",
+      "source": "IAM-TC-004",
+      "sourceRole": "test",
+      "target": "IAM-EVD-004",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "508d627b3621c3ed02188e10f0dd6d7999fe9c2f329a978ca4553dd65e51ec8e",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "44de74166a7a5d7afe0f134ef78274435b21a67dc632b113fa1efea865add928",
+      "source": "IAM-TC-005",
+      "sourceRole": "test",
+      "target": "IAM-EVD-005",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "31b09047c05a478e5f16f969294ffd332701da5524322f2af5e225cd76a635c4",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "048a740b9febdec70cf3e6fee709b9b4ff74d9efcb80cdda987a279d286884d1",
+      "source": "IAM-TC-006",
+      "sourceRole": "test",
+      "target": "IAM-EVD-006",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "82c049b6eafa1ce7dc2ab386c9d04cdf0b9e4953c2c0be0ab64723bd31d8dae9",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "0d55a30de6b9fae92fbf786e77243598146c34b85a0e2f63f8d9e9ca106acf05",
+      "source": "IAM-TC-007",
+      "sourceRole": "test",
+      "target": "IAM-EVD-007",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "9cedd2f452d0279343e08253c1a2ff74d209d74f0a700ca63e6e77c11e391b9f",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "13b270246c3dcdd1df3b6ab83f833ae83d1da589d51ba64cd2d5cb2006c8b01b",
+      "source": "IAM-TC-008",
+      "sourceRole": "test",
+      "target": "IAM-EVD-008",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "c5aab217f2e70b4e998516d55ab6bee11fed857c9424a19421f6dacdc4dda20d",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "50d6a2559295b40e07b86ed645cfc1edef7d8ca52bc4e3e312ce6373ed782c96",
+      "source": "IAM-TC-009",
+      "sourceRole": "test",
+      "target": "IAM-EVD-009",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "2de91d74cbd145868ad7c50fd916c24108be8f97de461ec9d6f8e958d20d7f37",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "36a4c53a7b13ce4328c22aa2a5ccd48f4715d11f6f08d4e7ee12f3ef165525df",
+      "source": "IAM-TC-010",
+      "sourceRole": "test",
+      "target": "IAM-EVD-010",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "67cf4098550ccb5268397b9c33ea105c5ceed2605ebc2ff03b2959cc9f615236",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "90910c50d148c80ac2f3b51734ff26dfd778da24798801674900f8fd190b74c9",
+      "source": "IAM-TC-011",
+      "sourceRole": "test",
+      "target": "IAM-EVD-011",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "7edea114efbf7a4cd69d15d344eca22e03e622113207c2663e2e2524675befe9",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "92ae8b835859e0c7c4d1be44af6eeced8ef4bfd6460bc756e174e6fb504e27f5",
+      "source": "IAM-TC-012",
+      "sourceRole": "test",
+      "target": "IAM-EVD-012",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "cc0f28bd274b4076ce7edf1d92130e5ae87238e96bac519a82e6766c4f37b76e",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "0438ef3c066e8020abf4efdba7835c0468f5211c9f589aa073915b236fe6237e",
+      "source": "IAM-TC-013",
+      "sourceRole": "test",
+      "target": "IAM-EVD-013",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "1387f51429b8935a30911bb57b5ded5cad6a8fa99be215d1110493a9741afc6a",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "cab61a08bd6e634122f4b3d509c62341fc81f2644c10f482146864db5488ff13",
+      "source": "IAM-TC-014",
+      "sourceRole": "test",
+      "target": "IAM-EVD-014",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "13dd5c1e7300911f4320c87137a4b5a75a2578d511ff3a1d848b9f82bfb101b9",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "a283dd3ef36ede928ddbb066b8659a24a8c9e0fb037b4eaaf62baa5f4518125a",
+      "source": "IAM-TC-015",
+      "sourceRole": "test",
+      "target": "IAM-EVD-015",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "7e07e3420a70b57341fbd07ffb16b30088892beaa98d66756dc9a809b2643999",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "ab0618fadcabb79b3fa1d6f2ffde61a2471ce8c52ce594f322a6c31be85d36ab",
+      "source": "IAM-TC-016",
+      "sourceRole": "test",
+      "target": "IAM-EVD-016",
+      "targetRole": "evidence"
+    },
+    {
+      "attributes": {},
+      "authoredFingerprint": "0ea73652891eaa560e23cc14fa7f2bac9700b231e72c9107f4be5261a16c1577",
+      "authoredName": "evidenced-by",
+      "impactDirection": "source_to_target",
+      "semanticFamily": "evidence",
+      "semanticFingerprint": "fb21f98cc8028158d7cc64fc0705207bab07d350f9b0653ca6b44c3de519934a",
+      "source": "IAM-TC-017",
+      "sourceRole": "test",
+      "target": "IAM-EVD-017",
+      "targetRole": "evidence"
+    }
+  ],
+  "report": {
+    "configurationPresent": true,
+    "findings": {
+      "byCode": {},
+      "counts": {
+        "error": 0,
+        "info": 0,
+        "total": 0,
+        "warning": 0
+      }
+    },
+    "gates": [
+      {
+        "actual": 0,
+        "denominator": null,
+        "name": "max-errors",
+        "passed": true,
+        "scope": "project",
+        "threshold": 0
+      },
+      {
+        "actual": 100.0,
+        "denominator": 26,
+        "name": "min-implementation-trace",
+        "passed": true,
+        "scope": "approved-requirements",
+        "threshold": 100.0
+      },
+      {
+        "actual": 100.0,
+        "denominator": 26,
+        "name": "min-implementation-effective",
+        "passed": true,
+        "scope": "approved-requirements",
+        "threshold": 100.0
+      },
+      {
+        "actual": 100.0,
+        "denominator": 26,
+        "name": "min-verification-trace",
+        "passed": true,
+        "scope": "approved-requirements",
+        "threshold": 100.0
+      },
+      {
+        "actual": 100.0,
+        "denominator": 26,
+        "name": "min-verification-successful",
+        "passed": true,
+        "scope": "approved-requirements",
+        "threshold": 100.0
+      },
+      {
+        "actual": 100.0,
+        "denominator": 26,
+        "name": "min-evidence",
+        "passed": true,
+        "scope": "approved-requirements",
+        "threshold": 100.0
+      },
+      {
+        "actual": 0,
+        "denominator": null,
+        "name": "require-risk-mitigation",
+        "passed": true,
+        "scope": "project",
+        "threshold": 0
+      }
+    ],
+    "generator": {
+      "name": "quarto-needs",
+      "version": "0.1.0"
+    },
+    "profile": "strict",
+    "referenceDate": "2026-08-26",
+    "schemaVersion": "1",
+    "scopes": {
+      "approved-high-unverified": {
+        "breakdowns": {
+          "priority": {},
+          "status": {},
+          "type": {}
+        },
+        "coverage": {
+          "evidence": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          },
+          "implementation-effective": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          },
+          "implementation-trace": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          },
+          "verification-successful": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          },
+          "verification-trace": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          }
+        },
+        "denominator": 0,
+        "gaps": {
+          "evidence": [],
+          "implementation-effective": [],
+          "verification-successful": []
+        },
+        "name": "approved-high-unverified"
+      },
+      "approved-requirements": {
+        "breakdowns": {
+          "priority": {
+            "high": 19,
+            "medium": 7
+          },
+          "status": {
+            "approved": 26
+          },
+          "type": {
+            "functional-requirement": 12,
+            "non-functional-requirement": 8,
+            "system-requirement": 6
+          }
+        },
+        "coverage": {
+          "evidence": {
+            "covered": 26,
+            "percent": 100.0,
+            "total": 26
+          },
+          "implementation-effective": {
+            "covered": 26,
+            "percent": 100.0,
+            "total": 26
+          },
+          "implementation-trace": {
+            "covered": 26,
+            "percent": 100.0,
+            "total": 26
+          },
+          "verification-successful": {
+            "covered": 26,
+            "percent": 100.0,
+            "total": 26
+          },
+          "verification-trace": {
+            "covered": 26,
+            "percent": 100.0,
+            "total": 26
+          }
+        },
+        "denominator": 26,
+        "gaps": {
+          "evidence": [],
+          "implementation-effective": [],
+          "verification-successful": []
+        },
+        "name": "approved-requirements"
+      },
+      "catalog": {
+        "breakdowns": {
+          "priority": {
+            "high": 19,
+            "low": 3,
+            "medium": 11
+          },
+          "status": {
+            "approved": 26,
+            "disapproved": 1,
+            "draft": 3,
+            "in-review": 3
+          },
+          "type": {
+            "functional-requirement": 15,
+            "non-functional-requirement": 10,
+            "system-requirement": 8
+          }
+        },
+        "coverage": {
+          "evidence": {
+            "covered": 26,
+            "percent": 78.8,
+            "total": 33
+          },
+          "implementation-effective": {
+            "covered": 26,
+            "percent": 78.8,
+            "total": 33
+          },
+          "implementation-trace": {
+            "covered": 26,
+            "percent": 78.8,
+            "total": 33
+          },
+          "verification-successful": {
+            "covered": 26,
+            "percent": 78.8,
+            "total": 33
+          },
+          "verification-trace": {
+            "covered": 26,
+            "percent": 78.8,
+            "total": 33
+          }
+        },
+        "denominator": 33,
+        "gaps": {
+          "evidence": [],
+          "implementation-effective": [
+            "IAM-FUN-013",
+            "IAM-FUN-014",
+            "IAM-FUN-015",
+            "IAM-NFR-009",
+            "IAM-NFR-010",
+            "IAM-SYS-007",
+            "IAM-SYS-008"
+          ],
+          "verification-successful": [
+            "IAM-FUN-013",
+            "IAM-FUN-014",
+            "IAM-FUN-015",
+            "IAM-NFR-009",
+            "IAM-NFR-010",
+            "IAM-SYS-007",
+            "IAM-SYS-008"
+          ]
+        },
+        "name": "catalog"
+      },
+      "evidence-gaps": {
+        "breakdowns": {
+          "priority": {},
+          "status": {},
+          "type": {}
+        },
+        "coverage": {
+          "evidence": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          },
+          "implementation-effective": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          },
+          "implementation-trace": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          },
+          "verification-successful": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          },
+          "verification-trace": {
+            "covered": 0,
+            "percent": 100.0,
+            "total": 0
+          }
+        },
+        "denominator": 0,
+        "gaps": {
+          "evidence": [],
+          "implementation-effective": [],
+          "verification-successful": []
+        },
+        "name": "evidence-gaps"
+      }
+    },
+    "summary": {
+      "exitCode": 0,
+      "gateFailures": 0,
+      "structuralErrors": false
+    }
+  },
+  "representationFingerprint": "3ee280b60ff04e7ed67e9e34cfc08caf058cebcc278453dd07dda50df67d6fb7",
+  "ruleSetVersion": "1",
+  "schemaVersion": "1",
+  "semanticGraphFingerprint": "64e93f483b567b71139e4b34b8ba1909789ff7c87deb92218652069cbc6757f0",
+  "valid": true
+}
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/examples/book/.quarto-needs/needs.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/examples/book/.quarto-needs/needs.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/examples/book/.quarto-needs/needs.json	2026-08-25 15:32:20.420021417 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/examples/book/.quarto-needs/needs.json	2026-08-26 15:24:42.704551406 -0300
@@ -736,21 +736,21 @@
             "passed": true,
             "scope": "project",
             "threshold": 0
           }
         ],
         "generator": {
           "name": "quarto-needs",
           "version": "0.1.0"
         },
         "profile": "strict",
-        "referenceDate": "2026-08-25",
+        "referenceDate": "2026-08-26",
         "schemaVersion": "1",
         "scopes": {
           "approved-high-unverified": {
             "breakdowns": {
               "priority": {},
               "status": {},
               "type": {}
             },
             "coverage": {
               "evidence": {
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/Makefile .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/Makefile
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/Makefile	2026-08-25 11:07:23.571108559 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/Makefile	2026-08-26 14:14:07.574423864 -0300
@@ -1,11 +1,11 @@
-.PHONY: setup test scan check coverage example preview-example sync-example check-example render-example render-example-all
+.PHONY: setup test scan check coverage example preview-example sync-example check-example render-example render-example-all baseline-example diff-example impact-example
 .DEFAULT_GOAL := test
 
 VENV_PYTHON := .venv/bin/python
 
 .venv/bin/python:
 	python3 -m venv .venv
 
 setup: .venv/bin/python
 	$(VENV_PYTHON) -m pip install -e ".[test]"
 
@@ -32,10 +32,19 @@
 check-example:
 	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book check
 
 render-example:
 	quarto render examples/book
 
 render-example-all:
 	quarto render examples/book --to html
 	quarto render examples/book --to docx
 	quarto render examples/book --to pdf
+
+baseline-example:
+	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book baseline create --force
+
+diff-example:
+	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book diff examples/book/baselines/quarto-needs.json
+
+impact-example:
+	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json --recompute-with current
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/pyproject.toml .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/pyproject.toml
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/pyproject.toml	2026-08-25 09:13:06.774378133 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/pyproject.toml	2026-08-25 16:57:23.887281125 -0300
@@ -17,18 +17,19 @@
   "Operating System :: OS Independent",
 ]
 
 [project.scripts]
 quarto-needs = "quarto_needs.cli:main"
 
 [project.optional-dependencies]
 test = [
   "pytest>=8",
   "jsonschema>=4.23",
+  "referencing",
 ]
 
 [tool.setuptools.packages.find]
 where = ["src"]
 
 [tool.pytest.ini_options]
 testpaths = ["tests"]
 pythonpath = ["src"]
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/README.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/README.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/README.md	2026-08-25 15:21:02.005590574 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/README.md	2026-08-26 15:14:32.686146959 -0300
@@ -372,30 +372,97 @@
 ### Profiles and exit codes
 
 | Profile | Structural failure | Semantic gate failure |
 |---|---|---|
 | `advisory` | 1 | 0 |
 | `default` | 1 | 0 (reported, not enforced) |
 | `strict` | 1 | 1 |
 
 A broken configuration exits 2 from every command.
 
+- `3`: operational failure — an artifact could not be read or written. The
+  message names the artifact; anything already written is left in place.
+
+### Baseline, diff, and impact
+
+`baseline create` snapshots the current graph — objects, authored relations,
+findings, and the projected report — into `baselines/quarto-needs.json`. It
+refuses to overwrite an existing baseline unless `--force` is given, and it
+refuses to write anything for a structurally invalid project unless
+`--allow-invalid` is given. That flag produces a diagnostic artifact marked
+`valid: false`; only `baseline inspect` accepts it. `diff` and `impact`
+reject it outright, because duplicate IDs make it ambiguous which object a
+comparison would even be comparing.
+
+`diff <baseline>` classifies what changed since that snapshot: added and
+removed objects, modifications by field, added and removed relations,
+relocation, and regressions in findings, metrics, and gates. A changed ID is
+reported as a removal plus an addition, never a rename — rename detection is
+heuristic, so Milestone 3 deliberately leaves it out rather than guess.
+
+Two of those classifications are easy to get wrong by intuition:
+
+- **Relocation is keyed on the file that declares an object, not its line.**
+  Moving `IAM-SYS-001` from `system.qmd` into `system-v2.qmd` is a
+  relocation; inserting a paragraph above it, which shifts every line number
+  underneath, is not. Fingerprints already exclude line numbers for exactly
+  this reason — otherwise one edited sentence would relocate every object
+  below it in the file.
+- **An authored alias flip is a representation change, never a relation
+  add/remove.** Rewriting `verified-by="IAM-TC-001"` on the requirement as
+  `verifies="IAM-SYS-001"` on the test case names the same edge from its
+  other end. The relation's semantic fingerprint sorts its two endpoints by
+  role, not by which side authored the attribute, so the fingerprint is
+  unchanged and `diff` reports it under `relations.representationChanged`
+  instead of manufacturing a spurious removal paired with an addition.
+
+Two guards decide which categories of delta mean anything at all. When the
+baseline's configuration fingerprint or reference date differs from the
+current run, `diff` emits a `configuration-changed` or `reference-date-changed`
+notice and suppresses every derived delta: findings, metrics, and gates were
+computed under different rules or a different date on each side, so their
+difference is not a project change. `--recompute-with current` re-resolves
+the baseline's authored relations through the *current* relation catalog, so
+semantic comparison is meaningful again after a catalog upgrade — but
+derived deltas stay suppressed until both sides are produced under the same
+configuration and the same reference date.
+
+`impact <baseline>` traverses the union of the baseline and current graphs,
+so a removed node or edge stays explainable instead of disappearing, and
+follows each relation's catalog `impactDirection`. Every result carries an
+explicit path, a distance, a classification (`direct` or `transitive`), and
+a priority; there is deliberately no risk score, since a single number would
+hide the path that justifies it. `impact` refuses a baseline whose
+configuration fingerprint or reference date differs from the current run
+unless `--recompute-with current` is supplied, so one policy always governs
+a traversal; under that flag, derived deltas remain suppressed, exactly as
+in `diff`.
+
+Determinism means byte-identical output for a fixed configuration **and** a
+fixed reference date. `SOURCE_DATE_EPOCH` (interpreted in UTC) fixes the
+latter; left unset, the reference date is today, which is why diffing
+against yesterday's baseline the next morning reports
+`reference-date-changed` even when the project itself has not moved.
+
 ## Commands
 
 ```bash
 quarto-needs scan                                    # build the canonical graph
 quarto-needs check                                   # validate and print findings
 quarto-needs coverage                                # legacy six-key metrics
 quarto-needs trace SYS-REQ-042                       # upstream/downstream IDs
 quarto-needs export --output graph.json              # write the v1 graph
 quarto-needs quality --format json --output q.json   # scoped metrics, findings, gates
 quarto-needs query approved-high-unverified          # ordered IDs for a named query
+quarto-needs baseline create                         # snapshot the graph to baselines/quarto-needs.json
+quarto-needs diff baselines/quarto-needs.json         # classify what changed since that snapshot
+quarto-needs impact baselines/quarto-needs.json       # trace what those changes reach
 ```
 
 `quality` writes its `--output` artifact atomically and keeps it even when a
 gate fails, so CI can publish the report that explains the failure. `--root`
 selects the project directory for every command.
 
 ## Current validation rules
 
 The rule engine grew from four embedded checks into the configurable catalog
 documented above. Structural, referential, and process validation now share one
@@ -445,24 +512,24 @@
 - relation constraints;
 - configurable process rules;
 - CI severity policies.
 
 ### 0.4 — Source traceability
 - code/test scanners;
 - `@implements` and `@verifies` annotations;
 - semantic symbols as graph nodes;
 - Tree-sitter backend.
 
-### 0.5 — Change management
-- Git baselines;
-- semantic diff;
-- graph-based impact analysis.
+### 0.5 — Change management (shipped)
+- baselines, semantic diff, and graph-based impact analysis — see
+  "Baseline, diff, and impact" above for `baseline create`/`baseline
+  inspect`, `diff`, and `impact`.
 
 ### Later
 - JSON/CSV/ReqIF;
 - VS Code extension;
 - GitHub/Jira/external artifacts;
 - GUI.
 
 ## Design principles
 
 - Requirements as Code
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/schemas/baseline-v1.schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/baseline-v1.schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/schemas/baseline-v1.schema.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/baseline-v1.schema.json	2026-08-26 01:09:31.868644198 -0300
@@ -0,0 +1,75 @@
+{
+  "$schema": "https://json-schema.org/draft/2020-12/schema",
+  "$id": "https://quarto-needs.dev/schema/baseline-v1.schema.json",
+  "title": "Quarto-Needs baseline v1",
+  "type": "object",
+  "additionalProperties": false,
+  "required": ["schemaVersion", "generator", "relationCatalogVersion", "ruleSetVersion", "referenceDate", "configurationFingerprint", "valid"],
+  "properties": {
+    "schemaVersion": {"const": "1"},
+    "generator": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["name", "version"],
+      "properties": {"name": {"type": "string"}, "version": {"type": "string"}}
+    },
+    "relationCatalogVersion": {"type": "string"},
+    "ruleSetVersion": {"type": "string"},
+    "referenceDate": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
+    "configurationFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
+    "semanticGraphFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
+    "representationFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
+    "valid": {"type": "boolean"},
+    "objects": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["id", "type", "title", "status", "body", "rationale", "attributes", "location", "contentFingerprint"],
+        "properties": {
+          "id": {"type": "string"},
+          "type": {"type": "string"},
+          "title": {"type": "string"},
+          "status": {"type": "string"},
+          "body": {"type": "string"},
+          "rationale": {"type": "string"},
+          "attributes": {"type": "object"},
+          "location": {
+            "type": ["object", "null"],
+            "additionalProperties": false,
+            "required": ["file", "line"],
+            "properties": {
+              "file": {"type": "string"},
+              "line": {"type": "integer"},
+              "anchor": {"type": ["string", "null"]}
+            }
+          },
+          "contentFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
+        }
+      }
+    },
+    "relations": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["source", "authoredName", "target", "semanticFamily", "sourceRole", "targetRole", "attributes", "authoredFingerprint", "semanticFingerprint"],
+        "properties": {
+          "source": {"type": "string"},
+          "authoredName": {"type": "string"},
+          "target": {"type": "string"},
+          "semanticFamily": {"type": "string"},
+          "sourceRole": {"type": "string"},
+          "targetRole": {"type": "string"},
+          "impactDirection": {"type": "string"},
+          "attributes": {"type": "object"},
+          "authoredFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
+          "semanticFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
+        }
+      }
+    },
+    "findings": {"type": "array", "items": {"type": "object"}},
+    "declarations": {"type": "array", "items": {"type": "object"}},
+    "report": {"type": "object"}
+  }
+}
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/schemas/diff-v1.schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/diff-v1.schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/schemas/diff-v1.schema.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/diff-v1.schema.json	2026-08-26 10:00:03.963170253 -0300
@@ -0,0 +1,68 @@
+{
+  "$schema": "https://json-schema.org/draft/2020-12/schema",
+  "$id": "https://quarto-needs.dev/schema/diff-v1.schema.json",
+  "title": "Quarto-Needs diff v1",
+  "type": "object",
+  "additionalProperties": false,
+  "required": ["schemaVersion", "referenceDate", "recomputed", "notices", "objects", "relations", "findings", "metrics", "gates", "empty"],
+  "properties": {
+    "schemaVersion": {"const": "1"},
+    "referenceDate": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["baseline", "current"],
+      "properties": {"baseline": {"type": "string"}, "current": {"type": "string"}}
+    },
+    "recomputed": {"type": "boolean"},
+    "notices": {
+      "type": "array",
+      "items": {"enum": ["configuration-changed", "reference-date-changed"]}
+    },
+    "objects": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["added", "removed", "modified", "relocated"],
+      "properties": {
+        "added": {"type": "array", "items": {"type": "string"}},
+        "removed": {"type": "array", "items": {"type": "string"}},
+        "modified": {
+          "type": "array",
+          "items": {
+            "type": "object",
+            "additionalProperties": false,
+            "required": ["id", "fields"],
+            "properties": {"id": {"type": "string"}, "fields": {"type": "array", "items": {"type": "string"}}}
+          }
+        },
+        "relocated": {"type": "array", "items": {"type": "object"}}
+      }
+    },
+    "relations": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["added", "removed", "representationChanged"],
+      "properties": {
+        "added": {"type": "array", "items": {"type": "object"}},
+        "removed": {"type": "array", "items": {"type": "object"}},
+        "representationChanged": {"type": "array", "items": {"type": "object"}}
+      }
+    },
+    "findings": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["added", "removed"],
+      "properties": {
+        "added": {"type": "array", "items": {"type": "object"}},
+        "removed": {"type": "array", "items": {"type": "object"}}
+      }
+    },
+    "metrics": {"type": "array", "items": {"type": "object"}},
+    "gates": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": ["regressed"],
+      "properties": {"regressed": {"type": "array", "items": {"type": "object"}}}
+    },
+    "empty": {"type": "boolean"}
+  }
+}
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/schemas/impact-v1.schema.json .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/impact-v1.schema.json
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/schemas/impact-v1.schema.json	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/schemas/impact-v1.schema.json	2026-08-26 10:48:50.384341729 -0300
@@ -0,0 +1,42 @@
+{
+  "$schema": "https://json-schema.org/draft/2020-12/schema",
+  "$id": "https://quarto-needs.dev/schema/impact-v1.schema.json",
+  "title": "Quarto-Needs impact v1",
+  "type": "object",
+  "additionalProperties": false,
+  "required": ["schemaVersion", "origins", "impacted"],
+  "properties": {
+    "schemaVersion": {"const": "1"},
+    "origins": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["id", "change"],
+        "properties": {
+          "id": {"type": "string"},
+          "change": {"enum": ["added", "removed", "modified", "relation-added", "relation-removed"]},
+          "fields": {"type": "array", "items": {"type": "string"}}
+        }
+      }
+    },
+    "impacted": {
+      "type": "array",
+      "items": {
+        "type": "object",
+        "additionalProperties": false,
+        "required": ["id", "origin", "change", "classification", "distance", "relations", "path", "priority"],
+        "properties": {
+          "id": {"type": "string"},
+          "origin": {"type": "string"},
+          "change": {"type": "string"},
+          "classification": {"enum": ["direct", "transitive"]},
+          "distance": {"type": "integer", "minimum": 1},
+          "relations": {"type": "array", "items": {"type": "string"}, "minItems": 1},
+          "path": {"type": "array", "items": {"type": "string"}, "minItems": 2},
+          "priority": {"type": ["string", "null"]}
+        }
+      }
+    }
+  }
+}
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/analysis.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/analysis.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/analysis.py	2026-08-25 13:03:20.899930532 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/analysis.py	2026-08-25 21:17:55.010723394 -0300
@@ -1,21 +1,22 @@
 from __future__ import annotations
 
 import json
 from collections.abc import Iterable
 from dataclasses import replace
 from pathlib import Path
 from typing import cast
 
 import quarto_needs
 
-from .config import NeedsConfig, embedded_defaults, load_config
+from . import fingerprints
+from .config import NeedsConfig, embedded_defaults, load_config, reference_date
 from .diagnostics import Finding
 from .model import EngineeringObject, Relation, SourceLocation
 from .parser import parse_project_declarations
 from .relations import DEFAULT_RELATION_CATALOG
 from .rules import apply_rule_settings, run_rules
 from .snapshot import (
     AnalysisResult,
     AnalysisSnapshot,
     DeclarationBatch,
     LocationRecord,
@@ -303,31 +304,40 @@
     outgoing: dict[str, tuple[RelationRecord, ...]] = {}
     incoming: dict[str, tuple[RelationRecord, ...]] = {}
     for item in objects:
         outgoing[item.id] = tuple(
             relation for relation in relations if relation.source == item.id
         )
         incoming[item.id] = tuple(
             relation for relation in relations if relation.target == item.id
         )
     metrics = legacy_coverage(objects, relations)
+    configuration = fingerprints.configuration_fingerprint(
+        effective_config, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
+    )
     draft = AnalysisSnapshot(
         objects=objects,
         relations=relations,
         findings=findings,
         metrics=metrics,
         objects_by_id=objects_by_id,
         outgoing=outgoing,
         incoming=incoming,
         generator_name="quarto-needs",
         generator_version=quarto_needs.__version__,
         relation_catalog_version=DEFAULT_RELATION_CATALOG.version,
+        reference_date=reference_date().isoformat(),
+        configuration_fingerprint=configuration,
+        semantic_graph_fingerprint=fingerprints.semantic_graph_fingerprint(
+            objects, relations, configuration
+        ),
+        representation_fingerprint=fingerprints.representation_fingerprint(relations),
     )
     rule_findings = run_rules(draft, effective_config)
     snapshot = (
         replace(draft, findings=_merge_findings(findings, rule_findings))
         if rule_findings
         else draft
     )
     return AnalysisResult(declarations, snapshot.findings, snapshot)
 
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/baseline.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/baseline.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/baseline.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/baseline.py	2026-08-26 01:10:24.420460974 -0300
@@ -0,0 +1,147 @@
+"""The baseline artifact: a canonical snapshot plus its comparison axes.
+
+A baseline stores authored content, not only fingerprints, because `diff`
+reports semantic modifications by field and cannot name a field it never saw.
+"""
+from __future__ import annotations
+
+import json
+from pathlib import Path
+from typing import Mapping, Sequence
+
+import quarto_needs
+
+from . import fingerprints
+from .analysis import AnalysisResult
+from .config import NeedsConfig
+from .export import _write_atomic_text
+from .quality import report_from_snapshot
+from .relations import DEFAULT_RELATION_CATALOG
+from .rules import RULE_SET_VERSION
+from .snapshot import AnalysisSnapshot, LocationRecord, thaw_json
+
+SCHEMA_VERSION = "1"
+DEFAULT_BASELINE_PATH = Path("baselines") / "quarto-needs.json"
+
+
+class BaselineError(Exception):
+    """A baseline could not be written, read, or trusted."""
+
+
+def _location(location: LocationRecord | None) -> dict[str, object] | None:
+    if location is None:
+        return None
+    return {"file": location.file, "line": location.line, "anchor": location.anchor}
+
+
+def _header(reference_date: str, configuration: str) -> dict[str, object]:
+    return {
+        "schemaVersion": SCHEMA_VERSION,
+        "generator": {"name": "quarto-needs", "version": quarto_needs.__version__},
+        "relationCatalogVersion": DEFAULT_RELATION_CATALOG.version,
+        "ruleSetVersion": RULE_SET_VERSION,
+        "referenceDate": reference_date,
+        "configurationFingerprint": configuration,
+    }
+
+
+def build_baseline(
+    snapshot: AnalysisSnapshot,
+    config: NeedsConfig,
+    *,
+    queries: Mapping[str, Sequence[str]] | None = None,
+) -> dict[str, object]:
+    payload = _header(snapshot.reference_date, snapshot.configuration_fingerprint)
+    payload["semanticGraphFingerprint"] = snapshot.semantic_graph_fingerprint
+    payload["representationFingerprint"] = snapshot.representation_fingerprint
+    payload["valid"] = True
+    payload["objects"] = [
+        {
+            "id": item.id,
+            "type": item.type,
+            "title": item.title,
+            "status": item.status,
+            "body": item.body,
+            "rationale": item.rationale,
+            "attributes": thaw_json(item.attributes),
+            "location": _location(item.locations[0] if item.locations else None),
+            "contentFingerprint": fingerprints.object_content_fingerprint(item),
+        }
+        for item in snapshot.objects
+    ]
+    payload["relations"] = [
+        {
+            "source": item.source,
+            "authoredName": item.authored_name,
+            "target": item.target,
+            "semanticFamily": item.semantic_family,
+            "sourceRole": item.source_role,
+            "targetRole": item.target_role,
+            "impactDirection": item.impact_direction,
+            "attributes": thaw_json(item.attributes),
+            "authoredFingerprint": fingerprints.relation_authored_fingerprint(item),
+            "semanticFingerprint": fingerprints.relation_semantic_fingerprint(item),
+        }
+        for item in snapshot.relations
+    ]
+    payload["findings"] = [finding.to_dict() for finding in snapshot.findings]
+    payload["report"] = report_from_snapshot(snapshot, config, queries=queries).to_dict()
+    return payload
+
+
+def build_invalid_baseline(result: AnalysisResult, config: NeedsConfig) -> dict[str, object]:
+    """The explicitly requested diagnostic artifact.
+
+    It is never accepted by `diff` or `impact`: structural failures make graph
+    comparison ambiguous. It exists so `baseline inspect` can explain why.
+    """
+    from .config import reference_date
+
+    configuration = fingerprints.configuration_fingerprint(
+        config, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
+    )
+    payload = _header(reference_date().isoformat(), configuration)
+    payload["valid"] = False
+    payload["declarations"] = [
+        {
+            "id": item.id,
+            "type": item.type,
+            "title": item.title,
+            "status": item.status,
+            "location": _location(item.location),
+        }
+        for item in result.declarations
+    ]
+    payload["findings"] = [finding.to_dict() for finding in result.findings]
+    return payload
+
+
+def render_baseline(payload: dict[str, object]) -> str:
+    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
+
+
+def write_baseline(path: Path, payload: dict[str, object], *, force: bool = False) -> None:
+    path = Path(path)
+    if path.exists() and not force:
+        raise BaselineError(f"{path} already exists; pass --force to overwrite it")
+    _write_atomic_text(path, render_baseline(payload))
+
+
+def load_baseline(path: Path) -> dict[str, object]:
+    path = Path(path)
+    try:
+        raw = path.read_text(encoding="utf-8")
+    except OSError as error:
+        raise BaselineError(f"Could not read {path}: {error}") from error
+    try:
+        payload = json.loads(raw)
+    except json.JSONDecodeError as error:
+        raise BaselineError(f"{path} is not valid JSON: {error}") from error
+    if not isinstance(payload, dict):
+        raise BaselineError(f"{path} is not a baseline document")
+    if payload.get("schemaVersion") != SCHEMA_VERSION:
+        raise BaselineError(
+            f"{path} declares baseline schema {payload.get('schemaVersion')!r}; "
+            f"this build reads {SCHEMA_VERSION!r}"
+        )
+    return payload
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/cli.py	2026-08-25 15:18:07.834006236 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/cli.py	2026-08-26 15:15:36.766060194 -0300
@@ -2,27 +2,30 @@
 
 import argparse
 import json
 import os
 import sys
 from collections import deque
 from collections.abc import Iterable
 from pathlib import Path
 from typing import TextIO
 
+from . import diff as diff_module
+from . import impact as impact_module
 from .analysis import analyze_project
+from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline
 from .config import NeedsConfig, load_config
 from .diagnostics import Finding
 from .export import _write_atomic_text, write_build_outputs, write_v1_graph
 from .metrics import render_measure
 from .queries import materialize_queries
-from .quality import QualityReport, build_quality_report, report_from_snapshot
+from .quality import QualityReport, build_quality_report, profile_exit_code, report_from_snapshot
 from .snapshot import AnalysisSnapshot
 
 
 class ConfigurationFailure(Exception):
     """Raised when `.quarto-needs.toml` cannot be used."""
 
 
 def _root(value: str | None) -> Path:
     return Path(value or os.getcwd()).resolve()
 
@@ -57,46 +60,52 @@
     return sorted(seen, key=lambda item: (item.casefold(), item))
 
 
 def build(root: Path, quiet: bool = False) -> int:
     try:
         config = load_config(root)
     except ValueError as error:
         if not quiet:
             print(f"Configuration error: {error}", file=sys.stderr)
         return 2
-    result = analyze_project(root, config=config)
-    if result.snapshot is None:
-        if not quiet:
-            print_findings(result.findings, stream=sys.stderr)
-        return 1
-    queries = materialize_queries(config, result.snapshot)
-    # The Lua dashboard reads only what Python projects here, so a configured
-    # project ships its materialized queries and its precomputed report.
-    extra_extensions = (
-        {
-            "quartoNeeds": {
-                "queries": {name: list(queries[name]) for name in sorted(queries)},
-                "report": report_from_snapshot(
-                    result.snapshot, config, queries=queries
-                ).to_dict(),
+    try:
+        result = analyze_project(root, config=config)
+        if result.snapshot is None:
+            if not quiet:
+                print_findings(result.findings, stream=sys.stderr)
+            return 1
+        queries = materialize_queries(config, result.snapshot)
+        # The Lua dashboard reads only what Python projects here, so a configured
+        # project ships its materialized queries and its precomputed report.
+        extra_extensions = (
+            {
+                "quartoNeeds": {
+                    "queries": {name: list(queries[name]) for name in sorted(queries)},
+                    "report": report_from_snapshot(
+                        result.snapshot, config, queries=queries
+                    ).to_dict(),
+                }
             }
-        }
-        if config.present
-        else None
-    )
-    write_build_outputs(
-        root / ".quarto-needs" / "needs.json",
-        root / "_extensions" / "quarto-needs" / "generated-index.lua",
-        result.snapshot,
-        extra_extensions=extra_extensions,
-    )
+            if config.present
+            else None
+        )
+        write_build_outputs(
+            root / ".quarto-needs" / "needs.json",
+            root / "_extensions" / "quarto-needs" / "generated-index.lua",
+            result.snapshot,
+            extra_extensions=extra_extensions,
+        )
+    except OSError as error:
+        # Reading the project or writing either artifact failed; both are
+        # operational, not validation, failures.
+        print(f"Could not scan {root}: {error}", file=sys.stderr)
+        return 3
     if not quiet:
         metrics = result.snapshot.metrics
         print(
             f"Quarto-Needs: {len(result.snapshot.objects)} objects, "
             f"{len(result.findings)} findings"
         )
         print(
             f"Requirements: {metrics['requirements']} | "
             f"implemented: {metrics['implementation_coverage']}% | "
             f"verified: {metrics['verification_coverage']}%"
@@ -178,55 +187,299 @@
         except OSError as error:
             print(f"Could not write quality report: {error}", file=sys.stderr)
             return 3
     if args.format == "json":
         print(json.dumps(payload, indent=2, sort_keys=True))
     else:
         _print_quality_text(report)
     return report.exit_code()
 
 
+def _baseline_destination(root: Path, output: str) -> Path:
+    candidate = Path(output)
+    return candidate if candidate.is_absolute() else root / candidate
+
+
+def _baseline_create(root: Path, args, config: NeedsConfig) -> int:
+    result = analyze_project(root, config=config)
+    if result.snapshot is None:
+        print_findings(result.findings, stream=sys.stderr)
+        if not args.allow_invalid:
+            return 1
+        payload = build_invalid_baseline(result, config)
+    else:
+        payload = build_baseline(
+            result.snapshot, config, queries=materialize_queries(config, result.snapshot)
+        )
+    destination = _baseline_destination(root, args.output)
+    try:
+        write_baseline(destination, payload, force=args.force)
+    except BaselineError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    except OSError as error:
+        print(f"Could not write baseline: {error}", file=sys.stderr)
+        return 3
+    if args.format == "json":
+        print(json.dumps({"path": str(destination), "valid": payload["valid"]}, indent=2, sort_keys=True))
+    else:
+        state = "valid" if payload["valid"] else "diagnostic (valid: false)"
+        print(f"Wrote {state} baseline to {destination}")
+    return 0
+
+
+def _baseline_summary(payload: dict[str, object]) -> dict[str, object]:
+    return {
+        "valid": payload["valid"],
+        "referenceDate": payload["referenceDate"],
+        "configurationFingerprint": payload["configurationFingerprint"],
+        "semanticGraphFingerprint": payload.get("semanticGraphFingerprint"),
+        "objects": len(payload.get("objects", payload.get("declarations", []))),
+        "relations": len(payload.get("relations", [])),
+        "findings": len(payload.get("findings", [])),
+    }
+
+
+def _baseline_inspect(args) -> int:
+    try:
+        payload = load_baseline(Path(args.baseline))
+    except BaselineError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    try:
+        summary = _baseline_summary(payload)
+    except KeyError as error:
+        # A tampered artifact can declare schemaVersion "1" yet omit required
+        # keys; load_baseline does not schema-validate, so this is the last
+        # line of defense before a raw traceback.
+        print(f"{args.baseline} is missing required key {error}; it is not a trustworthy baseline", file=sys.stderr)
+        return 2
+    if args.format == "json":
+        print(json.dumps(summary, indent=2, sort_keys=True))
+        return 0
+    print(f"Baseline {args.baseline}")
+    print(f"  valid: {summary['valid']}")
+    print(f"  reference date: {summary['referenceDate']}")
+    print(f"  objects: {summary['objects']}")
+    print(f"  relations: {summary['relations']}")
+    print(f"  findings: {summary['findings']}")
+    return 0
+
+
+def _print_diff_text(report) -> None:
+    for notice in report.notices:
+        print(f"[notice] {notice}: derived deltas suppressed; both sides must share configuration and reference date to compare them")
+    if report.is_empty():
+        print("No changes.")
+        return
+    for object_id in report.added_objects:
+        print(f"+ object {object_id}")
+    for object_id in report.removed_objects:
+        print(f"- object {object_id}")
+    for item in report.modified:
+        print(f"~ object {item['id']} ({', '.join(item['fields'])})")
+    for item in report.relocated:
+        print(f"> object {item['id']} moved {item['from'].get('file')} -> {item['to'].get('file')}")
+    for item in report.added_relations:
+        print(f"+ relation {item['source']} {item['authoredName']} {item['target']}")
+    for item in report.removed_relations:
+        print(f"- relation {item['source']} {item['authoredName']} {item['target']}")
+    for item in report.representation_changes:
+        print(f"= relation {item['source']} -> {item['target']} respelled {item['from']} -> {item['to']}")
+    for item in report.findings_added:
+        print(f"+ finding {item['code']} {item['object_id'] or ''}".rstrip())
+    for item in report.findings_removed:
+        print(f"- finding {item['code']} {item['object_id'] or ''}".rstrip())
+    for item in report.metric_deltas:
+        print(f"~ metric {item['scope']}/{item['strength']} {item['before']} -> {item['after']}")
+    for item in report.gate_regressions:
+        print(f"! gate {item['name']} failed (threshold {item['threshold']}, actual {item['actual']})")
+
+
+def _diff(root: Path, args, config: NeedsConfig) -> int:
+    try:
+        baseline_payload = load_baseline(Path(args.baseline))
+    except BaselineError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    result = analyze_project(root, config=config)
+    if result.snapshot is None:
+        print_findings(result.findings, stream=sys.stderr)
+        return 1
+    try:
+        report = diff_module.compare(
+            baseline_payload,
+            result.snapshot,
+            config,
+            recompute=args.recompute_with == "current",
+        )
+    except diff_module.DiffError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    if args.format == "json":
+        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
+    else:
+        _print_diff_text(report)
+    return profile_exit_code(config.profile, False, len(report.gate_regressions))
+
+
+def _impact(root: Path, args, config: NeedsConfig) -> int:
+    try:
+        baseline_payload = load_baseline(Path(args.baseline))
+    except BaselineError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    result = analyze_project(root, config=config)
+    if result.snapshot is None:
+        print_findings(result.findings, stream=sys.stderr)
+        return 1
+    try:
+        report = impact_module.analyze(
+            baseline_payload,
+            result.snapshot,
+            config,
+            recompute=args.recompute_with == "current",
+        )
+    except impact_module.ImpactError as error:
+        print(str(error), file=sys.stderr)
+        return 2
+    if args.format == "json":
+        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
+        return 0
+    if not report.origins:
+        print("No changes to propagate.")
+        return 0
+    for origin in report.origins:
+        print(f"origin {origin['id']} ({origin['change']})")
+    for item in report.impacted:
+        print(
+            f"  {item['classification']} d={item['distance']} {item['id']}"
+            f" via {' -> '.join(item['path'])}"
+            f" [{', '.join(item['relations'])}]"
+        )
+    return 0
+
+
+def _export(root: Path, args: argparse.Namespace, config: NeedsConfig | None) -> int:
+    effective = config if config is not None else load_config(root)
+    if args.baseline is not None and args.format != "markdown":
+        # Usage errors are reported before any analysis runs.
+        print(
+            "usage error: --baseline is only valid with --format markdown "
+            f"(got --format {args.format})",
+            file=sys.stderr,
+        )
+        return 2
+    result = analyze_project(root, config=effective)
+    if result.snapshot is None:
+        print_findings(result.findings, stream=sys.stderr)
+        return 1
+    output = root / args.output
+    try:
+        if args.format == "json":
+            # Byte-identity with the pre-task v1 projection holds by
+            # construction: the default format keeps the existing writer.
+            write_v1_graph(output, result.snapshot)
+        else:
+            # TODO(milestone-4a-writers): Tasks 3-6 replace this raise with
+            # the csv/sarif/junit/markdown writers, each routing its writes
+            # through _write_atomic_text like the json path above.
+            raise NotImplementedError(
+                f"--format {args.format} writer lands with the milestone-4a exporter tasks"
+            )
+    except OSError as error:
+        print(f"Could not write {output}: {error}", file=sys.stderr)
+        return 3
+    # The artifact is on disk before the policy verdict leaves the process.
+    report = report_from_snapshot(result.snapshot, effective)
+    return profile_exit_code(effective.profile, False, report.gate_failures())
+
+
 def main(argv: list[str] | None = None) -> int:
     parser = argparse.ArgumentParser(prog="quarto-needs", description="Requirements-as-code engine for Quarto")
     parser.add_argument("--root", help="Project root (default: current directory)")
     sub = parser.add_subparsers(dest="command", required=True)
     sub.add_parser("scan", help="Parse project and write .quarto-needs/needs.json")
     sub.add_parser("check", help="Validate the requirements graph")
     sub.add_parser("coverage", help="Print coverage metrics")
     trace = sub.add_parser("trace", help="Show upstream/downstream traceability")
     trace.add_argument("id")
     export = sub.add_parser("export", help="Export canonical graph JSON")
     export.add_argument("--output", default=".quarto-needs/needs.json")
+    export.add_argument("--format", choices=("json", "csv", "sarif", "junit", "markdown"), default="json")
+    export.add_argument("--baseline", help="Baseline for the Markdown change summary (markdown format only)")
     quality = sub.add_parser(
         "quality", help="Evaluate scoped metrics, findings, and configured gates"
     )
     quality.add_argument("--format", choices=("text", "json"), default="text")
     quality.add_argument("--output", help="Write the JSON report atomically to this path")
     query = sub.add_parser("query", help="Evaluate a named query and print its ordered IDs")
     query.add_argument("name")
     query.add_argument("--format", choices=("text", "json"), default="text")
+    baseline_parser = sub.add_parser("baseline", help="Create or inspect a canonical baseline")
+    baseline_sub = baseline_parser.add_subparsers(dest="baseline_command", required=True)
+    baseline_create = baseline_sub.add_parser("create", help="Write a baseline for the current graph")
+    baseline_create.add_argument("--output", default=str(DEFAULT_BASELINE_PATH))
+    baseline_create.add_argument("--force", action="store_true", help="Overwrite an existing baseline")
+    baseline_create.add_argument(
+        "--allow-invalid",
+        action="store_true",
+        help="Write a diagnostic artifact for a structurally invalid project",
+    )
+    baseline_create.add_argument("--format", choices=("text", "json"), default="text")
+    baseline_inspect = baseline_sub.add_parser("inspect", help="Summarize an existing baseline")
+    baseline_inspect.add_argument("baseline")
+    baseline_inspect.add_argument("--format", choices=("text", "json"), default="text")
+    diff_parser = sub.add_parser("diff", help="Compare a baseline against the current graph")
+    diff_parser.add_argument("baseline")
+    diff_parser.add_argument("--format", choices=("text", "json"), default="text")
+    diff_parser.add_argument(
+        "--recompute-with",
+        choices=("current",),
+        dest="recompute_with",
+        help="Re-resolve the baseline's relations under the current configuration and reference date",
+    )
+    impact_parser = sub.add_parser("impact", help="Explain what a baseline's changes reach")
+    impact_parser.add_argument("baseline")
+    impact_parser.add_argument("--format", choices=("text", "json"), default="text")
+    impact_parser.add_argument(
+        "--recompute-with",
+        choices=("current",),
+        dest="recompute_with",
+        help="Re-resolve the baseline's relations under the current configuration and reference date",
+    )
     args = parser.parse_args(argv)
     root = _root(args.root)
 
     if args.command == "scan":
         return build(root)
 
     try:
         config: NeedsConfig | None = load_config(root)
     except ValueError as error:
         print(f"Configuration error: {error}", file=sys.stderr)
         return 2
 
     if args.command == "quality":
         return _quality(root, args, config)
     if args.command == "query":
         return _query(root, args, config)
+    if args.command == "baseline":
+        if args.baseline_command == "inspect":
+            return _baseline_inspect(args)
+        return _baseline_create(root, args, config)
+    if args.command == "diff":
+        return _diff(root, args, config)
+    if args.command == "impact":
+        return _impact(root, args, config)
+    if args.command == "export":
+        return _export(root, args, config)
     result = analyze_project(root, config=config)
     if args.command == "check":
         print_findings(result.findings, stream=sys.stdout)
         print(
             f"Checked {len(result.declarations)} objects: "
             f"{sum(f.severity == 'error' for f in result.findings)} errors, "
             f"{sum(f.severity == 'warning' for f in result.findings)} warnings"
         )
         return 1 if any(f.severity == "error" for f in result.findings) else 0
     if result.snapshot is None:
@@ -248,18 +501,15 @@
         if args.id not in result.snapshot.objects_by_id:
             print(f"Unknown object: {args.id}", file=sys.stderr)
             return 2
         print("Upstream:")
         for item in _reachable(result.snapshot, args.id, "upstream"):
             print(f"  {item}")
         print("Downstream:")
         for item in _reachable(result.snapshot, args.id, "downstream"):
             print(f"  {item}")
         return 0
-    if args.command == "export":
-        write_v1_graph(root / args.output, result.snapshot)
-        return 0
     return 2
 
 
 if __name__ == "__main__":
     raise SystemExit(main())
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/config.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/config.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/config.py	2026-08-25 13:41:25.830887852 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/config.py	2026-08-26 14:41:53.817295052 -0300
@@ -6,20 +6,22 @@
 from datetime import date, datetime, timezone
 from pathlib import Path
 from types import MappingProxyType
 from typing import Any, Mapping
 
 if sys.version_info >= (3, 11):
     import tomllib
 else:  # pragma: no cover - exercised only on Python 3.10
     import tomli as tomllib
 
+from .snapshot import freeze_json, thaw_json
+
 
 CONFIG_FILENAME = ".quarto-needs.toml"
 
 KNOWN_TOP_LEVEL_KEYS = (
     "profile",
     "types",
     "relations",
     "governance",
     "rules",
     "queries",
@@ -92,20 +94,73 @@
     test_types: tuple[str, ...]
     risk_types: tuple[str, ...]
     ineffective_endpoint_statuses: tuple[str, ...]
     successful_test_statuses: tuple[str, ...]
     expiry_attribute: str
     rule_settings: Mapping[str, RuleSetting]
     named_query_sources: Mapping[str, Mapping[str, Any]]
     gates: Gates
     present: bool = False
 
+    def canonical_document(self) -> dict[str, object]:
+        """The single canonical form the configuration fingerprint hashes.
+
+        Excludes `present`: presence controls artifact projection, not graph
+        semantics. This object stores no file path, so there is none to exclude.
+        """
+        try:
+            queries = {
+                name: thaw_json(freeze_json(dict(source)))
+                for name, source in sorted(self.named_query_sources.items())
+            }
+        except TypeError as error:
+            raise _fail(f"[queries] contains a value that is not valid JSON: {error}") from error
+
+        return {
+            "profile": self.profile,
+            "types": {
+                name: {"required-attributes": list(self.required_attributes[name])}
+                for name in sorted(self.required_attributes)
+            },
+            "relations": {
+                name: {
+                    "allowed-source-types": list(policy.allowed_source_types),
+                    "allowed-target-types": list(policy.allowed_target_types),
+                    "minimum-per-source": policy.minimum_per_source,
+                    "maximum-per-source": policy.maximum_per_source,
+                }
+                for name, policy in sorted(self.relation_policies.items())
+            },
+            "governance": {
+                "test-types": list(self.test_types),
+                "risk-types": list(self.risk_types),
+                "successful-test-statuses": list(self.successful_test_statuses),
+                "ineffective-endpoint-statuses": list(self.ineffective_endpoint_statuses),
+                "expiry-attribute": self.expiry_attribute,
+            },
+            "rules": {
+                code: {"enabled": setting.enabled, "severity": setting.severity}
+                for code, setting in sorted(self.rule_settings.items())
+            },
+            "queries": queries,
+            "gates": {
+                "scope": self.gates.scope,
+                "max-errors": self.gates.max_errors,
+                "require-risk-mitigation": self.gates.require_risk_mitigation,
+                "min-implementation-trace": self.gates.min_implementation_trace,
+                "min-implementation-effective": self.gates.min_implementation_effective,
+                "min-verification-trace": self.gates.min_verification_trace,
+                "min-verification-successful": self.gates.min_verification_successful,
+                "min-evidence": self.gates.min_evidence,
+            },
+        }
+
 
 def reference_date() -> date:
     raw = os.environ.get("SOURCE_DATE_EPOCH")
     if raw is not None:
         try:
             return datetime.fromtimestamp(int(raw), tz=timezone.utc).date()
         except (ValueError, OverflowError, OSError):
             return date.today()
     return date.today()
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/diff.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/diff.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/diff.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/diff.py	2026-08-26 10:09:28.715101693 -0300
@@ -0,0 +1,382 @@
+"""Classified comparison between a baseline and the current snapshot.
+
+Two guards run before any comparison. A changed configuration or a changed
+reference date means the derived numbers were produced under different rules,
+so reporting their deltas as project changes would be a lie; the diff says so
+and suppresses them instead.
+"""
+from __future__ import annotations
+
+from dataclasses import dataclass
+from typing import Mapping, Sequence
+
+from . import fingerprints
+from .config import NeedsConfig
+from .quality import report_from_snapshot
+from .snapshot import AnalysisSnapshot
+
+SCHEMA_VERSION = "1"
+
+OBJECT_FIELDS = ("type", "title", "status", "body", "rationale", "attributes")
+
+
+class DiffError(Exception):
+    """The two sides cannot be compared."""
+
+
+@dataclass(frozen=True, slots=True)
+class DiffReport:
+    baseline_reference_date: str
+    current_reference_date: str
+    recomputed: bool
+    notices: tuple[str, ...]
+    added_objects: tuple[str, ...]
+    removed_objects: tuple[str, ...]
+    modified: tuple[Mapping[str, object], ...]
+    relocated: tuple[Mapping[str, object], ...]
+    added_relations: tuple[Mapping[str, object], ...]
+    removed_relations: tuple[Mapping[str, object], ...]
+    representation_changes: tuple[Mapping[str, object], ...]
+    findings_added: tuple[Mapping[str, object], ...]
+    findings_removed: tuple[Mapping[str, object], ...]
+    metric_deltas: tuple[Mapping[str, object], ...]
+    gate_regressions: tuple[Mapping[str, object], ...]
+
+    def is_empty(self) -> bool:
+        return not (
+            self.added_objects
+            or self.removed_objects
+            or self.modified
+            or self.relocated
+            or self.added_relations
+            or self.removed_relations
+            or self.representation_changes
+            or self.findings_added
+            or self.findings_removed
+            or self.metric_deltas
+            or self.gate_regressions
+        )
+
+    def to_dict(self) -> dict[str, object]:
+        return {
+            "schemaVersion": SCHEMA_VERSION,
+            "referenceDate": {
+                "baseline": self.baseline_reference_date,
+                "current": self.current_reference_date,
+            },
+            "recomputed": self.recomputed,
+            "notices": list(self.notices),
+            "objects": {
+                "added": list(self.added_objects),
+                "removed": list(self.removed_objects),
+                "modified": [dict(item) for item in self.modified],
+                "relocated": [dict(item) for item in self.relocated],
+            },
+            "relations": {
+                "added": [dict(item) for item in self.added_relations],
+                "removed": [dict(item) for item in self.removed_relations],
+                "representationChanged": [dict(item) for item in self.representation_changes],
+            },
+            "findings": {
+                "added": [dict(item) for item in self.findings_added],
+                "removed": [dict(item) for item in self.findings_removed],
+            },
+            "metrics": [dict(item) for item in self.metric_deltas],
+            "gates": {"regressed": [dict(item) for item in self.gate_regressions]},
+            "empty": self.is_empty(),
+        }
+
+
+def _baseline_objects(payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
+    return {str(item["id"]): item for item in payload.get("objects", [])}
+
+
+def _current_object(record) -> dict[str, object]:
+    from .snapshot import thaw_json
+
+    return {
+        "id": record.id,
+        "type": record.type,
+        "title": record.title,
+        "status": record.status,
+        "body": record.body,
+        "rationale": record.rationale,
+        "attributes": thaw_json(record.attributes),
+        "location": (
+            {
+                "file": record.locations[0].file,
+                "line": record.locations[0].line,
+                "anchor": record.locations[0].anchor,
+            }
+            if record.locations
+            else None
+        ),
+        "contentFingerprint": fingerprints.object_content_fingerprint(record),
+    }
+
+
+def _classify_objects(
+    before: Mapping[str, Mapping[str, object]], after: Mapping[str, Mapping[str, object]]
+) -> tuple[tuple[str, ...], tuple[str, ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
+    added = tuple(sorted(set(after) - set(before), key=lambda item: (item.casefold(), item)))
+    removed = tuple(sorted(set(before) - set(after), key=lambda item: (item.casefold(), item)))
+    modified: list[dict[str, object]] = []
+    relocated: list[dict[str, object]] = []
+    for object_id in sorted(set(before) & set(after), key=lambda item: (item.casefold(), item)):
+        old, new = before[object_id], after[object_id]
+        if old["contentFingerprint"] != new["contentFingerprint"]:
+            fields = [name for name in OBJECT_FIELDS if old.get(name) != new.get(name)]
+            modified.append({"id": object_id, "fields": fields})
+        old_location = old.get("location") or {}
+        new_location = new.get("location") or {}
+        # Relocation is keyed on the declaring file. A line-only shift is not a
+        # record: fingerprints already ignore line numbers, and one inserted
+        # paragraph would otherwise relocate every object below it.
+        if old_location.get("file") != new_location.get("file"):
+            relocated.append({"id": object_id, "from": old_location, "to": new_location})
+    return added, removed, tuple(modified), tuple(relocated)
+
+
+def _relation_entry(item: Mapping[str, object]) -> dict[str, object]:
+    return {
+        "source": item["source"],
+        "authoredName": item["authoredName"],
+        "target": item["target"],
+        "semanticFamily": item["semanticFamily"],
+    }
+
+
+def _current_relations(snapshot: AnalysisSnapshot) -> list[dict[str, object]]:
+    return [
+        {
+            "source": record.source,
+            "authoredName": record.authored_name,
+            "target": record.target,
+            "semanticFamily": record.semantic_family,
+            "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
+            "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
+        }
+        for record in snapshot.relations
+    ]
+
+
+def _classify_relations(
+    before: Sequence[Mapping[str, object]],
+    after: Sequence[Mapping[str, object]],
+    *,
+    key: str = "semanticFingerprint",
+) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
+    """Classify by `key`.
+
+    Semantic fingerprints are the default. When the configuration changed, the
+    caller keys on `authoredFingerprint` instead: a catalog change can move
+    families and roles, so semantic fingerprints from the two sides are not
+    comparable, and the spec requires authored tuples in that case.
+    """
+    before_semantic = {str(item[key]): item for item in before}
+    after_semantic = {str(item[key]): item for item in after}
+    added = tuple(
+        _relation_entry(after_semantic[key])
+        for key in sorted(set(after_semantic) - set(before_semantic))
+    )
+    removed = tuple(
+        _relation_entry(before_semantic[key])
+        for key in sorted(set(before_semantic) - set(after_semantic))
+    )
+    # Same edge, different authored spelling: informational, never a graph change.
+    representation = tuple(
+        {
+            **_relation_entry(after_semantic[key]),
+            "from": before_semantic[key]["authoredName"],
+            "to": after_semantic[key]["authoredName"],
+        }
+        for key in sorted(set(before_semantic) & set(after_semantic))
+        if before_semantic[key]["authoredFingerprint"] != after_semantic[key]["authoredFingerprint"]
+    )
+    return added, removed, representation
+
+
+def _finding_key(item: Mapping[str, object]) -> tuple[str, str, str]:
+    return (str(item.get("code")), str(item.get("object_id") or ""), str(item.get("message")))
+
+
+def _classify_findings(
+    before: Sequence[Mapping[str, object]], after: Sequence[Mapping[str, object]]
+) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
+    before_keys = {_finding_key(item): item for item in before}
+    after_keys = {_finding_key(item): item for item in after}
+    added = tuple(
+        {"code": key[0], "object_id": key[1] or None, "message": key[2], "severity": after_keys[key].get("severity")}
+        for key in sorted(set(after_keys) - set(before_keys))
+    )
+    removed = tuple(
+        {"code": key[0], "object_id": key[1] or None, "message": key[2], "severity": before_keys[key].get("severity")}
+        for key in sorted(set(before_keys) - set(after_keys))
+    )
+    return added, removed
+
+
+def _classify_metrics(
+    before: Mapping[str, object], after: Mapping[str, object]
+) -> tuple[dict[str, object], ...]:
+    deltas: list[dict[str, object]] = []
+    before_scopes = before.get("scopes", {}) if isinstance(before, Mapping) else {}
+    after_scopes = after.get("scopes", {})
+    for scope in sorted(set(before_scopes) | set(after_scopes)):
+        old_coverage = (before_scopes.get(scope) or {}).get("coverage", {})
+        new_coverage = (after_scopes.get(scope) or {}).get("coverage", {})
+        for strength in sorted(set(old_coverage) | set(new_coverage)):
+            old_percent = (old_coverage.get(strength) or {}).get("percent")
+            new_percent = (new_coverage.get(strength) or {}).get("percent")
+            if old_percent != new_percent:
+                deltas.append(
+                    {"scope": scope, "strength": strength, "before": old_percent, "after": new_percent}
+                )
+    return tuple(deltas)
+
+
+def _classify_gates(
+    before: Mapping[str, object], after: Mapping[str, object]
+) -> tuple[dict[str, object], ...]:
+    """Only pass -> fail is a regression; fail -> pass is progress, not a delta."""
+    before_gates = {
+        str(item["name"]): item for item in (before.get("gates", []) if isinstance(before, Mapping) else [])
+    }
+    regressions: list[dict[str, object]] = []
+    for item in after.get("gates", []):
+        name = str(item["name"])
+        was = before_gates.get(name)
+        if item.get("passed") is False and (was is None or was.get("passed") is not False):
+            regressions.append(
+                {"name": name, "scope": item.get("scope"), "threshold": item.get("threshold"), "actual": item.get("actual")}
+            )
+    return tuple(regressions)
+
+
+def _recomputed_relations(stored: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
+    """Re-resolve stored relations through the *current* catalog.
+
+    `--recompute-with current` must compare both sides under one policy, so the
+    baseline's authored names are resolved again rather than trusting the
+    families and roles that were canonical when it was written.
+    """
+    from .relations import DEFAULT_RELATION_CATALOG
+    from .snapshot import RelationRecord
+
+    recomputed: list[dict[str, object]] = []
+    for item in stored:
+        authored = str(item["authoredName"])
+        try:
+            kind = DEFAULT_RELATION_CATALOG.resolve(authored)
+        except ValueError:
+            # An authored name the current catalog no longer knows cannot be
+            # re-resolved; keep it verbatim so it surfaces as a real change.
+            recomputed.append(dict(item))
+            continue
+        record = RelationRecord(
+            source=str(item["source"]),
+            authored_name=authored,
+            catalog_name=kind.catalog_name,
+            v1_name=kind.v1_name,
+            target=str(item["target"]),
+            semantic_family=kind.semantic_family,
+            source_role=kind.source_role,
+            target_role=kind.target_role,
+            impact_direction=kind.impact_direction,
+            attributes=item.get("attributes") or {},
+            provenance=(),
+        )
+        recomputed.append(
+            {
+                "source": record.source,
+                "authoredName": record.authored_name,
+                "target": record.target,
+                "semanticFamily": record.semantic_family,
+                "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
+                "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
+            }
+        )
+    return recomputed
+
+
+def compare(
+    baseline_payload: Mapping[str, object],
+    snapshot: AnalysisSnapshot,
+    config: NeedsConfig,
+    *,
+    recompute: bool = False,
+) -> DiffReport:
+    if not baseline_payload.get("valid", False):
+        raise DiffError(
+            "This baseline is a diagnostic artifact (valid: false) and cannot be compared; "
+            "use `baseline inspect` to read it"
+        )
+
+    current_configuration = snapshot.configuration_fingerprint
+    baseline_configuration = str(baseline_payload.get("configurationFingerprint", ""))
+    baseline_date = str(baseline_payload.get("referenceDate", ""))
+
+    notices: list[str] = []
+    configuration_differs = baseline_configuration != current_configuration
+    date_differs = baseline_date != snapshot.reference_date
+    if not recompute:
+        if configuration_differs:
+            notices.append("configuration-changed")
+        if date_differs:
+            notices.append("reference-date-changed")
+
+    added, removed, modified, relocated = _classify_objects(
+        _baseline_objects(baseline_payload),
+        {record.id: _current_object(record) for record in snapshot.objects},
+    )
+
+    baseline_relations = list(baseline_payload.get("relations", []))
+    if recompute:
+        baseline_relations = _recomputed_relations(baseline_relations)
+    # A catalog change can move families and roles, so semantic fingerprints
+    # from the two sides stop being comparable. Fall back to authored tuples,
+    # which is exactly what the spec prescribes for this case.
+    relation_key = (
+        "authoredFingerprint" if "configuration-changed" in notices else "semanticFingerprint"
+    )
+    added_relations, removed_relations, representation = _classify_relations(
+        baseline_relations, _current_relations(snapshot), key=relation_key
+    )
+
+    # Derived results are stored in the baseline, never re-derived, so they are
+    # comparable only when both sides were produced under the same rules and
+    # the same reference date. `recompute` re-resolves authored relations
+    # through the current catalog; it cannot make stored findings, metrics, or
+    # gates comparable, so their deltas stay suppressed silently there.
+    derived_suppressed = configuration_differs or date_differs
+    if derived_suppressed:
+        findings_added: tuple[dict[str, object], ...] = ()
+        findings_removed: tuple[dict[str, object], ...] = ()
+        metric_deltas: tuple[dict[str, object], ...] = ()
+        gate_regressions: tuple[dict[str, object], ...] = ()
+    else:
+        current_report = report_from_snapshot(snapshot, config).to_dict()
+        baseline_report = baseline_payload.get("report", {})
+        findings_added, findings_removed = _classify_findings(
+            baseline_payload.get("findings", []), [item.to_dict() for item in snapshot.findings]
+        )
+        metric_deltas = _classify_metrics(baseline_report, current_report)
+        gate_regressions = _classify_gates(baseline_report, current_report)
+
+    return DiffReport(
+        baseline_reference_date=baseline_date,
+        current_reference_date=snapshot.reference_date,
+        recomputed=recompute,
+        notices=tuple(notices),
+        added_objects=added,
+        removed_objects=removed,
+        modified=modified,
+        relocated=relocated,
+        added_relations=added_relations,
+        removed_relations=removed_relations,
+        representation_changes=representation,
+        findings_added=findings_added,
+        findings_removed=findings_removed,
+        metric_deltas=metric_deltas,
+        gate_regressions=gate_regressions,
+    )
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/fingerprints.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/fingerprints.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/fingerprints.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/fingerprints.py	2026-08-26 00:51:16.052871934 -0300
@@ -0,0 +1,101 @@
+"""Pure content fingerprints over the canonical snapshot records.
+
+Every fingerprint excludes line numbers, `href` values, generated metrics,
+and any other derived data, so provenance changes and rendering changes can
+never masquerade as semantic ones.
+"""
+from __future__ import annotations
+
+import hashlib
+import json
+from typing import Iterable
+
+from .config import NeedsConfig
+from .rules import RULE_SET_VERSION
+from .snapshot import ObjectRecord, RelationRecord, thaw_json
+
+
+def _digest(payload: object) -> str:
+    encoded = json.dumps(
+        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
+    ).encode("utf-8")
+    return hashlib.sha256(encoded).hexdigest()
+
+
+def object_content_fingerprint(record: ObjectRecord) -> str:
+    return _digest(
+        {
+            "id": record.id,
+            "type": record.type,
+            "title": record.title,
+            "body": record.body,
+            "rationale": record.rationale,
+            "status": record.status,
+            "priority": record.priority,
+            "tags": list(record.tags),
+            "attributes": thaw_json(record.attributes),
+        }
+    )
+
+
+def relation_authored_fingerprint(record: RelationRecord) -> str:
+    return _digest(
+        {
+            "source": record.source,
+            "authored_name": record.authored_name,
+            "target": record.target,
+            "attributes": thaw_json(record.attributes),
+        }
+    )
+
+
+def relation_semantic_fingerprint(record: RelationRecord) -> str:
+    """Identity of the edge itself, independent of which end authored it.
+
+    Endpoints are sorted by role, so an alias flip that preserves the roles
+    yields the same fingerprint and is classified as representation-only.
+    """
+    endpoints = sorted(
+        (
+            {"id": record.source, "role": record.source_role},
+            {"id": record.target, "role": record.target_role},
+        ),
+        key=lambda item: (item["role"], item["id"]),
+    )
+    return _digest(
+        {
+            "family": record.semantic_family,
+            "endpoints": endpoints,
+            "attributes": thaw_json(record.attributes),
+        }
+    )
+
+
+def configuration_fingerprint(
+    config: NeedsConfig, *, relation_catalog_version: str
+) -> str:
+    return _digest(
+        {
+            "configuration": config.canonical_document(),
+            "relationCatalogVersion": relation_catalog_version,
+            "ruleSetVersion": RULE_SET_VERSION,
+        }
+    )
+
+
+def semantic_graph_fingerprint(
+    objects: Iterable[ObjectRecord],
+    relations: Iterable[RelationRecord],
+    configuration: str,
+) -> str:
+    return _digest(
+        {
+            "objects": sorted(object_content_fingerprint(item) for item in objects),
+            "relations": sorted(relation_semantic_fingerprint(item) for item in relations),
+            "configuration": configuration,
+        }
+    )
+
+
+def representation_fingerprint(relations: Iterable[RelationRecord]) -> str:
+    return _digest(sorted(relation_authored_fingerprint(item) for item in relations))
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/impact.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/impact.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/impact.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/impact.py	2026-08-26 11:15:26.013708733 -0300
@@ -0,0 +1,165 @@
+"""Union-graph impact traversal with explicit, auditable paths.
+
+The traversal runs over the union of the baseline and current graphs so a
+removed node or edge remains explainable. There is deliberately no risk score:
+the output is the path that produced each result.
+"""
+from __future__ import annotations
+
+from collections import deque
+from dataclasses import dataclass
+from typing import Mapping, Sequence
+
+from . import diff as diff_module
+from .config import NeedsConfig
+from .snapshot import AnalysisSnapshot
+
+SCHEMA_VERSION = "1"
+MAX_DISTANCE = 10
+
+
+class ImpactError(Exception):
+    """The two graphs cannot be traversed together."""
+
+
+@dataclass(frozen=True, slots=True)
+class ImpactReport:
+    origins: tuple[Mapping[str, object], ...]
+    impacted: tuple[Mapping[str, object], ...]
+
+    def to_dict(self) -> dict[str, object]:
+        return {
+            "schemaVersion": SCHEMA_VERSION,
+            "origins": [dict(item) for item in self.origins],
+            "impacted": [dict(item) for item in self.impacted],
+        }
+
+
+def _union_edges(
+    baseline_relations: Sequence[Mapping[str, object]], snapshot: AnalysisSnapshot
+) -> dict[str, list[tuple[str, str]]]:
+    """Adjacency keyed by source, following each relation's impact direction.
+
+    `both` yields an edge in each direction; `none` yields none at all.
+    """
+    adjacency: dict[str, list[tuple[str, str]]] = {}
+
+    def add(source: str, target: str, name: str, direction: str) -> None:
+        if direction in {"source_to_target", "both"}:
+            adjacency.setdefault(source, []).append((target, name))
+        if direction in {"target_to_source", "both"}:
+            adjacency.setdefault(target, []).append((source, name))
+
+    for item in baseline_relations:
+        add(
+            str(item["source"]),
+            str(item["target"]),
+            str(item["authoredName"]),
+            str(item.get("impactDirection", "none")),
+        )
+    for record in snapshot.relations:
+        add(record.source, record.target, record.authored_name, record.impact_direction)
+
+    for key in adjacency:
+        adjacency[key] = sorted(set(adjacency[key]))
+    return adjacency
+
+
+def _origins(report: diff_module.DiffReport) -> tuple[dict[str, object], ...]:
+    origins: list[dict[str, object]] = []
+    for object_id in report.added_objects:
+        origins.append({"id": object_id, "change": "added"})
+    for object_id in report.removed_objects:
+        origins.append({"id": object_id, "change": "removed"})
+    for item in report.modified:
+        origins.append({"id": str(item["id"]), "change": "modified", "fields": list(item["fields"])})
+    for item in report.added_relations:
+        origins.append({"id": str(item["source"]), "change": "relation-added"})
+    for item in report.removed_relations:
+        origins.append({"id": str(item["source"]), "change": "relation-removed"})
+    seen: dict[str, dict[str, object]] = {}
+    for origin in origins:
+        seen.setdefault(str(origin["id"]), origin)
+    return tuple(seen[key] for key in sorted(seen, key=lambda item: (item.casefold(), item)))
+
+
+def _priority(
+    object_id: str, snapshot: AnalysisSnapshot, baseline_objects: Mapping[str, Mapping[str, object]]
+) -> str | None:
+    record = snapshot.objects_by_id.get(object_id)
+    if record is not None:
+        return record.priority
+    stored = baseline_objects.get(object_id)
+    if stored is None:
+        return None
+    attributes = stored.get("attributes") or {}
+    value = attributes.get("priority")
+    return str(value) if value not in (None, "") else None
+
+
+def analyze(
+    baseline_payload: Mapping[str, object],
+    snapshot: AnalysisSnapshot,
+    config: NeedsConfig,
+    *,
+    recompute: bool = False,
+) -> ImpactReport:
+    if not baseline_payload.get("valid", False):
+        raise ImpactError(
+            "This baseline is a diagnostic artifact (valid: false) and cannot be traversed"
+        )
+    if not recompute:
+        if str(
+            baseline_payload.get("configurationFingerprint", "")
+        ) != snapshot.configuration_fingerprint:
+            raise ImpactError(
+                "The baseline was produced under a different configuration; "
+                "pass --recompute-with current so one relation policy governs the traversal"
+            )
+        if str(baseline_payload.get("referenceDate", "")) != snapshot.reference_date:
+            raise ImpactError(
+                "The baseline was produced under a different reference date; "
+                "pass --recompute-with current to traverse under the current date"
+            )
+
+    report = diff_module.compare(baseline_payload, snapshot, config, recompute=True)
+    origins = _origins(report)
+    adjacency = _union_edges(baseline_payload.get("relations", []), snapshot)
+    baseline_objects = {str(item["id"]): item for item in baseline_payload.get("objects", [])}
+    origin_ids = {str(item["id"]) for item in origins}
+
+    impacted: dict[tuple[str, str], dict[str, object]] = {}
+    for origin in origins:
+        start = str(origin["id"])
+        queue: deque[tuple[str, tuple[str, ...], tuple[str, ...]]] = deque([(start, (start,), ())])
+        visited = {start}
+        while queue:
+            current, path, relations = queue.popleft()
+            distance = len(path) - 1
+            if distance >= MAX_DISTANCE:
+                continue
+            for neighbor, relation_name in adjacency.get(current, []):
+                if neighbor in visited:
+                    continue
+                visited.add(neighbor)
+                next_path = path + (neighbor,)
+                next_relations = relations + (relation_name,)
+                key = (start, neighbor)
+                if neighbor not in origin_ids and key not in impacted:
+                    impacted[key] = {
+                        "id": neighbor,
+                        "origin": start,
+                        "change": origin["change"],
+                        "classification": "direct" if len(next_path) == 2 else "transitive",
+                        "distance": len(next_path) - 1,
+                        "relations": list(next_relations),
+                        "path": list(next_path),
+                        "priority": _priority(neighbor, snapshot, baseline_objects),
+                    }
+                queue.append((neighbor, next_path, next_relations))
+
+    ordered = tuple(
+        impacted[key]
+        for key in sorted(impacted, key=lambda item: (item[0].casefold(), item[0], item[1].casefold(), item[1]))
+    )
+    return ImpactReport(origins=origins, impacted=ordered)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/rules.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/rules.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/rules.py	2026-08-25 13:41:38.138862264 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/rules.py	2026-08-25 20:53:01.375229890 -0300
@@ -347,20 +347,25 @@
         RuleSpec(
             "REQ015",
             "Expired evidence",
             "Evidence carrying an expiry attribute must still be valid.",
             "warning",
             evaluator=_evaluate_expired_evidence,
         ),
     )
 }
 
+# Bumped whenever a rule is added, removed, or its default severity changes.
+# The configuration fingerprint includes it so a rule-catalog change is never
+# mistaken for a project change.
+RULE_SET_VERSION = "1"
+
 for _spec in RULES.values():
     if getattr(_spec, "evaluator", None) is None and _spec.code not in LEGACY_CODES:
         raise RuntimeError(f"rule {_spec.code} lacks an evaluator")
 
 
 def _resolved_severity(spec: RuleSpec, config: NeedsConfig) -> str | None:
     """Return the effective severity, or None when the rule stays inactive.
 
     Governance rules (REQ008+) are opt-in: they activate only through an
     explicit `[rules.<CODE>]` entry. Legacy rules are always active because
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/snapshot.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/snapshot.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/src/quarto_needs/snapshot.py	2026-08-25 09:32:13.098541935 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/src/quarto_needs/snapshot.py	2026-08-25 21:17:41.730756974 -0300
@@ -151,20 +151,24 @@
     objects: tuple[ObjectRecord, ...]
     relations: tuple[RelationRecord, ...]
     findings: tuple[Finding, ...]
     metrics: Mapping[str, object]
     objects_by_id: Mapping[str, ObjectRecord]
     outgoing: Mapping[str, tuple[RelationRecord, ...]]
     incoming: Mapping[str, tuple[RelationRecord, ...]]
     generator_name: str
     generator_version: str
     relation_catalog_version: str
+    reference_date: str = ""
+    configuration_fingerprint: str = ""
+    semantic_graph_fingerprint: str = ""
+    representation_fingerprint: str = ""
 
     def __post_init__(self) -> None:
         object.__setattr__(self, "objects", tuple(self.objects))
         object.__setattr__(self, "relations", tuple(self.relations))
         object.__setattr__(self, "findings", tuple(self.findings))
         object.__setattr__(self, "metrics", _freeze_mapping(self.metrics))
         object.__setattr__(
             self, "objects_by_id", MappingProxyType(dict(self.objects_by_id))
         )
         object.__setattr__(
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_baseline.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_baseline.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_baseline.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_baseline.py	2026-08-26 14:41:42.613326042 -0300
@@ -0,0 +1,136 @@
+from __future__ import annotations
+
+import json
+from pathlib import Path
+
+import pytest
+from jsonschema import Draft202012Validator
+
+from quarto_needs import baseline
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+
+ROOT = Path(__file__).resolve().parents[1]
+SCHEMA = ROOT / "schemas" / "baseline-v1.schema.json"
+
+
+def write_project(root: Path) -> None:
+    (root / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=functional-requirement status=approved priority=high}\n"
+        "verified-by: TC-1\n"
+        "rationale: Protect data.\n"
+        "\n## Authenticate\nThe service shall authenticate.\n"
+        ":::\n"
+        "\n"
+        "::: {.need #TC-1 type=test-case status=passed}\n"
+        "\n## Login test\nSigns a user in.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+
+
+def validator() -> Draft202012Validator:
+    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
+    Draft202012Validator.check_schema(schema)
+    return Draft202012Validator(schema)
+
+
+def build(root: Path) -> dict[str, object]:
+    config = load_config(root)
+    result = analyze_project(root, config=config)
+    assert result.snapshot is not None
+    return baseline.build_baseline(result.snapshot, config)
+
+
+def test_baseline_validates_against_its_schema(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    validator().validate(build(tmp_path))
+
+
+def test_baseline_carries_both_comparison_axes(tmp_path: Path) -> None:
+    """Configuration and reference date are what make a round trip stable."""
+    write_project(tmp_path)
+    payload = build(tmp_path)
+
+    assert payload["valid"] is True
+    assert len(payload["configurationFingerprint"]) == 64
+    assert payload["referenceDate"]
+    assert payload["ruleSetVersion"] == "1"
+
+
+def test_baseline_stores_authored_content_not_only_fingerprints(tmp_path: Path) -> None:
+    """Diff reports modifications by field, which needs the field values."""
+    write_project(tmp_path)
+    payload = build(tmp_path)
+
+    requirement = next(item for item in payload["objects"] if item["id"] == "REQ-1")
+    assert requirement["title"] == "Authenticate"
+    assert requirement["rationale"].startswith("Protect")
+    assert requirement["attributes"]["priority"] == "high"
+    assert requirement["location"]["file"] == "needs.qmd"
+
+
+def test_baseline_render_is_byte_stable(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    # Pin the reference date so a run crossing local midnight cannot change
+    # referenceDate between the two builds.
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
+    write_project(tmp_path)
+
+    assert baseline.render_baseline(build(tmp_path)) == baseline.render_baseline(build(tmp_path))
+
+
+def test_write_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
+    """An overwritten baseline is unrecoverable without version control."""
+    write_project(tmp_path)
+    payload = build(tmp_path)
+    destination = tmp_path / "baselines" / "quarto-needs.json"
+    baseline.write_baseline(destination, payload)
+    sentinel = destination.read_text(encoding="utf-8")
+
+    with pytest.raises(baseline.BaselineError):
+        baseline.write_baseline(destination, payload)
+
+    assert destination.read_text(encoding="utf-8") == sentinel
+    baseline.write_baseline(destination, payload, force=True)
+
+
+def test_load_round_trips_and_rejects_malformed_input(tmp_path: Path) -> None:
+    write_project(tmp_path)
+    payload = build(tmp_path)
+    destination = tmp_path / "b.json"
+    baseline.write_baseline(destination, payload)
+
+    assert baseline.load_baseline(destination) == payload
+
+    broken = tmp_path / "broken.json"
+    broken.write_text("{ not json", encoding="utf-8")
+    with pytest.raises(baseline.BaselineError):
+        baseline.load_baseline(broken)
+
+    wrong_version = tmp_path / "v2.json"
+    wrong_version.write_text(json.dumps({"schemaVersion": "2"}), encoding="utf-8")
+    with pytest.raises(baseline.BaselineError):
+        baseline.load_baseline(wrong_version)
+
+
+def test_invalid_baseline_preserves_declarations_and_findings(tmp_path: Path) -> None:
+    """The diagnostic artifact exists so `inspect` can explain the failure."""
+    (tmp_path / "dup.qmd").write_text(
+        "::: {.need #D-1 type=need status=draft}\n\n## A\nA.\n:::\n"
+        "\n::: {.need #D-1 type=need status=draft}\n\n## B\nB.\n:::\n",
+        encoding="utf-8",
+    )
+    config = load_config(tmp_path)
+    result = analyze_project(tmp_path, config=config)
+    assert result.snapshot is None
+
+    payload = baseline.build_invalid_baseline(result, config)
+
+    validator().validate(payload)
+    assert payload["valid"] is False
+    assert payload["declarations"]
+    assert any(finding["code"] == "REQ004" for finding in payload["findings"])
+    assert "objects" not in payload
+    assert "semanticGraphFingerprint" not in payload
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_cli.py	2026-08-25 15:17:44.086062911 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_cli.py	2026-08-26 15:16:01.302026971 -0300
@@ -538,10 +538,390 @@
 
     def counted(root: Path, **kwargs: object):
         nonlocal calls
         calls += 1
         return real_analyze(root, **kwargs)
 
     monkeypatch.setattr(cli, "analyze_project", counted)
 
     assert cli.build(tmp_path, quiet=True) == 0
     assert calls == 1
+
+
+@pytest.mark.parametrize("arguments", [["check"], ["coverage"], ["export"], ["trace", "DUP-1"]])
+def test_invalid_input_still_runs_exactly_one_analysis(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: list[str]
+) -> None:
+    """A structurally invalid project must not be re-analyzed while reporting."""
+    write_duplicate_project(tmp_path)
+    calls = 0
+    real_analyze = cli.analyze_project
+
+    def counted(root: Path, **kwargs: object):
+        nonlocal calls
+        calls += 1
+        return real_analyze(root, **kwargs)
+
+    monkeypatch.setattr(cli, "analyze_project", counted)
+
+    cli.main(["--root", str(tmp_path), *arguments])
+    assert calls == 1
+
+
+def test_trace_orders_ids_case_insensitively_and_survives_cycles(
+    tmp_path: Path, capsys: pytest.CaptureFixture[str]
+) -> None:
+    """Traversal must terminate on a cycle among non-start nodes and sort
+    the reachable set case-insensitively.
+
+    REQ-A (start) --references--> sub-b --references--> SUB-C
+                                     ^-------references-------/
+
+    The B<->C subcycle excludes the start node, so a `seen`-set regression
+    (dropping the visited check while keeping only the `candidate != start`
+    filter) would loop forever bouncing between sub-b and SUB-C. The two
+    downstream ids are also cased so that a plain `sorted()` ("SUB-C" before
+    "sub-b", since uppercase sorts before lowercase in ASCII) disagrees with
+    the casefold-keyed order the CLI is supposed to produce ("sub-b" before
+    "SUB-C").
+    """
+    (tmp_path / "cycle.qmd").write_text(
+        "::: {.need #REQ-A type=need status=draft}\n"
+        "references: sub-b\n"
+        "\n## A\nA body.\n:::\n"
+        "\n"
+        "::: {.need #sub-b type=need status=draft}\n"
+        "references: SUB-C\n"
+        "\n## B\nB body.\n:::\n"
+        "\n"
+        "::: {.need #SUB-C type=need status=draft}\n"
+        "references: sub-b\n"
+        "\n## C\nC body.\n:::\n",
+        encoding="utf-8",
+    )
+
+    assert cli.main(["--root", str(tmp_path), "trace", "REQ-A"]) == 0
+
+    output = capsys.readouterr().out
+    assert output == (
+        "Upstream:\n"
+        "Downstream:\n"
+        "  sub-b\n"
+        "  SUB-C\n"
+    )
+
+
+def test_baseline_create_writes_the_default_path_with_one_analysis(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    write_valid_project(tmp_path)
+    calls = 0
+    real_analyze = cli.analyze_project
+
+    def counted(root: Path, **kwargs: object):
+        nonlocal calls
+        calls += 1
+        return real_analyze(root, **kwargs)
+
+    monkeypatch.setattr(cli, "analyze_project", counted)
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
+    assert calls == 1
+
+    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
+    assert payload["valid"] is True
+    assert payload["schemaVersion"] == "1"
+
+
+def test_baseline_create_refuses_to_clobber(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
+    destination = tmp_path / "baselines" / "quarto-needs.json"
+    sentinel = destination.read_text(encoding="utf-8")
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 2
+    assert destination.read_text(encoding="utf-8") == sentinel
+    assert "--force" in capsys.readouterr().err
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--force"]) == 0
+
+
+def test_baseline_create_refuses_invalid_input_without_the_flag(
+    tmp_path: Path, capsys
+) -> None:
+    """Structural failure must not silently become a comparison baseline."""
+    write_duplicate_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 1
+    assert not (tmp_path / "baselines" / "quarto-needs.json").exists()
+    assert "REQ004" in capsys.readouterr().err
+
+
+def test_baseline_create_allow_invalid_writes_a_diagnostic_artifact(tmp_path: Path) -> None:
+    write_duplicate_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"]) == 0
+
+    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
+    assert payload["valid"] is False
+    assert payload["declarations"]
+
+
+def test_baseline_inspect_reports_both_variants(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    destination = str(tmp_path / "baselines" / "quarto-needs.json")
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination, "--format", "json"]) == 0
+    summary = json.loads(capsys.readouterr().out)
+    assert summary["valid"] is True
+    assert summary["objects"] == 3
+    assert summary["referenceDate"]
+
+    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination]) == 0
+    assert "objects" in capsys.readouterr().out
+
+
+def test_baseline_inspect_reports_a_missing_file_as_usage_error(tmp_path: Path) -> None:
+    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", str(tmp_path / "nope.json")]) == 2
+
+
+def test_diff_against_an_unchanged_project_is_empty_and_exits_zero(
+    tmp_path: Path, capsys
+) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    destination = str(tmp_path / "baselines" / "quarto-needs.json")
+
+    assert cli.main(["--root", str(tmp_path), "diff", destination, "--format", "json"]) == 0
+
+    payload = json.loads(capsys.readouterr().out)
+    assert payload["empty"] is True
+    assert payload["notices"] == []
+
+
+def test_diff_validates_against_the_diff_schema(tmp_path: Path, capsys) -> None:
+    from jsonschema import Draft202012Validator
+
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json"])
+    payload = json.loads(capsys.readouterr().out)
+
+    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "diff-v1.schema.json").read_text(encoding="utf-8"))
+    Draft202012Validator.check_schema(schema)
+    Draft202012Validator(schema).validate(payload)
+
+
+def test_diff_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    calls = 0
+    real_analyze = cli.analyze_project
+
+    def counted(root: Path, **kwargs: object):
+        nonlocal calls
+        calls += 1
+        return real_analyze(root, **kwargs)
+
+    monkeypatch.setattr(cli, "analyze_project", counted)
+
+    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")])
+    assert calls == 1
+
+
+def test_diff_rejects_a_diagnostic_baseline(tmp_path: Path, capsys) -> None:
+    write_duplicate_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"])
+    (tmp_path / "duplicates.qmd").unlink()
+    write_valid_project(tmp_path)
+
+    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")]) == 2
+    assert "diagnostic artifact" in capsys.readouterr().err
+
+
+def test_diff_reports_a_missing_baseline_as_usage_error(tmp_path: Path) -> None:
+    write_valid_project(tmp_path)
+    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "absent.json")]) == 2
+
+
+def test_diff_recompute_with_current_clears_notices(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    destination = tmp_path / "baselines" / "quarto-needs.json"
+    payload = json.loads(destination.read_text(encoding="utf-8"))
+    payload["referenceDate"] = "1999-01-01"
+    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
+
+    cli.main(["--root", str(tmp_path), "diff", str(destination), "--format", "json"])
+    assert "reference-date-changed" in json.loads(capsys.readouterr().out)["notices"]
+
+    cli.main([
+        "--root", str(tmp_path), "diff", str(destination),
+        "--recompute-with", "current", "--format", "json",
+    ])
+    assert json.loads(capsys.readouterr().out)["notices"] == []
+
+
+def test_impact_validates_against_the_impact_schema(tmp_path: Path, capsys) -> None:
+    from jsonschema import Draft202012Validator
+
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    capsys.readouterr()  # flush the create command's text output before the JSON run
+    (tmp_path / "needs.qmd").write_text(
+        (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace("First body.", "Changed body."),
+        encoding="utf-8",
+    )
+
+    assert cli.main([
+        "--root", str(tmp_path), "impact",
+        str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json",
+    ]) == 0
+    payload = json.loads(capsys.readouterr().out)
+
+    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "impact-v1.schema.json").read_text(encoding="utf-8"))
+    Draft202012Validator.check_schema(schema)
+    Draft202012Validator(schema).validate(payload)
+    assert payload["origins"]
+
+
+def test_impact_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    calls = 0
+    real_analyze = cli.analyze_project
+
+    def counted(root: Path, **kwargs: object):
+        nonlocal calls
+        calls += 1
+        return real_analyze(root, **kwargs)
+
+    monkeypatch.setattr(cli, "analyze_project", counted)
+
+    cli.main(["--root", str(tmp_path), "impact", str(tmp_path / "baselines" / "quarto-needs.json")])
+    assert calls == 1
+
+
+def test_impact_rejects_a_configuration_mismatch(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    cli.main(["--root", str(tmp_path), "baseline", "create"])
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
+    )
+
+    destination = str(tmp_path / "baselines" / "quarto-needs.json")
+    assert cli.main(["--root", str(tmp_path), "impact", destination]) == 2
+    assert "--recompute-with" in capsys.readouterr().err
+
+    assert cli.main(["--root", str(tmp_path), "impact", destination, "--recompute-with", "current"]) == 0
+
+
+def test_scan_on_an_unwritable_root_is_operational_failure(tmp_path: Path, capsys) -> None:
+    """Read-only scan targets are exit 3, not a traceback."""
+    import os
+
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+    target = tmp_path / "locked"
+    target.mkdir()
+    (target / "needs.qmd").write_text(
+        "::: {.need #REQ-2 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+    os.chmod(target, 0o500)
+
+    try:
+        assert cli.main(["--root", str(target), "scan"]) == 3
+        assert "Could not" in capsys.readouterr().err
+    finally:
+        os.chmod(target, 0o700)
+
+
+def test_export_to_an_unwritable_directory_is_operational_failure(tmp_path: Path, capsys) -> None:
+    """A failed artifact write exits 3 and names the artifact."""
+    import os
+
+    write_valid_project(tmp_path)
+    locked = tmp_path / "locked"
+    locked.mkdir()
+    os.chmod(locked, 0o500)
+
+    try:
+        destination = locked / "sub" / "needs.json"
+        assert cli.main(["--root", str(tmp_path), "export", "--output", str(destination)]) == 3
+        assert str(destination) in capsys.readouterr().err
+    finally:
+        os.chmod(locked, 0o700)
+
+
+def test_export_default_format_is_byte_identical_to_the_v1_projection(tmp_path: Path) -> None:
+    """No --format must mean today's json output, byte for byte."""
+    import hashlib
+
+    write_valid_project(tmp_path)
+    first = tmp_path / "a.json"
+    second = tmp_path / "b.json"
+    assert cli.main(["--root", str(tmp_path), "export", "--output", str(first)]) == 0
+    assert cli.main(["--root", str(tmp_path), "export", "--format", "json", "--output", str(second)]) == 0
+
+    assert first.read_bytes() == second.read_bytes()
+    assert len(hashlib.sha256(first.read_bytes()).hexdigest()) == 64
+
+
+# TODO(milestone-4a-writers): remove this xfail when Tasks 3-6 land the writers.
+@pytest.mark.xfail(strict=True, reason="csv/sarif/junit writers land in Tasks 3-6")
+def test_export_runs_exactly_one_analysis_per_format(
+    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    write_valid_project(tmp_path)
+    calls = 0
+    real_analyze = cli.analyze_project
+
+    def counted(root: Path, **kwargs: object):
+        nonlocal calls
+        calls += 1
+        return real_analyze(root, **kwargs)
+
+    monkeypatch.setattr(cli, "analyze_project", counted)
+
+    for name in ("json", "csv", "sarif", "junit", "markdown"):
+        destination = tmp_path / "out" / name
+        assert cli.main([
+            "--root", str(tmp_path), "export", "--format", name,
+            "--output", str(destination / "artifact"),
+        ]) in (0, 1), name
+    assert calls == 5
+
+
+def test_export_rejects_baseline_for_non_markdown_formats(tmp_path: Path, capsys) -> None:
+    write_valid_project(tmp_path)
+    assert cli.main([
+        "--root", str(tmp_path), "export", "--format", "sarif",
+        "--output", str(tmp_path / "out.sarif"), "--baseline", str(tmp_path / "none.json"),
+    ]) == 2
+    assert "markdown" in capsys.readouterr().err
+
+
+# TODO(milestone-4a-writers): remove this xfail when Task 6 lands the markdown writer.
+@pytest.mark.xfail(strict=True, reason="markdown writer lands in Task 6")
+def test_export_preserves_artifacts_on_policy_failure(tmp_path: Path) -> None:
+    """A failing strict gate still writes the artifact, then exits 1."""
+    # An approved requirement with no verification makes the verification gate
+    # fail with a non-zero denominator (an empty scope passes vacuously).
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
+        "\n## Authenticate\nBody.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n', encoding="utf-8"
+    )
+    destination = tmp_path / "artifacts" / "report.md"
+
+    assert cli.main(["--root", str(tmp_path), "export", "--format", "markdown", "--output", str(destination)]) == 1
+    assert destination.is_file()
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_config.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_config.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_config.py	2026-08-25 12:28:57.592445266 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_config.py	2026-08-25 21:05:25.424898054 -0300
@@ -1,23 +1,26 @@
 from __future__ import annotations
 
+import json
 from datetime import date
 from pathlib import Path
 
 import pytest
 
 from quarto_needs.config import (
     ConfigurationError,
     Gates,
     NeedsConfig,
     RelationPolicy,
     RuleSetting,
+    embedded_defaults,
+    load_config,
     reference_date,
 )
 
 
 def test_missing_file_yields_embedded_defaults(tmp_path: Path) -> None:
     config = load = __import__("quarto_needs.config", fromlist=["load_config"]).load_config(tmp_path)
     assert isinstance(config, NeedsConfig)
     assert config.profile == "default"
     assert config.rule_settings == {}
     assert config.named_query_sources == {}
@@ -115,10 +118,84 @@
     monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
     assert reference_date() == date.today()
 
 
 def test_config_is_immutable(tmp_path: Path) -> None:
     from quarto_needs.config import load_config
 
     config = load_config(tmp_path)
     with pytest.raises(Exception):
         config.profile = "strict"  # type: ignore[misc]
+
+
+def test_canonical_document_is_order_independent(tmp_path: Path) -> None:
+    """Two spellings of the same policy must canonicalize identically."""
+    first = tmp_path / "first"
+    second = tmp_path / "second"
+    first.mkdir()
+    second.mkdir()
+    (first / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n'
+        '[types.functional-requirement]\nrequired-attributes = ["priority", "tags"]\n'
+        '[types.test-case]\nrequired-attributes = ["tags"]\n',
+        encoding="utf-8",
+    )
+    (second / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n'
+        '[types.test-case]\nrequired-attributes = ["tags"]\n'
+        '[types.functional-requirement]\nrequired-attributes = ["priority", "tags"]\n',
+        encoding="utf-8",
+    )
+
+    assert json.dumps(load_config(first).canonical_document()) == json.dumps(
+        load_config(second).canonical_document()
+    )
+
+
+def test_canonical_document_excludes_presence_and_path(tmp_path: Path) -> None:
+    """Presence controls artifact projection, not graph semantics."""
+    (tmp_path / ".quarto-needs.toml").write_text("", encoding="utf-8")
+
+    from_file = load_config(tmp_path).canonical_document()
+    embedded = embedded_defaults().canonical_document()
+
+    assert from_file == embedded
+    assert "present" not in from_file
+    assert not any("quarto-needs.toml" in str(value) for value in from_file.values())
+
+
+def test_canonical_document_reflects_every_policy_section(tmp_path: Path) -> None:
+    """A change in any supported section must change the canonical document."""
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "advisory"\n'
+        '[types.requirement]\nrequired-attributes = ["priority"]\n'
+        '[relations."verified-by"]\nallowed-target-types = ["test-case"]\n'
+        '[governance]\ntest-types = ["test-case"]\n'
+        '[rules.REQ011]\nenabled = true\n'
+        '[queries.q]\nall = [{ field = "status", op = "eq", value = "approved" }]\n'
+        '[gates]\nmax-errors = 3\n',
+        encoding="utf-8",
+    )
+
+    document = load_config(tmp_path).canonical_document()
+
+    assert document["profile"] == "advisory"
+    assert document["types"]["requirement"]["required-attributes"] == ["priority"]
+    assert document["relations"]["verified-by"]["allowed-target-types"] == ["test-case"]
+    assert document["governance"]["test-types"] == ["test-case"]
+    assert document["rules"]["REQ011"]["enabled"] is True
+    assert "q" in document["queries"]
+    assert document["gates"]["max-errors"] == 3
+
+
+def test_canonical_document_rejects_non_json_query_values(tmp_path: Path) -> None:
+    """Query values must be JSON-serializable; TOML native dates are not."""
+    (tmp_path / ".quarto-needs.toml").write_text(
+        '[queries.q]\nall = [{ field = "status", op = "eq", value = 2026-01-01 }]\n',
+        encoding="utf-8",
+    )
+
+    config = load_config(tmp_path)
+    with pytest.raises(
+        ConfigurationError, match="contains a value that is not valid JSON"
+    ):
+        config.canonical_document()
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_diff.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_diff.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_diff.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_diff.py	2026-08-26 09:40:42.266829023 -0300
@@ -0,0 +1,303 @@
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
+
+from quarto_needs import baseline, diff
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+
+REQUIREMENT = (
+    "::: {{.need #REQ-1 type=system-requirement status=approved priority=high}}\n"
+    "verified-by: TC-1\n"
+    "\n## Authenticate\n{body}\n"
+    "\n### Rationale\nProtect data.\n"
+    ":::\n"
+)
+TEST_CASE = "::: {.need #TC-1 type=test-case status=passed}\n\n## Login\nSigns in.\n:::\n"
+
+
+def write(root: Path, *, body: str = "The service shall authenticate.", order: str = "requirement-first", file: str = "needs.qmd") -> None:
+    for existing in root.glob("*.qmd"):
+        existing.unlink()
+    blocks = [REQUIREMENT.format(body=body), TEST_CASE]
+    if order != "requirement-first":
+        blocks.reverse()
+    (root / file).write_text("\n".join(blocks), encoding="utf-8")
+
+
+def snapshot_of(root: Path):
+    config = load_config(root)
+    result = analyze_project(root, config=config)
+    assert result.snapshot is not None
+    return result.snapshot, config
+
+
+def baseline_of(root: Path) -> dict[str, object]:
+    snapshot, config = snapshot_of(root)
+    return baseline.build_baseline(snapshot, config)
+
+
+def test_identical_input_produces_an_empty_diff(tmp_path: Path) -> None:
+    """The round-trip guarantee the milestone gate names."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert report.is_empty()
+    assert report.notices == ()
+
+
+def test_reordering_declarations_is_not_a_change(tmp_path: Path) -> None:
+    """Swapping two blocks in a file changes nothing semantic."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, order="test-first")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert report.modified == ()
+    assert report.relocated == ()
+    assert report.is_empty()
+
+
+def test_moving_a_need_to_another_file_is_relocation_only(tmp_path: Path) -> None:
+    """File change is a relocation record; content is untouched."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, file="moved.qmd")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert report.modified == ()
+    assert {item["id"] for item in report.relocated} == {"REQ-1", "TC-1"}
+    moved = next(item for item in report.relocated if item["id"] == "REQ-1")
+    assert moved["from"]["file"] == "needs.qmd"
+    assert moved["to"]["file"] == "moved.qmd"
+    assert "line" in moved["from"] and "line" in moved["to"]
+
+
+def test_editing_a_body_is_a_modification_named_by_field(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, body="The service shall authenticate every administrator.")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert [item["id"] for item in report.modified] == ["REQ-1"]
+    assert report.modified[0]["fields"] == ["body"]
+    assert report.relocated == ()
+
+
+def test_added_and_removed_objects_are_classified(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / "extra.qmd").write_text(
+        "::: {.need #REQ-2 type=functional-requirement status=draft}\n\n## Second\nBody.\n:::\n",
+        encoding="utf-8",
+    )
+    (tmp_path / "needs.qmd").write_text(
+        REQUIREMENT.format(body="The service shall authenticate.").replace("verified-by: TC-1\n", ""),
+        encoding="utf-8",
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert report.added_objects == ("REQ-2",)
+    assert report.removed_objects == ("TC-1",)
+
+
+def test_a_changed_id_is_removal_plus_addition(tmp_path: Path) -> None:
+    """Rename detection is deliberately excluded; it is inherently heuristic."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / "needs.qmd").write_text(
+        REQUIREMENT.format(body="The service shall authenticate.").replace("#REQ-1", "#REQ-9")
+        + "\n" + TEST_CASE,
+        encoding="utf-8",
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert "REQ-9" in report.added_objects
+    assert "REQ-1" in report.removed_objects
+    assert report.modified == ()
+
+
+def test_configuration_change_suppresses_derived_deltas(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert "configuration-changed" in report.notices
+    assert report.findings_added == ()
+    assert report.gate_regressions == ()
+
+
+def test_reference_date_change_suppresses_date_derived_deltas(tmp_path: Path) -> None:
+    """Evidence coverage and REQ015 depend on the date, not on authored content."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    before = {**before, "referenceDate": "1999-01-01"}
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert "reference-date-changed" in report.notices
+    assert report.metric_deltas == ()
+    assert report.findings_added == ()
+
+
+def test_recompute_clears_the_guards(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    before = {**before, "referenceDate": "1999-01-01"}
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config, recompute=True)
+
+    assert report.notices == ()
+    assert report.recomputed is True
+
+
+def test_recompute_does_not_manufacture_derived_deltas_from_a_config_change(tmp_path: Path) -> None:
+    """The baseline stores its derived results; they cannot be re-derived, so a
+    config-only change must stay silent even under recompute.
+
+    REQ-2 is approved but unverified, so verification coverage is 1 of 2 (50%).
+    The baseline is taken under the default configuration (no verification
+    gate); only then does the configuration grow a 100.0 threshold. Authored
+    content never moves — any derived delta is manufactured by the config edit.
+    """
+    write(tmp_path)
+    (tmp_path / "extra.qmd").write_text(
+        "::: {.need #REQ-2 type=system-requirement status=approved priority=low}\n"
+        "\n## Second\nSecond body.\n"
+        "\n### Rationale\nSecond why.\n"
+        ":::\n",
+        encoding="utf-8",
+    )
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        "[gates]\nmin-verification-trace = 100.0\n", encoding="utf-8"
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config, recompute=True)
+
+    assert report.notices == ()
+    assert report.modified == ()
+    assert report.gate_regressions == ()
+    assert report.metric_deltas == ()
+    assert report.findings_added == ()
+
+
+def test_configuration_change_still_compares_authored_relations(tmp_path: Path) -> None:
+    """Authored comparison keeps running; only the derived deltas stop."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text('profile = "strict"\n', encoding="utf-8")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert "configuration-changed" in report.notices
+    assert report.added_relations == ()
+    assert report.removed_relations == ()
+    assert report.representation_changes == ()
+    assert report.modified == ()
+
+
+def test_recompute_reresolves_baseline_relations_through_the_catalog(tmp_path: Path) -> None:
+    """Stored families are not trusted; authored names are resolved again."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    poisoned = {
+        **before,
+        "relations": [
+            {**item, "semanticFamily": "bogus", "semanticFingerprint": "0" * 64}
+            for item in before["relations"]
+        ],
+    }
+    snapshot, config = snapshot_of(tmp_path)
+
+    assert diff.compare(poisoned, snapshot, config).added_relations != ()
+    assert diff.compare(poisoned, snapshot, config, recompute=True).added_relations == ()
+
+
+def test_an_invalid_baseline_is_never_comparable(tmp_path: Path) -> None:
+    write(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(diff.DiffError):
+        diff.compare({"schemaVersion": "1", "valid": False}, snapshot, config)
+
+
+def test_new_findings_are_reported_when_the_configuration_is_stable(tmp_path: Path) -> None:
+    """A warning that appears with no policy change is a real regression."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    # Drop the rationale: REQ002 fires, and nothing about the policy moved.
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
+        "verified-by: TC-1\n"
+        "\n## Authenticate\nThe service shall authenticate.\n"
+        ":::\n" + "\n" + TEST_CASE,
+        encoding="utf-8",
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    assert any(item["code"] == "REQ002" for item in report.findings_added)
+    assert report.notices == ()
+
+
+def test_metric_deltas_name_the_scope_and_strength(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    # Remove the verification edge: verification coverage drops.
+    (tmp_path / "needs.qmd").write_text(
+        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
+        "\n## Authenticate\nThe service shall authenticate.\n"
+        "\n### Rationale\nProtect data.\n"
+        ":::\n" + "\n" + TEST_CASE,
+        encoding="utf-8",
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = diff.compare(before, snapshot, config)
+
+    verification = [
+        item for item in report.metric_deltas
+        if item["scope"] == "approved-requirements" and item["strength"] == "verification-trace"
+    ]
+    assert verification
+    assert verification[0]["before"] > verification[0]["after"]
+
+
+def test_report_dict_is_json_safe_and_flags_emptiness(tmp_path: Path) -> None:
+    import json as _json
+
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    payload = diff.compare(before, snapshot, config).to_dict()
+
+    assert payload["empty"] is True
+    assert payload["schemaVersion"] == "1"
+    _json.dumps(payload)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_example_project.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_example_project.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_example_project.py	2026-08-25 15:18:54.737894300 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_example_project.py	2026-08-26 15:11:45.458373391 -0300
@@ -207,20 +207,96 @@
 
     assert (
         cli.main(
             ["--root", str(ROOT / "examples/book"), "query", "approved-high-unverified"]
         )
         == 0
     )
     assert cli.main(["--root", str(ROOT / "examples/book"), "query", "evidence-gaps"]) == 0
 
 
+def test_aegis_baseline_round_trips_to_an_empty_diff(
+    monkeypatch: pytest.MonkeyPatch,
+    capsys: pytest.CaptureFixture[str],
+):
+    """The gate: a checked-in baseline must still describe the published book.
+
+    Exit code alone is not the gate: `diff`'s exit code reflects only gate
+    regressions, so a modified object or an added/removed relation can leave
+    it at 0. The reference date is also pinned to the baseline's own stored
+    date, derived from the artifact rather than hard-coded, so this test
+    cannot decay into a tautological pass on any day after the baseline was
+    created — a differing reference date would otherwise emit
+    `reference-date-changed` and silently suppress every derived delta.
+    """
+    import json as _json
+    from datetime import datetime, timezone
+
+    from quarto_needs import cli
+
+    root = ROOT / "examples/book"
+    baseline_path = root / "baselines" / "quarto-needs.json"
+    assert baseline_path.is_file(), "run `make baseline-example` to create it"
+
+    payload = _json.loads(baseline_path.read_text(encoding="utf-8"))
+    assert payload["valid"] is True
+    assert payload["schemaVersion"] == "1"
+
+    reference_date = datetime.strptime(payload["referenceDate"], "%Y-%m-%d").replace(
+        tzinfo=timezone.utc
+    )
+    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(int(reference_date.timestamp())))
+
+    exit_code = cli.main(
+        ["--root", str(root), "diff", str(baseline_path), "--format", "json"]
+    )
+    diff_payload = _json.loads(capsys.readouterr().out)
+
+    assert exit_code == 0
+    assert diff_payload["empty"] is True
+    assert diff_payload["notices"] == []
+
+
+def test_aegis_baseline_validates_against_the_baseline_schema():
+    import json as _json
+    from jsonschema import Draft202012Validator
+
+    schema = _json.loads((ROOT / "schemas" / "baseline-v1.schema.json").read_text(encoding="utf-8"))
+    payload = _json.loads((ROOT / "examples/book/baselines/quarto-needs.json").read_text(encoding="utf-8"))
+    Draft202012Validator.check_schema(schema)
+    Draft202012Validator(schema).validate(payload)
+
+
+def test_aegis_impact_explains_a_removed_verification(tmp_path: Path):
+    """Removing an edge in a copy of the book must reach the requirement."""
+    import shutil as _shutil
+    from quarto_needs import cli
+
+    project = tmp_path / "book"
+    _shutil.copytree(ROOT / "examples/book", project, ignore=_shutil.ignore_patterns("_book", ".quarto"))
+    baseline_path = project / "baselines" / "quarto-needs.json"
+
+    system = project / "requirements" / "system.qmd"
+    system.write_text(
+        system.read_text(encoding="utf-8").replace('verified-by="IAM-TC-001"', "", 1),
+        encoding="utf-8",
+    )
+
+    # The checked-in baseline predates the run day, and impact (per spec)
+    # rejects a reference-date mismatch; the documented escape hatch keeps the
+    # showcase runnable on any date.
+    assert cli.main([
+        "--root", str(project), "impact", str(baseline_path),
+        "--recompute-with", "current", "--format", "json",
+    ]) == 0
+
+
 def test_aegis_quality_report_projects_passing_gates():
     """The projected report the dashboard reads must agree with the CLI verdict."""
     import json as _json
 
     graph = _json.loads(
         (ROOT / "examples/book/.quarto-needs/needs.json").read_text(encoding="utf-8")
     )
     report = graph["extensions"]["quartoNeeds"]["report"]
 
     assert report["profile"] == "strict"
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_fingerprints.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_fingerprints.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_fingerprints.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_fingerprints.py	2026-08-26 00:49:44.521332899 -0300
@@ -0,0 +1,121 @@
+from __future__ import annotations
+
+from quarto_needs import fingerprints
+from quarto_needs.config import embedded_defaults
+from quarto_needs.snapshot import LocationRecord, ObjectRecord, RelationRecord
+
+
+def make_object(**overrides: object) -> ObjectRecord:
+    base = dict(
+        id="REQ-1",
+        type="functional-requirement",
+        title="Authenticate",
+        status="approved",
+        body="The service shall authenticate.",
+        rationale="Protect data.",
+        attributes={"priority": "high", "tags": "security"},
+        locations=(LocationRecord("a.qmd", 10, "REQ-1"),),
+    )
+    base.update(overrides)
+    return ObjectRecord(**base)
+
+
+def make_relation(**overrides: object) -> RelationRecord:
+    base = dict(
+        source="REQ-1",
+        authored_name="verified-by",
+        catalog_name="verified-by",
+        v1_name="verified-by",
+        target="TC-1",
+        semantic_family="verification",
+        source_role="requirement",
+        target_role="test",
+        impact_direction="source_to_target",
+        attributes={},
+        provenance=(LocationRecord("a.qmd", 12, None),),
+    )
+    base.update(overrides)
+    return RelationRecord(**base)
+
+
+def test_object_fingerprint_ignores_line_numbers_and_file() -> None:
+    """Provenance is not authored semantics; moving a need must not modify it."""
+    moved = make_object(locations=(LocationRecord("b.qmd", 900, "REQ-1"),))
+
+    assert fingerprints.object_content_fingerprint(make_object()) == \
+        fingerprints.object_content_fingerprint(moved)
+
+
+def test_object_fingerprint_changes_with_every_authored_field() -> None:
+    """Each field the spec names must actually participate."""
+    original = fingerprints.object_content_fingerprint(make_object())
+    for field, value in (
+        ("id", "REQ-2"),
+        ("type", "system-requirement"),
+        ("title", "Other"),
+        ("status", "draft"),
+        ("body", "Different body."),
+        ("rationale", "Different rationale."),
+        # Vary priority and tags separately so each computed property is proven
+        # to participate on its own.
+        ("attributes", {"priority": "low", "tags": "security"}),
+        ("attributes", {"priority": "high", "tags": "authentication"}),
+    ):
+        assert fingerprints.object_content_fingerprint(make_object(**{field: value})) != original, field
+
+
+def test_alias_flip_keeps_the_semantic_fingerprint_and_changes_representation() -> None:
+    """REQ -verified-by-> TC and TC -verifies-> REQ are one semantic edge."""
+    forward = make_relation()
+    inverse = make_relation(
+        source="TC-1",
+        authored_name="verifies",
+        catalog_name="verifies",
+        v1_name="verifies",
+        target="REQ-1",
+        source_role="test",
+        target_role="requirement",
+        impact_direction="target_to_source",
+    )
+
+    assert fingerprints.relation_semantic_fingerprint(forward) == \
+        fingerprints.relation_semantic_fingerprint(inverse)
+    assert fingerprints.relation_authored_fingerprint(forward) != \
+        fingerprints.relation_authored_fingerprint(inverse)
+
+
+def test_semantic_relation_fingerprint_changes_with_family_and_endpoints() -> None:
+    original = fingerprints.relation_semantic_fingerprint(make_relation())
+
+    assert fingerprints.relation_semantic_fingerprint(make_relation(semantic_family="evidence")) != original
+    assert fingerprints.relation_semantic_fingerprint(make_relation(target="TC-2")) != original
+    assert fingerprints.relation_semantic_fingerprint(make_relation(source="REQ-2")) != original
+    assert fingerprints.relation_semantic_fingerprint(make_relation(attributes={"note": "x"})) != original
+
+
+def test_graph_fingerprint_is_order_independent_and_configuration_sensitive() -> None:
+    """Reordering declarations is not a change; changing policy is."""
+    objects = [make_object(), make_object(id="REQ-2")]
+    relations = [make_relation(), make_relation(target="TC-2")]
+    configuration = fingerprints.configuration_fingerprint(
+        embedded_defaults(), relation_catalog_version="1"
+    )
+
+    forward = fingerprints.semantic_graph_fingerprint(objects, relations, configuration)
+    reversed_order = fingerprints.semantic_graph_fingerprint(
+        list(reversed(objects)), list(reversed(relations)), configuration
+    )
+    other_configuration = fingerprints.semantic_graph_fingerprint(
+        objects, relations, configuration="different"
+    )
+
+    assert forward == reversed_order
+    assert forward != other_configuration
+
+
+def test_configuration_fingerprint_tracks_catalog_and_rule_set_versions() -> None:
+    """A catalog-only change must be visible as a configuration change."""
+    config = embedded_defaults()
+
+    assert fingerprints.configuration_fingerprint(config, relation_catalog_version="1") != \
+        fingerprints.configuration_fingerprint(config, relation_catalog_version="2")
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_impact.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_impact.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_impact.py	1969-12-31 21:00:00.000000000 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_impact.py	2026-08-26 11:08:49.858273901 -0300
@@ -0,0 +1,179 @@
+from __future__ import annotations
+
+from pathlib import Path
+
+import pytest
+
+from quarto_needs import baseline, impact
+from quarto_needs.analysis import analyze_project
+from quarto_needs.config import load_config
+
+CHAIN = """::: {{.need #STK-1 type=stakeholder-need status=approved priority=high}}
+
+## Stakeholder
+Needs secure access.
+:::
+
+::: {{.need #REQ-1 type=functional-requirement status=approved priority=high}}
+derives-from: STK-1
+verified-by: TC-1
+conflicts-with: DOC-1
+
+## Authenticate
+{body}
+
+### Rationale
+Protect data.
+:::
+
+::: {{.need #DOC-1 type=need status=draft}}
+
+## Manual
+Login manual.
+:::
+
+::: {{.need #TC-1 type=test-case status=passed}}
+
+## Login
+Signs in.
+:::
+"""
+
+
+def write(root: Path, *, body: str = "The service shall authenticate.", keep_test: bool = True) -> None:
+    text = CHAIN.format(body=body)
+    if not keep_test:
+        text = text.split("::: {.need #TC-1", 1)[0].replace("verified-by: TC-1\n", "")
+    (root / "chain.qmd").write_text(text, encoding="utf-8")
+
+
+def snapshot_of(root: Path):
+    config = load_config(root)
+    result = analyze_project(root, config=config)
+    assert result.snapshot is not None
+    return result.snapshot, config
+
+
+def baseline_of(root: Path) -> dict[str, object]:
+    snapshot, config = snapshot_of(root)
+    return baseline.build_baseline(snapshot, config)
+
+
+def test_no_change_produces_no_impact(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    assert report.origins == ()
+    assert report.impacted == ()
+
+
+def test_editing_a_requirement_impacts_its_verification(tmp_path: Path) -> None:
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, body="The service shall authenticate every administrator.")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    assert [item["id"] for item in report.origins] == ["REQ-1"]
+    impacted = {item["id"]: item for item in report.impacted}
+    assert "TC-1" in impacted
+    assert impacted["TC-1"]["classification"] == "direct"
+    assert impacted["TC-1"]["distance"] == 1
+    assert impacted["TC-1"]["path"] == ["REQ-1", "TC-1"]
+    assert impacted["TC-1"]["relations"] == ["verified-by"]
+
+
+def test_every_impacted_result_carries_an_explicit_path(tmp_path: Path) -> None:
+    """The gate forbids an opaque score; a path is the audit trail."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, body="Changed.")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    assert report.impacted
+    for item in report.impacted:
+        assert item["path"][0] == item["origin"]
+        assert item["path"][-1] == item["id"]
+        assert len(item["path"]) == item["distance"] + 1
+        assert item["classification"] in {"direct", "transitive"}
+        assert "priority" in item
+
+
+def test_removing_a_node_still_explains_its_neighbors(tmp_path: Path) -> None:
+    """Union traversal is why a removed node and its removed edges stay explainable.
+
+    `verified-by` propagates from requirement to test, so the removed test case
+    cannot reach the requirement it verified; the removal surfaces instead as
+    two origins — the removed node and the requirement that lost the edge.
+    """
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    write(tmp_path, keep_test=False)
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    changes = {item["id"]: item["change"] for item in report.origins}
+    assert changes.get("TC-1") == "removed"
+    assert changes.get("REQ-1") == "relation-removed"
+
+
+def test_removal_reaches_neighbors_through_baseline_only_edges(tmp_path: Path) -> None:
+    """A dropped `conflicts-with` still propagates: the edge exists only in the
+    baseline, so without the union adjacency DOC-1 would be unreachable."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    text = (tmp_path / "chain.qmd").read_text(encoding="utf-8").replace("conflicts-with: DOC-1\n", "")
+    (tmp_path / "chain.qmd").write_text(text, encoding="utf-8")
+    snapshot, config = snapshot_of(tmp_path)
+
+    report = impact.analyze(before, snapshot, config)
+
+    changes = {item["id"]: item["change"] for item in report.origins}
+    assert changes.get("REQ-1") == "relation-removed"
+    doc = next(item for item in report.impacted if item["id"] == "DOC-1")
+    assert doc["classification"] == "direct"
+    assert doc["relations"] == ["conflicts-with"]
+
+
+def test_impact_rejects_a_configuration_mismatch_without_recompute(tmp_path: Path) -> None:
+    """One relation policy must govern the whole traversal."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    (tmp_path / ".quarto-needs.toml").write_text(
+        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
+    )
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(impact.ImpactError):
+        impact.analyze(before, snapshot, config)
+
+    assert impact.analyze(before, snapshot, config, recompute=True) is not None
+
+
+def test_impact_rejects_a_reference_date_mismatch_without_recompute(tmp_path: Path) -> None:
+    """The reference date is a comparison axis for impact too (spec: impact
+    rejects the mismatch)."""
+    write(tmp_path)
+    before = baseline_of(tmp_path)
+    before = {**before, "referenceDate": "1999-01-01"}
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(impact.ImpactError):
+        impact.analyze(before, snapshot, config)
+
+    assert impact.analyze(before, snapshot, config, recompute=True) is not None
+
+
+def test_impact_rejects_a_diagnostic_baseline(tmp_path: Path) -> None:
+    write(tmp_path)
+    snapshot, config = snapshot_of(tmp_path)
+
+    with pytest.raises(impact.ImpactError):
+        impact.analyze({"schemaVersion": "1", "valid": False}, snapshot, config)
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_relations.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_relations.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_relations.py	2026-08-25 09:20:24.628799388 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_relations.py	2026-08-25 16:58:09.419161357 -0300
@@ -36,10 +36,24 @@
         "derived-from: REQ-1\n\n"
         "## Derived requirement\n"
         ":::\n",
         encoding="utf-8",
     )
 
     relation = parse_qmd(source)[0].relations[0]
 
     assert relation.authored_name == "derived-from"
     assert relation.type == "derives-from"
+
+
+def test_engineering_object_to_dict_omits_authored_name() -> None:
+    """authored_name is additive internal state and must stay out of v1 output."""
+    from quarto_needs.model import EngineeringObject, Relation
+
+    obj = EngineeringObject(id="REQ-1", type="functional-requirement", title="T", status="draft")
+    obj.relations.append(Relation("derives-from", "REQ-1", "STK-1", {}))
+    obj.relations[0].authored_name = "derived-from"
+
+    payload = obj.to_dict()
+
+    assert payload["relations"][0]["type"] == "derives-from"
+    assert "authored_name" not in payload["relations"][0]
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_snapshot.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_snapshot.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_snapshot.py	2026-08-25 09:29:03.318949909 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_snapshot.py	2026-08-25 21:17:31.450782966 -0300
@@ -1,10 +1,11 @@
+from pathlib import Path
 from types import MappingProxyType
 
 import pytest
 
 from quarto_needs.snapshot import freeze_json, thaw_json
 
 
 def test_freeze_json_is_recursive_and_round_trips() -> None:
     source = {"tags": ["security", "login"], "nested": {"rank": 1}}
 
@@ -12,10 +13,28 @@
     source["tags"].append("mutated")
 
     assert isinstance(frozen, MappingProxyType)
     assert frozen["tags"] == ("security", "login")
     with pytest.raises(TypeError):
         frozen["nested"]["rank"] = 2
     assert thaw_json(frozen) == {
         "nested": {"rank": 1},
         "tags": ["security", "login"],
     }
+
+
+def test_snapshot_records_reference_date_and_fingerprints(tmp_path: Path) -> None:
+    """Baselines need every comparison axis from the snapshot itself."""
+    from quarto_needs.analysis import analyze_project
+    from quarto_needs.config import reference_date
+
+    (tmp_path / "a.qmd").write_text(
+        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
+    )
+
+    snapshot = analyze_project(tmp_path).snapshot
+
+    assert snapshot is not None
+    assert snapshot.reference_date == reference_date().isoformat()
+    assert len(snapshot.configuration_fingerprint) == 64
+    assert len(snapshot.semantic_graph_fingerprint) == 64
+    assert len(snapshot.representation_fingerprint) == 64
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_v1_contract.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_v1_contract.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_v1_contract.py	2026-08-25 11:27:45.886107139 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-11-fix1/tests/test_v1_contract.py	2026-08-25 16:57:56.827194479 -0300
@@ -1,16 +1,18 @@
 from __future__ import annotations
 
 import json
 from pathlib import Path
 
-from jsonschema import Draft202012Validator, RefResolver
+from jsonschema import Draft202012Validator
+from referencing import Registry, Resource
+from referencing.jsonschema import DRAFT202012
 
 from quarto_needs.analysis import analyze_project
 from quarto_needs.export import render_v1_json
 
 ROOT = Path(__file__).resolve().parents[1]
 SCHEMAS = ROOT / "schemas"
 GOLDEN = ROOT / "tests/fixtures/v1/aegis-needs-v1.json"
 
 
 def load_json(path: Path) -> dict[str, object]:
@@ -43,30 +45,28 @@
                 relation["type"], relation["target"].casefold(), relation["target"],
                 json.dumps(relation.get("attributes", {}), ensure_ascii=False, sort_keys=True),
             ),
         )
     return projected
 
 
 def envelope_validator() -> Draft202012Validator:
     schema = load_json(SCHEMAS / "needs-envelope-v1.schema.json")
     Draft202012Validator.check_schema(schema)
-    resolver = RefResolver(
-        (SCHEMAS / "needs-envelope-v1.schema.json").as_uri(),
-        schema,
-        store={
-            "https://quarto-needs.dev/schema/needs.schema.json": load_json(
-                SCHEMAS / "needs.schema.json"
-            )
-        },
+    registry = Registry().with_resource(
+        "https://quarto-needs.dev/schema/needs.schema.json",
+        Resource.from_contents(
+            load_json(SCHEMAS / "needs.schema.json"),
+            default_specification=DRAFT202012,
+        ),
     )
-    return Draft202012Validator(schema, resolver=resolver)
+    return Draft202012Validator(schema, registry=registry)
 
 
 def test_frozen_aegis_payload_validates_against_v1_envelope() -> None:
     envelope_validator().validate(load_json(GOLDEN))
 
 
 def test_regenerated_aegis_graph_validates_against_v1_envelope() -> None:
     """The checked-in regenerated artifact stays schema-valid, extensions included."""
     payload = load_json(ROOT / "examples/book/.quarto-needs/needs.json")
     envelope_validator().validate(payload)
```
