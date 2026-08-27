from __future__ import annotations

import csv
import io
from pathlib import Path

from ..diagnostics import Finding
from ..export import _write_atomic_text
from ..snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord

OBJECT_COLUMNS = (
    "id",
    "type",
    "title",
    "status",
    "priority",
    "tags",
    "body",
    "rationale",
)
RELATION_COLUMNS = ("source", "authored_name", "target", "semantic_family")
FINDING_COLUMNS = ("code", "severity", "object_id", "message", "file", "line")

# A cell whose text starts with one of these characters would be interpreted
# as a formula by spreadsheet applications (CSV injection), so it is prefixed
# with an apostrophe, which spreadsheets render as literal text.
_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _neutralize(value: object) -> str:
    text = str(value)
    if text.startswith(_DANGEROUS_PREFIXES):
        return f"'{text}"
    return text


def _row_key(row: dict[str, str], columns: tuple[str, ...]) -> tuple[str, ...]:
    # Case-insensitive by the leading (identifying) field, then by each
    # remaining field, with the raw spelling breaking casefold ties.
    return tuple(
        part
        for column in columns
        for part in (row[column].casefold(), row[column])
    )


def _render(columns: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(columns)
    for row in sorted(rows, key=lambda item: _row_key(item, columns)):
        writer.writerow([_neutralize(row[column]) for column in columns])
    return buffer.getvalue()


def _object_row(item: ObjectRecord) -> dict[str, str]:
    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "status": item.status,
        "priority": item.priority or "",
        "tags": ";".join(item.tags),
        "body": item.body,
        "rationale": item.rationale,
    }


def _relation_row(item: RelationRecord) -> dict[str, str]:
    return {
        "source": item.source,
        "authored_name": item.authored_name,
        "target": item.target,
        "semantic_family": item.semantic_family,
    }


def _finding_row(item: Finding) -> dict[str, str]:
    location = item.location
    return {
        "code": item.code,
        "severity": item.severity,
        "object_id": item.object_id or "",
        "message": item.message,
        "file": location.file if location is not None else "",
        "line": str(location.line) if location is not None else "",
    }


def render_objects(snapshot: AnalysisSnapshot) -> str:
    return _render(OBJECT_COLUMNS, [_object_row(item) for item in snapshot.objects])


def render_relations(snapshot: AnalysisSnapshot) -> str:
    return _render(
        RELATION_COLUMNS, [_relation_row(item) for item in snapshot.relations]
    )


def render_findings(snapshot: AnalysisSnapshot) -> str:
    return _render(
        FINDING_COLUMNS, [_finding_row(item) for item in snapshot.findings]
    )


def write_all(directory: Path, snapshot: AnalysisSnapshot) -> tuple[Path, ...]:
    rendered = {
        "findings.csv": render_findings(snapshot),
        "objects.csv": render_objects(snapshot),
        "relations.csv": render_relations(snapshot),
    }
    written: list[Path] = []
    for name in sorted(rendered):
        path = Path(directory) / name
        _write_atomic_text(path, rendered[name])
        written.append(path)
    return tuple(written)
