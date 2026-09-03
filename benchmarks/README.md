# Core benchmarks

Reproducible performance measurements for the Quarto-Needs semantic core
(phase: `docs/superpowers/specs/2026-09-02-core-stabilization-design.md`,
section 11 — Performance contract).

## Running

```bash
.venv/bin/python benchmarks/benchmark_analysis.py
# custom sizes / output:
.venv/bin/python benchmarks/benchmark_analysis.py --sizes 100,1000,10000 --out benchmarks/results/run-$(date +%F).json
# every corpus shape (see below):
.venv/bin/python benchmarks/benchmark_analysis.py --shape all
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
| `query_ms` | one named query (`approved-requirements`) evaluated over the snapshot |
| `baseline_ms` | canonical baseline artifact construction |
| `diff_ms` | baseline vs current comparison, against a baseline with a real changed set |
| `impact_ms` | change-driven traversal from that same changed set |
| `export_ms` | canonical v1 JSON projection |

`diff_ms` and `impact_ms` are measured against a baseline in which every
10th object differs from the current model. Comparing a snapshot with an
identical baseline measures almost nothing: there is no changed set to
traverse from, so the traversal that dominates real runs never happens.

## Corpus shapes

Size alone does not determine cost — topology does. `--shape` selects one of
five deterministic corpora that share an identical object inventory and
differ only in their relations, so any measured difference is attributable
to graph structure:

| Shape | Topology | Stresses |
| --- | --- | --- |
| `mixed` | the original corpus, ≈2 edges/object | the general case; **byte-pinned**, since the earlier baselines were recorded from it |
| `sparse` | one derivation chain, ≈0.55 edges/object | the floor: how much cost is per-object rather than per-edge |
| `dense` | wide stride-based cross-linking, ≈4.2 edges/object | edge-dominated work |
| `cyclic` | derivation rings of 8 | cycle detection, which cannot terminate early, and cycle canonicalization |
| `high-fanout` | every requirement points at one hub component/test | in-degree concentration in neighborhood selection and impact traversal |

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

## Profiling consumers of repeated derivation (spec section 10)

Measured 2026-09-02 on the 50k-object model (102k relations), 5 changed
requirements as impact origins:

* `select_graph` (depth 2, 10 seeds): ~47 ms — consumes snapshot indexes;
  not material.
* `run_rules` re-run: ~5 ms — snapshot-native already; not material.
* `diff` (baseline vs current, recompute): ~2.7 s.
* `impact --recompute-with current` (5 origins, distance ≤ 10): 3.94 s
  before / **2.86 s after** removing one duplicated baseline-relation
  recomputation (the stored baseline relations were re-resolved through the
  current catalog once inside `diff.compare` and again to build the
  traversal adjacency; `impact.analyze` now re-resolves once and hands the
  list to both). Identical output (290 impacted objects).
* `suspect`: inherits the same win (it derives from the impact report).

The remaining cost is one-pass inherent work (one recomputation, one
current-side fingerprint pass, one classification). No caches were added;
no snapshot-level adjacency/family indexes were introduced — the measured
consumers either already use the canonical indexes or pay a single O(V+E)
pass per user-invoked operation.

## Shape observations

Recorded 2026-09-03, best-of-3, JSON in
[`results/shapes-2026-09-03.json`](results/shapes-2026-09-03.json).
Same environment as above.

```text
      shape    size    edges    parse   analyze   select   query     diff   impact   export
      mixed   10000    20499    162.3     434.6      6.7     8.8    290.9    543.6    168.3
high-fanout   10000    19999    161.8     447.2     21.1     8.3    283.7    591.0    164.1
      mixed   50000   102499    855.3    2624.6     49.6    49.5   1886.4   2947.2    872.4
high-fanout   50000    99999    952.4    2739.5    135.7    44.9   1675.7   2940.8    898.3
```

Two readings, and one of them is the point of having shapes at all:

1. **Everything scales linearly in graph size, in every shape.** From 10k to
   50k objects (5× objects, ≈5× edges) the pipeline stages grow ≈5-7×:
   `analyze` 6.0×, `impact` 5.4×, `query` 5.6× on the mixed corpus, with the
   same pattern in all five. Nothing is superlinear.

2. **Neighborhood selection is shape-sensitive at constant size.** At 10k
   objects, `high-fanout` costs **3.1× mixed** for `select_graph` (21.1 ms vs
   6.7 ms) while having *fewer* edges (19,999 vs 20,499); at 50k the ratio
   holds at 2.7×. In-degree concentration, not edge count, drives bounded
   selection cost. A single mixed corpus could not have shown this, and it
   is why the roadmap asks for these four shapes rather than four sizes.

The second reading is a documented characteristic, not a bottleneck: it is a
constant-factor effect that stays linear in size, and `select_graph`'s
absolute cost (136 ms at 50k, the worst shape) is two orders of magnitude
below `analyze`. **Per the phase rule — caching and incrementality are
introduced only when benchmarks identify a real bottleneck — this data
licenses no such work.** Withholding it is the finding.

## Limitations

* Absolute numbers are indicative only — one machine, one run date, best-of-3.
* The synthetic model exercises the structural/governance default rule set
  with no project configuration (`embedded_defaults`), no derived fields,
  and no variants; heavier configured projects shift time toward `rules_ms`.
* Parsing is measured from in-memory text; end-to-end CLI runs add disk I/O.
* CI runs no timing assertions; `tests/test_benchmarks.py` proves the
  harness and every corpus shape work, and pins the `mixed` corpus bytes —
  it asserts no timings.
* The roadmap also names LSP latency and Quarto rendering as Phase 8
  measurement targets. Neither is covered here: both are process-boundary
  measurements needing a different harness, and they remain open.
* Shapes vary topology at a fixed object-type mix; they do not vary the
  configured rule set, derived fields, or variants.
