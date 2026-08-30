from __future__ import annotations

import json
from pathlib import Path

from .parser import LOCALIZED_QMD_RE, parse_qmd_declarations


def _relation_signature(declaration) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((relation.authored_name, relation.target) for relation in declaration.relations)
    )


def semantic_signature(declaration) -> tuple[object, ...]:
    """Return engineering fields that translations must not change.

    Title, body, and rationale are presentation text and are intentionally
    excluded. Every field consumed by the canonical engineering model remains
    invariant across localized siblings.
    """
    return (
        declaration.id,
        declaration.type,
        declaration.status,
        declaration.attributes,
        _relation_signature(declaration),
    )


def validate_localized_pair(
    canonical: Path,
    translated: Path,
    project_root: Path,
) -> dict[str, str]:
    """Validate one localized QMD sibling and return translated titles by ID."""
    canonical_batch = parse_qmd_declarations(canonical, project_root)
    translated_batch = parse_qmd_declarations(translated, project_root)
    canonical_by_id = {item.id: item for item in canonical_batch.declarations}
    translated_by_id = {item.id: item for item in translated_batch.declarations}

    if set(canonical_by_id) != set(translated_by_id):
        raise RuntimeError(
            f"Localized source {translated.relative_to(project_root)} changes engineering object IDs relative to "
            f"{canonical.relative_to(project_root)}"
        )
    titles: dict[str, str] = {}
    for object_id, localized in translated_by_id.items():
        if semantic_signature(canonical_by_id[object_id]) != semantic_signature(localized):
            raise RuntimeError(
                f"Localized source {translated.relative_to(project_root)} changes semantic metadata for {object_id}; "
                "translations may change only presentation text"
            )
        titles[object_id] = localized.title
    return titles


def collect_localized_projections(project_root: Path) -> dict[str, dict[str, str]]:
    """Validate localized siblings and collect presentation-only title maps."""
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
        bucket = localized.setdefault(locale, {})
        for object_id, title in validate_localized_pair(canonical, path, project_root).items():
            if object_id in bucket:
                raise RuntimeError(f"Duplicate localized title for {object_id} in locale {locale}")
            bucket[object_id] = title
    return localized


def write_localized_projections(project_root: Path) -> dict[str, dict[str, str]]:
    """Validate localized sources and write deterministic presentation projections."""
    localized = collect_localized_projections(project_root)
    output = project_root / ".quarto-needs" / "i18n"
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("*.json"):
        old.unlink()
    for locale, titles in sorted(localized.items()):
        (output / f"{locale}.json").write_text(
            json.dumps({"locale": locale, "titles": titles}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return localized
