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


def _reqs(ctx: RuleContext) -> list[ObjectRecord]:
    return [o for o in ctx.snapshot.objects if o.type.endswith("requirement")]


def _decs(ctx: RuleContext) -> list[ObjectRecord]:
    return [o for o in ctx.snapshot.objects if o.type == DECISION_TYPE]


def _loc(o: ObjectRecord):
    return o.locations[0] if o.locations else None


def _exists(ctx: RuleContext, oid: str) -> bool:
    return oid in ctx.snapshot.objects_by_id


def _family_out(ctx: RuleContext, oid: str, family: str) -> tuple:
    return tuple(e for e in ctx.snapshot.outgoing.get(oid, ()) if e.semantic_family == family and _exists(ctx, e.target))


def _family_in(ctx: RuleContext, oid: str, family: str) -> tuple:
    return tuple(e for e in ctx.snapshot.incoming.get(oid, ()) if e.semantic_family == family and _exists(ctx, e.source))


def _required_attributes(ctx: RuleContext) -> Iterable[Finding]:
    for o in ctx.snapshot.objects:
        for attr in ctx.config.required_attributes.get(o.type, ()):
            value = o.attributes.get(attr)
            if value is None or (isinstance(value, str) and not value.strip()) or (isinstance(value, (tuple, list)) and not value):
                yield Finding("REQ008", RULES["REQ008"].default_severity, f"{o.id} is missing required attribute {attr}", o.id, _loc(o), {"attribute": attr})


def _relation_endpoints(ctx: RuleContext) -> Iterable[Finding]:
    for e in ctx.snapshot.relations:
        p = ctx.config.relation_policies.get(e.v1_name)
        if p is None:
            continue
        s = ctx.snapshot.objects_by_id.get(e.source)
        t = ctx.snapshot.objects_by_id.get(e.target)
        if s is not None and p.allowed_source_types and s.type not in p.allowed_source_types:
            yield Finding("REQ009", RULES["REQ009"].default_severity, f"{e.source} may not be the source of {e.v1_name} (allowed: {', '.join(p.allowed_source_types)})", e.source, e.provenance[0] if e.provenance else None, {"side": "source", "expected": p.allowed_source_types})
        if t is not None and p.allowed_target_types and t.type not in p.allowed_target_types:
            yield Finding("REQ009", RULES["REQ009"].default_severity, f"{e.target} may not be the target of {e.v1_name} (allowed: {', '.join(p.allowed_target_types)})", e.target, e.provenance[0] if e.provenance else None, {"side": "target", "expected": p.allowed_target_types})


def _cardinality(ctx: RuleContext) -> Iterable[Finding]:
    counts: dict[tuple[str, str], int] = {}
    for e in ctx.snapshot.relations:
        counts[(e.source, e.v1_name)] = counts.get((e.source, e.v1_name), 0) + 1
    for (source, name), count in sorted(counts.items()):
        p = ctx.config.relation_policies.get(name)
        if p is None:
            continue
        o = ctx.snapshot.objects_by_id.get(source)
        if p.minimum_per_source is not None and count < p.minimum_per_source:
            yield Finding("REQ010", RULES["REQ010"].default_severity, f"{source} declares {count} {name} relation(s); at least {p.minimum_per_source} required", source, _loc(o) if o else None, {"actual": count, "minimum": p.minimum_per_source})
        if p.maximum_per_source is not None and count > p.maximum_per_source:
            yield Finding("REQ010", RULES["REQ010"].default_severity, f"{source} declares {count} {name} relation(s); at most {p.maximum_per_source} allowed", source, _loc(o) if o else None, {"actual": count, "maximum": p.maximum_per_source})


def _approved_implementation(ctx: RuleContext) -> Iterable[Finding]:
    for o in _reqs(ctx):
        if o.status == "approved" and not any(e.semantic_family == "implementation" and _exists(ctx, e.target) for e in ctx.snapshot.outgoing.get(o.id, ())):
            yield Finding("REQ011", RULES["REQ011"].default_severity, f"{o.id} is approved but has no implementation relation", o.id, _loc(o))


def _test_evidence(ctx: RuleContext) -> Iterable[Finding]:
    accepted = {"approved", *ctx.config.successful_test_statuses}
    for o in ctx.snapshot.objects:
        if o.type in ctx.config.test_types and o.status.casefold() in accepted and not any(e.semantic_family == "evidence" and _exists(ctx, e.target) for e in ctx.snapshot.outgoing.get(o.id, ())):
            yield Finding("REQ012", RULES["REQ012"].default_severity, f"{o.id} is {o.status} but has no evidence relation", o.id, _loc(o))


