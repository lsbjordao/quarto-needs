# Quarto-Needs Milestone 4A Exporters and CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the CSV, SARIF, JUnit, and Markdown exporters behind `export --format`, close the exit-code-3 gap carried from the Milestone 3 whole-branch review, and split CI into the spec's `core`/`quarto`/`quality` jobs with preserved artifacts and a step summary.

**Architecture:** Every exporter is a pure function from the existing single-pass analysis products (`AnalysisSnapshot`, `QualityReport`, optionally a loaded baseline plus `DiffReport`/`ImpactReport`) to a deterministic string, written atomically through `export._write_atomic_text`. The CLI remains the only filesystem layer and still analyzes exactly once per invocation. The Markdown summary may load a baseline and run the pure `diff`/`impact` functions over the already-held snapshot; loading a baseline never analyzes.

**Tech Stack:** Python 3.10+, standard-library `csv`/`xml.etree`/`hashlib`/`json`, pytest, `jsonschema` (already a test dependency), `pyyaml` added to the `test` extra only (workflow structural tests); no new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-08-25-quarto-needs-evolution-design.md` — sections "Exporters", "CI design", "CLI and failure semantics", and the gate under "### Milestone 4".

## Global Constraints

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

## File Map

| Area | Files | Responsibility after Milestone 4A |
|---|---|---|
| Exit-code hardening | `src/quarto_needs/cli.py`, `README.md` | `scan`/`export` write failures become exit 3; exit-code table documents 3; impact's rejection semantics documented. |
| Exporter plumbing | `src/quarto_needs/cli.py` | `export --format <json\|csv\|sarif\|junit\|markdown>`, optional `--baseline`, artifacts preserved on policy failure. |
| CSV | `src/quarto_needs/exporters/__init__.py`, `src/quarto_needs/exporters/csv_export.py`, `tests/test_export_csv.py` | `objects.csv`, `relations.csv`, `findings.csv` with formula-injection protection. |
| SARIF | `src/quarto_needs/exporters/sarif_export.py`, `schemas/vendor/sarif-2.1.0/sarif-schema.json`, `schemas/vendor/sarif-2.1.0/VENDORED.md`, `tests/test_export_sarif.py` | Findings as SARIF 2.1.0 (GitHub-supported subset), schema-validated. |
| JUnit | `src/quarto_needs/exporters/junit_export.py`, `tests/test_export_junit.py` | One test case per evaluated quality gate; warnings per policy. |
| Markdown | `src/quarto_needs/exporters/markdown_export.py`, `tests/test_export_markdown.py` | CI summary: changes, coverage deltas, failed gates, high/critical impact. |
| Export integration | `tests/test_cli.py` | Format dispatch, one-analysis, exit codes, artifact preservation, JSON byte-identity. |
| CI | `.github/workflows/ci.yml`, `tests/test_ci_workflow.py` | `core` matrix (3.10–3.14), `quarto` render smoke, `quality` artifacts with `if: always()` uploads, step summary, least-privilege SARIF step. |
| Docs | `README.md`, `CONTRIBUTING.md` | Export format reference, exit-code table, CI artifact policy. |
| Tests | `tests/test_export_csv.py`, `tests/test_export_sarif.py`, `tests/test_export_junit.py`, `tests/test_export_markdown.py`, `tests/test_cli.py`, `tests/test_ci_workflow.py` | Unit, golden byte-identity, schema validation, CLI integration, workflow structure. |

---

### Task 1: Close the exit-code-3 gap (carried from Milestone 3)

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

---

### Task 2: `export --format` plumbing and policy-failure artifact preservation

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

---

### Task 3: CSV exporter

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

---

### Task 4: SARIF exporter

**Files:**
- Create: `src/quarto_needs/exporters/sarif_export.py`
- Create: `schemas/vendor/sarif-2.1.0/sarif-schema.json`
- Create: `schemas/vendor/sarif-2.1.0/VENDORED.md`
- Create: `tests/test_export_sarif.py`

**Interfaces:**
- Consumes: `AnalysisSnapshot`, `rules.RULES` registry, the vendored schema.
- Produces: `sarif_export.render(snapshot) -> str`, `sarif_export.write(path, snapshot) -> Path`.

- [ ] **Step 1: Vendor the SARIF 2.1.0 schema**

Download `https://json.schemastore.org/sarif-2.1.0.json` (or the equivalent official `sarif-2.1.0` JSON Schema from the OASIS repository) into `schemas/vendor/sarif-2.1.0/sarif-schema.json`; record in `VENDORED.md` the upstream URL, version, license (MIT), retrieval date, and the SHA-256 of the vendored file. If the workstation is offline, copy the schema from the locally installed `jsonschema` bundles if present, else STOP and report.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_export_sarif.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import sarif_export

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "vendor" / "sarif-2.1.0" / "sarif-schema.json"


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nBody.\n"
        ":::\n"
        "\n"
        "::: {.need #DUP type=need status=draft}\n\n## A\nA.\n:::\n"
        "\n::: {.need #DUP type=need status=draft}\n\n## B\nB.\n:::\n",
        encoding="utf-8",
    )


def snapshot_with_findings(root: Path):
    result = analyze_project(root, config=load_config(root))
    return result.declarations and result.findings and result or None


