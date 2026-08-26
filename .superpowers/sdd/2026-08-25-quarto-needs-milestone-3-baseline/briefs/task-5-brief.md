# Task 5: `baseline create` and `baseline inspect`

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

## Task 5

`baseline create` and `baseline inspect`

**Files:**
- Modify: `src/quarto_needs/cli.py:186-205`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: every `baseline` function from Task 4.
- Produces: `cli.main(["baseline", "create", ...])` and `cli.main(["baseline", "inspect", <path>])`, both honoring `--format text|json`.

- [ ] **Step 1: Write the failing CLI tests**

Add to `tests/test_cli.py`:

```python
def test_baseline_create_writes_the_default_path_with_one_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_valid_project(tmp_path)
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
    assert calls == 1

    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["schemaVersion"] == "1"


def test_baseline_create_refuses_to_clobber(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
    destination = tmp_path / "baselines" / "quarto-needs.json"
    sentinel = destination.read_text(encoding="utf-8")

    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 2
    assert destination.read_text(encoding="utf-8") == sentinel
    assert "--force" in capsys.readouterr().err

    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--force"]) == 0


def test_baseline_create_refuses_invalid_input_without_the_flag(
    tmp_path: Path, capsys
) -> None:
    """Structural failure must not silently become a comparison baseline."""
    write_duplicate_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 1
    assert not (tmp_path / "baselines" / "quarto-needs.json").exists()
    assert "REQ004" in capsys.readouterr().err


def test_baseline_create_allow_invalid_writes_a_diagnostic_artifact(tmp_path: Path) -> None:
    write_duplicate_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"]) == 0

    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
    assert payload["valid"] is False
    assert payload["declarations"]


def test_baseline_inspect_reports_both_variants(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    destination = str(tmp_path / "baselines" / "quarto-needs.json")

    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination, "--format", "json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["valid"] is True
    assert summary["objects"] == 3
    assert summary["referenceDate"]

    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination]) == 0
    assert "objects" in capsys.readouterr().out


def test_baseline_inspect_reports_a_missing_file_as_usage_error(tmp_path: Path) -> None:
    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", str(tmp_path / "nope.json")]) == 2
```

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k baseline`

Expected: FAIL with `SystemExit: 2` from argparse — the `baseline` command does not exist.

- [ ] **Step 3: Register the nested subcommand**

In `main`, after the `query` parser block and before `args = parser.parse_args(argv)`:

```python
    baseline_parser = sub.add_parser("baseline", help="Create or inspect a canonical baseline")
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_command", required=True)
    baseline_create = baseline_sub.add_parser("create", help="Write a baseline for the current graph")
    baseline_create.add_argument("--output", default=str(DEFAULT_BASELINE_PATH))
    baseline_create.add_argument("--force", action="store_true", help="Overwrite an existing baseline")
    baseline_create.add_argument(
        "--allow-invalid",
        action="store_true",
        help="Write a diagnostic artifact for a structurally invalid project",
    )
    baseline_create.add_argument("--format", choices=("text", "json"), default="text")
    baseline_inspect = baseline_sub.add_parser("inspect", help="Summarize an existing baseline")
    baseline_inspect.add_argument("baseline")
    baseline_inspect.add_argument("--format", choices=("text", "json"), default="text")
```

Add to the imports: `from .baseline import DEFAULT_BASELINE_PATH, BaselineError, build_baseline, build_invalid_baseline, load_baseline, write_baseline`.

- [ ] **Step 4: Implement the two handlers**

Add above `main`:

```python
def _baseline_destination(root: Path, output: str) -> Path:
    candidate = Path(output)
    return candidate if candidate.is_absolute() else root / candidate


def _baseline_create(root: Path, args, config: NeedsConfig) -> int:
    result = analyze_project(root, config=config)
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
    try:
        write_baseline(destination, payload, force=args.force)
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Could not write baseline: {error}", file=sys.stderr)
        return 3
    if args.format == "json":
        print(json.dumps({"path": str(destination), "valid": payload["valid"]}, indent=2, sort_keys=True))
    else:
        state = "valid" if payload["valid"] else "diagnostic (valid: false)"
        print(f"Wrote {state} baseline to {destination}")
    return 0


def _baseline_summary(payload: dict[str, object]) -> dict[str, object]:
    return {
        "valid": payload["valid"],
        "referenceDate": payload["referenceDate"],
        "configurationFingerprint": payload["configurationFingerprint"],
        "semanticGraphFingerprint": payload.get("semanticGraphFingerprint"),
        "objects": len(payload.get("objects", payload.get("declarations", []))),
        "relations": len(payload.get("relations", [])),
        "findings": len(payload.get("findings", [])),
    }


def _baseline_inspect(args) -> int:
    try:
        payload = load_baseline(Path(args.baseline))
    except BaselineError as error:
        print(str(error), file=sys.stderr)
        return 2
    summary = _baseline_summary(payload)
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    print(f"Baseline {args.baseline}")
    print(f"  valid: {summary['valid']}")
    print(f"  reference date: {summary['referenceDate']}")
    print(f"  objects: {summary['objects']}")
    print(f"  relations: {summary['relations']}")
    print(f"  findings: {summary['findings']}")
    return 0
```

- [ ] **Step 5: Route the command**

In `main`, next to the existing `quality` and `query` dispatch:

```python
    if args.command == "baseline":
        if args.baseline_command == "inspect":
            return _baseline_inspect(args)
        return _baseline_create(root, args, config)
```

Place it **before** the shared `result = analyze_project(root, config=config)` line, so `baseline` never analyzes twice and `inspect` never analyzes at all.

- [ ] **Step 6: Run the CLI tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q`

Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 8: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/cli.py tests/test_cli.py
  git commit -m "feat: add baseline create and inspect commands"
else
  echo "Checkpoint 5 verified; workspace has no Git metadata."
fi
```
