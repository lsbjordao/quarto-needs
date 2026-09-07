from __future__ import annotations

from dataclasses import dataclass, replace
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
    auto_activates: Callable[[NeedsConfig], bool] | None = None


@dataclass(frozen=True, slots=True)
class RuleContext:
    snapshot: AnalysisSnapshot
    config: NeedsConfig


Evaluator = Callable[[RuleContext], Iterable[Finding]]
STRUCTURAL_CODES = frozenset({"REQ004", "REQ005"})
LEGACY_CODES = frozenset({"REQ002", "REQ004", "REQ005", "REQ006"})
DECISION_TYPE = "architecture-decision"


def _has_role(ctx: RuleContext, obj: ObjectRecord, role: str) -> bool:
    configured = ctx.config.type_roles.get(obj.type)
    if configured is not None:
        return configured == role
    if role == "requirement":
        return obj.type.endswith("requirement")
    if role == "decision":
        return obj.type == DECISION_TYPE
    return False


def _reqs(ctx: RuleContext) -> list[ObjectRecord]:
    return [obj for obj in ctx.snapshot.objects if _has_role(ctx, obj, "requirement")]


def _decs(ctx: RuleContext) -> list[ObjectRecord]:
    return [obj for obj in ctx.snapshot.objects if _has_role(ctx, obj, "decision")]


def _loc(obj: ObjectRecord):
    return obj.locations[0] if obj.locations else None


def _exists(ctx: RuleContext, object_id: str) -> bool:
    return object_id in ctx.snapshot.objects_by_id


def _family_out(ctx: RuleContext, object_id: str, family: str) -> tuple:
    return tuple(
        edge
        for edge in ctx.snapshot.outgoing.get(object_id, ())
        if edge.semantic_family == family and _exists(ctx, edge.target)
    )


def _family_in(ctx: RuleContext, object_id: str, family: str) -> tuple:
    return tuple(
        edge
        for edge in ctx.snapshot.incoming.get(object_id, ())
        if edge.semantic_family == family and _exists(ctx, edge.source)
    )


def _relation_out(ctx: RuleContext, object_id: str, relation_name: str) -> tuple:
    """Return valid authored relations leaving *object_id* with exact semantic direction."""
    return tuple(
        edge
        for edge in ctx.snapshot.outgoing.get(object_id, ())
        if edge.v1_name == relation_name and _exists(ctx, edge.target)
    )


def _relation_in(ctx: RuleContext, object_id: str, relation_name: str) -> tuple:
    """Return valid authored relations entering *object_id* with exact semantic direction."""
    return tuple(
        edge
        for edge in ctx.snapshot.incoming.get(object_id, ())
        if edge.v1_name == relation_name and _exists(ctx, edge.source)
    )


def _required_attributes(ctx: RuleContext) -> Iterable[Finding]:
    for obj in ctx.snapshot.objects:
        for attr in ctx.config.required_attributes.get(obj.type, ()):
            value = obj.attributes.get(attr)
            if value is None or (isinstance(value, str) and not value.strip()) or (
                isinstance(value, (tuple, list)) and not value
            ):
                yield Finding(
                    "REQ008",
                    RULES["REQ008"].default_severity,
                    f"{obj.id} is missing required attribute {attr}",
                    obj.id,
                    _loc(obj),
                    {"attribute": attr},
                )


def _relation_endpoints(ctx: RuleContext) -> Iterable[Finding]:
    for edge in ctx.snapshot.relations:
        policy = ctx.config.relation_policies.get(edge.v1_name)
        if policy is None:
            continue
        source = ctx.snapshot.objects_by_id.get(edge.source)
        target = ctx.snapshot.objects_by_id.get(edge.target)
        if source is not None and policy.allowed_source_types and source.type not in policy.allowed_source_types:
            yield Finding(
                "REQ009",
                RULES["REQ009"].default_severity,
                f"{edge.source} may not be the source of {edge.v1_name} (allowed: {', '.join(policy.allowed_source_types)})",
                edge.source,
                edge.provenance[0] if edge.provenance else None,
                {"side": "source", "expected": policy.allowed_source_types},
            )
        if target is not None and policy.allowed_target_types and target.type not in policy.allowed_target_types:
            yield Finding(
                "REQ009",
                RULES["REQ009"].default_severity,
                f"{edge.target} may not be the target of {edge.v1_name} (allowed: {', '.join(policy.allowed_target_types)})",
                edge.target,
                edge.provenance[0] if edge.provenance else None,
                {"side": "target", "expected": policy.allowed_target_types},
            )


