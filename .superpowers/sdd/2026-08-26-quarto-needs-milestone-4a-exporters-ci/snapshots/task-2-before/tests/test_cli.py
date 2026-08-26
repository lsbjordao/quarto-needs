from __future__ import annotations

import json
from pathlib import Path

import pytest

from quarto_needs import cli


def write_valid_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=need status=draft}\n"
        "references: REQ-2\n"
        "\n"
        "## First\n"
        "First body.\n"
        ":::\n"
        "\n"
        "::: {.need #REQ-2 type=need status=draft}\n"
        "references: TC-1\n"
        "\n"
        "## Second\n"
        "Second body.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n"
        "## Test\n"
        "Test body.\n"
        ":::\n",
        encoding="utf-8",
    )


def write_duplicate_project(root: Path) -> None:
    (root / "duplicates.qmd").write_text(
        "::: {.need #DUP-1 type=need status=draft}\n"
        "\n"
        "## First\n"
        "First body.\n"
        ":::\n"
        "\n"
        "::: {.need #DUP-1 type=need status=draft}\n"
        "\n"
        "## Second\n"
        "Second body.\n"
        ":::\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ["scan"],
        ["check"],
        ["coverage"],
        ["trace", "REQ-1"],
        ["export", "--output", "exported.json"],
    ],
    ids=["scan", "check", "coverage", "trace", "export"],
)
def test_each_command_analyzes_project_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
) -> None:
    """Calling analysis twice would rescan files and split command state."""
    write_valid_project(tmp_path)
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    assert cli.main(["--root", str(tmp_path), *arguments]) == 0
    assert calls == 1


def test_scan_delegates_to_build_without_preanalysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scan branch must reach build before any analysis in main."""
    build_calls: list[tuple[Path, bool]] = []

    def fail_preanalysis(root: Path):
        raise AssertionError(f"main pre-analyzed {root}")

    def recorded_build(root: Path, quiet: bool = False) -> int:
        build_calls.append((root, quiet))
        return 7

    monkeypatch.setattr(cli, "analyze_project", fail_preanalysis)
    monkeypatch.setattr(cli, "build", recorded_build)

    assert cli.main(["--root", str(tmp_path), "scan"]) == 7
    assert build_calls == [(tmp_path.resolve(), False)]


def test_scan_writes_both_outputs_and_keeps_legacy_stdout(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A valid scan must retain its two generated artifacts and summary."""
    write_valid_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "scan"]) == 0

    captured = capsys.readouterr()
    assert captured.out == (
        "Quarto-Needs: 3 objects, 0 findings\n"
        "Requirements: 0 | implemented: 100.0% | verified: 100.0%\n"
    )
    assert captured.err == ""
    assert json.loads(
        (tmp_path / ".quarto-needs/needs.json").read_text(encoding="utf-8")
    )["schemaVersion"] == "1"
    assert (
        tmp_path / "_extensions/quarto-needs/generated-index.lua"
    ).read_text(encoding="utf-8").startswith("return {\n")


def test_invalid_scan_reports_error_without_replacing_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Structural invalidity must not clobber either last-known-good output."""
    write_duplicate_project(tmp_path)
    graph = tmp_path / ".quarto-needs/needs.json"
    index = tmp_path / "_extensions/quarto-needs/generated-index.lua"
    graph.parent.mkdir(parents=True)
    index.parent.mkdir(parents=True)
    graph.write_text("graph sentinel\n", encoding="utf-8")
    index.write_text("index sentinel\n", encoding="utf-8")

    assert cli.main(["--root", str(tmp_path), "scan"]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "[ERROR] REQ004: Duplicate ID: DUP-1\n"
    assert graph.read_text(encoding="utf-8") == "graph sentinel\n"
    assert index.read_text(encoding="utf-8") == "index sentinel\n"


def test_quiet_invalid_build_does_not_print_or_replace_outputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Quiet build suppresses findings without weakening write safety."""
    write_duplicate_project(tmp_path)
    graph = tmp_path / ".quarto-needs/needs.json"
    index = tmp_path / "_extensions/quarto-needs/generated-index.lua"
    graph.parent.mkdir(parents=True)
    index.parent.mkdir(parents=True)
    graph.write_text("graph sentinel\n", encoding="utf-8")
    index.write_text("index sentinel\n", encoding="utf-8")

    assert cli.build(tmp_path, quiet=True) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert graph.read_text(encoding="utf-8") == "graph sentinel\n"
    assert index.read_text(encoding="utf-8") == "index sentinel\n"


