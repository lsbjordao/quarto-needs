#!/usr/bin/env python3
"""Normalize localized Quarto Book output paths.

Localized source files intentionally use names such as ``components.pt-BR.qmd``.
Once BabelQuarto publishes them under ``_book/pt-BR/``, however, the locale is
already encoded by the directory. Public output should therefore use paths such
as ``pt-BR/components.html`` and ``pt-BR/components_files/`` rather than leaking
the source naming convention as ``components.pt-BR.html`` or
``components.pt-BR_files/``.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


TEXT_SUFFIXES = {".html", ".json", ".xml", ".js", ".css", ".txt"}


def locale_dir(output: Path, locale: str) -> Path:
    return output / locale


def localized_html_files(output: Path, locale: str) -> list[Path]:
    root = locale_dir(output, locale)
    if not root.is_dir():
        return []
    suffix = f".{locale}.html"
    return sorted(
        path
        for path in root.rglob("*.html")
        if path.name.endswith(suffix)
    )


def localized_resource_dirs(output: Path, locale: str) -> list[Path]:
    root = locale_dir(output, locale)
    if not root.is_dir():
        return []
    suffix = f".{locale}_files"
    return sorted(
        (path for path in root.rglob("*") if path.is_dir() and path.name.endswith(suffix)),
        key=lambda path: len(path.parts),
        reverse=True,
    )


def remove_existing(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def normalize(output: Path, locale: str) -> tuple[int, int]:
    output = output.resolve()
    if not output.is_dir():
        raise SystemExit(f"Output directory does not exist: {output}")

    html_suffix = f".{locale}.html"
    resource_suffix = f".{locale}_files"

    html_sources = localized_html_files(output, locale)
    for source in html_sources:
        target = source.with_name(source.name[: -len(html_suffix)] + ".html")
        # BabelQuarto may publish both the canonical-language copy and the
        # localized page inside the locale directory. The localized page is
        # authoritative at the public locale URL.
        remove_existing(target)
        source.replace(target)

    resource_sources = localized_resource_dirs(output, locale)
    for source in resource_sources:
        target = source.with_name(source.name[: -len(resource_suffix)] + "_files")
        # The localized resource directory must accompany the localized page at
        # its canonical public basename. If BabelQuarto copied an English
        # resource directory here as well, the localized directory wins.
        remove_existing(target)
        source.replace(target)

    # BabelQuarto writes source-derived names into navigation, page HTML, search
    # indexes and other generated textual assets. Rewrite references after the
    # filesystem paths themselves have been normalized.
    replacements = (
        (html_suffix, ".html"),
        (resource_suffix, "_files"),
    )
    for path in output.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = contents
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != contents:
            path.write_text(updated, encoding="utf-8")

    html_leftovers = localized_html_files(output, locale)
    resource_leftovers = localized_resource_dirs(output, locale)
    if html_leftovers or resource_leftovers:
        rendered = "\n".join(
            str(path) for path in [*html_leftovers, *resource_leftovers]
        )
        raise SystemExit(
            "Localized output normalization failed; redundant locale suffix "
            f"remains:\n{rendered}"
        )

    return len(html_sources), len(resource_sources)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, help="Rendered Quarto _book directory")
    parser.add_argument("--locale", default="pt-BR")
    args = parser.parse_args()

    html_count, resource_count = normalize(args.output, args.locale)
    print(
        f"Normalized {html_count} localized HTML filename(s) and "
        f"{resource_count} localized resource directorie(s) in "
        f"{args.output} for {args.locale}."
    )


if __name__ == "__main__":
    main()
