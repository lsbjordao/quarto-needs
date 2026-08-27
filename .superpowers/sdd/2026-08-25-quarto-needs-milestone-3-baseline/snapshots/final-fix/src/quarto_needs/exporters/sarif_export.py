"""SARIF 2.1.0 exporter.

SARIF consumes findings, not the snapshot: a structurally invalid project
(no snapshot) still exports its findings, so `render_from_findings` is the
load-bearing producer and `render`/`write` are conveniences around it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import quarto_needs

from ..diagnostics import Finding
from ..export import _write_atomic_text
from ..rules import RULES
from ..snapshot import AnalysisSnapshot

# The $id of the vendored schema (schemas/vendor/sarif-2.1.0/sarif-schema.json).
SCHEMA_URI = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
    "master/Schemata/sarif-schema-2.1.0.json"
)
SARIF_VERSION = "2.1.0"
TOOL_NAME = "quarto-needs"
AUTOMATION_ID = "quarto-needs/export"

# Finding severities map onto the SARIF level enum (none/note/warning/error).
_LEVEL_BY_SEVERITY = {
    "error": "error",
    "warning": "warning",
    "info": "note",
}


def _sort_key(finding: Finding) -> tuple[str, str, str]:
    # Deterministic output: results ordered by code, object_id, message.
    return (finding.code, finding.object_id or "", finding.message)


def _rule_descriptor(code: str) -> dict[str, object]:
    spec = RULES.get(code)
    descriptor: dict[str, object] = {
        "id": code,
        # Fall back to the bare code when the finding is not in the registry.
        "shortDescription": {"text": spec.title if spec is not None else code},
    }
    if spec is not None:
        descriptor["fullDescription"] = {"text": spec.help}
    return descriptor


def _result(finding: Finding) -> dict[str, object]:
    result: dict[str, object] = {
        "ruleId": finding.code,
        "level": _LEVEL_BY_SEVERITY.get(finding.severity, "note"),
        "message": {"text": finding.message},
        # The finding's existing stable identity hash, independent of
        # severity overrides, serves as the primary-location line hash.
        "fingerprints": {"primaryLocationLineHash": finding.fingerprint},
    }
    if finding.location is not None:
        # location.file is already the project-relative POSIX path.
        result["locations"] = [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": finding.location.file},
                    "region": {"startLine": finding.location.line},
                }
            }
        ]
    return result


def build_payload(findings: Sequence[Finding]) -> dict[str, object]:
    ordered = sorted(findings, key=_sort_key)
    return {
        "$schema": SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": TOOL_NAME,
                        "version": quarto_needs.__version__,
                        "rules": [
                            _rule_descriptor(code)
                            for code in sorted({finding.code for finding in ordered})
                        ],
                    }
                },
                "automationDetails": {"id": AUTOMATION_ID},
                "results": [_result(finding) for finding in ordered],
            }
        ],
    }


def render_from_findings(findings: Sequence[Finding]) -> str:
    return (
        json.dumps(
            build_payload(findings),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def render(snapshot: AnalysisSnapshot) -> str:
    return render_from_findings(snapshot.findings)


def write(path: Path, findings: Sequence[Finding]) -> Path:
    destination = Path(path)
    _write_atomic_text(destination, render_from_findings(findings))
    return destination
