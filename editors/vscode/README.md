# Quarto-Needs for VS Code

This directory contains the **thin VS Code client** for the Quarto-Needs language server.

It does not parse `.qmd` engineering declarations, resolve relations, evaluate policies, compute coverage, or maintain an editor-specific engineering graph. Those responsibilities remain in the Python semantic core.

## Architecture

```text
VS Code document
      │
      ▼
vscode-languageclient
      │ stdio / LSP
      ▼
quarto-needs --root <workspace> lsp
      │
      ▼
Python parser + analyzer + LanguageService
```

The extension starts one language-server process per workspace folder containing `.quarto-needs.toml`.

## Development

```bash
cd editors/vscode
npm install
npm run check
npm run compile
```

The command used to start the server is configurable as `quartoNeeds.server.command` and defaults to `quarto-needs`. This allows development environments to point the client at an executable inside a virtual environment without embedding environment-specific paths in the extension.

Additional server arguments can be supplied through `quartoNeeds.server.extraArgs`. They are inserted before the final `lsp` subcommand.

## Commands

- **Quarto-Needs: Restart Language Server**
- **Quarto-Needs: Show Language Server Output**

## Document selection

The client connects `.qmd` files recognized by VS Code as either `quarto` or `markdown`. All language intelligence is provided by the server.
