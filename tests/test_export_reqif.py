from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import xmlschema
from reqif.parser import ReqIFParser

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


def test_reqif_is_accepted_by_independent_parser(tmp_path: Path) -> None:
    """Cross the first interoperability boundary without making that parser runtime authority."""
    write_project(tmp_path)
    destination = tmp_path / "requirements.reqif"
    reqif_export.write(destination, build(tmp_path))

    bundle = ReqIFParser.parse(str(destination))
    specifications = bundle.core_content.req_if_content.specifications

    assert len(specifications) == 1
    assert specifications[0].long_name == "Quarto-Needs Engineering Graph"
    assert list(bundle.iterate_specification_hierarchy(specifications[0]))


def test_reqif_validates_against_normative_xsd_when_supplied(tmp_path: Path) -> None:
    """Validate against OMG's normative schema without vendoring or downloading it implicitly."""
    schema_path = os.environ.get("REQIF_12_XSD")
    if not schema_path:
        pytest.skip("set REQIF_12_XSD to the normative OMG ReqIF 1.2 reqif.xsd")

    write_project(tmp_path)
    destination = tmp_path / "requirements.reqif"
    reqif_export.write(destination, build(tmp_path))

    schema = xmlschema.XMLSchema(schema_path)
    schema.validate(str(destination))
