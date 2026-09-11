"""The registry is only worth having if it cannot drift from the code.

Every assertion here derives the expected value from the thing being
described -- the argparse parser, the routing predicates, the constants the
routing itself matches on -- rather than from a second list maintained
beside it. A test that restated the surface would just be a seventh place to
keep in sync.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pytest

from quarto_needs import surface
from quarto_needs.cli import build_parser
from quarto_needs.git_range_cli import GIT_RANGE_COMMANDS, git_action
from quarto_needs.interchange_cli import INTERCHANGE_FORMATS, interchange_action
from quarto_needs.migration_cli import SOURCES, migration_action
from quarto_needs.oslc_cli import OSLC_ACTIONS, oslc_action
from quarto_needs.variant_cli import variant_action

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/quarto-needs"


def _subparser_paths(parser: argparse.ArgumentParser) -> set[tuple[str, ...]]:
    """Every subparser path argparse actually registers."""
    found: set[tuple[str, ...]] = set()

    def walk(current: argparse.ArgumentParser, prefix: tuple[str, ...]) -> None:
        for action in current._actions:
            if not isinstance(action, argparse._SubParsersAction):
                continue
            for name, child in action.choices.items():
                found.add(prefix + (name,))
                walk(child, prefix + (name,))

    walk(parser, ())
    return found


def _run(arguments: list[str], **environment: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), **environment}
    return subprocess.run(
        [sys.executable, "-m", "quarto_needs.cli_entry", *arguments],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=120,
    )


# --- the registry itself -------------------------------------------------

def test_every_item_declares_a_known_tier():
    for item in (*surface.COMMANDS, *surface.INTEGRATIONS):
        assert item.tier in surface.TIERS, item.name
    for fmt in surface.EXPORT_FORMATS:
        assert fmt.tier in surface.TIERS, fmt.name


def test_every_command_carries_a_one_line_summary():
    for item in surface.COMMANDS:
        assert item.summary.strip()
        assert "\n" not in item.summary


def test_a_token_with_mixed_tiers_reports_the_least_stable_one():
    # `diff` is stable against a baseline and preview against a Git range.
    # A caller invoking the word may be getting either, so the weaker promise
    # is the honest answer -- and, for the runtime warning, the safe one.
    assert {item.tier for item in surface.by_token("diff")} == {
        surface.STABLE, surface.PREVIEW
    }
    assert surface.tier_of("diff") == surface.PREVIEW
    assert surface.tier_of("scan") == surface.STABLE
    assert surface.tier_of("oslc") == surface.EXPERIMENTAL
    assert surface.tier_of("no-such-command") is None


# --- argparse must not diverge ------------------------------------------

@pytest.mark.requirement("FUN-022")
@pytest.mark.quarto_need_test_case("TC-035")
def test_argparse_subparsers_and_the_registry_are_the_same_set():
    declared = {item.path for item in surface.COMMANDS if item.layer == surface.ARGPARSE}
    assert _subparser_paths(build_parser()) == declared


def test_every_argparse_help_line_comes_from_the_registry():
    """`--help` shows the tier because the help text is the registry's."""
    parser = build_parser()
    for item in surface.COMMANDS:
        if item.layer != surface.ARGPARSE:
            continue
        assert surface.parser_help(item.path) == f"[{item.tier}] {item.summary}"
    text = parser.format_help()
    assert "[stable] Validate the requirements graph" in text
    assert "[preview] Validate machine evidence" in text


def test_export_format_choices_match_the_registry():
    export = next(
        child
        for action in build_parser()._actions
        if isinstance(action, argparse._SubParsersAction)
        for name, child in action.choices.items()
        if name == "export"
    )
    choices = next(
        action.choices for action in export._actions if action.dest == "format"
    )
    assert set(choices) == {
        fmt.name for fmt in surface.EXPORT_FORMATS if fmt.layer == surface.ARGPARSE
    }
    assert set(INTERCHANGE_FORMATS) == {
        fmt.name for fmt in surface.EXPORT_FORMATS if fmt.layer == surface.DISPATCH
    }


