# Task 5: JUnit exporter

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

## Task 5

JUnit exporter

**Files:**
- Create: `src/quarto_needs/exporters/junit_export.py`
- Create: `tests/test_export_junit.py`

**Interfaces:**
- Consumes: `QualityReport` (from `quality.report_from_snapshot`).
- Produces: `junit_export.render(report: QualityReport) -> str`, `junit_export.write(path, report) -> Path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_export_junit.py`:

```python
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import junit_export
from quarto_needs.quality import report_from_snapshot


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nBody.\n"
        ":::\n"
        "\n"
        "::: {.need #REQ-2 type=system-requirement status=approved}\n"
        "\n## Second\nBody.\n"
        ":::\n",
        encoding="utf-8",
    )


def report_for(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None
    return report_from_snapshot(result.snapshot, load_config(root))


def test_junit_has_one_testcase_per_gate_and_failures_name_the_gate(tmp_path: Path) -> None:
    write_project(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n', encoding="utf-8"
    )
    report = report_for(tmp_path)

    root = ET.fromstring(junit_export.render(report))
    assert root.tag == "testsuites"
    suite = root.find("testsuite")
    names = [case.attrib["name"] for case in suite.findall("testcase")]
    assert names == sorted(g["name"] for g in report.to_dict()["gates"])

    failed = {case.attrib["name"] for case in suite.iter("testcase") if case.find("failure") is not None}
    expected = {g["name"] for g in report.to_dict()["gates"] if g["passed"] is False}
    assert failed == expected


def test_junit_properties_carry_warning_counts_and_output_is_deterministic(tmp_path: Path) -> None:
    write_project(tmp_path)
    report = report_for(tmp_path)

    first = junit_export.render(report)
    root = ET.fromstring(first)
    properties = {p.attrib["name"]: p.attrib["value"] for p in root.iter("property")}
    assert "warnings" in properties

    assert junit_export.render(report) == first
```

- [ ] **Step 2: Run them and verify they fail** — `ModuleNotFoundError`.
- [ ] **Step 3: Implement `junit_export.py`**

`xml.etree.ElementTree` with fixed attribute order guaranteed by constructing
elements in a fixed sequence and serializing with `ET.tostring(..., encoding="unicode")`
plus a trailing newline; one `testsuites`/`testsuite` pair; `tests`/`failures`
counts derived; one `testcase` per gate (classname `quarto-needs.gates`), a
`<failure message="threshold X, actual Y">` child for failed gates; `properties`
carrying `errors`, `warnings`, and `profile`; gates sorted by name. XML entity
handling comes from the stdlib serializer — never build markup by string
concatenation.

- [ ] **Step 4: Run the JUnit tests; full suite; remove Task 2's xfail for junit; conditional checkpoint.**
