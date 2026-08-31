from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..analysis import analyze_project
from ..config import NeedsConfig
from ..export import _write_atomic_text
from .apply_plan import MigrationApplyPlan


class MigrationApplyError(Exception):
    """Raised when an apply plan cannot be safely written to disk."""


@dataclass(frozen=True, slots=True)
class MigrationApplyResult:
    written: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {"schema": "migration-apply-result-v1", "written": list(self.written)}


def apply_migration_plan(
    root: Path,
    plan: MigrationApplyPlan,
    config: NeedsConfig,
) -> MigrationApplyResult:
    """Write every ready-create item in ``plan`` to its destination file.

    This is create-only (an existing destination file refuses the whole
    apply), all-or-nothing (any item not ``ready-create`` refuses the whole
    apply before any file is touched), and self-verifying: after every file
    is written, the project is re-scanned and any structural failure or
    error-severity finding rolls every file written in this call back before
    the error propagates. A second call against an already-applied plan is
    refused rather than duplicating or silently no-op-ing, because the
    canonical IDs it would create already exist in the project graph — that
    refusal *is* this feature's idempotence contract.
    """
    if not plan.items:
        raise MigrationApplyError("apply plan has no items to write")
    if not plan.ready:
        blocked = sorted(
            item.source_id for item in plan.items if item.status != "ready-create"
        )
        raise MigrationApplyError(
            "apply plan is not fully ready-create; refusing to write any file: "
            + ", ".join(blocked)
        )

    resolved_root = Path(root).resolve()
    destinations: dict[str, Path] = {}
    for item in plan.items:
        if item.destination_file is None or item.content_preview is None:
            raise MigrationApplyError(
                f"{item.source_id} is ready-create but missing a destination "
                "or content preview"
            )
        if item.destination_file in destinations:
            raise MigrationApplyError(
                f"destination file {item.destination_file!r} is targeted by "
                "more than one item"
            )
        path = (resolved_root / item.destination_file).resolve()
        if not path.is_relative_to(resolved_root):
            raise MigrationApplyError(
                f"destination file {item.destination_file!r} resolves outside "
                "the project root"
            )
        if path.exists():
            raise MigrationApplyError(
                f"destination file {item.destination_file!r} already exists "
                "on disk; migration is create-only"
            )
        destinations[item.destination_file] = path

    written: list[str] = []
    try:
        for item in plan.items:
            path = destinations[item.destination_file]
            _write_atomic_text(path, item.content_preview)
            written.append(item.destination_file)

        result = analyze_project(root, config=config)
        error_findings = [finding for finding in result.findings if finding.severity == "error"]
        if result.snapshot is None or error_findings:
            messages = "; ".join(
                f"{finding.code}: {finding.message}" for finding in error_findings
            ) or "the project no longer forms a valid engineering graph"
            raise MigrationApplyError(
                f"post-write scan/check failed, rolling back {len(written)} "
                f"file(s): {messages}"
            )
    except BaseException:
        for destination_file in written:
            destinations[destination_file].unlink(missing_ok=True)
        raise

    return MigrationApplyResult(written=tuple(sorted(written)))
