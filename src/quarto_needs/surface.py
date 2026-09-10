"""The declared public surface and its stability tier, in one place.

Before this module the command surface was declared in six places kept in
sync by hand: the argparse subparsers, a hand-written help string listing
what the outer dispatch layer routes, the routing itself, the README's
support contract, the CHANGELOG's release-surface section, and the manual.
A tier table maintained beside those would have been the seventh thing to
drift. So the tiers live here and everything else is rendered or verified
against this module.

Deliberately data only. It is consulted on every `--help` and on every
experimental command, and it is imported by the CLI entry point before any
work is dispatched, so it must not import feature modules or pay any
import-time cost beyond the standard library.

Tiers:

stable        Covered by SemVer. Breaking changes only in a major release.
              Documented in the manual, exercised across the full CI matrix.
preview       Functional and tested. The interface may change in a minor
              release, with a CHANGELOG entry.
experimental  May change or be removed at any time. Warns on stderr. Does
              not block a release.
"""
from __future__ import annotations

from dataclasses import dataclass

STABLE = "stable"
PREVIEW = "preview"
EXPERIMENTAL = "experimental"
TIERS = (STABLE, PREVIEW, EXPERIMENTAL)

#: Handled by the argparse parser in `cli.py`.
ARGPARSE = "argparse"
#: Intercepted by `cli_entry` before argparse ever runs.
DISPATCH = "dispatch"

TIER_SUMMARIES = {
    STABLE: "covered by SemVer; breaks only in a major release",
    PREVIEW: "tested; the interface may change in a minor release",
    EXPERIMENTAL: "may change or be removed at any time; warns on stderr",
}


@dataclass(frozen=True)
class Command:
    """One invocable command form.

    `path` is the argparse subparser path this registers, and is empty for
    dispatch-layer commands, which have no subparser. `token` is the
    top-level word the outer dispatch layer matches on, which is what the
    non-divergence tests compare against the real routing.
    """

    name: str
    tier: str
    summary: str
    layer: str
    token: str
    path: tuple[str, ...] = ()
    #: Rendered in `--help` under the dispatch-layer heading.
    dispatched_help: str = ""

    @property
    def warns(self) -> bool:
        return self.tier == EXPERIMENTAL


@dataclass(frozen=True)
class ExportFormat:
    """`export --format <name>`, whose tiers differ inside one command."""

    name: str
    tier: str
    layer: str = ARGPARSE


@dataclass(frozen=True)
class Integration:
    """Surface that is not a command: shortcodes, adapters, editor clients."""

    name: str
    tier: str
    summary: str