def test_check_prints_structural_findings_and_legacy_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An absent snapshot must not hide check diagnostics or change its stream."""
    write_duplicate_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "check"]) == 1

    captured = capsys.readouterr()
    assert captured.out == (
        "[ERROR] REQ004: Duplicate ID: DUP-1\n"
        "Checked 2 objects: 1 errors, 0 warnings\n"
    )
    assert captured.err == ""


def test_coverage_keeps_exact_legacy_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Snapshot-backed coverage must retain the documented six-key JSON."""
    write_valid_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "coverage"]) == 0

    captured = capsys.readouterr()
    assert captured.out == (
        "{\n"
        '  "requirements": 0,\n'
        '  "approved": 0,\n'
        '  "implemented": 0,\n'
        '  "verified": 0,\n'
        '  "implementation_coverage": 100.0,\n'
        '  "verification_coverage": 100.0\n'
        "}\n"
    )
    assert captured.err == ""


@pytest.mark.parametrize(
    ("command", "sentinel_path"),
    [
        (["coverage"], None),
        (["trace", "DUP-1"], None),
        (["export", "--output", "exported.json"], "exported.json"),
    ],
    ids=["coverage", "trace", "export"],
)
def test_snapshot_consumers_report_structural_failure_to_stderr(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command: list[str],
    sentinel_path: str | None,
) -> None:
    """Commands requiring a graph must fail safely when no snapshot exists."""
    write_duplicate_project(tmp_path)
    destination = tmp_path / sentinel_path if sentinel_path is not None else None
    if destination is not None:
        destination.write_text("sentinel\n", encoding="utf-8")

    assert cli.main(["--root", str(tmp_path), *command]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "[ERROR] REQ004: Duplicate ID: DUP-1\n"
    if destination is not None:
        assert destination.read_text(encoding="utf-8") == "sentinel\n"


def test_trace_is_transitive_and_deterministically_sorted(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Trace must traverse beyond direct neighbors using snapshot indexes."""
    write_valid_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "trace", "REQ-1"]) == 0

    captured = capsys.readouterr()
    assert captured.out == (
        "Upstream:\n"
        "Downstream:\n"
        "  REQ-2\n"
        "  TC-1\n"
    )
    assert captured.err == ""


def test_trace_unknown_id_keeps_exit_two_and_error_text(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A valid snapshot with an unknown trace start remains usage failure 2."""
    write_valid_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "trace", "UNKNOWN"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Unknown object: UNKNOWN\n"


def test_export_writes_requested_graph_without_build_side_effects(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Export writes only its requested v1 artifact and remains silent."""
    write_valid_project(tmp_path)

    assert cli.main(
        ["--root", str(tmp_path), "export", "--output", "artifacts/graph.json"]
    ) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert json.loads(
        (tmp_path / "artifacts/graph.json").read_text(encoding="utf-8")
    )["schemaVersion"] == "1"
    assert not (tmp_path / "_extensions/quarto-needs/generated-index.lua").exists()


def test_export_does_not_run_legacy_object_reanalysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Export must send the existing snapshot straight to the v1 writer."""
    write_valid_project(tmp_path)

    def fail_reanalysis(*args: object, **kwargs: object) -> None:
        raise AssertionError("legacy export wrapper re-analyzed objects")

    monkeypatch.setattr("quarto_needs.export.analyze_objects", fail_reanalysis)

    assert cli.main(
        ["--root", str(tmp_path), "export", "--output", "graph.json"]
    ) == 0
    assert json.loads(
        (tmp_path / "graph.json").read_text(encoding="utf-8")
    )["schemaVersion"] == "1"


def write_quality_project(root: Path) -> None:
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=functional-requirement status=approved}\n"
        "priority: high\n"
        "rationale: Protects access.\n"
        "verified-by: TC-1\n"
        "\n"
        "## Authenticated access\n"
        "Body.\n"
        ":::\n"
        "\n"
        "::: {.need #TC-1 type=test-case status=passed}\n"
        "\n"
        "## Login test\n"
        "Body.\n"
        ":::\n",
        encoding="utf-8",
    )


def test_quality_text_reports_scopes_gates_and_exit_zero(tmp_path: Path, capsys) -> None:
    write_quality_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "quality"]) == 0
    output = capsys.readouterr().out
    assert "profile=default" in output
    assert "Scope approved-requirements: 1 requirements" in output
    assert "verification-successful: 100.0% (1/1)" in output
    assert "[PASS] max-errors" in output


