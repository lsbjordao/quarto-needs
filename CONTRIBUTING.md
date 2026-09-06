# Contributing

## Development setup

```bash
make setup
source .venv/bin/activate
```

`make setup` creates `.venv` and installs the package together with its
`test` extra (`pytest`, `jsonschema`, `PyYAML`). No runtime dependency may be added
without a plan that explicitly allocates it.

## Workflow order

Every change follows strict red-green-refactor: write the failing test
first, run it to observe the intended failure, then implement the minimum
production change that turns it green, and only then refactor. A pull
request that adds production behavior without a persisted test covering it
is incomplete.

## Canonical extension location

`_extensions/quarto-needs/` at the repository root is the canonical **source**.
A normal GitHub install (`quarto add lsbjordao/quarto-needs`) is owner-scoped at
`_extensions/lsbjordao/quarto-needs/`; the self-hosted example mirrors that real
consumer layout and is synchronized by `tools/quarto_needs_pre_render.py`.

The starter template is the deliberate exception: it currently vendors the
same runtime assets under `_extensions/quarto-needs/` with a template-specific
manifest. Quarto 1.10.x still has an open upstream bug copying owner-scoped
extension directories from `quarto use template`, so keeping the starter
unscoped preserves a working template without changing the public `quarto add`
contract. `tests/test_extension_sync.py` requires every non-manifest starter
asset to stay byte-for-byte equal to the canonical source.

Never edit the self-hosted example's vendored runtime by hand.
`generated-index.lua` is project-generated and therefore excluded from source
synchronization.

## Fixture policy

- `tests/fixtures/canonical/expected-needs-v1.json` and
  `expected-generated-index.lua` are reviewed goldens. If a deliberate
  output change is approved, regenerate them once with the commands from
  the Task 6 plan step, inspect the diff, and check the new bytes in.
- `tests/fixtures/query-conformance.json` is the query engine's conformance
  vector: a frozen list of query sources with their expected ordered results.
  It is the single oracle both the Python evaluator and any future non-Python
  consumer must agree with. Add cases to it when adding grammar; never edit an
  existing expectation to make a failing evaluator pass.
- `tests/fixtures/views/.quarto-needs/needs.json` is authored by hand, not
  generated. It carries the `extensions.quartoNeeds` projections (relation
  catalog, materialized queries, quality report) that the Lua views read, so
  keep it consistent with what `cli.build` would emit for the same project.
- Tests must never rewrite a golden or fixture as a side effect of
  running. A mismatch is a failure to investigate, not a file to refresh.

## Verification commands

Run the full gate before opening a PR:

```bash
make setup               # install editable package plus test extra
make test                # full test suite
make sync-self-example   # synchronize extension assets and rebuild the graph
make check-self-example  # validate the regenerated example graph
make render-self-example # render the self-hosted example to HTML
```

The `quality` CI job generates JSON, CSV, SARIF, JUnit, Markdown, and quality
report artifacts from the self-hosted example (`examples/quarto-needs`). Its
artifact upload uses `if: always()`: a policy failure still leaves the diagnostic
outputs available for review. Operational failures exit `3` and name the artifact
that could not be produced. SARIF upload is a separate least-privilege step;
workflows must never use `pull_request_target` to execute pull-request code.

The example is governed by `examples/quarto-needs/.quarto-needs.toml` and runs
the `strict` profile, so it also has to keep passing its own gates:

```bash
.venv/bin/quarto-needs --root examples/quarto-needs quality --format json
.venv/bin/quarto-needs --root examples/quarto-needs query architecture-decisions
```

If Quarto is installed you can also serve the book with live reload:

```bash
make preview-self-example
```

## Design rule

Keep requirements-engineering semantics in `src/quarto_needs`. The Quarto
extension remains an adapter concerned with authoring, navigation, and
presentation; Lua reads the projected graph and never re-implements
relation semantics owned by the Python catalog.