COMMANDS: tuple[Command, ...] = (
    # --- argparse layer -------------------------------------------------
    Command("scan", STABLE, "Parse project and write .quarto-needs/needs.json",
            ARGPARSE, "scan", ("scan",)),
    Command("check", STABLE, "Validate the requirements graph",
            ARGPARSE, "check", ("check",)),
    Command("coverage", STABLE, "Print coverage metrics",
            ARGPARSE, "coverage", ("coverage",)),
    Command("trace", STABLE, "Show upstream/downstream traceability",
            ARGPARSE, "trace", ("trace",)),
    Command("export", STABLE, "Export canonical graph JSON",
            ARGPARSE, "export", ("export",)),
    Command("quality", STABLE, "Evaluate scoped metrics, findings, and configured gates",
            ARGPARSE, "quality", ("quality",)),
    Command("query", STABLE, "Evaluate a named query and print its ordered IDs",
            ARGPARSE, "query", ("query",)),
    Command("evidence", PREVIEW, "Validate machine evidence against the engineering graph",
            ARGPARSE, "evidence", ("evidence",)),
    Command("evidence check", PREVIEW, "Check a pytest evidence artifact against the current graph",
            ARGPARSE, "evidence", ("evidence", "check")),
    Command("baseline", STABLE, "Create or inspect a canonical baseline",
            ARGPARSE, "baseline", ("baseline",)),
    Command("baseline create", STABLE, "Write a baseline for the current graph",
            ARGPARSE, "baseline", ("baseline", "create")),
    Command("baseline inspect", STABLE, "Summarize an existing baseline",
            ARGPARSE, "baseline", ("baseline", "inspect")),
    Command("diff", STABLE, "Compare a baseline against the current graph",
            ARGPARSE, "diff", ("diff",)),
    Command("impact", STABLE, "Explain what a baseline's changes reach",
            ARGPARSE, "impact", ("impact",)),
    # --- outer dispatch layer -------------------------------------------
    Command("suspect --git BASE..HEAD", PREVIEW,
            "Traceability claims needing review after a change",
            DISPATCH, "suspect",
            dispatched_help="suspect --git BASE..HEAD"),
    Command("pr-report --git BASE..HEAD", PREVIEW,
            "Combined change/impact/suspect review report",
            DISPATCH, "pr-report",
            dispatched_help="pr-report --git BASE..HEAD"),
    Command("github-report --git BASE..HEAD", PREVIEW,
            "Summary, annotations, and check projection for GitHub",
            DISPATCH, "github-report",
            dispatched_help="github-report --git BASE..HEAD"),
    Command("diff --git BASE..HEAD", PREVIEW,
            "Compare two committed Git states instead of a baseline",
            DISPATCH, "diff",
            dispatched_help="diff|impact --git BASE..HEAD"),
    Command("impact --git BASE..HEAD", PREVIEW,
            "Compare two committed Git states instead of a baseline",
            DISPATCH, "impact"),
    Command("evidence attest", PREVIEW,
            "Sign and record an evidence attestation",
            DISPATCH, "evidence"),
    Command("lsp", PREVIEW, "Run the language server over stdio",
            DISPATCH, "lsp", dispatched_help="lsp"),
    Command("export --format reqif|jsonld", PREVIEW,
            "ReqIF 1.2 and JSON-LD interchange projections",
            DISPATCH, "export",
            dispatched_help="export --format reqif|jsonld"),
    Command("variant list|show NAME", EXPERIMENTAL,
            "Inspect configured build variants",
            DISPATCH, "variant",
            dispatched_help="variant list|show NAME"),
    Command("migrate SOURCE", EXPERIMENTAL,
            "Migration plans for sphinx-needs, doorstop, strictdoc, openfasttrace",
            DISPATCH, "migrate",
            dispatched_help="migrate SOURCE"),
    Command("oslc discover|catalog|query", EXPERIMENTAL,
            "Bounded read-only OSLC RM federation",
            DISPATCH, "oslc",
            dispatched_help="oslc discover|catalog|query"),
)

EXPORT_FORMATS: tuple[ExportFormat, ...] = (
    ExportFormat("json", STABLE),
    ExportFormat("csv", STABLE),
    ExportFormat("markdown", STABLE),
    ExportFormat("sarif", PREVIEW),
    ExportFormat("junit", PREVIEW),
    # Normative validation (XSD, PyLD) and tested determinism put these close
    # to stable; the mapping surface itself may still change, so they are not.
    ExportFormat("reqif", PREVIEW, DISPATCH),
    ExportFormat("jsonld", PREVIEW, DISPATCH),
)

INTEGRATIONS: tuple[Integration, ...] = (
    Integration("Quarto pre-render", STABLE,
                "The project pre-render contributed by the Quarto extension"),
    Integration("Documented non-C4 shortcodes", STABLE,
                "need, need-table, need-graph, need-coverage and the other documented shortcodes"),
    Integration("C4 projections", EXPERIMENTAL,
                "need-c4 and its PlantUML, D2 and Structurizr backends"),
    Integration("GitHub Issues adapter", EXPERIMENTAL,
                "Reconciliation between needs and GitHub Issues"),
    Integration("VS Code client", EXPERIMENTAL,
                "The language client packaged from editors/vscode"),
)

#: Environment variable that silences the experimental runtime warning.
SUPPRESS_WARNING_ENVIRONMENT = "QUARTO_NEEDS_SUPPRESS_EXPERIMENTAL_WARNING"


def by_token(token: str) -> tuple[Command, ...]:
    return tuple(item for item in COMMANDS if item.token == token)


