from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from ..export import _write_atomic_text
from ..snapshot import AnalysisSnapshot, thaw_json

REQIF_SPECIFICATION_VERSION = "1.2"
REQIF_HEADER_VERSION = "1.0"
REQIF_NS = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = f"{REQIF_NS} {REQIF_NS}"
_STRING_DATATYPE_ID = "QN-DATATYPE-STRING"
_SPECIFICATION_TYPE_ID = "QN-SPECIFICATION-TYPE"
_FIELDS = ("canonical-id", "status", "body", "rationale", "attributes-json")
_ID_SAFE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")

ET.register_namespace("", REQIF_NS)
ET.register_namespace("xsi", XSI_NS)


def _q(name: str) -> str:
    return f"{{{REQIF_NS}}}{name}"


def _identifier(kind: str, value: str) -> str:
    """Build a stable XML-ID-safe ReqIF identifier without constraining authored IDs."""
    digest = hashlib.sha256(f"{kind}\0{value}".encode("utf-8")).hexdigest()
    identifier = f"QN-{kind.upper()}-{digest}"
    assert _ID_SAFE.fullmatch(identifier)
    return identifier


def _timestamp(reference_date: str) -> str:
    """Derive deterministic ReqIF timestamps from the analysis reference date."""
    text = (reference_date or "").strip()
    if not text:
        return "1970-01-01T00:00:00Z"
    date = text.split("T", 1)[0]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return f"{date}T00:00:00Z"
    return "1970-01-01T00:00:00Z"


