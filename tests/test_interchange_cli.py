from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from quarto_needs.cli_entry import main
from quarto_needs.exporters import reqif_export


def _write_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #SYS-001 type=system-requirement status=approved verified-by=TC-001}\n"
        "## Authenticate users\n"
        "The system shall authenticate users.\n"
        ":::\n\n"
        "::: {.need #TC-001 type=test-case status=passed}\n"
        "## Authentication test\n"
        "Verify login.\n"
        ":::\n",
        encoding="utf-8",
    )


def test_installed_cli_exports_reqif_to_default_path(tmp_path: Path) -> None:
    _write_project(tmp_path)

    assert main(["--root", str(tmp_path), "export", "--format", "reqif"]) == 0

    output = tmp_path / ".quarto-needs" / "requirements.reqif"
    root = ET.fromstring(output.read_text(encoding="utf-8"))
    ns = {"r": reqif_export.REQIF_NS}
    assert root.find(".//r:REQ-IF-VERSION", ns).text == reqif_export.REQIF_HEADER_VERSION
    assert len(root.findall(".//r:SPEC-OBJECT", ns)) == 2


def test_installed_cli_exports_reqif_to_explicit_path(tmp_path: Path) -> None:
    _write_project(tmp_path)

    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "export",
                "--format",
                "reqif",
                "--output",
                "exchange/model.reqif",
            ]
        )
        == 0
    )
    assert (tmp_path / "exchange" / "model.reqif").is_file()