# --- the dispatch layer must not diverge ---------------------------------

def test_git_range_commands_match_the_registry():
    declared = {
        item.token
        for item in surface.COMMANDS
        if item.layer == surface.DISPATCH and "--git" in item.name
    }
    assert set(GIT_RANGE_COMMANDS) == declared


def test_every_dispatched_command_is_routed_by_the_real_predicates():
    """Probe the routing itself, not a list describing it."""
    probes = {
        "suspect": lambda: git_action(["suspect", "--git", "a..b"]) is not None,
        "pr-report": lambda: git_action(["pr-report", "--git", "a..b"]) is not None,
        "github-report": lambda: git_action(["github-report", "--git", "a..b"]) is not None,
        "diff": lambda: git_action(["diff", "--git", "a..b"]) is not None,
        "impact": lambda: git_action(["impact", "--git", "a..b"]) is not None,
        "variant": lambda: variant_action(["variant", "list"]) is not None,
        "export": lambda: interchange_action(["export", "--format", "reqif"]) is not None,
        "migrate": lambda: migration_action(["migrate", "doorstop"]) is not None,
        "oslc": lambda: oslc_action(["oslc", "discover"]) is not None,
    }
    dispatched = {
        item.token
        for item in surface.COMMANDS
        if item.layer == surface.DISPATCH and item.token != "lsp"
    }
    # `evidence attest` is routed inside cli_dispatch rather than cli_entry.
    dispatched.discard("evidence")
    assert dispatched == set(probes), "a dispatched command is missing from the registry"
    for token, routed in probes.items():
        assert routed(), f"{token} is declared as dispatched but nothing routes it"


def test_migration_sources_and_oslc_actions_are_named_by_the_registry():
    migrate = next(item for item in surface.COMMANDS if item.token == "migrate")
    for source in SOURCES:
        assert source in migrate.summary, source
    oslc = next(item for item in surface.COMMANDS if item.token == "oslc")
    assert oslc.name == f"oslc {'|'.join(OSLC_ACTIONS)}"


# --- the rendered help ---------------------------------------------------

def test_the_dispatch_epilog_is_rendered_not_written():
    rendered = surface.dispatched_command_help()
    for item in surface.COMMANDS:
        if item.layer == surface.DISPATCH and item.dispatched_help:
            assert item.dispatched_help in rendered
            assert item.summary in rendered
            assert f"[{item.tier}] {item.dispatched_help}" in rendered
    for tier in surface.TIERS:
        assert surface.TIER_SUMMARIES[tier] in rendered
    assert surface.SUPPRESS_WARNING_ENVIRONMENT in rendered


def test_cli_module_no_longer_holds_a_hand_written_command_list():
    """The literal that had to be edited whenever the surface moved is gone."""
    source = (ROOT / "src/quarto_needs/cli.py").read_text(encoding="utf-8")
    assert "DISPATCHED_COMMAND_HELP" not in source
    for token in ("pr-report", "github-report", "oslc discover"):
        assert token not in source, f"{token} is described in cli.py again"


# --- prose must not diverge ----------------------------------------------

@pytest.mark.parametrize("document", ["README.md", "CHANGELOG.md"])
def test_public_prose_embeds_the_generated_contract_blocks(document):
    """Generated rather than parsed: the file has to contain these lines."""
    text = (ROOT / document).read_text(encoding="utf-8")
    for tier in surface.TIERS:
        assert surface.contract_block(tier) in text, f"{document} is stale for {tier}"


def test_the_english_manual_embeds_the_generated_table_verbatim():
    text = (ROOT / "docs/src/stability.qmd").read_text(encoding="utf-8")
    assert surface.tier_table() in text, "stability.qmd is stale"


