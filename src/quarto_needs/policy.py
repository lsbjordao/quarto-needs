"""Bounded declarative engineering policies.

The policy language is intentionally small. It composes existing named-query
selection, canonical relation semantics, and configured type roles. It never
evaluates Python, Lua, JavaScript, expressions, templates, or shell commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .diagnostics import Finding
from .queries import query_ids
from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot


class PolicyError(ValueError):
    """A declarative policy violates the bounded policy grammar."""


@dataclass(frozen=True, slots=True)
class PolicySpec:
    name: str
    scope: str
    assert_relation: str
    target_role: str | None = None
    minimum: int = 1
    severity: str = "error"

    @property
    def code(self) -> str:
        return f"POLICY:{self.name}"

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "scope": self.scope,
            "assert-relation": self.assert_relation,
            "minimum": self.minimum,
            "severity": self.severity,
        }
        if self.target_role is not None:
            payload["target-role"] = self.target_role
        return payload


_ALLOWED_KEYS = frozenset(
    {"scope", "assert-relation", "target-role", "minimum", "severity"}
)
_SEVERITIES = frozenset({"error", "warning", "info"})


def _nonempty_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f"{context} must be a non-empty string")
    return value.strip()


def compile_policy(name: str, raw: Mapping[str, object]) -> PolicySpec:
    policy_name = _nonempty_string(name, "policy name")
    if not isinstance(raw, Mapping):
        raise PolicyError(f"policy {policy_name} must be a table")
    unknown = set(raw) - _ALLOWED_KEYS
    if unknown:
        raise PolicyError(
            f"policy {policy_name} has unknown keys: {', '.join(sorted(unknown))}"
        )
    scope = _nonempty_string(raw.get("scope"), f"policy {policy_name}.scope")
    authored_relation = _nonempty_string(
        raw.get("assert-relation"), f"policy {policy_name}.assert-relation"
    )
    try:
        relation = DEFAULT_RELATION_CATALOG.resolve(authored_relation).v1_name
    except ValueError as error:
        raise PolicyError(f"policy {policy_name}: {error}") from error

    target_role_raw = raw.get("target-role")
    target_role = (
        _nonempty_string(target_role_raw, f"policy {policy_name}.target-role")
        if target_role_raw is not None
        else None
    )
    minimum_raw = raw.get("minimum", 1)
    if (
        isinstance(minimum_raw, bool)
        or not isinstance(minimum_raw, int)
        or minimum_raw < 1
    ):
        raise PolicyError(f"policy {policy_name}.minimum must be an integer >= 1")
    severity = raw.get("severity", "error")
    if not isinstance(severity, str) or severity not in _SEVERITIES:
        raise PolicyError(
            f"policy {policy_name}.severity must be one of: error, warning, info"
        )
    return PolicySpec(
        name=policy_name,
        scope=scope,
        assert_relation=relation,
        target_role=target_role,
        minimum=minimum_raw,
        severity=severity,
    )


def compile_policies(raw: Mapping[str, object] | None) -> Mapping[str, PolicySpec]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise PolicyError("[policies] must be a table")
    compiled: dict[str, PolicySpec] = {}
    for name in sorted(raw, key=lambda value: (str(value).casefold(), str(value))):
        if not isinstance(name, str):
            raise PolicyError("policy names must be strings")
        value = raw[name]
        if not isinstance(value, Mapping):
            raise PolicyError(f"policy {name} must be a table")
        compiled[name] = compile_policy(name, value)
    return compiled


def _target_role(config: object, snapshot: AnalysisSnapshot, target: str) -> str | None:
    record = snapshot.objects_by_id.get(target)
    if record is None:
        return None
    roles: Mapping[str, str] = getattr(config, "type_roles", {}) or {}
    return roles.get(record.type)


def evaluate_policy(
    spec: PolicySpec,
    snapshot: AnalysisSnapshot,
    config: object,
) -> tuple[Finding, ...]:
    try:
        scoped_ids = query_ids(config, snapshot, spec.scope)
    except ValueError as error:
        raise PolicyError(f"policy {spec.name} scope {spec.scope!r}: {error}") from error

    findings: list[Finding] = []
    for object_id in scoped_ids:
        source = snapshot.objects_by_id.get(object_id)
        if source is None:
            continue
        matches = []
        for relation in snapshot.outgoing.get(object_id, ()):
            if relation.v1_name != spec.assert_relation:
                continue
            if relation.target not in snapshot.objects_by_id:
                continue
            if spec.target_role is not None and _target_role(config, snapshot, relation.target) != spec.target_role:
                continue
            matches.append(relation)
        if len(matches) >= spec.minimum:
            continue
        role_text = f" to role {spec.target_role}" if spec.target_role else ""
        location = source.locations[0] if source.locations else None
        findings.append(
            Finding(
                spec.code,
                spec.severity,
                (
                    f"{object_id} matches policy scope {spec.scope!r} but declares "
                    f"{len(matches)} {spec.assert_relation} relation(s){role_text}; "
                    f"at least {spec.minimum} required"
                ),
                object_id,
                location,
                {
                    "policy": spec.name,
                    "scope": spec.scope,
                    "relation": spec.assert_relation,
                    "targetRole": spec.target_role,
                    "actual": len(matches),
                    "minimum": spec.minimum,
                },
            )
        )
    return tuple(findings)


def evaluate_policies(
    policies: Mapping[str, PolicySpec],
    snapshot: AnalysisSnapshot,
    config: object,
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for name in sorted(policies, key=lambda value: (value.casefold(), value)):
        findings.extend(evaluate_policy(policies[name], snapshot, config))
    return tuple(findings)
