# Task 3: CSV exporter

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

## Task 3

CSV exporter

**Files:**
- Create: `src/quarto_needs/exporters/__init__.py`
- Create: `src/quarto_needs/exporters/csv_export.py`
- Create: `tests/test_export_csv.py`

**Interfaces:**
- Consumes: `AnalysisSnapshot`, `export._write_atomic_text`.
- Produces: `csv_export.render_objects(snapshot) -> str`, `render_relations(snapshot) -> str`, `render_findings(snapshot) -> str`, and `csv_export.write_all(directory: Path, snapshot) -> tuple[Path, ...]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_export_csv.py`:

```python
from __future__ import annotations

import csv
from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import csv_export


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "rationale: Protect data.\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n## Login\n=SUM(A1:A9) starts a formula when pasted into a spreadsheet\n"
        ":::\n",
        encoding="utf-8",
    )


def build(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None
    return result.snapshot


def test_csv_writes_three_files_with_expected_headers(tmp_path: Path) -> None:
    write_project(tmp_path)
    written = csv_export.write_all(tmp_path / "csv", build(tmp_path))

    assert [path.name for path in written] == ["findings.csv", "objects.csv", "relations.csv"]
    rows = list(csv.DictReader((tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8").splitlines()))
    assert rows[0]["id"] == "REQ-1"
    assert rows[0]["type"] == "system-requirement"


def test_csv_neutralizes_formula_injection(tmp_path: Path) -> None:
    write_project(tmp_path)
    csv_export.write_all(tmp_path / "csv", build(tmp_path))

    text = (tmp_path / "csv" / "objects.csv").read_text(encoding="utf-8")
    cells = {value: None for row in csv.DictReader(text.splitlines()) for value in row.values()}
    dangerous = [value for value in cells if value.startswith(("=", "+", "-", "@", "\t", "\r"))]
    assert not dangerous
    assert any(value.startswith("'=") for value in cells), "the neutralized cell must carry the apostrophe prefix"


def test_csv_is_deterministic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    write_project(tmp_path)
    first = csv_export.render_objects(build(tmp_path))
    second = csv_export.render_objects(build(tmp_path))
    assert first == second
```

- [ ] **Step 2: Run them and verify they fail** — `ModuleNotFoundError: No module named 'quarto_needs.exporters'`.

- [ ] **Step 3: Implement `csv_export.py`**

Deterministic ordering (case-insensitive by id, then by field), fixed column sets (`objects`: id, type, title, status, priority, tags, body, rationale; `relations`: source, authored_name, target, semantic_family; `findings`: code, severity, object_id, message, file, line), `\r\n` line endings per RFC 4180 via `csv.writer` over `io.StringIO`, and a `_neutralize(value)` helper that prefixes `'` when a stringified cell starts with `=`, `+`, `-`, `@`, tab, or carriage return. `write_all` creates the directory and writes atomically, returning the three paths sorted.

- [ ] **Step 4: Run the CSV tests** — Expected: PASS.
- [ ] **Step 5: Full suite; remove Task 2's xfail for csv if present; conditional checkpoint.**
