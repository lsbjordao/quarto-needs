from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import freeze_json, thaw_json

CONFIG_FILENAME = ".quarto-needs.toml"
KNOWN_TOP_LEVEL_KEYS = (
    "profile",
    "types",
    "relations",
    "governance",
    "rules",
    "queries",
    "policies",
    "constraints",
    "derived",
    "variants",
    "gates",
    "graph",
    "federation",
)
PROFILES = ("advisory", "default", "strict")
SEVERITIES = ("error", "warning", "info")
GRAPH_MODES = ("catalog", "diff", "impact")
MAX_GRAPH_DEPTH = 10
GATE_PERCENT_KEYS = {
    "min-implementation-trace": "min_implementation_trace",
    "min-implementation-effective": "min_implementation_effective",
    "min-verification-trace": "min_verification_trace",
    "min-verification-successful": "min_verification_successful",
    "min-evidence": "min_evidence",
}


class ConfigurationError(ValueError):
    """Raised when `.quarto-needs.toml` carries an invalid value."""


@dataclass(frozen=True, slots=True)
class RelationPolicy:
    allowed_source_types: tuple[str, ...] = ()
    allowed_target_types: tuple[str, ...] = ()
    minimum_per_source: int | None = None
    maximum_per_source: int | None = None


@dataclass(frozen=True, slots=True)
class RuleSetting:
    enabled: bool = True
    severity: str | None = None


@dataclass(frozen=True, slots=True)
class Gates:
    max_errors: int = 0
    min_implementation_trace: float | None = None
    min_implementation_effective: float | None = None
    min_verification_trace: float | None = None
    min_verification_successful: float | None = None
    min_evidence: float | None = None
    require_risk_mitigation: bool = False
    scope: str = "approved-requirements"


