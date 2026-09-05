# Runtime: baseline, diff, impact

How change is measured between two engineering-graph states (`baseline.py`, `diff.py`, `impact.py`).

## Data flow

```
AnalysisSnapshot -> fingerprint (config + ruleset version) -> baselines/quarto-needs.json

current AnalysisSnapshot ---+--> diff   -> DiffReport   -> text|json
(baseline payload)        --+--> impact -> ImpactReport -> text|json
```

## Why comparisons are guarded before they run

A baseline stores a configuration fingerprint, a ruleset version, and a reference date alongside the captured graph state. Before `diff`/`impact` inspects a single object or relation, those two values decide which categories of delta the comparison is even allowed to report. Comparing snapshots produced under different rules would otherwise report false deltas.

## Purity

`diff` and `impact` are pure functions over two snapshot values (baseline payload, current snapshot); neither touches the filesystem or Quarto. The CLI is the only layer that reads a baseline file, writes one, or prints a report — this is what makes both operations independently testable without a project on disk.

## Impact as explicit paths, not a score

`impact.py` traverses the union of the baseline and current graphs and returns explicit, auditable graph paths for what changed and what it reaches, rather than an opaque numeric risk score (`notes/ROADMAP.md` guardrail 6, "change intelligence is explainable").
