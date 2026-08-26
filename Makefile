.PHONY: setup test scan check coverage example preview-example sync-example check-example render-example render-example-all baseline-example diff-example impact-example
.DEFAULT_GOAL := test

VENV_PYTHON := .venv/bin/python
AEGIS_REFERENCE_EPOCH = $(shell $(VENV_PYTHON) -c 'import json; from datetime import datetime, timezone; value=json.load(open("examples/book/baselines/quarto-needs.json", encoding="utf-8"))["referenceDate"]; print(int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()))')

.venv/bin/python:
	python3 -m venv .venv

setup: .venv/bin/python
	$(VENV_PYTHON) -m pip install -e ".[test]"

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

render-example-all:
	quarto render examples/book --to html
	quarto render examples/book --to docx
	quarto render examples/book --to pdf

baseline-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book baseline create --force

diff-example:
	SOURCE_DATE_EPOCH=$(AEGIS_REFERENCE_EPOCH) PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book diff examples/book/baselines/quarto-needs.json

impact-example:
	SOURCE_DATE_EPOCH=$(AEGIS_REFERENCE_EPOCH) PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json