def _risk_mitigation(ctx: RuleContext) -> Iterable[Finding]:
    for o in ctx.snapshot.objects:
        if o.type not in ctx.config.risk_types or str(o.attributes.get("priority", "")).casefold() not in {"high", "critical"}:
            continue
        if not any(e.semantic_family == "mitigation" for e in ctx.snapshot.incoming.get(o.id, ())):
            yield Finding("REQ013", RULES["REQ013"].default_severity, f"{o.id} is a high-priority risk without mitigation", o.id, _loc(o))


def _orphans(ctx: RuleContext) -> Iterable[Finding]:
    for o in ctx.snapshot.objects:
        if not ctx.snapshot.outgoing.get(o.id, ()) and not ctx.snapshot.incoming.get(o.id, ()):
            yield Finding("REQ014", RULES["REQ014"].default_severity, f"{o.id} has no relations in either direction", o.id, _loc(o))


def _expired_evidence(ctx: RuleContext) -> Iterable[Finding]:
    attr = ctx.config.expiry_attribute
    if not attr:
        return
    today = reference_date()
    for o in ctx.snapshot.objects:
        raw = o.attributes.get(attr)
        if raw is None or str(raw).strip() == "":
            continue
        parsed = parse_iso_date(str(raw))
        props = {"attribute": attr, "referenceDate": today.isoformat()}
        if parsed is None:
            yield Finding("REQ015", RULES["REQ015"].default_severity, f"{o.id} has an unparseable {attr} value: {raw}", o.id, _loc(o), {**props, "reason": "unparseable"})
        elif parsed < today:
            yield Finding("REQ015", RULES["REQ015"].default_severity, f"{o.id} evidence expired on {parsed.isoformat()}", o.id, _loc(o), {**props, "reason": "expired"})


def _id_prefix(ctx: RuleContext) -> Iterable[Finding]:
    for o in ctx.snapshot.objects:
        prefix = ctx.config.id_prefixes.get(o.type)
        if prefix and not o.id.startswith(prefix):
            yield Finding("ID001", RULES["ID001"].default_severity, f"{o.id} does not use configured prefix {prefix!r} for type {o.type}", o.id, _loc(o), {"type": o.type, "prefix": prefix})


def _allowed_status(ctx: RuleContext) -> Iterable[Finding]:
    for o in ctx.snapshot.objects:
        allowed = ctx.config.allowed_statuses.get(o.type)
        if allowed and o.status not in allowed:
            yield Finding("OBJ001", RULES["OBJ001"].default_severity, f"{o.id} has status {o.status!r}; allowed for {o.type}: {', '.join(allowed)}", o.id, _loc(o), {"type": o.type, "allowed": allowed})


def _decision_driver(ctx: RuleContext) -> Iterable[Finding]:
    for o in _decs(ctx):
        if o.status == "accepted" and not _family_out(ctx, o.id, "decision-addressing"):
            yield Finding("DEC001", RULES["DEC001"].default_severity, f"{o.id} is accepted but addresses no engineering driver", o.id, _loc(o))


def _decision_scope(ctx: RuleContext) -> Iterable[Finding]:
    for o in _decs(ctx):
        if o.status == "accepted" and not _family_out(ctx, o.id, "decision-scope"):
            yield Finding("DEC002", RULES["DEC002"].default_severity, f"{o.id} is accepted but has no architectural scope", o.id, _loc(o))


def _decision_confirmation(ctx: RuleContext) -> Iterable[Finding]:
    for o in _decs(ctx):
        if o.status == "accepted" and not _family_out(ctx, o.id, "decision-confirmation"):
            yield Finding("DEC003", RULES["DEC003"].default_severity, f"{o.id} is accepted but has no confirmation relation", o.id, _loc(o))


def _decision_successor(ctx: RuleContext) -> Iterable[Finding]:
    for o in _decs(ctx):
        if o.status == "superseded" and not (_family_out(ctx, o.id, "decision-lineage") or _family_in(ctx, o.id, "decision-lineage")):
            yield Finding("DEC004", RULES["DEC004"].default_severity, f"{o.id} is superseded but has no decision-lineage relation", o.id, _loc(o))


