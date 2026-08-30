from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from ..export import _write_atomic_text
from ..snapshot import AnalysisSnapshot, thaw_json

JSONLD_CONTEXT_VERSION = "1"
QN_NAMESPACE = "urn:quarto-needs:v1:"

_CONTEXT = {
    "@version": 1.1,
    "qn": {"@id": QN_NAMESPACE, "@prefix": True},
    "quartoNeedsJsonLdVersion": "qn:jsonLdProjectionVersion",
    "canonicalId": "qn:canonicalId",
    "objectType": "qn:objectType",
    "title": "qn:title",
    "status": "qn:status",
    "body": "qn:body",
    "rationale": "qn:rationale",
    "attributes": {"@id": "qn:attributes", "@type": "@json"},
    "source": {"@id": "qn:source", "@type": "@id"},
    "target": {"@id": "qn:target", "@type": "@id"},
    "relationType": "qn:relationType",
    "authoredName": "qn:authoredName",
    "semanticFamily": "qn:semanticFamily",
    "sourceRole": "qn:sourceRole",
    "targetRole": "qn:targetRole",
    "impactDirection": "qn:impactDirection",
    "referenceDate": "qn:referenceDate",
    "configurationFingerprint": "qn:configurationFingerprint",
    "semanticGraphFingerprint": "qn:semanticGraphFingerprint",
    "generator": "qn:generator",
    "generatorVersion": "qn:generatorVersion",
}


def _object_iri(canonical_id: str) -> str:
    return f"{QN_NAMESPACE}object:{quote(canonical_id, safe='')}"


def _relation_iri(source: str, relation_type: str, target: str, ordinal: int) -> str:
    digest = hashlib.sha256(
        f"{source}\0{relation_type}\0{target}\0{ordinal}".encode("utf-8")
    ).hexdigest()
    return f"{QN_NAMESPACE}relation:{digest}"


def _graph_iri(snapshot: AnalysisSnapshot) -> str:
    fingerprint = snapshot.semantic_graph_fingerprint or hashlib.sha256(
        "\0".join(item.id for item in snapshot.objects).encode("utf-8")
    ).hexdigest()
    return f"{QN_NAMESPACE}graph:{fingerprint}"


def build_document(snapshot: AnalysisSnapshot) -> dict[str, object]:
    graph: list[dict[str, object]] = [
        {
            "@id": _graph_iri(snapshot),
            "@type": "qn:EngineeringGraph",
            "referenceDate": snapshot.reference_date,
            "configurationFingerprint": snapshot.configuration_fingerprint,
            "semanticGraphFingerprint": snapshot.semantic_graph_fingerprint,
            "generator": snapshot.generator_name,
            "generatorVersion": snapshot.generator_version,
        }
    ]

    for item in sorted(snapshot.objects, key=lambda value: (value.id.casefold(), value.id)):
        graph.append(
            {
                "@id": _object_iri(item.id),
                "@type": "qn:EngineeringObject",
                "canonicalId": item.id,
                "objectType": item.type,
                "title": item.title,
                "status": item.status,
                "body": item.body,
                "rationale": item.rationale,
                "attributes": thaw_json(item.attributes),
            }
        )

    ordered_relations = sorted(
        snapshot.relations,
        key=lambda item: (
            item.source.casefold(),
            item.source,
            item.catalog_name.casefold(),
            item.catalog_name,
            item.target.casefold(),
            item.target,
            item.authored_name.casefold(),
            item.authored_name,
        ),
    )
    counters: dict[tuple[str, str, str], int] = {}
    for relation in ordered_relations:
        key = (relation.source, relation.catalog_name, relation.target)
        ordinal = counters.get(key, 0) + 1
        counters[key] = ordinal
        graph.append(
            {
                "@id": _relation_iri(
                    relation.source,
                    relation.catalog_name,
                    relation.target,
                    ordinal,
                ),
                "@type": "qn:Relation",
                "source": _object_iri(relation.source),
                "target": _object_iri(relation.target),
                "relationType": relation.catalog_name,
                "authoredName": relation.authored_name,
                "semanticFamily": relation.semantic_family,
                "sourceRole": relation.source_role,
                "targetRole": relation.target_role,
                "impactDirection": relation.impact_direction,
            }
        )

    return {
        "@context": _CONTEXT,
        "@graph": graph,
        "quartoNeedsJsonLdVersion": JSONLD_CONTEXT_VERSION,
    }


def render(snapshot: AnalysisSnapshot) -> str:
    return json.dumps(
        build_document(snapshot),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def write(path: Path, snapshot: AnalysisSnapshot) -> Path:
    destination = Path(path)
    _write_atomic_text(destination, render(snapshot))
    return destination
