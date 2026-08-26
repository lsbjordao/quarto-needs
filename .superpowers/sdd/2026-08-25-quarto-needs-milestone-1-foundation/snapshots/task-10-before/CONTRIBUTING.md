# Contributing

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e . pytest
pytest -q
```

## Design rule

Keep requirements-engineering semantics in `src/quarto_needs`. The Quarto extension should remain an adapter concerned with authoring, navigation and presentation.

## Before opening a PR

```bash
pytest -q
quarto-needs scan
quarto-needs check
```

If Quarto is installed, also preview the example book:

```bash
quarto preview examples/book
```