def test_sarif_validates_against_the_vendored_schema(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    (tmp_path / "ok.qmd").write_text(
        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
    )
    result = analyze_project(tmp_path, config=load_config(tmp_path))
    assert result.snapshot is not None

    payload = json.loads(sarif_export.render(result.snapshot))
    Draft202012Validator(schema).validate(payload)


def test_sarif_maps_findings_with_locations_and_fingerprints(tmp_path: Path) -> None:
    write_project(tmp_path)
    result = analyze_project(tmp_path, config=load_config(tmp_path))
    assert any(f.code == "REQ004" for f in result.findings)

    payload = json.loads(sarif_export.render_from_findings(result.findings))
    result_entry = next(r for r in payload["runs"][0]["results"] if r["ruleId"] == "REQ004")

    assert result_entry["fingerprints"]["primaryLocationLineHash"]
    assert result_entry["locations"][0]["physicalLocation"]["region"]["startLine"] > 0
    assert payload["runs"][0]["tool"]["driver"]["rules"], "rule metadata must be present"


def test_sarif_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    write_project(tmp_path)
    result = analyze_project(tmp_path, config=load_config(tmp_path))
    assert sarif_export.render_from_findings(result.findings) == sarif_export.render_from_findings(result.findings)
```

> Interface note: SARIF consumes **findings**, not the snapshot alone — the
> load-bearing producer is `render_from_findings(findings: Sequence[Finding]) -> str`
> (plus a `render(snapshot)` convenience that forwards `snapshot.findings`).
> Findings from a structurally invalid project (snapshot is None) must still
> export; that is why the producer is findings-based.

- [ ] **Step 3: Run them and verify they fail** — `ModuleNotFoundError`.
- [ ] **Step 4: Implement `sarif_export.py`**

`$schema` pinned to the vendored URI, `version: "2.1.0"`, one run; `tool.driver` name `quarto-needs` with the package version and one `reportingDescriptor` per distinct finding code (from `rules.RULES` for help/text, falling back to the code); one `result` per finding with `level` mapped error→error / warning→warning / info→note, `message.text`, `locations[0].physicalLocation` (`artifactLocation.uri` as the project-relative file, `region.startLine`), and `fingerprints.primaryLocationLineHash` from the finding's existing stable identity hash; results sorted by (code, object_id, message) for determinism; `automationDetails.id` fixed, no timestamps.

- [ ] **Step 5: Run the SARIF tests; full suite; remove Task 2's xfail for sarif; conditional checkpoint.**

---

### Task 5: JUnit exporter

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

---

### Task 6: Markdown CI summary exporter

**Files:**
- Create: `src/quarto_needs/exporters/markdown_export.py`
- Create: `tests/test_export_markdown.py`

**Interfaces:**
- Consumes: `AnalysisSnapshot`, `NeedsConfig`, `QualityReport`, optional baseline payload via `diff.compare` and `impact.analyze`.
- Produces: `markdown_export.render(snapshot, config, *, baseline: Mapping[str, object] | None = None) -> str`, `markdown_export.write(path, snapshot, config, *, baseline=None) -> Path`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_export_markdown.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from quarto_needs import baseline as baseline_module
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import markdown_export


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n## Login\nSigns in.\n"
        ":::\n",
        encoding="utf-8",
    )


def built(root: Path):
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return result.snapshot, config


def test_summary_without_a_baseline_says_so_and_lists_failed_gates(tmp_path: Path) -> None:
    write_project(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n', encoding="utf-8"
    )
    snapshot, config = built(tmp_path)

    text = markdown_export.render(snapshot, config)

    assert "## Changes" in text and "No baseline was supplied" in text
    assert "## Failed gates" in text and "min-verification-trace" in text
    assert "## High and critical impact" in text


def test_summary_with_a_baseline_reports_changes_and_impact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    write_project(tmp_path)
    snapshot, config = built(tmp_path)
    payload = baseline_module.build_baseline(snapshot, config)

    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nThe service shall authenticate every administrator.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n## Login\nSigns in.\n"
        ":::\n",
        encoding="utf-8",
    )
    snapshot, config = built(tmp_path)

    text = markdown_export.render(snapshot, config, baseline=payload)

    assert "REQ-1" in text and "body" in text
    assert "TC-1" in text  # impacted via verified-by
    assert "## Coverage deltas" in text


def test_summary_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    write_project(tmp_path)
    snapshot, config = built(tmp_path)
    assert markdown_export.render(snapshot, config) == markdown_export.render(snapshot, config)
```

- [ ] **Step 2: Run them and verify they fail** — `ModuleNotFoundError`.
- [ ] **Step 3: Implement `markdown_export.py`**

Sections in fixed order: `# Quarto-Needs CI summary`; `## Changes` (from
`diff.compare(baseline, snapshot, config)` — added/removed objects, modified
by field, relocated; without a baseline, the sentence "No baseline was
supplied; change classification is unavailable."); `## Coverage deltas`
(metric deltas table scope/strength before→after, or "No coverage deltas.");
`## Failed gates` (name, threshold, actual — or "All gates passed.");
`## High and critical impact` (impacted entries whose `priority` is `high`
or `critical`, with path and distance; without a baseline the same
no-baseline sentence). When a baseline is supplied, run `diff.compare(...,
recompute=True)` and `impact.analyze(..., recompute=True)` so one policy
governs and date mismatches cannot refuse the summary. End with a
`## Findings` counts line (errors/warnings).

- [ ] **Step 4: Run the Markdown tests; full suite; remove Task 2's xfail for markdown; conditional checkpoint.**

---

### Task 7: CI workflow split and milestone acceptance

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
