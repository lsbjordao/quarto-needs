# Task 11: Showcase, documentation, and milestone acceptance

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

## Task 11

Showcase, documentation, and milestone acceptance

**Files:**
- Create: `examples/book/baselines/quarto-needs.json`
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `CONTRIBUTING.md`
- Modify: `Makefile`
- Modify: `tests/test_example_project.py`

**Interfaces:**
- Consumes: every command from Tasks 5, 8, and 10.
- Produces: the Milestone 3 acceptance command set and a checked-in Aegis baseline.

- [ ] **Step 1: Write the failing showcase tests**

Add to `tests/test_example_project.py`:

```python
def test_aegis_baseline_round_trips_to_an_empty_diff():
    """The gate: a checked-in baseline must still describe the published book."""
    import json as _json
    from quarto_needs import cli

    root = ROOT / "examples/book"
    baseline_path = root / "baselines" / "quarto-needs.json"
    assert baseline_path.is_file(), "run `make baseline-example` to create it"

    payload = _json.loads(baseline_path.read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["schemaVersion"] == "1"

    assert cli.main(["--root", str(root), "diff", str(baseline_path)]) == 0


def test_aegis_baseline_validates_against_the_baseline_schema():
    import json as _json
    from jsonschema import Draft202012Validator

    schema = _json.loads((ROOT / "schemas" / "baseline-v1.schema.json").read_text(encoding="utf-8"))
    payload = _json.loads((ROOT / "examples/book/baselines/quarto-needs.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_aegis_impact_explains_a_removed_verification(tmp_path: Path):
    """Removing an edge in a copy of the book must reach the requirement."""
    import json as _json
    import shutil as _shutil
    from quarto_needs import cli

    project = tmp_path / "book"
    _shutil.copytree(ROOT / "examples/book", project, ignore=_shutil.ignore_patterns("_book", ".quarto"))
    baseline_path = project / "baselines" / "quarto-needs.json"

    system = project / "requirements" / "system.qmd"
    system.write_text(
        system.read_text(encoding="utf-8").replace('verified-by="IAM-TC-001"', "", 1),
        encoding="utf-8",
    )

    # The checked-in baseline predates the run day, and impact (per spec)
    # rejects a reference-date mismatch; the documented escape hatch keeps the
    # showcase runnable on any date.
    assert cli.main([
        "--root", str(project), "impact", str(baseline_path),
        "--recompute-with", "current", "--format", "json",
    ]) == 0
```

Note: this last test reads the JSON only to prove the command exits 0 on a real project; asserting exact reachability is already covered by `tests/test_impact.py`.

- [ ] **Step 2: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_example_project.py -q -k baseline`

Expected: FAIL — `examples/book/baselines/quarto-needs.json` does not exist yet.

- [ ] **Step 3: Add the Make targets**

In `Makefile`, extend `.PHONY` with `baseline-example diff-example impact-example` and append:

```make
baseline-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book baseline create --force

diff-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book diff examples/book/baselines/quarto-needs.json

impact-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json --recompute-with current
```

- [ ] **Step 4: Create the checked-in baseline**

Run:

```bash
make sync-example
make baseline-example
make diff-example
```

Expected: `baseline create` exits 0, and `diff-example` prints `No changes.` and exits 0. If the diff is non-empty immediately after creation, a fingerprint is reading derived data — stop and fix Task 3 rather than regenerating.

- [ ] **Step 5: Run the showcase tests**

Run: `.venv/bin/python -m pytest tests/test_example_project.py -q`

Expected: PASS.

- [ ] **Step 6: Document the commands in the README**

Extend the `## Commands` block with the three new entries and add a `### Baseline, diff, and impact` section after the configuration reference. It must state:

