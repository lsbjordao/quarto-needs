"""Deterministic JUnit projection of evaluated quality gates."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..export import _write_atomic_text
from ..quality import QualityReport


def _display(value: object) -> str:
    return "not evaluated" if value is None else str(value)


def render(report: QualityReport) -> str:
    gates = sorted(report.gates, key=lambda gate: (gate.name.casefold(), gate.name))
    failures = sum(1 for gate in gates if not gate.passed)

    suites = ET.Element(
        "testsuites",
        {"name": "quarto-needs", "tests": str(len(gates)), "failures": str(failures)},
    )
    suite = ET.SubElement(
        suites,
        "testsuite",
        {
            "name": "quarto-needs.gates",
            "tests": str(len(gates)),
            "failures": str(failures),
        },
    )
    properties = ET.SubElement(suite, "properties")
    for name, value in (
        ("errors", report.findings_by_severity.get("error", 0)),
        ("warnings", report.findings_by_severity.get("warning", 0)),
        ("profile", report.profile),
        ("reference-date", report.reference_date),
    ):
        ET.SubElement(properties, "property", {"name": name, "value": str(value)})

    for gate in gates:
        case = ET.SubElement(
            suite,
            "testcase",
            {"classname": "quarto-needs.gates", "name": gate.name},
        )
        if not gate.passed:
            message = (
                f"threshold {_display(gate.threshold)}, actual {_display(gate.actual)}"
            )
            failure = ET.SubElement(case, "failure", {"message": message})
            failure.text = (
                f"Gate {gate.name} failed in scope {gate.scope}: {message}."
            )

    ET.indent(suites, space="  ")
    return ET.tostring(suites, encoding="unicode", short_empty_elements=True) + "\n"


def write(path: Path, report: QualityReport) -> Path:
    destination = Path(path)
    _write_atomic_text(destination, render(report))
    return destination
