# Review package

Snapshot range: `task-1-before` -> `task-1-after`

## Files changed (4)

- `pyproject.toml`
- `tests/test_cli.py`
- `tests/test_relations.py`
- `tests/test_v1_contract.py`

## Summary

66 lines added, 10 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/pyproject.toml .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/pyproject.toml
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/pyproject.toml	2026-08-25 09:13:06.774378133 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/pyproject.toml	2026-08-25 16:57:23.887281125 -0300
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
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/tests/test_cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_cli.py	2026-08-25 15:17:44.086062911 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/tests/test_cli.py	2026-08-25 16:58:23.871123343 -0300
@@ -538,10 +538,51 @@
 
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
+    """Traversal must terminate on a cycle and sort deterministically."""
+    (tmp_path / "cycle.qmd").write_text(
+        "::: {.need #req-b type=need status=draft}\n"
+        "references: REQ-A\n"
+        "\n## B\nB body.\n:::\n"
+        "\n"
+        "::: {.need #REQ-A type=need status=draft}\n"
+        "references: req-b\n"
+        "\n## A\nA body.\n:::\n",
+        encoding="utf-8",
+    )
+
+    assert cli.main(["--root", str(tmp_path), "trace", "REQ-A"]) == 0
+
+    output = capsys.readouterr().out
+    assert "req-b" in output
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_relations.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/tests/test_relations.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_relations.py	2026-08-25 09:20:24.628799388 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/tests/test_relations.py	2026-08-25 16:58:09.419161357 -0300
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
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_v1_contract.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/tests/test_v1_contract.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-before/tests/test_v1_contract.py	2026-08-25 11:27:45.886107139 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/tests/test_v1_contract.py	2026-08-25 16:57:56.827194479 -0300
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
