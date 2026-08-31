from __future__ import annotations

import struct
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
BRANDING = ROOT / "docs" / "assets" / "branding"


def _png_size(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    assert payload[12:16] == b"IHDR"
    return struct.unpack(">II", payload[16:24])


def test_branding_svg_masters_exist_and_are_parseable() -> None:
    for name in (
        "quarto-needs-logo.svg",
        "quarto-needs-symbol.svg",
        "quarto-needs-app-icon.svg",
        "quarto-needs-roadmap-infographic.svg",
    ):
        path = BRANDING / name
        assert path.is_file(), name
        root = ET.parse(path).getroot()
        assert root.tag.endswith("svg")
        assert root.attrib.get("viewBox"), f"{name} must declare a viewBox"


def test_packaged_application_icons_are_synchronized() -> None:
    icon_256 = BRANDING / "quarto-needs-app-icon-256.png"
    icon_512 = BRANDING / "quarto-needs-app-icon-512.png"
    vscode_icon = ROOT / "editors" / "vscode" / "icon.png"

    assert _png_size(icon_256) == (256, 256)
    assert _png_size(icon_512) == (512, 512)
    assert vscode_icon.read_bytes() == icon_256.read_bytes()


def test_documentation_does_not_depend_on_retired_branding_rasters() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    branding_doc = (ROOT / "docs" / "branding.md").read_text(encoding="utf-8")
    retired = (
        "quarto-needs-logo.webp",
        "quarto-needs-symbol.webp",
        "quarto-needs-roadmap-infographic.webp",
    )
    for name in retired:
        assert name not in readme
        assert name not in branding_doc
