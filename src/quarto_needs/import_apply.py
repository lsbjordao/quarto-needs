"""Apply an accepted import plan to the authored project files.

This is the one write path downstream of reconciliation and the reviewed
import plan. It inherits the migration apply's safety contracts and adds
updates: every applicable item (``ready-create``/``ready-update``) is
preflighted against a fresh scan of the project — stale plans refuse the
whole apply before any file is touched — writes are atomic per file, the
project is re-scanned after writing and rolled back if it no longer
forms a valid graph, and a second apply of the same plan refuses because
the created IDs already exist. Items whose disposition is not applicable
(blocked, review-required, ignored, no-change) are reported as skipped,
never half-applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .analysis import analyze_project
from .export import _write_atomic_text
from .oslc_import_plan import ImportPlanItem, OslcImportPlan
from .parser import HEADING_RE
from .snapshot import AnalysisSnapshot

_APPLICABLE = {"ready-create", "ready-update"}


class ImportApplyError(Exception):
    """Raised when an import plan cannot be safely written to disk."""


@dataclass(frozen=True, slots=True)
class ImportApplyRecord:
    """One applied plan item."""

    external_uri: str
    action: str
    canonical_id: str
    file: str

    def to_dict(self) -> dict[str, object]:
        return {
            "externalUri": self.external_uri,
            "action": self.action,
            "canonicalId": self.canonical_id,
            "file": self.file,
        }


@dataclass(frozen=True, slots=True)
class ImportApplySkip:
    """One plan item deliberately not applied, with the plan's own reason."""

    external_uri: str
    disposition: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "externalUri": self.external_uri,
            "disposition": self.disposition,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class ImportApplyResult:
    applied: tuple[ImportApplyRecord, ...]
    skipped: tuple[ImportApplySkip, ...]
    written_files: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "import-apply-result-v1",
            "applied": [record.to_dict() for record in self.applied],
            "skipped": [skip.to_dict() for skip in self.skipped],
            "writtenFiles": list(self.written_files),
        }