@dataclass(frozen=True, slots=True)
class GraphSettings:
    max_nodes: int = 100
    max_edges: int = 300
    depth: int = 1
    mode: str = "catalog"
    layout: str = "hierarchical"
    seed: int = 1
    relations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NeedsConfig:
    profile: str
    required_attributes: Mapping[str, tuple[str, ...]]
    relation_policies: Mapping[str, RelationPolicy]
    test_types: tuple[str, ...]
    risk_types: tuple[str, ...]
    ineffective_endpoint_statuses: tuple[str, ...]
    successful_test_statuses: tuple[str, ...]
    expiry_attribute: str
    rule_settings: Mapping[str, RuleSetting]
    named_query_sources: Mapping[str, Mapping[str, Any]]
    gates: Gates
    graph: GraphSettings = GraphSettings()
    present: bool = False
    id_prefixes: Mapping[str, str] = MappingProxyType({})
    type_roles: Mapping[str, str] = MappingProxyType({})
    allowed_statuses: Mapping[str, tuple[str, ...]] = MappingProxyType({})
    policy_sources: Mapping[str, Mapping[str, Any]] = MappingProxyType({})
    attribute_schemas: Mapping[str, Mapping[str, Any]] = MappingProxyType({})
    constraint_sources: Mapping[str, Mapping[str, Any]] = MappingProxyType({})
    derived_sources: Mapping[str, Mapping[str, Any]] = MappingProxyType({})
    variant_sources: Mapping[str, Mapping[str, Any]] = MappingProxyType({})

    def canonical_document(self) -> dict[str, object]:
        try:
            queries = {
                name: thaw_json(freeze_json(dict(source)))
                for name, source in sorted(self.named_query_sources.items())
            }
            policies = {
                name: thaw_json(freeze_json(dict(source)))
                for name, source in sorted(self.policy_sources.items())
            }
            schemas = {
                name: thaw_json(freeze_json(dict(source)))
                for name, source in sorted(self.attribute_schemas.items())
            }
            constraints = {
                name: thaw_json(freeze_json(dict(source)))
                for name, source in sorted(self.constraint_sources.items())
            }
            derived = {
                name: thaw_json(freeze_json(dict(source)))
                for name, source in sorted(self.derived_sources.items())
            }
            variants = {
                name: thaw_json(freeze_json(dict(source)))
                for name, source in sorted(self.variant_sources.items())
            }
        except TypeError as error:
            raise _fail(
                "[queries]/[policies]/[constraints]/[derived]/[variants]/attribute-schema "
                f"contains a value that is not valid JSON: {error}"
            ) from error

        type_names = sorted(
            set(self.required_attributes)
            | set(self.id_prefixes)
            | set(self.type_roles)
            | set(self.allowed_statuses)
            | set(self.attribute_schemas)
        )
        types: dict[str, object] = {}
        for name in type_names:
            entry: dict[str, object] = {
                "required-attributes": list(self.required_attributes.get(name, ()))
            }
            if name in self.id_prefixes:
                entry["id-prefix"] = self.id_prefixes[name]
            if name in self.type_roles:
                entry["role"] = self.type_roles[name]
            if name in self.allowed_statuses:
                entry["allowed-statuses"] = list(self.allowed_statuses[name])
            if name in schemas:
                entry["attribute-schema"] = schemas[name]
            types[name] = entry

        return {
            "profile": self.profile,
            "types": types,
            "relations": {
                name: {
                    "allowed-source-types": list(policy.allowed_source_types),
                    "allowed-target-types": list(policy.allowed_target_types),
                    "minimum-per-source": policy.minimum_per_source,
                    "maximum-per-source": policy.maximum_per_source,
                }
                for name, policy in sorted(self.relation_policies.items())
            },
            "governance": {
                "test-types": list(self.test_types),
                "risk-types": list(self.risk_types),
                "successful-test-statuses": list(self.successful_test_statuses),
                "ineffective-endpoint-statuses": list(self.ineffective_endpoint_statuses),
                "expiry-attribute": self.expiry_attribute,
            },
            "rules": {
                code: {"enabled": setting.enabled, "severity": setting.severity}
                for code, setting in sorted(self.rule_settings.items())
            },
            "queries": queries,
            "policies": policies,
            "constraints": constraints,
            "derived": derived,
            "variants": variants,
            "gates": {
                "scope": self.gates.scope,
                "max-errors": self.gates.max_errors,
                "require-risk-mitigation": self.gates.require_risk_mitigation,
                "min-implementation-trace": self.gates.min_implementation_trace,
                "min-implementation-effective": self.gates.min_implementation_effective,
                "min-verification-trace": self.gates.min_verification_trace,
                "min-verification-successful": self.gates.min_verification_successful,
                "min-evidence": self.gates.min_evidence,
            },
        }


def reference_date() -> date:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw is not None:
        try:
            return datetime.fromtimestamp(int(raw), tz=timezone.utc).date()
        except (ValueError, OverflowError, OSError):
            return date.today()
    return date.today()


def parse_iso_date(raw: str) -> date | None:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return date.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return None


def _fail(message: str) -> ConfigurationError:
    return ConfigurationError(message)


