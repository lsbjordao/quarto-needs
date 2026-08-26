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
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib


CONFIG_FILENAME = ".quarto-needs.toml"

KNOWN_TOP_LEVEL_KEYS = (
    "profile",
    "types",
    "relations",
    "governance",
    "rules",
    "queries",
    "gates",
)

PROFILES = ("advisory", "default", "strict")

SEVERITIES = ("error", "warning", "info")

KNOWN_RULE_CODES = (
    "REQ002",
    "REQ004",
    "REQ005",
    "REQ006",
    "REQ008",
    "REQ009",
    "REQ010",
    "REQ011",
    "REQ012",
    "REQ013",
    "REQ014",
    "REQ015",
)

GATE_PERCENT_KEYS = {
    "min-implementation-trace": "min_implementation_trace",
    "min-implementation-effective": "min_implementation_effective",
    "min-verification-trace": "min_verification_trace",
    "min-verification-successful": "min_verification_successful",
    "min-evidence": "min_evidence",
}


class ConfigurationError(ValueError):
    """Raised when `.quarto-needs.toml` is missing a required value or carries an invalid one."""


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
    present: bool = False


def reference_date() -> date:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw is not None:
        try:
            return datetime.fromtimestamp(int(raw), tz=timezone.utc).date()
        except (ValueError, OverflowError, OSError):
            return date.today()
    return date.today()


def parse_iso_date(raw: str) -> date | None:
    """Parse an ISO-8601 date or datetime; None when unparseable."""
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


def _parse_types(raw: object) -> dict[str, tuple[str, ...]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise _fail("[types] must be a table")
    result: dict[str, tuple[str, ...]] = {}
    for name, section in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise _fail("[types.*] keys must be non-empty strings")
        if not isinstance(section, dict):
            raise _fail(f"[types.{name}] must be a table")
        unknown = set(section) - {"required-attributes"}
        if unknown:
            raise _fail(
                f"[types.{name}] has unknown keys: {', '.join(sorted(unknown))}"
            )
        required = _string_list(
            section.get("required-attributes", []),
            f"[types.{name}] required-attributes",
        )
        result[name] = tuple(required)
    return result


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
        unknown = set(section) - {
            "allowed-source-types",
            "allowed-target-types",
            "minimum-per-source",
            "maximum-per-source",
        }
        if unknown:
            raise _fail(
                f'[relations."{name}"] has unknown keys: {", ".join(sorted(unknown))}'
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
        policies[name] = RelationPolicy(
            allowed_source_types=tuple(
                _string_list(
                    section.get("allowed-source-types", []),
                    f'[relations."{name}"] allowed-source-types',
                )
            ),
            allowed_target_types=tuple(
                _string_list(
                    section.get("allowed-target-types", []),
                    f'[relations."{name}"] allowed-target-types',
                )
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
            raw["successful-test-statuses"],
            "[governance] successful-test-statuses",
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
    for code, section in raw.items():
        if not isinstance(code, str) or code not in KNOWN_RULE_CODES:
            raise _fail(
                f"[rules.{code}] is not a known rule code "
                f"(known: {', '.join(KNOWN_RULE_CODES)})"
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
        if severity is not None:
            if not isinstance(severity, str) or severity not in SEVERITIES:
                raise _fail(
                    f"[rules.{code}] severity must be one of: {', '.join(SEVERITIES)}"
                )
        settings[code] = RuleSetting(enabled=enabled, severity=severity)

    # Fail fast against the rule registry so invalid overrides surface at load
    # time instead of mid-analysis. Local import avoids the module cycle.
    from .rules import RULES

    for code, setting in settings.items():
        spec = RULES[code]
        if spec.structural and not setting.enabled:
            raise _fail(f"rule {code} is structural and cannot be disabled")
        if spec.structural and setting.severity is not None:
            raise _fail(f"rule {code} is structural; its severity cannot be overridden")
        if setting.severity is not None and setting.severity not in spec.supported_severities:
            raise _fail(
                f"rule {code} does not support severity {setting.severity} "
                f"(supported: {', '.join(spec.supported_severities)})"
            )
    return settings


def _parse_gates(raw: object) -> Gates:
    if raw is None:
        return Gates()
    if not isinstance(raw, dict):
        raise _fail("[gates] must be a table")
    unknown = set(raw) - set(GATE_PERCENT_KEYS) - {
        "max-errors",
        "require-risk-mitigation",
        "scope",
    }
    if unknown:
        raise _fail(f"[gates] has unknown keys: {', '.join(sorted(unknown))}")
    values: dict[str, object] = {}
    values["max_errors"] = _optional_int(
        raw.get("max-errors", 0), "[gates] max-errors"
    )
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


def embedded_defaults() -> NeedsConfig:
    """Configuration reproducing pre-M2 behavior exactly."""
    return NeedsConfig(
        profile="default",
        required_attributes=MappingProxyType({}),
        relation_policies=MappingProxyType({}),
        test_types=("test-case",),
        risk_types=("risk",),
        ineffective_endpoint_statuses=(
            "disapproved",
            "rejected",
            "failed",
            "deprecated",
        ),
        successful_test_statuses=("passed",),
        expiry_attribute="expires",
        rule_settings=MappingProxyType({}),
        named_query_sources=MappingProxyType({}),
        gates=Gates(),
        present=False,
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
            f"{CONFIG_FILENAME} has unknown top-level keys: "
            f"{', '.join(sorted(unknown))} (known: {', '.join(KNOWN_TOP_LEVEL_KEYS)})"
        )

    profile = document.get("profile", "default")
    if not isinstance(profile, str) or profile not in PROFILES:
        raise _fail(f'profile must be one of: {", ".join(PROFILES)}')

    governance = _parse_governance(document.get("governance"))
    gates = _parse_gates(document.get("gates"))

    queries = document.get("queries")
    if queries is not None and not isinstance(queries, dict):
        raise _fail("[queries] must be a table of named queries")

    return NeedsConfig(
        profile=profile,
        required_attributes=MappingProxyType(_parse_types(document.get("types"))),
        relation_policies=MappingProxyType(_parse_relations(document.get("relations"))),
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
        present=True,
    )
