from __future__ import annotations

import json
from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_objects
from quarto_needs.cli_entry import main
from quarto_needs.exporters import reqif_export
from quarto_needs.migrations.reqif import (
    ReqifMigrationError,
    build_migration_plan,
    load_reqif_document,
)
from quarto_needs.model import EngineeringObject, Relation


def _snapshot():
    result = analyze_objects(
        [
            EngineeringObject(
                "REQ-1",
                "system-requirement",
                "Authenticate users",
                status="approved",
                body="The system shall authenticate users.",
                rationale="Protect privileged operations.",
                attributes={"tags": "security", "priority": "high"},
                relations=[Relation("verified-by", "REQ-1", "TC-1")],
            ),
            EngineeringObject(
                "TC-1",
                "test-case",
                "Login test",
                status="passed",
                body="Exercise the login flow.",
            ),
        ]
    )
    assert result.snapshot is not None
    return result.snapshot


def _round_trip_root(tmp_path: Path) -> Path:
    path = tmp_path / "export.reqif"
    path.write_text(reqif_export.render(_snapshot()), encoding="utf-8")
    return path


def test_the_export_round_trips_through_the_import_plan(tmp_path: Path) -> None:
    document = load_reqif_document(_round_trip_root(tmp_path))

    plan = build_migration_plan(
        document,
        type_map={"system-requirement": "system-requirement", "test-case": "test-case"},
        relation_map={"verified-by": "verified-by"},
    )

    assert plan.schema == "reqif-migration-plan-v1"
    assert plan.tool == "ReqIF"
    assert [issue.code for issue in plan.issues] == []
    by_id = {candidate.source_id: candidate for candidate in plan.candidates}
    assert set(by_id) == {"REQ-1", "TC-1"}

    requirement = by_id["REQ-1"]
    assert requirement.source_type == "system-requirement"
    assert requirement.target_type == "system-requirement"
    assert requirement.title == "Authenticate users"
    assert requirement.status == "approved"
    assert "The system shall authenticate users." in requirement.content
    assert "### Rationale" in requirement.content
    assert "Protect privileged operations." in requirement.content
    assert requirement.relations == (
        type(requirement.relations[0])(
            source="REQ-1", relation="verified-by", target="TC-1", source_field="verified-by"
        ),
    )
    assert requirement.extras["tags"] == "security"
    assert requirement.extras["priority"] == "high"

    test_case = by_id["TC-1"]
    assert test_case.status == "passed"
    assert test_case.relations == ()


def test_unmapped_source_types_and_relations_are_reported(tmp_path: Path) -> None:
    document = load_reqif_document(_round_trip_root(tmp_path))

    plan = build_migration_plan(document)

    codes = sorted(issue.code for issue in plan.issues)
    assert codes == ["RELATION_UNMAPPED", "TYPE_UNMAPPED", "TYPE_UNMAPPED"]
    assert all(candidate.target_type is None for candidate in plan.candidates)


def test_typed_values_are_recovered_with_explicit_loss_reports(tmp_path: Path) -> None:
    document_text = """<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd">
  <THE-HEADER>
    <REQ-IF-HEADER IDENTIFIER="h1"><TITLE>Typed source</TITLE><REQ-IF-VERSION>1.0</REQ-IF-VERSION></REQ-IF-HEADER>
  </THE-HEADER>
  <CORE-CONTENT><REQ-IF-CONTENT>
    <DATATYPES>
      <DATATYPE-DEFINITION-ENUMERATION IDENTIFIER="dt-status" LONG-NAME="Status">
        <SPECIFIED-VALUES>
          <ENUM-VALUE IDENTIFIER="status-ok" LONG-NAME="approved"/>
        </SPECIFIED-VALUES>
      </DATATYPE-DEFINITION-ENUMERATION>
    </DATATYPES>
    <SPEC-TYPES>
      <SPEC-OBJECT-TYPE IDENTIFIER="ot-req" LONG-NAME="ReqIF Requirement">
        <SPEC-ATTRIBUTES>
          <ATTRIBUTE-DEFINITION-ENUMERATION IDENTIFIER="ad-status" LONG-NAME="status"/>
          <ATTRIBUTE-DEFINITION-XHTML IDENTIFIER="ad-body" LONG-NAME="body"/>
          <ATTRIBUTE-DEFINITION-BOOLEAN IDENTIFIER="ad-urgent" LONG-NAME="urgent"/>
        </SPEC-ATTRIBUTES>
      </SPEC-OBJECT-TYPE>
    </SPEC-TYPES>
    <SPEC-OBJECTS>
      <SPEC-OBJECT IDENTIFIER="obj-1" LONG-NAME="Typed object">
        <VALUES>
          <ATTRIBUTE-VALUE-ENUMERATION THE-VALUE="status-ok">
            <DEFINITION><ATTRIBUTE-DEFINITION-ENUMERATION-REF>ad-status</ATTRIBUTE-DEFINITION-ENUMERATION-REF></DEFINITION>
          </ATTRIBUTE-VALUE-ENUMERATION>
          <ATTRIBUTE-VALUE-XHTML>
            <DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>ad-body</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>
            <THE-VALUE><div xmlns="http://www.w3.org/1999/xhtml">Rendered <b>body</b> text.</div></THE-VALUE>
          </ATTRIBUTE-VALUE-XHTML>
          <ATTRIBUTE-VALUE-BOOLEAN THE-VALUE="true">
            <DEFINITION><ATTRIBUTE-DEFINITION-BOOLEAN-REF>ad-urgent</ATTRIBUTE-DEFINITION-BOOLEAN-REF></DEFINITION>
          </ATTRIBUTE-VALUE-BOOLEAN>
        </VALUES>
        <TYPE><SPEC-OBJECT-TYPE-REF>ot-req</SPEC-OBJECT-TYPE-REF></TYPE>
      </SPEC-OBJECT>
    </SPEC-OBJECTS>
    <SPEC-RELATIONS/>
    <SPECIFICATIONS/>
  </REQ-IF-CONTENT></CORE-CONTENT>
</REQ-IF>
"""
    path = tmp_path / "typed.reqif"
    path.write_text(document_text, encoding="utf-8")

    plan = build_migration_plan(
        load_reqif_document(path), type_map={"ReqIF Requirement": "functional-requirement"}
    )

    assert [issue.code for issue in plan.issues] == ["VALUE_FLATTENED"]
    assert "xhtml" in plan.issues[0].message
    candidate = plan.candidates[0]
    assert candidate.status == "approved"
    assert candidate.content == "Rendered body text."
    assert candidate.extras == {"urgent": "true"}


