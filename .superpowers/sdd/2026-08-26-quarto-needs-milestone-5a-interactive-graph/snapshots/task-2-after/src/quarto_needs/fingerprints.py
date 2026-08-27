"""Pure content fingerprints over the canonical snapshot records.

Every fingerprint excludes line numbers, `href` values, generated metrics,
and any other derived data, so provenance changes and rendering changes can
never masquerade as semantic ones.
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable

from .config import NeedsConfig
from .rules import RULE_SET_VERSION
from .snapshot import ObjectRecord, RelationRecord, thaw_json


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def object_content_fingerprint(record: ObjectRecord) -> str:
    return _digest(
        {
            "id": record.id,
            "type": record.type,
            "title": record.title,
            "body": record.body,
            "rationale": record.rationale,
            "status": record.status,
            "priority": record.priority,
            "tags": list(record.tags),
            "attributes": thaw_json(record.attributes),
        }
    )


def relation_authored_fingerprint(record: RelationRecord) -> str:
    return _digest(
        {
            "source": record.source,
            "authored_name": record.authored_name,
            "target": record.target,
            "attributes": thaw_json(record.attributes),
        }
    )


def relation_semantic_fingerprint(record: RelationRecord) -> str:
    """Identity of the edge itself, independent of which end authored it.

    Endpoints are sorted by role, so an alias flip that preserves the roles
    yields the same fingerprint and is classified as representation-only.
    """
    endpoints = sorted(
        (
            {"id": record.source, "role": record.source_role},
            {"id": record.target, "role": record.target_role},
        ),
        key=lambda item: (item["role"], item["id"]),
    )
    return _digest(
        {
            "family": record.semantic_family,
            "endpoints": endpoints,
            "attributes": thaw_json(record.attributes),
        }
    )


def configuration_fingerprint(
    config: NeedsConfig, *, relation_catalog_version: str
) -> str:
    return _digest(
        {
            "configuration": config.canonical_document(),
            "relationCatalogVersion": relation_catalog_version,
            "ruleSetVersion": RULE_SET_VERSION,
        }
    )


def semantic_graph_fingerprint(
    objects: Iterable[ObjectRecord],
    relations: Iterable[RelationRecord],
    configuration: str,
) -> str:
    return _digest(
        {
            "objects": sorted(object_content_fingerprint(item) for item in objects),
            "relations": sorted(relation_semantic_fingerprint(item) for item in relations),
            "configuration": configuration,
        }
    )


def representation_fingerprint(relations: Iterable[RelationRecord]) -> str:
    return _digest(sorted(relation_authored_fingerprint(item) for item in relations))
