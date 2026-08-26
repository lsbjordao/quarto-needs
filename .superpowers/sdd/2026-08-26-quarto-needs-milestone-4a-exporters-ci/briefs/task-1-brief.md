# Task 1: Close the exit-code-3 gap (carried from Milestone 3)

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

## Task 1

Close the exit-code-3 gap (carried from Milestone 3)

The whole-branch review verified that `scan` on a read-only root and `export --output`
into an unwritable directory raise raw `PermissionError` tracebacks and exit 1,
while the spec reserves exit 3 for operational I/O failure. The README exit-code
table also lacks code 3, and impact's config/date rejection is undocumented.

**Files:**
- Modify: `src/quarto_needs/cli.py`
- Modify: `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `scan`/`export` (and, once later tasks land, every exporter path) mapping `OSError` during artifact writes to exit 3 with a one-line stderr message naming the artifact.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
def test_scan_on_an_unwritable_root_is_operational_failure(tmp_path: Path, capsys) -> None:
    """Read-only scan targets are exit 3, not a traceback."""
    import os

    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
    )
    target = tmp_path / "locked"
    target.mkdir()
    (target / "needs.qmd").write_text(
        "::: {.need #REQ-2 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
    )
    os.chmod(target, 0o500)

    try:
        assert cli.main(["--root", str(target), "scan"]) == 3
        assert "Could not" in capsys.readouterr().err
    finally:
        os.chmod(target, 0o700)


def test_export_to_an_unwritable_directory_is_operational_failure(tmp_path: Path, capsys) -> None:
    """A failed artifact write exits 3 and names the artifact."""
    import os

    write_valid_project(tmp_path)
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)

    try:
        destination = locked / "sub" / "needs.json"
        assert cli.main(["--root", str(tmp_path), "export", "--output", str(destination)]) == 3
        assert str(destination) in capsys.readouterr().err
    finally:
        os.chmod(locked, 0o700)
```

> Note: `scan` reads `.qmd` files; making the ROOT unwritable also blocks reading
> on some platforms. The test above relies on directory-read remaining possible
> with mode 0o500 while creation/writes fail. If on this platform reading also
> fails, keep the export test (which is the load-bearing one) and replace the
> scan probe with a monkeypatched `Path.write_text`/`Path.mkdir` raising
> `PermissionError` — record whichever variant you shipped in the report.

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q -k operational_failure`

Expected: FAIL — the commands currently raise `PermissionError` (test error) or exit 1.

- [ ] **Step 3: Implement the guards**

In `cli.py`, wrap the `scan` path collection and the `export` write in
`try/except OSError` handlers that print
`Could not write <path>: <error>` (or `Could not scan <root>: <error>` for scan)
to stderr and return 3. Do not catch `ConfigurationError` or validation paths.

- [ ] **Step 4: Document exit code 3 and impact's guards in the README**

In the exit-code list after code 2, add:

```markdown
- `3`: operational failure — an artifact could not be read or written. The
  message names the artifact; anything already written is left in place.
```

In the `### Baseline, diff, and impact` section's impact paragraph, append one
sentence: "`impact` refuses a baseline whose configuration fingerprint or
reference date differs from the current run unless `--recompute-with current`
is supplied, so one policy always governs a traversal; under that flag, derived
deltas remain suppressed, exactly as in `diff`."

- [ ] **Step 5: Run the CLI tests and the full suite**

Run: `.venv/bin/python -m pytest tests/test_cli.py -q` then `.venv/bin/python -m pytest -q`

Expected: PASS with zero warnings (241 + new tests).

- [ ] **Step 6: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/cli.py README.md tests/test_cli.py
  git commit -m "fix: map scan and export write failures to exit code 3"
else
  echo "Checkpoint 1 verified; workspace has no Git metadata."
fi
```