def _normalize_relative(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ImportApplyError(f"target path {value!r} resolves outside the project root")
    return path


def _render_create_block(item: ImportPlanItem) -> str:
    changes = dict(item.changes)
    title = str(changes["title"]["to"])
    body = str(changes["body"]["to"] or "")
    lines = [
        f'::: {{.need #{item.canonical_id} type="{item.canonical_type}"'
        f' status="{item.canonical_status}"}}',
        "",
        f"## {title}",
    ]
    if body:
        lines.extend(["", body])
    lines.append(":::")
    return "\n".join(lines) + "\n"


def _locate_need_block(text: str, object_id: str) -> tuple[int, int]:
    """Return the [start, end) character span of one .need block."""
    marker = f"::: {{.need #{object_id} "
    alternative = f"::: {{.need #{object_id}}}"
    start = text.find(marker)
    if start == -1:
        start = text.find(alternative)
    if start == -1:
        raise ImportApplyError(f"authored block for {object_id} was not found in its file")
    line_start = text.rfind("\n", 0, start) + 1
    close = text.find("\n:::", start)
    if close == -1:
        raise ImportApplyError(f"authored block for {object_id} is not closed")
    end = text.index("\n", close + 1) + 1 if "\n" in text[close + 1:] else len(text)
    return line_start, end


def _rewrite_block(block_text: str, new_title: str, new_body: str) -> str:
    """Rebuild one .need block with a new title and body, preamble intact.

    Requires the block's title to be authored as a heading (the canonical
    form); a block whose title lives in a ``title:`` metadata key refuses
    the rewrite rather than guessing at preamble surgery.
    """
    lines = block_text.split("\n")
    open_line, interior = lines[0], lines[1:-1]
    heading_index = next(
        (index for index, line in enumerate(interior) if HEADING_RE.match(line)),
        None,
    )
    if heading_index is None:
        raise ImportApplyError(
            "update requires a heading-authored block; this block carries its "
            "title in the metadata preamble"
        )
    preamble = interior[:heading_index]
    while preamble and not preamble[-1].strip():
        preamble.pop()
    rebuilt = [open_line, *preamble, "", f"## {new_title}"]
    if new_body:
        rebuilt.extend(["", new_body])
    rebuilt.append(":::")
    return "\n".join(rebuilt) + "\n"


def _current_field(record, field: str) -> str:  # type: ignore[no-untyped-def]
    return getattr(record, "title" if field == "title" else "body")


def apply_import_plan(
    root: Path,
    plan: OslcImportPlan,
    snapshot: AnalysisSnapshot,
    *,
    config,  # type: ignore[no-untyped-def]
) -> ImportApplyResult:
    """Write every applicable plan item, all-or-nothing, then self-verify.

    ``snapshot`` must be a fresh scan of the same project: preflight
    re-checks every applicable item against it (existing IDs for creates,
    unchanged ``from`` values for updates) so a plan built against an
    older graph refuses the whole apply instead of applying stale intent.
    """
    if not plan.items:
        raise ImportApplyError("import plan has no items to apply")

    applicable: list[tuple[ImportPlanItem, Path]] = []
    skipped: list[ImportApplySkip] = []
    touched_files: dict[str, ImportPlanItem] = {}
    for item in plan.items:
        if item.disposition not in _APPLICABLE:
            skipped.append(
                ImportApplySkip(
                    external_uri=item.external_uri,
                    disposition=item.disposition,
                    message=item.message,
                )
            )
            continue
        if item.target_path is None:
            raise ImportApplyError(
                f"{item.external_uri} is {item.disposition} but carries no target path"
            )
        if item.target_path in touched_files:
            raise ImportApplyError(
                f"target file {item.target_path!r} is touched by more than one item; "
                "split the plan"
            )
        touched_files[item.target_path] = item
        applicable.append((item, _normalize_relative(root, item.target_path)))

    originals: dict[Path, str | None] = {}
    records: list[ImportApplyRecord] = []
    try:
        for item, path in applicable:
            if path in originals:
                continue
            if item.disposition == "ready-create":
                assert item.canonical_id is not None
                if item.canonical_id in snapshot.objects_by_id:
                    raise ImportApplyError(
                        f"{item.external_uri} plans create of {item.canonical_id}, "
                        "which already exists in the current graph; the plan is stale "
                        "or was already applied"
                    )
                text = path.read_text(encoding="utf-8") if path.exists() else None
                block = _render_create_block(item)
                new_text = (
                    (text.rstrip("\n") + "\n\n" + block) if text is not None else block
                )
            else:
                assert item.canonical_id is not None
                record = snapshot.objects_by_id.get(item.canonical_id)
                if record is None:
                    raise ImportApplyError(
                        f"{item.external_uri} plans update of {item.canonical_id}, "
                        "which is not present in the current graph; the plan is stale"
                    )
                if not record.locations:
                    raise ImportApplyError(
                        f"{item.canonical_id} has no authored location to update"
                    )
                authored_file = record.locations[0].file
                if item.target_path != authored_file:
                    raise ImportApplyError(
                        f"{item.canonical_id} is authored in {authored_file!r} but the "
                        f"plan targets {item.target_path!r}; refusing the mismatch"
                    )
                changes = dict(item.changes)
                for field, change in changes.items():
                    expected_from = str(change["from"])
                    if _current_field(record, field) != expected_from:
                        raise ImportApplyError(
                            f"{item.canonical_id}'s {field} changed since the plan was "
                            f"built (plan from-value {expected_from!r}); the plan is stale"
                        )
                text = path.read_text(encoding="utf-8")
                start, end = _locate_need_block(text, item.canonical_id)
                new_title = str(changes.get("title", {"to": record.title})["to"])
                new_body = str(changes.get("body", {"to": record.body})["to"])
                new_text = text[:start] + _rewrite_block(
                    text[start:end], new_title, new_body
                ) + text[end:]
            originals[path] = path.read_text(encoding="utf-8") if path.exists() else None
            _write_atomic_text(path, new_text)
            assert item.canonical_id is not None
            records.append(
                ImportApplyRecord(
                    external_uri=item.external_uri,
                    action=item.disposition,
                    canonical_id=item.canonical_id,
                    file=item.target_path or "",
                )
            )

        failure = _post_write_failure(root, config)
        if failure is not None:
            raise ImportApplyError(failure)
    except BaseException:
        for path, original in originals.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                _write_atomic_text(path, original)
        raise

    return ImportApplyResult(
        applied=tuple(records),
        skipped=tuple(skipped),
        written_files=tuple(sorted(str(path) for path in originals)),
    )


def _post_write_failure(root: Path, config) -> str | None:  # type: ignore[no-untyped-def]
    """Re-scan the project; return a failure message if it is no longer valid."""
    result = analyze_project(root, config=config)
    error_findings = [
        finding for finding in (result.findings or ()) if finding.severity == "error"
    ]
    if result.snapshot is None or error_findings:
        messages = "; ".join(
            f"{finding.code}: {finding.message}" for finding in error_findings
        ) or "the project no longer forms a valid engineering graph"
        return f"post-write scan/check failed: {messages}"
    return None