def test_quality_json_round_trips(tmp_path: Path, capsys) -> None:
    write_quality_project(tmp_path)
    assert cli.main(
        ["--root", str(tmp_path), "quality", "--format", "json"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schemaVersion"] == "1"
    assert payload["scopes"]["catalog"]["denominator"] == 1
    assert payload["summary"]["exitCode"] == 0


def test_strict_gate_failure_returns_one_but_writes_artifact(tmp_path: Path) -> None:
    write_quality_project(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[gates]\nmin-evidence = 100\n',
        encoding="utf-8",
    )
    artifact = tmp_path / ".quarto-needs" / "quality.json"
    assert cli.main(
        [
            "--root",
            str(tmp_path),
            "quality",
            "--format",
            "json",
            "--output",
            ".quarto-needs/quality.json",
        ]
    ) == 1
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["summary"]["exitCode"] == 1
    evidence = next(
        gate for gate in payload["gates"] if gate["name"] == "min-evidence"
    )
    assert evidence["passed"] is False
    assert evidence["denominator"] == 1


def test_advisory_profile_reports_failures_with_exit_zero(tmp_path: Path) -> None:
    write_quality_project(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "advisory"\n[gates]\nmin-evidence = 100\n',
        encoding="utf-8",
    )
    assert cli.main(["--root", str(tmp_path), "quality"]) == 0


def test_broken_configuration_fails_fast_with_exit_two(tmp_path: Path, capsys) -> None:
    write_quality_project(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text('profle = "strict"\n', encoding="utf-8")
    assert cli.main(["--root", str(tmp_path), "check"]) == 2
    assert "profle" in capsys.readouterr().err
    assert cli.main(["--root", str(tmp_path), "scan"]) == 2


def test_structural_failure_still_reports_quality_with_exit_one(tmp_path: Path) -> None:
    write_duplicate_project(tmp_path)
    assert (
        cli.main(
            ["--root", str(tmp_path), "quality", "--format", "json"],
        )
        == 1
    )


def write_query_project(root: Path) -> None:
    (root / ".quarto-needs.toml").write_text(
        "[queries.approved-high-unverified]\n"
        "all = [\n"
        '  { field = "status", op = "eq", value = "approved" },\n'
        '  { field = "priority", op = "in", values = ["high", "critical"] },\n'
        '  { relation = "verified-by", direction = "out", op = "missing" },\n'
        "]\n",
        encoding="utf-8",
    )
    (root / "needs.qmd").write_text(
        "::: {.need #REQ-HIGH type=functional-requirement status=approved priority=high}\n"
        "\n"
        "## Unverified high requirement\n"
        ":::\n"
        "::: {.need #REQ-OK type=functional-requirement status=draft}\n"
        "\n"
        "## Draft\n"
        ":::\n",
        encoding="utf-8",
    )


def test_query_command_prints_materialized_ids(tmp_path: Path, capsys) -> None:
    write_query_project(tmp_path)
    assert (
        cli.main(["--root", str(tmp_path), "query", "approved-high-unverified"]) == 0
    )
    assert capsys.readouterr().out == "REQ-HIGH\n"


def test_query_command_json_output(tmp_path: Path, capsys) -> None:
    write_query_project(tmp_path)
    result = cli.main(
        [
            "--root",
            str(tmp_path),
            "query",
            "approved-high-unverified",
            "--format",
            "json",
        ]
    )
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"name": "approved-high-unverified", "ids": ["REQ-HIGH"]}


def test_unknown_query_name_exits_two(tmp_path: Path, capsys) -> None:
    write_query_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "query", "nope"]) == 2
    captured = capsys.readouterr()
    assert "nope" in captured.err
    assert "approved-requirements" in captured.err


