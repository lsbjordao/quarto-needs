# Quarto-Needs Milestone 4D Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Date:** 2026-08-26
**Status:** Second in the committed adoption arc — starts once 4A is accepted.

**Goal:** Make Quarto-Needs installable and usable by someone who has never seen this repository, and keep it that way.

**Architecture:** Nothing about the engine changes. Quarto-Needs ships as two coordinated distributions — a Quarto extension installed with `quarto add`, and a Python package installed with `pip` that the extension's pre-render hook invokes. This milestone builds the release plumbing that publishes both, the documentation a stranger follows, and the checks that fail loudly when either drifts.

**Tech Stack:** Python packaging (`build`, `twine`), GitHub Actions, Quarto extension manifest, Bash

**Design inputs:** `docs/superpowers/specs/2026-08-26-quarto-needs-capability-evolution.md` — the adoption arc and the guardrail that new artifact formats receive golden, malformed, determinism, and migration tests.

## Prerequisite discovered before planning: the repository is private

`quarto add lsbjordao/quarto-needs` fails today with *"Extension not found in
local or remote sources"*. The cause is not the extension: `_extensions/quarto-needs`
is present on `origin/main` with a valid manifest, and the extension renders
correctly when copied in by hand. The GitHub API and the default-branch tarball
both return **HTTP 404** anonymously — the repository is private, and that is
what Quarto reports as a missing extension.

Every task below that involves `quarto add` is blocked until the repository is
public. That is a human decision, not an implementation step: publishing exposes
the full history, including the `.superpowers/sdd/` execution ledgers and roughly
51 MB of review snapshots committed before this project had `.gitignore` coverage
for them. Both are worth reviewing before the repository becomes readable.

Tasks 1, 2, and 3 do not depend on it and can proceed first.

## Why this milestone exists

The engine is complete enough to be useful and nobody can install it. Every check in this repository installs the package editable from a checkout and renders the in-tree Aegis book, so the distribution itself — packaging metadata, the console script, extension assets that must resolve outside the repository — was never exercised until `tools/check_installed_path.sh` was added. That script proved the path works today. This milestone makes it reachable.

The ordering claim is narrow and worth stating plainly: capability work below this line is unreachable by users until this line is crossed. That is the whole argument for putting it second.

## Global Constraints

- Do not change engine behavior. This milestone is packaging, publication, and documentation. A code change outside `tools/`, `.github/`, `pyproject.toml`, and the docs is a signal the task is wrong.
- Do not add a runtime dependency. Release tooling (`build`, `twine`) belongs in a `release` optional dependency group or is installed only inside CI.
- The two distributions must agree on version. A user pairing extension `0.2.0` with engine `0.1.0` must get a clear diagnostic, not a confusing failure.
- Preserve every existing CLI command, shortcode, and exit code.
- `tools/check_installed_path.sh` must keep passing after every task, and must be extended rather than weakened when it gets in the way.
- Publication to a real index is irreversible. No task publishes to production PyPI without explicit human approval recorded in the ledger; TestPyPI is the rehearsal target.
- The workspace may or may not have Git metadata depending on when this runs. Tasks end with a conditional checkpoint that commits only inside a Git worktree.

## File Map

| Area | Files | Responsibility after Milestone 4D |
|---|---|---|
| Version source | `pyproject.toml`, `_extensions/quarto-needs/_extension.yml`, `src/quarto_needs/__init__.py` | One version, asserted identical across all three by a test. |
| Compatibility check | `src/quarto_needs/cli.py`, `_extensions/quarto-needs/data.lua` | The extension detects an engine version it cannot work with and says so in the rendered document. |
| Release automation | `.github/workflows/release.yml` | Tag-triggered build, TestPyPI rehearsal, and gated production publish. |
| Install verification | `tools/check_installed_path.sh`, `.github/workflows/ci.yml` | Already present; extended with the version-skew and `quarto add` cases. |
| User documentation | `README.md`, `docs/quickstart.md` | A five-minute path from nothing to a rendered requirement, written for someone who has never seen this repository. |

---

### Task 1: One version, asserted in three places