def _cardinality(ctx: RuleContext) -> Iterable[Finding]:
    counts: dict[tuple[str, str], int] = {}
    for edge in ctx.snapshot.relations:
        counts[(edge.source, edge.v1_name)] = counts.get((edge.source, edge.v1_name), 0) + 1
    for (source, name), count in sorted(counts.items()):
        policy = ctx.config.relation_policies.get(name)
        if policy is None:
            continue
        obj = ctx.snapshot.objects_by_id.get(source)
        if policy.minimum_per_source is not None and count < policy.minimum_per_source:
            yield Finding(
                "REQ010", RULES["REQ010"].default_severity,
                f"{source} declares {count} {name} relation(s); at least {policy.minimum_per_source} required",
                source, _loc(obj) if obj else None,
                {"actual": count, "minimum": policy.minimum_per_source},
            )
        if policy.maximum_per_source is not None and count > policy.maximum_per_source:
            yield Finding(
                "REQ010", RULES["REQ010"].default_severity,
                f"{source} declares {count} {name} relation(s); at most {policy.maximum_per_source} allowed",
                source, _loc(obj) if obj else None,
                {"actual": count, "maximum": policy.maximum_per_source},
            )


def _approved_implementation(ctx: RuleContext) -> Iterable[Finding]:
    for obj in _reqs(ctx):
        if obj.status == "approved" and not any(
            edge.semantic_family == "implementation" and _exists(ctx, edge.target)
            for edge in ctx.snapshot.outgoing.get(obj.id, ())
        ):
            yield Finding(
                "REQ011", RULES["REQ011"].default_severity,
                f"{obj.id} is approved but has no implementation relation", obj.id, _loc(obj)
            )


def _test_evidence(ctx: RuleContext) -> Iterable[Finding]:
    accepted = {"approved", *ctx.config.successful_test_statuses}
    for obj in ctx.snapshot.objects:
        if obj.type in ctx.config.test_types and obj.status.casefold() in accepted and not any(
            edge.semantic_family == "evidence" and _exists(ctx, edge.target)
            for edge in ctx.snapshot.outgoing.get(obj.id, ())
        ):
            yield Finding(
                "REQ012", RULES["REQ012"].default_severity,
                f"{obj.id} is {obj.status} but has no evidence relation", obj.id, _loc(obj)
            )


def _risk_mitigation(ctx: RuleContext) -> Iterable[Finding]:
    for obj in ctx.snapshot.objects:
        if obj.type not in ctx.config.risk_types or str(obj.attributes.get("priority", "")).casefold() not in {"high", "critical"}:
            continue
        if not any(edge.semantic_family == "mitigation" for edge in ctx.snapshot.incoming.get(obj.id, ())):
            yield Finding(
                "REQ013", RULES["REQ013"].default_severity,
                f"{obj.id} is a high-priority risk without mitigation", obj.id, _loc(obj)
            )


def _orphans(ctx: RuleContext) -> Iterable[Finding]:
    for obj in ctx.snapshot.objects:
        if not ctx.snapshot.outgoing.get(obj.id, ()) and not ctx.snapshot.incoming.get(obj.id, ()):
            yield Finding(
                "REQ014", RULES["REQ014"].default_severity,
                f"{obj.id} has no relations in either direction", obj.id, _loc(obj)
            )


