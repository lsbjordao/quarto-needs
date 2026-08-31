from __future__ import annotations

import json

import pytest

from quarto_needs.oslc_rdf import (
    OslcRdfError,
    index_expanded_nodes,
    materialize_reference,
    normalize_rdf_representation,
)


OSLC_SERVICE = "http://open-services.net/ns/core#service"


def _node(nodes, identifier: str):
    return next(node for node in nodes if node.get("@id") == identifier)


def test_jsonld_normalization_is_expanded_and_network_free() -> None:
    document = {
        "@id": "https://provider.test/oslc/sp/1",
        OSLC_SERVICE: [{"@id": "https://provider.test/oslc/service/rm"}],
    }
    nodes = normalize_rdf_representation(
        json.dumps(document).encode("utf-8"),
        media_type="application/ld+json",
    )
    provider = _node(nodes, "https://provider.test/oslc/sp/1")
    assert provider[OSLC_SERVICE] == [{"@id": "https://provider.test/oslc/service/rm"}]

    remote_context = {
        "@context": "https://evil.test/context.jsonld",
        "@id": "https://provider.test/oslc/sp/1",
    }
    with pytest.raises(OslcRdfError, match="remote JSON-LD"):
        normalize_rdf_representation(
            json.dumps(remote_context).encode("utf-8"),
            media_type="application/ld+json",
        )


def test_turtle_and_rdfxml_normalize_to_same_expanded_identity() -> None:
    turtle = b"""
        @prefix oslc: <http://open-services.net/ns/core#> .
        <https://provider.test/oslc/sp/1>
            oslc:service <https://provider.test/oslc/service/rm> .
    """
    rdfxml = b"""<?xml version="1.0"?>
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                 xmlns:oslc="http://open-services.net/ns/core#">
          <rdf:Description rdf:about="https://provider.test/oslc/sp/1">
            <oslc:service rdf:resource="https://provider.test/oslc/service/rm"/>
          </rdf:Description>
        </rdf:RDF>
    """

    turtle_nodes = normalize_rdf_representation(turtle, media_type="text/turtle")
    xml_nodes = normalize_rdf_representation(rdfxml, media_type="application/rdf+xml")
    turtle_provider = _node(turtle_nodes, "https://provider.test/oslc/sp/1")
    xml_provider = _node(xml_nodes, "https://provider.test/oslc/sp/1")

    assert turtle_provider[OSLC_SERVICE] == xml_provider[OSLC_SERVICE]


def test_normalization_rejects_malformed_payload_and_node_budget() -> None:
    with pytest.raises(OslcRdfError, match="malformed JSON"):
        normalize_rdf_representation(b"{", media_type="application/json")

    document = [
        {"@id": f"https://provider.test/resource/{index}"}
        for index in range(3)
    ]
    with pytest.raises(OslcRdfError, match="limit is 2"):
        normalize_rdf_representation(
            json.dumps(document).encode("utf-8"),
            media_type="application/ld+json",
            max_nodes=2,
        )


def test_expanded_index_rejects_duplicate_identity_and_materializes_known_reference() -> None:
    nodes = (
        {"@id": "https://provider.test/a", OSLC_SERVICE: [{"@id": "https://provider.test/b"}]},
        {"@id": "https://provider.test/b", "@type": ["https://example.test/Type"]},
    )
    index = index_expanded_nodes(nodes)
    assert materialize_reference({"@id": "https://provider.test/b"}, index=index) == nodes[1]
    assert materialize_reference({"@id": "https://provider.test/missing"}, index=index) == {
        "@id": "https://provider.test/missing"
    }

    with pytest.raises(OslcRdfError, match="duplicate expanded RDF node identity"):
        index_expanded_nodes((nodes[0], nodes[0]))
