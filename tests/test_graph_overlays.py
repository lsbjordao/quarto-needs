from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs import baseline, graph_projection
from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.diff import DiffError
from quarto_needs.impact import ImpactError

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "graph-public-v1.schema.json"

GHOST_BODY_CANARY = "GHOSTBODYcanary7f3a"

V1_A = (
    "::: {.need #REQ-1 type=functional-requirement status=approved priority=high tags=\"core\"}\n"
    "verified-by:\n"
    "  - TC-1\n"
    "  - TC-2\n"
    "\n## Authenticate\nOriginal body.\n:::\n"
    "\n"
    "::: {.need #REQ-2 type=functional-requirement status=draft priority=low tags=\"aux\"}\n"
    f"\n## Legacy\n{GHOST_BODY_CANARY} lives only in the baseline.\n:::\n"
    "\n"
    "::: {.need #TC-1 type=test-case status=passed}\n\n## Login test\nSigns a user in.\n:::\n"
)

V1_B = (
    "::: {.need #TC-2 type=test-case status=passed}\n\n## Logout test\nSigns a user out.\n:::\n"
)

V2_REQ1 = (
    "::: {.need #REQ-1 type=functional-requirement status=approved priority=high tags=\"core\"}\n"
    "verified-by:\n"
    "  - TC-2\n"
    "\n## Authenticate\nEdited body.\n:::\n"
)

V2_REQ3 = (
    "::: {.need #REQ-3 type=functional-requirement status=draft priority=medium tags=\"new\"}\n"
    "verified-by: TC-2\n"
    "\n## Fresh\nA brand-new requirement.\n:::\n"
)

V2_TC1 = (
    "::: {.need #TC-1 type=test-case status=passed}\n\n## Login test\nSigns a user in.\n:::\n"
)


def write(root: Path, files: dict[str, str], config: str | None = None) -> None:
    for existing in root.glob("*.qmd"):
        existing.unlink()
    if config is None:
        (root / ".quarto-needs.toml").unlink(missing_ok=True)
    else:
        (root / ".quarto-needs.toml").write_text(config, encoding="utf-8")
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")


def v1(root: Path) -> None:
    write(root, {"a.qmd": V1_A, "b.qmd": V1_B})


def v2(root: Path, *, order: str = "forward") -> None:
    blocks = [V2_REQ1, V2_REQ3, V2_TC1]
    if order != "forward":
        blocks = [V2_REQ3, V2_REQ1, V2_TC1]
    write(root, {"a.qmd": "\n".join(blocks) + "\n", "c.qmd": V1_B})


