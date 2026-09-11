from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def parsed() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_has_the_three_specified_jobs() -> None:
    jobs = parsed()["jobs"]
    assert {"core", "quarto", "quality"} <= set(jobs)


def test_core_runs_the_python_matrix() -> None:
    matrix = parsed()["jobs"]["core"]["strategy"]["matrix"]["python-version"]
    assert ["3.10", "3.11", "3.12", "3.13", "3.14"] == matrix


def test_artifacts_upload_always_and_sarif_is_least_privilege() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if: always()" in text
    assert "pull_request_target" not in text
    quality = parsed()["jobs"]["quality"]
    assert quality["permissions"] == {
        "actions": "read",
        "contents": "read",
        "security-events": "write",
    }
    steps = quality["steps"]
    upload_steps = [step for step in steps if "upload-artifact" in str(step.get("uses", ""))]
    assert upload_steps, "quality must upload artifacts"
    assert any(
        step.get("uses") == "github/codeql-action/upload-sarif@v4" for step in steps
    )


def test_quality_generates_every_export_format_and_summary() -> None:
    run_steps = [str(step.get("run", "")) for step in parsed()["jobs"]["quality"]["steps"]]
    joined = "\n".join(run_steps)
    for name in ("json", "csv", "sarif", "junit", "markdown"):
        assert f"--format {name}" in joined, name
    assert "$GITHUB_STEP_SUMMARY" in joined


def test_pull_requests_generate_git_native_change_intelligence() -> None:
    quality = parsed()["jobs"]["quality"]
    checkout = next(step for step in quality["steps"] if step.get("name") == "Check out repository")
    assert checkout["with"]["fetch-depth"] == 0

    change = next(
        step
        for step in quality["steps"]
        if step.get("name") == "Generate PR engineering change projections"
    )
    assert change["if"] == "github.event_name == 'pull_request'"
    assert change["env"] == {
        "BASE_SHA": "${{ github.event.pull_request.base.sha }}",
        "HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
    }
    run = change["run"]
    assert "pr-report --git \"$RANGE\"" in run
    assert "github-report --git \"$RANGE\"" in run
    assert "--recompute-with current" in run
    assert "--format markdown" in run
    assert "--format annotations" in run
    assert "artifacts/pr-report.json" in run
    assert "artifacts/pr-summary.md" in run
    assert "artifacts/pr-annotations.txt" in run
    assert 'cat artifacts/pr-summary.md >> "$GITHUB_STEP_SUMMARY"' in run
    assert "cat artifacts/pr-annotations.txt" in run


def test_quarto_is_pinned_to_a_stable_release() -> None:
    steps = parsed()["jobs"]["quarto"]["steps"]
    install = next(step for step in steps if step.get("name") == "Install project and test dependencies")
    setup = next(step for step in steps if "quarto-actions/setup" in str(step.get("uses", "")))
    assert install["run"] == "make setup"
    assert setup["uses"] == "quarto-dev/quarto-actions/setup@v2"
    assert setup["with"]["version"] == "1.10.18"


def test_quarto_job_gates_the_responsive_margin_sidebar_in_a_real_browser() -> None:
    steps = parsed()["jobs"]["quarto"]["steps"]
    node = next(step for step in steps if "actions/setup-node" in str(step.get("uses", "")))
    regression = next(
        step
        for step in steps
        if step.get("name") == "Test responsive margin-sidebar behavior"
    )

    assert node["with"]["node-version"] == "22"
    assert "command -v google-chrome" in regression["run"]
    assert (
        "tests/test_margin_sidebar.py::"
        "test_collapsed_margin_sidebar_stays_hidden_across_left_sidebar_breakpoint"
        in regression["run"]
    )


def test_pdf_rendering_jobs_install_tinytex() -> None:
    """`install` and `quarto-minimum` both render PDF via check_extension_first_path.sh.

    Found 2026-09-03: both failed with "No TeX installation was detected" --
    `quarto-dev/quarto-actions/setup@v2` needs `tinytex: true` explicitly,
    matching what the `quarto` job (which also renders PDF) already has.
    """
    jobs = parsed()["jobs"]
    for name in ("install", "quarto-minimum"):
        setup_steps = [
            step
            for step in jobs[name]["steps"]
            if step.get("uses", "").startswith("quarto-dev/quarto-actions/setup")
        ]
        assert setup_steps, f"{name} has no Quarto setup step"
        assert setup_steps[0]["with"].get("tinytex") is True, (
            f"{name}'s Quarto setup must install TinyTeX for its PDF render"
        )


def test_sarif_upload_does_not_fail_the_build_when_code_scanning_is_off() -> None:
    """Code scanning is a repository *setting*, not a workflow permission.

    `security-events: write` is necessary but not sufficient -- GitHub also
    requires Code scanning enabled under repo Settings -> Security, which
    only the repository owner can toggle. Until then this step's own
    findings are redundant with the quality-artifacts upload just before
    it, so failing the whole job over it is not warranted.
    """
    quality = parsed()["jobs"]["quality"]
    sarif_steps = [
        step
        for step in quality["steps"]
        if step.get("uses") == "github/codeql-action/upload-sarif@v4"
    ]
    assert sarif_steps, "quality must still attempt the SARIF upload"
    assert sarif_steps[0].get("continue-on-error") is True