def tier_of(token: str) -> str | None:
    """The tier of a top-level command word, or None if it is not declared.

    A word carrying more than one tier -- `diff` is stable against a
    baseline and preview against a Git range, `export` varies by format --
    reports the least stable of them, because that is what a caller may
    actually be invoking.
    """
    tiers = {item.tier for item in by_token(token)}
    if not tiers:
        return None
    return next(tier for tier in reversed(TIERS) if tier in tiers)


def experimental_tokens() -> tuple[str, ...]:
    return tuple(sorted({item.token for item in COMMANDS if item.warns}))


def _tag(tier: str) -> str:
    return f"[{tier}]"


def parser_help(path: tuple[str, ...]) -> str:
    """The `--help` line for an argparse subparser, tier included."""
    item = next(
        entry for entry in COMMANDS if entry.layer == ARGPARSE and entry.path == path
    )
    return f"{_tag(item.tier)} {item.summary}"


def dispatched_command_help() -> str:
    """The epilog listing the commands argparse never sees.

    Rendered rather than written out. Without it `--help` would present the
    argparse group as the whole CLI and hide half of it; with it written by
    hand it was one of the six places the surface had to be kept in sync.
    """
    lines = ["", "stability tiers:"]
    width = max(len(tier) for tier in TIERS) + 2
    for tier in TIERS:
        lines.append(f"  {tier:<{width}}{TIER_SUMMARIES[tier]}")
    lines.extend(["", "commands handled by the outer dispatch layer:"])
    for item in COMMANDS:
        if item.layer != DISPATCH or not item.dispatched_help:
            continue
        lines.append(f"  {_tag(item.tier)} {item.dispatched_help}")
        lines.append(f"      {item.summary}")
    lines.extend(["", "export formats by tier:"])
    for tier in TIERS:
        names = [fmt.name for fmt in EXPORT_FORMATS if fmt.tier == tier]
        if names:
            lines.append(f"  {_tag(tier)} {'|'.join(names)}")
    lines.extend([
        "",
        "`oslc` and `migrate` subcommands accept their own --help. Experimental",
        f"commands warn on stderr; set {SUPPRESS_WARNING_ENVIRONMENT}=1 to",
        "silence that. The complete reference for every command above is the CLI",
        "reference chapter of the manual, and the Stability chapter defines the",
        "tiers.",
        "",
    ])
    return "\n".join(lines)


def tier_table() -> str:
    """The complete surface as one Markdown table.

    `docs/src/stability.qmd` embeds this verbatim, so the manual's table is
    the registry rather than a copy of it that someone has to remember to
    update. The pt-BR projection translates the summaries and is checked for
    coverage of every name instead.
    """
    def cell(value: str) -> str:
        # `variant list|show NAME` would otherwise end the table cell early.
        return value.replace("|", "\\|")

    rows = ["| Surface | Tier | Layer | Summary |", "|---|---|---|---|"]
    for item in COMMANDS:
        rows.append(f"| `{cell(item.name)}` | {item.tier} | {item.layer} | {item.summary} |")
    for fmt in EXPORT_FORMATS:
        rows.append(f"| `export --format {cell(fmt.name)}` | {fmt.tier} | {fmt.layer} | "
                    f"Export projection |")
    for item in INTEGRATIONS:
        rows.append(f"| {item.name} | {item.tier} | not a command | {item.summary} |")
    return "\n".join(rows)


def contract_block(tier: str) -> str:
    """One Markdown bullet naming every surface item in a tier.

    The README's support contract and the CHANGELOG's release-surface
    section embed these verbatim, so the prose cannot drift from the
    registry without a test noticing.
    """
    # The export formats are listed once, as one aggregate, so the dispatched
    # `export --format reqif|jsonld` entry is not repeated beside them.
    names = [
        item.name for item in COMMANDS
        if item.tier == tier and not (item.token == "export" and item.layer == DISPATCH)
    ]
    formats = [fmt.name for fmt in EXPORT_FORMATS if fmt.tier == tier]
    if formats:
        names.append(f"export --format {'|'.join(formats)}")
    rendered = [f"`{name}`" for name in names]
    # Integrations are prose, not something anyone types.
    rendered.extend(item.name for item in INTEGRATIONS if item.tier == tier)
    return f"- **{tier.capitalize()}**: {', '.join(rendered)}."
