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

if (!requireNamespace("fs", quietly = TRUE)) {
  stop("The `fs` package is required by the multilingual render wrapper.", call. = FALSE)
}

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
if (length(script_arg) != 1L) {
  stop("Cannot determine tools/render_multilingual.R location.", call. = FALSE)
}
script_path <- normalizePath(sub("^--file=", "", script_arg[[1]]), mustWork = TRUE)
repo_root <- normalizePath(file.path(dirname(script_path), ".."), mustWork = TRUE)
project_path <- normalizePath(args[[1]], mustWork = TRUE)
output_dir <- "_book"

render_multilingual <- function(project_path) {
  # Keep the real working tree out of BabelQuarto's internal copy/merge cycle.
  # This also prevents an interrupted or concurrently recreated _book from
  # colliding with fs::dir_copy() when BabelQuarto publishes its staged result.
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

  final_output <- file.path(project_path, output_dir)
  if (dir.exists(final_output)) {
    unlink(final_output, recursive = TRUE, force = TRUE)
  }
  fs::dir_copy(staged_output, final_output)
}

render_multilingual(project_path)
