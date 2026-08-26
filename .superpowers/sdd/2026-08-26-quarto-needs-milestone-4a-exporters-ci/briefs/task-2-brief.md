# Task 2: `export --format` plumbing and policy-failure artifact preservation

> Extracted from `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4a-exporters-ci.md`. This brief is your complete requirements.
> Use every value in it verbatim.

## Global Constraints (bind every task)

- Do not add a runtime dependency. `pyyaml` enters the `test` optional dependency group only.
- One analysis per command invocation. `export` in every format calls `analyze_project` exactly once; loading a baseline for the Markdown summary never analyzes.
- `export --format json` (and `export` with no `--format`) must stay byte-identical to the current v1 projection for an unchanged project; a golden hash test locks this.
- Exit codes are stable: `0` gates passed; `1` validation or policy failure; `2` invalid usage or configuration; `3` operational I/O or serialization failure. Export artifacts are still written when policy returns exit 1; operational failures return 3 and name the artifact that could not be produced.
- Exporter output is deterministic for a fixed project, configuration, and reference date: sorted rows/entries, no wall-clock timestamps; any timestamp comes from `SOURCE_DATE_EPOCH` with a `1970-01-01T00:00:00Z` fallback.
- All generated files are written atomically through `export._write_atomic_text`; CSV's three files are written to a directory created on demand.
- Preserve every existing signature and documented behavior, including the v1 JSON schema and `extensions.quartoNeeds` projection.
- The workspace has no `.git` metadata. Do not initialize Git. Every task ends with a conditional checkpoint that records a commit only when the executor is inside a Git worktree.
- Do not stop or restart the preview server listening on `127.0.0.1:8777`.
- Vendored assets (the SARIF 2.1.0 JSON Schema) record upstream URL, version, license notice, and SHA-256 checksum in a `VENDORED.md` next to the asset; a test verifies the checksum so an offline build cannot drift.

## Task 2

`export --format` plumbing and policy-failure artifact preservation

**Files:**
- Modify: `src/quarto_needs/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `export --format <json|csv|sarif|junit|markdown>` (default `json`), `export --baseline <path>` (Markdown only; rejected for other formats with exit 2), and the guarantee that artifacts are written before the profile exit code is returned.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
def test_export_default_format_is_byte_identical_to_the_v1_projection(tmp_path: Path) -> None:
    """No --format must mean today's json output, byte for byte."""
    import hashlib

    write_valid_project(tmp_path)
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    assert cli.main(["--root", str(tmp_path), "export", "--output", str(first)]) == 0
    assert cli.main(["--root", str(tmp_path), "export", "--format", "json", "--output", str(second)]) == 0

    assert first.read_bytes() == second.read_bytes()
    assert len(hashlib.sha256(first.read_bytes()).hexdigest()) == 64


def test_export_runs_exactly_one_analysis_per_format(
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

    for name in ("json", "csv", "sarif", "junit", "markdown"):
        destination = tmp_path / "out" / name
        assert cli.main([
            "--root", str(tmp_path), "export", "--format", name,
            "--output", str(destination / "artifact"),
        ]) in (0, 1), name
    assert calls == 5


def test_export_rejects_baseline_for_non_markdown_formats(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    assert cli.main([
        "--root", str(tmp_path), "export", "--format", "sarif",
        "--output", str(tmp_path / "out.sarif"), "--baseline", str(tmp_path / "none.json"),
    ]) == 2
    assert "markdown" in capsys.readouterr().err


def test_export_preserves_artifacts_on_policy_failure(tmp_path: Path) -> None:
    """A failing strict gate still writes the artifact, then exits 1."""
    # An approved requirement with no verification makes the verification gate
    # fail with a non-zero denominator (an empty scope passes vacuously).
    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
        "\n## Authenticate\nBody.\n"
        ":::\n",
        encoding="utf-8",
    )
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n', encoding="utf-8"
    )
    destination = tmp_path / "artifacts" / "report.md"

    assert cli.main(["--root", str(tmp_path), "export", "--format", "markdown", "--output", str(destination)]) == 1
    assert destination.is_file()
```

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k export`

Expected: FAIL — `--format`/`--baseline` do not exist (argparse exit 2 via SystemExit) and the policy-failure path is absent.

- [ ] **Step 3: Implement the plumbing**

Extend the `export` parser:

```python
    export.add_argument("--format", choices=("json", "csv", "sarif", "junit", "markdown"), default="json")
    export.add_argument("--baseline", help="Baseline for the Markdown change summary (markdown format only)")
```

Replace the `export` dispatch block with a `_export(root, args, config)` handler that: analyzes once; dispatches per format to a writer module (Tasks 3–6 land the writers; until then a temporary `raise NotImplementedError` for non-json formats is acceptable ONLY within this task's branch — final acceptance requires all five); writes through `_write_atomic_text`; returns `profile_exit_code(config.profile, False, failed_gate_count)` where the gate count comes from `report_from_snapshot(snapshot, config)` reusing the snapshot (no second analysis). `--baseline` with a non-markdown format prints a usage error and returns 2 before analysis.

- [ ] **Step 4: Run the CLI tests**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k export`

Expected: the byte-identity, one-analysis, and baseline-rejection tests PASS. The per-format loop and policy-failure tests may remain blocked until Tasks 3–6 land — if so, mark them `xfail(strict=True)` with a `# TODO(milestone-4a-writers)` note and record that in the report; Tasks 3–6 remove the marks.

- [ ] **Step 5: Run the full suite and record the checkpoint conditionally**