def _expired_evidence(ctx: RuleContext) -> Iterable[Finding]:
    attr = ctx.config.expiry_attribute
    if not attr:
        return
    today = reference_date()
    for obj in ctx.snapshot.objects:
        raw = obj.attributes.get(attr)
        if raw is None or str(raw).strip() == "":
            continue
        parsed = parse_iso_date(str(raw))
        props = {"attribute": attr, "referenceDate": today.isoformat()}
        if parsed is None:
            yield Finding(
                "REQ015", RULES["REQ015"].default_severity,
                f"{obj.id} has an unparseable {attr} value: {raw}", obj.id, _loc(obj),
                {**props, "reason": "unparseable"},
            )
        elif parsed < today:
            yield Finding(
                "REQ015", RULES["REQ015"].default_severity,
                f"{obj.id} evidence expired on {parsed.isoformat()}", obj.id, _loc(obj),
                {**props, "reason": "expired"},
            )


def _id_prefix(ctx: RuleContext) -> Iterable[Finding]:
    for obj in ctx.snapshot.objects:
        prefix = ctx.config.id_prefixes.get(obj.type)
        if prefix and not obj.id.startswith(prefix):
            yield Finding(
                "ID001", RULES["ID001"].default_severity,
                f"{obj.id} does not use configured prefix {prefix!r} for type {obj.type}",
                obj.id, _loc(obj), {"type": obj.type, "prefix": prefix},
            )


def _allowed_status(ctx: RuleContext) -> Iterable[Finding]:
    for obj in ctx.snapshot.objects:
        allowed = ctx.config.allowed_statuses.get(obj.type)
        if allowed and obj.status not in allowed:
            yield Finding(
                "OBJ001", RULES["OBJ001"].default_severity,
                f"{obj.id} has status {obj.status!r}; allowed for {obj.type}: {', '.join(allowed)}",
                obj.id, _loc(obj), {"type": obj.type, "allowed": allowed},
            )


def _attribute_schema(ctx: RuleContext) -> Iterable[Finding]:
    if not ctx.config.attribute_schemas:
        return ()
    from .type_schema import compile_type_schemas, validate_type_schemas

    schemas = compile_type_schemas(ctx.config.attribute_schemas)
    return validate_type_schemas(schemas, ctx.snapshot)


def _decision_driver(ctx: RuleContext) -> Iterable[Finding]:
    for obj in _decs(ctx):
        has_driver = (
            _relation_out(ctx, obj.id, "addresses")
            or _relation_in(ctx, obj.id, "addressed-by")
        )
        if obj.status == "accepted" and not has_driver:
            yield Finding(
                "DEC001", RULES["DEC001"].default_severity,
                f"{obj.id} is accepted but addresses no engineering driver", obj.id, _loc(obj)
            )


def _decision_scope(ctx: RuleContext) -> Iterable[Finding]:
    for obj in _decs(ctx):
        if obj.status == "accepted" and not _family_out(ctx, obj.id, "decision-scope"):
            yield Finding(
                "DEC002", RULES["DEC002"].default_severity,
                f"{obj.id} is accepted but has no architectural scope", obj.id, _loc(obj)
            )


def _decision_confirmation(ctx: RuleContext) -> Iterable[Finding]:
    for obj in _decs(ctx):
        has_confirmation = (
            _relation_out(ctx, obj.id, "confirmed-by")
            or _relation_in(ctx, obj.id, "confirms")
        )
        if obj.status == "accepted" and not has_confirmation:
            yield Finding(
                "DEC003", RULES["DEC003"].default_severity,
                f"{obj.id} is accepted but has no confirmation relation", obj.id, _loc(obj)
            )


def _decision_successor(ctx: RuleContext) -> Iterable[Finding]:
    for obj in _decs(ctx):
        has_successor = (
            _relation_out(ctx, obj.id, "superseded-by")
            or _relation_in(ctx, obj.id, "supersedes")
        )
        if obj.status == "superseded" and not has_successor:
            yield Finding(
                "DEC004", RULES["DEC004"].default_severity,
                f"{obj.id} is superseded but identifies no successor decision", obj.id, _loc(obj)
            )


