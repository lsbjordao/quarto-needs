from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.graph_output import (
    query_view_id,
    render_public_projection,
    write_default_projection,
)
from quarto_needs.graph_projection import build_projection


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "graph-public-v1.schema.json").read_text(encoding="utf-8"))

PROJECT = '''
::: {.need #STK-001 type="stakeholder-need" status="approved" tags="security"}
## Security stakeholder need
:::

::: {.need #SYS-001 type="system-requirement" status="approved" priority="high" tags="security" derives-from="STK-001"}
## Authenticate protected access
:::
'''.strip() + "\n"

CONFIG = '''
profile = "default"

[types.stakeholder-need]
role = "need"
allowed-statuses = ["approved"]

[types.system-requirement]
role = "requirement"
allowed-statuses = ["approved"]
required-attributes = ["priority", "tags"]

[queries.security-driver]
all = [
  { field = "id", op = "eq", value = "STK-001" },
]
sort = ["id:asc"]

[graph]
depth = 2
'''.strip() + "\n"


def prepare(tmp_path: Path):
    (tmp_path / "index.qmd").write_text(PROJECT, encoding="utf-8")
    (tmp_path / ".quarto-needs.toml").write_text(CONFIG, encoding="utf-8")
    config = load_config(tmp_path)
    result = analyze_project(tmp_path, config=config)
    assert result.snapshot is not None
    return config, result.snapshot


def validate_public(payload: dict[str, object]) -> None:
    Draft202012Validator(SCHEMA).validate(payload)


def test_public_projection_publishes_catalog_semantics(tmp_path: Path) -> None:
    config, snapshot = prepare(tmp_path)
    projection = build_projection(
        snapshot,
        node_ids=("STK-001", "SYS-001"),
        view_id="semantic-test",
    )

    payload = json.loads(render_public_projection(projection, config, snapshot=snapshot))
    validate_public(payload)

    assert payload["relationCatalogVersion"] == "3"
    derives = payload["relationSemantics"]["derives-from"]
    assert derives["family"] == "derivation"
    assert derives["sourceRole"] == "derived"
    assert derives["targetRole"] == "source"
    assert derives["impactDirection"] == "target_to_source"
    assert derives["traversalDirection"] == "target_to_source"
    assert "derivation" in payload["traversalProfiles"]["traceability"]
    assert payload["traversalProfiles"]["verification"] == [
        "verification",
        "evidence",
        "decision-confirmation",
    ]
    assert payload["typeRoles"] == {
        "stakeholder-need": "need",
        "system-requirement": "requirement",
    }

    edge = payload["edges"][0]
    assert edge["source"] == "SYS-001"
    assert edge["target"] == "STK-001"
    assert edge["provenance"] == [
        {"file": "index.qmd", "line": 5, "anchor": "SYS-001"}
    ]


def test_public_projection_omits_provenance_without_snapshot(tmp_path: Path) -> None:
    config, snapshot = prepare(tmp_path)
    projection = build_projection(
        snapshot,
        node_ids=("STK-001", "SYS-001"),
        view_id="semantic-test",
    )

    payload = json.loads(render_public_projection(projection, config))
    validate_public(payload)

    assert "provenance" not in payload["edges"][0]
    assert "traversalProfiles" in payload


def test_named_query_is_materialized_as_reusable_graph_view(tmp_path: Path) -> None:
    config, snapshot = prepare(tmp_path)

    default_path = write_default_projection(tmp_path, snapshot, config)
    assert default_path.is_file()

    default_payload = json.loads(default_path.read_text(encoding="utf-8"))
    validate_public(default_payload)

    view_id = query_view_id("security-driver")
    query_path = tmp_path / ".quarto-needs" / "graphs" / f"{view_id}.json"
    manifest_path = tmp_path / ".quarto-needs" / "graphs" / "views.json"

    assert query_path.is_file()
    assert manifest_path.is_file()

    query_payload = json.loads(query_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_public(query_payload)

    assert query_payload["view"]["id"] == view_id
    assert query_payload["view"]["query"] == "security-driver"
    assert "STK-001" in {node["id"] for node in query_payload["nodes"]}
    assert query_payload["traversalProfiles"]["architecture"]
    assert any("provenance" in edge for edge in query_payload["edges"])
    assert manifest == {
        "schemaVersion": "graph-views-v1",
        "queries": {"security-driver": view_id},
        "unavailable": {},
    }
