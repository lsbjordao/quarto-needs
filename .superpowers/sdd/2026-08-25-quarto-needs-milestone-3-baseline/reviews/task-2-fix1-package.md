# Review package

Snapshot range: `task-2-after` -> `task-2-fix1`

## Files changed (3)

- `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`
- `src/quarto_needs/config.py`
- `tests/test_config.py`

## Summary

67 lines added, 14 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-25 20:48:53.196049377 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-fix1/docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md	2026-08-25 21:04:43.613025593 -0300
@@ -249,74 +249,106 @@
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
@@ -329,24 +361,21 @@
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
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/src/quarto_needs/config.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-fix1/src/quarto_needs/config.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/src/quarto_needs/config.py	2026-08-25 20:52:51.459262632 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-fix1/src/quarto_needs/config.py	2026-08-25 21:06:19.052734474 -0300
@@ -97,23 +97,31 @@
     successful_test_statuses: tuple[str, ...]
     expiry_attribute: str
     rule_settings: Mapping[str, RuleSetting]
     named_query_sources: Mapping[str, Mapping[str, Any]]
     gates: Gates
     present: bool = False
 
     def canonical_document(self) -> dict[str, object]:
         """The single canonical form the configuration fingerprint hashes.
 
-        Excludes `present` and the file path: presence controls artifact
-        projection, not graph semantics, and the path is environment-specific.
+        Excludes `present` and the configuration file's path: presence controls
+        artifact projection, not graph semantics, and the path is environment-specific.
         """
+        try:
+            queries = {
+                name: thaw_json(freeze_json(dict(source)))
+                for name, source in sorted(self.named_query_sources.items())
+            }
+        except TypeError as error:
+            raise _fail(f"[queries] contains a value that is not valid JSON: {error}") from error
+
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
@@ -126,24 +134,21 @@
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
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/tests/test_config.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-fix1/tests/test_config.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/tests/test_config.py	2026-08-25 20:52:28.083339821 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-fix1/tests/test_config.py	2026-08-25 21:05:25.424898054 -0300
@@ -1,12 +1,13 @@
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
@@ -138,45 +139,63 @@
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
+        '[types.requirement]\nrequired-attributes = ["priority"]\n'
         '[relations."verified-by"]\nallowed-target-types = ["test-case"]\n'
         '[governance]\ntest-types = ["test-case"]\n'
         '[rules.REQ011]\nenabled = true\n'
         '[queries.q]\nall = [{ field = "status", op = "eq", value = "approved" }]\n'
         '[gates]\nmax-errors = 3\n',
         encoding="utf-8",
     )
 
     document = load_config(tmp_path).canonical_document()
 
     assert document["profile"] == "advisory"
+    assert document["types"]["requirement"]["required-attributes"] == ["priority"]
     assert document["relations"]["verified-by"]["allowed-target-types"] == ["test-case"]
     assert document["governance"]["test-types"] == ["test-case"]
     assert document["rules"]["REQ011"]["enabled"] is True
     assert "q" in document["queries"]
     assert document["gates"]["max-errors"] == 3
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
```
