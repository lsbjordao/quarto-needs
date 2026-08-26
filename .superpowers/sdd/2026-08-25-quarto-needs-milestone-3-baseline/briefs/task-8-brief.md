# Task 8: `diff` command and its schema

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

## Task 8

`diff` command and its schema

**Files:**
- Modify: `src/quarto_needs/cli.py`
- Create: `schemas/diff-v1.schema.json`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `diff.compare` from Task 7, `baseline.load_baseline` from Task 4.
- Produces: `cli.main(["diff", <path>, "--format", "json", "--recompute-with", "current"])`.

- [ ] **Step 1: Write the diff JSON Schema**

Create `schemas/diff-v1.schema.json` matching `DiffReport.to_dict()` exactly:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schema/diff-v1.schema.json",
  "title": "Quarto-Needs diff v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "referenceDate", "recomputed", "notices", "objects", "relations", "findings", "metrics", "gates", "empty"],
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
        "relocated": {"type": "array", "items": {"type": "object"}}
      }
    },
    "relations": {
      "type": "object",
      "additionalProperties": false,
      "required": ["added", "removed", "representationChanged"],
      "properties": {
        "added": {"type": "array", "items": {"type": "object"}},
        "removed": {"type": "array", "items": {"type": "object"}},
        "representationChanged": {"type": "array", "items": {"type": "object"}}
      }
    },
    "findings": {
      "type": "object",
      "additionalProperties": false,
      "required": ["added", "removed"],
      "properties": {
        "added": {"type": "array", "items": {"type": "object"}},
        "removed": {"type": "array", "items": {"type": "object"}}
      }
    },
    "metrics": {"type": "array", "items": {"type": "object"}},
    "gates": {
      "type": "object",
      "additionalProperties": false,
      "required": ["regressed"],
      "properties": {"regressed": {"type": "array", "items": {"type": "object"}}}
    },
    "empty": {"type": "boolean"}
  }
}
```

- [ ] **Step 2: Write the failing CLI tests**

Add to `tests/test_cli.py`:

```python
def test_diff_against_an_unchanged_project_is_empty_and_exits_zero(
    tmp_path: Path, capsys
) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    destination = str(tmp_path / "baselines" / "quarto-needs.json")

    assert cli.main(["--root", str(tmp_path), "diff", destination, "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["empty"] is True
    assert payload["notices"] == []


def test_diff_validates_against_the_diff_schema(tmp_path: Path, capsys) -> None:
    from jsonschema import Draft202012Validator

    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "diff-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_diff_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")])
    assert calls == 1


def test_diff_rejects_a_diagnostic_baseline(tmp_path: Path, capsys) -> None:
    write_duplicate_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"])
    (tmp_path / "duplicates.qmd").unlink()
    write_valid_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")]) == 2
    assert "diagnostic artifact" in capsys.readouterr().err


def test_diff_reports_a_missing_baseline_as_usage_error(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "absent.json")]) == 2


def test_diff_recompute_with_current_clears_notices(tmp_path: Path, capsys) -> None:
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
    assert json.loads(capsys.readouterr().out)["notices"] == []
```

- [ ] **Step 3: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k diff`

Expected: FAIL with `SystemExit: 2` — the `diff` command does not exist.

- [ ] **Step 4: Register the command**

In `main`, after the `baseline` parser block:

```python
    diff_parser = sub.add_parser("diff", help="Compare a baseline against the current graph")
    diff_parser.add_argument("baseline")
    diff_parser.add_argument("--format", choices=("text", "json"), default="text")
    diff_parser.add_argument(
        "--recompute-with",
        choices=("current",),
        dest="recompute_with",
        help="Re-resolve the baseline's relations under the current configuration and reference date",
    )
```

Add `from . import diff as diff_module` to the imports.

- [ ] **Step 5: Implement the handler**

Add above `main`:

```python
def _print_diff_text(report) -> None:
    for notice in report.notices:
        print(f"[notice] {notice}: derived deltas suppressed; both sides must share configuration and reference date to compare them")
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
        print(f"> object {item['id']} moved {item['from'].get('file')} -> {item['to'].get('file')}")
    for item in report.added_relations:
        print(f"+ relation {item['source']} {item['authoredName']} {item['target']}")
    for item in report.removed_relations:
        print(f"- relation {item['source']} {item['authoredName']} {item['target']}")
    for item in report.representation_changes:
        print(f"= relation {item['source']} -> {item['target']} respelled {item['from']} -> {item['to']}")
    for item in report.findings_added:
        print(f"+ finding {item['code']} {item['object_id'] or ''}".rstrip())
    for item in report.findings_removed:
        print(f"- finding {item['code']} {item['object_id'] or ''}".rstrip())
    for item in report.metric_deltas:
        print(f"~ metric {item['scope']}/{item['strength']} {item['before']} -> {item['after']}")
    for item in report.gate_regressions:
        print(f"! gate {item['name']} failed (threshold {item['threshold']}, actual {item['actual']})")


def _diff(root: Path, args, config: NeedsConfig) -> int:
    try:
        baseline_payload = load_baseline(Path(args.baseline))
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    result = analyze_project(root, config=config)
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
    except diff_module.DiffError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        _print_diff_text(report)
    return profile_exit_code(config.profile, False, len(report.gate_regressions))
```

Add `profile_exit_code` to the existing `from .quality import ...` line.

- [ ] **Step 6: Route the command**

In `main`, alongside the `baseline` dispatch and before the shared analysis line:

```python
    if args.command == "diff":
        return _diff(root, args, config)
```

- [ ] **Step 7: Run the CLI tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`

Expected: PASS.

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 9: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/cli.py schemas/diff-v1.schema.json tests/test_cli.py
  git commit -m "feat: add the diff command"
else
  echo "Checkpoint 8 verified; workspace has no Git metadata."
fi
```
