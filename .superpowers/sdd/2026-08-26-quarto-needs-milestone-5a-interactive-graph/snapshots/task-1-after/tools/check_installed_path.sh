#!/usr/bin/env bash
# Prove Quarto-Needs works the way a user installs it, not the way we develop it.
#
# Every other check in this repository runs from an editable install against the
# in-tree Aegis book. That exercises the code but never the distribution: a
# missing packaging entry, a broken console script, or an extension asset that
# only resolves relative to the checkout would all pass CI and fail the first
# person who runs `quarto add`.
#
# This builds the package, installs it non-editable into a clean environment,
# and renders a project created outside the repository.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Some environments ship only `python3`; CI's setup-python provides both.
PYTHON="$(command -v python3 || command -v python)"
[[ -n "$PYTHON" ]] || { echo "FAIL: no python interpreter on PATH" >&2; exit 1; }

echo "==> Building and installing the package non-editable"
"$PYTHON" -m venv "$WORK/venv"
"$WORK/venv/bin/python" -m pip install --quiet --upgrade pip
"$WORK/venv/bin/python" -m pip install --quiet "$REPO"

export PATH="$WORK/venv/bin:$PATH"

command -v quarto-needs >/dev/null || {
  echo "FAIL: the quarto-needs console script is not on PATH after install" >&2
  exit 1
}

echo "==> Creating a consumer project outside the repository"
PROJECT="$WORK/consumer"
mkdir -p "$PROJECT/_extensions"
# Stand in for `quarto add lsbjordao/quarto-needs`, which installs exactly this.
cp -r "$REPO/_extensions/quarto-needs" "$PROJECT/_extensions/"

cat > "$PROJECT/_quarto.yml" <<'YAML'
project:
  type: default
  pre-render: quarto-needs scan
filters:
  - quarto-needs
YAML

cat > "$PROJECT/index.qmd" <<'QMD'
---
title: "Installed path check"
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

echo "==> Rendering as an installed user would"
( cd "$PROJECT" && quarto render . )

echo "==> Asserting the results"
GRAPH="$PROJECT/.quarto-needs/needs.json"
[[ -f "$GRAPH" ]] || { echo "FAIL: pre-render did not write $GRAPH" >&2; exit 1; }
"$WORK/venv/bin/python" -c "
import json, sys
graph = json.load(open('$GRAPH'))
ids = {item['id'] for item in graph['objects']}
assert ids == {'REQ-1', 'TC-1'}, f'unexpected objects: {ids}'
" || { echo "FAIL: the emitted graph is not what the source declares" >&2; exit 1; }

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

echo "PASS: the installed path builds the graph and renders through the extension"
