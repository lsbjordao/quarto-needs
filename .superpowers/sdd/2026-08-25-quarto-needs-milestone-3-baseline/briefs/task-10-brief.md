# Task 10: `impact` command and its schema

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

## Task 10

`impact` command and its schema

**Files:**
- Modify: `src/quarto_needs/cli.py`
- Create: `schemas/impact-v1.schema.json`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `impact.analyze` from Task 9.
- Produces: `cli.main(["impact", <path>, "--format", "json", "--recompute-with", "current"])`.

- [ ] **Step 1: Write the impact JSON Schema**

Create `schemas/impact-v1.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schema/impact-v1.schema.json",
  "title": "Quarto-Needs impact v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "origins", "impacted"],
  "properties": {
    "schemaVersion": {"const": "1"},
    "origins": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "change"],
        "properties": {
          "id": {"type": "string"},
          "change": {"enum": ["added", "removed", "modified", "relation-added", "relation-removed"]},
          "fields": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "impacted": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "origin", "change", "classification", "distance", "relations", "path", "priority"],
        "properties": {
          "id": {"type": "string"},
          "origin": {"type": "string"},
          "change": {"type": "string"},
          "classification": {"enum": ["direct", "transitive"]},
          "distance": {"type": "integer", "minimum": 1},
          "relations": {"type": "array", "items": {"type": "string"}, "minItems": 1},
          "path": {"type": "array", "items": {"type": "string"}, "minItems": 2},
          "priority": {"type": ["string", "null"]}
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing CLI tests**

Add to `tests/test_cli.py`:

```python
def test_impact_validates_against_the_impact_schema(tmp_path: Path, capsys) -> None:
    from jsonschema import Draft202012Validator

    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    (tmp_path / "needs.qmd").write_text(
        (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace("First body.", "Changed body."),
        encoding="utf-8",
    )

    assert cli.main([
        "--root", str(tmp_path), "impact",
        str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)

    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "impact-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    assert payload["origins"]


def test_impact_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    cli.main(["--root", str(tmp_path), "impact", str(tmp_path / "baselines" / "quarto-needs.json")])
    assert calls == 1


def test_impact_rejects_a_configuration_mismatch(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
    )

    destination = str(tmp_path / "baselines" / "quarto-needs.json")
    assert cli.main(["--root", str(tmp_path), "impact", destination]) == 2
    assert "--recompute-with" in capsys.readouterr().err

    assert cli.main(["--root", str(tmp_path), "impact", destination, "--recompute-with", "current"]) == 0
```

- [ ] **Step 3: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k impact`

Expected: FAIL with `SystemExit: 2` — the `impact` command does not exist.

- [ ] **Step 4: Register the command**

In `main`, after the `diff` parser block:

```python
    impact_parser = sub.add_parser("impact", help="Explain what a baseline's changes reach")
    impact_parser.add_argument("baseline")
    impact_parser.add_argument("--format", choices=("text", "json"), default="text")
    impact_parser.add_argument(
        "--recompute-with",
        choices=("current",),
        dest="recompute_with",
        help="Re-resolve the baseline's relations under the current configuration and reference date",
    )
```

Add `from . import impact as impact_module` to the imports.

- [ ] **Step 5: Implement the handler**

Add above `main`:

```python
def _impact(root: Path, args, config: NeedsConfig) -> int:
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
        report = impact_module.analyze(
            baseline_payload,
            result.snapshot,
            config,
            recompute=args.recompute_with == "current",
        )
    except impact_module.ImpactError as error:
        print(str(error), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return 0
    if not report.origins:
        print("No changes to propagate.")
        return 0
    for origin in report.origins:
        print(f"origin {origin['id']} ({origin['change']})")
    for item in report.impacted:
        print(
            f"  {item['classification']} d={item['distance']} {item['id']}"
            f" via {' -> '.join(item['path'])}"
            f" [{', '.join(item['relations'])}]"
        )
    return 0
```

- [ ] **Step 6: Route the command**

In `main`, next to the `diff` dispatch:

```python
    if args.command == "impact":
        return _impact(root, args, config)
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
  git add src/quarto_needs/cli.py schemas/impact-v1.schema.json tests/test_cli.py
  git commit -m "feat: add the impact command"
else
  echo "Checkpoint 10 verified; workspace has no Git metadata."
fi
```
