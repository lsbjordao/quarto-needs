"""Integration coverage for ``examples/minimal``.

The minimal example is the onboarding contract: a new user models a small
engineering problem and the canonical workflow (scan → check → trace →
render) must work without knowing the Quarto-Needs implementation.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from quarto_needs.analysis import analyze_project

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "examples" / "minimal"

EXPECTED_OBJECTS = {
    "STK-001",
    "REQ-001",
    "REQ-002",
    "REQ-003",
    "REQ-004",
    "ADR-001",
    "COMP-001",
    "COMP-002",
    "TC-001",
    "TC-002",
    "TC-003",
    "TC-004",
    "EVD-001",
    "EVD-002",
    "EVD-003",
}

EXPECTED_RELATIONS = {
    ("REQ-001", "STK-001"),
    ("REQ-002", "STK-001"),
    ("REQ-003", "STK-001"),
    ("REQ-004", "STK-001"),
    ("REQ-001", "COMP-001"),
    ("REQ-002", "COMP-001"),
    ("REQ-003", "COMP-002"),
    ("REQ-004", "COMP-002"),
    ("REQ-001", "TC-001"),
    ("REQ-002", "TC-002"),
    ("REQ-003", "TC-003"),
    ("REQ-004", "TC-004"),
    ("ADR-001", "REQ-001"),
    ("ADR-001", "REQ-002"),
    ("ADR-001", "COMP-001"),
    ("ADR-001", "COMP-002"),
    ("TC-001", "EVD-001"),
    ("TC-002", "EVD-002"),
    ("TC-003", "EVD-003"),
    ("TC-004", "EVD-001"),
}


def test_minimal_example_analyzes_cleanly_with_the_expected_story() -> None:
    result = analyze_project(MINIMAL)

    assert result.snapshot is not None
    snapshot = result.snapshot
    assert {record.id for record in snapshot.objects} == EXPECTED_OBJECTS
    assert {(item.source, item.target) for item in snapshot.relations} == (
        EXPECTED_RELATIONS
    )
    # A clean onboarding project reports nothing.
    assert snapshot.findings == ()


def test_minimal_example_quality_gate_is_appropriate() -> None:
    result = analyze_project(MINIMAL)
    assert result.snapshot is not None
    assert not [
        finding
        for finding in result.snapshot.findings
        if finding.severity == "error"
    ]


@pytest.mark.skipif(
    shutil.which("quarto") is None, reason="Quarto is not installed"
)
def test_minimal_example_renders_with_quarto(tmp_path: Path) -> None:
    venv_bin = Path(sys.prefix) / "bin"
    env = dict(os.environ)
    if venv_bin.is_dir():
        env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"

    subprocess.run(
        ["quarto", "render", "--to", "html"],
        cwd=MINIMAL,
        env=env,
        check=True,
        timeout=600,
    )
    assert (MINIMAL / "_book" / "index.html").is_file()
