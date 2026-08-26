# Task 7: CI workflow split and milestone acceptance

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

## Task 7

CI workflow split and milestone acceptance

**Files:**
- Modify: `.github/workflows/ci.yml`
- Create: `tests/test_ci_workflow.py`
- Modify: `README.md`, `CONTRIBUTING.md`

**Interfaces:**
- Produces: the three-job workflow (`core`, `quarto`, `quality`) with `if: always()` artifact uploads, a step summary, and a least-privilege SARIF upload; structural tests pinning the contract.

- [ ] **Step 1: Write the failing structural tests**

Create `tests/test_ci_workflow.py`:

```python
from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def parsed() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_has_the_three_specified_jobs() -> None:
    jobs = parsed()["jobs"]
    assert {"core", "quarto", "quality"} <= set(jobs)


def test_core_runs_the_python_matrix() -> None:
    matrix = parsed()["jobs"]["core"]["strategy"]["matrix"]["python-version"]
    assert ["3.10", "3.11", "3.12", "3.13", "3.14"] == matrix


def test_artifacts_upload_always_and_sarif_is_least_privilege() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if: always()" in text
    assert "pull_request_target" not in text
    quality = parsed()["jobs"]["quality"]["steps"]
    upload_steps = [step for step in quality if "upload-artifact" in str(step.get("uses", ""))]
    assert upload_steps, "quality must upload artifacts"
    assert any("github/codeql-action/upload-sarif" in str(step.get("uses", "")) for step in quality)


def test_quality_generates_every_export_format() -> None:
    run_steps = [str(step.get("run", "")) for step in parsed()["jobs"]["quality"]["steps"]]
    joined = "\n".join(run_steps)
    for name in ("json", "csv", "sarif", "junit", "markdown"):
        assert f"--format {name}" in joined, name
```

- [ ] **Step 2: Run them and verify they fail** — the current single-job workflow has no `core`/`quarto`/`quality`.

- [ ] **Step 3: Add `pyyaml` to the test extra and rewrite the workflow**

`pyproject.toml`: add `"pyyaml"` to the `test` optional list; run `make setup`.
Rewrite `.github/workflows/ci.yml`:

- `core`: matrix `["3.10", "3.11", "3.12", "3.13", "3.14"]` on `ubuntu-latest`, `pip install -e ".[test]"`, `pytest -q`, plus `quarto-needs scan`/`check` on the example book with `PYTHONPATH=src`.
- `quarto`: `needs: core`, pinned Quarto (`quarto-dev/quarto-actions/setup@v0` with a pinned version), `make sync-example`, `make render-example-all`, `make check-example`.
- `quality`: `needs: core`, strict profile run over `examples/book` generating all five export formats into `artifacts/`, `quarto-needs quality --format json --output artifacts/quality.json`, artifact upload with `if: always()`, `$GITHUB_STEP_SUMMARY` append from the markdown export, and a separate `github/codeql-action/upload-sarif@v3` step with `permissions: contents: read` / `security-events: write` scoped to that step's job.
- No `pull_request_target` anywhere; `on: [push, pull_request]`.

- [ ] **Step 4: Run the structural tests** — Expected: PASS.

- [ ] **Step 5: Document in README/CONTRIBUTING**

README: an `## Export formats` subsection under the export command listing the
five formats, their outputs (three CSV files in a directory; single SARIF,
JUnit, Markdown documents), determinism guarantee, and the exit-1-with-artifacts
behavior. CONTRIBUTING: CI artifact policy — artifacts are uploaded `if:
always()`; a failed gate run still produces them; operational failures exit 3
and name the missing artifact.

- [ ] **Step 6: Acceptance run**

```bash
make setup && make test
PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/book export --format csv --output /tmp/m4a/csv
PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/book export --format sarif --output /tmp/m4a/out.sarif
PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/book export --format junit --output /tmp/m4a/out.xml
PYTHONPATH=src .venv/bin/python -m quarto_needs.cli --root examples/book export --format markdown --output /tmp/m4a/out.md --baseline examples/book/baselines/quarto-needs.json
make diff-example
.venv/bin/python -m pytest -q
```

Expected: every export exits 0; `diff-example` still prints `No changes.`;
full suite passes with zero warnings; repeated markdown/sarif/junit runs with
`SOURCE_DATE_EPOCH` pinned are byte-identical.

- [ ] **Step 7: Record the Milestone 4A checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add -A
  git commit -m "feat: complete milestone four a exporters and ci"
else
  echo "Milestone 4A verified; workspace has no Git metadata."
fi
```

Expected: every Milestone 4A acceptance gate is complete. Milestone 4B starts only after this checkpoint, with its own implementation plan.