_C4_LAYER_ORDER = ("system", "container", "component", "source-module")
_C4_LAYER_INDEX = {name: index for index, name in enumerate(_C4_LAYER_ORDER)}


def _architecture_layer_adjacency(ctx: RuleContext) -> Iterable[Finding]:
    """part-of/decomposes must connect a layer to the one exactly above it.

    part-of and decomposes are a genuine inverse-direction pair (like
    implements/implemented-by, not like derives-from/derived-from's same-
    direction synonym pair) — Task 1 gives them distinct v1_names for
    exactly this reason: a per-direction relation_policies entry must be
    able to target one authoring direction without silently also matching
    the other. This rule handles both authored directions explicitly
    rather than assuming only one is ever used: a part-of edge's source is
    the child (deeper layer) and target is the parent (shallower layer); a
    decomposes edge is the reverse. Types outside the fixed C4 layer set
    (actor, external-system, or any project-specific type never meant to
    participate in this hierarchy) are not this rule's concern — they
    simply never match the layer table.
    """
    for edge in ctx.snapshot.relations:
        if edge.authored_name == "part-of":
            child_id, parent_id = edge.source, edge.target
        elif edge.authored_name == "decomposes":
            child_id, parent_id = edge.target, edge.source
        else:
            continue
        child = ctx.snapshot.objects_by_id.get(child_id)
        parent = ctx.snapshot.objects_by_id.get(parent_id)
        if child is None or parent is None:
            continue
        child_index = _C4_LAYER_INDEX.get(child.type)
        parent_index = _C4_LAYER_INDEX.get(parent.type)
        if child_index is None or parent_index is None:
            continue
        if child_index != parent_index + 1:
            yield Finding(
                "ARC001",
                RULES["ARC001"].default_severity,
                f"{child_id} ({child.type}) may not be a child of "
                f"{parent_id} ({parent.type}): part-of/decomposes must "
                "connect a layer to the layer exactly above it "
                f"({' > '.join(_C4_LAYER_ORDER)})",
                child_id,
                edge.provenance[0] if edge.provenance else None,
                {"sourceType": child.type, "targetType": parent.type},
            )


def _decision_cycle(ctx: RuleContext) -> Iterable[Finding]:
    graph: dict[str, set[str]] = {obj.id: set() for obj in _decs(ctx)}
    for edge in ctx.snapshot.relations:
        if edge.semantic_family != "decision-lineage":
            continue
        if edge.v1_name == "supersedes":
            graph.setdefault(edge.source, set()).add(edge.target)
        elif edge.v1_name == "superseded-by":
            graph.setdefault(edge.target, set()).add(edge.source)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, path: tuple[str, ...]) -> tuple[str, ...] | None:
        if node in visiting:
            return path[path.index(node):] + (node,) if node in path else path + (node,)
        if node in visited:
            return None
        visiting.add(node)
        for target in sorted(graph.get(node, ())):
            cycle = visit(target, path + (node,))
            if cycle:
                return cycle
        visiting.remove(node)
        visited.add(node)
        return None

    for node in sorted(graph):
        cycle = visit(node, ())
        if cycle:
            obj = ctx.snapshot.objects_by_id.get(cycle[0])
            yield Finding(
                "DEC005", RULES["DEC005"].default_severity,
                f"Architecture decision supersession cycle: {' -> '.join(cycle)}",
                cycle[0], _loc(obj) if obj else None, {"cycle": cycle},
            )
            return


def _decision_revisit(ctx: RuleContext) -> Iterable[Finding]:
    today = reference_date()
    for obj in _decs(ctx):
        if obj.status != "accepted":
            continue
        raw = obj.attributes.get("revisit-after")
        if raw is None or not str(raw).strip():
            continue
        parsed = parse_iso_date(str(raw))
        props = {"attribute": "revisit-after", "referenceDate": today.isoformat()}
        if parsed is None:
            yield Finding(
                "DEC006", RULES["DEC006"].default_severity,
                f"{obj.id} has an unparseable revisit-after value: {raw}", obj.id, _loc(obj),
                {**props, "reason": "unparseable"},
            )
        elif parsed < today:
            yield Finding(
                "DEC006", RULES["DEC006"].default_severity,
                f"{obj.id} was due for architecture-decision review on {parsed.isoformat()}",
                obj.id, _loc(obj), {**props, "reason": "overdue", "due": parsed.isoformat()},
            )


