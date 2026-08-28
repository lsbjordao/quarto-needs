args <- commandArgs(trailingOnly = TRUE)

if (length(args) != 1L) {
  stop("usage: Rscript tools/render_multilingual.R <quarto-book-path>", call. = FALSE)
}

if (!requireNamespace("babelquarto", quietly = TRUE)) {
  stop(
    paste(
      "babelquarto is required.",
      "Run `make setup-babelquarto` before rendering multilingual books."
    ),
    call. = FALSE
  )
}

project_path <- normalizePath(args[[1]], mustWork = TRUE)
repo_root <- normalizePath(".", mustWork = TRUE)

# BabelQuarto renders a staged copy of the book. Export the original repository
# root so project-local hooks can still reach the canonical Python package and
# pre-render implementation without relying on paths that escape the staged
# project directory.
Sys.setenv(QUARTO_NEEDS_REPO_ROOT = repo_root)

# Quarto's transient state can be surprisingly large and may itself contain
# nested session directories from interrupted renders. Never copy that state
# into the BabelQuarto staging area; it is reproducible and safe to discard.
for (name in c(".quarto", "_book")) {
  path <- file.path(project_path, name)
  if (dir.exists(path)) {
    unlink(path, recursive = TRUE, force = TRUE)
  }
}

options("babelquarto.quiet" = TRUE)
babelquarto::render_book(project_path = project_path, preview = FALSE)
