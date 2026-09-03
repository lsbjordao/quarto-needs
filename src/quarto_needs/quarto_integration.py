"""The canonical Quarto pre-render application service.

One semantic build operation, two callers: `quarto-needs scan` and the
extension's managed-runtime bootstrap. Both land here, so an extension-driven
render and a CLI-driven render cannot produce different artifacts -- there is
only one path that could produce them.

This module is deliberately narrow. It takes a project root and returns a
process exit status. It parses no arguments, reads no environment, and knows
nothing about how it was invoked. Everything semantic lives further in
(`analysis`, `graph_output`, `export`); everything presentational lives
further out (Lua filters, browser assets), and consumes the artifacts written
here rather than being reached back into.

Spec: docs/superpowers/specs/2026-09-02-extension-first-distribution-design.md (§7)
"""
from __future__ import annotations

import sys
from pathlib import Path

from .analysis import analyze_project
from .config import load_config
from .diagnostics import print_findings
from .export import write_build_outputs
from .queries import materialize_queries
from .quality import report_from_snapshot

# Exit statuses. These are the CLI's established `scan` contract and are part
# of what the bootstrap must reproduce, so they are named rather than spelled
# as literals at each return.
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_IO_ERROR = 3


def run_quarto_pre_render(root: Path, quiet: bool = False) -> int:
    """Analyze *root* and publish every canonical artifact Quarto consumes.

    Returns the process exit status: 0 on success, 1 when the project has
    error-severity findings or cannot produce a snapshot, 2 for a bad
    configuration, 3 for an I/O failure.
    """
    try:
        config = load_config(root)
    except ValueError as error:
        if not quiet:
            print(f"Configuration error: {error}", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR
    try:
        result = analyze_project(root, config=config)
        if result.snapshot is None:
            if not quiet:
                print_findings(result.findings, stream=sys.stderr)
            return EXIT_FINDINGS
        queries = materialize_queries(config, result.snapshot)
        # The Lua dashboard reads only what Python projects here, so a configured
        # project ships its materialized queries and its precomputed report.
        extra_extensions = (
            {
                "quartoNeeds": {
                    "queries": {name: list(queries[name]) for name in sorted(queries)},
                    "report": report_from_snapshot(
                        result.snapshot, config, queries=queries
                    ).to_dict(),
                }
            }
            if config.present
            else None
        )
        write_build_outputs(
            root / ".quarto-needs" / "needs.json",
            root / "_extensions" / "quarto-needs" / "generated-index.lua",
            result.snapshot,
            extra_extensions=extra_extensions,
        )
        from .graph_output import write_default_projection

        write_default_projection(root, result.snapshot, config)

        from .graph_output import write_c4_projections

        write_c4_projections(root, result.snapshot)
    except OSError as error:
        # Reading the project or writing either artifact failed; both are
        # operational, not validation, failures.
        print(f"Could not scan {root}: {error}", file=sys.stderr)
        return EXIT_IO_ERROR
    if not quiet:
        metrics = result.snapshot.metrics
        print(
            f"Quarto-Needs: {len(result.snapshot.objects)} objects, "
            f"{len(result.findings)} findings"
        )
        print(
            f"Requirements: {metrics['requirements']} | "
            f"implemented: {metrics['implementation_coverage']}% | "
            f"verified: {metrics['verification_coverage']}%"
        )
    return (
        EXIT_FINDINGS
        if any(f.severity == "error" for f in result.findings)
        else EXIT_OK
    )
