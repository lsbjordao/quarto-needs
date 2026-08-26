# Review package

Snapshot range: `task-2-before` -> `task-2-after`

## Files changed (3)

- `src/quarto_needs/config.py`
- `src/quarto_needs/rules.py`
- `tests/test_config.py`

## Summary

113 lines added, 0 lines removed.

## Full diff (10 lines of context)

```diff
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-before/src/quarto_needs/config.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/src/quarto_needs/config.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-before/src/quarto_needs/config.py	2026-08-25 13:41:25.830887852 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/src/quarto_needs/config.py	2026-08-25 20:52:51.459262632 -0300
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
@@ -92,20 +94,68 @@
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
+        Excludes `present` and the file path: presence controls artifact
+        projection, not graph semantics, and the path is environment-specific.
+        """
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
+            "queries": {
+                name: thaw_json(freeze_json(dict(source)))
+                for name, source in sorted(self.named_query_sources.items())
+            },
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
 
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-before/src/quarto_needs/rules.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/src/quarto_needs/rules.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-before/src/quarto_needs/rules.py	2026-08-25 13:41:38.138862264 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/src/quarto_needs/rules.py	2026-08-25 20:53:01.375229890 -0300
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
diff -ruN '--unified=10' .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-before/tests/test_config.py .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/tests/test_config.py
--- .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-before/tests/test_config.py	2026-08-25 12:28:57.592445266 -0300
+++ .superpowers/sdd/2026-08-25-quarto-needs-milestone-3-baseline/snapshots/task-2-after/tests/test_config.py	2026-08-25 20:52:28.083339821 -0300
@@ -4,20 +4,22 @@
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
@@ -115,10 +117,66 @@
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
+    assert load_config(first).canonical_document() == load_config(second).canonical_document()
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
+    assert document["relations"]["verified-by"]["allowed-target-types"] == ["test-case"]
+    assert document["governance"]["test-types"] == ["test-case"]
+    assert document["rules"]["REQ011"]["enabled"] is True
+    assert "q" in document["queries"]
+    assert document["gates"]["max-errors"] == 3
```
