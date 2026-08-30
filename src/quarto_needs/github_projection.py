"""GitHub-compatible projections over canonical PR change intelligence.

This module does not call GitHub APIs. It emits portable surfaces that a
workflow can consume: step-summary Markdown, workflow command annotations, and
a structured check summary. GitHub remains a projection target, never semantic
authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .pr_report import PullRequestReport, render_markdown
from .snapshot import AnalysisSnapshot

SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class GitHubProjection:
    summary_markdown: str
    annotations: tuple[Mapping[str, object], ...]
    check: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            "stepSummary": self.summary_markdown,
            "annotations": [dict(item) for item in self.annotations],
            "check": dict(self.check),
        }


def _location(snapshot: AnalysisSnapshot, object_id: str | None) -> tuple[str | None, int | None]:
    if not object_id:
        return None, None
    record = snapshot.objects_by_id.get(object_id)
    if record is None or not record.locations:
        return None, None
    location = record.locations[0]
    return location.file, location.line


def _url(model_url: str | None, object_id: str | None) -> str | None:
    if not model_url or not object_id:
        return None
    return model_url.rstrip("#") + "#" + object_id


def _annotation(
    *,
    level: str,
    title: str,
    message: str,
    snapshot: AnalysisSnapshot,
    object_id: str | None = None,
    model_url: str | None = None,
) -> dict[str, object]:
    file_name, line = _location(snapshot, object_id)
    item: dict[str, object] = {
        "level": level,
        "title": title,
        "message": message,
    }
    if object_id:
        item["objectId"] = object_id
    if file_name:
        item["file"] = file_name
    if line is not None:
        item["line"] = line
    target_url = _url(model_url, object_id)
    if target_url:
        item["url"] = target_url
    return item


def build(
    report: PullRequestReport,
    snapshot: AnalysisSnapshot,
    *,
    model_url: str | None = None,
) -> GitHubProjection:
    annotations: list[dict[str, object]] = []

    severity_level = {"error": "error", "warning": "warning", "info": "notice"}
    for finding in report.findings_added:
        object_id = str(finding.get("object_id")) if finding.get("object_id") else None
        severity = str(finding.get("severity") or "warning")
        annotations.append(
            _annotation(
                level=severity_level.get(severity, "warning"),
                title=f"Quarto-Needs {finding.get('code', 'finding')}",
                message=str(finding.get("message") or "New engineering finding"),
                snapshot=snapshot,
                object_id=object_id,
                model_url=model_url,
            )
        )

    for claim in report.suspect_claims:
        object_id = str(claim["id"])
        annotations.append(
            _annotation(
                level="warning",
                title=f"Suspect traceability: {object_id}",
                message=f"Re-review required: {claim['witness']}",
                snapshot=snapshot,
                object_id=object_id,
                model_url=model_url,
            )
        )

    for gate in report.gate_regressions:
        annotations.append(
            _annotation(
                level="error",
                title=f"Quality gate regression: {gate.get('name')}",
                message=(
                    f"Gate regressed: threshold={gate.get('threshold')} "
                    f"actual={gate.get('actual')}"
                ),
                snapshot=snapshot,
                model_url=model_url,
            )
        )

    annotations.sort(
        key=lambda item: (
            {"error": 0, "warning": 1, "notice": 2}.get(str(item["level"]), 3),
            str(item.get("file") or "").casefold(),
            int(item.get("line") or 0),
            str(item["title"]).casefold(),
        )
    )

    error_findings = sum(
        1 for item in report.findings_added if str(item.get("severity")) == "error"
    )
    if report.gate_regressions or error_findings:
        conclusion = "failure"
    elif report.suspect_claims or report.findings_added:
        conclusion = "neutral"
    else:
        conclusion = "success"

    check: dict[str, object] = {
        "name": "Quarto-Needs engineering change",
        "conclusion": conclusion,
        "summary": (
            f"{sum(len(ids) for ids in report.changed.values())} changed, "
            f"{sum(len(ids) for ids in report.affected.values())} affected, "
            f"{len(report.suspect_claims)} suspect, "
            f"{len(report.gate_regressions)} gate regression(s)"
        ),
        "annotationCount": len(annotations),
    }
    if model_url:
        check["modelUrl"] = model_url

    return GitHubProjection(
        summary_markdown=render_markdown(report),
        annotations=tuple(annotations),
        check=check,
    )


def _escape_data(value: object) -> str:
    return (
        str(value)
        .replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def _escape_property(value: object) -> str:
    return _escape_data(value).replace(":", "%3A").replace(",", "%2C")


def render_workflow_commands(projection: GitHubProjection) -> str:
    """Render GitHub Actions workflow command annotations safely."""
    lines: list[str] = []
    for annotation in projection.annotations:
        properties = [f"title={_escape_property(annotation['title'])}"]
        if annotation.get("file"):
            properties.append(f"file={_escape_property(annotation['file'])}")
        if annotation.get("line") is not None:
            properties.append(f"line={int(annotation['line'])}")
        message = _escape_data(annotation["message"])
        if annotation.get("url"):
            message += " — " + _escape_data(annotation["url"])
        lines.append(
            f"::{annotation['level']} {','.join(properties)}::{message}"
        )
    return "\n".join(lines) + ("\n" if lines else "")
