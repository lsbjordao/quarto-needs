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


# --- Corpus shapes (Phase 8: sparse/dense/cyclic/high-fanout) ----------------

import hashlib  # noqa: E402
import re  # noqa: E402

RELATION_LINE = re.compile(
    r"^(derives-from|implemented-by|verified-by|evidences|part-of|addresses|"
    r"refines|references|depends-on|conflicts-with):\s*(.+)$"
)

# The recorded benchmark baselines were produced from this exact corpus.
# Changing the default shape's bytes invalidates them, so it is pinned.
MIXED_100_SHA256 = "4566225cd521b58568be0fac79c3c7fabcc20afdd58111ceb1fa41fa00e3e918"


def _generator():
    return _load("bench_generate_model", BENCHMARKS / "generate_model.py")


def _count_relations(text: str) -> int:
    total = 0
    for line in text.splitlines():
        match = RELATION_LINE.match(line)
        if match:
            total += len([t for t in match.group(2).split(";") if t.strip()])
    return total


def _degrees(text: str) -> dict[str, int]:
    """In-degree per target id, straight from the emitted text."""
    degrees: dict[str, int] = {}
    for line in text.splitlines():
        match = RELATION_LINE.match(line)
        if match:
            for token in match.group(2).split(";"):
                token = token.strip()
                if token:
                    degrees[token] = degrees.get(token, 0) + 1
    return degrees


def test_default_shape_bytes_are_pinned_to_the_recorded_baseline() -> None:
    generate_model = _generator()
    text = generate_model.generate_model_text(100).text
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == MIXED_100_SHA256


def test_every_shape_is_reproducible() -> None:
    generate_model = _generator()
    for shape in generate_model.SHAPES:
        first = generate_model.generate_model_text(200, shape=shape)
        second = generate_model.generate_model_text(200, shape=shape)
        assert first.text == second.text, f"{shape} is not reproducible"


def test_every_shape_reports_the_relation_count_it_actually_emitted() -> None:
    generate_model = _generator()
    for shape in generate_model.SHAPES:
        model = generate_model.generate_model_text(200, shape=shape)
        assert model.relation_count == _count_relations(model.text), shape


def test_shapes_are_ordered_by_edge_density() -> None:
    generate_model = _generator()

    def density(shape: str) -> float:
        model = generate_model.generate_model_text(500, shape=shape)
        return model.relation_count / 500

    assert density("sparse") < density("mixed") < density("dense")


def test_high_fanout_concentrates_in_degree_far_above_the_mixed_corpus() -> None:
    generate_model = _generator()
    fanout = max(_degrees(generate_model.generate_model_text(500, shape="high-fanout").text).values())
    mixed = max(_degrees(generate_model.generate_model_text(500, shape="mixed").text).values())
    assert fanout > 10 * mixed, f"high-fanout hub degree {fanout} vs mixed {mixed}"


def test_cyclic_shape_actually_contains_a_cycle() -> None:
    generate_model = _generator()
    model = generate_model.generate_model_text(300, shape="cyclic")

    edges: dict[str, list[str]] = {}
    current: str | None = None
    for line in model.text.splitlines():
        opener = re.match(r"^::: \{\.need #([A-Za-z0-9_.:-]+)", line)
        if opener:
            current = opener.group(1)
            continue
        match = RELATION_LINE.match(line)
        if match and current is not None:
            for token in match.group(2).split(";"):
                token = token.strip()
                if token:
                    edges.setdefault(current, []).append(token)

    colour: dict[str, int] = {}

    def has_cycle(node: str) -> bool:
        colour[node] = 1
        for neighbour in edges.get(node, ()):
            state = colour.get(neighbour, 0)
            if state == 1:
                return True
            if state == 0 and has_cycle(neighbour):
                return True
        colour[node] = 2
        return False

    assert any(has_cycle(node) for node in list(edges) if colour.get(node, 0) == 0)


def test_every_shape_analyzes_into_a_snapshot() -> None:
    """A corpus that cannot analyze cannot be benchmarked.

    Structural findings (QND001/002, REQ004/005/007) block snapshot
    construction, so this fails loudly if a shape emits a dangling or
    duplicated relation endpoint.
    """
    from quarto_needs.analysis import _analyze_batch
    from quarto_needs.config import embedded_defaults
    from quarto_needs.parser import parse_qmd_text_declarations

    generate_model = _generator()
    config = embedded_defaults()

    for shape in generate_model.SHAPES:
        model = generate_model.generate_model_text(200, shape=shape)
        batch = parse_qmd_text_declarations(model.text, "benchmarks/synthetic.qmd")
        result = _analyze_batch(batch, None, config)
        assert result.snapshot is not None, (
            f"{shape} did not analyze: "
            f"{[f.code for f in result.findings][:5]}"
        )
        assert len(result.snapshot.objects) == 200, shape
        assert len(result.snapshot.relations) == model.relation_count, shape


def test_measure_size_covers_the_roadmap_operations_and_records_the_shape() -> None:
    """Phase 8 names queries, baseline/diff/impact and export as measured.

    Without these the harness cannot tell whether a bottleneck lives in the
    kernel or in the change-intelligence path built on top of it.
    """
    benchmark = _load("bench_benchmark", BENCHMARKS / "benchmark_analysis.py")

    row = benchmark.measure_size(100, repeats=1, shape="cyclic")

    assert row["shape"] == "cyclic"
    for key in (
        "parse_ms",
        "analyze_ms",
        "select_graph_ms",
        "rules_ms",
        "fingerprint_ms",
        "query_ms",
        "baseline_ms",
        "diff_ms",
        "impact_ms",
        "export_ms",
    ):
        assert key in row, f"missing measurement: {key}"
        assert isinstance(row[key], (int, float)) and row[key] >= 0, key


def test_measure_size_defaults_to_the_pinned_mixed_shape() -> None:
    benchmark = _load("bench_benchmark", BENCHMARKS / "benchmark_analysis.py")
    assert benchmark.measure_size(100, repeats=1)["shape"] == "mixed"


def test_selection_budget_never_aborts_the_measurement() -> None:
    """The benchmark must measure selection, not trip its own guard rail.

    `select_graph` raises `GraphLimitExceeded` above its budgets by design.
    A fixed budget silently turns "how fast is selection at 50k dense?" into
    a crash, so the budget has to be derived from the corpus being measured.
    """
    from quarto_needs.analysis import _analyze_batch
    from quarto_needs.config import embedded_defaults
    from quarto_needs.parser import parse_qmd_text_declarations

    benchmark = _load("bench_benchmark", BENCHMARKS / "benchmark_analysis.py")
    generate_model = _generator()

    model = generate_model.generate_model_text(2000, shape="dense")
    batch = parse_qmd_text_declarations(model.text, "b.qmd")
    snapshot = _analyze_batch(batch, None, embedded_defaults()).snapshot

    limits = benchmark.selection_limits(snapshot)

    # A depth-2 neighbourhood can reach the whole graph; the budget must
    # cover that worst case rather than a constant guessed in advance.
    assert limits["nodes"] >= len(snapshot.objects)
    assert limits["edges"] >= len(snapshot.relations)
