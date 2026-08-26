from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import cast

import quarto_needs

from .config import NeedsConfig, embedded_defaults, load_config
from .diagnostics import Finding
from .model import EngineeringObject, Relation, SourceLocation
from .parser import parse_project_declarations
from .relations import DEFAULT_RELATION_CATALOG
from .rules import apply_rule_settings, run_rules
from .snapshot import (
    AnalysisResult,
    AnalysisSnapshot,
    DeclarationBatch,
    LocationRecord,
    ObjectDeclaration,
    ObjectRecord,
    RelationRecord,
    RelationToken,
    thaw_json,
)
from .validation import finding_key, validate


STRUCTURAL_ERROR_CODES = frozenset(
    {"QND001", "QND002", "REQ004", "REQ005", "REQ007"}
)


def text_key(value: str) -> tuple[str, str]:
    return value.casefold(), value


def object_key(item: ObjectRecord) -> tuple[object, ...]:
    location = item.locations[0] if item.locations else None
    return (
        *text_key(item.id),
        location.file.casefold() if location else "",
        location.file if location else "",
        location.line if location else 0,
    )


def relation_key(item: RelationRecord) -> tuple[object, ...]:
    attributes = json.dumps(
        thaw_json(item.attributes),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        *text_key(item.source),
        item.v1_name,
        *text_key(item.target),
        item.authored_name,
        attributes,
    )


def _analysis_finding_key(item: Finding) -> tuple[object, ...]:
    location = item.location
    anchor = location.anchor if location is not None else None
    properties = json.dumps(
        thaw_json(item.properties),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        *finding_key(item),
        item.severity.casefold(),
        item.severity,
        item.object_id is not None,
        location is not None,
        anchor is not None,
        (anchor or "").casefold(),
        anchor or "",
        properties,
    )


def legacy_coverage(
    objects: tuple[ObjectRecord, ...],
    relations: tuple[RelationRecord, ...],
) -> dict[str, object]:
    requirements = [item for item in objects if item.type.endswith("requirement")]
    outgoing = {item.id: [] for item in objects}
    for relation in relations:
        outgoing.setdefault(relation.source, []).append(relation)
    implemented = [
        item
        for item in requirements
        if any(
            relation.v1_name in {"implements", "implemented-by"}
            for relation in outgoing[item.id]
        )
    ]
    verified = [
        item
        for item in requirements
        if any(
            relation.v1_name in {"verified-by", "validated-by"}
            for relation in outgoing[item.id]
        )
    ]
    total = len(requirements)
    return {
        "requirements": total,
        "approved": sum(item.status == "approved" for item in requirements),
        "implemented": len(implemented),
        "verified": len(verified),
        "implementation_coverage": (
            round(100 * len(implemented) / total, 1) if total else 100.0
        ),
        "verification_coverage": (
            round(100 * len(verified) / total, 1) if total else 100.0
        ),
    }


def _location(source: SourceLocation | None) -> LocationRecord | None:
    if source is None:
        return None
    return LocationRecord(source.file, source.line, source.anchor)


def _declaration(item: EngineeringObject) -> ObjectDeclaration:
    location = _location(item.source)
    return ObjectDeclaration(
        id=item.id,
        type=item.type,
        title=item.title,
        status=item.status,
        body=item.body,
        rationale=item.rationale,
        attributes=item.attributes,
        relations=tuple(
            RelationToken(
                relation.authored_name or relation.type,
                relation.target,
                relation.attributes,
                location,
            )
            for relation in item.relations
        ),
        location=location,
    )


def _legacy_objects(
    declarations: tuple[ObjectDeclaration, ...],
) -> tuple[list[EngineeringObject], list[Finding]]:
    objects: list[EngineeringObject] = []
    unsupported: list[Finding] = []
    for declaration in declarations:
        relations: list[Relation] = []
        for token in declaration.relations:
            try:
                relation_type = DEFAULT_RELATION_CATALOG.resolve(
                    token.authored_name
                ).v1_name
            except ValueError:
                relation_type = token.authored_name
                unsupported.append(
                    Finding(
                        "REQ007",
                        "error",
                        "Unsupported relation type "
                        f"{token.authored_name} on {declaration.id}",
                        declaration.id,
                        token.location or declaration.location,
                    )
                )
            relations.append(
                Relation(
                    relation_type,
                    declaration.id,
                    token.target,
                    cast(dict[str, object], thaw_json(token.attributes)),
                    token.authored_name,
                )
            )
        source = (
            SourceLocation(
                declaration.location.file,
                declaration.location.line,
                declaration.location.anchor,
            )
            if declaration.location is not None
            else None
        )
        objects.append(
            EngineeringObject(
                id=declaration.id,
                type=declaration.type,
                title=declaration.title,
                status=declaration.status,
                body=declaration.body,
                rationale=declaration.rationale,
                attributes=cast(
                    dict[str, object], thaw_json(declaration.attributes)
                ),
                relations=relations,
                source=source,
            )
        )
    return objects, unsupported


