# Self-hosted example baselines

`quarto-needs.json` is a **historical baseline**: the engineering graph exactly
as it stood at commit `73c5ea0` — immediately *before* the Phase 6 C4 retrofit
(`19193f4`) added the system/actor/external-system/container objects and the
`part-of` hierarchy to `architecture.qmd`/`implementation.qmd`.

It is retained as a change-intelligence fixture so the interactive graph's
Changes and Impact modes (and the CLI's `diff`/`impact` commands) demonstrate a
real, truthful evolution of this very model instead of a synthetic one. It is
not the current state of the model and must not be used as a template for new
authored objects.

## Provenance and regeneration

Captured with the reference date pinned to the commit itself:

```bash
EPOCH=$(git log -1 --format=%ct 73c5ea0)
git archive 73c5ea0 examples/quarto-needs | tar -x -C /tmp/qn-hist
SOURCE_DATE_EPOCH=$EPOCH .venv/bin/quarto-needs \
  --root /tmp/qn-hist/examples/quarto-needs \
  baseline create --force --output baselines/quarto-needs.json
```

Regeneration from the same commit with the same epoch is byte-identical
(verified before committing). Advancing the baseline to a newer milestone is a
deliberate curation act: pick the commit that represents "the state before the
change you want the views to explain", regenerate the same way, and say so
here.