RULES: Mapping[str, RuleSpec]
RULES = {spec.code: spec for spec in (
    RuleSpec("REQ002", "Missing rationale", "Requirement declarations should explain why they exist.", "warning"),
    RuleSpec("REQ004", "Duplicate identifier", "Every engineering object needs a unique ID.", "error", structural=True),
    RuleSpec("REQ005", "Unknown relation target", "Relations must point at declared objects.", "error", structural=True),
    RuleSpec("REQ006", "Approved without verification", "Approved requirements need a verification relation.", "warning", supported_severities=("error", "warning")),
    RuleSpec("REQ008", "Required attribute missing", "Configured types may require attributes.", "warning", evaluator=_required_attributes, auto_activates=lambda config: bool(config.required_attributes)),
    RuleSpec("REQ009", "Relation endpoint not allowed", "Configured relations restrict endpoint types.", "warning", evaluator=_relation_endpoints, auto_activates=lambda config: bool(config.relation_policies)),
    RuleSpec("REQ010", "Relation cardinality violated", "Configured relations may constrain cardinality.", "warning", evaluator=_cardinality, auto_activates=lambda config: bool(config.relation_policies)),
    RuleSpec("REQ011", "Approved without implementation", "Approved requirements need an implementation-family relation.", "warning", evaluator=_approved_implementation),
    RuleSpec("REQ012", "Test without evidence", "Approved or passed tests need evidence-family relations.", "warning", evaluator=_test_evidence),
    RuleSpec("REQ013", "High risk without mitigation", "High/critical risks need incoming mitigation relations.", "warning", evaluator=_risk_mitigation),
    RuleSpec("REQ014", "Orphaned object", "Objects with no relations in either direction.", "info", evaluator=_orphans),
    RuleSpec("REQ015", "Expired evidence", "Evidence carrying an expiry attribute must still be valid.", "warning", evaluator=_expired_evidence),
    RuleSpec("ID001", "Configured ID prefix violated", "Object IDs may be governed by a prefix per engineering type.", "warning", evaluator=_id_prefix, auto_activates=lambda config: bool(config.id_prefixes)),
    RuleSpec("OBJ001", "Status outside type lifecycle", "Object status must belong to the configured lifecycle for its type.", "warning", evaluator=_allowed_status, auto_activates=lambda config: bool(config.allowed_statuses)),
    RuleSpec("OBJ002", "Attribute schema violation", "Object attributes may be constrained by a per-type Draft 2020-12 JSON Schema.", "error", evaluator=_attribute_schema, auto_activates=lambda config: bool(config.attribute_schemas)),
    RuleSpec("DEC001", "Accepted decision without driver", "Accepted architecture decisions should address at least one engineering driver.", "warning", evaluator=_decision_driver),
    RuleSpec("DEC002", "Accepted decision without architectural scope", "Accepted architecture decisions should identify affected architecture elements.", "warning", evaluator=_decision_scope),
    RuleSpec("DEC003", "Accepted decision without confirmation", "Accepted architecture decisions should define how continued conformance is confirmed.", "warning", evaluator=_decision_confirmation),
    RuleSpec("DEC004", "Superseded decision without successor", "Superseded decisions need explicit lineage to another decision.", "warning", evaluator=_decision_successor),
    RuleSpec("DEC005", "Decision supersession cycle", "Supersession lineage must remain acyclic.", "error", supported_severities=("error",), evaluator=_decision_cycle),
    RuleSpec("DEC006", "Accepted decision overdue for review", "Accepted decisions with revisit-after dates should be reviewed when due.", "warning", evaluator=_decision_revisit),
    RuleSpec("ARC001", "Architecture layer skipped", "part-of must connect adjacent C4 layers (system > container > component > source-module).", "error", supported_severities=("error",), evaluator=_architecture_layer_adjacency, auto_activates=lambda config: True),
)}
RULE_SET_VERSION = "7"

