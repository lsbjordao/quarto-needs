"""Reproducible Quarto render benchmark for the extension-first pipeline.

The core benchmarks measure the semantic core; the open render-measurement
mandate covers what an actual Quarto build costs on top of it. This
measures, per synthetic project size, rendered by the real `quarto` binary
through the real extension bootstrap (the same managed-runtime path a user
takes):

| Stage | Meaning |
| --- | --- |
| `prerender_ms` | the canonical semantic build the extension performs (`run_quarto_pre_render`) — parsing, analysis, queries, report, all canonical artifacts |
| `quarto_render_ms` | one full `quarto render --to html` wall clock, including that pre-render, Pandoc, and the Lua filters |

Sizes are deliberately small (the HTML document itself dominates the wall
clock once the model is large); the signal is the split between the
semantic build and everything Quarto adds around it.

Prerequisites: `quarto` on PATH. The engine is provisioned from this
checkout through the documented local-source override, exactly like the
rest of the repository's renders.

Usage:

    .venv/bin/python benchmarks/benchmark_render.py --sizes 100,1000 \
        [--out benchmarks/results/render-YYYY-MM-DD.json]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "benchmarks"))

import generate_model  # noqa: E402

from quarto_needs.quarto_integration import run_quarto_pre_render  # noqa: E402


def _build_project(model, root: Path) -> None:
    (root / "_extensions").mkdir(parents=True)
    shutil.copytree(REPO / "_extensions" / "quarto-needs", root / "_extensions" / "quarto-needs")
    (root / "_quarto.yml").write_text(
        "project:\n  type: default\n\nfilters:\n  - quarto-needs\n",
        encoding="utf-8",
    )
    (root / "index.qmd").write_text(
        model.text
        + "\n\n{{< need-count types=\"functional-requirement\" >}}\n\n"
        + "{{< need-table id=\"catalog\" types=\"functional-requirement\" "
        "columns=\"id;title\" >}}\n",
        encoding="utf-8",
    )


def measure_size(total: int, quarto: str | None) -> dict[str, object]:
    model = generate_model.generate_model_text(total)

    with tempfile.TemporaryDirectory(prefix="quarto-needs-render-") as tmp:
        root = Path(tmp) / "project"
        _build_project(model, root)

        started = time.perf_counter()
        status = run_quarto_pre_render(root, quiet=True)
        prerender_seconds = time.perf_counter() - started
        assert status == 0, f"pre-render failed with status {status}"

        environment = dict(os.environ)
        environment["QUARTO_NEEDS_ENGINE_SOURCE"] = str(REPO)
        command = [quarto or "quarto", "render", ".", "--to", "html"]
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            cwd=str(root),
            capture_output=True,
            text=True,
            env=environment,
            timeout=900,
        )
        render_seconds = time.perf_counter() - started
        assert completed.returncode == 0, completed.stderr[-2000:]
        html = (root / "index.html").read_text(encoding="utf-8")
        assert "need-card" in html, "the filter did not render the model"

    return {
        "objects": len(model.requirement_ids),
        "prerender_ms": round(prerender_seconds * 1000, 1),
        "quarto_render_ms": round(render_seconds * 1000, 1),
        "quarto_share_pct": round(
            100.0 * (render_seconds - prerender_seconds) / render_seconds, 1
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=str, default="100,1000")
    parser.add_argument("--quarto", type=str, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    sizes = [int(size) for size in args.sizes.split(",") if size.strip()]
    results = [measure_size(size, args.quarto) for size in sizes]

    print("objects | prerender_ms | quarto_render_ms | quarto_share_pct")
    for row in results:
        print(
            f"{row['objects']} | {row['prerender_ms']} | "
            f"{row['quarto_render_ms']} | {row['quarto_share_pct']}"
        )

    if args.out:
        payload = {
            "generator": "benchmarks/benchmark_render.py",
            "python": platform.python_version(),
            "machine": platform.machine(),
            "sizes": sizes,
            "results": results,
        }
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
