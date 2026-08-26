from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Callable, Iterable, Mapping

from .config import ConfigurationError, NeedsConfig, parse_iso_date, reference_date
from .diagnostics import Finding
from .snapshot import AnalysisSnapshot, ObjectRecord


@dataclass(frozen=True, slots=True)
class RuleSpec:
    code: str
    title: str
    help: str
    default_severity: str
    supported_severities: tuple[str, ...] = ("error", "warning", "info")
    structural: bool = False
    evaluator: Evaluator | None = None
    # Declaring the corresponding policy section implies wanting the check;
    # None means the rule needs an explicit [rules.<CODE>] entry.
    auto_activates: Callable[[NeedsConfig], bool] | None = None


@dataclass(frozen=True, slots=True)
class RuleContext:
    snapshot: AnalysisSnapshot
    config: NeedsConfig


Evaluator = Callable[[RuleContext], Iterable[Finding]]


STRUCTURAL_CODES = frozenset({"REQ004", "REQ005"})

LEGACY_CODES = frozenset({"REQ002", "REQ004", "REQ005", "REQ006"})


def _requirement_objects(ctx: RuleContext) -> list[ObjectRecord]:
    return [item for item in ctx.snapshot.objects if item.type.endswith("requirement")]


def _existing(ctx: RuleContext, object_id: str) -> bool:
    return object_id in ctx.snapshot.objects_by_id


# --- governance rule evaluators ----------------------------------------------


def _evaluate_required_attributes(ctx: RuleContext) -> Iterable[Finding]:
    for record in ctx.snapshot.objects:
        required = ctx.config.required_attributes.get(record.type)
        if not required:
            continue
        for attribute in required:
            value = record.attributes.get(attribute)
            empty = (
                value is None
                or (isinstance(value, str) and not value.strip())
                or (isinstance(value, (tuple, list)) and not value)
            )
            if empty:
                yield Finding(
                    "REQ008",
                    RULES["REQ008"].default_severity,
                    f"{record.id} is missing required attribute {attribute}",
                    record.id,
                    record.locations[0] if record.locations else None,
                    {"attribute": attribute},
                )


def _evaluate_relation_endpoints(ctx: RuleContext) -> Iterable[Finding]:
    for relation in ctx.snapshot.relations:
        policy = ctx.config.relation_policies.get(relation.v1_name)
        if policy is None:
            continue
        source = ctx.snapshot.objects_by_id.get(relation.source)
        target = ctx.snapshot.objects_by_id.get(relation.target)
        if (
            source is not None
            and policy.allowed_source_types
            and source.type not in policy.allowed_source_types
        ):
            yield Finding(
                "REQ009",
                RULES["REQ009"].default_severity,
                f"{relation.source} may not be the source of {relation.v1_name} "
                f"(allowed: {', '.join(policy.allowed_source_types)})",
                relation.source,
                relation.provenance[0] if relation.provenance else None,
                {"side": "source", "expected": policy.allowed_source_types},
            )
        if (
            target is not None
            and policy.allowed_target_types
            and target.type not in policy.allowed_target_types
        ):
            yield Finding(
                "REQ009",
                RULES["REQ009"].default_severity,
                f"{relation.target} may not be the target of {relation.v1_name} "
                f"(allowed: {', '.join(policy.allowed_target_types)})",
                relation.target,
                relation.provenance[0] if relation.provenance else None,
                {"side": "target", "expected": policy.allowed_target_types},
            )


def _evaluate_cardinality(ctx: RuleContext) -> Iterable[Finding]:
    counts: dict[tuple[str, str], int] = {}
    for relation in ctx.snapshot.relations:
        key = (relation.source, relation.v1_name)
        counts[key] = counts.get(key, 0) + 1
    for (source_id, v1_name), count in sorted(counts.items()):
        policy = ctx.config.relation_policies.get(v1_name)
        if policy is None:
            continue
        location_record = next(
            (
                item.locations[0]
                for item in ctx.snapshot.objects
                if item.id == source_id and item.locations
            ),
            None,
        )
        if policy.minimum_per_source is not None and count < policy.minimum_per_source:
            yield Finding(
                "REQ010",
                RULES["REQ010"].default_severity,
                f"{source_id} declares {count} {v1_name} relation(s); "
                f"at least {policy.minimum_per_source} required",
                source_id,
                location_record,
                {"actual": count, "minimum": policy.minimum_per_source},
            )
        if policy.maximum_per_source is not None and count > policy.maximum_per_source:
            yield Finding(
                "REQ010",
                RULES["REQ010"].default_severity,
                f"{source_id} declares {count} {v1_name} relation(s); "
                f"at most {policy.maximum_per_source} allowed",
                source_id,
                location_record,
                {"actual": count, "maximum": policy.maximum_per_source},
            )


