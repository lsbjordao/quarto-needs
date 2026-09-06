"""The canonical Quarto pre-render application service.

One semantic build operation, two callers: `quarto-needs scan` and the
extension's managed-runtime bootstrap. Both land here, so an extension-driven
render and a CLI-driven render cannot produce different artifacts -- there is
only one path that could produce them.

This module is deliberately narrow. It takes a project root and returns a
process exit status. Everything semantic lives further in (`analysis`,
`graph_output`, `export`); everything presentational lives further out (Lua
filters, browser assets), and consumes the artifacts written here rather than
being reached back into.

The extension entry point may set ``QUARTO_NEEDS_EXTENSION_DIR`` so build
artifacts that are consumed by Lua are written into the extension directory
that Quarto actually activated. This matters for GitHub installs, which Quarto
places under ``_extensions/<owner>/<name>``.

Contract: Phase 8B extension-first distribution.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .analysis import analyze_project
from .config import load_config
from .diagnostics import print_findings
from .export import write_build_outputs
from .queries import materialize_queries
from .quality import report_from_snapshot

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_IO_ERROR = 3


def _safe_extension_path(root: Path, path: Path) -> Path:
    """Resolve *path* and require it to stay inside this project's extensions."""
    project_root = root.resolve()
    extensions_root = (project_root / "_extensions").resolve()
    try:
        extensions_root.relative_to(project_root)
    except ValueError as error:
        raise OSError(
            f"project _extensions directory resolves outside project: {extensions_root}"
        ) from error

    candidate = path if path.is_absolute() else project_root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(extensions_root)
    except ValueError as error:
        raise OSError(
            f"active Quarto-Needs extension resolves outside project _extensions: {resolved}"
        ) from error
    return resolved


def _runtime_extension_dir(root: Path) -> Path:
    """Resolve the extension directory that consumes generated-index.lua."""
    configured = os.environ.get("QUARTO_NEEDS_EXTENSION_DIR")
    if configured:
        return _safe_extension_path(root, Path(configured).expanduser())

    # Canonical GitHub installation layout produced by
    # `quarto add lsbjordao/quarto-needs`.
    canonical = root / "_extensions" / "lsbjordao" / "quarto-needs"
    if canonical.is_dir():
        return _safe_extension_path(root, canonical)

    # Be friendly to a single namespaced fork when the standalone CLI is used
    # directly. The extension entry point remains authoritative during render.
    extensions = root / "_extensions"
    candidates = sorted(
        path for path in extensions.glob("*/quarto-needs") if path.is_dir()
    ) if extensions.is_dir() else []
    if len(candidates) == 1:
        return _safe_extension_path(root, candidates[0])

    # CLI-only and repository-development workflows historically use this
    # unnamespaced location; preserve that contract when no active extension
    # can be identified.
    return _safe_extension_path(root, root / "_extensions" / "quarto-needs")


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
            _runtime_extension_dir(root) / "generated-index.lua",
            result.snapshot,
            extra_extensions=extra_extensions,
        )
        from .graph_output import write_default_projection

        write_default_projection(root, result.snapshot, config)

        from .graph_output import write_c4_projections

        write_c4_projections(root, result.snapshot)
    except OSError as error:
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
