from __future__ import annotations

from pathlib import Path

import pytest


yaml = pytest.importorskip("yaml")
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_pages_site_is_assembled_from_manual_and_self_hosted_example() -> None:
    quarto = _workflow()["jobs"]["quarto"]
    steps = quarto["steps"]
    names = [step.get("name") for step in steps]

    manual = names.index("Render multilingual Quarto-Needs manual")
    diagrams = names.index("Enforce that every C4 diagram actually rendered")
    assemble = names.index("Assemble complete published site")
    preview = names.index("Upload complete site preview")
    pages = names.index("Upload GitHub Pages artifact")

    assert manual < diagrams < assemble < preview < pages

    run = steps[assemble]["run"]
    assert "cp -a docs/. pages-site/" in run
    assert "rm -rf pages-site/src" in run
    assert "cp -a examples/quarto-needs/_book/. pages-site/examples/quarto-needs/" in run
    assert "test -f pages-site/failure-gallery.html" in run
    assert "test -f pages-site/pt-BR/failure-gallery.html" in run
    assert "test -f pages-site/examples/quarto-needs/index.html" in run

    assert steps[preview]["uses"] == "actions/upload-artifact@v4"
    assert steps[preview]["with"]["path"] == "pages-site/"
    assert steps[pages]["uses"] == "actions/upload-pages-artifact@v4"
    assert steps[pages]["with"]["path"] == "pages-site/"
    assert steps[pages]["if"] == (
        "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    )


def test_pages_deploy_has_only_pages_and_oidc_write_permissions() -> None:
    jobs = _workflow()["jobs"]
    assert "publish-self-example" not in jobs

    deploy = jobs["deploy-pages"]
    assert deploy["needs"] == "quarto"
    assert deploy["if"] == (
        "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    )
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    assert deploy["environment"] == {
        "name": "github-pages",
        "url": "${{ steps.deployment.outputs.page_url }}",
    }
    assert deploy["steps"] == [
        {
            "name": "Deploy GitHub Pages",
            "id": "deployment",
            "uses": "actions/deploy-pages@v4",
        }
    ]


def test_pages_publication_never_pushes_generated_html_to_main() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: write" not in text
    assert "git push origin" not in text
    assert "docs: publish self-hosted example" not in text
