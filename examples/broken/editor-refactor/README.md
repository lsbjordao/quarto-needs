# Editor / refactor failure

A refactor that would collide. In the editor, the author renames `REQ-2` to
`REQ-1` in an unsaved buffer — merging two requirements into one by giving
them the same identifier. The rename has not touched disk yet; the failure is
caught in memory or it becomes an invalid graph on disk.

## The mistake

Assuming a rename is always safe because the editor offers one. A rename onto
an identifier that already exists is not a merge; it is an attempt to mint the
same canonical ID twice. On disk that would be a `REQ004` duplicate — the
snapshot is refused and nothing renders.

## What the engine does

In the editor (or with a JSON-RPC probe):

```bash
quarto-needs --root examples/broken/editor-refactor lsp
```

`textDocument/rename` at the `REQ-2` declaration with `newName: "REQ-1"`
refuses with the canonical message
`Cannot rename REQ-2 to existing object ID REQ-1` (`-32603`), the same
diagnostic vocabulary the engine uses everywhere else. A rename onto a free
identifier returns the full edit — every declaration and reference — because
refactoring to a *new* ID is safe and still relation-aware.