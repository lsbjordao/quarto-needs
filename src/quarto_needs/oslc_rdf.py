from __future__ import annotations

import json
from collections.abc import Mapping

from .oslc_http import OslcTransportError


class OslcRdfError(RuntimeError):
    pass


def _load_pyld():
    try:
        from pyld import jsonld  # type: ignore[import-not-found]
    except ImportError as error:
        raise OslcRdfError(
            "OSLC RDF normalization requires the optional 'oslc' dependencies; "
            "install with pip install 'quarto-needs[oslc]'"
        ) from error
    return jsonld


def _load_rdflib():
    try:
        import rdflib  # type: ignore[import-not-found]
    except ImportError as error:
        raise OslcRdfError(
            "Turtle/RDF/XML normalization requires the optional 'oslc' dependencies; "
            "install with pip install 'quarto-needs[oslc]'"
        ) from error
    return rdflib


def _offline_document_loader(url: str, options=None):  # type: ignore[no-untyped-def]
    raise OslcRdfError(
        f"remote JSON-LD context/document loading is disabled for OSLC normalization: {url}"
    )


def _parse_json(payload: bytes) -> object:
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OslcRdfError(f"malformed JSON/JSON-LD representation: {error}") from error


def _rdf_to_jsonld(payload: bytes, *, media_type: str) -> object:
    rdflib = _load_rdflib()
    graph = rdflib.Graph()
    rdf_format = "turtle" if media_type == "text/turtle" else "xml"
    try:
        graph.parse(data=payload, format=rdf_format)
        serialized = graph.serialize(format="json-ld", auto_compact=False)
    except Exception as error:  # rdflib exposes parser-specific exceptions
        raise OslcRdfError(f"malformed {media_type} representation: {error}") from error
    if isinstance(serialized, bytes):
        serialized = serialized.decode("utf-8")
    try:
        return json.loads(serialized)
    except json.JSONDecodeError as error:
        raise OslcRdfError("RDF normalization produced invalid JSON-LD") from error


def normalize_rdf_representation(
    payload: bytes,
    *,
    media_type: str,
    max_nodes: int = 5_000,
) -> tuple[Mapping[str, object], ...]:
    """Normalize one bounded OSLC representation into expanded JSON-LD nodes.

    No remote JSON-LD contexts/documents are dereferenced. The HTTP transport
    owns network access; RDF normalization is deterministic and network-free.
    """
    if max_nodes <= 0:
        raise ValueError("max_nodes must be positive")

    normalized_media_type = media_type.split(";", 1)[0].strip().lower()
    if normalized_media_type in {"application/ld+json", "application/json"}:
        document = _parse_json(payload)
    elif normalized_media_type in {"text/turtle", "application/rdf+xml"}:
        document = _rdf_to_jsonld(payload, media_type=normalized_media_type)
    else:
        raise OslcTransportError(
            "unsupported-media-type",
            f"unsupported RDF normalization media type: {normalized_media_type!r}",
        )

    jsonld = _load_pyld()
    try:
        expanded = jsonld.expand(
            document,
            options={"documentLoader": _offline_document_loader},
        )
    except OslcRdfError:
        raise
    except Exception as error:
        raise OslcRdfError(f"cannot expand OSLC JSON-LD representation: {error}") from error

    if not isinstance(expanded, list):
        raise OslcRdfError("expanded OSLC JSON-LD must be an array")
    if len(expanded) > max_nodes:
        raise OslcRdfError(
            f"expanded OSLC representation has {len(expanded)} nodes, limit is {max_nodes}"
        )

    nodes: list[Mapping[str, object]] = []
    for node in expanded:
        if not isinstance(node, Mapping):
            raise OslcRdfError("expanded OSLC JSON-LD nodes must be objects")
        nodes.append(node)
    return tuple(nodes)


def index_expanded_nodes(
    nodes: tuple[Mapping[str, object], ...],
) -> dict[str, Mapping[str, object]]:
    index: dict[str, Mapping[str, object]] = {}
    for node in nodes:
        identifier = node.get("@id")
        if not isinstance(identifier, str):
            continue
        if identifier in index:
            raise OslcRdfError(f"duplicate expanded RDF node identity: {identifier}")
        index[identifier] = node
    return index


def materialize_reference(
    value: object,
    *,
    index: Mapping[str, Mapping[str, object]],
) -> object:
    if isinstance(value, list):
        return [materialize_reference(item, index=index) for item in value]
    if not isinstance(value, Mapping):
        return value
    if set(value) == {"@id"} and isinstance(value.get("@id"), str):
        target = index.get(value["@id"])
        if target is not None:
            return dict(target)
    return dict(value)
