from __future__ import annotations

import json
from pathlib import Path

from quarto_needs.export import export_graph
from quarto_needs.model import EngineeringObject, Relation


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
