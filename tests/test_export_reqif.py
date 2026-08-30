from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import reqif_export

NS = {"r": reqif_export.REQIF_NS}


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved priority=high}\n"
        "verified-by: TC-1\n"
        "rationale: Protect data.\n\n"
        "## Authenticate & authorize\n"
        "The service shall authenticate <users>.\n"
        ":::\n\n"
        "::: {.need #TC-1 type=test-case status=passed}\n\n"
        "## Login test\n"
        "Exercise authentication.\n"
        ":::\n",
        encoding="utf-8",
    )


def build(root: Path):
    result = analyze_project(root, config=load_config(root))
    assert result.snapshot is not None
    return result.snapshot


def test_reqif_renders_namespace_objects_relations_and_specification(tmp_path: Path) -> None:
    write_project(tmp_path)
    rendered = reqif_export.render(build(tmp_path))
    root = ET.fromstring(rendered)

    assert root.tag == f"{{{reqif_export.REQIF_NS}}}REQ-IF"
    assert root.find(".//r:REQ-IF-VERSION", NS).text == "1.2"
    assert len(root.findall(".//r:SPEC-OBJECT", NS)) == 2
    assert len(root.findall(".//r:SPEC-RELATION", NS)) == 1
    assert len(root.findall(".//r:SPECIFICATION", NS)) == 1
    assert len(root.findall(".//r:SPEC-HIERARCHY", NS)) == 2


def test_reqif_preserves_canonical_ids_and_relation_semantics(tmp_path: Path) -> None:
    write_project(tmp_path)
    root = ET.fromstring(reqif_export.render(build(tmp_path)))

    values = {
        node.attrib["THE-VALUE"]
        for node in root.findall(".//r:ATTRIBUTE-VALUE-STRING", NS)
    }
    relation_types = {
        node.attrib.get("LONG-NAME", "")
        for node in root.findall(".//r:SPEC-RELATION-TYPE", NS)
    }
    descriptions = {
        node.attrib.get("DESC", "")
        for node in root.findall(".//r:SPEC-RELATION-TYPE", NS)
    }

    assert {"REQ-1", "TC-1"} <= values
    assert "verified-by" in relation_types
    assert any("verification" in description for description in descriptions)


def test_reqif_is_deterministic_and_xml_escapes_authored_text(tmp_path: Path) -> None:
    write_project(tmp_path)
    snapshot = build(tmp_path)
    first = reqif_export.render(snapshot)
    second = reqif_export.render(snapshot)

    assert first == second
    assert "Authenticate &amp; authorize" in first
    assert "&lt;users&gt;" in first


def test_reqif_write_uses_atomic_export_path(tmp_path: Path) -> None:
    write_project(tmp_path)
    destination = tmp_path / "out" / "requirements.reqif"
    written = reqif_export.write(destination, build(tmp_path))

    assert written == destination
    assert destination.read_text(encoding="utf-8").startswith("<?xml version=")
