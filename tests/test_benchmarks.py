"""Smoke coverage for the benchmark harness.

Deliberately not a performance gate: this only proves the deterministic
generator and the measurement pipeline run and produce sane output (spec
section 11 — no hard millisecond thresholds in ordinary CI).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BENCHMARKS = Path(__file__).resolve().parents[1] / "benchmarks"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_deterministic_generator_is_reproducible_and_complete() -> None:
    generate_model = _load("bench_generate_model", BENCHMARKS / "generate_model.py")

    first = generate_model.generate_model_text(100)
    second = generate_model.generate_model_text(100)

    assert first.text == second.text
    assert "#REQ-000000" in first.text
    assert first.relation_count > 0


def test_benchmark_measurement_pipeline_produces_sane_rows() -> None:
    generate_model = _load("bench_generate_model", BENCHMARKS / "generate_model.py")
    benchmark = _load("bench_benchmark", BENCHMARKS / "benchmark_analysis.py")

    row = benchmark.measure_size(100, repeats=1)

    expected = generate_model.generate_model_text(100).relation_count
    assert row["objects"] == 100
    assert row["relations"] == expected
    assert row["analyze_ms"] > 0
    assert row["semantic_fingerprint"]
