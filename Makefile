.PHONY: setup setup-branding setup-babelquarto test branding-assets branding-check scan check coverage render-manual-multilingual preview-self-example sync-self-example check-self-example check-rendered-diagrams evidence-self-example render-self-example install-diagram-backends check-install check-extension-first check-cli-install check-release-build
.DEFAULT_GOAL := test

VENV_PYTHON := .venv/bin/python

# Rendering an example now runs the extension's own bootstrap, which
# provisions `quarto-needs==<extension version>` from the package index.
# That version is not published, so the repository renders its examples
# against this checkout through the documented local-source override.
export QUARTO_NEEDS_ENGINE_SOURCE ?= $(CURDIR)

.venv/bin/python:
	python3 -m venv .venv

setup: .venv/bin/python
	$(VENV_PYTHON) -m pip install -e ".[test]"

setup-branding: .venv/bin/python
	$(VENV_PYTHON) -m pip install -e ".[branding]"

setup-babelquarto:
	# babelquarto itself is not on CRAN, so r-universe has to come first for
	# it specifically -- but its transitive deps (curl, fs, httr, rmarkdown,
	# bslib, sass, whoami) ARE on CRAN, and hardcoding a source-only mirror
	# for them forces every one to compile, which fails on a bare Ubuntu
	# runner missing libcurl/libuv headers. getOption("repos") carries
	# whatever CI's `setup-r` action already configured -- RSPM's
	# binary-serving mirror by default on Ubuntu -- so appending it here
	# lets the CRAN deps resolve as binaries instead of overriding that
	# with a source-only fallback.
	Rscript -e 'install.packages("babelquarto", repos=c("https://ropensci.r-universe.dev", getOption("repos")))'

test:
	$(VENV_PYTHON) -m pytest -q

branding-assets:
	$(VENV_PYTHON) tools/render_branding.py

branding-check:
	$(VENV_PYTHON) tools/render_branding.py --check

scan:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli scan

check:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli check

coverage:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli coverage

preview-self-example: render-self-example
	cd examples/quarto-needs/_book && python3 -m http.server 8001

sync-self-example:
	cd examples/quarto-needs && ../../$(VENV_PYTHON) ../../tools/quarto_needs_pre_render.py

check-self-example:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/quarto-needs check

.PHONY: quality
quality:
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli --root examples/quarto-needs quality

# The optional C4 backends fall back to a code block when their CLI is absent,
# which is right for an author and wrong for a publishing pipeline: it is how
# the published example came to show DSL source instead of diagrams.
install-diagram-backends:
	./tools/install_diagram_backends.sh

# Turns that silent fallback into a failure. It reads a rendered book, so it
# stays out of check-self-example and runs only after a render.
check-rendered-diagrams:
	$(VENV_PYTHON) tools/check_rendered_diagrams.py examples/quarto-needs/_book \
		--source examples/quarto-needs

evidence-self-example:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src $(VENV_PYTHON) -m pytest -q \
		-p quarto_needs.pytest_plugin \
		--quarto-needs-evidence=examples/quarto-needs/.quarto-needs/evidence/pytest-provider.json \
		tests/test_architecture_decisions.py::test_accepted_decision_passes_decision_governance \
		tests/test_localization.py::test_localized_source_semantic_parity_rejects_model_drift \
		tests/test_graph_semantics.py::test_public_projection_publishes_catalog_semantics \
		tests/test_graph_semantics.py::test_named_query_is_materialized_as_reusable_graph_view \
		tests/test_impact.py::test_editing_a_requirement_impacts_its_verification \
		tests/test_graph_assets.py::test_margin_sidebar_toggle_stays_entirely_outside_page_toc \
		tests/test_oslc_federation.py::test_discovery_orchestrates_fetch_normalization_service_and_shape_parsing \
		tests/test_oslc_reconcile.py::test_matching_external_identifier_never_creates_implicit_identity \
		tests/test_oslc_query.py::test_execute_oslc_query_uses_existing_bounded_fetch_and_reports_response_provenance \
		tests/test_oslc_observe.py::test_materialization_fetches_each_member_and_preserves_individual_provenance \
		tests/test_oslc_import_plan.py::test_unbound_observation_requires_explicit_create_directive \
		tests/test_github_issues.py::test_fetch_external_github_issue_composes_transport_identity_and_parsing \
		tests/test_github_issues.py::test_fetch_external_github_issue_sends_conditional_request_when_cache_is_stale \
		tests/test_github_issues.py::test_fetch_external_github_issue_list_pages_follows_rel_next_across_pages \
		tests/test_github_reconcile.py::test_github_issue_number_stays_data_even_when_it_equals_a_canonical_id \
		tests/test_github_http.py::test_fetch_github_resource_403_with_exhausted_rate_limit_is_rate_limited \
		tests/test_extension_first_distribution.py::test_a_clean_consumer_project_needs_no_engine_installation \
		tests/test_extension_first_distribution.py::test_a_second_render_succeeds_without_any_engine_source \
		tests/test_extension_first_distribution.py::test_the_project_path_may_contain_spaces \
		tests/test_extension_bootstrap.py::test_a_wrong_global_engine_never_wins_over_the_managed_runtime \
		tests/test_extension_bootstrap.py::test_a_corrupted_runtime_is_reprovisioned \
		tests/test_extension_bootstrap.py::test_two_concurrent_bootstrap_processes_produce_one_installation \
		tests/test_extension_distribution_contract.py::test_manifest_declares_the_quarto_floor \
		tests/test_cli_version.py::test_version_works_outside_a_project \
		tests/test_vacuous_gates.py::test_unknown_scope_names_valid_scopes \
		tests/test_reproducibility.py::test_subprocess_perturbations_preserve_artifacts
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli_entry --root examples/quarto-needs evidence attest \
		.quarto-needs/evidence/pytest-provider.json \
		--output .quarto-needs/evidence/pytest.json --expires-hours 24
	PYTHONPATH=src $(VENV_PYTHON) -m quarto_needs.cli_entry --root examples/quarto-needs evidence check \
		.quarto-needs/evidence/pytest.json

render-self-example: evidence-self-example
	Rscript tools/render_multilingual.R examples/quarto-needs --in-place
	$(VENV_PYTHON) tools/normalize_multilingual_output.py examples/quarto-needs/_book --locale pt-BR

render-manual-multilingual:
	Rscript tools/render_multilingual.R docs/src
	$(VENV_PYTHON) tools/normalize_multilingual_output.py docs --locale pt-BR

check-install: check-extension-first check-cli-install

# The primary user-installation scenario: an activated extension that
# provisions its own engine. No package install, no CLI on PATH.
check-extension-first:
	./tools/check_extension_first_path.sh

# The CLI-installed path, still supported for engineering and CI users.
check-cli-install:
	./tools/check_installed_path.sh

# The build and metadata checks from the release workflow, run locally:
# the plan requires every release gate to have a meaningful local path,
# because Actions availability is not a given. Upload steps stay
# workflow-only; nothing here publishes anything.
check-release-build:
	rm -rf dist
	$(VENV_PYTHON) -m build
	$(VENV_PYTHON) -m twine check dist/*
	$(VENV_PYTHON) tools/check_release_artifacts.py
