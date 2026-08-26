# Quarto-Needs

Quarto-Needs is an experimental **requirements-as-code** engine and Quarto extension. It turns traceable engineering objects declared in `.qmd` files into a canonical requirements graph, validates references, computes coverage, and exposes the graph back to Quarto for navigable documentation.

> Status: MVP / architecture seed. The core is intentionally independent from the Quarto rendering layer.

## Architecture

```text
.qmd / code / tests
       |
       v
Quarto-Needs Core
 parser -> model -> graph -> validation/query
       |
       +--> .quarto-needs/needs.json
       |
       +--> Quarto extension -> HTML/PDF/DOCX
```

The canonical model is a property graph of engineering objects and typed relations. Quarto is an authoring and publishing adapter, not the source of business logic.

## Repository layout

```text
src/quarto_needs/              Core engine
_extensions/quarto-needs/     Quarto filter + shortcode
schemas/                       Canonical JSON Schema seed
tools/                         Zero-install pre-render entrypoint
examples/book/                 Example Quarto Book
tests/                         Unit tests
.github/workflows/             CI seed
```

## Quick start

### 1. Install the CLI for development

```bash
make setup
source .venv/bin/activate
```

### 2. Run tests

```bash
make test
```

### 3. Build the canonical graph

```bash
quarto-needs scan
```

This writes:

```text
.quarto-needs/needs.json
```

### 4. Validate

```bash
quarto-needs check
quarto-needs coverage
quarto-needs trace SYS-REQ-042
```

### 5. Preview the example book

From the repository root:

```bash
make preview-example
```

The example uses a Quarto pre-render script. Quarto supports project `pre-render` hooks, which makes the canonical graph available before Pandoc renders pages.

## Authoring syntax

The working MVP syntax uses native Pandoc Div attributes, which remain structured in the AST:

```qmd
::: {.need #SYS-REQ-042 type="system-requirement" status="approved" priority="high" derived-from="STK-NEED-003" verified-by="TC-AUTH-012"}
## Authentication

The system shall authenticate the user before allowing access to private data.

### Rationale
Authentication protects private data from unauthorized access.
:::
```

The Python parser also contains the initial machinery for the YAML-like preamble proposed in the design document. Richer YAML parsing, multiline values, relation attributes, and schema-driven authoring are planned next.

## Cross references

Use the bundled shortcode:

```qmd
{{< need SYS-REQ-042 >}}
{{< need SYS-REQ-042 title=true >}}
```

`need` resolves IDs through the cached canonical graph. During pre-render the
engine still writes `generated-index.lua` for external consumers, but the
bundled shortcodes no longer read it at runtime.

In HTML the link points at the page that declares the need, relative to the
page being rendered — `nested/details.html#TC-LOGIN` from the index, and
`../index.html#REQ-APPROVED` from a nested page. DOCX and PDF are single
documents, so every link there is anchor-only (`#TC-LOGIN`). An unknown ID
never becomes a broken link: it renders as `need-ref-missing` text and logs a
warning.

## Generated views

The extension reads the canonical `.quarto-needs/needs.json` graph during a
Quarto render. It provides six graph-backed view shortcodes in addition to
the `need` cross reference:

```qmd
{{< need-table types="functional-requirement;non-functional-requirement" status="approved" columns="id;title;status;priority;verified-by" sort="priority;id" caption="Approved requirements" >}}

{{< need-list tags="authentication" show="status;priority" >}}

{{< need-count types="system-requirement" status="approved" >}}

{{< need-matrix rows="functional-requirement" columns="test-case" relation="verified-by" >}}

{{< need-flow root="IAM-STK-001" depth="4" relations="derives-from;implemented-by;verified-by" direction="LR" >}}

{{< need-backlinks IAM-SYS-001 >}}
```

`need-table` renders a linked table; with no filters it includes every
engineering object. `need-list` renders linked IDs and titles, and
`need-count` renders the number of matches. `need-matrix` shows whether a
configured relation connects each row type to each column type. `need-flow`
emits a Mermaid relation graph rooted at an object (or a bounded graph when no
root is supplied). `need-backlinks` lists every relation that points *at* the
given need, grouped under the catalog's inverse label. A need with no incoming
relation renders the explicit empty state `No backlinks for <ID>.`; an unknown
ID renders a `need-view-warning` reading `Unknown need ID: <ID>` and logs the
same message, so a typo is never mistaken for an empty result. Omitting the ID
warns with `Missing need ID for need-backlinks.`.

## Relations on need cards

Every `.need` card gains up to two static sections built from the emitted
relation catalog:

- **Need relations** — outgoing edges, grouped by the catalog `directLabel`
  (`Verified by`, `Implemented by`, `Derives from`, …);
- **Need backlinks** — incoming edges, grouped by the catalog `inverseLabel`
  (`Verifies`, `Implements`, `Source for`, …).

