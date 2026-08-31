from __future__ import annotations

import argparse
import hashlib
import tempfile
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render(svg: Path, target: Path, size: int) -> None:
    try:
        import cairosvg
        from PIL import Image
    except ImportError as error:  # pragma: no cover - developer tooling guard
        raise SystemExit(
            "branding tooling is not installed; run `make setup-branding` first"
        ) from error

    with tempfile.TemporaryDirectory(prefix="quarto-needs-branding-") as tmp:
        raw = Path(tmp) / "icon.png"
        cairosvg.svg2png(
            url=str(svg),
            write_to=str(raw),
            output_width=size,
            output_height=size,
        )
        image = Image.open(raw).convert("RGBA")
        # Palette quantization keeps packaged extension assets compact while
        # preserving transparency and deterministic source-derived artwork.
        image = image.quantize(colors=96, method=Image.Quantize.FASTOCTREE)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, optimize=True)


def _expected(root: Path) -> tuple[tuple[Path, int], ...]:
    branding = root / "docs" / "assets" / "branding"
    return (
        (branding / "quarto-needs-app-icon-256.png", 256),
        (branding / "quarto-needs-app-icon-512.png", 512),
        (root / "editors" / "vscode" / "icon.png", 256),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate or verify raster app-icon derivatives from the canonical SVG."
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    svg = root / "docs" / "assets" / "branding" / "quarto-needs-app-icon.svg"
    if not svg.exists():
        raise SystemExit(f"canonical branding source is missing: {svg}")

    if not args.check:
        for target, size in _expected(root):
            _render(svg, target, size)
        print("Regenerated Quarto-Needs app icon derivatives from the canonical SVG.")
        return 0

    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="quarto-needs-branding-check-") as tmp:
        temp_root = Path(tmp)
        generated: dict[int, Path] = {}
        for size in (256, 512):
            target = temp_root / f"icon-{size}.png"
            _render(svg, target, size)
            generated[size] = target

        for target, size in _expected(root):
            if not target.exists():
                failures.append(f"missing derived asset: {target.relative_to(root)}")
                continue
            if target.read_bytes() != generated[size].read_bytes():
                failures.append(
                    f"stale derived asset: {target.relative_to(root)} "
                    f"(actual sha256={_sha256(target)}, expected sha256={_sha256(generated[size])})"
                )

    if failures:
        for failure in failures:
            print(failure)
        print("Run `make branding-assets` to regenerate the derived assets.")
        return 1

    print("Branding derivatives match the canonical SVG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
