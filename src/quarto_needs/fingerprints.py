"""Pure content fingerprints over the canonical snapshot records.

Every fingerprint excludes line numbers, `href` values, generated metrics,
and any other incidental rendering data. Deterministic derived engineering
values are semantic projections and therefore participate explicitly in the
semantic graph fingerprint; named build variants have their own fingerprint.
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable, Mapping

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
    """Identity of the edge itself, independent of which end authored it."""
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
    derived: Mapping[str, Mapping[str, object]] | None = None,
) -> str:
    payload: dict[str, object] = {
        "objects": sorted(object_content_fingerprint(item) for item in objects),
        "relations": sorted(relation_semantic_fingerprint(item) for item in relations),
        "configuration": configuration,
    }
    if derived:
        payload["derived"] = {
            object_id: {
                name: thaw_json(value)
                for name, value in sorted(fields.items())
            }
            for object_id, fields in sorted(derived.items())
        }
    return _digest(payload)


def representation_fingerprint(relations: Iterable[RelationRecord]) -> str:
    return _digest(sorted(relation_authored_fingerprint(item) for item in relations))


def variant_fingerprint(
    variants: Mapping[str, tuple[str, ...]], semantic_graph: str
) -> str:
    return _digest(
        {
            "semanticGraphFingerprint": semantic_graph,
            "variants": {
                name: list(ids)
                for name, ids in sorted(variants.items())
            },
        }
    )
