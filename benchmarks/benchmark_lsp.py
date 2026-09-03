"""Reproducible LSP latency benchmark for the Quarto-Needs language service.

The core-stabilization phase's performance contract measured the semantic
core; editor latency was explicitly left open. This closes that gap with
the same conventions: no benchmark framework, best-of-N wall clock, one
deterministic synthetic corpus, absolute numbers indicative and relative
scaling the signal.

Per model size, over a real on-disk project (the service is root-scoped):

| Stage | Meaning |
| --- | --- |
| `lsp_load_ms` | `LanguageService.load`: full analysis from disk — the project-open / reload path |
| `lsp_diagnostics_ms` | publishing diagnostics for every object |
| `lsp_completions_ms` | completions for the prefix `REQ` across all objects |
| `lsp_hover_ms` | one hover response |
| `lsp_definition_ms` | one definition lookup |
| `lsp_references_ms` | references for the most-referenced requirement |
| `lsp_symbols_ms` | full document symbol sweep |

Usage:

    .venv/bin/python benchmarks/benchmark_lsp.py [--sizes 100,1000,10000] \
        [--repeats 3] [--out benchmarks/results/lsp-YYYY-MM-DD.json]
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import generate_model  # noqa: E402

from quarto_needs.config import embedded_defaults  # noqa: E402
from quarto_needs.language_service import LanguageService  # noqa: E402


def _best_of(repeats: int, function, *args):
    samples = []
    result = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = function(*args)
        samples.append(time.perf_counter() - started)
    return min(samples), statistics.median(samples), result


def _write_project(model, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "model.qmd").write_text(model.text, encoding="utf-8")


def measure_size(total: int, repeats: int) -> dict[str, object]:
    model = generate_model.generate_model_text(total)
    with tempfile.TemporaryDirectory(prefix="quarto-needs-lsp-") as tmp:
        root = Path(tmp) / "project"
        _write_project(model, root)

        load_best, load_median, _ = _best_of(
            repeats, LanguageService.load, root
        )
        # The remaining stages measure the interactive path: the service a
        # running editor already holds, answering requests over the snapshot.
        service = LanguageService.load(root)
        config = embedded_defaults()

        def run_diagnostics():
            return service.diagnostics()

        diagnostics_best, diagnostics_median, _ = _best_of(repeats, run_diagnostics)

        completions_best, completions_median, _ = _best_of(
            repeats, service.completions, "REQ"
        )
        first_id = model.requirement_ids[0]
        hover_best, hover_median, _ = _best_of(repeats, service.hover, first_id)
        definition_best, definition_median, _ = _best_of(
            repeats, service.definition, first_id
        )
        references_best, references_median, _ = _best_of(
            repeats, service.references, first_id
        )
        symbols_best, symbols_median, _ = _best_of(repeats, service.symbols)

    return {
        "objects": len(service.snapshot.objects),
        "relations": len(service.snapshot.relations),
        "diagnostics_published": len(run_diagnostics()),
        "lsp_load_ms": round(load_best * 1000, 1),
        "lsp_diagnostics_ms": round(diagnostics_best * 1000, 1),
        "lsp_completions_ms": round(completions_best * 1000, 1),
        "lsp_hover_ms": round(hover_best * 1000, 1),
        "lsp_definition_ms": round(definition_best * 1000, 1),
        "lsp_references_ms": round(references_best * 1000, 1),
        "lsp_symbols_ms": round(symbols_best * 1000, 1),
        "medians_ms": {
            "load": round(load_median * 1000, 1),
            "diagnostics": round(diagnostics_median * 1000, 1),
            "completions": round(completions_median * 1000, 1),
            "hover": round(hover_median * 1000, 1),
            "definition": round(definition_median * 1000, 1),
            "references": round(references_median * 1000, 1),
            "symbols": round(symbols_median * 1000, 1),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=str, default="100,1000,10000")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    sizes = [int(size) for size in args.sizes.split(",") if size.strip()]
    results = [measure_size(size, args.repeats) for size in sizes]

    headers = [
        "objects",
        "lsp_load_ms",
        "lsp_diagnostics_ms",
        "lsp_completions_ms",
        "lsp_hover_ms",
        "lsp_definition_ms",
        "lsp_references_ms",
        "lsp_symbols_ms",
    ]
    print(" | ".join(headers))
    for row in results:
        print(" | ".join(str(row[header]) for header in headers))

    if args.out:
        payload = {
            "generator": "benchmarks/benchmark_lsp.py",
            "python": platform.python_version(),
            "machine": platform.machine(),
            "sizes": sizes,
            "repeats": args.repeats,
            "results": results,
        }
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
