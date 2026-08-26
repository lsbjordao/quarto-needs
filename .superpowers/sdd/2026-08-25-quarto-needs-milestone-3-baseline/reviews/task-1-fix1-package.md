# Review package

Snapshot range: `task-1-after` -> `task-1-fix1`

## Files changed (2)

- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `tests/test_cli.py`

## Summary

31 lines added, 8 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-25 16:49:49.608611780 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-25 17:04:47.350114594 -0300
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
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/tests/test_cli.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-fix1/tests/test_cli.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-after/tests/test_cli.py	2026-08-25 16:58:23.871123343 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-1-fix1/tests/test_cli.py	2026-08-25 20:46:10.864585396 -0300
@@ -563,26 +563,48 @@
 
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
