# Runtime: editor and LSP

The unsaved-edit flow: how an editor (VS Code, via `editors/vscode/`) sees diagnostics and hovers for content that has not been saved or rendered yet.

## Flow

1. The editor sends the current buffer contents to the language server as an overlay for the corresponding file, without touching the file on disk.
2. The LSP server re-parses and re-analyzes the project with that overlay substituted in place of the on-disk file, producing an updated `AnalysisSnapshot` in memory.
3. Diagnostics, hover text, and go-to-references are computed against that overlay snapshot and returned to the editor.
4. Saving the file (or closing without saving) drops the overlay; the next analysis uses the on-disk content again.

## Why the LSP does not maintain a second parser or rule engine

Per the "editor integrations remain thin" guardrail (`notes/ROADMAP.md`), the LSP server is a thin client of the same `parser.py`/`analysis.py`/`rules.py` the CLI and Quarto build use. An overlay is a substitution of *input*, not a different analysis path — this is what keeps live editor diagnostics from disagreeing with what `quarto-needs check` reports on the same content once saved.

## What this page does not cover

VS Code UI details (extension activation, command palette entries) belong in `editors/vscode/`'s own documentation, not here; this page is scoped to the semantic contract between editor and server.
