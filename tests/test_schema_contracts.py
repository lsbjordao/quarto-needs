"""Public artifact schema contract tests.

Companion to ``notes/schema-compatibility.md``: every public-versioned
artifact must carry its version identifier, ship a parseable JSON Schema,
and expose only allowlist-constructed fields. These tests fail when an
artifact silently loses its version marker or when an internal field leaks
into a public projection.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project
from quarto_needs.baseline import build_baseline
from quarto_needs.config import embedded_defaults
from quarto_needs.diff import SCHEMA_VERSION as DIFF_VERSION
from quarto_needs.diff import compare
from quarto_needs.graph_projection import (
    PUBLIC_EDGE_FIELDS,
    PUBLIC_NODE_FIELDS,
    SCHEMA_VERSION as GRAPH_VERSION,
)
from quarto_needs.graph_projection import build_projection, render_projection
from quarto_needs.impact import SCHEMA_VERSION as IMPACT_VERSION
from quarto_needs.impact import analyze as impact_analyze

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "tests/fixtures/canonical"


def _canonical_snapshot():
    result = analyze_project(
        FIXTURES,
        files=[FIXTURES / "a-tests.qmd", FIXTURES / "z-requirements.qmd"],
    )
    assert result.snapshot is not None
    return result.snapshot


def test_every_packaged_schema_is_valid_json_with_a_dialect() -> None:
    schema_files = sorted(SCHEMAS.glob("*.schema.json"))
    assert schema_files, "schemas/ is expected to package public schemas"
    for path in schema_files:
        document = json.loads(path.read_text(encoding="utf-8"))
        assert "$schema" in document, f"{path.name} lacks a $schema dialect"


def test_public_artifacts_carry_their_schema_version_markers() -> None:
    from quarto_needs import suspect as suspect_module
    from quarto_needs.suspect import SCHEMA_VERSION as SUSPECT_VERSION

    snapshot = _canonical_snapshot()
    config = embedded_defaults()

    baseline_payload = build_baseline(snapshot, config)
    assert baseline_payload["schemaVersion"] == "1"

    diff_report = compare(baseline_payload, snapshot, config)
    assert diff_report.to_dict()["schemaVersion"] == DIFF_VERSION == "1"

    suspect_report = suspect_module.analyze(baseline_payload, snapshot, config)
    assert suspect_report.to_dict()["schemaVersion"] == SUSPECT_VERSION

    impact_report = impact_analyze(baseline_payload, snapshot, config)
    assert impact_report.to_dict()["schemaVersion"] == IMPACT_VERSION


def test_graph_projection_payload_is_allowlist_built() -> None:
    snapshot = _canonical_snapshot()

    projection = build_projection(
        snapshot,
        node_ids=[record.id for record in snapshot.objects],
        view_id="contract",
    )
    payload = json.loads(render_projection(projection))

    assert payload["schemaVersion"] == GRAPH_VERSION == "graph-public-v1"
    for node in payload["nodes"]:
        assert set(node) <= set(PUBLIC_NODE_FIELDS)
    for edge in payload["edges"]:
        assert set(edge) <= set(PUBLIC_EDGE_FIELDS)


@pytest.mark.parametrize(
    ("artifact", "schema_name"),
    [
        ("baseline", "baseline-v1.schema.json"),
        ("diff", "diff-v1.schema.json"),
        ("impact", "impact-v1.schema.json"),
        ("graph-public", "graph-public-v1.schema.json"),
        ("needs-envelope", "needs-envelope-v1.schema.json"),
        ("evidence-envelope", "evidence-envelope-v1.schema.json"),
    ],
)
def test_schema_file_naming_tracks_the_versioned_contract(
    artifact: str, schema_name: str
) -> None:
    # A public version bump must rename its schema file; this keeps the
    # naming convention observable when that happens.
    assert (SCHEMAS / schema_name).is_file()
    assert schema_name.startswith(f"{artifact}-v")
