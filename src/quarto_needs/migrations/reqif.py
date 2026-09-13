"""ReqIF 1.2 import: a ReqIF document becomes the shared migration plan.

Converging on the existing migration-plan contract (as Doorstop, StrictDoc and
OpenFastTrace do) is what makes this import review-first: parsing only
produces candidates, issues and provenance, and the shared apply/update paths
decide what may ever become authored text.

Typed attribute recovery is explicit rather than implicit: string, boolean,
integer, real and date values are recovered as their textual value; an
enumeration recovers the value's LONG-NAME; XHTML is flattened to text and
every lossy conversion is reported as an issue, never silently applied. The
document is parsed with entity expansion and DOCTYPE declarations refused, and
a byte cap, because a ReqIF file is an external input.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Mapping

from .sphinx_needs import (
    MigrationIssue,
    MigratedRelation,
    SphinxNeedCandidate,
    SphinxNeedsMigrationPlan,
)

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
_CORE_FIELDS = {
    "canonical-id",
    "status",
    "body",
    "rationale",
    "attributes-json",
    "tags",
}
_ATTRIBUTE_KEY = re.compile(r"[^A-Za-z0-9_-]+")


class ReqifMigrationError(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if _local(child.tag) == name:
            return child
    return None


def _children(element: ET.Element | None, name: str) -> list[ET.Element]:
    if element is None:
        return []
    return [child for child in element if _local(child.tag) == name]


def _descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in element.iter() if node is not element and _local(node.tag) == name]


def _child_text(element: ET.Element | None, name: str) -> str:
    node = _child(element, name) if element is not None else None
    return "".join(node.itertext()).strip() if node is not None else ""


def load_reqif_document(path: Path) -> ET.Element:
    """Read and parse a ReqIF document, refusing entity-bearing inputs."""
    source = Path(path)
    try:
        data = source.read_bytes()
    except OSError as error:
        raise ReqifMigrationError(f"cannot read ReqIF document: {error}") from error
    if len(data) > MAX_DOCUMENT_BYTES:
        raise ReqifMigrationError(
            f"ReqIF document exceeds {MAX_DOCUMENT_BYTES} bytes"
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReqifMigrationError(f"ReqIF document is not UTF-8: {error}") from error
    prolog = text[:4096].upper()
    if "<!DOCTYPE" in prolog or "<!ENTITY" in prolog:
        raise ReqifMigrationError(
            "ReqIF documents with DOCTYPE or ENTITY declarations are refused"
        )
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ReqifMigrationError(f"ReqIF document is not well-formed XML: {error}") from error
    if _local(root.tag) != "REQ-IF":
        raise ReqifMigrationError("ReqIF document root must be REQ-IF")
    return root


def _enum_labels(content: ET.Element) -> dict[str, str]:
    labels: dict[str, str] = {}
    for datatype in _descendants(content, "DATATYPE-DEFINITION-ENUMERATION"):
        for value in _descendants(datatype, "ENUM-VALUE"):
            identifier = value.get("IDENTIFIER")
            if identifier:
                labels[identifier] = value.get("LONG-NAME") or identifier
    return labels


def _attribute_fields(content: ET.Element) -> dict[str, str]:
    """Attribute-definition identifier -> authored field name."""
    fields: dict[str, str] = {}
    for node in content.iter():
        if not _local(node.tag).startswith("ATTRIBUTE-DEFINITION-"):
            continue
        identifier = node.get("IDENTIFIER")
        if not identifier:
            continue
        label = node.get("LONG-NAME") or identifier
        if label.startswith("quarto-needs."):
            label = label[len("quarto-needs."):]
        fields[identifier] = label
    return fields


def _type_labels(content: ET.Element, kind: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for node in _descendants(content, kind):
        identifier = node.get("IDENTIFIER")
        if identifier:
            labels[identifier] = node.get("LONG-NAME") or identifier
    return labels


def _value_text(
    node: ET.Element, enum_labels: Mapping[str, str]
) -> tuple[str, str | None]:
    """The textual value of one ATTRIBUTE-VALUE-* node, plus a loss marker."""
    kind = _local(node.tag).removeprefix("ATTRIBUTE-VALUE-")
    if kind == "XHTML":
        value = _child(node, "THE-VALUE")
        return ("".join(value.itertext()).strip() if value is not None else ""), "xhtml"
    raw = node.get("THE-VALUE")
    if raw is None:
        child = _child(node, "THE-VALUE")
        raw = "".join(child.itertext()).strip() if child is not None else ""
    if kind == "ENUMERATION":
        label = enum_labels.get(raw)
        if label is None:
            return raw, "unknown-enum"
        return label, None
    if kind in {"STRING", "BOOLEAN", "INTEGER", "REAL", "DATE"}:
        return raw, None
    return raw, "unsupported-kind"


def _attribute_key(name: str) -> str:
    return _ATTRIBUTE_KEY.sub("-", name.strip()).strip("-").casefold() or "attribute"


def _definition_ref(node: ET.Element) -> str:
    definition = _child(node, "DEFINITION")
    if definition is None:
        return ""
    for child in definition:
        text = "".join(child.itertext()).strip()
        if text:
            return text
    return ""


def build_migration_plan(
    root: ET.Element,
    *,
    type_map: Mapping[str, str] | None = None,
    relation_map: Mapping[str, str] | None = None,
) -> SphinxNeedsMigrationPlan:
    """Build a conservative migration plan from a parsed ReqIF document."""
    types = dict(type_map or {})
    relations = dict(relation_map or {})
    content = _descendants(root, "REQ-IF-CONTENT")
    if not content:
        raise ReqifMigrationError("ReqIF document has no REQ-IF-CONTENT")
    content = content[0]

    enum_labels = _enum_labels(content)
    fields_by_definition = _attribute_fields(content)
    object_types = _type_labels(content, "SPEC-OBJECT-TYPE")
    relation_types = _type_labels(content, "SPEC-RELATION-TYPE")

    issues: list[MigrationIssue] = []
    objects: dict[str, dict[str, object]] = {}
    spec_objects = _child(content, "SPEC-OBJECTS")
    for node in _children(spec_objects, "SPEC-OBJECT"):
        identifier = node.get("IDENTIFIER")
        if not identifier:
            raise ReqifMigrationError("a SPEC-OBJECT is missing its IDENTIFIER")
        if identifier in objects:
            raise ReqifMigrationError(f"duplicate SPEC-OBJECT IDENTIFIER {identifier!r}")
        type_ref = _child_text(_child(node, "TYPE"), "SPEC-OBJECT-TYPE-REF")
        source_type = object_types.get(type_ref, type_ref)
        fields: dict[str, str] = {}
        values = _child(node, "VALUES")
        for value in list(values) if values is not None else []:
            definition = _definition_ref(value)
            field = fields_by_definition.get(definition)
            text, loss = _value_text(value, enum_labels)
            if loss is not None:
                issues.append(
                    MigrationIssue(
                        code="VALUE_FLATTENED",
                        message=(
                            f"ReqIF value of kind {_local(value.tag).removeprefix('ATTRIBUTE-VALUE-')!r} "
                            f"for {identifier!r} was recovered as text ({loss})"
                        ),
                        need_id=identifier,
                        field=definition or None,
                    )
                )
            if field is None:
                issues.append(
                    MigrationIssue(
                        code="ATTRIBUTE_UNMAPPED",
                        message=(
                            f"attribute definition {definition!r} on {identifier!r} "
                            "has no LONG-NAME to recover it under"
                        ),
                        need_id=identifier,
                        field=definition or None,
                    )
                )
                continue
            fields.setdefault(field, text)
        objects[identifier] = {
            "source_id": fields.get("canonical-id") or identifier,
            "source_type": source_type,
            "title": node.get("LONG-NAME") or "",
            "desc": node.get("DESC") or "",
            "fields": fields,
        }

    recovered: dict[str, str] = {}
    for identifier, payload in objects.items():
        source_id = str(payload["source_id"])
        if source_id in recovered:
            raise ReqifMigrationError(
                f"two SPEC-OBJECTs recover the same canonical ID {source_id!r} "
                f"({recovered[source_id]!r} and {identifier!r})"
            )
        recovered[source_id] = identifier

    migrated: dict[str, list[MigratedRelation]] = {}
    spec_relations = _child(content, "SPEC-RELATIONS")
    for node in _children(spec_relations, "SPEC-RELATION"):
        source_ref = _child_text(_child(node, "SOURCE"), "SPEC-OBJECT-REF")
        target_ref = _child_text(_child(node, "TARGET"), "SPEC-OBJECT-REF")
        type_ref = _child_text(_child(node, "TYPE"), "SPEC-RELATION-TYPE-REF")
        relation_label = relation_types.get(type_ref, type_ref)
        if source_ref not in objects or target_ref not in objects:
            issues.append(
                MigrationIssue(
                    code="RELATION_TARGET_UNKNOWN",
                    message=(
                        f"ReqIF relation references an object not present in the "
                        f"document ({source_ref!r} -> {target_ref!r})"
                    ),
                    need_id=source_ref or None,
                    field=relation_label or None,
                )
            )
            continue
        canonical = relations.get(relation_label)
        if canonical is None:
            issues.append(
                MigrationIssue(
                    code="RELATION_UNMAPPED",
                    message=(
                        f"ReqIF relation type {relation_label!r} has no explicit "
                        "relation mapping"
                    ),
                    need_id=str(objects[source_ref]["source_id"]),
                    field=relation_label or None,
                )
            )
            continue
        migrated.setdefault(source_ref, []).append(
            MigratedRelation(
                source=str(objects[source_ref]["source_id"]),
                relation=canonical,
                target=str(objects[target_ref]["source_id"]),
                source_field=relation_label,
            )
        )

    for node in _descendants(content, "SPEC-HIERARCHY"):
        if _children(node, "CHILDREN"):
            issues.append(
                MigrationIssue(
                    code="HIERARCHY_UNMAPPED",
                    message=(
                        "ReqIF hierarchy children are not mapped to authored "
                        "containment; author part-of relations explicitly"
                    ),
                    need_id=node.get("IDENTIFIER"),
                )
            )

    candidates: list[SphinxNeedCandidate] = []
    for identifier in sorted(
        objects,
        key=lambda value: (
            str(objects[value]["source_id"]).casefold(),
            str(objects[value]["source_id"]),
        ),
    ):
        payload = objects[identifier]
        source_id = str(payload["source_id"])
        fields = payload["fields"]
        assert isinstance(fields, dict)
        source_type = str(payload["source_type"])
        target_type = types.get(source_type)
        if target_type is None:
            issues.append(
                MigrationIssue(
                    code="TYPE_UNMAPPED",
                    message=(
                        f"ReqIF object type {source_type!r} has no explicit type mapping"
                    ),
                    need_id=source_id,
                    field=source_type or None,
                )
            )

        extras: dict[str, object] = {}
        raw_extras = fields.get("attributes-json")
        if raw_extras is not None:
            try:
                parsed = json.loads(raw_extras)
            except json.JSONDecodeError:
                issues.append(
                    MigrationIssue(
                        code="EXTRAS_INVALID",
                        message=(
                            f"quarto-needs.attributes-json on {source_id!r} is not valid JSON"
                        ),
                        need_id=source_id,
                        field="attributes-json",
                    )
                )
            else:
                if isinstance(parsed, dict):
                    extras.update(parsed)
                else:
                    issues.append(
                        MigrationIssue(
                            code="EXTRAS_INVALID",
                            message=(
                                f"quarto-needs.attributes-json on {source_id!r} must be a JSON object"
                            ),
                            need_id=source_id,
                            field="attributes-json",
                        )
                    )
        for field, value in fields.items():
            if field in _CORE_FIELDS:
                continue
            key = _attribute_key(field)
            if key != field:
                issues.append(
                    MigrationIssue(
                        code="ATTRIBUTE_RENAMED",
                        message=(
                            f"ReqIF attribute {field!r} was authored as {key!r} "
                            "because the .need grammar has no escape for it"
                        ),
                        need_id=source_id,
                        field=field,
                    )
                )
            extras.setdefault(key, value)

        content_text = str(fields.get("body", ""))
        rationale = str(fields.get("rationale", "")).strip()
        if rationale:
            content_text = (
                f"{content_text}\n\n### Rationale\n{rationale}"
                if content_text
                else f"### Rationale\n{rationale}"
            )

        field_tags = tuple(
            part.strip()
            for part in str(fields.get("tags", "")).split(";")
            if part.strip()
        )
        lifted_tags: tuple[str, ...] = ()
        if "tags" in extras:
            lifted = extras.pop("tags")
            if isinstance(lifted, list):
                lifted_tags = tuple(
                    str(value).strip() for value in lifted if str(value).strip()
                )
            elif isinstance(lifted, str):
                lifted_tags = tuple(
                    part.strip() for part in lifted.split(";") if part.strip()
                )

        candidates.append(
            SphinxNeedCandidate(
                source_id=source_id,
                source_type=source_type,
                target_type=target_type,
                title=(
                    str(payload["title"])
                    or str(payload["desc"])
                    or str(fields.get("canonical-id", ""))
                    or source_id
                ),
                content=content_text,
                status=str(fields.get("status", "")).strip() or None,
                tags=field_tags or lifted_tags,
                relations=tuple(
                    sorted(
                        migrated.get(identifier, ()),
                        key=lambda relation: (relation.relation, relation.target),
                    )
                ),
                unmapped_links={},
                extras=dict(sorted(extras.items())),
            )
        )

    header = _descendants(root, "REQ-IF-HEADER")
    header = header[0] if header else None
    return SphinxNeedsMigrationPlan(
        source_project=_child_text(header, "TITLE") or None,
        source_version=_child_text(header, "REQ-IF-VERSION") or "unknown",
        candidates=tuple(candidates),
        issues=tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.need_id or "",
                    issue.code,
                    issue.field or "",
                    issue.message,
                ),
            )
        ),
        tool="ReqIF",
        schema="reqif-migration-plan-v1",
    )