def test_documents_with_entities_and_malformed_xml_are_refused(tmp_path: Path) -> None:
    hostile = tmp_path / "hostile.reqif"
    hostile.write_text(
        '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY x "y">]><REQ-IF>&x;</REQ-IF>',
        encoding="utf-8",
    )
    with pytest.raises(ReqifMigrationError, match="DOCTYPE"):
        load_reqif_document(hostile)

    broken = tmp_path / "broken.reqif"
    broken.write_text("<REQ-IF><unclosed></REQ-IF>", encoding="utf-8")
    with pytest.raises(ReqifMigrationError, match="well-formed"):
        load_reqif_document(broken)

    wrong_root = tmp_path / "wrong.reqif"
    wrong_root.write_text("<NOT-REQIF/>", encoding="utf-8")
    with pytest.raises(ReqifMigrationError, match="root"):
        load_reqif_document(wrong_root)


def test_duplicate_identifiers_are_refused(tmp_path: Path) -> None:
    text = """<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd">
  <CORE-CONTENT><REQ-IF-CONTENT>
    <SPEC-TYPES/>
    <SPEC-OBJECTS>
      <SPEC-OBJECT IDENTIFIER="dup" LONG-NAME="A"><TYPE><SPEC-OBJECT-TYPE-REF>t</SPEC-OBJECT-TYPE-REF></TYPE></SPEC-OBJECT>
      <SPEC-OBJECT IDENTIFIER="dup" LONG-NAME="B"><TYPE><SPEC-OBJECT-TYPE-REF>t</SPEC-OBJECT-TYPE-REF></TYPE></SPEC-OBJECT>
    </SPEC-OBJECTS>
  </REQ-IF-CONTENT></CORE-CONTENT>
</REQ-IF>
"""
    path = tmp_path / "duplicate.reqif"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ReqifMigrationError, match="duplicate"):
        build_migration_plan(load_reqif_document(path))


def test_cli_builds_a_reqif_plan_and_writes_it(tmp_path: Path, capsys) -> None:
    _round_trip_root(tmp_path)

    exit_code = main(
        [
            "--root",
            str(tmp_path),
            "migrate",
            "reqif",
            "export.reqif",
            "--type-map",
            "system-requirement=system-requirement",
            "--type-map",
            "test-case=test-case",
            "--relation-map",
            "verified-by=verified-by",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "reqif-migration-plan-v1"
    assert {candidate["sourceId"] for candidate in payload["candidates"]} == {
        "REQ-1",
        "TC-1",
    }
    plan_path = tmp_path / ".quarto-needs" / "migrations" / "reqif-plan.json"
    assert plan_path.is_file()


def test_cli_round_trip_writes_markers_and_the_update_plan_is_no_change(
    tmp_path: Path, capsys
) -> None:
    _round_trip_root(tmp_path)
    common = [
        "--root",
        str(tmp_path),
        "migrate",
        "reqif",
        "export.reqif",
        "--type-map",
        "system-requirement=system-requirement",
        "--type-map",
        "test-case=test-case",
        "--relation-map",
        "verified-by=verified-by",
    ]

    written = main(
        common
        + [
            "--destination",
            "REQ-1=requirements.qmd",
            "--destination",
            "TC-1=verification.qmd",
            "--apply-plan",
            "--write",
        ]
    )
    assert written == 0
    requirements = (tmp_path / "requirements.qmd").read_text(encoding="utf-8")
    assert 'source-tool="reqif"' in requirements
    assert 'source-id="REQ-1"' in requirements
    assert "verified-by: TC-1" in requirements

    capsys.readouterr()
    classified = main(common + ["--update-plan", "--format", "json"])

    assert classified == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "migration-update-plan-v1"
    assert payload["applicable"] is True
    assert {item["status"] for item in payload["items"]} == {"no-change"}
