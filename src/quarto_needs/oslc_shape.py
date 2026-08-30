from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

from .oslc_rm import OSLC_CORE_NS

OSLC_DESCRIBES = f"{OSLC_CORE_NS}describes"
OSLC_PROPERTY = f"{OSLC_CORE_NS}property"
OSLC_NAME = f"{OSLC_CORE_NS}name"
OSLC_OCCURS = f"{OSLC_CORE_NS}occurs"
OSLC_PROPERTY_DEFINITION = f"{OSLC_CORE_NS}propertyDefinition"
OSLC_VALUE_TYPE = f"{OSLC_CORE_NS}valueType"
OSLC_RANGE = f"{OSLC_CORE_NS}range"
OSLC_READ_ONLY = f"{OSLC_CORE_NS}readOnly"
OSLC_REPRESENTATION = f"{OSLC_CORE_NS}representation"
OSLC_VALUE_SHAPE = f"{OSLC_CORE_NS}valueShape"

_ALLOWED_OCCURS = {
    f"{OSLC_CORE_NS}Exactly-one",
    f"{OSLC_CORE_NS}One-or-many",
    f"{OSLC_CORE_NS}Zero-or-many",
    f"{OSLC_CORE_NS}Zero-or-one",
}


@dataclass(frozen=True, slots=True)
class OslcShapeProperty:
    name: str
    property_definition: str
    occurs: str
    value_type: str | None = None
    ranges: tuple[str, ...] = ()
    read_only: bool | None = None
    representation: str | None = None
    value_shapes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OslcResourceShape:
    shape_uri: str | None
    describes: tuple[str, ...]
    properties: tuple[OslcShapeProperty, ...]


def _objects(value: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _ids(value: object) -> tuple[str, ...]:
    result: list[str] = []
    for item in _objects(value):
        identifier = item.get("@id")
        if isinstance(identifier, str):
            result.append(identifier)
    return tuple(result)


def _values(value: object) -> tuple[object, ...]:
    result: list[object] = []
    for item in _objects(value):
        if "@value" in item:
            result.append(item["@value"])
    return tuple(result)


def _one_id(node: Mapping[str, object], key: str, *, required: bool) -> str | None:
    values = _ids(node.get(key))
    if not values and not required:
        return None
    if len(values) != 1:
        qualifier = "exactly one" if required else "at most one"
        raise ValueError(f"OSLC shape property {key} must contain {qualifier} URI")
    return values[0]


def _one_string(node: Mapping[str, object], key: str) -> str:
    values = _values(node.get(key))
    if len(values) != 1 or not isinstance(values[0], str) or not values[0]:
        raise ValueError(f"OSLC shape property {key} must contain exactly one string")
    return values[0]


def _optional_bool(node: Mapping[str, object], key: str) -> bool | None:
    values = _values(node.get(key))
    if not values:
        return None
    if len(values) != 1 or not isinstance(values[0], bool):
        raise ValueError(f"OSLC shape property {key} must contain at most one boolean")
    return values[0]


def _absolute_uri(value: str, field: str) -> str:
    if not urlparse(value).scheme:
        raise ValueError(f"{field} must be an absolute URI")
    return value


def parse_resource_shape(expanded_shape: Mapping[str, object]) -> OslcResourceShape:
    shape_uri_value = expanded_shape.get("@id")
    if shape_uri_value is not None and not isinstance(shape_uri_value, str):
        raise ValueError("OSLC ResourceShape @id must be a string when present")
    shape_uri = (
        _absolute_uri(shape_uri_value, "shape_uri")
        if isinstance(shape_uri_value, str)
        else None
    )

    describes = tuple(sorted(set(_ids(expanded_shape.get(OSLC_DESCRIBES)))))
    for described_type in describes:
        _absolute_uri(described_type, "describes")

    properties: list[OslcShapeProperty] = []
    for property_node in _objects(expanded_shape.get(OSLC_PROPERTY)):
        name = _one_string(property_node, OSLC_NAME)
        property_definition = _one_id(
            property_node, OSLC_PROPERTY_DEFINITION, required=True
        )
        assert property_definition is not None
        _absolute_uri(property_definition, "property_definition")
        occurs = _one_id(property_node, OSLC_OCCURS, required=True)
        assert occurs is not None
        if occurs not in _ALLOWED_OCCURS:
            raise ValueError(f"unsupported OSLC oslc:occurs value: {occurs}")

        value_type = _one_id(property_node, OSLC_VALUE_TYPE, required=False)
        if value_type is not None:
            _absolute_uri(value_type, "value_type")
        ranges = tuple(sorted(set(_ids(property_node.get(OSLC_RANGE)))))
        for range_uri in ranges:
            _absolute_uri(range_uri, "range")
        representation = _one_id(
            property_node, OSLC_REPRESENTATION, required=False
        )
        if representation is not None:
            _absolute_uri(representation, "representation")
        value_shapes = tuple(
            sorted(set(_ids(property_node.get(OSLC_VALUE_SHAPE))))
        )
        for value_shape in value_shapes:
            _absolute_uri(value_shape, "value_shape")

        properties.append(
            OslcShapeProperty(
                name=name,
                property_definition=property_definition,
                occurs=occurs,
                value_type=value_type,
                ranges=ranges,
                read_only=_optional_bool(property_node, OSLC_READ_ONLY),
                representation=representation,
                value_shapes=value_shapes,
            )
        )

    return OslcResourceShape(
        shape_uri=shape_uri,
        describes=describes,
        properties=tuple(
            sorted(properties, key=lambda item: (item.name.casefold(), item.name, item.property_definition))
        ),
    )
