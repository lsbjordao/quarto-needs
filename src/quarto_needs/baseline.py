"""The baseline artifact: a canonical snapshot plus its comparison axes.

A baseline stores authored content, not only fingerprints, because `diff`
reports semantic modifications by field and cannot name a field it never saw.
Derived fields and named variants are stored separately from authored object
attributes so the artifact preserves their provenance as computed projections.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import quarto_needs

from . import fingerprints
from .analysis import AnalysisResult
from .config import NeedsConfig
from .export import _write_atomic_text
from .quality import report_from_snapshot
from .relations import DEFAULT_RELATION_CATALOG
from .rules import RULE_SET_VERSION
from .snapshot import AnalysisSnapshot, LocationRecord, thaw_json

SCHEMA_VERSION = "1"
DEFAULT_BASELINE_PATH = Path("baselines") / "quarto-needs.json"


class BaselineError(Exception):
    """A baseline could not be written, read, or trusted."""


def _location(location: LocationRecord | None) -> dict[str, object] | None:
    if location is None:
        return None
    return {"file": location.file, "line": location.line, "anchor": location.anchor}


def _header(reference_date: str, configuration: str) -> dict[str, object]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generator": {"name": "quarto-needs", "version": quarto_needs.__version__},
        "relationCatalogVersion": DEFAULT_RELATION_CATALOG.version,
        "ruleSetVersion": RULE_SET_VERSION,
        "referenceDate": reference_date,
        "configurationFingerprint": configuration,
    }


def build_baseline(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    *,
    queries: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, object]:
    payload = _header(snapshot.reference_date, snapshot.configuration_fingerprint)
    payload["semanticGraphFingerprint"] = snapshot.semantic_graph_fingerprint
    payload["representationFingerprint"] = snapshot.representation_fingerprint
    if snapshot.variant_fingerprint:
        payload["variantFingerprint"] = snapshot.variant_fingerprint
    payload["valid"] = True
    payload["objects"] = [
        {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "status": item.status,
            "body": item.body,
            "rationale": item.rationale,
            "attributes": thaw_json(item.attributes),
            "location": _location(item.locations[0] if item.locations else None),
            "contentFingerprint": fingerprints.object_content_fingerprint(item),
        }
        for item in snapshot.objects
    ]
    payload["relations"] = [
        {
            "source": item.source,
            "authoredName": item.authored_name,
            "target": item.target,
            "semanticFamily": item.semantic_family,
            "sourceRole": item.source_role,
            "targetRole": item.target_role,
            "impactDirection": item.impact_direction,
            "attributes": thaw_json(item.attributes),
            "authoredFingerprint": fingerprints.relation_authored_fingerprint(item),
            "semanticFingerprint": fingerprints.relation_semantic_fingerprint(item),
        }
        for item in snapshot.relations
    ]
    if snapshot.derived:
        payload["derived"] = thaw_json(snapshot.derived)
    if snapshot.variants:
        payload["variants"] = {
            name: list(ids) for name, ids in snapshot.variants.items()
        }
    payload["findings"] = [finding.to_dict() for finding in snapshot.findings]
    payload["report"] = report_from_snapshot(snapshot, config, queries=queries).to_dict()
    return payload


def build_invalid_baseline(result: AnalysisResult, config: NeedsConfig) -> dict[str, object]:
    """The explicitly requested diagnostic artifact.

    It is never accepted by `diff` or `impact`: structural failures make graph
    comparison ambiguous. It exists so `baseline inspect` can explain why.
    """
    from .config import reference_date

    configuration = fingerprints.configuration_fingerprint(
        config, relation_catalog_version=DEFAULT_RELATION_CATALOG.version
    )
    payload = _header(reference_date().isoformat(), configuration)
    payload["valid"] = False
    payload["declarations"] = [
        {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "status": item.status,
            "location": _location(item.location),
        }
        for item in result.declarations
    ]
    payload["findings"] = [finding.to_dict() for finding in result.findings]
    return payload


def render_baseline(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_baseline(path: Path, payload: dict[str, object], *, force: bool = False) -> None:
    path = Path(path)
    if path.exists() and not force:
        raise BaselineError(f"{path} already exists; pass --force to overwrite it")
    _write_atomic_text(path, render_baseline(payload))


def load_baseline(path: Path) -> dict[str, object]:
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise BaselineError(f"Could not read {path}: {error}") from error
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise BaselineError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise BaselineError(f"{path} is not a baseline document")
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise BaselineError(
            f"{path} declares baseline schema {payload.get('schemaVersion')!r}; "
            f"this build reads {SCHEMA_VERSION!r}"
        )
    return payload
