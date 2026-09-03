#!/usr/bin/env bash
# Prove the way a user is told to install Quarto-Needs actually works.
#
# The claim this phase makes is narrow and testable: `quarto add`, activate the
# filter, render. No `pip install quarto-needs`, no console script on PATH, no
# hand-authored `project.pre-render`. So this deliberately builds an
# environment that has none of those and renders a project created outside the
# repository.
#
# `tools/check_installed_path.sh` still covers the CLI-installed path, which
# remains supported for engineering and CI users. It is no longer the primary
# user-installation scenario.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
# A path with a space, because `quarto run` has to survive one and this is a
# release gate rather than a curiosity.
WORK="$(mktemp -d)/Quarto Needs Consumer Project"
mkdir -p "$WORK"
trap 'rm -rf "$(dirname "$WORK")"' EXIT

PYTHON="$(command -v python3 || command -v python)"
[[ -n "$PYTHON" ]] || { echo "FAIL: no python interpreter on PATH" >&2; exit 1; }

echo "==> Creating a consumer project outside the repository"
PROJECT="$WORK/consumer"
mkdir -p "$PROJECT/_extensions"
# Stand in for `quarto add lsbjordao/quarto-needs`, which installs exactly this.
cp -r "$REPO/_extensions/quarto-needs" "$PROJECT/_extensions/"

# Deliberately no `pre-render`. That line disappearing is the phase.
cat > "$PROJECT/_quarto.yml" <<'YAML'
project:
  type: default
filters:
  - quarto-needs
YAML

cat > "$PROJECT/index.qmd" <<'QMD'
---
title: "Extension-first install check"
---

::: {.need #REQ-1 type=functional-requirement status=approved priority=high}
## Authenticate the user

The system shall authenticate the user.

### Rationale
Protect private data.
:::

::: {.need #TC-1 type=test-case status=passed}
## Login test

Signs a user in.
:::

Count: {{< need-count types="functional-requirement" >}}
QMD

echo "==> Confirming the engine is not installed anywhere the render could reach"
if command -v quarto-needs >/dev/null 2>&1; then
  echo "FAIL: a quarto-needs executable is on PATH; this check must run without one" >&2
  exit 1
fi
if "$PYTHON" -c "import quarto_needs" 2>/dev/null; then
  echo "FAIL: quarto_needs is importable from the ambient interpreter" >&2
  exit 1
fi

echo "==> Rendering the way an ordinary Quarto author would"
# The paired engine version is not published yet, so provision it from this
# checkout through the documented local-source override. Everything else about
# the scenario is exactly what a user gets.
(
  cd "$PROJECT"
  QUARTO_NEEDS_ENGINE_SOURCE="$REPO" quarto render .
)

echo "==> Asserting the results"
GRAPH="$PROJECT/.quarto-needs/needs.json"
[[ -f "$GRAPH" ]] || { echo "FAIL: the extension did not write $GRAPH" >&2; exit 1; }
"$PYTHON" -c "
import json
graph = json.load(open('$GRAPH'))
ids = {item['id'] for item in graph['objects']}
assert ids == {'REQ-1', 'TC-1'}, f'unexpected objects: {ids}'
assert graph['schemaVersion'] == '1', f\"unexpected schemaVersion: {graph['schemaVersion']}\"
" || { echo "FAIL: the emitted graph is not what the source declares" >&2; exit 1; }

# The engine ran from a project-local managed runtime, not from the system.
MARKER="$(find "$PROJECT/.quarto-needs/runtime" -name installed.json | head -1)"
[[ -n "$MARKER" ]] || { echo "FAIL: no managed runtime was provisioned" >&2; exit 1; }
"$PYTHON" -c "
import json
marker = json.load(open('$MARKER'))
assert marker['schemaVersion'] == 'quarto-needs-managed-runtime-v1', marker
" || { echo "FAIL: the runtime marker is not the expected contract" >&2; exit 1; }

HTML="$PROJECT/index.html"
[[ -f "$HTML" ]] || { echo "FAIL: no rendered HTML at $HTML" >&2; exit 1; }

grep -q 'data-need-count="1"' "$HTML" || {
  echo "FAIL: the need-count shortcode did not resolve against the graph" >&2
  exit 1
}
grep -q 'need-card' "$HTML" || {
  echo "FAIL: the need filter did not turn the div into a card" >&2
  exit 1
}
# A shortcode Quarto never expanded, or a graph the filter could not load, both
# render as visible text rather than failing the build — assert their absence.
! grep -q '{{<' "$HTML" || { echo "FAIL: an unexpanded shortcode reached the output" >&2; exit 1; }
! grep -q 'need-view-warning\|not found' "$HTML" || {
  echo "FAIL: the extension warned about a missing or invalid graph" >&2
  exit 1
}

echo "==> Rendering again with no engine source and no package index"
# After one successful provisioning the runtime is cached, so a render must
# need neither the override nor the network. PIP_NO_INDEX makes that testable
# rather than assumed: if the bootstrap reached for pip at all, it would fail.
rm -f "$GRAPH" "$HTML"
(
  cd "$PROJECT"
  PIP_NO_INDEX=1 PIP_NO_NETWORK=1 quarto render .
)

[[ -f "$GRAPH" ]] || { echo "FAIL: the offline second render produced no graph" >&2; exit 1; }
"$PYTHON" -c "
import json
ids = {item['id'] for item in json.load(open('$GRAPH'))['objects']}
assert ids == {'REQ-1', 'TC-1'}, f'unexpected objects: {ids}'
" || { echo "FAIL: the offline render did not reproduce the graph" >&2; exit 1; }
grep -q 'data-need-count="1"' "$HTML" || {
  echo "FAIL: the offline render did not resolve the shortcode" >&2
  exit 1
}

echo "PASS: an activated extension provisions its engine and renders, then renders offline"