def test_babelquarto_install_lets_its_cran_dependencies_resolve_as_binaries() -> None:
    """babelquarto isn't on CRAN, but its dependencies (curl, fs, httr,
    rmarkdown, bslib, sass, whoami) are. Found 2026-09-03: hardcoding
    `repos=c("https://ropensci.r-universe.dev", "https://cloud.r-project.org")`
    replaces R's session default entirely, forcing those CRAN dependencies
    through a source-only mirror -- `curl` and `fs` then fail to compile on
    a bare Ubuntu runner missing libcurl/libuv headers, cascading through
    every package that needs them.

    `getOption("repos")` carries whatever `setup-r@v2` already configured --
    Posit Package Manager's binary-serving mirror by default on Ubuntu --
    so appending it (rather than replacing R's defaults outright) lets the
    CRAN half resolve as binaries while r-universe still serves babelquarto
    itself.
    """
    makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text(
        encoding="utf-8"
    )
    target = makefile.split("setup-babelquarto:", 1)[1].split("\n\n", 1)[0]
    assert "getOption(\"repos\")" in target
    assert "https://ropensci.r-universe.dev" in target


def test_pdf_verifying_jobs_install_poppler_utils() -> None:
    """`ubuntu-latest` does not ship `pdftotext` by default; TinyTeX doesn't
    provide it either -- it's a separate system package
    (check_extension_first_path.sh uses it to assert PDF content).
    """
    jobs = parsed()["jobs"]
    for name in ("install", "quarto-minimum"):
        run_steps = "\n".join(str(step.get("run", "")) for step in jobs[name]["steps"])
        assert "poppler-utils" in run_steps, f"{name} must install poppler-utils"


def test_quarto_job_provisions_the_optional_c4_backends_before_publishing() -> None:
    """Found 2026-09-07: section 5.9 of the published example showed DSL source
    instead of diagrams. `need-c4`'s PlantUML/D2/Structurizr backends fall back
    to a code block when their CLI is missing, and this job -- whose artifact
    `publish-self-example` commits to docs/ -- installed none of them. The
    provisioning must precede the render, and the gate that catches a repeat
    must run after it and before the artifact is uploaded.
    """
    steps = parsed()["jobs"]["quarto"]["steps"]
    names = [step.get("name") for step in steps]

    install = names.index("Install optional C4 diagram backends")
    render = names.index("Render multilingual self-hosted HTML")
    gate = names.index("Enforce that every C4 diagram actually rendered")
    upload = names.index("Upload rendered self-hosted example")

    assert install < render < gate < upload
    assert "make install-diagram-backends" in steps[install]["run"]
    assert 'echo "$HOME/.local/bin" >> "$GITHUB_PATH"' in steps[install]["run"]
    assert "make check-rendered-diagrams" in steps[gate]["run"]


def test_reproducibility_matrix_has_a_blocking_aggregate():
    workflow = yaml.safe_load((WORKFLOW.parent / 'reproducibility.yml').read_text(encoding='utf-8'))
    assert {'push', 'pull_request'} <= set(workflow['on'])
    jobs = workflow['jobs']
    matrix = jobs['artifacts']['strategy']['matrix']
    assert matrix['python-version'] == ['3.10', '3.11', '3.12', '3.13', '3.14']
    assert matrix['os'] == ['ubuntu-latest', 'macos-latest', 'windows-latest']
    aggregate = jobs['reproducibility']
    assert aggregate['name'] == 'reproducibility'
    assert aggregate['needs'] == 'artifacts'
    assert aggregate['if'] == 'always()'
    assert aggregate.get('continue-on-error', False) is False
    steps = jobs['artifacts']['steps']
    assert any('locale-gen pt_BR.UTF-8' in str(step.get('run', '')) for step in steps)
    assert any('tools/reproducibility.py matrix' in str(step.get('run', '')) for step in steps)
    assert any('tools/reproducibility.py compare' in str(step.get('run', '')) for step in aggregate['steps'])


def test_ci_requires_the_collation_locale_the_suite_may_otherwise_skip():
    """`pytest -q` skips the collation axis when no locale is installed.

    That leniency is for contributors on slim images, not for CI. Without
    this assertion someone drops the variable, the seven perturbation tests
    turn green by skipping, and the axis goes silent -- a quieter version of
    the vacuous pass this project keeps hunting, because a skip is even
    easier to scroll past than a pass.
    """
    core = parsed()["jobs"]["core"]
    assert core["env"]["QUARTO_NEEDS_REQUIRE_COLLATION"] == "1"
    run_steps = "\n".join(str(step.get("run", "")) for step in core["steps"])
    assert "locale-gen pt_BR.UTF-8" in run_steps, (
        "core requires the locale, so it must provision one rather than "
        "depend on what the runner image ships"
    )

    reproducibility = yaml.safe_load(
        (WORKFLOW.parent / "reproducibility.yml").read_text(encoding="utf-8")
    )
    artifacts = reproducibility["jobs"]["artifacts"]
    assert artifacts["env"]["QUARTO_NEEDS_REQUIRE_COLLATION"] == "1"
