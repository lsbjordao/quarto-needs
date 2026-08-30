"""Safe derived values and deterministic build variants.

The grammar is deliberately finite: derived values can count logical relation
targets or test whether a fixed relation path exists. Variants start from a
named-query scope and may expand over an explicitly listed relation set up to a
bounded depth. No expressions, templates, callbacks, or arbitrary code are
executed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from .queries import query_ids
from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot, ObjectRecord


class DerivedError(ValueError):
    """A derived-field or variant declaration violates the bounded grammar."""


DerivedOperation = Literal["relation-count", "path-exists"]
MAX_VARIANT_DEPTH = 10


@dataclass(frozen=True, slots=True)
class DerivedFieldSpec:
    name: str
    scope: str
    operation: DerivedOperation
    relations: tuple[str, ...]
    target_role: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "scope": self.scope,
            "operation": self.operation,
            "relations": list(self.relations),
        }
        if self.target_role is not None:
            payload["target-role"] = self.target_role
        return payload


@dataclass(frozen=True, slots=True)
class VariantSpec:
    name: str
    scope: str
    relations: tuple[str, ...] = ()
    depth: int = 0

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"scope": self.scope}
        if self.relations:
            payload["relations"] = list(self.relations)
            payload["depth"] = self.depth
        return payload


_DERIVED_KEYS = frozenset({"scope", "operation", "relation", "relations", "target-role"})
_VARIANT_KEYS = frozenset({"scope", "relations", "depth"})
_OPERATIONS = frozenset({"relation-count", "path-exists"})


def _nonempty(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DerivedError(f"{context} must be a non-empty string")
    return value.strip()


def _relations(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise DerivedError(f"{context} must be a non-empty array of relation names")
    resolved: list[str] = []
    for authored in value:
        try:
            resolved.append(DEFAULT_RELATION_CATALOG.resolve(authored).v1_name)
        except ValueError as error:
            raise DerivedError(f"{context}: {error}") from error
    return tuple(resolved)


def compile_derived_field(name: str, raw: Mapping[str, object]) -> DerivedFieldSpec:
    field_name = _nonempty(name, "derived field name")
    if not isinstance(raw, Mapping):
        raise DerivedError(f"derived field {field_name} must be a table")
    unknown = set(raw) - _DERIVED_KEYS
    if unknown:
        raise DerivedError(
            f"derived field {field_name} has unknown keys: {', '.join(sorted(unknown))}"
        )
    scope = _nonempty(raw.get("scope"), f"derived field {field_name}.scope")
    operation_raw = raw.get("operation")
    if not isinstance(operation_raw, str) or operation_raw not in _OPERATIONS:
        raise DerivedError(
            f"derived field {field_name}.operation must be one of: "
            f"{', '.join(sorted(_OPERATIONS))}"
        )
    operation: DerivedOperation = operation_raw  # type: ignore[assignment]
    target_role_raw = raw.get("target-role")
    target_role = (
        _nonempty(target_role_raw, f"derived field {field_name}.target-role")
        if target_role_raw is not None
        else None
    )
    if operation == "relation-count":
        if "relations" in raw:
            raise DerivedError(
                f"derived field {field_name} relation-count accepts relation, not relations"
            )
        relation = _nonempty(raw.get("relation"), f"derived field {field_name}.relation")
        try:
            canonical = DEFAULT_RELATION_CATALOG.resolve(relation).v1_name
        except ValueError as error:
            raise DerivedError(f"derived field {field_name}.relation: {error}") from error
        return DerivedFieldSpec(field_name, scope, operation, (canonical,), target_role)

    if "relation" in raw:
        raise DerivedError(
            f"derived field {field_name} path-exists accepts relations, not relation"
        )
    relations = _relations(raw.get("relations"), f"derived field {field_name}.relations")
    return DerivedFieldSpec(field_name, scope, operation, relations, target_role)


def compile_derived_fields(raw: Mapping[str, object] | None) -> Mapping[str, DerivedFieldSpec]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise DerivedError("[derived] must be a table")
    compiled: dict[str, DerivedFieldSpec] = {}
    for name in sorted(raw, key=lambda value: (str(value).casefold(), str(value))):
        if not isinstance(name, str):
            raise DerivedError("derived field names must be strings")
        value = raw[name]
        if not isinstance(value, Mapping):
            raise DerivedError(f"derived field {name} must be a table")
        compiled[name] = compile_derived_field(name, value)
    return compiled


def compile_variant(name: str, raw: Mapping[str, object]) -> VariantSpec:
    variant_name = _nonempty(name, "variant name")
    if not isinstance(raw, Mapping):
        raise DerivedError(f"variant {variant_name} must be a table")
    unknown = set(raw) - _VARIANT_KEYS
    if unknown:
        raise DerivedError(
            f"variant {variant_name} has unknown keys: {', '.join(sorted(unknown))}"
        )
    scope = _nonempty(raw.get("scope"), f"variant {variant_name}.scope")
    relation_values = raw.get("relations")
    if relation_values is None:
        if "depth" in raw:
            raise DerivedError(
                f"variant {variant_name}.depth requires an explicit relations array"
            )
        return VariantSpec(variant_name, scope)
    relations = _relations(relation_values, f"variant {variant_name}.relations")
    depth = raw.get("depth", 1)
    if isinstance(depth, bool) or not isinstance(depth, int) or not 1 <= depth <= MAX_VARIANT_DEPTH:
        raise DerivedError(
            f"variant {variant_name}.depth must be an integer between 1 and {MAX_VARIANT_DEPTH}"
        )
    return VariantSpec(variant_name, scope, relations, depth)


def compile_variants(raw: Mapping[str, object] | None) -> Mapping[str, VariantSpec]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise DerivedError("[variants] must be a table")
    compiled: dict[str, VariantSpec] = {}
    for name in sorted(raw, key=lambda value: (str(value).casefold(), str(value))):
        if not isinstance(name, str):
            raise DerivedError("variant names must be strings")
        value = raw[name]
        if not isinstance(value, Mapping):
            raise DerivedError(f"variant {name} must be a table")
        compiled[name] = compile_variant(name, value)
    return compiled


def _role(config: object, record: ObjectRecord) -> str | None:
    configured: Mapping[str, str] = getattr(config, "type_roles", {}) or {}
    role = configured.get(record.type)
    if role is not None:
        return role
    if record.type.endswith("requirement"):
        return "requirement"
    if record.type == "test-case":
        return "verification"
    if record.type == "evidence":
        return "evidence"
    if record.type == "architecture-decision":
        return "decision"
    if record.type in {"component", "interface"}:
        return "architecture-element"
    if record.type == "source-module":
        return "implementation-artifact"
    return None


def _logical_targets(snapshot: AnalysisSnapshot, object_id: str, relation_name: str) -> tuple[str, ...]:
    try:
        inverse = DEFAULT_RELATION_CATALOG.inverse_v1_name(relation_name)
    except ValueError as error:
        raise DerivedError(str(error)) from error
    targets = {
        edge.target
        for edge in snapshot.outgoing.get(object_id, ())
        if edge.v1_name == relation_name and edge.target in snapshot.objects_by_id
    }
    if inverse is not None:
        targets.update(
            edge.source
            for edge in snapshot.incoming.get(object_id, ())
            if edge.v1_name == inverse and edge.source in snapshot.objects_by_id
        )
    return tuple(sorted(targets, key=lambda value: (value.casefold(), value)))


def _scope_ids(config: object, snapshot: AnalysisSnapshot, name: str, owner: str) -> tuple[str, ...]:
    try:
        return query_ids(config, snapshot, name)
    except ValueError as error:
        raise DerivedError(f"{owner} scope {name!r}: {error}") from error


def materialize_derived(
    specs: Mapping[str, DerivedFieldSpec],
    snapshot: AnalysisSnapshot,
    config: object,
) -> Mapping[str, Mapping[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for name in sorted(specs, key=lambda value: (value.casefold(), value)):
        spec = specs[name]
        for object_id in _scope_ids(config, snapshot, spec.scope, f"derived field {name}"):
            if spec.operation == "relation-count":
                targets = [
                    target
                    for target in _logical_targets(snapshot, object_id, spec.relations[0])
                    if spec.target_role is None
                    or _role(config, snapshot.objects_by_id[target]) == spec.target_role
                ]
                value: object = len(targets)
            else:
                current = {object_id}
                for relation in spec.relations:
                    current = {
                        target
                        for source in current
                        for target in _logical_targets(snapshot, source, relation)
                    }
                    if not current:
                        break
                value = any(
                    spec.target_role is None
                    or _role(config, snapshot.objects_by_id[target]) == spec.target_role
                    for target in current
                )
            result.setdefault(object_id, {})[name] = value
    return {
        object_id: {
            name: fields[name]
            for name in sorted(fields, key=lambda value: (value.casefold(), value))
        }
        for object_id, fields in sorted(
            result.items(), key=lambda item: (item[0].casefold(), item[0])
        )
    }


def materialize_variants(
    specs: Mapping[str, VariantSpec],
    snapshot: AnalysisSnapshot,
    config: object,
) -> Mapping[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for name in sorted(specs, key=lambda value: (value.casefold(), value)):
        spec = specs[name]
        selected = set(_scope_ids(config, snapshot, spec.scope, f"variant {name}"))
        frontier = set(selected)
        for _ in range(spec.depth):
            if not frontier or not spec.relations:
                break
            discovered: set[str] = set()
            for object_id in frontier:
                for relation in spec.relations:
                    discovered.update(_logical_targets(snapshot, object_id, relation))
                    try:
                        inverse = DEFAULT_RELATION_CATALOG.inverse_v1_name(relation)
                    except ValueError as error:
                        raise DerivedError(str(error)) from error
                    if inverse is not None:
                        discovered.update(_logical_targets(snapshot, object_id, inverse))
            discovered.difference_update(selected)
            selected.update(discovered)
            frontier = discovered
        result[name] = tuple(sorted(selected, key=lambda value: (value.casefold(), value)))
    return result
