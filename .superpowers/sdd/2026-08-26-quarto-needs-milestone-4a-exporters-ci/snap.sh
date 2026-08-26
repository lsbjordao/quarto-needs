#!/bin/bash
# Capture the reviewable source tree. Replaces git commits for review ranges,
# because this workspace has no Git metadata.
set -euo pipefail
DEST="$1"
rm -rf "$DEST"
mkdir -p "$DEST"
rsync -a \
  --exclude '.venv/' --exclude '__pycache__/' --exclude '.pytest_cache/' \
  --exclude '.superpowers/' --exclude '*.egg-info/' \
  --exclude 'examples/book/_book/' --exclude 'examples/book/.quarto/' \
  --exclude 'examples/book/*_files/' \
  --include 'src/***' --include 'tests/***' --include 'schemas/***' \
  --include 'tools/***' --include '_extensions/***' \
  --include 'examples/book/**' \
  --include 'docs/***' \
  --include 'Makefile' --include 'pyproject.toml' \
  --include 'README.md' --include 'ARCHITECTURE.md' --include 'CONTRIBUTING.md' \
  --include '*/' --exclude '*' \
  ./ "$DEST/"