def _decision_cycle(ctx: RuleContext) -> Iterable[Finding]:
    graph: dict[str, set[str]] = {o.id: set() for o in _decs(ctx)}
    for e in ctx.snapshot.relations:
        if e.semantic_family != "decision-lineage":
            continue
        if e.v1_name == "supersedes":
            graph.setdefault(e.source, set()).add(e.target)
        elif e.v1_name == "superseded-by":
            graph.setdefault(e.target, set()).add(e.source)
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
            o = ctx.snapshot.objects_by_id.get(cycle[0])
            yield Finding("DEC005", RULES["DEC005"].default_severity, f"Architecture decision supersession cycle: {' -> '.join(cycle)}", cycle[0], _loc(o) if o else None, {"cycle": cycle})
            return


RULES: Mapping[str, RuleSpec]
RULES = {s.code: s for s in (
    RuleSpec("REQ002", "Missing rationale", "Requirement declarations should explain why they exist.", "warning"),
    RuleSpec("REQ004", "Duplicate identifier", "Every engineering object needs a unique ID.", "error", structural=True),
    RuleSpec("REQ005", "Unknown relation target", "Relations must point at declared objects.", "error", structural=True),
    RuleSpec("REQ006", "Approved without verification", "Approved requirements need a verification relation.", "warning", supported_severities=("error", "warning")),
    RuleSpec("REQ008", "Required attribute missing", "Configured types may require attributes.", "warning", evaluator=_required_attributes, auto_activates=lambda c: bool(c.required_attributes)),
    RuleSpec("REQ009", "Relation endpoint not allowed", "Configured relations restrict endpoint types.", "warning", evaluator=_relation_endpoints, auto_activates=lambda c: bool(c.relation_policies)),
    RuleSpec("REQ010", "Relation cardinality violated", "Configured relations may constrain cardinality.", "warning", evaluator=_cardinality, auto_activates=lambda c: bool(c.relation_policies)),
    RuleSpec("REQ011", "Approved without implementation", "Approved requirements need an implementation-family relation.", "warning", evaluator=_approved_implementation),
    RuleSpec("REQ012", "Test without evidence", "Approved or passed tests need evidence-family relations.", "warning", evaluator=_test_evidence),
    RuleSpec("REQ013", "High risk without mitigation", "High/critical risks need incoming mitigation relations.", "warning", evaluator=_risk_mitigation),
    RuleSpec("REQ014", "Orphaned object", "Objects with no relations in either direction.", "info", evaluator=_orphans),
    RuleSpec("REQ015", "Expired evidence", "Evidence carrying an expiry attribute must still be valid.", "warning", evaluator=_expired_evidence),
    RuleSpec("ID001", "Configured ID prefix violated", "Object IDs may be governed by a prefix per engineering type.", "warning", evaluator=_id_prefix, auto_activates=lambda c: bool(c.id_prefixes)),
    RuleSpec("OBJ001", "Status outside type lifecycle", "Object status must belong to the configured lifecycle for its type.", "warning", evaluator=_allowed_status, auto_activates=lambda c: bool(c.allowed_statuses)),
    RuleSpec("DEC001", "Accepted decision without driver", "Accepted architecture decisions should address at least one engineering driver.", "warning", evaluator=_decision_driver),
    RuleSpec("DEC002", "Accepted decision without architectural scope", "Accepted architecture decisions should identify affected architecture elements.", "warning", evaluator=_decision_scope),
    RuleSpec("DEC003", "Accepted decision without confirmation", "Accepted architecture decisions should define how continued conformance is confirmed.", "warning", evaluator=_decision_confirmation),
    RuleSpec("DEC004", "Superseded decision without successor", "Superseded decisions need explicit lineage to another decision.", "warning", evaluator=_decision_successor),
    RuleSpec("DEC005", "Decision supersession cycle", "Supersession lineage must remain acyclic.", "error", supported_severities=("error",), evaluator=_decision_cycle),
)}
RULE_SET_VERSION = "2"

for _spec in RULES.values():
    if _spec.evaluator is None and _spec.code not in LEGACY_CODES:
        raise RuntimeError(f"rule {_spec.code} lacks an evaluator")


def _resolved_severity(spec: RuleSpec, config: NeedsConfig) -> str | None:
    setting = config.rule_settings.get(spec.code)
    if setting is None:
        if spec.code in LEGACY_CODES or (spec.auto_activates is not None and spec.auto_activates(config)):
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
        raise ConfigurationError(f"rule {spec.code} does not support severity {setting.severity} (supported: {', '.join(spec.supported_severities)})")
    return setting.severity


def run_rules(snapshot: AnalysisSnapshot, config: NeedsConfig) -> tuple[Finding, ...]:
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
        findings.extend(replace(f, severity=severity) for f in spec.evaluator(ctx))
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
