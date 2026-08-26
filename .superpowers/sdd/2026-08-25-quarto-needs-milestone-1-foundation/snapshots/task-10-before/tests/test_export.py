from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_objects, analyze_project
from quarto_needs.export import (
    build_v1_payload,
    coverage,
    export_graph,
    export_lua_index,
    render_lua_index,
    render_v1_json,
    write_build_outputs,
    write_v1_graph,
)
from quarto_needs.model import EngineeringObject, Relation
from quarto_needs.snapshot import AnalysisSnapshot

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/canonical"


def canonical_snapshot() -> AnalysisSnapshot:
    result = analyze_project(
        FIXTURE,
        files=[FIXTURE / "a-tests.qmd", FIXTURE / "z-requirements.qmd"],
    )
    assert result.snapshot is not None
    return result.snapshot


def test_export_keeps_attributes_relations_and_backlinks(tmp_path: Path):
    """A graph export must retain view data needed by the Lua adapter."""
    req = EngineeringObject(
        "REQ-1",
        "functional-requirement",
        "Login",
        status="approved",
        attributes={"priority": "high", "tags": "security;login"},
        relations=[Relation("verified-by", "REQ-1", "TC-1")],
    )
    tc = EngineeringObject("TC-1", "test-case", "Login test", status="passed")
    output = tmp_path / "needs.json"

    export_graph(output, [req, tc], [])

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["objects"][0]["attributes"]["priority"] == "high"
    assert payload["relations"][0]["target"] == "TC-1"
    assert payload["backlinks"]["TC-1"] == [{"source": "REQ-1", "type": "verified-by"}]


def test_v1_render_is_byte_identical_for_reversed_file_order() -> None:
    first = analyze_project(
        FIXTURE,
        files=[FIXTURE / "a-tests.qmd", FIXTURE / "z-requirements.qmd"],
    )
    second = analyze_project(
        FIXTURE,
        files=[FIXTURE / "z-requirements.qmd", FIXTURE / "a-tests.qmd"],
    )
    assert first.snapshot is not None and second.snapshot is not None
    assert render_v1_json(first.snapshot) == render_v1_json(second.snapshot)
    assert render_v1_json(first.snapshot).endswith("\n")
    assert render_lua_index(first.snapshot).endswith("\n")


def test_v1_nested_relations_exactly_equal_top_level_relations() -> None:
    payload = json.loads(render_v1_json(canonical_snapshot()))
    nested = [relation for item in payload["objects"] for relation in item["relations"]]
    assert nested == payload["relations"]
    assert payload["relations"][0]["type"] == "derives-from"
    assert "authored_name" not in json.dumps(payload)


def test_v1_relation_catalog_contains_only_sorted_present_names() -> None:
    payload = build_v1_payload(canonical_snapshot())
    catalog = payload["extensions"]["quartoNeeds"]["relationCatalog"]
    assert list(catalog) == ["derives-from", "verified-by"]
    assert catalog["derives-from"] == {
        "directLabel": "Derives from",
        "inverseLabel": "Source for",
        "semanticFamily": "derivation",
        "sourceRole": "derived",
        "targetRole": "source",
        "impactDirection": "target_to_source",
        "public": True,
    }


def test_v1_relation_catalog_rejects_conflicting_alias_metadata() -> None:
    snapshot = canonical_snapshot()
    original = snapshot.outgoing["A-REQ-001"][0]
    conflicting = replace(
        original,
        authored_name="verified-by",
        catalog_name="verified-by",
        semantic_family="verification",
        source_role="requirement",
        target_role="test",
        impact_direction="source_to_target",
    )
    outgoing = dict(snapshot.outgoing)
    outgoing["A-REQ-001"] = (original, conflicting)
    malformed = replace(
        snapshot,
        relations=(original, conflicting),
        outgoing=outgoing,
    )

    with pytest.raises(ValueError, match="Conflicting relation aliases for v1 name derives-from"):
        build_v1_payload(malformed)


def test_v1_writer_replaces_destination_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "needs.json"
    destination.write_text("sentinel", encoding="utf-8")
    replacements: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def recording_replace(source: str | Path, target: str | Path) -> None:
        replacements.append((Path(source), Path(target)))
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", recording_replace)
    write_v1_graph(destination, canonical_snapshot())
    assert replacements and replacements[-1][1] == destination
    assert json.loads(destination.read_text(encoding="utf-8"))["schemaVersion"] == "1"
    assert not list(tmp_path.glob(".needs.json.*.tmp"))


def test_build_outputs_render_both_before_replacing_either_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph_path = tmp_path / "needs.json"
    index_path = tmp_path / "generated-index.lua"
    graph_path.write_text("old graph\n", encoding="utf-8")
    index_path.write_text("old index\n", encoding="utf-8")

    def fail_lua_render(snapshot: AnalysisSnapshot) -> str:
        raise TypeError("unsupported Lua index value")

    monkeypatch.setattr("quarto_needs.export.render_lua_index", fail_lua_render)
    with pytest.raises(TypeError, match="unsupported Lua index value"):
        write_build_outputs(graph_path, index_path, canonical_snapshot())
    assert graph_path.read_text(encoding="utf-8") == "old graph\n"
    assert index_path.read_text(encoding="utf-8") == "old index\n"


def test_lua_index_escapes_control_characters() -> None:
    result = analyze_objects(
        [
            EngineeringObject(
                'ID"\\',
                "test-case",
                "line one\nline two\rline three",
                status='pa"ssed',
            )
        ]
    )
    assert result.snapshot is not None
    rendered = render_lua_index(result.snapshot)
    assert '["ID\\"\\\\"]' in rendered
    assert 'title = "line one\\nline two\\rline three"' in rendered
    assert 'status = "pa\\"ssed"' in rendered


def test_coverage_keeps_exact_legacy_six_key_projection() -> None:
    result = coverage(
        [EngineeringObject("REQ-1", "functional-requirement", "Login")]
    )
    assert set(result) == {
        "requirements",
        "approved",
        "implemented",
        "verified",
        "implementation_coverage",
        "verification_coverage",
    }


@pytest.mark.parametrize("writer", [export_graph, export_lua_index])
def test_compatibility_writers_do_not_touch_invalid_destination(
    tmp_path: Path, writer: object
) -> None:
    destination = tmp_path / "existing-output"
    destination.write_text("sentinel\n", encoding="utf-8")
    duplicates = [
        EngineeringObject("DUP-1", "functional-requirement", "First"),
        EngineeringObject("DUP-1", "functional-requirement", "Second"),
    ]

    with pytest.raises(
        ValueError,
        match="^Cannot export a structurally invalid requirements graph$",
    ):
        if writer is export_graph:
            export_graph(destination, duplicates, [])
        else:
            export_lua_index(destination, duplicates)
    assert destination.read_text(encoding="utf-8") == "sentinel\n"


def test_canonical_fixture_matches_checked_in_bytes() -> None:
    snapshot = canonical_snapshot()
    assert render_v1_json(snapshot) == (
        FIXTURE / "expected-needs-v1.json"
    ).read_text(encoding="utf-8")
    assert render_lua_index(snapshot) == (
        FIXTURE / "expected-generated-index.lua"
    ).read_text(encoding="utf-8")
