args <- commandArgs(trailingOnly = TRUE)

# Default: publish the staged output into the parent of the book project (the
# GitHub Pages root), so docs/src -> docs/. With --in-place, publish it back
# into the project's own _book/ instead, leaving the parent untouched.
in_place <- "--in-place" %in% args
args <- setdiff(args, "--in-place")

if (length(args) != 1L) {
  stop("usage: Rscript tools/render_multilingual.R <quarto-book-path> [--in-place]", call. = FALSE)
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

if (!requireNamespace("fs", quietly = TRUE)) {
  stop("The `fs` package is required by the multilingual render wrapper.", call. = FALSE)
}

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1L) {
  stop("Cannot determine tools/render_multilingual.R location.", call. = FALSE)
}
script_path <- normalizePath(sub("^--file=", "", script_arg[[1]]), mustWork = TRUE)
repo_root <- normalizePath(file.path(dirname(script_path), ".."), mustWork = TRUE)

# Resolve relative book paths against the repository root, never the current
# working directory: invoking the wrapper from inside a book project would
# otherwise nest the output (e.g. <book>/examples/quarto-needs/_book).
if (grepl("^/", args[[1]])) {
  project_path <- normalizePath(args[[1]], mustWork = TRUE)
} else {
  project_path <- normalizePath(file.path(repo_root, args[[1]]), mustWork = TRUE)
}
output_dir <- "_book"

render_multilingual <- function(project_path) {
  # Keep the real working tree out of BabelQuarto's internal copy/merge cycle.
  # Public filename normalization is intentionally performed only after this
  # wrapper returns, by tools/normalize_multilingual_output.py from the Makefile.
  for (name in c(".quarto", output_dir)) {
    path <- file.path(project_path, name)
    if (dir.exists(path)) {
      unlink(path, recursive = TRUE, force = TRUE)
    }
  }

  staging_parent <- tempfile("quarto-needs-babel-")
  dir.create(staging_parent, recursive = TRUE)
  on.exit(unlink(staging_parent, recursive = TRUE, force = TRUE), add = TRUE)

  fs::dir_copy(project_path, staging_parent)
  staged_project <- file.path(staging_parent, basename(project_path))

  old_repo_root <- Sys.getenv("QUARTO_NEEDS_REPO_ROOT", unset = NA_character_)
  on.exit({
    if (is.na(old_repo_root)) {
      Sys.unsetenv("QUARTO_NEEDS_REPO_ROOT")
    } else {
      Sys.setenv(QUARTO_NEEDS_REPO_ROOT = old_repo_root)
    }
  }, add = TRUE)

  # The showcase pre-render hook lives inside the staged book, but its Python
  # implementation and package sources remain canonical in the original repo.
  Sys.setenv(QUARTO_NEEDS_REPO_ROOT = repo_root)

  options("babelquarto.quiet" = TRUE)
  babelquarto::render_book(project_path = staged_project, preview = FALSE)

  staged_output <- file.path(staged_project, output_dir)
  if (!dir.exists(staged_output)) {
    stop(
      sprintf("BabelQuarto completed without producing %s", staged_output),
      call. = FALSE
    )
  }

  # Publish the rendered book. Default: into the parent of the project
  # directory (the GitHub Pages root, e.g. docs/), never into the project
  # directory itself. With --in-place, into the project's own _book/. In both
  # modes the project directory holds only authored sources and is not
  # overwritten, but only the parent-publish mode clears the publish root's
  # stale entries (everything that is not the project directory itself).
  if (in_place) {
    publish_root <- file.path(project_path, output_dir)
    dir.create(publish_root, recursive = TRUE, showWarnings = FALSE)
  } else {
    publish_root <- dirname(project_path)
    src_name <- basename(project_path)
    publish_root_entries <- list.files(publish_root, all.files = TRUE, no.. = TRUE, full.names = TRUE)
    for (entry in publish_root_entries) {
      if (identical(basename(entry), src_name)) next
      unlink(entry, recursive = TRUE, force = TRUE)
    }
  }
  for (child in list.files(staged_output, all.files = TRUE, no.. = TRUE, full.names = TRUE)) {
    target <- file.path(publish_root, basename(child))
    if (dir.exists(child)) {
      fs::dir_copy(child, target)
    } else {
      fs::file_copy(child, target)
    }
  }
}

render_multilingual(project_path)