def _evaluate_approved_implementation(ctx: RuleContext) -> Iterable[Finding]:
    for record in _requirement_objects(ctx):
        if record.status != "approved":
            continue
        implemented = any(
            item.semantic_family == "implementation" and _existing(ctx, item.target)
            for item in ctx.snapshot.outgoing.get(record.id, ())
        )
        if not implemented:
            yield Finding(
                "REQ011",
                RULES["REQ011"].default_severity,
                f"{record.id} is approved but has no implementation relation",
                record.id,
                record.locations[0] if record.locations else None,
            )


def _evaluate_test_evidence(ctx: RuleContext) -> Iterable[Finding]:
    accepted_statuses = {"approved", *ctx.config.successful_test_statuses}
    for record in ctx.snapshot.objects:
        if record.type not in ctx.config.test_types:
            continue
        if record.status.casefold() not in accepted_statuses:
            continue
        evidenced = any(
            item.semantic_family == "evidence" and _existing(ctx, item.target)
            for item in ctx.snapshot.outgoing.get(record.id, ())
        )
        if not evidenced:
            yield Finding(
                "REQ012",
                RULES["REQ012"].default_severity,
                f"{record.id} is {record.status} but has no evidence relation",
                record.id,
                record.locations[0] if record.locations else None,
            )


def _evaluate_risk_mitigation(ctx: RuleContext) -> Iterable[Finding]:
    high_priorities = {"high", "critical"}
    for record in ctx.snapshot.objects:
        if record.type not in ctx.config.risk_types:
            continue
        priority = record.attributes.get("priority")
        if priority is None or str(priority).casefold() not in high_priorities:
            continue
        mitigated = any(
            item.semantic_family == "mitigation"
            for item in ctx.snapshot.incoming.get(record.id, ())
        )
        if not mitigated:
            yield Finding(
                "REQ013",
                RULES["REQ013"].default_severity,
                f"{record.id} is a high-priority risk without mitigation",
                record.id,
                record.locations[0] if record.locations else None,
            )


def _evaluate_orphans(ctx: RuleContext) -> Iterable[Finding]:
    for record in ctx.snapshot.objects:
        outgoing = ctx.snapshot.outgoing.get(record.id, ())
        incoming = ctx.snapshot.incoming.get(record.id, ())
        if not outgoing and not incoming:
            yield Finding(
                "REQ014",
                RULES["REQ014"].default_severity,
                f"{record.id} has no relations in either direction",
                record.id,
                record.locations[0] if record.locations else None,
            )


def _evaluate_expired_evidence(ctx: RuleContext) -> Iterable[Finding]:
    """Check every object carrying the configured expiry attribute.

    The rule is attribute-scoped rather than relation-scoped so an evidence
    object whose edge was removed still reports why it is unusable.
    """
    attribute = ctx.config.expiry_attribute
    if not attribute:
        return
    today = reference_date()
    for endpoint in ctx.snapshot.objects:
        raw = endpoint.attributes.get(attribute)
        if raw is None or str(raw).strip() == "":
            continue
        parsed = parse_iso_date(str(raw))
        properties = {"attribute": attribute, "referenceDate": today.isoformat()}
        if parsed is None:
            yield Finding(
                "REQ015",
                RULES["REQ015"].default_severity,
                f"{endpoint.id} has an unparseable {attribute} value: {raw}",
                endpoint.id,
                endpoint.locations[0] if endpoint.locations else None,
                {**properties, "reason": "unparseable"},
            )
        elif parsed < today:
            yield Finding(
                "REQ015",
                RULES["REQ015"].default_severity,
                f"{endpoint.id} evidence expired on {parsed.isoformat()}",
                endpoint.id,
                endpoint.locations[0] if endpoint.locations else None,
                {**properties, "reason": "expired"},
            )


# --- registry -----------------------------------------------------------------


