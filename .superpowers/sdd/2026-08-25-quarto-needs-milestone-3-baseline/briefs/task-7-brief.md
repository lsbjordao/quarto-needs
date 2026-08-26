# Task 7: Diff engine — findings, metrics, gates, and `compare`

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

## Task 7

Diff engine — findings, metrics, gates, and `compare`

**Files:**
- Modify: `src/quarto_needs/diff.py`
- Modify: `tests/test_diff.py`

**Interfaces:**
- Consumes: the helpers and `DiffReport` from Task 6.
- Produces: `diff.compare(baseline_payload, snapshot, config, *, recompute=False) -> DiffReport`, consumed by Task 8.

- [ ] **Step 1: Write the failing derived-delta tests**

Append to `tests/test_diff.py`:

```python
def test_new_findings_are_reported_when_the_configuration_is_stable(tmp_path: Path) -> None:
    """A warning that appears with no policy change is a real regression."""
    write(tmp_path)
    before = baseline_of(tmp_path)
    # Drop the rationale: REQ002 fires, and nothing about the policy moved.
    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
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
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        "\n### Rationale\nProtect data.\n"
        ":::\n" + "\n" + TEST_CASE,
        encoding="utf-8",
    )
    snapshot, config = snapshot_of(tmp_path)

    report = diff.compare(before, snapshot, config)

    verification = [
        item for item in report.metric_deltas
        if item["scope"] == "approved-requirements" and item["strength"] == "verification-trace"
    ]
    assert verification
    assert verification[0]["before"] > verification[0]["after"]


def test_report_dict_is_json_safe_and_flags_emptiness(tmp_path: Path) -> None:
    import json as _json

    write(tmp_path)
    before = baseline_of(tmp_path)
    snapshot, config = snapshot_of(tmp_path)

    payload = diff.compare(before, snapshot, config).to_dict()

    assert payload["empty"] is True
    assert payload["schemaVersion"] == "1"
    _json.dumps(payload)
```

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_diff.py -q`

Expected: FAIL with `AttributeError: module 'quarto_needs.diff' has no attribute 'compare'`.

- [ ] **Step 3: Implement the derived-delta helpers**

Append to `diff.py`:

```python
def _finding_key(item: Mapping[str, object]) -> tuple[str, str, str]:
    return (str(item.get("code")), str(item.get("object_id") or ""), str(item.get("message")))


