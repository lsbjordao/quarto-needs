# Phase 8B — Extension-First Distribution and Managed Engine

**Date:** 2026-09-02  
**Status:** Proposed — implementation-ready  
**Roadmap:** Phase 8 — Scale, performance, compatibility, and release hardening  
**Supersedes:** the user-installation assumption in `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-4d-distribution.md`

## 1. Goal

Make the Quarto extension the primary user-facing distribution of Quarto-Needs.

A user who wants Quarto-Needs for a Quarto project must not have to separately:

- install the `quarto-needs` Python package;
- place the `quarto-needs` CLI on `PATH`;
- author `project.pre-render: quarto-needs scan`;
- understand that a Python semantic engine exists behind the extension.

The normal Quarto activation step remains explicit: an existing project uses the installed filter with:

```yaml
filters:
  - quarto-needs
```

Once the extension is active, ordinary:

```bash
quarto render
```

must automatically ensure that the matching semantic engine is available, analyze the project, publish the canonical artifacts, and then let the existing Lua presentation layer consume those artifacts.

The target user experience is therefore:

```text
quarto add lsbjordao/quarto-needs
        ↓
activate filter in the Quarto project
        ↓
quarto render
        ↓
Quarto-Needs works
```

and not:

```text
pip install quarto-needs
        ↓
quarto add ...
        ↓
edit project.pre-render
        ↓
fix PATH
        ↓
quarto render
```

## 2. Product decision

Quarto-Needs remains architecturally:

```text
Python = semantic authority
Lua    = presentation
Quarto = execution/documentation host
```

This phase does **not** rewrite the semantic engine in Lua, JavaScript, TypeScript, or Deno.

Instead, the extension becomes responsible for provisioning and invoking an exact compatible Python engine.

The existing Python package remains valuable and remains supported for:

- direct CLI users;
- CI pipelines that deliberately install it;
- LSP/editor integration;
- development;
- external Python integrations;
- advanced users who want `quarto-needs trace`, `diff`, `impact`, etc. directly on `PATH`.

But that package becomes **optional for rendering a Quarto project**.

The correctness of `quarto render` must not depend on a globally installed `quarto-needs`.

## 3. Why this changes Milestone 4D

Milestone 4D established two coordinated distributions:

1. a Quarto extension installed with `quarto add`;
2. a Python package installed independently with `pip`.

That was appropriate as an initial distribution milestone, but it exposes an internal architectural boundary directly to end users.

The new default contract is:

> one user-facing Quarto extension, one internally managed semantic engine.

There may still be two release artifacts internally, but there must no longer be two installation responsibilities for the ordinary Quarto user.

## 4. Quarto-native integration

Quarto supports metadata extensions that merge project-level metadata.

Quarto-Needs will extend its existing `_extension.yml` with a metadata contribution that installs its pre-render integration automatically when the extension is active.

Conceptually:

```yaml
contributes:
  filters:
    - needs.lua
    - margin-sidebar.lua

  shortcodes:
    - shortcodes.lua
    - adr-shortcodes.lua

  metadata:
    project:
      pre-render:
        - quarto run _extensions/quarto-needs/bootstrap.py
```

The exact syntax must be verified against real Quarto 1.6.0 and the current supported integration version before it becomes the committed contract.

The relative `quarto run` command is intentional. Do not depend on Quarto converting an extension script into an absolute command path.

The bootstrap script is part of the extension.

The project author no longer declares a Quarto-Needs pre-render hook.

## 5. Runtime model

### 5.1 Phase 8B runtime prerequisite

This slice continues to require:

```text
Quarto >= 1.6
Python >= 3.10
Python pip module available
```

The user does **not** run `pip install quarto-needs`.

Python is a platform prerequisite in this phase, not a separately managed Quarto-Needs installation.

Removing the Python prerequisite entirely through standalone engine binaries is a possible later distribution slice and must not be mixed into this one.

### 5.2 Project-local managed runtime

The bootstrap provisions the engine inside the generated Quarto-Needs state tree:

```text
.quarto-needs/
├── needs.json
├── graphs/
├── ...
└── runtime/
    └── <engine-version>/
        └── <python/platform-tag>/
            ├── site-packages/
            └── installed.json
```

`.quarto-needs/` is generated state and remains ignored by Git.

Nothing is installed globally.

Nothing is installed into the user's active virtualenv.

Nothing modifies `PATH`.

Nothing modifies the system Python environment.

### 5.3 Version-specific runtime

The runtime directory contains the exact Quarto-Needs release paired with the extension.

For extension version `0.2.0`:

```text
managed engine == 0.2.0
```

not merely:

```text
managed engine ~= 0.2
```

The extension-managed path uses exact compatibility because the extension and engine are released together.

The existing looser compatibility policy may remain for explicitly external/legacy graph artifacts, but it does not apply to the managed runtime.

## 6. Bootstrap responsibilities

`_extensions/quarto-needs/bootstrap.py` must use only the Python standard library before the managed runtime is loaded.

It is responsible for:

```text
locate project
      ↓
check Python version
      ↓
resolve exact runtime directory
      ↓
acquire bootstrap lock
      ↓
validate existing runtime
      ↓
if absent:
    install exact engine into staging directory
      ↓
validate installed engine version
      ↓
atomically publish runtime
      ↓
load canonical Quarto-Needs integration entry point
      ↓
run semantic pre-render
      ↓
return canonical exit status
```

It must not contain:

- parser logic;
- graph semantics;
- rule evaluation;
- C4 semantics;
- evidence semantics;
- projection logic;
- authored-relation interpretation.

It is a runtime adapter only.

## 7. Canonical pre-render entry point

The extension must not duplicate the `scan` command implementation.

The existing CLI `scan` path should be factored, only as much as necessary, into a narrow Python application entry point such as:

```python
run_quarto_pre_render(root: Path) -> int
```

or an equivalent name discovered to fit the current code.

Both:

```text
quarto-needs scan
```

and:

```text
extension bootstrap
```

must call the same application service.

This refactor must preserve:

- parser behavior;
- diagnostics;
- exit codes;
- artifact bytes;
- graph fingerprints;
- graph/C4 projections;
- generated paths;
- logging semantics where externally observable.

No new semantic path is allowed.

## 8. Engine provisioning

### 8.1 Default source

When no cached runtime exists, the bootstrap installs:

```text
quarto-needs==<extension-version>
```

into the project-local runtime.

The installation must use:

```text
python -m pip
```

from the interpreter Quarto selected for the bootstrap.

The bootstrap never invokes bare `pip`.

### 8.2 Installation target

Use an empty staging directory and `pip --target`, not the current interpreter environment.

Conceptually:

```text
runtime/
  .staging-<unique>/
      site-packages/
```

Only after installation and validation succeed is the staging runtime promoted to the final versioned directory.

A failed installation must never leave a runtime that appears valid.

### 8.3 Development/offline source override

Support one explicit environment-only override for development, tests, and air-gapped preparation:

```text
QUARTO_NEEDS_ENGINE_SOURCE
```

Allowed default meaning:

- unset → exact released package `quarto-needs==VERSION`;
- local filesystem path → install the package from that local path.

Do not accept an arbitrary remote URL through project configuration.

Regardless of source, the installed `quarto_needs.__version__` must equal the extension version.

An explicit local source is never trusted merely because the filename contains the right version.

### 8.4 No implicit system fallback

Do not silently execute a random `quarto-needs` found on `PATH`.

A globally installed:

```text
quarto-needs 0.1.0
```

must not affect an extension:

```text
Quarto-Needs 0.2.0
```

This property removes an entire class of extension/engine skew.

A future explicit `QUARTO_NEEDS_ENGINE_PATH` escape hatch may be considered separately if there is a demonstrated need.

## 9. Runtime identity

Each installed managed runtime writes an `installed.json` marker containing at least:

```json
{
  "schemaVersion": "quarto-needs-managed-runtime-v1",
  "engineVersion": "0.2.0",
  "pythonVersion": "3.13.5",
  "pythonImplementation": "cpython",
  "pythonTag": "cpython-313",
  "platform": "linux",
  "machine": "x86_64"
}
```

The exact field names may be refined during implementation.

The marker is descriptive, not authoritative.

A cached runtime must still prove that importing `quarto_needs` from its own `site-packages` yields the expected exact engine version.

## 10. Concurrency and atomicity

Two concurrent Quarto renders must not corrupt runtime provisioning.

Bootstrap uses a project-local exclusive lock.

Required behavior:

```text
Process A: installs
Process B: sees active lock → waits boundedly
Process A: atomically publishes valid runtime
Process B: validates published runtime → reuses it
```

A stale lock must be recoverable.

A failed installer must clean its staging directory and release the lock.

Never install directly into the final runtime directory.

## 11. Offline behavior

After one successful provisioning:

```bash
quarto render
```

must work without network access.

The bootstrap must never contact a package index when a valid exact runtime already exists.

First use while offline and without a prepared runtime must fail clearly.

The failure must say:

- which engine version is required;
- that no managed runtime exists;
- that the engine could not be provisioned;
- how to prepare it using an online render or explicit local engine source.

Do not silently continue into rendering without a graph.

## 12. Updates

Updating the extension from `0.2.0` to `0.2.1` produces a different runtime identity:

```text
runtime/0.2.0/...
runtime/0.2.1/...
```

Do not mutate an older runtime in place.

The new runtime is provisioned on first use.

Old runtimes may remain until explicit cleanup.

Automatic garbage collection is not part of this slice.

## 13. Failure semantics

Bootstrap failures are build failures.

Examples:

```text
Python < 3.10
pip unavailable
managed package unavailable
network unavailable on first provisioning
wrong locally supplied package version
corrupt cached runtime
runtime installation failure
runtime lock timeout
canonical scan failure
```

Each must produce an actionable diagnostic.

Do not degrade these cases into an empty requirements graph.

A successful Quarto document that silently omitted its engineering model is considered a more serious failure than a render that stops visibly.

## 14. Activation semantics

`quarto add` installs an extension; Quarto's normal filter mechanism still determines whether that extension is used.

Therefore the supported existing-project configuration remains:

```yaml
filters:
  - quarto-needs
```

There is deliberately no claim that installing arbitrary Quarto filter files automatically changes a project's rendering behavior.

For a new project, a Quarto-Needs starter template may provide this configuration automatically.

This distinction must be stated clearly in the quickstart:

```text
installation ≠ activation
```

but:

```text
activation ⇒ complete Quarto-Needs runtime integration
```

## 15. CLI and editor separation

Extension-first distribution does not remove the Python distribution.

Two consumption modes become explicit.

### Ordinary Quarto author

```text
Quarto extension
    ↓
managed engine
    ↓
quarto render
```

No package install required.

### Engineering/power user

```text
pip/pipx install quarto-needs
    ↓
quarto-needs diff
quarto-needs impact
quarto-needs baseline
quarto-needs lsp
...
```

The installed CLI and the extension-managed runtime may coexist.

They must never accidentally substitute for each other.

## 16. Security boundaries

The bootstrap is executable supply-chain code and must be treated accordingly.

Required constraints:

1. No arbitrary shell command is constructed from project-authored values.
2. Python subprocess calls use argument arrays.
3. Runtime installation occurs only below `.quarto-needs/runtime`.
4. No global site-packages modification.
5. No `sudo`.
6. No arbitrary code from `.quarto-needs.toml` is executed.
7. The engine version is exact.
8. Local-source override is explicit through process environment.
9. Credentials are never persisted in runtime metadata.
10. Bootstrap logs must not expose package-index credentials embedded in environment configuration.
11. Runtime files are generated state, never semantic authored data.
12. Renderer or runtime choices must not enter semantic/configuration fingerprints unless they actually change semantic configuration.

## 17. Quarto compatibility

Metadata extensions were introduced before the project's current Quarto floor, so this feature must not automatically raise:

```yaml
quarto-required: ">=1.6.0"
```

However the integration must be executed against exact Quarto 1.6.0 before that claim is retained.

The test matrix must include:

```text
Quarto 1.6.0
current supported Quarto
project path without spaces
project path with spaces
```

The implementation must not depend on Quarto's problematic absolute extension-script command resolution.

The preferred metadata command is a relative project-root command:

```text
quarto run _extensions/quarto-needs/bootstrap.py
```

If this cannot be made reliable on the declared minimum version, the incompatibility must be treated as a release decision, not hidden with a brittle shell workaround.

## 18. Existing pre-render hooks

Quarto-Needs must coexist with project-authored pre-render hooks.

Given:

```yaml
project:
  pre-render:
    - prepare-data.py

filters:
  - quarto-needs
```

the effective behavior must include both:

```text
prepare-data.py
Quarto-Needs bootstrap/scan
```

The implementation must test the actual ordering produced by Quarto.

Do not assume list-merge semantics without an integration test.

If ordering materially affects correctness, document and enforce the required order.

## 19. Formats

The runtime bootstrap occurs before Quarto's output-format-specific rendering.

Therefore the same integration must serve:

```text
HTML
PDF
DOCX
other existing supported formats
```

There is no format-specific semantic engine.

The current progressive-enhancement boundary remains:

```text
semantic artifacts → common
presentation       → format-specific where necessary
```

## 20. Non-goals

This phase does not:

- rewrite the Python core;
- remove the Python package;
- add standalone native engine binaries;
- install Python itself;
- put a CLI executable on global `PATH`;
- automatically rewrite arbitrary existing `_quarto.yml` files;
- implement C4 Dynamic or Deployment views;
- add new requirements semantics;
- add new interchange formats;
- change graph schema versions merely for distribution;
- change baseline/diff/impact behavior;
- introduce auto-update-to-latest behavior;
- garbage-collect old runtimes.

## 21. Acceptance contract

A clean consumer project satisfies the phase when all of the following are true.

Environment:

```text
Quarto installed
Python 3.10+ installed
pip available to that Python
NO quarto-needs package preinstalled
NO quarto-needs CLI on PATH
```

Project:

```yaml
project:
  type: default

filters:
  - quarto-needs
```

There is deliberately no:

```yaml
pre-render: quarto-needs scan
```

Then:

```bash
quarto render
```

must:

1. invoke the extension-provided bootstrap;
2. provision the exact engine if needed;
3. produce `.quarto-needs/needs.json`;
4. produce all currently expected graph/C4 artifacts;
5. render `.need` blocks;
6. resolve Quarto-Needs shortcodes;
7. preserve backlinks and generated views;
8. return success for a valid project.

A second render with network unavailable must also succeed.

## 22. Definition of done

The phase is complete when the repository can truthfully replace its installation documentation from:

```bash
pip install quarto-needs
quarto add lsbjordao/quarto-needs
# manually configure pre-render
```

to the ordinary Quarto-user path:

```bash
quarto add lsbjordao/quarto-needs
```

activate:

```yaml
filters:
  - quarto-needs
```

and render:

```bash
quarto render
```

with no separately installed Quarto-Needs engine.

At that point Quarto-Needs behaves externally like the product it claims to be:

> a Quarto extension backed internally by a semantic engineering engine.
