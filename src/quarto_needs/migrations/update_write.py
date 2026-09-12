"""Apply a reviewed migration update plan to already-migrated authored files.

Mirrors `apply_write.py`'s safety contracts for the update path: every item
is preflighted before any write (the plan must be fully ready, each matched
file must still carry the digest the plan recorded, and every block must be
locatable), writes are atomic per file, the project is re-scanned afterwards,
and any structural failure restores every touched file before the error
propagates. A stale plan is refused rather than applied to changed content.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from ..analysis import analyze_project
from ..config import NeedsConfig
from ..export import _write_atomic_text
from .apply_plan import MigrationUpdateItem, MigrationUpdatePlan


class MigrationUpdateError(Exception):
    """Raised when an update plan cannot be safely written to disk."""


@dataclass(frozen=True, slots=True)
class MigrationUpdateResult:
    updated: tuple[tuple[str, str, str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "migration-update-result-v1",
            "updated": [
                {"sourceId": source_id, "canonicalId": canonical_id, "file": file}
                for source_id, canonical_id, file in sorted(self.updated)
            ],
        }


_BLOCK_START = re.compile(r"^\s*:::\s*\{\.need\s+#(?P<id>[A-Za-z0-9_.:-]+)(?=[\s}])")


def _block_span(lines: list[str], identifier: str) -> tuple[int, int] | None:
    """The inclusive [start, end] line span of a .need block, if present."""
    for index, line in enumerate(lines):
        match = _BLOCK_START.match(line)
        if match and match.group("id") == identifier:
            for end in range(index + 1, len(lines)):
                if lines[end].strip() == ":::":
                    return (index, end)
            return None
    return None


def _updated_file(
    path: Path, items: list[MigrationUpdateItem], destination_file: str
) -> str:
    original = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    for item in items:
        if item.current_file_digest != digest:
            raise MigrationUpdateError(
                f"stale update plan: {destination_file!r} changed since the "
                "plan was built; rebuild the plan and review it again"
            )

    lines = original.splitlines(keepends=True)
    located: list[tuple[int, int, MigrationUpdateItem]] = []
    for item in items:
        span = _block_span(lines, item.canonical_id)
        if span is None:
            raise MigrationUpdateError(
                f"block #{item.canonical_id} not found in {destination_file!r}; "
                "the plan no longer matches the authored file"
            )
        located.append((span[0], span[1], item))

    # Replace from the end so earlier spans keep their line offsets.
    for start, end, item in sorted(located, reverse=True):
        assert item.content_preview is not None
        replacement = item.content_preview.splitlines(keepends=True)
        if replacement and not replacement[-1].endswith("\n"):
            replacement[-1] += "\n"
        lines[start : end + 1] = replacement
    return "".join(lines)


def apply_migration_update_plan(
    root: Path,
    plan: MigrationUpdatePlan,
    config: NeedsConfig,
) -> MigrationUpdateResult:
    """Write every ``ready-update`` item to its already-authored file."""
    if not plan.items:
        raise MigrationUpdateError("update plan has no items")
    not_ready = sorted(
        f"{item.source_id} ({item.status})"
        for item in plan.items
        if item.status not in {"ready-update", "no-change"}
    )
    if not_ready:
        raise MigrationUpdateError(
            "update plan is not fully ready; refusing to write any file: "
            + ", ".join(not_ready)
            + ". Apply ready-create items with --apply-plan --write first."
        )
    updates = [item for item in plan.items if item.status == "ready-update"]
    if not updates:
        raise MigrationUpdateError("update plan has no items to update")

    resolved_root = Path(root).resolve()
    by_file: dict[str, list[MigrationUpdateItem]] = {}
    for item in updates:
        if item.destination_file is None or item.content_preview is None:
            raise MigrationUpdateError(
                f"{item.source_id} is ready-update but missing a destination or preview"
            )
        by_file.setdefault(item.destination_file, []).append(item)

    originals: dict[Path, str] = {}
    new_texts: dict[Path, str] = {}
    for destination_file, items in sorted(by_file.items()):
        path = (resolved_root / destination_file).resolve()
        if not path.is_relative_to(resolved_root):
            raise MigrationUpdateError(
                f"destination file {destination_file!r} resolves outside the project root"
            )
        if not path.is_file():
            raise MigrationUpdateError(
                f"destination file {destination_file!r} does not exist"
            )
        originals[path] = path.read_text(encoding="utf-8")
        new_texts[path] = _updated_file(path, items, destination_file)

    updated: list[tuple[str, str, str]] = []
    try:
        for path, text in new_texts.items():
            _write_atomic_text(path, text)
        for destination_file, items in by_file.items():
            for item in items:
                updated.append((item.source_id, item.canonical_id, destination_file))

        result = analyze_project(root, config=config)
        error_findings = [
            finding for finding in result.findings if finding.severity == "error"
        ]
        if result.snapshot is None or error_findings:
            messages = "; ".join(
                f"{finding.code}: {finding.message}" for finding in error_findings
            ) or "the project no longer forms a valid engineering graph"
            raise MigrationUpdateError(
                f"post-write scan/check failed, rolling back {len(originals)} "
                f"file(s): {messages}"
            )
    except BaseException:
        for path, original in originals.items():
            path.write_text(original, encoding="utf-8")
        raise

    return MigrationUpdateResult(updated=tuple(sorted(updated)))
