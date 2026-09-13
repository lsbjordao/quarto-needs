from __future__ import annotations

from pathlib import Path

from quarto_needs.migration_cli import SOURCES


ROOT = Path(__file__).resolve().parents[1]
RELEASE_GATES = ROOT / "notes/release-gates.md"


def test_migration_release_gate_names_every_declared_source() -> None:
    text = RELEASE_GATES.read_text(encoding="utf-8")
    migration_row = next(
        line for line in text.splitlines() if line.startswith("| Migrations |")
    )

    assert "migration_cli.SOURCES" in migration_row
    assert "Four adapters" not in migration_row
    for source in SOURCES:
        assert f"`{source}`" in migration_row, source


def test_migration_release_gate_includes_reqif_evidence() -> None:
    text = RELEASE_GATES.read_text(encoding="utf-8")
    migration_row = next(
        line for line in text.splitlines() if line.startswith("| Migrations |")
    )
    assert "tests/test_reqif_migration*.py" in migration_row