def test_build_embeds_named_queries_in_extensions(tmp_path: Path) -> None:
    write_query_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "scan"]) == 0
    payload = json.loads(
        (tmp_path / ".quarto-needs/needs.json").read_text(encoding="utf-8")
    )
    queries = payload["extensions"]["quartoNeeds"]["queries"]
    assert queries["approved-requirements"] == ["REQ-HIGH"]
    assert queries["approved-high-unverified"] == ["REQ-HIGH"]


def test_build_without_config_keeps_extensions_free_of_queries(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "scan"]) == 0
    payload = json.loads(
        (tmp_path / ".quarto-needs/needs.json").read_text(encoding="utf-8")
    )
    assert "queries" not in payload["extensions"]["quartoNeeds"]


CONFIGURED_PROJECT = """profile = "strict"

[queries.approved-needs]
all = [
  { field = "status", op = "eq", value = "draft" },
]
sort = ["id:asc"]
"""


def test_build_projects_the_quality_report_for_configured_projects(
    tmp_path: Path,
) -> None:
    """The dashboard reads extensions.quartoNeeds.report, so build must write it."""
    write_valid_project(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(CONFIGURED_PROJECT, encoding="utf-8")

    assert cli.build(tmp_path, quiet=True) == 0

    graph = json.loads((tmp_path / ".quarto-needs" / "needs.json").read_text(encoding="utf-8"))
    quarto_needs = graph["extensions"]["quartoNeeds"]
    assert "approved-needs" in quarto_needs["queries"]

    report = quarto_needs["report"]
    assert report["profile"] == "strict"
    assert report["schemaVersion"] == "1"
    assert "catalog" in report["scopes"]
    # The named query becomes a report scope, so the dashboard can show it.
    assert "approved-needs" in report["scopes"]
    assert set(report["findings"]["counts"]) == {"total", "error", "warning", "info"}
    assert any(gate["name"] == "max-errors" for gate in report["gates"])


def test_build_omits_the_report_without_configuration(tmp_path: Path) -> None:
    """A project with no config keeps its byte-for-byte legacy projection."""
    write_valid_project(tmp_path)

    assert cli.build(tmp_path, quiet=True) == 0

    graph = json.loads((tmp_path / ".quarto-needs" / "needs.json").read_text(encoding="utf-8"))
    assert "report" not in graph["extensions"]["quartoNeeds"]
    assert "queries" not in graph["extensions"]["quartoNeeds"]


def test_build_projects_the_report_with_one_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Projecting the report must not re-scan the project a second time."""
    write_valid_project(tmp_path)
    (tmp_path / ".quarto-needs.toml").write_text(CONFIGURED_PROJECT, encoding="utf-8")
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    assert cli.build(tmp_path, quiet=True) == 0
    assert calls == 1


@pytest.mark.parametrize("arguments", [["check"], ["coverage"], ["export"], ["trace", "DUP-1"]])
def test_invalid_input_still_runs_exactly_one_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    """A structurally invalid project must not be re-analyzed while reporting."""
    write_duplicate_project(tmp_path)
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    cli.main(["--root", str(tmp_path), *arguments])
    assert calls == 1


def test_trace_orders_ids_case_insensitively_and_survives_cycles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Traversal must terminate on a cycle among non-start nodes and sort
    the reachable set case-insensitively.

    REQ-A (start) --references--> sub-b --references--> SUB-C
                                     ^-------references-------/

    The B<->C subcycle excludes the start node, so a `seen`-set regression
    (dropping the visited check while keeping only the `candidate != start`
    filter) would loop forever bouncing between sub-b and SUB-C. The two
    downstream ids are also cased so that a plain `sorted()` ("SUB-C" before
    "sub-b", since uppercase sorts before lowercase in ASCII) disagrees with
    the casefold-keyed order the CLI is supposed to produce ("sub-b" before
    "SUB-C").
    """
    (tmp_path / "cycle.qmd").write_text(
        "::: {.need #REQ-A type=need status=draft}\n"
        "references: sub-b\n"
        "\n## A\nA body.\n:::\n"
        "\n"
        "::: {.need #sub-b type=need status=draft}\n"
        "references: SUB-C\n"
        "\n## B\nB body.\n:::\n"
        "\n"
        "::: {.need #SUB-C type=need status=draft}\n"
        "references: sub-b\n"
        "\n## C\nC body.\n:::\n",
        encoding="utf-8",
    )

    assert cli.main(["--root", str(tmp_path), "trace", "REQ-A"]) == 0

    output = capsys.readouterr().out
    assert output == (
        "Upstream:\n"
        "Downstream:\n"
        "  sub-b\n"
        "  SUB-C\n"
    )


def test_baseline_create_writes_the_default_path_with_one_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_valid_project(tmp_path)
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
    assert calls == 1

    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
    assert payload["valid"] is True
    assert payload["schemaVersion"] == "1"


def test_baseline_create_refuses_to_clobber(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 0
    destination = tmp_path / "baselines" / "quarto-needs.json"
    sentinel = destination.read_text(encoding="utf-8")

    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 2
    assert destination.read_text(encoding="utf-8") == sentinel
    assert "--force" in capsys.readouterr().err

    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--force"]) == 0


def test_baseline_create_refuses_invalid_input_without_the_flag(
    tmp_path: Path, capsys
) -> None:
    """Structural failure must not silently become a comparison baseline."""
    write_duplicate_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "baseline", "create"]) == 1
    assert not (tmp_path / "baselines" / "quarto-needs.json").exists()
    assert "REQ004" in capsys.readouterr().err