- `baseline create` writes `baselines/quarto-needs.json`, refuses to overwrite without `--force`, and refuses a structurally invalid project unless `--allow-invalid` is given;
- `--allow-invalid` produces a diagnostic artifact marked `valid: false` that only `baseline inspect` accepts — `diff` and `impact` reject it, because duplicate IDs make comparison ambiguous;
- `diff` classifies added/removed objects, modifications by field, added/removed relations, relocation, and findings/metrics/gate regressions; a changed ID is reported as a removal plus an addition because rename detection is heuristic and deliberately excluded;
- **relocation is keyed on the declaring file** — a line-only shift produces no record;
- an authored alias flip (`verified-by` to `verifies`) that preserves endpoint roles is a representation change, never a relation addition or removal;
- the two guards: a changed configuration fingerprint or reference date emits `configuration-changed` / `reference-date-changed` and suppresses derived deltas; `--recompute-with current` re-resolves the baseline's authored relations through the current catalog so semantic comparison is valid again, while derived deltas stay suppressed until both sides are produced under the same configuration and reference date;
- `impact` traverses the union of both graphs so removed nodes stay explainable, follows each relation's catalog `impactDirection`, and gives every result an explicit path, distance, classification, and priority — there is no risk score;
- determinism means byte-identical output for a fixed configuration **and** a fixed reference date; `SOURCE_DATE_EPOCH` fixes the latter.

- [ ] **Step 7: Update the pipeline diagram**

In `ARCHITECTURE.md`, extend the canonical pipeline block:

```text
AnalysisSnapshot -> fingerprints -> baselines/quarto-needs.json
                                          |
        current AnalysisSnapshot ---------+--> diff  -> DiffReport   -> text|json
                                          +--> impact -> ImpactReport -> text|json
```

Add a paragraph stating that `diff` and `impact` are pure functions over two snapshots, that the CLI is the only layer touching the filesystem, and that the configuration fingerprint and reference date are the two guards deciding which categories of delta are meaningful.

- [ ] **Step 8: Document the fixture and baseline policy**

In `CONTRIBUTING.md`, extend the fixture policy: `examples/book/baselines/quarto-needs.json` is a checked-in baseline that must always diff clean against the published book. Regenerate it with `make baseline-example` only when a deliberate change to the showcase is approved, and inspect the resulting diff before committing the new bytes. Never regenerate it to silence a failing test.

- [ ] **Step 9: Acceptance run**

Run each command and record its output:

```bash
make setup && make test
make sync-example && make sync-example   # SHA-256 pairs identical
make check-example
.venv/bin/python -m quarto_needs.cli --root examples/book quality --format json
.venv/bin/python -m quarto_needs.cli --root examples/book query approved-high-unverified
make baseline-example && make diff-example && make impact-example
make render-example-all
curl --fail --silent --show-error http://127.0.0.1:8777/ >/dev/null
.venv/bin/python -m pytest -q
```

Expected:

- the full suite passes with **zero** warnings;
- two consecutive `make sync-example` runs leave `examples/book/.quarto-needs/needs.json` and `generated-index.lua` byte-identical;
- `diff-example` prints `No changes.` and exits 0;
- `impact-example` prints `No changes to propagate.` and exits 0;
- `make render-example-all` exits 0 for HTML, DOCX, and PDF, and the rendered book contains no `need-ref-missing`, no unexpanded `{{<`, and no raw Mermaid source;
- the preview server answers and is neither stopped nor restarted.

Each render of the book rebuilds `_book`, so re-render HTML afterwards to leave the usual state on disk:

```bash
quarto render examples/book --to html
```

- [ ] **Step 10: Record the Milestone 3 acceptance checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add README.md ARCHITECTURE.md CONTRIBUTING.md Makefile \
    examples/book/baselines/quarto-needs.json tests/test_example_project.py
  git commit -m "docs: complete milestone three acceptance"
else
  echo "Milestone 3 verified; workspace has no Git metadata."
fi
```

Expected: every Milestone 3 acceptance gate is complete. Milestone 4A starts only after this checkpoint, with its own implementation plan.