RULES: Mapping[str, RuleSpec]
RULES = {
    spec.code: spec
    for spec in (
        RuleSpec(
            "REQ002",
            "Missing rationale",
            "Requirement declarations should explain why they exist.",
            "warning",
        ),
        RuleSpec(
            "REQ004",
            "Duplicate identifier",
            "Every engineering object needs a unique ID.",
            "error",
            structural=True,
        ),
        RuleSpec(
            "REQ005",
            "Unknown relation target",
            "Relations must point at declared objects.",
            "error",
            structural=True,
        ),
        RuleSpec(
            "REQ006",
            "Approved without verification",
            "Approved requirements need a verification relation.",
            "warning",
            supported_severities=("error", "warning"),
        ),
        RuleSpec(
            "REQ008",
            "Required attribute missing",
            "Configured types may require attributes such as priority.",
            "warning",
            evaluator=_evaluate_required_attributes,
            auto_activates=lambda config: bool(config.required_attributes),
        ),
        RuleSpec(
            "REQ009",
            "Relation endpoint not allowed",
            "Configured relations restrict which types may be endpoints.",
            "warning",
            evaluator=_evaluate_relation_endpoints,
            auto_activates=lambda config: bool(config.relation_policies),
        ),
        RuleSpec(
            "REQ010",
            "Relation cardinality violated",
            "Configured relations may require a minimum/maximum per source.",
            "warning",
            evaluator=_evaluate_cardinality,
            auto_activates=lambda config: bool(config.relation_policies),
        ),
        RuleSpec(
            "REQ011",
            "Approved without implementation",
            "Approved requirements need an implementation-family relation.",
            "warning",
            evaluator=_evaluate_approved_implementation,
        ),
        RuleSpec(
            "REQ012",
            "Test without evidence",
            "Approved or passed tests need evidence-family relations.",
            "warning",
            evaluator=_evaluate_test_evidence,
        ),
        RuleSpec(
            "REQ013",
            "High risk without mitigation",
            "High/critical risks need incoming mitigation relations.",
            "warning",
            evaluator=_evaluate_risk_mitigation,
        ),
        RuleSpec(
            "REQ014",
            "Orphaned object",
            "Objects with no relations in either direction.",
            "info",
            evaluator=_evaluate_orphans,
        ),
        RuleSpec(
            "REQ015",
            "Expired evidence",
            "Evidence carrying an expiry attribute must still be valid.",
            "warning",
            evaluator=_evaluate_expired_evidence,
        ),
    )
}

for _spec in RULES.values():
    if getattr(_spec, "evaluator", None) is None and _spec.code not in LEGACY_CODES:
        raise RuntimeError(f"rule {_spec.code} lacks an evaluator")


def _resolved_severity(spec: RuleSpec, config: NeedsConfig) -> str | None:
    """Return the effective severity, or None when the rule stays inactive.

    Governance rules (REQ008+) are opt-in: they activate only through an
    explicit `[rules.<CODE>]` entry. Legacy rules are always active because
    validation.py emits them; configuration may only disable/remap those.
    """
    setting = config.rule_settings.get(spec.code)
    if setting is None:
        if spec.code in LEGACY_CODES or (
            spec.auto_activates is not None and spec.auto_activates(config)
        ):
            return spec.default_severity
        return None
    if not setting.enabled:
        if spec.structural:
            raise ConfigurationError(
                f"rule {spec.code} is structural and cannot be disabled"
            )
        return None
    if setting.severity is None:
        return spec.default_severity
    if spec.structural:
        raise ConfigurationError(
            f"rule {spec.code} is structural; its severity cannot be overridden"
        )
    if setting.severity not in spec.supported_severities:
        raise ConfigurationError(
            f"rule {spec.code} does not support severity {setting.severity} "
            f"(supported: {', '.join(spec.supported_severities)})"
        )
    return setting.severity


def run_rules(snapshot: AnalysisSnapshot, config: NeedsConfig) -> tuple[Finding, ...]:
    """Evaluate every configured governance rule against the snapshot."""
    context = RuleContext(snapshot=snapshot, config=config)
    findings: list[Finding] = []
    for code in sorted(RULES):
        spec = RULES[code]
        if spec.code in LEGACY_CODES:
            continue  # legacy rules are produced by validation.py, then remapped
        severity = _resolved_severity(spec, config)
        if severity is None:
            continue
        for finding in spec.evaluator(context):
            findings.append(replace(finding, severity=severity))
    return tuple(findings)


def apply_rule_settings(
    findings: Iterable[Finding],
    config: NeedsConfig,
) -> tuple[Finding, ...]:
    """Drop disabled legacy findings and remap severities per configuration."""
    result: list[Finding] = []
    for finding in findings:
        spec = RULES.get(finding.code)
        if spec is None:
            result.append(finding)
            continue
        severity = _resolved_severity(spec, config)
        if severity is None:
            continue
        if severity != finding.severity:
            result.append(replace(finding, severity=severity))
        else:
            result.append(finding)
    return tuple(result)
