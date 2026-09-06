from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import quarto_needs

ROOT = Path(__file__).resolve().parents[1]


def extension_version(manifest: Path) -> str:
    match = re.search(r"^version:\s*(\S+)\s*$", manifest.read_text(encoding="utf-8"), re.M)
    assert match, f"{manifest} declares no version"
    return match.group(1)


def test_all_manifests_declare_the_same_version() -> None:
    """A user pairs a `quarto add` extension with a `pip install` engine.

    Those are two distributions a user updates independently, so a version they
    disagree on is a support burden that surfaces as confusing behavior rather
    than a clear error. Pin them together here, where drift is cheap to find.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packaged = pyproject["project"]["version"]
    canonical = extension_version(ROOT / "_extensions" / "quarto-needs" / "_extension.yml")

    assert quarto_needs.__version__ == packaged, (
        f"__init__ declares {quarto_needs.__version__}, pyproject declares {packaged}"
    )
    assert canonical == packaged, (
        f"the Quarto extension declares {canonical}, the package declares {packaged}"
    )


def test_the_showcase_extension_matches_the_canonical_one() -> None:
    """The example's installed copy is synchronized, never hand-edited.

    `tests/test_extension_sync.py` already compares the assets byte for byte;
    this names the version specifically, because a stale version there is what a
    reader of the showcase would see and believe.
    """
    canonical = extension_version(ROOT / "_extensions" / "quarto-needs" / "_extension.yml")
    installed = extension_version(
        ROOT
        / "examples"
        / "quarto-needs"
        / "_extensions"
        / "lsbjordao"
        / "quarto-needs"
        / "_extension.yml"
    )

    assert installed == canonical


def test_the_bootstrap_provisions_the_version_the_extension_declares(monkeypatch) -> None:
    """The managed runtime installs `quarto-needs==<extension version>`.

    Version parity stops being tidiness in the extension-first distribution
    and becomes a resolvable-install precondition: the bootstrap reads its
    own manifest to decide what to provision, so a bootstrap that read a
    different version would install an engine the extension was never tested
    against. Assert it reads what the manifest declares, and that the exact
    pin -- not a range, not `latest` -- is what it asks for.
    """
    import importlib.util

    path = ROOT / "_extensions" / "quarto-needs" / "bootstrap.py"
    spec = importlib.util.spec_from_file_location("quarto_needs_bootstrap", path)
    assert spec and spec.loader
    bootstrap = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(bootstrap)
    finally:
        sys.dont_write_bytecode = previous

    canonical = extension_version(ROOT / "_extensions" / "quarto-needs" / "_extension.yml")

    # The suite points the bootstrap at a locally built wheel so unpublished
    # engines can be provisioned; this assertion is about the default, so it
    # clears that override.
    monkeypatch.delenv("QUARTO_NEEDS_ENGINE_SOURCE", raising=False)

    assert bootstrap.extension_version() == canonical
    assert bootstrap.engine_source(canonical) == f"quarto-needs=={canonical}"


# --- Release gates (Task 9) --------------------------------------------

RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def test_the_release_workflow_exercises_the_extension_bootstrap_pre_publish() -> None:
    """Gate 5/7: not just the CLI installs -- the extension must provision too.

    The CLI-installed rehearsal proves the package itself is sound; it says
    nothing about whether the contributed bootstrap can actually provision
    that candidate with no local override, which is the path an ordinary
    Quarto user takes. Both must be exercised before a release is approved.
    """
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "Provision the published candidate through the extension bootstrap" in workflow
    assert "PIP_INDEX_URL: https://test.pypi.org/simple/" in workflow
    # No local-source override: this step proves the candidate resolves from
    # the index alone, the way a real user's render would.
    bootstrap_step = workflow.split(
        "Provision the published candidate through the extension bootstrap", 1
    )[1].split("\n\n", 1)[0]
    assert "QUARTO_NEEDS_ENGINE_SOURCE" not in bootstrap_step


def test_testpypi_cli_rehearsal_does_not_replace_the_published_package() -> None:
    """The TestPyPI gate must keep exercising the artifact it just installed."""
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    rehearse = workflow.split("rehearse:", 1)[1].split("\n  publish:", 1)[0]

    assert "Install the published CLI from TestPyPI" in rehearse
    assert '"quarto-needs==${VERSION}"' in rehearse
    assert 'importlib.metadata.version("quarto-needs")' in rehearse
    assert "./tools/check_installed_path.sh" not in rehearse


def test_the_release_workflow_verifies_the_real_published_package() -> None:
    """Gate: after production publish, prove the artifact people download works.

    Everything before this rehearses against a build or a test index. This
    is the only step that installs with no override of any kind, immediately
    after the version genuinely exists on production PyPI.
    """
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "verify-production:" in workflow
    assert "needs: publish" in workflow
    production_job = workflow.split("verify-production:", 1)[1]
    # No env: block overriding the engine source or the package index -- the
    # prose explaining that absence is fine; an actual override is not.
    assert "QUARTO_NEEDS_ENGINE_SOURCE:" not in production_job
    assert "PIP_INDEX_URL:" not in production_job
    assert "test.pypi.org" not in production_job


def test_the_release_workflow_refuses_a_tag_that_disagrees_with_the_package() -> None:
    """A release cannot even be built under a version it does not declare."""
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "Verify the tag matches the packaged version" in workflow


def test_tomli_is_declared_for_python_versions_that_need_it() -> None:
    """`config.py` and `oslc_profiles.py` fall back to `import tomli as
    tomllib` on Python < 3.11, since `tomllib` is standard library only
    from 3.11 onward. `requires-python` is ">=3.10", so that fallback is a
    real runtime path for a real supported version -- and until now `tomli`
    was not declared as a dependency anywhere, meaning `pip install
    quarto-needs` on Python 3.10 would have installed a package whose own
    config loader crashes with ModuleNotFoundError the first time it runs.

    It happened to work locally and in CI's own test collection only
    because something else transitively pulled `tomli` in; that is luck,
    not a contract.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    tomli_entries = [dep for dep in dependencies if dep.split(";")[0].strip().split(">")[0].split("=")[0].strip() == "tomli"]
    assert tomli_entries, "tomli must be declared as a dependency for Python < 3.11"
    assert "python_version" in tomli_entries[0] and "3.11" in tomli_entries[0], (
        f"tomli should be conditional on Python < 3.11, got: {tomli_entries[0]!r}"
    )
