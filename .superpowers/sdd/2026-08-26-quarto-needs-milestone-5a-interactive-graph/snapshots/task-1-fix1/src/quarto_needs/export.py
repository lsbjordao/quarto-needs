from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import cast

from .analysis import analyze_objects, legacy_coverage
from .model import EngineeringObject
from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord, thaw_json
from .validation import Finding


_INVALID_GRAPH_ERROR = "Cannot export a structurally invalid requirements graph"


def _legacy_coverage_fallback(
    objects: list[EngineeringObject],
) -> dict[str, object]:
    requirements = [item for item in objects if item.type.endswith("requirement")]
    implemented = [
        item
        for item in requirements
        if any(
            relation.type in {"implements", "implemented-by"}
            for relation in item.relations
        )
    ]
    verified = [
        item
        for item in requirements
        if any(
            relation.type in {"verified-by", "validated-by"}
            for relation in item.relations
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


def coverage(objects: list[EngineeringObject]) -> dict[str, object]:
    result = analyze_objects(objects)
    if result.snapshot is None:
        return _legacy_coverage_fallback(objects)
    return cast(
        dict[str, object],
        thaw_json(legacy_coverage(result.snapshot.objects, result.snapshot.relations)),
    )


def _relation_v1(item: RelationRecord) -> dict[str, object]:
    return {
        "type": item.v1_name,
        "source": item.source,
        "target": item.target,
        "attributes": thaw_json(item.attributes),
    }


def _object_v1(
    item: ObjectRecord,
    outgoing: tuple[RelationRecord, ...],
) -> dict[str, object]:
    source = item.locations[0] if item.locations else None
    href = (
        f"{Path(source.file).with_suffix('').as_posix()}.html#"
        f"{source.anchor or item.id}"
        if source
        else f"#{item.id}"
    )
    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "status": item.status,
        "body": item.body,
        "rationale": item.rationale,
        "attributes": thaw_json(item.attributes),
        "relations": [_relation_v1(relation) for relation in outgoing],
        "source": (
            {
                "file": source.file,
                "line": source.line,
                "anchor": source.anchor,
            }
            if source
            else None
        ),
        "href": href,
    }


def _relation_metadata(item: RelationRecord) -> dict[str, object]:
    kind = DEFAULT_RELATION_CATALOG.resolve(item.authored_name)
    return {
        "directLabel": kind.direct_label,
        "inverseLabel": kind.inverse_label,
        "semanticFamily": kind.semantic_family,
        "sourceRole": kind.source_role,
        "targetRole": kind.target_role,
        "impactDirection": kind.impact_direction,
        "public": kind.public,
    }


def _project_relation_catalog(
    relations: tuple[RelationRecord, ...],
) -> dict[str, object]:
    metadata_by_name: dict[str, dict[str, object]] = {}
    for relation in relations:
        metadata = _relation_metadata(relation)
        previous = metadata_by_name.get(relation.v1_name)
        if previous is not None and previous != metadata:
            raise ValueError(
                "Conflicting relation aliases for v1 name " f"{relation.v1_name}"
            )
        metadata_by_name[relation.v1_name] = metadata
    return {name: metadata_by_name[name] for name in sorted(metadata_by_name)}


def build_v1_payload(
    snapshot: AnalysisSnapshot,
    *,
    extra_extensions: dict[str, object] | None = None,
) -> dict[str, object]:
    objects: list[dict[str, object]] = []
    relations: list[dict[str, object]] = []
    for item in snapshot.objects:
        projected = _object_v1(item, snapshot.outgoing[item.id])
        objects.append(projected)
        relations.extend(cast(list[dict[str, object]], projected["relations"]))

    backlinks = {
        item.id: [
            {"source": relation.source, "type": relation.v1_name}
            for relation in sorted(
                snapshot.incoming[item.id],
                key=lambda relation: (
                    relation.source.casefold(),
                    relation.source,
                    relation.v1_name,
                ),
            )
        ]
        for item in snapshot.objects
    }
    return {
        "schemaVersion": "1",
        "objects": objects,
        "relations": relations,
        "coverage": thaw_json(snapshot.metrics),
        "validation": [finding.to_dict() for finding in snapshot.findings],
        "backlinks": backlinks,
        "extensions": _merged_extensions(snapshot, extra_extensions),
    }


def _merged_extensions(
    snapshot: AnalysisSnapshot,
    extra_extensions: dict[str, object] | None,
) -> dict[str, object]:
    extensions: dict[str, object] = {
        "quartoNeeds": {
            "generator": {
                "name": snapshot.generator_name,
                "version": snapshot.generator_version,
            },
            "relationCatalogVersion": snapshot.relation_catalog_version,
            "relationCatalog": _project_relation_catalog(snapshot.relations),
        }
    }
    if not extra_extensions:
        return extensions
    for namespace, additions in extra_extensions.items():
        if namespace not in extensions:
            extensions[namespace] = additions
            continue
        current = extensions[namespace]
        if not isinstance(current, dict) or not isinstance(additions, dict):
            raise ValueError(
                f"Cannot merge extension namespace {namespace}: conflicting types"
            )
        merged = dict(current)
        for key, value in additions.items():
            if key in merged and merged[key] != value:
                raise ValueError(
                    f"Cannot overwrite reserved extension key {namespace}.{key}"
                )
            merged[key] = value
        extensions[namespace] = merged
    return extensions


def render_v1_json(
    snapshot: AnalysisSnapshot,
    *,
    extra_extensions: dict[str, object] | None = None,
) -> str:
    return json.dumps(
        build_v1_payload(snapshot, extra_extensions=extra_extensions),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _lua_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )


def render_lua_index(snapshot: AnalysisSnapshot) -> str:
    lines = ["return {"]
    for item in snapshot.objects:
        source = item.locations[0] if item.locations else None
        href = (
            f"{Path(source.file).with_suffix('').as_posix()}.html#"
            f"{source.anchor or item.id}"
            if source
            else f"#{item.id}"
        )
        lines.append(
            f'  ["{_lua_escape(item.id)}"] = '
            f'{{ title = "{_lua_escape(item.title)}", '
            f'href = "{_lua_escape(href)}", '
            f'type = "{_lua_escape(item.type)}", '
            f'status = "{_lua_escape(item.status)}" }},'
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def _write_atomic_text(path: Path, contents: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_v1_graph(
    path: Path,
    snapshot: AnalysisSnapshot,
    *,
    extra_extensions: dict[str, object] | None = None,
) -> None:
    _write_atomic_text(path, render_v1_json(snapshot, extra_extensions=extra_extensions))


def write_lua_index(path: Path, snapshot: AnalysisSnapshot) -> None:
    _write_atomic_text(path, render_lua_index(snapshot))


def write_build_outputs(
    graph_path: Path,
    index_path: Path,
    snapshot: AnalysisSnapshot,
    *,
    extra_extensions: dict[str, object] | None = None,
) -> None:
    graph = render_v1_json(snapshot, extra_extensions=extra_extensions)
    index = render_lua_index(snapshot)
    _write_atomic_text(graph_path, graph)
    _write_atomic_text(index_path, index)


def export_graph(
    path: Path,
    objects: list[EngineeringObject],
    findings: list[Finding],
) -> None:
    result = analyze_objects(objects, reported_findings=findings)
    if result.snapshot is None:
        raise ValueError(_INVALID_GRAPH_ERROR)
    write_v1_graph(path, result.snapshot)


def export_lua_index(path: Path, objects: list[EngineeringObject]) -> None:
    result = analyze_objects(objects)
    if result.snapshot is None:
        raise ValueError(_INVALID_GRAPH_ERROR)
    write_lua_index(path, result.snapshot)
