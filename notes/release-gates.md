# Release gates

**Status:** Phase 8 release-gate matrix. Every gate below names what it
promises, the executable evidence that keeps the promise honest, and where
that evidence runs. A gate without executable evidence is listed as open
rather than described as covered.

The rule is the repository's own: a capability is not released because it is
described, but because something runs and fails when it stops being true.
Release steps that depend on publication (PyPI, GitHub release) stay in
`.github/workflows/release.yml`; this matrix covers what can be checked in the
repository or on a release machine.

## Matrix

| Gate | Promise | Executable evidence | Runs in |
| --- | --- | --- | --- |
| Schema compatibility | Public artifacts keep their versioned contract or bump the version deliberately | [`notes/schema-compatibility.md`](schema-compatibility.md), `tests/test_schema_contracts.py` | core CI |
| Determinism | Artifacts and fingerprints are byte-identical across hash seeds, time zones, locales, working directories, source order, OS and Python | `tools/reproducibility.py`, `tests/test_reproducibility.py`, `.github/workflows/reproducibility.yml` | reproducibility workflow |
| Migrations | Four adapters converge on one plan → apply-plan → write contract, with rollback and refusal-based idempotence | `tests/test_migration_*.py`, `tests/test_sphinx_needs_migration.py`, `tests/test_doorstop_migration*.py`, `tests/test_strictdoc_migration*.py`, `tests/test_openfasttrace_migration.py` | core CI |
| Accessibility | Interactive projections stay keyboard-operable, labelled and announced | `tests/test_graph_assets.py` (focusable canvas, no `aria-hidden` contradiction), `tests/test_quarto_views.py` (labelled regions and controls in a real render), `tests/test_margin_sidebar.py` (collapsed sidebar stays hidden), `tests/test_graph_exploration_assets.py` (focus events and breadcrumbs) | core CI (static), Quarto job (rendered subset) |
| Projection security | Authored data cannot escape a published projection container (HTML, JSON, Lua, Mermaid, XML) | `tests/test_projection_security.py` (inline JSON escape, with a real render of a hostile title), `tests/test_graph_render.py` (Mermaid label escaping), `tests/test_views_helpers.py` (view-ID sanitization), `tests/test_export_*.py` (format escaping) | core CI (static), Quarto job (projection security step) |
| Performance budgets | Measured cost stays within recorded evidence plus documented headroom | `benchmarks/budgets.json`, `benchmarks/check_budgets.py`, `tests/test_benchmark_budgets.py`, `make check-performance-budgets` | core CI (budget document), release rehearsal (fresh timings) |
| Supported Python / Quarto | Every supported runtime runs the suite; the declared Quarto floor renders | `.github/workflows/ci.yml` Python 3.10–3.14 matrix, `quarto-minimum` job (`make check-release-build` covers build metadata locally) | core and quarto-minimum jobs |
| Editor compatibility | The thin VS Code client installs, type-checks, activates the extension host through the Python LSP, and packages a VSIX | `.github/workflows/ci.yml` `vscode` job (`npm run check`, `compile`, `test:extension` under xvfb, `package`, VSIX artifact), `editors/vscode/` | vscode job |
| Interoperability | Exports and federation are verified against real formats and real services | `tests/test_export_reqif.py`, `tests/test_export_jsonld.py`, `tests/test_export_sarif.py`, `tests/test_export_junit.py`, `tests/test_oslc_*.py`, `tests/test_github_*.py` | core CI |
| Self-hosted example health | The case study models the tool and passes its own strict profile and evidence gates | `make check-self-example`, `make evidence-self-example`, `make check-rendered-diagrams`, `tests/test_self_hosted_example.py` | core and Quarto jobs |

## Deliberate boundaries

- **CI asserts no timings.** Performance budgets are checked on the release
  machine through `make check-performance-budgets`; CI only proves the budget
  document agrees with the recorded evidence. This is the same stance
  `tests/test_benchmarks.py` already takes, kept deliberately.
- **Accessibility is pinned, not certified.** The tests above fail when a
  keyboard path, an accessible name or an ARIA relationship is removed. They
  are not a WCAG conformance audit; no automated browser audit is run.
- **Projection security covers the projection boundary.** Authored Markdown
  may contain raw HTML by design (Pandoc's contract); the gate is about data
  interpolated into containers the author did not write — inline JSON, view
  identifiers, Mermaid labels, export documents.
- **Publication gates are reviewer-gated.** The `pypi` environment requires a
  reviewer before an irreversible publish; `release.yml` rehearses both the
  CLI and the extension bootstrap against TestPyPI first.

## Keeping the matrix honest

When a gate gains or loses evidence, update this file in the same change. If a
gate cannot name a test, a workflow step or a command, it is open — say so
here instead of implying coverage.