def test_the_translation_covers_every_registry_entry():
    """The pt-BR summaries are translated, so coverage is what is checked."""
    text = (ROOT / "docs/src/stability.pt-BR.qmd").read_text(encoding="utf-8")
    for item in surface.COMMANDS:
        assert item.name.replace("|", "\\|") in text, f"pt-BR omits {item.name}"
    for integration in surface.INTEGRATIONS:
        assert integration.name in text, f"pt-BR omits {integration.name}"
    for tier in surface.TIERS:
        assert tier in text


# --- the runtime warning -------------------------------------------------

def test_experimental_commands_warn_on_stderr():
    result = _run(["--root", str(EXAMPLE), "variant", "list"])
    assert "is experimental and outside the stability contract" in result.stderr
    assert "'variant'" in result.stderr
    assert result.stderr.count("is experimental") == 1, "the warning must be one line"


@pytest.mark.parametrize("arguments", [
    ["check"], ["coverage"], ["query", "architecture-decisions"],
])
def test_stable_and_preview_commands_never_warn(arguments):
    result = _run(["--root", str(EXAMPLE), *arguments])
    assert "is experimental" not in result.stderr, result.stderr


def test_help_is_not_use():
    for arguments in (["--help"], ["oslc", "--help"], ["migrate", "--help"]):
        result = _run(arguments)
        assert "is experimental and outside" not in result.stderr, arguments


def test_the_warning_is_suppressible():
    result = _run(
        ["--root", str(EXAMPLE), "variant", "list"],
        **{surface.SUPPRESS_WARNING_ENVIRONMENT: "1"},
    )
    assert "is experimental" not in result.stderr


def test_experimental_stdout_is_unchanged_by_the_warning():
    """stdout is a machine interface; the warning must not reach it."""
    warned = _run(["--root", str(EXAMPLE), "variant", "list"])
    silent = _run(
        ["--root", str(EXAMPLE), "variant", "list"],
        **{surface.SUPPRESS_WARNING_ENVIRONMENT: "1"},
    )
    assert warned.stdout == silent.stdout
    assert warned.returncode == silent.returncode == 0
    assert "experimental" not in warned.stdout


def test_every_experimental_command_warns_and_no_other_does():
    assert surface.experimental_tokens() == ("migrate", "oslc", "variant")
    for item in surface.COMMANDS:
        assert item.warns == (item.tier == surface.EXPERIMENTAL)


# --- packaging invariant (D4) --------------------------------------------

RDF_MODULES = ("rdflib", "pyld")


def test_core_operation_imports_no_rdf_or_oslc_dependency(tmp_path):
    """`pip install quarto-needs` without extras must stay RDF-free.

    Both packages are installed here through the `test` extra, so their mere
    absence would prove nothing. They are blocked at the import hook instead:
    the core path has to run with them made unavailable.
    """
    output = str(tmp_path / "needs.json")
    program = f"""
import sys

class Blocked:
    # find_spec, not find_module: the legacy hook was removed in 3.12, where
    # it would be ignored and this whole check would pass without checking.
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in {RDF_MODULES!r}:
            raise AssertionError(f'core operation imported {{name}}')
        return None

sys.meta_path.insert(0, Blocked())

# Prove the blocker blocks before trusting it to have found nothing.
for name in {RDF_MODULES!r}:
    try:
        __import__(name)
    except AssertionError:
        pass
    else:
        raise SystemExit(f'import hook did not block {{name}}')
    sys.modules.pop(name, None)

from quarto_needs.cli_entry import main
# Read-only commands only, plus an export written outside the repository:
# a test must not leave artifacts in the working tree it analyses.
for arguments in (['check'], ['coverage'], ['quality'],
                  ['export', '--format', 'json', '--output', {output!r}]):
    code = main(['--root', {str(EXAMPLE)!r}, *arguments])
    assert code == 0, (arguments, code)
for name in {RDF_MODULES!r}:
    assert name not in sys.modules, name
print('clean')
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True, text=True, encoding="utf-8", timeout=180,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "clean" in result.stdout
