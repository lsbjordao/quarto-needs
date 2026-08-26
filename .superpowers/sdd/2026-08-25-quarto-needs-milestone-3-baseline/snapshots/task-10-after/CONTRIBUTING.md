# Contributing

## Development setup

```bash
make setup
source .venv/bin/activate
```

`make setup` creates `.venv` and installs the package together with its
`test` extra (`pytest`, `jsonschema`). No runtime dependency may be added
without a plan that explicitly allocates it.

## Workflow order

Every change follows strict red-green-refactor: write the failing test
first, run it to observe the intended failure, then implement the minimum
production change that turns it green, and only then refactor. A pull
request that adds production behavior without a persisted test covering it
is incomplete.

## Canonical extension location

`_extensions/quarto-needs/` at the repository root is canonical. Never edit
`examples/book/_extensions/quarto-needs/` by hand: the pre-render helper
(`tools/quarto_needs_pre_render.py`) copies every canonical asset into the
example before building the graph, and `tests/test_extension_sync.py` fails
when the two diverge. `generated-index.lua` is the one deliberate
exception — it stays project-generated instead of copied.

## Fixture policy

- `tests/fixtures/v1/aegis-needs-v1.json` is a frozen byte-for-byte capture
  of the pre-refactor graph. It is never regenerated; the compatibility
  contract tests compare current output against it.
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
make test                # full Python, Lua, and render suite
make sync-example        # synchronize extension assets and rebuild the graph
make check-example       # validate the regenerated example graph
make render-example-all  # render the example book to HTML, DOCX, and PDF
```

The example book is governed by `examples/book/.quarto-needs.toml` and runs the
`strict` profile, so it also has to keep passing its own gates:

```bash
.venv/bin/quarto-needs --root examples/book quality --format json
.venv/bin/quarto-needs --root examples/book query approved-high-unverified
```

If Quarto is installed you can also serve the book with live reload:

```bash
make preview-example
```

## Design rule

Keep requirements-engineering semantics in `src/quarto_needs`. The Quarto
extension remains an adapter concerned with authoring, navigation, and
presentation; Lua reads the projected graph and never re-implements
relation semantics owned by the Python catalog.