Groups sort case-insensitively by label and entries sort by the opposite
endpoint ID. A card with no relation in a direction shows no heading for it.
Both sections are ordinary Pandoc blocks, so the same labels, IDs, and titles
appear in HTML, DOCX, and PDF without any JavaScript. An endpoint missing from
the graph is printed as plain text marked `need-relation-missing` — never as an
invented link.

All views use the same deterministic filters: `ids`, `types` (or `type`),
`status`, `priority`, and `tags`. Commas and semicolons separate alternatives;
alternatives within one field are OR-ed, while fields are AND-ed. Matching is
case-insensitive and tags may be either a delimited scalar or a list. `sort`
accepts comma/semicolon-separated fields; priority sorts as `critical`,
`high`, `medium`, `low`, then unspecified. Unknown table columns are empty,
rather than build errors.

Status and priority are separate, text-bearing badges. Status values
`approved`/`passed`, `disapproved`/`rejected`/`failed`, `in-review`, `draft`,
`implemented`, `verified`, and `deprecated` map to semantic status badges.
Priority values `critical`, `high`, `medium`, and `low` map to semantic
priority badges. Their labels remain visible when color is unavailable — every
badge carries text, so color is never the only cue.

| Value | Color |
|---|---|
| `approved`, `passed` | green |
| `disapproved`, `rejected`, `failed` | red |
| `in-review` | amber |
| `draft` | gray |
| `implemented` | blue |
| `verified` | teal |
| `critical` | dark red |
| `high` | orange |
| `medium` | blue |
| `low` | gray |

### Repeatable example checks

From the repository root, these commands install the toolchain, verify it, and
regenerate every example artifact:

```bash
make setup               # create .venv and install the package with its test extra
make test                # run the full Python, Lua, and render suite
make sync-example        # copy canonical extension assets and rebuild the graph
make check-example       # validate the regenerated example graph
make render-example-all  # render the example book to HTML, DOCX, and PDF
make preview-example     # pre-process, then serve the book with live reload
```

`make sync-example` is deterministic: running it twice leaves
`examples/book/.quarto-needs/needs.json` and
`examples/book/_extensions/quarto-needs/generated-index.lua` byte-identical.
`make render-example` remains the single-format shortcut.

`make render-example` regenerates the graph, synchronizes the local
extension, and writes the static book to `examples/book/_book`.
`make preview-example` performs the same pre-processing and starts the
development server with automatic reloading.

`_extensions/quarto-needs` is canonical. The pre-render helper copies every
regular canonical extension asset into the project-local installed extension
before building the graph, while leaving `generated-index.lua` to be generated
for that project.

## Current validation rules

- `REQ002`: requirement without rationale (warning)
- `REQ004`: duplicate ID (error)
- `REQ005`: relation target does not exist (error)
- `REQ006`: approved requirement without verification relation (warning)

The rule engine is intentionally small in 0.1. It is designed to grow into structural, referential, and process validation.

## Canonical graph

`.quarto-needs/needs.json` contains:

- engineering objects;
- typed relations;
- source provenance;
- backlinks;
- coverage metrics;
- validation findings.

This file is the first interoperability boundary for future JSON/CSV/ReqIF exports and semantic diff/baselines.

### Compatibility contract

- **schema v1 stays the public projection.** Required keys, value types,
  relation orientation, the `derived-from` → `derives-from` normalization,
  nested and top-level relation duplication, backlink meaning, HTML `href`
  behavior, and the six legacy coverage keys are all preserved. Output is
  deterministic and written atomically, with no wall-clock timestamps or
  absolute local paths.
- **`extensions.quartoNeeds` is additive.** It carries the generator identity
  and `relationCatalog` — each relation's `directLabel`, `inverseLabel`,
  `semanticFamily`, `sourceRole`, `targetRole`, `impactDirection`, and `public`
  flag. Python owns these semantics; Lua only reads the projection, so it never
  hard-codes competing inverse rules. Consumers that ignore `extensions` keep
  working unchanged.
- **`generated-index.lua` is still emitted** for external compatibility, but the
  bundled extension resolves everything through the cached `needs.json` instead.
- **Structural errors never overwrite a good graph.** A duplicate ID or a
  dangling relation target produces located findings and no snapshot, and
  `build`/`export` leave the previous outputs in place.

## Roadmap

### 0.2 — Quarto UX follow-ups
- backlinks rendered inside cards;
- query shortcode.

### 0.3 — Engineering validation
- project-defined schemas;
- relation constraints;
- configurable process rules;
- CI severity policies.

### 0.4 — Source traceability
- code/test scanners;
- `@implements` and `@verifies` annotations;
- semantic symbols as graph nodes;
- Tree-sitter backend.

### 0.5 — Change management
- Git baselines;
- semantic diff;
- graph-based impact analysis.

### Later
- JSON/CSV/ReqIF;
- VS Code extension;
- GitHub/Jira/external artifacts;
- GUI.

## Design principles

- Requirements as Code
- Documentation as interface
- Traceability as graph
- Single source of truth
- Derived matrices/diagrams/coverage
- Extensible types, attributes, relations and rules
- Renderer-independent canonical model
- CI/CD first

## License

MIT
