from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
QUICKSTART = ROOT / "notes" / "quickstart.md"
MANUAL = ROOT / "docs" / "src"


def public_sources() -> list[Path]:
    return [README, QUICKSTART, *sorted(MANUAL.glob("*.qmd"))]


def public_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in public_sources())


def test_public_docs_do_not_advertise_the_unreleased_github_cli() -> None:
    assert "quarto-needs github fetch" not in public_text()


def test_public_docs_do_not_advertise_a_nonexistent_migration_dry_run_flag() -> None:
    assert "--dry-run" not in public_text()


def test_migration_docs_never_describe_output_as_a_qmd_destination() -> None:
    migration_text = "\n".join(
        (MANUAL / name).read_text(encoding="utf-8")
        for name in ("migrations.qmd", "migrations.pt-BR.qmd")
    )
    assert not re.search(
        r"quarto-needs\s+migrate[\s\S]{0,160}?--output\s+\S+\.qmd",
        migration_text,
    )
    assert "migration-plan JSON" in migration_text
    assert "JSON do plano de migração" in migration_text
    assert "--apply-plan --write" in migration_text


def test_getting_started_documents_the_complete_extension_first_install() -> None:
    for name in ("getting-started.qmd", "getting-started.pt-BR.qmd"):
        text = (MANUAL / name).read_text(encoding="utf-8")
        assert "quarto add lsbjordao/quarto-needs" in text
        assert "filters:" in text
        assert "- quarto-needs" in text
        assert "quarto render" in text


def test_quickstart_documents_the_real_github_namespace_layout() -> None:
    text = QUICKSTART.read_text(encoding="utf-8")
    assert "_extensions/lsbjordao/quarto-needs/" in text
    assert "quarto add lsbjordao/quarto-needs" in text
    assert "filters:\n  - quarto-needs" in text


def test_interoperability_docs_show_required_oslc_query_context() -> None:
    for name in ("interoperability.qmd", "interoperability.pt-BR.qmd"):
        text = (MANUAL / name).read_text(encoding="utf-8")
        assert "quarto-needs oslc query" in text
        assert "--service-provider-uri" in text