def _merge_findings(*groups: Iterable[Finding]) -> tuple[Finding, ...]:
    merged: list[Finding] = []
    seen: set[tuple[object, ...]] = set()
    for group in groups:
        for finding in group:
            key = _analysis_finding_key(finding)
            if key not in seen:
                seen.add(key)
                merged.append(finding)
    return tuple(sorted(merged, key=_analysis_finding_key))


def _records(
    declarations: tuple[ObjectDeclaration, ...],
) -> tuple[tuple[ObjectRecord, ...], tuple[RelationRecord, ...]]:
    objects = tuple(
        sorted(
            (
                ObjectRecord(
                    id=declaration.id,
                    type=declaration.type,
                    title=declaration.title,
                    status=declaration.status,
                    body=declaration.body,
                    rationale=declaration.rationale,
                    attributes=declaration.attributes,
                    locations=(declaration.location,)
                    if declaration.location is not None
                    else (),
                )
                for declaration in declarations
            ),
            key=object_key,
        )
    )
    relations: list[RelationRecord] = []
    for declaration in declarations:
        for token in declaration.relations:
            kind = DEFAULT_RELATION_CATALOG.resolve(token.authored_name)
            relations.append(
                RelationRecord(
                    source=declaration.id,
                    authored_name=token.authored_name,
                    catalog_name=kind.catalog_name,
                    v1_name=kind.v1_name,
                    target=token.target,
                    semantic_family=kind.semantic_family,
                    source_role=kind.source_role,
                    target_role=kind.target_role,
                    impact_direction=kind.impact_direction,
                    attributes=token.attributes,
                    provenance=(token.location,)
                    if token.location is not None
                    else (),
                )
            )
    return objects, tuple(sorted(relations, key=relation_key))


def _analyze_batch(
    batch: DeclarationBatch,
    reported_findings: Iterable[Finding] | None = None,
    config: NeedsConfig | None = None,
) -> AnalysisResult:
    effective_config = config if config is not None else embedded_defaults()
    declarations = batch.declarations
    legacy_objects, unsupported = _legacy_objects(declarations)
    compatibility_findings = validate(legacy_objects)
    if reported_findings is None:
        selected_findings = apply_rule_settings(compatibility_findings, effective_config)
    else:
        selected_findings = [
            finding
            for finding in compatibility_findings
            if finding.code in STRUCTURAL_ERROR_CODES
        ]
    findings = _merge_findings(
        batch.findings,
        () if reported_findings is None else reported_findings,
        selected_findings,
        unsupported,
    )
    if any(finding.code in STRUCTURAL_ERROR_CODES for finding in findings):
        return AnalysisResult(declarations, findings, None)

    objects, relations = _records(declarations)
    objects_by_id = {item.id: item for item in objects}
    outgoing: dict[str, tuple[RelationRecord, ...]] = {}
    incoming: dict[str, tuple[RelationRecord, ...]] = {}
    for item in objects:
        outgoing[item.id] = tuple(
            relation for relation in relations if relation.source == item.id
        )
        incoming[item.id] = tuple(
            relation for relation in relations if relation.target == item.id
        )
    metrics = legacy_coverage(objects, relations)
    draft = AnalysisSnapshot(
        objects=objects,
        relations=relations,
        findings=findings,
        metrics=metrics,
        objects_by_id=objects_by_id,
        outgoing=outgoing,
        incoming=incoming,
        generator_name="quarto-needs",
        generator_version=quarto_needs.__version__,
        relation_catalog_version=DEFAULT_RELATION_CATALOG.version,
    )
    rule_findings = run_rules(draft, effective_config)
    snapshot = (
        replace(draft, findings=_merge_findings(findings, rule_findings))
        if rule_findings
        else draft
    )
    return AnalysisResult(declarations, snapshot.findings, snapshot)


def analyze_project(
    root: Path,
    files: Iterable[Path] | None = None,
    *,
    config: NeedsConfig | None = None,
) -> AnalysisResult:
    effective_config = config if config is not None else load_config(root)
    if files is None:
        selected = None
    else:
        resolved_root = root.resolve()
        unique: set[Path] = set()
        for path in files:
            if path.is_absolute():
                resolved = path.resolve()
            else:
                resolved = path.resolve()
                if not resolved.is_relative_to(resolved_root):
                    resolved = (resolved_root / path).resolve()
            unique.add(resolved)
        selected = tuple(
            sorted(
                unique,
                key=lambda path: (path.as_posix().casefold(), path.as_posix()),
            )
        )
    return _analyze_batch(parse_project_declarations(root, selected), config=effective_config)


def analyze_objects(
    objects: Iterable[EngineeringObject],
    reported_findings: Iterable[Finding] | None = None,
    *,
    config: NeedsConfig | None = None,
) -> AnalysisResult:
    declarations = tuple(_declaration(item) for item in objects)
    return _analyze_batch(
        DeclarationBatch(declarations, ()),
        reported_findings,
        config=config if config is not None else embedded_defaults(),
    )
