# Task 4: Baseline artifact — schema, serialization, and load

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

## Task 4

Baseline artifact — schema, serialization, and load

**Files:**
- Create: `src/quarto_needs/baseline.py`
- Create: `schemas/baseline-v1.schema.json`
- Create: `tests/test_baseline.py`

**Interfaces:**
- Consumes: every fingerprint helper and snapshot field from Task 3; `quality.report_from_snapshot` from Milestone 2; `export._write_atomic_text`.
- Produces:
  - `baseline.BaselineError(Exception)`
  - `baseline.build_baseline(snapshot: AnalysisSnapshot, config: NeedsConfig, *, queries: Mapping[str, Sequence[str]] | None = None) -> dict[str, object]`
  - `baseline.build_invalid_baseline(result: AnalysisResult, config: NeedsConfig) -> dict[str, object]`
  - `baseline.render_baseline(payload: dict[str, object]) -> str`
  - `baseline.write_baseline(path: Path, payload: dict[str, object], *, force: bool = False) -> None`
  - `baseline.load_baseline(path: Path) -> dict[str, object]`

- [ ] **Step 1: Write the baseline JSON Schema**

Create `schemas/baseline-v1.schema.json`. It is a separate, separately versioned schema — it never references the v1 graph schema:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schema/baseline-v1.schema.json",
  "title": "Quarto-Needs baseline v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "generator", "relationCatalogVersion", "ruleSetVersion", "referenceDate", "configurationFingerprint", "valid"],
  "properties": {
    "schemaVersion": {"const": "1"},
    "generator": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "version"],
      "properties": {"name": {"type": "string"}, "version": {"type": "string"}}
    },
    "relationCatalogVersion": {"type": "string"},
    "ruleSetVersion": {"type": "string"},
    "referenceDate": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"},
    "configurationFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "semanticGraphFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "representationFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "valid": {"type": "boolean"},
    "objects": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "type", "title", "status", "body", "rationale", "attributes", "location", "contentFingerprint"],
        "properties": {
          "id": {"type": "string"},
          "type": {"type": "string"},
          "title": {"type": "string"},
          "status": {"type": "string"},
          "body": {"type": "string"},
          "rationale": {"type": "string"},
          "attributes": {"type": "object"},
          "location": {
            "type": ["object", "null"],
            "additionalProperties": false,
            "required": ["file", "line"],
            "properties": {
              "file": {"type": "string"},
              "line": {"type": "integer"},
              "anchor": {"type": ["string", "null"]}
            }
          },
          "contentFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        }
      }
    },
    "relations": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["source", "authoredName", "target", "semanticFamily", "sourceRole", "targetRole", "attributes", "authoredFingerprint", "semanticFingerprint"],
        "properties": {
          "source": {"type": "string"},
          "authoredName": {"type": "string"},
          "target": {"type": "string"},
          "semanticFamily": {"type": "string"},
          "sourceRole": {"type": "string"},
          "targetRole": {"type": "string"},
          "impactDirection": {"type": "string"},
          "attributes": {"type": "object"},
          "authoredFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
          "semanticFingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
        }
      }
    },
    "findings": {"type": "array", "items": {"type": "object"}},
    "declarations": {"type": "array", "items": {"type": "object"}},
    "report": {"type": "object"}
  }
}
```

- [ ] **Step 2: Write the failing baseline tests**

Create `tests/test_baseline.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs import baseline
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "baseline-v1.schema.json"


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=functional-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "rationale: Protect data.\n"
        "\n## Authenticate\nThe service shall authenticate.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n## Login test\nSigns a user in.\n"
        ":::\n",
        encoding="utf-8",
    )


def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def build(root: Path) -> dict[str, object]:
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return baseline.build_baseline(result.snapshot, config)


def test_baseline_validates_against_its_schema(tmp_path: Path) -> None:
    write_project(tmp_path)
    validator().validate(build(tmp_path))


def test_baseline_carries_both_comparison_axes(tmp_path: Path) -> None:
    """Configuration and reference date are what make a round trip stable."""
    write_project(tmp_path)
    payload = build(tmp_path)

    assert payload["valid"] is True
    assert len(payload["configurationFingerprint"]) == 64
    assert payload["referenceDate"]
    assert payload["ruleSetVersion"] == "1"


def test_baseline_stores_authored_content_not_only_fingerprints(tmp_path: Path) -> None:
    """Diff reports modifications by field, which needs the field values."""
    write_project(tmp_path)
    payload = build(tmp_path)

    requirement = next(item for item in payload["objects"] if item["id"] == "REQ-1")
    assert requirement["title"] == "Authenticate"
    assert requirement["rationale"].startswith("Protect")
    assert requirement["attributes"]["priority"] == "high"
    assert requirement["location"]["file"] == "needs.qmd"


def test_baseline_render_is_byte_stable(tmp_path: Path) -> None:
    write_project(tmp_path)

    assert baseline.render_baseline(build(tmp_path)) == baseline.render_baseline(build(tmp_path))


def test_write_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    """An overwritten baseline is unrecoverable without version control."""
    write_project(tmp_path)
    payload = build(tmp_path)
    destination = tmp_path / "baselines" / "quarto-needs.json"
    baseline.write_baseline(destination, payload)
    sentinel = destination.read_text(encoding="utf-8")

    with pytest.raises(baseline.BaselineError):
        baseline.write_baseline(destination, payload)

    assert destination.read_text(encoding="utf-8") == sentinel
    baseline.write_baseline(destination, payload, force=True)