def snapshot_of(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None, [str(f) for f in result.findings]
    return result.snapshot


def baseline_of(root: Path) -> dict[str, object]:
    return baseline.build_baseline(snapshot_of(root), load_config(root))


def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def diff_overlay(root: Path, *, order: str = "forward", **overrides):
    v1(root)
    payload = baseline_of(root)
    v2(root, order=order)
    snapshot = snapshot_of(root)
    kwargs = dict(
        node_ids=("REQ-1", "REQ-3", "TC-1", "TC-2"),
        view_id="need-graph-diff",
    )
    kwargs.update(overrides)
    return graph_projection.build_diff_overlay(payload, snapshot, load_config(root), **kwargs)


# --- diff overlay -------------------------------------------------------------


def test_diff_overlay_classifies_every_change(tmp_path: Path) -> None:
    projection = diff_overlay(tmp_path)
    payload = json.loads(graph_projection.render_projection(projection))

    assert payload["view"]["mode"] == "diff"
    changes = {node["id"]: node.get("change") for node in payload["nodes"]}
    assert changes["REQ-1"] == "modified"
    assert changes["REQ-3"] == "added"
    assert changes["TC-1"] == "unchanged"
    assert changes["TC-2"] == "relocated"
    assert changes["REQ-2"] == "removed"

    by_key = {
        (edge["source"], edge["target"], edge["relation"]): edge.get("change")
        for edge in payload["edges"]
    }
    assert by_key[("REQ-1", "TC-2", "verified-by")] == "unchanged"
    assert by_key[("REQ-3", "TC-2", "verified-by")] == "added"
    assert by_key[("REQ-1", "TC-1", "verified-by")] == "removed"


def test_ghost_nodes_carry_only_public_baseline_fields(tmp_path: Path) -> None:
    projection = diff_overlay(tmp_path)
    serialized = graph_projection.render_projection(projection)
    payload = json.loads(serialized)

    ghost = next(node for node in payload["nodes"] if node["id"] == "REQ-2")
    assert ghost["title"] == "Legacy"
    assert ghost["type"] == "functional-requirement"
    assert ghost["status"] == "draft"
    assert ghost["priority"] == "low"
    assert ghost["tags"] == ["aux"]
    assert ghost["href"] == "#REQ-2"
    assert set(ghost) <= set(graph_projection.PUBLIC_NODE_FIELDS)

    assert GHOST_BODY_CANARY not in serialized, "a baseline body reached the diff overlay"


def test_ghost_edges_use_the_current_catalog_for_relation_and_label(tmp_path: Path) -> None:
    payload = json.loads(graph_projection.render_projection(diff_overlay(tmp_path)))

    ghost_edge = next(
        edge for edge in payload["edges"] if edge["target"] == "TC-1"
    )
    assert ghost_edge["relation"] == "verified-by"
    assert ghost_edge["label"] == "Verified by"
    assert set(ghost_edge) <= set(graph_projection.PUBLIC_EDGE_FIELDS)


def test_diff_overlay_validates_against_its_schema(tmp_path: Path) -> None:
    validator().validate(json.loads(graph_projection.render_projection(diff_overlay(tmp_path))))


def test_diff_overlay_is_byte_identical_across_input_permutations(tmp_path: Path) -> None:
    forward = graph_projection.render_projection(diff_overlay(tmp_path, order="forward"))
    reverse = graph_projection.render_projection(diff_overlay(tmp_path, order="reverse"))
    assert forward == reverse

    permuted_request = graph_projection.render_projection(
        diff_overlay(tmp_path, node_ids=("TC-2", "REQ-3", "REQ-1", "TC-1"))
    )
    assert forward == permuted_request


def test_diff_overlay_builds_across_configuration_and_date_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Configuration change: the engine notices, but content classes survive.
    v1(tmp_path)
    payload = baseline_of(tmp_path)
    write(tmp_path, {"a.qmd": V2_REQ1 + "\n" + V2_REQ3 + "\n" + V2_TC1, "c.qmd": V1_B},
          config="[rules.REQ011]\nenabled = true\n")
    snapshot = snapshot_of(tmp_path)
    overlay = graph_projection.build_diff_overlay(
        payload, snapshot, load_config(tmp_path), node_ids=("REQ-1", "TC-2"), view_id="g"
    )
    changes = {node.id: node.change for node in overlay.nodes}
    assert changes["REQ-1"] == "modified"

    # Reference-date change: same story, the guard never blocks `diff`.
    other = tmp_path / "dated"
    other.mkdir()
    v1(other)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1600000000")
    dated_payload = baseline_of(other)
    monkeypatch.delenv("SOURCE_DATE_EPOCH")
    v2(other)
    overlay = graph_projection.build_diff_overlay(
        dated_payload, snapshot_of(other), load_config(other),
        node_ids=("REQ-1", "REQ-3", "TC-1", "TC-2"), view_id="g",
    )
    changes = {node.id: node.change for node in overlay.nodes}
    assert changes["REQ-3"] == "added"


def test_diff_overlay_refuses_a_diagnostic_baseline(tmp_path: Path) -> None:
    (tmp_path / "dup.qmd").write_text(
        "::: {.need #D-1 type=need status=draft}\n\n## A\nA.\n:::\n"
        "\n::: {.need #D-1 type=need status=draft}\n\n## B\nB.\n:::\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is None
    payload = baseline.build_invalid_baseline(result, config)

    with pytest.raises(DiffError):
        graph_projection.build_diff_overlay(
            payload, result.snapshot, config, node_ids=(), view_id="g"
        )


def test_diff_limits_count_ghost_nodes(tmp_path: Path) -> None:
    with pytest.raises(graph_projection.GraphLimitExceeded) as raised:
        diff_overlay(tmp_path, limits={"nodes": 4, "edges": 300})
    # 4 current nodes + 1 ghost.
    assert raised.value.actual["nodes"] == 5


# --- impact overlay -----------------------------------------------------------


CHAIN_V1 = (
    "::: {.need #STK-1 type=need status=approved priority=high}\n"
    "\n## Stake\nStakeholder concern.\n:::\n"
    "\n"
    "::: {.need #SYS-1 type=system-requirement status=approved priority=high "
    'derives-from="STK-1" verified-by="TC-9"}\n'
    "\n## System\nThe system shall do it.\n:::\n"
    "\n"
    "::: {.need #TC-9 type=test-case status=passed}\n\n## Verify\nChecks the system.\n:::\n"
)

CHAIN_V2 = CHAIN_V1.replace("Stakeholder concern.", "Stakeholder concern, revised.")


def impact_overlay(root: Path, *, recompute: bool = False, seed_selection=("STK-1",)):
    (root / "chain.qmd").write_text(CHAIN_V1, encoding="utf-8")
    payload = baseline_of(root)
    (root / "chain.qmd").write_text(CHAIN_V2, encoding="utf-8")
    snapshot = snapshot_of(root)
    return graph_projection.build_impact_overlay(
        payload, snapshot, load_config(root),
        node_ids=seed_selection, view_id="need-graph-impact", recompute=recompute,
    )


def test_impact_overlay_maps_report_paths_onto_the_projection(tmp_path: Path) -> None:
    (tmp_path / "chain.qmd").write_text(CHAIN_V1, encoding="utf-8")
    projection = impact_overlay(tmp_path)
    payload = json.loads(graph_projection.render_projection(projection))

    assert payload["view"]["mode"] == "impact"
    assert payload["impact"] == [
        {
            "id": "SYS-1",
            "origin": "STK-1",
            "distance": 1,
            "path": ["STK-1", "SYS-1"],
            "classification": "direct",
        },
        {
            "id": "TC-9",
            "origin": "STK-1",
            "distance": 2,
            "path": ["STK-1", "SYS-1", "TC-9"],
            "classification": "transitive",
        },
    ]

    # The node set grew from the selection to the whole explained path...
    assert {node["id"] for node in payload["nodes"]} == {"STK-1", "SYS-1", "TC-9"}
    # ...and exactly the path edges are marked as path members, regardless of
    # which end authored the relation.
    members = {
        (edge["source"], edge["target"], edge["relation"]): edge.get("pathMember")
        for edge in payload["edges"]
    }
    assert members[("SYS-1", "STK-1", "derives-from")] is True
    assert members[("SYS-1", "TC-9", "verified-by")] is True


def test_impact_overlay_validates_against_its_schema(tmp_path: Path) -> None:
    (tmp_path / "chain.qmd").write_text(CHAIN_V1, encoding="utf-8")
    validator().validate(
        json.loads(graph_projection.render_projection(impact_overlay(tmp_path)))
    )


def test_impact_overlay_is_byte_identical_across_request_permutations(tmp_path: Path) -> None:
    """Request order must not leak into the projection; a redundant seed id
    that already sits on an explained path changes nothing either."""
    plain = graph_projection.render_projection(impact_overlay(tmp_path))
    permuted = graph_projection.render_projection(
        impact_overlay(tmp_path, seed_selection=("SYS-1", "STK-1"))
    )
    redundant = graph_projection.render_projection(
        impact_overlay(tmp_path, seed_selection=("STK-1", "SYS-1"))
    )
    assert plain == permuted == redundant


def test_impact_overlay_refuses_guard_mismatches_without_recompute(tmp_path: Path) -> None:
    (tmp_path / "chain.qmd").write_text(CHAIN_V1, encoding="utf-8")

    # Configuration mismatch.
    payload = baseline_of(tmp_path)
    (tmp_path / "chain.qmd").write_text(CHAIN_V2, encoding="utf-8")
    (tmp_path / ".quarto-needs.toml").write_text(
        "[rules.REQ011]\nenabled = true\n", encoding="utf-8"
    )
    snapshot = snapshot_of(tmp_path)
    config = load_config(tmp_path)
    with pytest.raises(ImpactError, match="different configuration"):
        graph_projection.build_impact_overlay(
            payload, snapshot, config, node_ids=("STK-1",), view_id="g"
        )
    overlay = graph_projection.build_impact_overlay(
        payload, snapshot, config, node_ids=("STK-1",), view_id="g", recompute=True
    )
    assert overlay.impact


def test_impact_overlay_refuses_a_date_mismatch_but_recomputes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1600000000")
    (tmp_path / "chain.qmd").write_text(CHAIN_V1, encoding="utf-8")
    payload = baseline_of(tmp_path)
    monkeypatch.delenv("SOURCE_DATE_EPOCH")

    (tmp_path / "chain.qmd").write_text(CHAIN_V2, encoding="utf-8")
    snapshot = snapshot_of(tmp_path)
    config = load_config(tmp_path)
    with pytest.raises(ImpactError, match="different reference date"):
        graph_projection.build_impact_overlay(
            payload, snapshot, config, node_ids=("STK-1",), view_id="g"
        )
    overlay = graph_projection.build_impact_overlay(
        payload, snapshot, config, node_ids=("STK-1",), view_id="g", recompute=True
    )
    assert {entry.id for entry in overlay.impact} == {"SYS-1", "TC-9"}


def test_graph_settings_change_trips_neither_guard(tmp_path: Path) -> None:
    """A `[graph]`-only change is presentation policy, not graph semantics.

    Pinned end to end: impact must traverse without `--recompute-with current`
    even though the config file on disk changed between baseline and current.
    """
    (tmp_path / "chain.qmd").write_text(CHAIN_V1, encoding="utf-8")
    payload = baseline_of(tmp_path)
    (tmp_path / "chain.qmd").write_text(CHAIN_V2, encoding="utf-8")
    (tmp_path / ".quarto-needs.toml").write_text("[graph]\nmax-nodes = 5\n", encoding="utf-8")

    overlay = graph_projection.build_impact_overlay(
        payload, snapshot_of(tmp_path), load_config(tmp_path),
        node_ids=("STK-1",), view_id="g",
    )
    assert {entry.id for entry in overlay.impact} == {"SYS-1", "TC-9"}


def test_diff_overlay_surfaces_technology_attribute(tmp_path: Path) -> None:
    """Verify technology attribute flows through diff overlay construction."""
    # V1: Need with technology attribute
    v1_needs = (
        "::: {.need #REQ-1 type=container status=approved technology=\"Python 3.12\"}\n"
        "\n## Backend\nThe backend service.\n:::\n"
    )
    v1(tmp_path)
    (tmp_path / "a.qmd").write_text(v1_needs, encoding="utf-8")
    (tmp_path / "b.qmd").unlink(missing_ok=True)
    payload = baseline_of(tmp_path)

    # V2: Same need, to verify it's preserved
    v2_needs = (
        "::: {.need #REQ-1 type=container status=approved technology=\"Python 3.13\"}\n"
        "\n## Backend\nThe backend service (upgraded).\n:::\n"
    )
    (tmp_path / "a.qmd").write_text(v2_needs, encoding="utf-8")
    snapshot = snapshot_of(tmp_path)

    overlay = graph_projection.build_diff_overlay(
        payload, snapshot, load_config(tmp_path),
        node_ids=("REQ-1",), view_id="test-tech"
    )
    node_dict = json.loads(graph_projection.render_projection(overlay))["nodes"][0]
    assert node_dict["technology"] == "Python 3.13"


def test_impact_overlay_surfaces_technology_attribute(tmp_path: Path) -> None:
    """Verify technology attribute flows through impact overlay construction."""
    chain_v1_tech = (
        "::: {.need #STK-1 type=need status=approved}\n"
        "\n## Stake\nStakeholder concern.\n:::\n"
        "\n"
        "::: {.need #SYS-1 type=system-requirement status=approved technology=\"Go 1.21\" "
        'derives-from="STK-1"}\n'
        "\n## System\nThe system shall do it.\n:::\n"
    )
    (tmp_path / "chain.qmd").write_text(chain_v1_tech, encoding="utf-8")
    payload = baseline_of(tmp_path)
    snapshot = snapshot_of(tmp_path)
    config = load_config(tmp_path)

    overlay = graph_projection.build_impact_overlay(
        payload, snapshot, config, node_ids=("STK-1", "SYS-1"), view_id="test-impact-tech"
    )

    # Verify the node in the impact overlay has technology
    rendered = json.loads(graph_projection.render_projection(overlay))
    sys_node = next((n for n in rendered["nodes"] if n["id"] == "SYS-1"), None)
    assert sys_node is not None
    assert sys_node["technology"] == "Go 1.21"
