from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .config import NeedsConfig, parse_iso_date, reference_date
from .queries import (
    DEFAULT_QUERY_NAME,
    DEFAULT_QUERY_SOURCE,
    compile_query,
    evaluate as evaluate_query,
)
from .snapshot import AnalysisSnapshot, ObjectRecord


IMPLEMENTATION_FAMILY = "implementation"
VERIFICATION_FAMILY = "verification"
EVIDENCE_FAMILY = "evidence"

CATALOG_SCOPE = "catalog"

COVERAGE_STRENGTHS = (
    "implementation-trace",
    "implementation-effective",
    "verification-trace",
    "verification-successful",
    "evidence",
)


@dataclass(frozen=True, slots=True)
class CoverageMeasure:
    covered: int
    total: int

    @property
    def percent(self) -> float:
        """An empty denominator reports full availability, mirroring legacy coverage."""
        if self.total == 0:
            return 100.0
        return round(100.0 * self.covered / self.total, 1)

    def to_dict(self) -> dict[str, object]:
        return {"covered": self.covered, "total": self.total, "percent": self.percent}


@dataclass(frozen=True, slots=True)
class ScopeMetrics:
    name: str
    denominator: int
    breakdowns: Mapping[str, Mapping[str, int]]
    coverage: Mapping[str, CoverageMeasure]
    gaps: Mapping[str, tuple[str, ...]]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "denominator": self.denominator,
            "breakdowns": {key: dict(self.breakdowns[key]) for key in sorted(self.breakdowns)},
            "coverage": {
                key: self.coverage[key].to_dict() for key in COVERAGE_STRENGTHS
            },
            "gaps": {key: list(self.gaps[key]) for key in sorted(self.gaps)},
        }


@dataclass(frozen=True, slots=True)
class ReportMetrics:
    scopes: Mapping[str, ScopeMetrics]

    def to_dict(self) -> dict[str, object]:
        return {
            "scopes": {name: self.scopes[name].to_dict() for name in sorted(self.scopes)}
        }


def _text_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def _requirement_ids(snapshot: AnalysisSnapshot) -> set[str]:
    return {item.id for item in snapshot.objects if item.type.endswith("requirement")}


def _priority_of(record: ObjectRecord) -> str:
    value = record.attributes.get("priority")
    if value is None or str(value).strip() == "":
        return "unspecified"
    return str(value).casefold()


def _parse_expiry(raw: object, config: NeedsConfig) -> bool | None:
    """True when valid/non-expired, False when expired/unparseable, None when unchecked."""
    if raw is None or str(raw).strip() == "":
        return True
    parsed = parse_iso_date(str(raw))
    if parsed is None:
        return False
    return parsed >= reference_date()


def _compute_scope(
    name: str,
    members: set[str],
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
) -> ScopeMetrics:
    records = [
        snapshot.objects_by_id[object_id]
        for object_id in members
        if object_id in snapshot.objects_by_id
    ]
    denominator = len(records)

    type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    for record in records:
        type_counts[record.type] = type_counts.get(record.type, 0) + 1
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
        priority = _priority_of(record)
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

    ineffective = {status.casefold() for status in config.ineffective_endpoint_statuses}
    successful = {status.casefold() for status in config.successful_test_statuses}

    impl_trace: set[str] = set()
    impl_effective: set[str] = set()
    ver_trace: set[str] = set()
    ver_successful: set[str] = set()
    evidence_ok: set[str] = set()

    today_checked = bool(config.expiry_attribute)
    for record in records:
        outgoing = snapshot.outgoing.get(record.id, ())
        for relation in outgoing:
            target = snapshot.objects_by_id.get(relation.target)
            if target is None:
                continue
            if relation.semantic_family == IMPLEMENTATION_FAMILY:
                impl_trace.add(record.id)
                if target.status.casefold() not in ineffective:
                    impl_effective.add(record.id)
            elif relation.semantic_family == VERIFICATION_FAMILY:
                ver_trace.add(record.id)
                if target.status.casefold() in successful:
                    ver_successful.add(record.id)
        if record.id not in ver_successful:
            continue
        # Evidence strength: at least one successful verifying test must point
        # at an existing, allowed, non-expired evidence endpoint.
        verifying_tests = [
            snapshot.objects_by_id[relation.target]
            for relation in outgoing
            if relation.semantic_family == VERIFICATION_FAMILY
            and relation.target in snapshot.objects_by_id
            and snapshot.objects_by_id[relation.target].status.casefold() in successful
        ]
        for test in verifying_tests:
            for edge in snapshot.outgoing.get(test.id, ()):
                evidence = snapshot.objects_by_id.get(edge.target)
                if evidence is None or edge.semantic_family != EVIDENCE_FAMILY:
                    continue
                expiry_state: bool | None = (
                    _parse_expiry(evidence.attributes.get(config.expiry_attribute), config)
                    if today_checked
                    else True
                )
                if expiry_state:
                    evidence_ok.add(record.id)
                    break
            if record.id in evidence_ok:
                break

    covered = {
        "implementation-trace": len(impl_trace),
        "implementation-effective": len(impl_effective),
        "verification-trace": len(ver_trace),
        "verification-successful": len(ver_successful),
        "evidence": len(evidence_ok),
    }
    gaps = {
        "implementation-effective": tuple(
            sorted(
                (item.id for item in records if item.id not in impl_effective),
                key=_text_key,
            )
        ),
        "verification-successful": tuple(
            sorted(
                (item.id for item in records if item.id not in ver_successful),
                key=_text_key,
            )
        ),
        "evidence": tuple(
            sorted(
                (
                    item.id
                    for item in records
                    if item.id in ver_successful and item.id not in evidence_ok
                ),
                key=_text_key,
            )
        ),
    }
    return ScopeMetrics(
        name=name,
        denominator=denominator,
        breakdowns={
            "type": type_counts,
            "status": status_counts,
            "priority": priority_counts,
        },
        coverage={
            strength: CoverageMeasure(covered[strength], denominator)
            for strength in COVERAGE_STRENGTHS
        },
        gaps=gaps,
    )


def compute_report_metrics(
    snapshot: AnalysisSnapshot,
    config: NeedsConfig,
    scope_ids: Mapping[str, tuple[str, ...]] | None = None,
) -> ReportMetrics:
    requirements = _requirement_ids(snapshot)
    scopes: dict[str, ScopeMetrics] = {
        CATALOG_SCOPE: _compute_scope(CATALOG_SCOPE, requirements, snapshot, config)
    }
    if scope_ids is None:
        default = compile_query(DEFAULT_QUERY_NAME, dict(DEFAULT_QUERY_SOURCE))
        approved = {item.id for item in evaluate_query(default, snapshot)}
    else:
        approved = set(scope_ids.get(DEFAULT_QUERY_NAME, ()))
    scopes[DEFAULT_QUERY_NAME] = _compute_scope(
        DEFAULT_QUERY_NAME, requirements & approved, snapshot, config
    )
    for name, ids in (scope_ids or {}).items():
        if name == DEFAULT_QUERY_NAME:
            continue
        scopes[name] = _compute_scope(name, requirements & set(ids), snapshot, config)
    return ReportMetrics(scopes=scopes)


def render_measure(measure: CoverageMeasure) -> str:
    """Human-readable `value% (covered/total)` used by text output."""
    return f"{measure.percent}% ({measure.covered}/{measure.total})"
