"""Zero-install pre-render entry point for a Quarto project."""
import json
import os
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path.cwd().resolve()
GENERATED_INDEX = Path("generated-index.lua")
sys.path.insert(0, str(REPO_ROOT / "src"))

from quarto_needs.cli import build  # noqa: E402
from quarto_needs.parser import (  # noqa: E402
    LOCALIZED_QMD_RE,
    parse_qmd_declarations,
)


def sync_extension(project_root: Path) -> None:
    """Install all canonical extension assets except the generated lookup index."""
    source = REPO_ROOT / "_extensions" / "quarto-needs"
    target = project_root / "_extensions" / "quarto-needs"
    if target.is_symlink() or target.parent.is_symlink():
        raise RuntimeError(f"Refusing to synchronize extension through symlink: {target}")
    target.mkdir(parents=True, exist_ok=True)

    source_files = {
        path.relative_to(source)
        for path in source.rglob("*")
        if path.is_file() and path.relative_to(source) != GENERATED_INDEX
    }
    source_directories = {
        path.relative_to(source)
        for path in source.rglob("*")
        if path.is_dir()
    }

    for target_path, directories, filenames in os.walk(target, topdown=False, followlinks=False):
        current = Path(target_path)
        for name in filenames:
            installed = current / name
            relative = installed.relative_to(target)
            if relative == GENERATED_INDEX:
                if installed.is_symlink():
                    raise RuntimeError(f"Refusing to use generated index symlink: {installed}")
                continue
            if installed.is_symlink() or relative not in source_files:
                installed.unlink()
        for name in directories:
            installed = current / name
            relative = installed.relative_to(target)
            if installed.is_symlink():
                installed.unlink()
            elif relative not in source_directories:
                installed.rmdir()

    for source_path in source.rglob("*"):
        if not source_path.is_file() or source_path.relative_to(source) == GENERATED_INDEX:
            continue
        target_path = target / source_path.relative_to(source)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def _relation_signature(declaration) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((relation.authored_name, relation.target) for relation in declaration.relations)
    )


def _semantic_signature(declaration) -> tuple[object, ...]:
    """Fields that translations must not change.

    Title, body and rationale are intentionally excluded. Everything used by the
    engineering model remains invariant across localized presentation sources.
    """
    return (
        declaration.id,
        declaration.type,
        declaration.status,
        declaration.attributes,
        _relation_signature(declaration),
    )


def write_localized_projections(project_root: Path) -> None:
    """Validate localized siblings and emit presentation-only title projections."""
    localized: dict[str, dict[str, str]] = {}
    for path in sorted(project_root.rglob("*.qmd")):
        relative = path.relative_to(project_root)
        if any(part.startswith(".") or part.startswith("_") for part in relative.parts[:-1]):
            continue
        match = LOCALIZED_QMD_RE.match(path.name)
        if match is None:
            continue
        canonical = path.with_name(f"{match.group('stem')}.qmd")
        if not canonical.is_file():
            continue

        locale = match.group("locale")
        canonical_batch = parse_qmd_declarations(canonical, project_root)
        translated_batch = parse_qmd_declarations(path, project_root)
        canonical_by_id = {item.id: item for item in canonical_batch.declarations}
        translated_by_id = {item.id: item for item in translated_batch.declarations}

        if set(canonical_by_id) != set(translated_by_id):
            raise RuntimeError(
                f"Localized source {relative} changes engineering object IDs relative to "
                f"{canonical.relative_to(project_root)}"
            )
        for object_id, translated in translated_by_id.items():
            if _semantic_signature(canonical_by_id[object_id]) != _semantic_signature(translated):
                raise RuntimeError(
                    f"Localized source {relative} changes semantic metadata for {object_id}; "
                    "translations may change only presentation text"
                )
            bucket = localized.setdefault(locale, {})
            if object_id in bucket:
                raise RuntimeError(f"Duplicate localized title for {object_id} in locale {locale}")
            bucket[object_id] = translated.title

    output = project_root / ".quarto-needs" / "i18n"
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("*.json"):
        old.unlink()
    for locale, titles in localized.items():
        (output / f"{locale}.json").write_text(
            json.dumps({"locale": locale, "titles": titles}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    sync_extension(PROJECT_ROOT)
    result = build(PROJECT_ROOT, quiet=False)
    if result != 0:
        return result
    write_localized_projections(PROJECT_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
