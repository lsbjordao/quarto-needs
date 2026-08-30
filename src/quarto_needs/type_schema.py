"""Per-type JSON Schema validation for engineering object attributes.

Schemas validate the `attributes` mapping only; identity, type, status, title,
body, rationale, and relations retain their dedicated Quarto-Needs semantics.
Remote references are rejected so configuration cannot trigger network access.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from .diagnostics import Finding
from .snapshot import AnalysisSnapshot, ObjectRecord, thaw_json


class TypeSchemaError(ValueError):
    """A configured per-type attribute schema is invalid or unsafe."""


@dataclass(frozen=True, slots=True)
class TypeSchemaSpec:
    type_name: str
    schema: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return dict(self.schema)


def _walk_refs(value: object, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            current = path + (key_text,)
            if key_text in {"$ref", "$dynamicRef"}:
                if not isinstance(child, str) or not child.startswith("#"):
                    dotted = "/".join(current)
                    raise TypeSchemaError(
                        f"attribute schema reference {dotted} must be local (#...)"
                    )
            _walk_refs(child, current)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _walk_refs(child, path + (str(index),))


def compile_type_schema(type_name: str, raw: Mapping[str, object]) -> TypeSchemaSpec:
    if not isinstance(type_name, str) or not type_name.strip():
        raise TypeSchemaError("type schema name must be a non-empty string")
    if not isinstance(raw, Mapping):
        raise TypeSchemaError(f"attribute schema for {type_name} must be a table")
    schema = dict(raw)
    _walk_refs(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        message = error.message or str(error)
        raise TypeSchemaError(
            f"attribute schema for {type_name} is not valid Draft 2020-12 JSON Schema: {message}"
        ) from error
    return TypeSchemaSpec(type_name=type_name.strip(), schema=schema)


def compile_type_schemas(
    raw: Mapping[str, Mapping[str, object]] | None,
) -> Mapping[str, TypeSchemaSpec]:
    if raw is None:
        return {}
    compiled: dict[str, TypeSchemaSpec] = {}
    for type_name in sorted(raw, key=lambda value: (value.casefold(), value)):
        compiled[type_name] = compile_type_schema(type_name, raw[type_name])
    return compiled


def _json_pointer(parts: Sequence[object]) -> str:
    if not parts:
        return ""
    escaped = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(escaped)


def _location(record: ObjectRecord):
    return record.locations[0] if record.locations else None


def _validation_key(error: ValidationError) -> tuple[object, ...]:
    return (
        tuple(str(part) for part in error.absolute_path),
        tuple(str(part) for part in error.absolute_schema_path),
        error.validator or "",
        error.message,
    )


def validate_type_schemas(
    schemas: Mapping[str, TypeSchemaSpec],
    snapshot: AnalysisSnapshot,
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    validators = {
        type_name: Draft202012Validator(spec.schema)
        for type_name, spec in schemas.items()
    }
    for record in snapshot.objects:
        validator = validators.get(record.type)
        if validator is None:
            continue
        instance = thaw_json(record.attributes)
        errors = sorted(validator.iter_errors(instance), key=_validation_key)
        for error in errors:
            instance_path = _json_pointer(tuple(error.absolute_path))
            schema_path = _json_pointer(tuple(error.absolute_schema_path))
            location_text = instance_path or "/"
            findings.append(
                Finding(
                    "OBJ002",
                    "error",
                    f"{record.id} attributes violate schema at {location_text}: {error.message}",
                    record.id,
                    _location(record),
                    {
                        "type": record.type,
                        "instancePath": instance_path,
                        "schemaPath": schema_path,
                        "validator": error.validator,
                    },
                )
            )
    return tuple(findings)
