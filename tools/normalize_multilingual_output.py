#!/usr/bin/env python3
"""Normalize localized Quarto Book output filenames.

Localized source files intentionally use names such as ``components.pt-BR.qmd``.
Once BabelQuarto publishes them under ``_book/pt-BR/``, however, the locale is
already encoded by the directory. Public URLs should therefore use
``pt-BR/components.html`` rather than ``pt-BR/components.pt-BR.html``.
"""

from __future__ import annotations

import argparse
from pathlib import Path


TEXT_SUFFIXES = {".html", ".json", ".xml", ".js", ".css", ".txt"}


def localized_html_files(output: Path, locale: str) -> list[Path]:
    locale_dir = output / locale
    if not locale_dir.is_dir():
        return []
    suffix = f".{locale}.html"
    return sorted(
        path
        for path in locale_dir.rglob("*.html")
        if path.name.endswith(suffix)
    )


def normalize(output: Path, locale: str) -> int:
    output = output.resolve()
    if not output.is_dir():
        raise SystemExit(f"Output directory does not exist: {output}")

    suffix = f".{locale}.html"
    sources = localized_html_files(output, locale)

    for source in sources:
        target = source.with_name(source.name[: -len(suffix)] + ".html")
        # BabelQuarto may publish both the canonical-language copy and the
        # localized page inside the locale directory. In that case the
        # localized file is authoritative and should replace the existing
        # canonical-named file at the public locale URL.
        if target.exists():
            target.unlink()
        source.replace(target)

    # BabelQuarto writes localized filenames into navigation links, search
    # indexes and other generated text assets. Rewrite all textual references
    # after the files themselves have been renamed.
    for path in output.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = contents.replace(suffix, ".html")
        if updated != contents:
            path.write_text(updated, encoding="utf-8")

    leftovers = localized_html_files(output, locale)
    if leftovers:
        rendered = "\n".join(str(path) for path in leftovers)
        raise SystemExit(
            "Localized HTML filename normalization failed; redundant locale "
            f"suffix remains:\n{rendered}"
        )

    return len(sources)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, help="Rendered Quarto _book directory")
    parser.add_argument("--locale", default="pt-BR")
    args = parser.parse_args()

    count = normalize(args.output, args.locale)
    print(
        f"Normalized {count} localized HTML filename(s) in "
        f"{args.output} for {args.locale}."
    )


if __name__ == "__main__":
    main()
