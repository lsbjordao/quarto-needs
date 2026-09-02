# Core benchmarks

Reproducible performance measurements for the Quarto-Needs semantic core
(phase: `docs/superpowers/specs/2026-09-02-core-stabilization-design.md`,
section 11 — Performance contract).

## Running

```bash
.venv/bin/python benchmarks/benchmark_analysis.py
# custom sizes / output:
.venv/bin/python benchmarks/benchmark_analysis.py --sizes 100,1000,10000 --out benchmarks/results/run-$(date +%F).json
# regenerate the deterministic synthetic model:
.venv/bin/python benchmarks/generate_model.py 1000 --out /tmp/model.qmd
```

No benchmark framework is used — `time.perf_counter` best-of-N (default 3)
wall clock per stage. Medians are recorded alongside the minima in the JSON
output.

## What is measured

Per model size (deterministic synthetic model, fixed seed `20260902`,
positional IDs; requirements/tests/architecture/evidence with relations from
the derivation, implementation, verification, evidence, decomposition, and
decision-addressing families — see `generate_model.py`):

| Stage | Meaning |
| --- | --- |
| `parse_ms` | QMD text → `DeclarationBatch` (in-memory text, no disk I/O) |
| `analyze_ms` | `DeclarationBatch` → `AnalysisSnapshot`: the full canonical pipeline (validation, records, indexes, metrics, fingerprints, rules) |
| `select_graph_ms` | bounded neighborhood projection: 10 requirement seeds, depth 2 |
| `rules_ms` | `run_rules` re-run on the built snapshot |
| `fingerprint_ms` | semantic graph fingerprint re-computation |

The last two stages exist to expose what repeated work would cost consumers
(see spec section 10): if they were material relative to `analyze_ms`,
caching/indexing inside the snapshot might be justified. As of the baseline
below they are not.

## Baseline observations

Recorded 2026-09-02 (post linear-time index construction,
commit `8854a65`), JSON in
[`results/baseline-2026-09-02.json`](results/baseline-2026-09-02.json).

Environment: CPython 3.13.5, Linux 6.12 (Debian), x86_64, project `.venv`.

```text
   size    edges   parse_ms   analyze_ms  select_ms   rules_ms    fp_ms
    100      204        1.5          4.1        0.2        0.0      1.8
   1000     2049       15.1         39.6        0.7        0.1     14.7
  10000    20499      154.9        430.6        7.1        0.7    148.8
  50000   102499      887.9       2613.9       46.9        4.7    753.6
```

Reading: every stage scales linearly in graph size (10× objects → ≈10×
time; 50× objects → ≈58×). The relation-ratio is ≈2 edges per object and
stays constant across sizes. No superlinear behavior is visible after the
single-pass index construction change; no further optimization is justified
by this data.

## Limitations

* Absolute numbers are indicative only — one machine, one run date, best-of-3.
* The synthetic model exercises the structural/governance default rule set
  with no project configuration (`embedded_defaults`), no derived fields,
  and no variants; heavier configured projects shift time toward `rules_ms`.
* Parsing is measured from in-memory text; end-to-end CLI runs add disk I/O.
* CI runs no timing assertions; the only benchmark-related test
  (`tests/test_benchmarks.py`) proves the harness works at size 100.
