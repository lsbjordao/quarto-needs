# Task 6: Markdown CI summary exporter

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

## Task 6

Markdown CI summary exporter

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
