# Task 4: SARIF exporter

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

## Task 4

SARIF exporter

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
from jsonschema import Draft7Validator

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
    Draft7Validator.check_schema(schema)

    (tmp_path / "ok.qmd").write_text(
        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
    )
    result = analyze_project(tmp_path, config=load_config(tmp_path))
    assert result.snapshot is not None

    payload = json.loads(sarif_export.render(result.snapshot))
    Draft7Validator(schema).validate(payload)


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