def _string_list(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise _fail(f"{context} must be an array of strings")
    return tuple(value)


def _optional_int(value: object, context: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(f"{context} must be an integer")
    if value < 0:
        raise _fail(f"{context} must not be negative")
    return value


def _optional_percent(value: object, context: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"{context} must be a number between 0 and 100")
    number = float(value)
    if number < 0.0 or number > 100.0:
        raise _fail(f"{context} must be a number between 0 and 100")
    return number


def _parse_types(raw: object) -> tuple[
    dict[str, tuple[str, ...]],
    dict[str, str],
    dict[str, str],
    dict[str, tuple[str, ...]],
    dict[str, Mapping[str, Any]],
]:
    if raw is None:
        return {}, {}, {}, {}, {}
    if not isinstance(raw, dict):
        raise _fail("[types] must be a table")
    required: dict[str, tuple[str, ...]] = {}
    prefixes: dict[str, str] = {}
    roles: dict[str, str] = {}
    statuses: dict[str, tuple[str, ...]] = {}
    schemas: dict[str, Mapping[str, Any]] = {}
    for name, section in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise _fail("[types.*] keys must be non-empty strings")
        if not isinstance(section, dict):
            raise _fail(f"[types.{name}] must be a table")
        unknown = set(section) - {
            "required-attributes",
            "id-prefix",
            "role",
            "allowed-statuses",
            "attribute-schema",
        }
        if unknown:
            raise _fail(
                f"[types.{name}] has unknown keys: {', '.join(sorted(unknown))}"
            )
        required[name] = _string_list(
            section.get("required-attributes", []),
            f"[types.{name}] required-attributes",
        )
        if "id-prefix" in section:
            prefix = section["id-prefix"]
            if not isinstance(prefix, str) or not prefix:
                raise _fail(f"[types.{name}] id-prefix must be a non-empty string")
            prefixes[name] = prefix
        if "role" in section:
            role = section["role"]
            if not isinstance(role, str) or not role.strip():
                raise _fail(f"[types.{name}] role must be a non-empty string")
            roles[name] = role.strip()
        if "allowed-statuses" in section:
            values = _string_list(
                section["allowed-statuses"], f"[types.{name}] allowed-statuses"
            )
            if not values:
                raise _fail(f"[types.{name}] allowed-statuses must not be empty")
            statuses[name] = values
        if "attribute-schema" in section:
            schema_raw = section["attribute-schema"]
            if not isinstance(schema_raw, dict):
                raise _fail(f"[types.{name}] attribute-schema must be a table")
            from .type_schema import TypeSchemaError, compile_type_schema

            try:
                spec = compile_type_schema(name, schema_raw)
            except TypeSchemaError as error:
                raise _fail(str(error)) from error
            schemas[name] = MappingProxyType(dict(spec.to_dict()))
    return required, prefixes, roles, statuses, schemas


def _parse_relations(raw: object) -> dict[str, RelationPolicy]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail("[relations] must be a table")
    policies: dict[str, RelationPolicy] = {}
    for name, section in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise _fail('[relations."*"] keys must be non-empty strings')
        if not isinstance(section, dict):
            raise _fail(f'[relations."{name}"] must be a table')
        try:
            canonical_name = DEFAULT_RELATION_CATALOG.resolve(name).v1_name
        except ValueError as error:
            raise _fail(str(error)) from error
        unknown = set(section) - {
            "allowed-source-types",
            "allowed-target-types",
            "minimum-per-source",
            "maximum-per-source",
        }
        if unknown:
            raise _fail(
                f'[relations."{name}"] has unknown keys: '
                f"{', '.join(sorted(unknown))}"
            )
        minimum = _optional_int(
            section.get("minimum-per-source"),
            f'[relations."{name}"] minimum-per-source',
        )
        maximum = _optional_int(
            section.get("maximum-per-source"),
            f'[relations."{name}"] maximum-per-source',
        )
        if minimum is not None and maximum is not None and minimum > maximum:
            raise _fail(
                f'[relations."{name}"] minimum-per-source exceeds maximum-per-source'
            )
        policies[canonical_name] = RelationPolicy(
            allowed_source_types=_string_list(
                section.get("allowed-source-types", []),
                f'[relations."{name}"] allowed-source-types',
            ),
            allowed_target_types=_string_list(
                section.get("allowed-target-types", []),
                f'[relations."{name}"] allowed-target-types',
            ),
            minimum_per_source=minimum,
            maximum_per_source=maximum,
        )
    return policies


def _parse_governance(raw: object) -> dict[str, object]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail("[governance] must be a table")
    unknown = set(raw) - {
        "test-types",
        "risk-types",
        "successful-test-statuses",
        "ineffective-endpoint-statuses",
        "expiry-attribute",
    }
    if unknown:
        raise _fail(f"[governance] has unknown keys: {', '.join(sorted(unknown))}")
    parsed: dict[str, object] = {}
    if "test-types" in raw:
        parsed["test_types"] = _string_list(raw["test-types"], "[governance] test-types")
    if "risk-types" in raw:
        parsed["risk_types"] = _string_list(raw["risk-types"], "[governance] risk-types")
    if "successful-test-statuses" in raw:
        parsed["successful_test_statuses"] = _string_list(
            raw["successful-test-statuses"], "[governance] successful-test-statuses"
        )
    if "ineffective-endpoint-statuses" in raw:
        parsed["ineffective_endpoint_statuses"] = _string_list(
            raw["ineffective-endpoint-statuses"],
            "[governance] ineffective-endpoint-statuses",
        )
    if "expiry-attribute" in raw:
        value = raw["expiry-attribute"]
        if not isinstance(value, str):
            raise _fail("[governance] expiry-attribute must be a string")
        parsed["expiry_attribute"] = value
    return parsed


def _parse_rules(raw: object) -> dict[str, RuleSetting]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail("[rules] must be a table")
    settings: dict[str, RuleSetting] = {}
    from .rules import RULES

    for code, section in raw.items():
        if not isinstance(code, str) or code not in RULES:
            raise _fail(
                f"[rules.{code}] is not a known rule code "
                f"(known: {', '.join(sorted(RULES))})"
            )
        if not isinstance(section, dict):
            raise _fail(f"[rules.{code}] must be a table")
        unknown = set(section) - {"enabled", "severity"}
        if unknown:
            raise _fail(
                f"[rules.{code}] has unknown keys: {', '.join(sorted(unknown))}"
            )
        enabled = section.get("enabled", True)
        if not isinstance(enabled, bool):
            raise _fail(f"[rules.{code}] enabled must be a boolean")
        severity = section.get("severity")
        if severity is not None and (
            not isinstance(severity, str) or severity not in SEVERITIES
        ):
            raise _fail(
                f"[rules.{code}] severity must be one of: {', '.join(SEVERITIES)}"
            )
        setting = RuleSetting(enabled=enabled, severity=severity)
        spec = RULES[code]
        if spec.structural and not setting.enabled:
            raise _fail(f"rule {code} is structural and cannot be disabled")
        if spec.structural and setting.severity is not None:
            raise _fail(
                f"rule {code} is structural; its severity cannot be overridden"
            )
        if (
            setting.severity is not None
            and setting.severity not in spec.supported_severities
        ):
            raise _fail(
                f"rule {code} does not support severity {setting.severity} "
                f"(supported: {', '.join(spec.supported_severities)})"
            )
        settings[code] = setting
    return settings


def _parse_gates(raw: object) -> Gates:
    if raw is None:
        return Gates()
    if not isinstance(raw, dict):
        raise _fail("[gates] must be a table")
    unknown = set(raw) - set(GATE_PERCENT_KEYS) - {
        "max-errors", "require-risk-mitigation", "scope"
    }
    if unknown:
        raise _fail(f"[gates] has unknown keys: {', '.join(sorted(unknown))}")
    values: dict[str, object] = {
        "max_errors": _optional_int(raw.get("max-errors", 0), "[gates] max-errors")
    }
    mitigation = raw.get("require-risk-mitigation", False)
    if not isinstance(mitigation, bool):
        raise _fail("[gates] require-risk-mitigation must be a boolean")
    values["require_risk_mitigation"] = mitigation
    scope = raw.get("scope", "approved-requirements")
    if not isinstance(scope, str) or not scope.strip():
        raise _fail("[gates] scope must be a non-empty string")
    values["scope"] = scope
    for key, attribute in GATE_PERCENT_KEYS.items():
        values[attribute] = _optional_percent(raw.get(key), f"[gates] {key}")
    return Gates(**values)


def _parse_graph(raw: object) -> GraphSettings:
    if raw is None:
        return GraphSettings()
    if not isinstance(raw, dict):
        raise _fail("[graph] must be a table")
    unknown = set(raw) - {
        "max-nodes", "max-edges", "depth", "mode", "layout", "seed", "relations"
    }
    if unknown:
        raise _fail(f"[graph] has unknown keys: {', '.join(sorted(unknown))}")

    def positive_int(key: str, default: int) -> int:
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise _fail(f"[graph] {key} must be an integer of at least 1")
        return value

    depth = raw.get("depth", 1)
    if (
        isinstance(depth, bool)
        or not isinstance(depth, int)
        or not 1 <= depth <= MAX_GRAPH_DEPTH
    ):
        raise _fail(
            f"[graph] depth must be an integer between 1 and {MAX_GRAPH_DEPTH}"
        )
    mode = raw.get("mode", "catalog")
    if not isinstance(mode, str) or mode not in GRAPH_MODES:
        raise _fail(f"[graph] mode must be one of: {', '.join(GRAPH_MODES)}")
    layout = raw.get("layout", "hierarchical")
    if not isinstance(layout, str) or not layout.strip():
        raise _fail("[graph] layout must be a non-empty string")
    seed = raw.get("seed", 1)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise _fail("[graph] seed must be a non-negative integer")

    relations_raw = raw.get("relations")
    if relations_raw is not None:
        names = _string_list(relations_raw, "[graph] relations")
        if not names:
            raise _fail(
                "[graph] relations must not be empty; omit the key to publish every relation"
            )
        resolved = []
        for name in names:
            try:
                resolved.append(DEFAULT_RELATION_CATALOG.resolve(name).v1_name)
            except ValueError as error:
                raise _fail(f"[graph] relations: {error}") from error
        relations = tuple(sorted(set(resolved)))
    else:
        relations = ()
    return GraphSettings(
        max_nodes=positive_int("max-nodes", 100),
        max_edges=positive_int("max-edges", 300),
        depth=depth,
        mode=mode,
        layout=layout,
        seed=seed,
        relations=relations,
    )


def _parse_policies(raw: object) -> dict[str, Mapping[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail("[policies] must be a table")
    from .policy import PolicyError, compile_policies

    try:
        compiled = compile_policies(raw)
    except PolicyError as error:
        raise _fail(str(error)) from error
    return {
        name: MappingProxyType(dict(spec.to_dict()))
        for name, spec in compiled.items()
    }


def _parse_constraints(raw: object) -> dict[str, Mapping[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail("[constraints] must be a table")
    from .graph_constraints import GraphConstraintError, compile_graph_constraints

    try:
        compiled = compile_graph_constraints(raw)
    except GraphConstraintError as error:
        raise _fail(str(error)) from error
    normalized: dict[str, Mapping[str, Any]] = {}
    for name, spec in compiled.items():
        payload = dict(spec.to_dict())
        if spec.kind == "connected" and not spec.relations:
            payload.pop("relations", None)
        normalized[name] = MappingProxyType(payload)
    return normalized


def _parse_derived(raw: object) -> dict[str, Mapping[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail("[derived] must be a table")
    from .derived import DerivedError, compile_derived_fields

    try:
        compiled = compile_derived_fields(raw)
    except DerivedError as error:
        raise _fail(str(error)) from error
    normalized: dict[str, Mapping[str, Any]] = {}
    for name, spec in compiled.items():
        payload = dict(spec.to_dict())
        if spec.operation == "relation-count":
            payload["relation"] = spec.relations[0]
            payload.pop("relations", None)
        normalized[name] = MappingProxyType(payload)
    return normalized


def _parse_variants(raw: object) -> dict[str, Mapping[str, Any]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail("[variants] must be a table")
    from .derived import DerivedError, compile_variants

    try:
        compiled = compile_variants(raw)
    except DerivedError as error:
        raise _fail(str(error)) from error
    return {
        name: MappingProxyType(dict(spec.to_dict()))
        for name, spec in compiled.items()
    }


def embedded_defaults() -> NeedsConfig:
    return NeedsConfig(
        profile="default",
        required_attributes=MappingProxyType({}),
        relation_policies=MappingProxyType({}),
        test_types=("test-case",),
        risk_types=("risk",),
        ineffective_endpoint_statuses=(
            "disapproved", "rejected", "failed", "deprecated"
        ),
        successful_test_statuses=("passed",),
        expiry_attribute="expires",
        rule_settings=MappingProxyType({}),
        named_query_sources=MappingProxyType({}),
        gates=Gates(),
        graph=GraphSettings(),
        present=False,
        id_prefixes=MappingProxyType({}),
        type_roles=MappingProxyType({}),
        allowed_statuses=MappingProxyType({}),
        policy_sources=MappingProxyType({}),
        attribute_schemas=MappingProxyType({}),
        constraint_sources=MappingProxyType({}),
        derived_sources=MappingProxyType({}),
        variant_sources=MappingProxyType({}),
    )


def load_config(root: Path) -> NeedsConfig:
    path = Path(root) / CONFIG_FILENAME
    if not path.is_file():
        return embedded_defaults()
    try:
        with path.open("rb") as stream:
            document = tomllib.load(stream)
    except tomllib.TOMLDecodeError as error:
        raise _fail(f"{CONFIG_FILENAME} is not valid TOML: {error}") from error

    unknown = set(document) - set(KNOWN_TOP_LEVEL_KEYS)
    if unknown:
        raise _fail(
            f"{CONFIG_FILENAME} has unknown top-level keys: {', '.join(sorted(unknown))} "
            f"(known: {', '.join(KNOWN_TOP_LEVEL_KEYS)})"
        )
    profile = document.get("profile", "default")
    if not isinstance(profile, str) or profile not in PROFILES:
        raise _fail(f"profile must be one of: {', '.join(PROFILES)}")

    # Federation is operational/read-only configuration, so validate it here
    # without adding it to NeedsConfig.canonical_document(). This makes every
    # ordinary command reject malformed OSLC profiles while endpoint/cache
    # changes remain outside the canonical engineering fingerprint.
    from .oslc_profiles import OslcProfileError, parse_oslc_profiles

    try:
        parse_oslc_profiles(document.get("federation"))
    except OslcProfileError as error:
        raise _fail(str(error)) from error

    governance = _parse_governance(document.get("governance"))
    gates = _parse_gates(document.get("gates"))
    queries = document.get("queries")
    if queries is not None and not isinstance(queries, dict):
        raise _fail("[queries] must be a table of named queries")
    required, prefixes, roles, statuses, schemas = _parse_types(document.get("types"))
    policies = _parse_policies(document.get("policies"))
    constraints = _parse_constraints(document.get("constraints"))
    derived = _parse_derived(document.get("derived"))
    variants = _parse_variants(document.get("variants"))

    return NeedsConfig(
        profile=profile,
        required_attributes=MappingProxyType(required),
        relation_policies=MappingProxyType(
            _parse_relations(document.get("relations"))
        ),
        test_types=governance.get("test_types", ("test-case",)),
        risk_types=governance.get("risk_types", ("risk",)),
        ineffective_endpoint_statuses=governance.get(
            "ineffective_endpoint_statuses",
            ("disapproved", "rejected", "failed", "deprecated"),
        ),
        successful_test_statuses=governance.get(
            "successful_test_statuses", ("passed",)
        ),
        expiry_attribute=governance.get("expiry_attribute", "expires"),
        rule_settings=MappingProxyType(_parse_rules(document.get("rules"))),
        named_query_sources=MappingProxyType(dict(queries or {})),
        gates=gates,
        graph=_parse_graph(document.get("graph")),
        present=True,
        id_prefixes=MappingProxyType(prefixes),
        type_roles=MappingProxyType(roles),
        allowed_statuses=MappingProxyType(statuses),
        policy_sources=MappingProxyType(policies),
        attribute_schemas=MappingProxyType(schemas),
        constraint_sources=MappingProxyType(constraints),
        derived_sources=MappingProxyType(derived),
        variant_sources=MappingProxyType(variants),
    )
