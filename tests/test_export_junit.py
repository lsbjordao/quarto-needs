from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from quarto_needs.analysis import analyze_project
from quarto_needs.config import load_config
from quarto_needs.exporters import junit_export
from quarto_needs.quality import report_from_snapshot


def write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=system-requirement status=approved}\n"
        "verified-by: TC-1\n"
        "\n## Authenticate\nBody.\n"
        ":::\n"
        "\n"
        "::: {.need #REQ-2 type=system-requirement status=approved}\n"
        "\n## Second\nBody.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n## Login\nSigns in.\n"
        ":::\n",
        encoding="utf-8",
    )


def report_for(root: Path):
    config = load_config(root)
    result = analyze_project(root, config=config)
    assert result.snapshot is not None
    return report_from_snapshot(result.snapshot, config)


def test_junit_has_one_testcase_per_gate_and_failures_name_the_gate(tmp_path: Path) -> None:
    write_project(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[gates]\nmin-verification-trace = 100.0\n', encoding="utf-8"
    )
    report = report_for(tmp_path)

    root = ET.fromstring(junit_export.render(report))
    assert root.tag == "testsuites"
    suite = root.find("testsuite")
    assert suite is not None
    names = [case.attrib["name"] for case in suite.findall("testcase")]
    assert names == sorted(g["name"] for g in report.to_dict()["gates"])

    failed = {
        case.attrib["name"]
        for case in suite.iter("testcase")
        if case.find("failure") is not None
    }
    expected = {g["name"] for g in report.to_dict()["gates"] if g["passed"] is False}
    assert failed == expected


def test_junit_properties_carry_warning_counts_and_output_is_deterministic(tmp_path: Path) -> None:
    write_project(tmp_path)
    report = report_for(tmp_path)

    first = junit_export.render(report)
    root = ET.fromstring(first)
    properties = {p.attrib["name"]: p.attrib["value"] for p in root.iter("property")}
    assert properties["warnings"] == str(report.findings_by_severity.get("warning", 0))
    assert properties["profile"] == report.profile

    assert junit_export.render(report) == first


def test_junit_writer_uses_the_atomic_text_path(tmp_path: Path) -> None:
    write_project(tmp_path)
    report = report_for(tmp_path)
    destination = tmp_path / "nested" / "quality.xml"

    assert junit_export.write(destination, report) == destination
    assert destination.read_text(encoding="utf-8") == junit_export.render(report)
