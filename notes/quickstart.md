# Quickstart

From an empty directory to a rendered, traceable requirement.

You need [Quarto](https://quarto.org) 1.6 or later, and Python 3.10 or later with `pip` available. Python is a platform prerequisite; you do not separately install Quarto-Needs through it for ordinary rendering. The extension provisions its paired engine the first time you render.

> **Starting a brand-new project?** `quarto use template lsbjordao/quarto-needs/templates/starter` does steps 1 and 2 below in one command: it bundles the extension and the generated `_quarto.yml` already has `filters: [quarto-needs]` activated. Skip to [step 3](#3-write-a-requirement) if you use it.

## 1. Add the extension

```bash
quarto add lsbjordao/quarto-needs
```

Quarto installs GitHub extensions under the repository-owner namespace, so this creates `_extensions/lsbjordao/quarto-needs/` in your project.

For local development from a clone, reproduce that same layout explicitly:

```bash
mkdir -p _extensions/lsbjordao
cp -r /path/to/quarto-needs/_extensions/quarto-needs _extensions/lsbjordao/
```

## 2. Activate it

Installing the extension is not the same as using it. Create `_quarto.yml`:

```yaml
project:
  type: default

filters:
  - quarto-needs
```

That is the whole configuration. Activating the filter also installs the extension's own pre-render step — you do not author one.

> **Updating a project that predates this?** Earlier versions asked for two extra pieces: `pip install quarto-needs` and a hand-authored pre-render in `_quarto.yml`, typically `quarto-needs scan`. Both are obsolete for rendering. Delete the hand-authored `pre-render` entry; the extension supplies its own. The standalone Python package remains optional tooling (see below).

## 3. Write a requirement

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

The `#REQ-1` is the identifier you will reference from everywhere else. The attributes are ordinary Pandoc Div attributes, so they stay structured in the AST rather than being parsed out of prose.

## 4. Render

```bash
quarto render
```

The first render provisions the exact engine version paired with the extension into `.quarto-needs/runtime/`, a project-local managed runtime. A released extension therefore expects its matching `quarto-needs` Python package version to be available from PyPI. Later renders reuse the validated runtime and do not need to reinstall it.

Open `index.html`. You should see the requirement as a card with type, status, and priority badges, and the count resolving to `1`.

## 5. Link them

Change `REQ-1` to declare its verification:

```qmd
::: {.need #REQ-1 type=functional-requirement status=approved priority=high verified-by="TC-1"}
```

Render again. The card now carries a **Need relations** section linking to the test case, and the test case carries a **Need backlinks** section pointing back. You wrote one edge; both ends know about it.

## Where to go next

- **Views** — `need-table`, `need-list`, `need-matrix`, and `need-flow` render filtered, linked collections.
- **Governance** — add `.quarto-needs.toml` to declare required attributes, relation policies, named queries, and quality gates.
- **Change intelligence** — install the optional CLI, create a baseline, then use `diff` and `impact` to inspect engineering changes.

## Optional: the standalone CLI and editor tooling

Rendering never needs a globally installed CLI, but engineering and CI users who want the graph directly can install the same engine as an ordinary Python package:

```bash
pip install quarto-needs
```

This puts a `quarto-needs` console script on `PATH` and unlocks commands such as:

```bash
quarto-needs trace REQ-1
quarto-needs coverage
quarto-needs diff --git main..HEAD
quarto-needs impact --git main..HEAD
quarto-needs lsp
```

The extension-managed runtime and the optional global/virtualenv CLI are independent installations. A project's `quarto render` always uses the exact engine version paired with the installed extension.

## Troubleshooting

**The card renders but shortcodes show as literal `{{< … >}}`.** The extension is not registered. Check that `filters: [quarto-needs]` is in `_quarto.yml` and that `_extensions/lsbjordao/quarto-needs/` exists for the canonical GitHub install.

**The first render fails with a provisioning error.** Check that Python 3.10+ and `pip` are available and that the matching `quarto-needs` version can be installed. For local development or an offline package mirror, set `QUARTO_NEEDS_ENGINE_SOURCE` to a local wheel or checkout path before rendering.

**A later render unexpectedly reprovisions.** Once `.quarto-needs/runtime/<version>/<python-tag>-<platform>-<machine>/` contains a validated engine, later renders reuse it. If that directory was removed or corrupted, the bootstrap provisions it again.

**Force a clean reprovision.** Delete `.quarto-needs/runtime/` and render again. It is generated state and safe to remove.

**A warning names two versions.** Your extension and an existing graph disagree on schema, typically because `.quarto-needs/needs.json` predates an extension update. Delete `.quarto-needs/` and render again.

---

*The release gate exercises this same owner-namespaced installation layout, including a project path containing spaces, HTML/DOCX/PDF output, and an offline second render.*
