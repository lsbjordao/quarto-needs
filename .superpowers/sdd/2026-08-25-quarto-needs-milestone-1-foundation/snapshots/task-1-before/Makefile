.PHONY: setup test scan check coverage example preview-example sync-example check-example render-example
.DEFAULT_GOAL := test

VENV_PYTHON := .venv/bin/python

.venv/bin/python:
	python3 -m venv .venv

setup: .venv/bin/python
	$(VENV_PYTHON) -m pip install -e . pytest

test:
	$(VENV_PYTHON) -m pytest -q

scan:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli scan

check:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli check

coverage:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli coverage

example:
	quarto preview examples/book

preview-example: example

sync-example:
	cd examples/book && ../../$(VENV_PYTHON) ../../tools/quarto_needs_pre_render.py

check-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book check

render-example:
	quarto render examples/book