**Files:**
- Modify: `src/quarto_needs/__init__.py`
- Test: `tests/test_packaging.py` (create)

**Interfaces:**
- Produces: `quarto_needs.__version__` as the single source, and a test that fails when `pyproject.toml` or `_extension.yml` drifts from it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_packaging.py`:

```python
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import quarto_needs

ROOT = Path(__file__).resolve().parents[1]


def test_all_three_manifests_declare_the_same_version() -> None:
    """A user pairs an extension with an engine; drift between them is a support burden."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packaged = pyproject["project"]["version"]

    manifest = (ROOT / "_extensions" / "quarto-needs" / "_extension.yml").read_text(encoding="utf-8")
    match = re.search(r"^version:\s*(\S+)\s*$", manifest, re.M)
    assert match, "the Quarto extension manifest declares no version"

    assert quarto_needs.__version__ == packaged == match.group(1)
```

- [ ] **Step 2: Run it**

Run: `.venv/bin/python -m pytest tests/test_packaging.py -q`

Expected: PASS if the three already agree, FAIL naming the mismatch otherwise. Either outcome is informative; do not edit the test to match a drift you find — fix the drift.

- [ ] **Step 3: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/__init__.py tests/test_packaging.py
  git commit -m "test: pin extension and package versions together"
else
  echo "Checkpoint 1 verified; workspace has no Git metadata."
fi
```

---

### Task 2: Tell the user when the extension and engine disagree

**Files:**
- Modify: `_extensions/quarto-needs/data.lua`
- Modify: `src/quarto_needs/export.py`
- Test: `tests/test_lua_data.py`

**Interfaces:**
- Consumes: the `generator.version` already written into `needs.json` by the v1 writer.
- Produces: a rendered warning naming both versions when the extension's own version is incompatible with the graph's generator version.

- [ ] **Step 1: Write the failing Lua assertions**

The graph already records `extensions.quartoNeeds.generator.version`. Add to `tests/test_lua_data.py` a case asserting `data.load` surfaces a version mismatch as a distinguishable error rather than silently proceeding:

```lua
local incompatible = data.load(__SKEWED_GRAPH_PATH__)
assert(incompatible == nil, "a graph from an incompatible engine must not load silently")
```

Build the skewed fixture in Python by writing a graph whose `generator.version` differs in its major component from `quarto_needs.__version__`.

- [ ] **Step 2: Run it and verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lua_data.py -q`

Expected: FAIL — the loader currently accepts any generator version.

- [ ] **Step 3: Implement the check**

In `data.lua`, after decoding the graph, compare the major component of `extensions.quartoNeeds.generator.version` against the extension's own version and return a message naming both when they differ. Match on the major component only: a patch-level difference between extension and engine must keep working, because users update the two independently.

- [ ] **Step 4: Verify the message reaches the reader**

A mismatch must render as a visible `need-view-warning`, not a silent empty view — the same reasoning as `Dashboard report unavailable.` A build that renders a document missing all its requirements without saying why is worse than one that fails.

- [ ] **Step 5: Extend the installed-path check**

Add a skew case to `tools/check_installed_path.sh`: install the engine, hand the project a graph from an incompatible version, render, and assert the warning appears in the HTML.

- [ ] **Step 6: Run the suite and the install check**

Run: `.venv/bin/python -m pytest -q && make check-install`

Expected: PASS.

- [ ] **Step 7: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add _extensions/quarto-needs/data.lua src/quarto_needs/export.py tests/test_lua_data.py tools/check_installed_path.sh
  git commit -m "feat: warn when extension and engine versions are incompatible"
else
  echo "Checkpoint 2 verified; workspace has no Git metadata."
fi
```

---

### Task 3: A quickstart a stranger can finish in five minutes

**Files:**
- Create: `docs/quickstart.md`
- Modify: `README.md`

**Interfaces:**
- Produces: the install path this milestone exists to enable, written for someone with no knowledge of this repository.

- [ ] **Step 1: Write the quickstart**

`docs/quickstart.md` must take a reader from an empty directory to a rendered requirement. It states, in order: install the engine (`pip install quarto-needs`), add the extension (`quarto add lsbjordao/quarto-needs`), declare the pre-render hook, author one `.need` block, render, and see the card plus a working shortcode. Every command must be copy-pasteable and must have been run.

The reader is not a contributor. Do not send them to `make setup`, a virtualenv in this repository, or the Aegis book.

- [ ] **Step 2: Separate the two audiences in the README**

The README's current quick start is developer-oriented (`make setup`, `source .venv/bin/activate`). Move it under a contributor heading and put the user path first, linking to the quickstart. A reader deciding whether to try this project should not have to recognize that the first instructions are not for them.

- [ ] **Step 3: Run every command in the quickstart, in order, from an empty directory**

Not a review of the prose — an execution of it. Any command that fails, or any step that assumes knowledge the reader does not have, is a defect in the document.

- [ ] **Step 4: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add docs/quickstart.md README.md
  git commit -m "docs: add a user quickstart separate from contributor setup"
else
  echo "Checkpoint 3 verified; workspace has no Git metadata."
fi
```

---

### Task 4: Tag-triggered release with a rehearsal before the real thing

**Files:**
- Create: `.github/workflows/release.yml`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: a workflow that builds on a `v*` tag, publishes to TestPyPI unconditionally, and publishes to PyPI only through a protected environment requiring human approval.

- [ ] **Step 1: Add the release optional dependency group**

Add `release = ["build", "twine"]` to `[project.optional-dependencies]`. It is not a runtime dependency and must not appear in `dependencies`.

- [ ] **Step 2: Write the workflow**

`.github/workflows/release.yml` triggers on `push: tags: ["v*"]`. It builds the sdist and wheel, verifies with `twine check`, and publishes to TestPyPI. The production PyPI step uses a GitHub environment (`pypi`) configured to require reviewer approval, and trusted publishing rather than a stored token.

- [ ] **Step 3: Assert the tag matches the packaged version**

Before building, fail the workflow when the tag does not match `project.version`. A release published under a tag that disagrees with its own metadata is confusing to diagnose and impossible to withdraw.

- [ ] **Step 4: Rehearse against TestPyPI**

Tag a pre-release, let the workflow publish to TestPyPI, then install *from TestPyPI into a clean environment* and run `tools/check_installed_path.sh` against that installation rather than against the local build. This is the only step that proves the published artifact — not the local one — actually works.

- [ ] **Step 5: STOP — production publication requires explicit approval**

Do not publish to production PyPI as part of executing this plan. Report that the rehearsal succeeded, state the version to be published, and wait. Publication is irreversible: a released version number can never be reused, and a broken first release is the worst possible introduction for a tool nobody has tried yet.

- [ ] **Step 6: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add .github/workflows/release.yml pyproject.toml
  git commit -m "ci: add gated release workflow with TestPyPI rehearsal"
else
  echo "Checkpoint 4 verified; workspace has no Git metadata."
fi
```

---

### Task 5: Prove `quarto add` works against the published repository

**Files:**
- Modify: `tools/check_installed_path.sh`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Replace the copy with a real `quarto add`**

`check_installed_path.sh` currently copies `_extensions/quarto-needs` to stand in for `quarto add`. Add a second mode that runs the real command against the repository, so the extension manifest, the repository layout, and Quarto's own resolution are exercised rather than assumed.

Keep the copy mode: it is the one that works offline and on a branch that has no release yet. The two modes answer different questions and both are worth keeping.

- [ ] **Step 2: Run the real mode in CI on the default branch only**

`quarto add` reaches the network and resolves the default branch, so it cannot verify a pull request's own changes. Run it on push to the default branch and on tags, where it is meaningful.

- [ ] **Step 3: Run both modes and the suite**

Run: `make check-install && .venv/bin/python -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Record the milestone checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add tools/check_installed_path.sh .github/workflows/ci.yml
  git commit -m "ci: verify quarto add against the published repository"
else
  echo "Milestone 4D verified; workspace has no Git metadata."
fi
```

Expected: a stranger can install both distributions, follow the quickstart, and render a requirement — and CI fails when any part of that stops being true.
