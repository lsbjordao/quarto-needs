from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

from quarto_needs.analysis import analyze_project
from quarto_needs.export import render_v1_json

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
GOLDEN = ROOT / "tests/fixtures/v1/aegis-needs-v1.json"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def legacy_projection(payload: dict[str, object]) -> dict[str, object]:
    projected = {key: value for key, value in payload.items() if key != "extensions"}
    projected["objects"] = sorted(projected["objects"], key=lambda item: (item["id"].casefold(), item["id"]))
    projected["relations"] = sorted(
        projected["relations"],
        key=lambda item: (
            item["source"].casefold(), item["source"], item["type"],
            item["target"].casefold(), item["target"],
            json.dumps(item.get("attributes", {}), ensure_ascii=False, sort_keys=True),
        ),
    )
    projected["validation"] = sorted(
        projected["validation"],
        key=lambda item: (item["severity"], item["code"], item.get("object_id") or "", item["message"]),
    )
    projected["backlinks"] = {
        key: sorted(value, key=lambda item: (item["source"].casefold(), item["type"]))
        for key, value in sorted(projected["backlinks"].items())
    }
    for item in projected["objects"]:
        item["relations"] = sorted(
            item.get("relations", []),
            key=lambda relation: (
                relation["type"], relation["target"].casefold(), relation["target"],
                json.dumps(relation.get("attributes", {}), ensure_ascii=False, sort_keys=True),
            ),
        )
    return projected


def envelope_validator() -> Draft202012Validator:
    schema = load_json(SCHEMAS / "needs-envelope-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    resolver = RefResolver(
        (SCHEMAS / "needs-envelope-v1.schema.json").as_uri(),
        schema,
        store={
            "https://quarto-needs.dev/schema/needs.schema.json": load_json(
                SCHEMAS / "needs.schema.json"
            )
        },
    )
    return Draft202012Validator(schema, resolver=resolver)


def test_frozen_aegis_payload_validates_against_v1_envelope() -> None:
    envelope_validator().validate(load_json(GOLDEN))


def test_regenerated_aegis_graph_validates_against_v1_envelope() -> None:
    """The checked-in regenerated artifact stays schema-valid, extensions included."""
    payload = load_json(ROOT / "examples/book/.quarto-needs/needs.json")
    envelope_validator().validate(payload)
    assert "relationCatalog" in payload["extensions"]["quartoNeeds"]


def test_frozen_payload_has_nested_and_top_level_relation_equivalence() -> None:
    payload = load_json(GOLDEN)
    nested = [relation for item in payload["objects"] for relation in item.get("relations", [])]
    key = lambda relation: json.dumps(relation, ensure_ascii=False, sort_keys=True)
    assert sorted(nested, key=key) == sorted(payload["relations"], key=key)


def test_refactored_aegis_export_preserves_v1_semantics() -> None:
    frozen = load_json(GOLDEN)
    result = analyze_project(ROOT / "examples/book")
    assert result.snapshot is not None
    current = json.loads(render_v1_json(result.snapshot))
    assert legacy_projection(current) == legacy_projection(frozen)
