"""Thin CLI projection for deterministic named build variants."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .analysis import analyze_project
from .config import ConfigurationError, load_config


def variant_action(argv: Sequence[str]) -> tuple[str, str | None] | None:
    values = list(argv)
    try:
        index = values.index("variant")
    except ValueError:
        return None
    if index + 1 >= len(values):
        return None
    action = values[index + 1]
    if action == "list":
        return action, None
    if action == "show" and index + 2 < len(values):
        return action, values[index + 2]
    return None


def _format(argv: Sequence[str]) -> str:
    values = list(argv)
    try:
        index = values.index("--format")
    except ValueError:
        return "text"
    if index + 1 >= len(values):
        return "text"
    return values[index + 1]


def run_variant_action(
    root: Path,
    argv: Sequence[str],
    action: str,
    name: str | None,
) -> int:
    try:
        config = load_config(root)
        result = analyze_project(root, config=config)
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    if result.snapshot is None:
        from .cli import print_findings

        print_findings(result.findings, stream=sys.stderr)
        return 1
    snapshot = result.snapshot
    output_format = _format(argv)
    if output_format not in {"text", "json"}:
        print("variant --format must be text or json", file=sys.stderr)
        return 2

    if action == "list":
        projection = {
            "variants": [
                {"name": variant, "objects": list(ids), "count": len(ids)}
                for variant, ids in snapshot.variants.items()
            ],
            "variantFingerprint": snapshot.variant_fingerprint,
            "semanticGraphFingerprint": snapshot.semantic_graph_fingerprint,
        }
        if output_format == "json":
            print(json.dumps(projection, indent=2, sort_keys=True))
        elif not snapshot.variants:
            print("No named build variants are configured.")
        else:
            for variant, ids in snapshot.variants.items():
                print(f"{variant}: {len(ids)} object(s)")
        return 0

    assert name is not None
    ids = snapshot.variants.get(name)
    if ids is None:
        print(f"Unknown build variant: {name}", file=sys.stderr)
        return 2
    projection = {
        "name": name,
        "objects": list(ids),
        "count": len(ids),
        "variantFingerprint": snapshot.variant_fingerprint,
        "semanticGraphFingerprint": snapshot.semantic_graph_fingerprint,
    }
    if output_format == "json":
        print(json.dumps(projection, indent=2, sort_keys=True))
    else:
        print(f"Variant {name}: {len(ids)} object(s)")
        for object_id in ids:
            print(object_id)
    return 0
