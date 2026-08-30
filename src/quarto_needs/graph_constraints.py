"""Bounded declarative constraints over the canonical engineering graph.

Graph constraints consume named-query scopes and canonical relation views. They
never evaluate arbitrary expressions or code. Each violation is emitted as a
normal Finding so quality, diff, PR, and GitHub projections reuse one contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from .diagnostics import Finding
from .queries import query_ids
from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot, ObjectRecord


class GraphConstraintError(ValueError):
    """A declarative graph constraint violates the bounded grammar."""


ConstraintKind = Literal[
    "required-path",
    "forbidden-cycle",
    "connected",
    "max-relations",
]


@dataclass(frozen=True, slots=True)
class GraphConstraintSpec:
    name: str
    kind: ConstraintKind
    scope: str | None = None
    relations: tuple[str, ...] = ()
    target_role: str | None = None
    minimum: int = 1
    maximum: int | None = None
    severity: str = "error"

    @property
    def code(self) -> str:
        return f"CONSTRAINT:{self.name}"

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "kind": self.kind,
            "relations": list(self.relations),
            "severity": self.severity,
        }
        if self.scope is not None:
            payload["scope"] = self.scope
        if self.target_role is not None:
            payload["target-role"] = self.target_role
        if self.kind == "connected":
            payload["minimum"] = self.minimum
        if self.maximum is not None:
            payload["maximum"] = self.maximum
        return payload


_ALLOWED_KEYS = frozenset(
    {"kind", "scope", "relations", "target-role", "minimum", "maximum", "severity"}
)
_SEVERITIES = frozenset({"error", "warning", "info"})
_KINDS = frozenset({"required-path", "forbidden-cycle", "connected", "max-relations"})


def _nonempty(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GraphConstraintError(f"{context} must be a non-empty string")
    return value.strip()


def _positive_int(value: object, context: str, *, default: int | None = None) -> int:
    if value is None and default is not None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise GraphConstraintError(f"{context} must be an integer >= 1")
    return value


def _relations(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise GraphConstraintError(f"{context} must be a non-empty array of relation names")
    resolved: list[str] = []
    for authored in value:
        try:
            resolved.append(DEFAULT_RELATION_CATALOG.resolve(authored).v1_name)
        except ValueError as error:
            raise GraphConstraintError(f"{context}: {error}") from error
    return tuple(resolved)


def compile_graph_constraint(name: str, raw: Mapping[str, object]) -> GraphConstraintSpec:
    constraint_name = _nonempty(name, "constraint name")
    if not isinstance(raw, Mapping):
        raise GraphConstraintError(f"constraint {constraint_name} must be a table")
    unknown = set(raw) - _ALLOWED_KEYS
    if unknown:
        raise GraphConstraintError(
            f"constraint {constraint_name} has unknown keys: {', '.join(sorted(unknown))}"
        )
    kind_raw = raw.get("kind")
    if not isinstance(kind_raw, str) or kind_raw not in _KINDS:
        raise GraphConstraintError(
            f"constraint {constraint_name}.kind must be one of: {', '.join(sorted(_KINDS))}"
        )
    kind: ConstraintKind = kind_raw  # type: ignore[assignment]
    severity = raw.get("severity", "error")
    if not isinstance(severity, str) or severity not in _SEVERITIES:
        raise GraphConstraintError(
            f"constraint {constraint_name}.severity must be one of: error, warning, info"
        )
    scope_raw = raw.get("scope")
    scope = _nonempty(scope_raw, f"constraint {constraint_name}.scope") if scope_raw is not None else None
    target_role_raw = raw.get("target-role")
    target_role = (
        _nonempty(target_role_raw, f"constraint {constraint_name}.target-role")
        if target_role_raw is not None
        else None
    )

    if kind == "required-path":
        if scope is None:
            raise GraphConstraintError(f"constraint {constraint_name}.scope is required for required-path")
        relations = _relations(raw.get("relations"), f"constraint {constraint_name}.relations")
        if "minimum" in raw or "maximum" in raw:
            raise GraphConstraintError(f"constraint {constraint_name} required-path does not accept minimum/maximum")
        return GraphConstraintSpec(
            constraint_name, kind, scope, relations, target_role, severity=severity
        )

    if kind == "forbidden-cycle":
        relations = _relations(raw.get("relations"), f"constraint {constraint_name}.relations")
        if target_role is not None or "minimum" in raw or "maximum" in raw:
            raise GraphConstraintError(
                f"constraint {constraint_name} forbidden-cycle accepts only kind/scope/relations/severity"
            )
        return GraphConstraintSpec(
            constraint_name, kind, scope, relations, severity=severity
        )

    if kind == "connected":
        if scope is None:
            raise GraphConstraintError(f"constraint {constraint_name}.scope is required for connected")
        if target_role is not None or "maximum" in raw:
            raise GraphConstraintError(
                f"constraint {constraint_name} connected does not accept target-role/maximum"
            )
        relation_values = raw.get("relations")
        relations = (
            _relations(relation_values, f"constraint {constraint_name}.relations")
            if relation_values is not None
            else ()
        )
        minimum = _positive_int(
            raw.get("minimum"), f"constraint {constraint_name}.minimum", default=1
        )
        return GraphConstraintSpec(
            constraint_name, kind, scope, relations, minimum=minimum, severity=severity
        )

    # max-relations
    if scope is None:
        raise GraphConstraintError(f"constraint {constraint_name}.scope is required for max-relations")
    relations = _relations(raw.get("relations"), f"constraint {constraint_name}.relations")
    if len(relations) != 1:
        raise GraphConstraintError(
            f"constraint {constraint_name} max-relations requires exactly one relation"
        )
    if "minimum" in raw:
        raise GraphConstraintError(f"constraint {constraint_name} max-relations does not accept minimum")
    maximum = _positive_int(raw.get("maximum"), f"constraint {constraint_name}.maximum")
    return GraphConstraintSpec(
        constraint_name,
        kind,
        scope,
        relations,
        target_role,
        maximum=maximum,
        severity=severity,
    )


def compile_graph_constraints(
    raw: Mapping[str, object] | None,
) -> Mapping[str, GraphConstraintSpec]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise GraphConstraintError("[constraints] must be a table")
    compiled: dict[str, GraphConstraintSpec] = {}
    for name in sorted(raw, key=lambda value: (str(value).casefold(), str(value))):
        if not isinstance(name, str):
            raise GraphConstraintError("constraint names must be strings")
        value = raw[name]
        if not isinstance(value, Mapping):
            raise GraphConstraintError(f"constraint {name} must be a table")
        compiled[name] = compile_graph_constraint(name, value)
    return compiled


def _role(config: object, record: ObjectRecord) -> str | None:
    configured: Mapping[str, str] = getattr(config, "type_roles", {}) or {}
    value = configured.get(record.type)
    if value is not None:
        return value
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


def _logical_targets(
    snapshot: AnalysisSnapshot,
    object_id: str,
    relation_name: str,
) -> tuple[str, ...]:
    try:
        inverse = DEFAULT_RELATION_CATALOG.inverse_v1_name(relation_name)
    except ValueError as error:
        raise GraphConstraintError(str(error)) from error
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


def _scope_ids(spec: GraphConstraintSpec, snapshot: AnalysisSnapshot, config: object) -> tuple[str, ...]:
    if spec.scope is None:
        return tuple(record.id for record in snapshot.objects)
    try:
        return query_ids(config, snapshot, spec.scope)
    except ValueError as error:
        raise GraphConstraintError(
            f"constraint {spec.name} scope {spec.scope!r}: {error}"
        ) from error


def _finding(
    spec: GraphConstraintSpec,
    record: ObjectRecord,
    message: str,
    properties: Mapping[str, object],
) -> Finding:
    location = record.locations[0] if record.locations else None
    return Finding(spec.code, spec.severity, message, record.id, location, dict(properties))


def _required_path(
    spec: GraphConstraintSpec, snapshot: AnalysisSnapshot, config: object
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for object_id in _scope_ids(spec, snapshot, config):
        current: dict[str, tuple[str, ...]] = {object_id: (object_id,)}
        for relation in spec.relations:
            next_nodes: dict[str, tuple[str, ...]] = {}
            for node_id, path in current.items():
                for target in _logical_targets(snapshot, node_id, relation):
                    candidate = path + (target,)
                    previous = next_nodes.get(target)
                    if previous is None or candidate < previous:
                        next_nodes[target] = candidate
            current = next_nodes
            if not current:
                break
        valid = [
            (target, path)
            for target, path in current.items()
            if spec.target_role is None
            or _role(config, snapshot.objects_by_id[target]) == spec.target_role
        ]
        if valid:
            continue
        record = snapshot.objects_by_id[object_id]
        findings.append(
            _finding(
                spec,
                record,
                f"{object_id} has no required path {' -> '.join(spec.relations)}"
                + (f" to role {spec.target_role}" if spec.target_role else ""),
                {
                    "kind": spec.kind,
                    "relations": list(spec.relations),
                    "targetRole": spec.target_role,
                },
            )
        )
    return tuple(findings)


def _forbidden_cycle(
    spec: GraphConstraintSpec, snapshot: AnalysisSnapshot, config: object
) -> tuple[Finding, ...]:
    selected = set(_scope_ids(spec, snapshot, config))
    graph = {
        object_id: tuple(
            target
            for relation in spec.relations
            for target in _logical_targets(snapshot, object_id, relation)
            if target in selected
        )
        for object_id in sorted(selected)
    }
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> tuple[str, ...] | None:
        if node in visiting:
            index = stack.index(node)
            return tuple(stack[index:] + [node])
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for target in sorted(set(graph.get(node, ()))):
            cycle = visit(target)
            if cycle is not None:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for object_id in sorted(selected):
        cycle = visit(object_id)
        if cycle is None:
            continue
        record = snapshot.objects_by_id[cycle[0]]
        return (
            _finding(
                spec,
                record,
                f"Forbidden graph cycle: {' -> '.join(cycle)}",
                {
                    "kind": spec.kind,
                    "relations": list(spec.relations),
                    "cycle": list(cycle),
                },
            ),
        )
    return ()


def _connected(
    spec: GraphConstraintSpec, snapshot: AnalysisSnapshot, config: object
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    allowed = set(spec.relations)
    inverse_names = {
        name: DEFAULT_RELATION_CATALOG.inverse_v1_name(name) for name in allowed
    }
    for object_id in _scope_ids(spec, snapshot, config):
        if not allowed:
            count = len(snapshot.outgoing.get(object_id, ())) + len(snapshot.incoming.get(object_id, ()))
        else:
            neighbors: set[tuple[str, str]] = set()
            for name in allowed:
                for target in _logical_targets(snapshot, object_id, name):
                    neighbors.add((name, target))
                inverse = inverse_names.get(name)
                if inverse is not None:
                    for target in _logical_targets(snapshot, object_id, inverse):
                        neighbors.add((inverse, target))
            count = len(neighbors)
        if count >= spec.minimum:
            continue
        record = snapshot.objects_by_id[object_id]
        findings.append(
            _finding(
                spec,
                record,
                f"{object_id} has {count} qualifying graph connection(s); at least {spec.minimum} required",
                {
                    "kind": spec.kind,
                    "relations": list(spec.relations),
                    "actual": count,
                    "minimum": spec.minimum,
                },
            )
        )
    return tuple(findings)


def _max_relations(
    spec: GraphConstraintSpec, snapshot: AnalysisSnapshot, config: object
) -> tuple[Finding, ...]:
    assert spec.maximum is not None
    relation = spec.relations[0]
    findings: list[Finding] = []
    for object_id in _scope_ids(spec, snapshot, config):
        targets = [
            target
            for target in _logical_targets(snapshot, object_id, relation)
            if spec.target_role is None
            or _role(config, snapshot.objects_by_id[target]) == spec.target_role
        ]
        if len(targets) <= spec.maximum:
            continue
        record = snapshot.objects_by_id[object_id]
        findings.append(
            _finding(
                spec,
                record,
                f"{object_id} has {len(targets)} {relation} relation(s); at most {spec.maximum} allowed",
                {
                    "kind": spec.kind,
                    "relation": relation,
                    "targetRole": spec.target_role,
                    "targets": targets,
                    "actual": len(targets),
                    "maximum": spec.maximum,
                },
            )
        )
    return tuple(findings)


def evaluate_graph_constraint(
    spec: GraphConstraintSpec,
    snapshot: AnalysisSnapshot,
    config: object,
) -> tuple[Finding, ...]:
    if spec.kind == "required-path":
        return _required_path(spec, snapshot, config)
    if spec.kind == "forbidden-cycle":
        return _forbidden_cycle(spec, snapshot, config)
    if spec.kind == "connected":
        return _connected(spec, snapshot, config)
    return _max_relations(spec, snapshot, config)


def evaluate_graph_constraints(
    constraints: Mapping[str, GraphConstraintSpec],
    snapshot: AnalysisSnapshot,
    config: object,
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for name in sorted(constraints, key=lambda value: (value.casefold(), value)):
        findings.extend(evaluate_graph_constraint(constraints[name], snapshot, config))
    return tuple(findings)
