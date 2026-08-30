.PHONY: setup setup-babelquarto test scan check coverage example preview-example sync-example check-example render-example render-example-all render-example-multilingual render-manual-multilingual preview-self-example sync-self-example check-self-example evidence-self-example render-self-example baseline-example diff-example impact-example check-install
.DEFAULT_GOAL := test

VENV_PYTHON := .venv/bin/python
AEGIS_REFERENCE_EPOCH = $(shell $(VENV_PYTHON) -c 'import json; from datetime import datetime, timezone; value=json.load(open("examples/book/baselines/quarto-needs.json", encoding="utf-8"))["referenceDate"]; print(int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()))')

.venv/bin/python:
	python3 -m venv .venv

setup: .venv/bin/python
	$(VENV_PYTHON) -m pip install -e ".[test]"

setup-babelquarto:
	Rscript -e 'install.packages("babelquarto", repos=c("https://ropensci.r-universe.dev", "https://cloud.r-project.org"))'

test:
	$(VENV_PYTHON) -m pytest -q

scan:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli scan

check:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli check

coverage:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli coverage

example: render-example

preview-example: render-example
	cd examples/book/_book && python3 -m http.server 8000

sync-example:
	cd examples/book && ../../$(VENV_PYTHON) ../../tools/quarto_needs_pre_render.py

check-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book check

render-example:
	Rscript tools/render_multilingual.R examples/book
	$(VENV_PYTHON) tools/normalize_multilingual_output.py examples/book/_book --locale pt-BR

render-example-multilingual:
	Rscript tools/render_multilingual.R examples/book
	$(VENV_PYTHON) tools/normalize_multilingual_output.py examples/book/_book --locale pt-BR

preview-self-example: render-self-example
	cd examples/quarto-needs/_book && python3 -m http.server 8001

sync-self-example:
	cd examples/quarto-needs && ../../$(VENV_PYTHON) ../../tools/quarto_needs_pre_render.py

check-self-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/quarto-needs check

evidence-self-example:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src $(VENV_PYTHON) -m pytest -q \
		-p quarto_needs.pytest_plugin \
		--quarto-needs-evidence=examples/quarto-needs/.quarto-needs/evidence/pytest.json \
		tests/test_architecture_decisions.py::test_accepted_decision_passes_decision_governance \
		tests/test_graph_semantics.py::test_public_projection_publishes_catalog_semantics \
		tests/test_graph_semantics.py::test_named_query_is_materialized_as_reusable_graph_view \
		tests/test_impact.py::test_editing_a_requirement_impacts_its_verification
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/quarto-needs evidence check \
		.quarto-needs/evidence/pytest.json

render-self-example: evidence-self-example
	Rscript tools/render_multilingual.R examples/quarto-needs
	$(VENV_PYTHON) tools/normalize_multilingual_output.py examples/quarto-needs/_book --locale pt-BR

render-manual-multilingual:
	Rscript tools/render_multilingual.R docs/manual
	$(VENV_PYTHON) tools/normalize_multilingual_output.py docs/manual/_book --locale pt-BR

render-example-all:
	Rscript tools/render_multilingual.R examples/book
	$(VENV_PYTHON) tools/normalize_multilingual_output.py examples/book/_book --locale pt-BR
	quarto render examples/book --to docx
	quarto render examples/book --to pdf

baseline-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book baseline create --force

diff-example:
	SOURCE_DATE_EPOCH=$(AEGIS_REFERENCE_EPOCH) PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book diff examples/book/baselines/quarto-needs.json

impact-example:
	SOURCE_DATE_EPOCH=$(AEGIS_REFERENCE_EPOCH) PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/book impact examples/book/baselines/quarto-needs.json

check-install:
	./tools/check_installed_path.sh
