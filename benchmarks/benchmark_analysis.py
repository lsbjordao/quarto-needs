"""Reproducible performance benchmark for the Quarto-Needs semantic core.

Measures, per model size:

* parse: QMD text -> DeclarationBatch
* analyze: DeclarationBatch -> AnalysisSnapshot (validation, records,
  indexes, metrics, fingerprints, rules — the canonical pipeline)
* select_graph: bounded neighborhood projection (10 seeds, depth 2)
* rules: run_rules on the built snapshot (repeated work view)
* fingerprint: semantic graph fingerprint computation (repeated work view)
* query: one named query evaluated over the snapshot
* baseline: canonical baseline artifact construction
* diff: baseline vs current comparison with a real changed set
* impact: change-driven traversal from that same changed set
* export: canonical v1 JSON projection

`--shape` selects the corpus topology (see generate_model.SHAPES): graph
shape, not just size, is what moves traversal cost.

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

from quarto_needs import diff as diff_module  # noqa: E402
from quarto_needs import impact as impact_module  # noqa: E402
from quarto_needs.analysis import _analyze_batch  # noqa: E402
from quarto_needs.baseline import build_baseline  # noqa: E402
from quarto_needs.export import render_v1_json  # noqa: E402
from quarto_needs.config import embedded_defaults, reference_date  # noqa: E402
from quarto_needs.fingerprints import (  # noqa: E402
    configuration_fingerprint,
    semantic_graph_fingerprint,
)
from quarto_needs.parser import parse_qmd_text_declarations  # noqa: E402
from quarto_needs.queries import DEFAULT_QUERY_NAME, query_ids  # noqa: E402
from quarto_needs.relations import DEFAULT_RELATION_CATALOG  # noqa: E402
from quarto_needs.rules import run_rules  # noqa: E402
from generate_model import SEED, SHAPES, generate_model_text  # noqa: E402

DEFAULT_SIZES = (100, 1_000, 10_000, 50_000)


def _best_of(repeats: int, function, *args):
    samples = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = function(*args)
        samples.append(time.perf_counter() - started)
    return min(samples), statistics.median(samples), result


def selection_limits(snapshot) -> dict[str, int]:
    """Selection budgets that cannot abort a measurement on this snapshot."""
    return {
        "nodes": max(1, len(snapshot.objects)),
        "edges": max(1, len(snapshot.relations)),
    }


def _changed_baseline(payload: dict[str, object], stride: int = 10) -> dict[str, object]:
    """A baseline whose every *stride*-th object differs from the current one.

    Diff and impact against an identical baseline measure almost nothing:
    there is no changed set to traverse from. Perturbing the *baseline* (not
    the snapshot) keeps the current model, its fingerprints and the config
    guard intact while giving the traversal real seeds.
    """
    perturbed = dict(payload)
    objects = []
    for index, item in enumerate(payload.get("objects", [])):
        entry = dict(item)
        if index % stride == 0:
            entry["body"] = str(entry.get("body", "")) + " (baseline revision)"
        objects.append(entry)
    perturbed["objects"] = objects
    return perturbed


def measure_size(
    total: int, repeats: int, shape: str = "mixed"
) -> dict[str, object]:
    model = generate_model_text(total, shape=shape)
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

        # The default 100/300 limits would raise by design at these sizes,
        # and so would any constant: a depth-2 neighbourhood over a dense or
        # high-fanout corpus can reach the entire graph. Budget for that
        # worst case so the measurement records selection cost instead of
        # dying on its own guard rail. The selection work is identical.
        return select_graph(
            snapshot,
            seeds=seeds,
            depth=2,
            limits=selection_limits(snapshot),
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

    query_best, query_median, _ = _best_of(
        repeats, query_ids, config, snapshot, DEFAULT_QUERY_NAME
    )

    baseline_best, baseline_median, baseline_payload = _best_of(
        repeats, build_baseline, snapshot, config
    )
    changed_baseline = _changed_baseline(baseline_payload)

    diff_best, diff_median, _ = _best_of(
        repeats, diff_module.compare, changed_baseline, snapshot, config
    )
    impact_best, impact_median, _ = _best_of(
        repeats, impact_module.analyze, changed_baseline, snapshot, config
    )
    export_best, export_median, _ = _best_of(repeats, render_v1_json, snapshot)

    return {
        "shape": shape,
        "objects": len(snapshot.objects),
        "relations": len(snapshot.relations),
        "parse_ms": round(parse_best * 1000, 1),
        "analyze_ms": round(analyze_best * 1000, 1),
        "select_graph_ms": round(selection_best * 1000, 1),
        "rules_ms": round(rules_best * 1000, 1),
        "fingerprint_ms": round(fingerprint_best * 1000, 1),
        "query_ms": round(query_best * 1000, 1),
        "baseline_ms": round(baseline_best * 1000, 1),
        "diff_ms": round(diff_best * 1000, 1),
        "impact_ms": round(impact_best * 1000, 1),
        "export_ms": round(export_best * 1000, 1),
        "medians_ms": {
            "parse": round(parse_median * 1000, 1),
            "analyze": round(analyze_median * 1000, 1),
            "select_graph": round(selection_median * 1000, 1),
            "rules": round(rules_median * 1000, 1),
            "fingerprint": round(fingerprint_median * 1000, 1),
            "query": round(query_median * 1000, 1),
            "baseline": round(baseline_median * 1000, 1),
            "diff": round(diff_median * 1000, 1),
            "impact": round(impact_median * 1000, 1),
            "export": round(export_median * 1000, 1),
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
    parser.add_argument(
        "--shape",
        type=str,
        default="mixed",
        help=f"corpus topology, or 'all'; one of {', '.join(SHAPES)}",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    sizes = [int(item) for item in args.sizes.split(",") if item.strip()]
    shapes = SHAPES if args.shape == "all" else (args.shape,)
    rows = [
        measure_size(size, args.repeats, shape)
        for shape in shapes
        for size in sizes
    ]

    header = (
        f"{'shape':>11} {'size':>7} {'edges':>8} {'parse':>8} {'analyze':>9} "
        f"{'select':>8} {'rules':>8} {'fp':>7} {'query':>7} {'base':>7} "
        f"{'diff':>7} {'impact':>8} {'export':>8}"
    )
    print(header + "   (best-of-N, ms)")
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['shape']:>11} {row['objects']:>7} {row['relations']:>8} "
            f"{row['parse_ms']:>8} {row['analyze_ms']:>9} "
            f"{row['select_graph_ms']:>8} {row['rules_ms']:>8} "
            f"{row['fingerprint_ms']:>7} {row['query_ms']:>7} "
            f"{row['baseline_ms']:>7} {row['diff_ms']:>7} "
            f"{row['impact_ms']:>8} {row['export_ms']:>8}"
        )

    if args.out is not None:
        payload = {
            "generated_at": reference_date().isoformat(),
            "seed": SEED,
            "shapes": list(shapes),
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
