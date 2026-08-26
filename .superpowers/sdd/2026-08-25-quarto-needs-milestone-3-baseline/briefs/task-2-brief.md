# Task 2: Canonical configuration form and rule-set version

> Extracted from `docs/superpowers/plans/2026-08-25-quarto-needs-milestone-3-baseline.md`. This brief is your complete requirements.
> Use every value in it verbatim.

## Global Constraints (bind every task)

- Do not add a runtime dependency. `referencing` enters the `test` optional dependency group only; it already ships as a `jsonschema` dependency.
- One analysis per command invocation. `baseline create`, `diff`, and `impact` each call `analyze_project` exactly once, matching the Milestone 1 guarantee locked by `tests/test_cli.py`.
- Preserve every existing signature and documented behavior: `parse_qmd`, `parse_project`, `RequirementsGraph.build`, `validate`, `coverage`, `export_graph`, `export_lua_index`, `cli.build`, `build_v1_payload`, `write_build_outputs`, `report_from_snapshot`, `build_quality_report`, and every existing CLI command and shortcode.
- Preserve schema v1 exactly. Fingerprints and baselines are new, separately named and versioned schemas. Nothing in this milestone changes `needs.json` bytes for a project whose configuration and reference date are unchanged.
- Fingerprints exclude line numbers, `href` values, generated metrics, and every other derived value.
- Exit codes are stable: `0` success, `1` validation or policy failure, `2` invalid usage or configuration, `3` operational I/O or serialization failure.
- Generated artifacts are deterministic for a fixed configuration and a fixed reference date, and are written atomically through `export._write_atomic_text`.
- The workspace has no `.git` metadata. Do not initialize Git. Every task ends with a conditional checkpoint that records a commit only when the executor is inside a Git worktree.
- Do not stop or restart the preview server listening on `127.0.0.1:8777`.
- Milestone 3 adds no Quarto shortcode and no `extensions.quartoNeeds` projection for diff or impact. `need-graph` and the interactive graph remain Milestone 5A.

## Task 2

Canonical configuration form and rule-set version

**Files:**
- Modify: `src/quarto_needs/config.py`
- Modify: `src/quarto_needs/rules.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `NeedsConfig.canonical_document() -> dict[str, object]` and `rules.RULE_SET_VERSION: str`, both consumed by `fingerprints.configuration_fingerprint` in Task 3.

- [ ] **Step 1: Write the failing canonicalization tests**

Add to `tests/test_config.py`:

```python
def test_canonical_document_is_order_independent(tmp_path: Path) -> None:
    """Two spellings of the same policy must canonicalize identically."""
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / ".quarto-needs.toml").write_text(
        'profile = "strict"\n'
        '[types.functional-requirement]\nrequired-attributes = ["priority", "tags"]\n'
        '[types.test-case]\nrequired-attributes = ["tags"]\n',
        encoding="utf-8",
    )
    (second / ".quarto-needs.toml").write_text(
        'profile = "strict"\n'
        '[types.test-case]\nrequired-attributes = ["tags"]\n'
        '[types.functional-requirement]\nrequired-attributes = ["priority", "tags"]\n',
        encoding="utf-8",
    )

    assert load_config(first).canonical_document() == load_config(second).canonical_document()


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
        '[relations."verified-by"]\nallowed-target-types = ["test-case"]\n'
        '[governance]\ntest-types = ["test-case"]\n'
        '[rules.REQ011]\nenabled = true\n'
        '[queries.q]\nall = [{ field = "status", op = "eq", value = "approved" }]\n'
        '[gates]\nmax-errors = 3\n',
        encoding="utf-8",
    )

    document = load_config(tmp_path).canonical_document()

    assert document["profile"] == "advisory"
    assert document["relations"]["verified-by"]["allowed-target-types"] == ["test-case"]
    assert document["governance"]["test-types"] == ["test-case"]
    assert document["rules"]["REQ011"]["enabled"] is True
    assert "q" in document["queries"]
    assert document["gates"]["max-errors"] == 3
```

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py -q -k canonical_document`

Expected: FAIL with `AttributeError: 'NeedsConfig' object has no attribute 'canonical_document'`.

- [ ] **Step 3: Implement `canonical_document`**

Add as a method on `NeedsConfig` in `src/quarto_needs/config.py`. Every container is converted to a plain, sorted, JSON-safe structure so the fingerprint hashes one spelling per policy:

```python
    def canonical_document(self) -> dict[str, object]:
        """The single canonical form the configuration fingerprint hashes.

        Excludes `present` and the file path: presence controls artifact
        projection, not graph semantics, and the path is environment-specific.
        """
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
                    "minimum-per-source": policy.minimum_per_source,
                    "maximum-per-source": policy.maximum_per_source,
                }
                for name, policy in sorted(self.relation_policies.items())
            },
            "governance": {
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
            "queries": {
                name: thaw_json(freeze_json(dict(source)))
                for name, source in sorted(self.named_query_sources.items())
            },
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
        }
```

Add `from .snapshot import freeze_json, thaw_json` to the imports. `freeze_json` sorts nested query mappings deterministically; `thaw_json` returns plain JSON containers.

- [ ] **Step 4: Add the rule-set version**

In `src/quarto_needs/rules.py`, next to the `RULES` registry:

```python
# Bumped whenever a rule is added, removed, or its default severity changes.
# The configuration fingerprint includes it so a rule-catalog change is never
# mistaken for a project change.
RULE_SET_VERSION = "1"
```

Add `"RULE_SET_VERSION"` to that module's `__all__` if one exists; otherwise no export change is needed.

- [ ] **Step 5: Run the config tests**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 7: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/config.py src/quarto_needs/rules.py tests/test_config.py
  git commit -m "feat: add canonical configuration document and rule set version"
else
  echo "Checkpoint 2 verified; workspace has no Git metadata."
fi
```