def _canonical_attributes(item) -> str:
    return json.dumps(
        thaw_json(item.attributes),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _field_definition_id(type_name: str, field: str) -> str:
    return _identifier("attribute", f"{type_name}\0{field}")


def _object_type_id(type_name: str) -> str:
    return _identifier("object-type", type_name)


def _relation_type_id(catalog_name: str) -> str:
    return _identifier("relation-type", catalog_name)


def _object_id(canonical_id: str) -> str:
    return _identifier("object", canonical_id)


def _relation_id(source: str, catalog_name: str, target: str, ordinal: int) -> str:
    return _identifier("relation", f"{source}\0{catalog_name}\0{target}\0{ordinal}")


def _add_text(parent: ET.Element, name: str, value: str) -> ET.Element:
    node = ET.SubElement(parent, _q(name))
    node.text = value
    return node


def _add_string_definition(
    parent: ET.Element, *, type_name: str, field: str, timestamp: str
) -> None:
    definition = ET.SubElement(
        parent,
        _q("ATTRIBUTE-DEFINITION-STRING"),
        {
            "IDENTIFIER": _field_definition_id(type_name, field),
            "LAST-CHANGE": timestamp,
            "LONG-NAME": f"quarto-needs.{field}",
        },
    )
    type_node = ET.SubElement(definition, _q("TYPE"))
    _add_text(type_node, "DATATYPE-DEFINITION-STRING-REF", _STRING_DATATYPE_ID)


def _add_string_value(
    parent: ET.Element, *, type_name: str, field: str, value: str
) -> None:
    attribute = ET.SubElement(
        parent,
        _q("ATTRIBUTE-VALUE-STRING"),
        {"THE-VALUE": value},
    )
    definition = ET.SubElement(attribute, _q("DEFINITION"))
    _add_text(
        definition,
        "ATTRIBUTE-DEFINITION-STRING-REF",
        _field_definition_id(type_name, field),
    )


def render(snapshot: AnalysisSnapshot) -> str:
    """Render one deterministic ReqIF 1.2 projection of the canonical graph."""
    timestamp = _timestamp(snapshot.reference_date)
    fingerprint = snapshot.semantic_graph_fingerprint or "\0".join(
        item.id for item in snapshot.objects
    )
    root = ET.Element(
        _q("REQ-IF"),
        {f"{{{XSI_NS}}}schemaLocation": SCHEMA_LOCATION},
    )

    the_header = ET.SubElement(root, _q("THE-HEADER"))
    header = ET.SubElement(
        the_header,
        _q("REQ-IF-HEADER"),
        {"IDENTIFIER": _identifier("header", fingerprint)},
    )
    _add_text(header, "CREATION-TIME", timestamp)
    _add_text(
        header,
        "REPOSITORY-ID",
        snapshot.configuration_fingerprint or fingerprint,
    )
    tool = f"{snapshot.generator_name} {snapshot.generator_version}".strip()
    _add_text(header, "REQ-IF-TOOL-ID", tool or "Quarto-Needs")
    # The ReqIF 1.2 normative XSD fixes this *document header field* to 1.0.
    # This value is therefore intentionally distinct from the OMG specification
    # revision implemented by this exporter (REQIF_SPECIFICATION_VERSION == 1.2).
    _add_text(header, "REQ-IF-VERSION", REQIF_HEADER_VERSION)
    _add_text(header, "SOURCE-TOOL-ID", tool or "Quarto-Needs")
    _add_text(header, "TITLE", "Quarto-Needs engineering graph")

    core = ET.SubElement(root, _q("CORE-CONTENT"))
    content = ET.SubElement(core, _q("REQ-IF-CONTENT"))

    datatypes = ET.SubElement(content, _q("DATATYPES"))
    ET.SubElement(
        datatypes,
        _q("DATATYPE-DEFINITION-STRING"),
        {
            "IDENTIFIER": _STRING_DATATYPE_ID,
            "LAST-CHANGE": timestamp,
            "LONG-NAME": "String",
            "MAX-LENGTH": "2147483647",
        },
    )

    object_types = sorted(
        {item.type for item in snapshot.objects},
        key=lambda value: (value.casefold(), value),
    )
    relation_names = sorted(
        {item.catalog_name for item in snapshot.relations},
        key=lambda value: (value.casefold(), value),
    )
    semantic_family: dict[str, str] = {}
    for relation in snapshot.relations:
        semantic_family.setdefault(relation.catalog_name, relation.semantic_family)

    spec_types = ET.SubElement(content, _q("SPEC-TYPES"))
    ET.SubElement(
        spec_types,
        _q("SPECIFICATION-TYPE"),
        {
            "IDENTIFIER": _SPECIFICATION_TYPE_ID,
            "LAST-CHANGE": timestamp,
            "LONG-NAME": "Quarto-Needs Engineering Graph",
        },
    )
    for type_name in object_types:
        object_type = ET.SubElement(
            spec_types,
            _q("SPEC-OBJECT-TYPE"),
            {
                "IDENTIFIER": _object_type_id(type_name),
                "LAST-CHANGE": timestamp,
                "LONG-NAME": type_name,
            },
        )
        attributes = ET.SubElement(object_type, _q("SPEC-ATTRIBUTES"))
        for field in _FIELDS:
            _add_string_definition(
                attributes,
                type_name=type_name,
                field=field,
                timestamp=timestamp,
            )

    for relation_name in relation_names:
        attributes = {
            "IDENTIFIER": _relation_type_id(relation_name),
            "LAST-CHANGE": timestamp,
            "LONG-NAME": relation_name,
        }
        family = semantic_family.get(relation_name, "")
        if family:
            attributes["DESC"] = f"Quarto-Needs semantic family: {family}"
        ET.SubElement(spec_types, _q("SPEC-RELATION-TYPE"), attributes)

    spec_objects = ET.SubElement(content, _q("SPEC-OBJECTS"))
    for item in sorted(
        snapshot.objects, key=lambda value: (value.id.casefold(), value.id)
    ):
        spec_object = ET.SubElement(
            spec_objects,
            _q("SPEC-OBJECT"),
            {
                "IDENTIFIER": _object_id(item.id),
                "LAST-CHANGE": timestamp,
                "LONG-NAME": item.title or item.id,
            },
        )
        values = ET.SubElement(spec_object, _q("VALUES"))
        payload = {
            "canonical-id": item.id,
            "status": item.status,
            "body": item.body,
            "rationale": item.rationale,
            "attributes-json": _canonical_attributes(item),
        }
        for field in _FIELDS:
            _add_string_value(
                values,
                type_name=item.type,
                field=field,
                value=payload[field],
            )
        type_node = ET.SubElement(spec_object, _q("TYPE"))
        _add_text(type_node, "SPEC-OBJECT-TYPE-REF", _object_type_id(item.type))

    spec_relations = ET.SubElement(content, _q("SPEC-RELATIONS"))
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
        node = ET.SubElement(
            spec_relations,
            _q("SPEC-RELATION"),
            {
                "IDENTIFIER": _relation_id(
                    relation.source,
                    relation.catalog_name,
                    relation.target,
                    ordinal,
                ),
                "LAST-CHANGE": timestamp,
                "LONG-NAME": relation.catalog_name,
            },
        )
        source = ET.SubElement(node, _q("SOURCE"))
        _add_text(source, "SPEC-OBJECT-REF", _object_id(relation.source))
        target = ET.SubElement(node, _q("TARGET"))
        _add_text(target, "SPEC-OBJECT-REF", _object_id(relation.target))
        type_node = ET.SubElement(node, _q("TYPE"))
        _add_text(
            type_node,
            "SPEC-RELATION-TYPE-REF",
            _relation_type_id(relation.catalog_name),
        )

    specifications = ET.SubElement(content, _q("SPECIFICATIONS"))
    specification = ET.SubElement(
        specifications,
        _q("SPECIFICATION"),
        {
            "IDENTIFIER": _identifier("specification", fingerprint),
            "LAST-CHANGE": timestamp,
            "LONG-NAME": "Quarto-Needs Engineering Graph",
        },
    )
    type_node = ET.SubElement(specification, _q("TYPE"))
    _add_text(type_node, "SPECIFICATION-TYPE-REF", _SPECIFICATION_TYPE_ID)
    children = ET.SubElement(specification, _q("CHILDREN"))
    for item in sorted(
        snapshot.objects, key=lambda value: (value.id.casefold(), value.id)
    ):
        hierarchy = ET.SubElement(
            children,
            _q("SPEC-HIERARCHY"),
            {
                "IDENTIFIER": _identifier("hierarchy", item.id),
                "LAST-CHANGE": timestamp,
                "LONG-NAME": item.title or item.id,
            },
        )
        object_node = ET.SubElement(hierarchy, _q("OBJECT"))
        _add_text(object_node, "SPEC-OBJECT-REF", _object_id(item.id))

    ET.SubElement(content, _q("SPEC-RELATION-GROUPS"))
    ET.SubElement(root, _q("TOOL-EXTENSIONS"))

    ET.indent(root, space="  ")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + ET.tostring(root, encoding="unicode", short_empty_elements=True)
        + "\n"
    )


def write(path: Path, snapshot: AnalysisSnapshot) -> Path:
    destination = Path(path)
    _write_atomic_text(destination, render(snapshot))
    return destination
