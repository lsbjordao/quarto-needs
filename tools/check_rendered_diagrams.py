"""Fail the build when a C4 backend silently fell back to its DSL source.

``need-c4``'s optional backends are fail-soft by design: when PlantUML, D2 or
Structurizr is missing, ``c4.lua`` emits a syntax-highlighted code block and
the render still succeeds. That is right for an author who never installed
them and wrong for a publishing pipeline, because the degradation is silent --
it is how the published example came to show DSL source under "Additional C4
diagram backends" while every local render showed diagrams.

This check compares what each chapter asked for against what was rendered, so
a backend that disappears from the render environment breaks the build instead
of quietly republishing source code.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The fallback in c4.lua emits `pandoc.CodeBlock(source, {language})`, where the
# language is the backend name. Both patterns match a whole class token rather
# than a substring, so neither a compound class (d2's own `d2-svg`) nor an
# inlined stylesheet rule can be mistaken for rendered output.
FALLBACK = re.compile(
    r'<pre class="(?:[^"]*\s)?(structurizr|plantuml|d2)(?:\s[^"]*)?"'
)
# Every rendered diagram is wrapped in this div, whatever the backend.
FIGURE = re.compile(r'class="(?:[^"]*\s)?need-c4-scroll(?:\s[^"]*)?"')
# `level="code"` renders a table rather than a diagram, so it expects no figure.
SHORTCODE = re.compile(r"\{\{<\s*need-c4\s+([^>]*?)>\}\}")
CODE_LEVEL = re.compile(r'level\s*=\s*"code"')


def source_for(page: Path, book: Path, source_root: Path) -> Path | None:
    """Map a rendered page back to the .qmd it came from, across both locales."""
    relative = page.relative_to(book)
    if len(relative.parts) == 1:
        return source_root / f"{page.stem}.qmd"
    locale = relative.parts[0]
    if len(relative.parts) == 2:
        return source_root / f"{page.stem}.{locale}.qmd"
    return None


def expected_figures(qmd: Path) -> int:
    return sum(
        0 if CODE_LEVEL.search(arguments) else 1
        for arguments in SHORTCODE.findall(qmd.read_text(encoding="utf-8"))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("book", type=Path, help="rendered book directory")
    parser.add_argument(
        "--source", type=Path, required=True, help="directory holding the .qmd sources"
    )
    arguments = parser.parse_args()

    book: Path = arguments.book.resolve()
    source_root: Path = arguments.source.resolve()
    if not book.is_dir():
        print(f"error: rendered book not found: {book}", file=sys.stderr)
        return 2

    failures: list[str] = []
    checked = 0
    for page in sorted(book.rglob("*.html")):
        qmd = source_for(page, book, source_root)
        if qmd is None or not qmd.is_file():
            continue
        html = page.read_text(encoding="utf-8", errors="replace")
        relative = page.relative_to(book)

        fell_back = sorted(set(FALLBACK.findall(html)))
        if fell_back:
            failures.append(
                f"{relative}: {', '.join(fell_back)} fell back to DSL source; "
                "install the backend CLI (tools/install_diagram_backends.sh)"
            )

        wanted = expected_figures(qmd)
        rendered = len(FIGURE.findall(html))
        if rendered != wanted:
            failures.append(
                f"{relative}: {qmd.name} asks for {wanted} C4 diagram(s), "
                f"{rendered} rendered"
            )
        checked += 1

    if not checked:
        print(f"error: no rendered page matched a source in {source_root}", file=sys.stderr)
        return 2
    for failure in failures:
        print(f"error: {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"Every C4 diagram rendered across {checked} page(s) in {book}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
