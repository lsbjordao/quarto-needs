"""Apply a reviewed migration update plan to already-migrated authored files.

Mirrors `apply_write.py`'s safety contracts for the sync path: every item is
preflighted before any write (the plan must be fully ready, each updated
block's file must still carry the digest the plan recorded, each create's
canonical ID must still be absent, and every destination must be safe), writes
are atomic per file, the project is re-scanned afterwards, and any structural
failure restores every touched file — or removes every file this call created
— before the error propagates. A stale plan is refused rather than applied to
changed content.

The plan's `ready-create` items are applied here too: an upstream source that
gained an item is part of the same reviewed sync, and sending the user to the
first-migration create path would refuse anyway because the already-migrated
IDs collide there.
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
    applied: tuple[tuple[str, str, str, str], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "migration-update-result-v1",
            "updated": [
                {
                    "sourceId": source_id,
                    "canonicalId": canonical_id,
                    "file": file,
                    "action": action,
                }
                for source_id, canonical_id, file, action in sorted(self.applied)
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


def _apply_updates(
    lines: list[str], items: list[MigrationUpdateItem], destination_file: str
) -> None:
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


def _append_creates(text: str, items: list[MigrationUpdateItem]) -> str:
    for item in items:
        assert item.content_preview is not None
        preview = item.content_preview.strip("\n")
        if text.strip():
            text = text.rstrip("\n") + "\n\n" + preview + "\n"
        else:
            text = preview + "\n"
    return text


def _file_text(
    path: Path,
    *,
    destination_file: str,
    updates: list[MigrationUpdateItem],
    creates: list[MigrationUpdateItem],
) -> str:
    if updates and not path.is_file():
        raise MigrationUpdateError(
            f"destination file {destination_file!r} does not exist"
        )
    if path.is_file():
        original = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for item in updates:
            if item.current_file_digest != digest:
                raise MigrationUpdateError(
                    f"stale update plan: {destination_file!r} changed since the "
                    "plan was built; rebuild the plan and review it again"
                )
    else:
        original = ""

    lines = original.splitlines(keepends=True)
    if updates:
        _apply_updates(lines, updates, destination_file)
    return _append_creates("".join(lines), creates)


def apply_migration_update_plan(
    root: Path,
    plan: MigrationUpdatePlan,
    config: NeedsConfig,
) -> MigrationUpdateResult:
    """Apply every ready-create and ready-update item in one reviewed sync."""
    if not plan.items:
        raise MigrationUpdateError("update plan has no items")
    not_ready = sorted(
        f"{item.source_id} ({item.status})"
        for item in plan.items
        if item.status not in {"ready-create", "ready-update", "no-change"}
    )
    if not_ready:
        raise MigrationUpdateError(
            "update plan is not fully ready; refusing to write any file: "
            + ", ".join(not_ready)
            + ". Add the missing destinations or mappings and rebuild the plan."
        )
    updates = [item for item in plan.items if item.status == "ready-update"]
    creates = [item for item in plan.items if item.status == "ready-create"]
    if not updates and not creates:
        raise MigrationUpdateError("update plan has no items to apply")

    create_ids = sorted(item.canonical_id for item in creates)
    if len(set(create_ids)) != len(create_ids):
        raise MigrationUpdateError(
            "update plan proposes the same canonical ID more than once: "
            + ", ".join(sorted({value for value in create_ids if create_ids.count(value) > 1}))
        )

    resolved_root = Path(root).resolve()
    preflight = analyze_project(root, config=config)
    if preflight.snapshot is None:
        raise MigrationUpdateError(
            "the project does not currently form a valid engineering graph; "
            "refusing to write any file"
        )
    existing = set(preflight.snapshot.objects_by_id)
    for item in creates:
        if item.canonical_id in existing:
            raise MigrationUpdateError(
                f"canonical ID {item.canonical_id!r} already exists; "
                "rebuild the plan and review it again"
            )

    updates_by_file: dict[str, list[MigrationUpdateItem]] = {}
    creates_by_file: dict[str, list[MigrationUpdateItem]] = {}
    for item in plan.items:
        if item.status == "no-change":
            continue
        if item.destination_file is None or item.content_preview is None:
            raise MigrationUpdateError(
                f"{item.source_id} is {item.status} but missing a destination or preview"
            )
        target = (
            updates_by_file if item.status == "ready-update" else creates_by_file
        )
        target.setdefault(item.destination_file, []).append(item)

    originals: dict[Path, str | None] = {}
    new_texts: dict[Path, str] = {}
    for destination_file in sorted(set(updates_by_file) | set(creates_by_file)):
        path = (resolved_root / destination_file).resolve()
        if not path.is_relative_to(resolved_root):
            raise MigrationUpdateError(
                f"destination file {destination_file!r} resolves outside the project root"
            )
        originals[path] = path.read_text(encoding="utf-8") if path.is_file() else None
        new_texts[path] = _file_text(
            path,
            destination_file=destination_file,
            updates=updates_by_file.get(destination_file, []),
            creates=sorted(
                creates_by_file.get(destination_file, []),
                key=lambda item: (item.canonical_id.casefold(), item.canonical_id),
            ),
        )

    applied: list[tuple[str, str, str, str]] = []
    try:
        for path, text in new_texts.items():
            _write_atomic_text(path, text)
        for item in plan.items:
            if item.status in {"ready-create", "ready-update"}:
                applied.append(
                    (item.source_id, item.canonical_id, item.destination_file or "", item.status)
                )

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
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(original, encoding="utf-8")
        raise

    return MigrationUpdateResult(applied=tuple(sorted(applied)))