def _classify_findings(
    before: Sequence[Mapping[str, object]], after: Sequence[Mapping[str, object]]
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    before_keys = {_finding_key(item): item for item in before}
    after_keys = {_finding_key(item): item for item in after}
    added = tuple(
        {"code": key[0], "object_id": key[1] or None, "message": key[2], "severity": after_keys[key].get("severity")}
        for key in sorted(set(after_keys) - set(before_keys))
    )
    removed = tuple(
        {"code": key[0], "object_id": key[1] or None, "message": key[2], "severity": before_keys[key].get("severity")}
        for key in sorted(set(before_keys) - set(after_keys))
    )
    return added, removed


def _classify_metrics(
    before: Mapping[str, object], after: Mapping[str, object]
) -> tuple[dict[str, object], ...]:
    deltas: list[dict[str, object]] = []
    before_scopes = before.get("scopes", {}) if isinstance(before, Mapping) else {}
    after_scopes = after.get("scopes", {})
    for scope in sorted(set(before_scopes) | set(after_scopes)):
        old_coverage = (before_scopes.get(scope) or {}).get("coverage", {})
        new_coverage = (after_scopes.get(scope) or {}).get("coverage", {})
        for strength in sorted(set(old_coverage) | set(new_coverage)):
            old_percent = (old_coverage.get(strength) or {}).get("percent")
            new_percent = (new_coverage.get(strength) or {}).get("percent")
            if old_percent != new_percent:
                deltas.append(
                    {"scope": scope, "strength": strength, "before": old_percent, "after": new_percent}
                )
    return tuple(deltas)


def _classify_gates(
    before: Mapping[str, object], after: Mapping[str, object]
) -> tuple[dict[str, object], ...]:
    """Only pass -> fail is a regression; fail -> pass is progress, not a delta."""
    before_gates = {
        str(item["name"]): item for item in (before.get("gates", []) if isinstance(before, Mapping) else [])
    }
    regressions: list[dict[str, object]] = []
    for item in after.get("gates", []):
        name = str(item["name"])
        was = before_gates.get(name)
        if item.get("passed") is False and (was is None or was.get("passed") is not False):
            regressions.append(
                {"name": name, "scope": item.get("scope"), "threshold": item.get("threshold"), "actual": item.get("actual")}
            )
    return tuple(regressions)
```

- [ ] **Step 4: Implement `compare` with both guards**

Append to `diff.py`:

```python
def _recomputed_relations(stored: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Re-resolve stored relations through the *current* catalog.

    `--recompute-with current` must compare both sides under one policy, so the
    baseline's authored names are resolved again rather than trusting the
    families and roles that were canonical when it was written.
    """
    from .relations import DEFAULT_RELATION_CATALOG
    from .snapshot import RelationRecord

    recomputed: list[dict[str, object]] = []
    for item in stored:
        authored = str(item["authoredName"])
        try:
            kind = DEFAULT_RELATION_CATALOG.resolve(authored)
        except ValueError:
            # An authored name the current catalog no longer knows cannot be
            # re-resolved; keep it verbatim so it surfaces as a real change.
            recomputed.append(dict(item))
            continue
        record = RelationRecord(
            source=str(item["source"]),
            authored_name=authored,
            catalog_name=kind.catalog_name,
            v1_name=kind.v1_name,
            target=str(item["target"]),
            semantic_family=kind.semantic_family,
            source_role=kind.source_role,
            target_role=kind.target_role,
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
                "authoredFingerprint": fingerprints.relation_authored_fingerprint(record),
                "semanticFingerprint": fingerprints.relation_semantic_fingerprint(record),
            }
        )
    return recomputed


def compare(
    baseline_payload: Mapping[str, object],
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    recompute: bool = False,
) -> DiffReport:
    if not baseline_payload.get("valid", False):
        raise DiffError(
            "This baseline is a diagnostic artifact (valid: false) and cannot be compared; "
            "use `baseline inspect` to read it"
        )

    current_configuration = snapshot.configuration_fingerprint
    baseline_configuration = str(baseline_payload.get("configurationFingerprint", ""))
    baseline_date = str(baseline_payload.get("referenceDate", ""))

    notices: list[str] = []
    configuration_differs = baseline_configuration != current_configuration
    date_differs = baseline_date != snapshot.reference_date
    if not recompute:
        if configuration_differs:
            notices.append("configuration-changed")
        if date_differs:
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

    # Derived results are stored in the baseline, never re-derived, so they are
    # comparable only when both sides were produced under the same rules and
    # the same reference date. `recompute` re-resolves authored relations
    # through the current catalog; it cannot make stored findings, metrics, or
    # gates comparable, so their deltas stay suppressed silently there.
    derived_suppressed = configuration_differs or date_differs
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
        )
        metric_deltas = _classify_metrics(baseline_report, current_report)
        gate_regressions = _classify_gates(baseline_report, current_report)

    return DiffReport(
        baseline_reference_date=baseline_date,
        current_reference_date=snapshot.reference_date,
        recomputed=recompute,
        notices=tuple(notices),
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
        gate_regressions=gate_regressions,
    )
```

Note the deliberate asymmetry: a configuration change still reports **authored** object and relation changes, exactly as the spec requires ("default `diff` compares authored object content and authored relation tuples only"). Only the derived categories are suppressed.

- [ ] **Step 5: Run the diff tests**

Run: `.venv/bin/python -m pytest tests/test_diff.py -q`

Expected: PASS, all sixteen.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 7: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/diff.py tests/test_diff.py
  git commit -m "feat: complete the semantic diff engine"
else
  echo "Checkpoint 7 verified; workspace has no Git metadata."
fi
```