def test_load_round_trips_and_rejects_malformed_input(tmp_path: Path) -> None:
    write_project(tmp_path)
    payload = build(tmp_path)
    destination = tmp_path / "b.json"
    baseline.write_baseline(destination, payload)

    assert baseline.load_baseline(destination) == payload

    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(baseline.BaselineError):
        baseline.load_baseline(broken)

    wrong_version = tmp_path / "v2.json"
    wrong_version.write_text(json.dumps({"schemaVersion": "2"}), encoding="utf-8")
    with pytest.raises(baseline.BaselineError):
        baseline.load_baseline(wrong_version)


def test_invalid_baseline_preserves_declarations_and_findings(tmp_path: Path) -> None:
    """The diagnostic artifact exists so `inspect` can explain the failure."""
    (tmp_path / "dup.qmd").write_text(
        "::: {.need #D-1 type=need status=draft}\n\n## A\nA.\n:::\n"
        "\n::: {.need #D-1 type=need status=draft}\n\n## B\nB.\n:::\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is None

    payload = baseline.build_invalid_baseline(result, config)

    validator().validate(payload)
    assert payload["valid"] is False
    assert payload["declarations"]
    assert any(finding["code"] == "REQ004" for finding in payload["findings"])
    assert "objects" not in payload
    assert "semanticGraphFingerprint" not in payload
```

- [ ] **Step 3: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_baseline.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'quarto_needs.baseline'`.

- [ ] **Step 4: Implement `baseline.py`**

```python
"""The baseline artifact: a canonical snapshot plus its comparison axes.

A baseline stores authored content, not only fingerprints, because `diff`
reports semantic modifications by field and cannot name a field it never saw.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import quarto_needs

from . import fingerprints
from .analysis import AnalysisResult
from .config import NeedsConfig
from .export import _write_atomic_text
from .quality import report_from_snapshot
from .relations import DEFAULT_RELATION_CATALOG
from .rules import RULE_SET_VERSION
from .snapshot import AnalysisSnapshot, LocationRecord, thaw_json

SCHEMA_VERSION = "1"
DEFAULT_BASELINE_PATH = Path("baselines") / "quarto-needs.json"


class BaselineError(Exception):
    """A baseline could not be written, read, or trusted."""


def _location(location: LocationRecord | None) -> dict[str, object] | None:
    if location is None:
        return None
    return {"file": location.file, "line": location.line, "anchor": location.anchor}


def _header(reference_date: str, configuration: str) -> dict[str, object]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generator": {"name": "quarto-needs", "version": quarto_needs.__version__},
        "relationCatalogVersion": DEFAULT_RELATION_CATALOG.version,
        "ruleSetVersion": RULE_SET_VERSION,
        "referenceDate": reference_date,
        "configurationFingerprint": configuration,
    }


def build_baseline(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    queries: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    payload = _header(snapshot.reference_date, snapshot.configuration_fingerprint)
    payload["semanticGraphFingerprint"] = snapshot.semantic_graph_fingerprint
    payload["representationFingerprint"] = snapshot.representation_fingerprint
    payload["valid"] = True
    payload["objects"] = [
        {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "status": item.status,
            "body": item.body,
            "rationale": item.rationale,
            "attributes": thaw_json(item.attributes),
            "location": _location(item.locations[0] if item.locations else None),
            "contentFingerprint": fingerprints.object_content_fingerprint(item),
        }
        for item in snapshot.objects
    ]
    payload["relations"] = [
        {
            "source": item.source,
            "authoredName": item.authored_name,
            "target": item.target,
            "semanticFamily": item.semantic_family,
            "sourceRole": item.source_role,
            "targetRole": item.target_role,
            "impactDirection": item.impact_direction,
            "attributes": thaw_json(item.attributes),
            "authoredFingerprint": fingerprints.relation_authored_fingerprint(item),
            "semanticFingerprint": fingerprints.relation_semantic_fingerprint(item),
        }
        for item in snapshot.relations
    ]
    payload["findings"] = [finding.to_dict() for finding in snapshot.findings]
    payload["report"] = report_from_snapshot(snapshot, config, queries=queries).to_dict()
    return payload


def build_invalid_baseline(result: AnalysisResult, config: NeedsConfig) -> dict[str, object]:
    """The explicitly requested diagnostic artifact.

    It is never accepted by `diff` or `impact`: structural failures make graph
    comparison ambiguous. It exists so `baseline inspect` can explain why.
    """
    from .config import reference_date

    configuration = fingerprints.configuration_fingerprint(
        config, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    payload = _header(reference_date().isoformat(), configuration)
    payload["valid"] = False
    payload["declarations"] = [
        {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "status": item.status,
            "location": _location(item.location),
        }
        for item in result.declarations
    ]
    payload["findings"] = [finding.to_dict() for finding in result.findings]
    return payload


def render_baseline(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_baseline(path: Path, payload: dict[str, object], *, force: bool = False) -> None:
    path = Path(path)
    if path.exists() and not force:
        raise BaselineError(f"{path} already exists; pass --force to overwrite it")
    _write_atomic_text(path, render_baseline(payload))


def load_baseline(path: Path) -> dict[str, object]:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise BaselineError(f"Could not read {path}: {error}") from error
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise BaselineError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise BaselineError(f"{path} is not a baseline document")
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise BaselineError(
            f"{path} declares baseline schema {payload.get('schemaVersion')!r}; "
            f"this build reads {SCHEMA_VERSION!r}"
        )
    return payload
```

- [ ] **Step 5: Run the baseline tests**

Run: `.venv/bin/python -m pytest tests/test_baseline.py -q`

Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS, no warnings.

- [ ] **Step 7: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/baseline.py schemas/baseline-v1.schema.json tests/test_baseline.py
  git commit -m "feat: add the canonical baseline artifact"
else
  echo "Checkpoint 4 verified; workspace has no Git metadata."
fi
```
