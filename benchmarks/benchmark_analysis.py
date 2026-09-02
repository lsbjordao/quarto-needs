"""Reproducible performance benchmark for the Quarto-Needs semantic core.

Measures, per model size:

* parse: QMD text -> DeclarationBatch
* analyze: DeclarationBatch -> AnalysisSnapshot (validation, records,
  indexes, metrics, fingerprints, rules — the canonical pipeline)
* select_graph: bounded neighborhood projection (10 seeds, depth 2)
* rules: run_rules on the built snapshot (repeated work view)
* fingerprint: semantic graph fingerprint computation (repeated work view)

Usage:

    .venv/bin/python benchmarks/benchmark_analysis.py [--sizes 100,1000,...] \
        [--repeats 3] [--out benchmarks/results/baseline-YYYY-MM-DD.json]

Prints a human-readable table and optionally writes machine-readable JSON.
Timings are best-of-N wall clock on an otherwise idle machine; treat
absolute numbers as indicative and relative scaling as the signal.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quarto_needs.analysis import _analyze_batch  # noqa: E402
from quarto_needs.config import embedded_defaults, reference_date  # noqa: E402
from quarto_needs.fingerprints import (  # noqa: E402
    configuration_fingerprint,
    semantic_graph_fingerprint,
)
from quarto_needs.parser import parse_qmd_text_declarations  # noqa: E402
from quarto_needs.relations import DEFAULT_RELATION_CATALOG  # noqa: E402
from quarto_needs.rules import run_rules  # noqa: E402
from generate_model import SEED, generate_model_text  # noqa: E402

DEFAULT_SIZES = (100, 1_000, 10_000, 50_000)


def _best_of(repeats: int, function, *args):
    samples = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = function(*args)
        samples.append(time.perf_counter() - started)
    return min(samples), statistics.median(samples), result


def measure_size(total: int, repeats: int) -> dict[str, object]:
    model = generate_model_text(total)
    config = embedded_defaults()

    parse_best, parse_median, batch = _best_of(
        repeats, parse_qmd_text_declarations, model.text, "benchmarks/synthetic.qmd"
    )
    analyze_best, analyze_median, analysis = _best_of(
        repeats, _analyze_batch, batch, None, config
    )
    snapshot = analysis.snapshot
    assert snapshot is not None, "synthetic model must analyze cleanly"

    seeds = list(model.requirement_ids[:10])

    def run_selection():
        from quarto_needs.graph_projection import select_graph

        # Explicit budgets: the default 100/300 limits would raise by design
        # at these sizes; the selection work itself is identical.
        return select_graph(
            snapshot,
            seeds=seeds,
            depth=2,
            limits={"nodes": 10_000, "edges": 50_000},
        )

    selection_best, selection_median, _ = _best_of(repeats, run_selection)
    rules_best, rules_median, _ = _best_of(repeats, run_rules, snapshot, config)

    configuration = configuration_fingerprint(
        config, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )

    def run_fingerprint():
        return semantic_graph_fingerprint(
            snapshot.objects, snapshot.relations, configuration
        )

    fingerprint_best, fingerprint_median, _ = _best_of(repeats, run_fingerprint)

    return {
        "objects": len(snapshot.objects),
        "relations": len(snapshot.relations),
        "parse_ms": round(parse_best * 1000, 1),
        "analyze_ms": round(analyze_best * 1000, 1),
        "select_graph_ms": round(selection_best * 1000, 1),
        "rules_ms": round(rules_best * 1000, 1),
        "fingerprint_ms": round(fingerprint_best * 1000, 1),
        "medians_ms": {
            "parse": round(parse_median * 1000, 1),
            "analyze": round(analyze_median * 1000, 1),
            "select_graph": round(selection_median * 1000, 1),
            "rules": round(rules_median * 1000, 1),
            "fingerprint": round(fingerprint_median * 1000, 1),
        },
        "semantic_fingerprint": run_fingerprint(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sizes",
        type=str,
        default=",".join(str(size) for size in DEFAULT_SIZES),
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    sizes = [int(item) for item in args.sizes.split(",") if item.strip()]
    rows = [measure_size(size, args.repeats) for size in sizes]

    header = (
        f"{'size':>7} {'edges':>8} {'parse_ms':>10} {'analyze_ms':>12} "
        f"{'select_ms':>10} {'rules_ms':>10} {'fp_ms':>8}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['objects']:>7} {row['relations']:>8} {row['parse_ms']:>10} "
            f"{row['analyze_ms']:>12} {row['select_graph_ms']:>10} "
            f"{row['rules_ms']:>10} {row['fingerprint_ms']:>8}"
        )

    if args.out is not None:
        payload = {
            "generated_at": reference_date().isoformat(),
            "seed": SEED,
            "method": "best-of-N wall clock via time.perf_counter; "
            "medians included alongside",
            "environment": {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
                "machine": platform.machine(),
                "system": platform.platform(),
            },
            "results": rows,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