for _spec in RULES.values():
    if _spec.evaluator is None and _spec.code not in LEGACY_CODES:
        raise RuntimeError(f"rule {_spec.code} lacks an evaluator")


def _resolved_severity(spec: RuleSpec, config: NeedsConfig) -> str | None:
    setting = config.rule_settings.get(spec.code)
    if setting is None:
        if spec.code in LEGACY_CODES or (
            spec.auto_activates is not None and spec.auto_activates(config)
        ):
            return spec.default_severity
        return None
    if not setting.enabled:
        if spec.structural:
            raise ConfigurationError(f"rule {spec.code} is structural and cannot be disabled")
        return None
    if setting.severity is None:
        return spec.default_severity
    if spec.structural:
        raise ConfigurationError(f"rule {spec.code} is structural; its severity cannot be overridden")
    if setting.severity not in spec.supported_severities:
        raise ConfigurationError(
            f"rule {spec.code} does not support severity {setting.severity} "
            f"(supported: {', '.join(spec.supported_severities)})"
        )
    return setting.severity


def validate_gate_rule_dependencies(config: NeedsConfig) -> None:
    """Reject gates that can only ever pass because their rule is inactive.

    `require-risk-mitigation` is measured by counting REQ013 findings, and
    REQ013 is opt-in. Enabling the gate alone therefore reports a pass for
    every project, including one carrying unmitigated critical risks — a
    false assurance rather than a missing check. The two declarations have to
    agree, so an incoherent pair is a configuration error like any other.
    """
    if not config.gates.require_risk_mitigation:
        return
    if _resolved_severity(RULES["REQ013"], config) is None:
        raise ConfigurationError(
            "[gates] require-risk-mitigation counts REQ013 findings, but rule "
            "REQ013 is not enabled, so the gate could only ever pass. Add "
            '[rules.REQ013] enabled = true, or remove the gate.'
        )


def run_rules(snapshot: AnalysisSnapshot, config: NeedsConfig) -> tuple[Finding, ...]:
    validate_gate_rule_dependencies(config)
    ctx = RuleContext(snapshot=snapshot, config=config)
    findings: list[Finding] = []
    for code in sorted(RULES):
        spec = RULES[code]
        if code in LEGACY_CODES:
            continue
        severity = _resolved_severity(spec, config)
        if severity is None:
            continue
        assert spec.evaluator is not None
        findings.extend(replace(finding, severity=severity) for finding in spec.evaluator(ctx))

    if config.policy_sources:
        from .policy import PolicyError, compile_policies, evaluate_policies

        try:
            policies = compile_policies(config.policy_sources)
            findings.extend(evaluate_policies(policies, snapshot, config))
        except PolicyError as error:
            raise ConfigurationError(str(error)) from error

    if config.constraint_sources:
        from .graph_constraints import (
            GraphConstraintError,
            compile_graph_constraints,
            evaluate_graph_constraints,
        )

        try:
            constraints = compile_graph_constraints(config.constraint_sources)
            findings.extend(evaluate_graph_constraints(constraints, snapshot, config))
        except GraphConstraintError as error:
            raise ConfigurationError(str(error)) from error
    return tuple(findings)


def apply_rule_settings(findings: Iterable[Finding], config: NeedsConfig) -> tuple[Finding, ...]:
    result: list[Finding] = []
    for finding in findings:
        spec = RULES.get(finding.code)
        if spec is None:
            result.append(finding)
            continue
        severity = _resolved_severity(spec, config)
        if severity is not None:
            result.append(replace(finding, severity=severity) if severity != finding.severity else finding)
    return tuple(result)
