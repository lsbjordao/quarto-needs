# Interchange loss

The team ships a ReqIF 1.2 and a JSON-LD 1.1 projection of this project to a
downstream consumer, trusting that exporting is a round trip. It is not, and
this fixture exists to make the loss explicit instead of discoverable only by
accident.

Both projections are read-only views of the canonical graph. What they cannot
represent is *documented inside the export itself*:

- `quarto-needs export --format reqif` writes the details that stay behind as
  `PROJECTION-NOTE` entries under `TOOL-EXTENSIONS`.
- `quarto-needs export --format jsonld` records the same loss in the
  `quartoNeedsProjectionNotes` member.

## The mistake

Treating the interchange projection as lossless. The requirements scan clean
and the export succeeds — yet when the consumer later asks "where does this
requirement live in the repository?", that provenance (the authored `file:line`
of every object and relation) is not in the document.

## What the engine does

```bash
quarto-needs --root examples/broken/interchange-loss export --format reqif
quarto-needs --root examples/broken/interchange-loss export --format jsonld
```

- The project scans clean; no error findings.
- The ReqIF document's `TOOL-EXTENSIONS` section names exactly which authored
  details stay behind — object source locations (`REQ-A (index.qmd:1)`, ...)
  and relation source locations (`verified-by REQ-A -> TC-B (index.qmd:1)`,
  ...).
- The JSON-LD document carries the same documentation, because the two
  projections agree by construction about the loss.
- Attribute text itself survives the boundary: JSON-LD keeps `attributes` as
  JSON, so a consumer can distinguish "documented loss" from "silent rewrite".

Read the notes, plan around them, and treat a projection as a projection.