def test_baseline_create_allow_invalid_writes_a_diagnostic_artifact(tmp_path: Path) -> None:
    write_duplicate_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"]) == 0

    payload = json.loads((tmp_path / "baselines" / "quarto-needs.json").read_text(encoding="utf-8"))
    assert payload["valid"] is False
    assert payload["declarations"]


def test_baseline_inspect_reports_both_variants(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    destination = str(tmp_path / "baselines" / "quarto-needs.json")

    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination, "--format", "json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["valid"] is True
    assert summary["objects"] == 3
    assert summary["referenceDate"]

    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", destination]) == 0
    assert "objects" in capsys.readouterr().out


def test_baseline_inspect_reports_a_missing_file_as_usage_error(tmp_path: Path) -> None:
    assert cli.main(["--root", str(tmp_path), "baseline", "inspect", str(tmp_path / "nope.json")]) == 2


def test_diff_against_an_unchanged_project_is_empty_and_exits_zero(
    tmp_path: Path, capsys
) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    destination = str(tmp_path / "baselines" / "quarto-needs.json")

    assert cli.main(["--root", str(tmp_path), "diff", destination, "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["empty"] is True
    assert payload["notices"] == []


def test_diff_validates_against_the_diff_schema(tmp_path: Path, capsys) -> None:
    from jsonschema import Draft202012Validator

    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "diff-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_diff_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")])
    assert calls == 1


def test_diff_rejects_a_diagnostic_baseline(tmp_path: Path, capsys) -> None:
    write_duplicate_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create", "--allow-invalid"])
    (tmp_path / "duplicates.qmd").unlink()
    write_valid_project(tmp_path)

    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "baselines" / "quarto-needs.json")]) == 2
    assert "diagnostic artifact" in capsys.readouterr().err


