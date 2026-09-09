# Reproduce the README screenshots

These are browser captures of real Quarto output. `dashboard.png`, `matrix.png`
and `card.png` come from the self-hosted case study; `minimal.png` comes from
[`notes/examples/readme.qmd`](../../examples/readme.qmd).

Install Playwright in a separate tooling environment, with Chrome or Chromium
available, then run from the repository root:

```bash
python -m venv /tmp/quarto-needs-capture
/tmp/quarto-needs-capture/bin/python -m pip install playwright
/tmp/quarto-needs-capture/bin/python tools/capture-screenshots.py
```

For an unpublished engine, contributors can set `QUARTO_NEEDS_ENGINE_SOURCE`
to a built wheel as documented in the contributor setup. The default command
renders the case study, renders the minimal example, starts a local HTTP server,
and captures the pages. `--browser` selects a browser executable;
`--reuse-render` reuses an unchanged case-study render when adjusting framing.

The script uses the page's own control to collapse the margin navigation.
Dashboard and matrix images are viewport excerpts; no engineering data or page
styles are rewritten for the images. Follow the README's live links for the
complete views. `captures.json` records selectors and the source graph digest.
