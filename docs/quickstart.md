# Quickstart

From an empty directory to a rendered, traceable requirement.

You need [Quarto](https://quarto.org) 1.6 or later, and Python 3.10 or later
with `pip` available. Python is a platform prerequisite, the same way a
LaTeX installation is for PDF output — you do not separately install
Quarto-Needs through it. The extension provisions its own engine the first
time you render.

> **Starting a brand-new project?** `quarto use template lsbjordao/quarto-needs/templates/starter`
> does steps 1 and 2 below in one command: it installs the extension, and the
> generated `_quarto.yml` already has `filters: [quarto-needs]` activated. Skip
> to [step 3](#3-write-a-requirement) if you use it.

## 1. Add the extension

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

## 2. Activate it

Installing the extension is not the same as using it. Create `_quarto.yml`:

```yaml
project:
  type: default

filters:
  - quarto-needs
```

That is the whole configuration. Activating the filter also installs the
extension's own pre-render step — you do not author one.

> **Updating a project that predates this?** Earlier versions asked for two
> extra pieces: `pip install quarto-needs` and a hand-authored pre-render in
> `_quarto.yml`, typically:
>
> ```yaml
> project:
>   pre-render:
>     - quarto-needs scan
> ```
>
> Both are obsolete. Delete the `pre-render` entry — the extension supplies
> its own, and leaving the old line in makes the render depend on a
> `quarto-needs` command the extension-first install never puts on `PATH`.
> The `pip install` becomes optional tooling (see [below](#optional-the-standalone-cli-and-editor-tooling)).
> Your requirements, configuration, and rendered output do not change.

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

The `#REQ-1` is the identifier you will reference from everywhere else. The
attributes are ordinary Pandoc Div attributes, so they stay structured in the
AST rather than being parsed out of prose.

## 4. Render

```bash
quarto render
```

The first render provisions the engine into `.quarto-needs/runtime/` — a
project-local, version-pinned install that nothing outside this project ever
sees. It contacts the package index once, for that first render only; every
render after it reuses the cached engine and needs no network access at all.

Open `index.html`. You should see the requirement as a card with type, status,
and priority badges, and the count resolving to `1`.

## 5. Link them

Change `REQ-1` to declare its verification:

```qmd
::: {.need #REQ-1 type=functional-requirement status=approved priority=high verified-by="TC-1"}
```

Render again. The card now carries a **Need relations** section linking to the
test case, and the test case carries a **Need backlinks** section pointing back.
You wrote one edge; both ends know about it.

## Where to go next

- **Views** — `need-table`, `need-list`, `need-matrix`, and `need-flow` render
  filtered, linked collections. See the README's *Generated views*.
- **Governance** — add `.quarto-needs.toml` to declare required attributes,
  relation policies, named queries, and quality gates that fail your build. See
  the README's *Configuration*.
- **Change intelligence** — `baseline create`, then `diff` and `impact` to see
  what changed between two states of the project and what it reaches. See
  *Optional: the standalone CLI and editor tooling* below.

## Optional: the standalone CLI and editor tooling

Rendering never needs it, but engineering and CI users who want the graph
directly — outside of what a rendered page shows — can install the same
engine as an ordinary Python package:

```bash
pip install quarto-needs
```

> **Before the first release.** The package is not on PyPI yet, and the
> repository is not public, so this resolves only from a local clone you
> already have access to: `pip install /path/to/quarto-needs`.

This puts a `quarto-needs` console script on `PATH` and unlocks:

```bash
quarto-needs trace REQ-1
quarto-needs coverage
quarto-needs diff --git main..HEAD
quarto-needs impact --git main..HEAD
quarto-needs lsp
```

The document and the command line read the same graph, so they cannot
disagree — but they are two independent installs that you update separately.
A project's `quarto render` never depends on this one being present, and this
one is never substituted in for the render's own managed engine even when
both happen to be on the same machine: the extension always uses the exact
version it provisioned for itself.

## Troubleshooting

**The card renders but shortcodes show as literal `{{< … >}}`.** The extension
is not registered. Check that `filters: [quarto-needs]` is in `_quarto.yml`
and that `_extensions/quarto-needs/` exists.

**The first render is slow, or fails with a network error.** The first render
in a project provisions the engine, which needs to reach the package index
once. On a machine with no network access, prepare the project on a
connected machine first and commit nothing from `.quarto-needs/` — it is
generated state — or set `QUARTO_NEEDS_ENGINE_SOURCE` to a local wheel or
checkout path before rendering, which installs from there instead of the
index.

**A later render still tries to reach the network.** It should not: once
`.quarto-needs/runtime/<version>/<python-tag>-<platform>-<machine>/` (for
example `0.1.0/cpython-313-linux-x86_64`) holds a validated engine, every
later render reuses it with no network access at all. If a render still
reaches out, something removed or corrupted that directory — see below.

**The render fails with a provisioning error.** The message names the engine
version it needed, that no valid runtime existed, and the two ways to
recover: render again with network access, or set
`QUARTO_NEEDS_ENGINE_SOURCE` to a local engine. Bootstrap failures deliberately
fail the render rather than continuing with an empty graph.

**Force a clean reprovision.** Delete `.quarto-needs/runtime/` and render
again. It is generated state, safe to remove any time, and the next render
rebuilds it from scratch.

**A warning names two versions.** Your extension and a graph it is reading
disagree on schema — typically a `.quarto-needs/needs.json` left over from
before the extension was updated. Delete `.quarto-needs/` and render again.

---

*Every command on this page was executed in order, from an empty directory,
against the version of Quarto-Needs it ships with.*