def test_diff_reports_a_missing_baseline_as_usage_error(tmp_path: Path) -> None:
    write_valid_project(tmp_path)
    assert cli.main(["--root", str(tmp_path), "diff", str(tmp_path / "absent.json")]) == 2


def test_diff_recompute_with_current_clears_notices(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    destination = tmp_path / "baselines" / "quarto-needs.json"
    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload["referenceDate"] = "1999-01-01"
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cli.main(["--root", str(tmp_path), "diff", str(destination), "--format", "json"])
    assert "reference-date-changed" in json.loads(capsys.readouterr().out)["notices"]

    cli.main([
        "--root", str(tmp_path), "diff", str(destination),
        "--recompute-with", "current", "--format", "json",
    ])
    assert json.loads(capsys.readouterr().out)["notices"] == []


def test_impact_validates_against_the_impact_schema(tmp_path: Path, capsys) -> None:
    from jsonschema import Draft202012Validator

    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    capsys.readouterr()  # flush the create command's text output before the JSON run
    (tmp_path / "needs.qmd").write_text(
        (tmp_path / "needs.qmd").read_text(encoding="utf-8").replace("First body.", "Changed body."),
        encoding="utf-8",
    )

    assert cli.main([
        "--root", str(tmp_path), "impact",
        str(tmp_path / "baselines" / "quarto-needs.json"), "--format", "json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)

    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "impact-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    assert payload["origins"]


def test_impact_runs_exactly_one_analysis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    calls = 0
    real_analyze = cli.analyze_project

    def counted(root: Path, **kwargs: object):
        nonlocal calls
        calls += 1
        return real_analyze(root, **kwargs)

    monkeypatch.setattr(cli, "analyze_project", counted)

    cli.main(["--root", str(tmp_path), "impact", str(tmp_path / "baselines" / "quarto-needs.json")])
    assert calls == 1


def test_impact_rejects_a_configuration_mismatch(tmp_path: Path, capsys) -> None:
    write_valid_project(tmp_path)
    cli.main(["--root", str(tmp_path), "baseline", "create"])
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "strict"\n[rules.REQ011]\nenabled = true\n', encoding="utf-8"
    )

    destination = str(tmp_path / "baselines" / "quarto-needs.json")
    assert cli.main(["--root", str(tmp_path), "impact", destination]) == 2
    assert "--recompute-with" in capsys.readouterr().err

    assert cli.main(["--root", str(tmp_path), "impact", destination, "--recompute-with", "current"]) == 0


def test_scan_on_an_unwritable_root_is_operational_failure(tmp_path: Path, capsys) -> None:
    """Read-only scan targets are exit 3, not a traceback."""
    import os

    (tmp_path / "needs.qmd").write_text(
        "::: {.need #REQ-1 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
    )
    target = tmp_path / "locked"
    target.mkdir()
    (target / "needs.qmd").write_text(
        "::: {.need #REQ-2 type=need status=draft}\n\n## T\nBody.\n:::\n", encoding="utf-8"
    )
    os.chmod(target, 0o500)

    try:
        assert cli.main(["--root", str(target), "scan"]) == 3
        assert "Could not" in capsys.readouterr().err
    finally:
        os.chmod(target, 0o700)


def test_export_to_an_unwritable_directory_is_operational_failure(tmp_path: Path, capsys) -> None:
    """A failed artifact write exits 3 and names the artifact."""
    import os

    write_valid_project(tmp_path)
    locked = tmp_path / "locked"
    locked.mkdir()
    os.chmod(locked, 0o500)

    try:
        destination = locked / "sub" / "needs.json"
        assert cli.main(["--root", str(tmp_path), "export", "--output", str(destination)]) == 3
        assert str(destination) in capsys.readouterr().err
    finally:
        os.chmod(locked, 0o700)
