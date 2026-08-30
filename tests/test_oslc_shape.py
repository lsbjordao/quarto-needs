from __future__ import annotations

import pytest

from quarto_needs.oslc_rm import OSLC_CORE_NS, OSLC_RM_NS
from quarto_needs.oslc_shape import (
    OSLC_DESCRIBES,
    OSLC_NAME,
    OSLC_OCCURS,
    OSLC_PROPERTY,
    OSLC_PROPERTY_DEFINITION,
    OSLC_RANGE,
    OSLC_READ_ONLY,
    OSLC_VALUE_TYPE,
    parse_resource_shape,
)


def _ref(uri: str) -> dict[str, str]:
    return {"@id": uri}


def _literal(value: object) -> dict[str, object]:
    return {"@value": value}


def test_parse_resource_shape_preserves_bounded_property_contract() -> None:
    shape = {
        "@id": "https://provider.test/oslc/shapes/requirement",
        OSLC_DESCRIBES: [_ref(f"{OSLC_RM_NS}Requirement")],
        OSLC_PROPERTY: [
            {
                OSLC_NAME: [_literal("title")],
                OSLC_OCCURS: [_ref(f"{OSLC_CORE_NS}Exactly-one")],
                OSLC_PROPERTY_DEFINITION: [
                    _ref("http://purl.org/dc/terms/title")
                ],
                OSLC_VALUE_TYPE: [_ref("http://www.w3.org/2001/XMLSchema#string")],
                OSLC_READ_ONLY: [_literal(False)],
            },
            {
                OSLC_NAME: [_literal("validatedBy")],
                OSLC_OCCURS: [_ref(f"{OSLC_CORE_NS}Zero-or-many")],
                OSLC_PROPERTY_DEFINITION: [
                    _ref(f"{OSLC_RM_NS}validatedBy")
                ],
                OSLC_RANGE: [_ref(f"{OSLC_RM_NS}Requirement")],
            },
        ],
    }

    parsed = parse_resource_shape(shape)

    assert parsed.shape_uri == "https://provider.test/oslc/shapes/requirement"
    assert parsed.describes == (f"{OSLC_RM_NS}Requirement",)
    assert [item.name for item in parsed.properties] == ["title", "validatedBy"]
    assert parsed.properties[0].read_only is False
    assert parsed.properties[1].ranges == (f"{OSLC_RM_NS}Requirement",)


def test_parse_resource_shape_rejects_missing_required_property_definition() -> None:
    shape = {
        OSLC_PROPERTY: [
            {
                OSLC_NAME: [_literal("title")],
                OSLC_OCCURS: [_ref(f"{OSLC_CORE_NS}Exactly-one")],
            }
        ]
    }

    with pytest.raises(ValueError, match="propertyDefinition"):
        parse_resource_shape(shape)


def test_parse_resource_shape_rejects_unknown_occurrence_semantics() -> None:
    shape = {
        OSLC_PROPERTY: [
            {
                OSLC_NAME: [_literal("title")],
                OSLC_OCCURS: [_ref(f"{OSLC_CORE_NS}Sometimes")],
                OSLC_PROPERTY_DEFINITION: [
                    _ref("http://purl.org/dc/terms/title")
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="unsupported OSLC oslc:occurs"):
        parse_resource_shape(shape)


def test_parse_resource_shape_orders_properties_deterministically() -> None:
    def property_node(name: str, uri: str) -> dict[str, object]:
        return {
            OSLC_NAME: [_literal(name)],
            OSLC_OCCURS: [_ref(f"{OSLC_CORE_NS}Zero-or-one")],
            OSLC_PROPERTY_DEFINITION: [_ref(uri)],
        }

    parsed = parse_resource_shape(
        {
            OSLC_PROPERTY: [
                property_node("zeta", "https://example.test/zeta"),
                property_node("Alpha", "https://example.test/alpha"),
            ]
        }
    )

    assert [item.name for item in parsed.properties] == ["Alpha", "zeta"]
