# Quickstart

From an empty directory to a rendered, traceable requirement.

You need [Quarto](https://quarto.org) 1.6 or later and Python 3.10 or later.

## 1. Install the engine

Quarto-Needs ships as two pieces: a Quarto extension that renders, and a Python
engine that analyses. Install the engine first.

```bash
pip install quarto-needs
```

> **Before the first release.** The package is not on PyPI yet, and the
> repository is not public, so neither `pip install quarto-needs` nor an install
> straight from the URL will resolve. Until both change, this works only from a
> local clone you already have access to:
>
> ```bash
> pip install /path/to/quarto-needs
> ```
>
> Everything after this step behaves identically either way.

Check it:

```bash
quarto-needs --help
```

## 2. Add the extension

```bash
quarto add lsbjordao/quarto-needs
```

This creates `_extensions/quarto-needs/` in your project.

> **Before the repository is public**, `quarto add` reports *"Extension not
> found in local or remote sources"* — it resolves the repository anonymously
> and gets a 404. Copy the directory out of your local clone instead:
>
> ```bash
> mkdir -p _extensions
> cp -r /path/to/quarto-needs/_extensions/quarto-needs _extensions/
> ```

## 3. Wire the pre-render hook

Quarto-Needs analyses your project before Pandoc renders it, so the extension
has a graph to read. Create `_quarto.yml`:

```yaml
project:
  type: default
  pre-render: quarto-needs scan

filters:
  - quarto-needs
```

## 4. Write a requirement

Create `index.qmd`:

````qmd
---
title: "My requirements"
---

::: {.need #REQ-1 type=functional-requirement status=approved priority=high}
## Authenticate the user

The system shall authenticate the user before granting access to private data.

### Rationale
Authentication protects private data from unauthorized access.
:::

::: {.need #TC-1 type=test-case status=passed}
## Login test

Signs a user in and asserts the session is established.
:::

Approved requirements: {{< need-count types="functional-requirement" status="approved" >}}
````

The `#REQ-1` is the identifier you will reference from everywhere else. The
attributes are ordinary Pandoc Div attributes, so they stay structured in the
AST rather than being parsed out of prose.

## 5. Render

```bash
quarto render
```

Open `index.html`. You should see the requirement as a card with type, status,
and priority badges, and the count resolving to `1`.

## 6. Link them

Change `REQ-1` to declare its verification:

```qmd
::: {.need #REQ-1 type=functional-requirement status=approved priority=high verified-by="TC-1"}
```

Render again. The card now carries a **Need relations** section linking to the
test case, and the test case carries a **Need backlinks** section pointing back.
You wrote one edge; both ends know about it.

Ask the engine the same question:

```bash
quarto-needs trace REQ-1
quarto-needs coverage
```

The document and the command line read the same graph, so they cannot disagree.

## Where to go next

- **Views** — `need-table`, `need-list`, `need-matrix`, and `need-flow` render
  filtered, linked collections. See the README's *Generated views*.
- **Governance** — add `.quarto-needs.toml` to declare required attributes,
  relation policies, named queries, and quality gates that fail your build. See
  the README's *Configuration*.
- **Change intelligence** — `baseline create`, then `diff` and `impact` to see
  what changed between two states of the project and what it reaches. See the
  README's *Baseline, diff, and impact*.

## Troubleshooting

**The card renders but shortcodes show as literal `{{< … >}}`.** The extension
is not registered. Check that `filters: [quarto-needs]` is in `_quarto.yml` and
that `_extensions/quarto-needs/` exists.

**A warning says the graph was not found.** The pre-render hook did not run or
`quarto-needs` is not on your `PATH`. Run `quarto-needs scan` by hand and
confirm `.quarto-needs/needs.json` appears.

**A warning names two versions.** Your extension and engine are from
incompatible releases. Update whichever is older; the message says which.

---

*Every command on this page was executed in order, from an empty directory,
against the version of Quarto-Needs it ships with.*
