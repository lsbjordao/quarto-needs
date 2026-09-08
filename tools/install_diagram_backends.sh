#!/usr/bin/env bash
# Provision the optional C4 diagram backends (PlantUML, D2, Structurizr).
#
# `need-c4`'s non-Mermaid backends are fail-soft by design: when the local CLI
# is missing, c4.lua falls back to a syntax-highlighted code block. That is the
# right behavior for an author who never installed them, but it is silent --
# a render environment without the tools publishes DSL source where diagrams
# belong, and nothing fails. CI therefore provisions all three here and
# verifies each one, so an absent backend breaks the build instead of quietly
# degrading the published site.
#
# Linux x86_64 only; CI is the primary caller, contributors the secondary one.
set -euo pipefail

D2_VERSION="${D2_VERSION:-0.8.2}"
STRUCTURIZR_VERSION="${STRUCTURIZR_VERSION:-2026.06.28}"
PREFIX="${PREFIX:-$HOME/.local}"
BIN="$PREFIX/bin"

mkdir -p "$BIN"

install_d2() {
  if command -v d2 >/dev/null 2>&1; then
    echo "d2 already installed: $(command -v d2)"
    return
  fi
  local archive
  archive="$(mktemp -d)/d2.tar.gz"
  curl -fsSL -o "$archive" \
    "https://github.com/terrastruct/d2/releases/download/v${D2_VERSION}/d2-v${D2_VERSION}-linux-amd64.tar.gz"
  tar -xzf "$archive" -C "$(dirname "$archive")"
  install -m 0755 "$(dirname "$archive")/d2-v${D2_VERSION}/bin/d2" "$BIN/d2"
}

install_plantuml() {
  if command -v plantuml >/dev/null 2>&1; then
    echo "plantuml already installed: $(command -v plantuml)"
    return
  fi
  # Graphviz is what PlantUML lays out non-sequence diagrams with, and the
  # C4 diagrams this project emits are all of that kind.
  sudo apt-get update
  sudo apt-get install -y plantuml graphviz
}

# Structurizr publishes no standalone archive: the supported distribution is a
# container image, and only the `-playwright` variant carries the browser its
# SVG exporter drives. A thin wrapper puts `structurizr` on PATH so views.lua's
# `pandoc.pipe("structurizr", ...)` needs no knowledge of any of this. The
# wrapper mounts the caller's working directory because views.lua runs the
# export inside a Pandoc temporary directory and reads `out/` back from it.
install_structurizr() {
  if command -v structurizr >/dev/null 2>&1; then
    echo "structurizr already installed: $(command -v structurizr)"
    return
  fi
  docker pull "structurizr/structurizr:${STRUCTURIZR_VERSION}-playwright"
  cat > "$BIN/structurizr" <<WRAPPER
#!/bin/sh
exec docker run --rm \\
  --user "\$(id -u):\$(id -g)" \\
  --volume "\$PWD:/work" \\
  --workdir /work \\
  "structurizr/structurizr:${STRUCTURIZR_VERSION}-playwright" "\$@"
WRAPPER
  chmod 0755 "$BIN/structurizr"
}

install_d2
install_plantuml
install_structurizr

export PATH="$BIN:$PATH"

echo
echo "Verifying every backend resolves and runs:"
for tool in d2 plantuml structurizr; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "error: $tool is still not on PATH after provisioning" >&2
    exit 1
  }
done
# `sed -n` consumes the whole stream, unlike `head`, which would SIGPIPE the
# producer and trip pipefail on an otherwise healthy tool.
d2 --version
plantuml -version 2>&1 | sed -n '1p'
structurizr version 2>&1 | sed -n '1,2p'
