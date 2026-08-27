# Quarto-Needs IAM Showcase Design

## Goal

Turn the current four-object example into a substantial identity-and-access-management (IAM) requirements project, while adding reusable Quarto views inspired by Sphinx-Needs: filtered tables, lists, counts, trace matrices, and relation flows.

## Product decisions

- The canonical requirements graph remains the source of truth. Quarto and Lua only query and present the graph.
- All generated views render during the Quarto build and therefore work in HTML, PDF, and DOCX.
- HTML receives progressive enhancement for table search and sorting; the underlying table remains usable without JavaScript.
- The implementation follows Sphinx-Needs concepts, not its reStructuredText syntax or Python-expression filters.
- Filters are deterministic exact-match filters. Arbitrary Python/Lua evaluation is explicitly excluded.
- No new runtime dependency is added. Python standard library, Pandoc/Quarto Lua, CSS, and a small vanilla-JavaScript enhancer are sufficient.

## Data flow

```text
.qmd need blocks
      |
      v
Python parser -> canonical graph -> .quarto-needs/needs.json
                                      |
                                      v
                           Lua shortcode adapter
                                      |
                  +-------------------+------------------+
                  |                   |                  |
              Pandoc tables       lists/counts       Mermaid flow
                  |
          optional HTML enhancement
```

The pre-render hook builds `needs.json` before Pandoc expands the shortcodes. The Lua adapter reads the JSON and exposes one shared filter/sort pipeline to every generated view.

## Shortcode API

### Reference

```qmd
{{< need IAM-SYS-001 title=true >}}
```

The existing shortcode remains compatible.

### Table

```qmd
{{< need-table
  types="functional-requirement;non-functional-requirement"
  status="approved"
  priority="high;critical"
  tags="security"
  columns="id;title;type;status;priority;verified-by"
  sort="priority;id"
  caption="Approved security requirements"
>}}
```

With no filters, `need-table` shows every engineering object. Default columns are `id;title;type;status;priority`. IDs and relation targets are links. Status and priority cells use semantic badges.

### List and count

```qmd
{{< need-list tags="authentication" show="status;priority" >}}
{{< need-count types="system-requirement" status="approved" >}}
```

`need-list` returns linked IDs and titles. `need-count` returns the number of matching objects.

### Traceability matrix

```qmd
{{< need-matrix
  rows="functional-requirement;non-functional-requirement"
  columns="test-case"
  relation="verified-by"
>}}
```

Rows and columns are filtered by type. A linked check mark indicates that the configured relation exists. Empty intersections use an em dash.

### Relation flow

```qmd
{{< need-flow
  root="IAM-STK-001"
  depth="4"
  relations="derives-from;implemented-by;verified-by"
  direction="LR"
>}}
```

`need-flow` emits a Mermaid flowchart from the selected subgraph. Without `root`, it includes all filtered objects up to a safe display limit. Node labels contain ID and title, node classes represent object types, and edges show relation names.

## Shared query semantics

- Supported filters: `ids`, `types`/`type`, `status`, `priority`, and `tags`.
- Commas and semicolons separate alternatives; alternatives within a field are OR-ed and different fields are AND-ed.
- Matching is case-insensitive.
- `tags` accepts either a scalar delimited value or a list from the canonical graph.
- `sort` accepts field names separated by commas/semicolons; priority uses `critical`, `high`, `medium`, `low`, then unspecified.
- Unknown columns render an empty cell rather than crashing a documentation build.
- Missing graph data or an unknown flow root produces a visible `.need-view-warning` block.
- An empty valid query produces an accessible empty-state message.

## Visual language

Status and priority are independent badges and always include text. Color is supplemental, not the only signal.

| Dimension | Value | Visual meaning |
|---|---|---|
| status | `approved`, `passed` | green |
| status | `disapproved`, `rejected`, `failed` | red |
| status | `in-review` | amber |
| status | `draft` | neutral gray |
| status | `implemented` | blue |
| status | `verified` | teal |
| status | `deprecated` | dark gray |
| priority | `critical` | dark red |
| priority | `high` | orange |
| priority | `medium` | blue |
| priority | `low` | gray |

Cards, generated tables, and lists reuse the same badge classes. Print output preserves readable borders and labels even when colors are unavailable.

## Example project

The book becomes an IAM system called **Aegis IAM** with at least 60 traceable objects:

- stakeholders and high-level stakeholder needs;
- system requirements;
- functional requirements for authentication, authorization, lifecycle, audit, and recovery;
- non-functional requirements for security, privacy, availability, performance, usability, and compliance;
- risks and threats mitigated by requirements;
- architecture components and interfaces implementing requirements;
- test cases verifying requirements;
- evidence records supporting passed tests.

The book contains overview dashboards, filtered catalogs, a requirements-to-tests matrix, a multi-level trace flow, a system context diagram, a component diagram, and an authentication sequence diagram. It deliberately includes a small number of draft, in-review, and disapproved items so all badge states are demonstrated, while the approved subset remains fully traced.

## Validation and coverage

- Every relation target must exist.
- Every approved requirement must have a direct `verified-by` or `validated-by` relation.
- Approved functional and non-functional requirements must also have `implemented-by` links.
- The example integration test requires at least 60 objects, representative counts for every object class, zero validation errors, and successful Quarto rendering when Quarto is installed.
- Unit tests cover parser metadata, graph export, badge classes, filtering, empty results, table columns, matrix links, and flow generation through rendered HTML assertions.

## Repository integration

`_extensions/quarto-needs` is the canonical extension source. The example's installed copy stays synchronized by the pre-render helper and a test compares the adapter assets. Generated graph/index files remain ignored.

## Non-goals

- Full Sphinx-Needs feature parity.
- Arbitrary expression evaluation.
- External inventories, ReqIF, Jira, or GitHub imports.
- Client-side mutation of the canonical graph.
- A general dashboard framework beyond the five documented shortcodes.
