"""Deterministic interchange-loss documentation for the read-only projections.

ReqIF and JSON-LD are projections of the canonical graph, not round-trip
copies. Details the target format cannot represent are authored, analyzed,
and then dropped at the export boundary; pretending otherwise would make a
consumer believe the export carried information it did not. This module is
the single source of truth for *which* authored details stay behind, so the
ReqIF and JSON-LD exporters document exactly the same loss.

The returned notes are human-readable and intentionally deterministic: the
same graph always produces the same documentation, so two team members
exporting the same project agree on what a downstream ReqIF or RDF consumer
will and will not receive.
"""

from __future__ import annotations

from ..snapshot import AnalysisSnapshot


def _location_text(location) -> str:
    return f"{location.file}:{location.line}"


def projection_loss_notes(snapshot: AnalysisSnapshot) -> tuple[str, ...]:
    """Loss shared by every projection: source provenance and relation data."""
    notes: list[str] = []

    objects = sorted(snapshot.objects, key=lambda item: (item.id.casefold(), item.id))
    located_objects = [item for item in objects if item.locations]
    if located_objects:
        detail = ", ".join(
            f"{item.id} ({_location_text(item.locations[0])})"
            for item in located_objects
        )
        notes.append(f"object source locations stay behind: {detail}")

    relations = sorted(
        snapshot.relations,
        key=lambda item: (
            item.source.casefold(),
            item.source,
            item.catalog_name.casefold(),
            item.catalog_name,
            item.target.casefold(),
            item.target,
        ),
    )
    located_relations = [item for item in relations if item.provenance]
    if located_relations:
        detail = ", ".join(
            f"{item.source} --{item.catalog_name}--> {item.target} "
            f"({_location_text(item.provenance[0])})"
            for item in located_relations
        )
        notes.append(f"relation source locations stay behind: {detail}")

    attributed_relations = [
        (item.source, item.catalog_name, item.target, key)
        for item in relations
        for key in sorted(item.attributes)
    ]
    if attributed_relations:
        detail = ", ".join(
            f"{source} --{catalog}--> {target} .{key}"
            for source, catalog, target, key in attributed_relations
        )
        notes.append(f"relation attributes stay behind: {detail}")

    return tuple(notes)


def reqif_flattening_note(snapshot: AnalysisSnapshot) -> str | None:
    """Loss specific to the ReqIF projection: only STRING cells are declared.

    Every authored attribute is carried as text inside the single
    ``attributes-json`` STRING cell. Values that were hashes or other
    structured data when authored survive as JSON text; the ReqIF consumer
    sees a string, not the typed value. Returned as a single documented note
    naming exactly which attribute that happened to, or ``None`` when every
    attribute value in the graph already is a plain string.
    """
    flattened = sorted(
        {
            (item.id, key)
            for item in snapshot.objects
            for key, value in item.attributes.items()
            if not isinstance(value, str)
        },
        key=lambda pair: (pair[0].casefold(), pair[0], pair[1].casefold(), pair[1]),
    )
    if not flattened:
        return None
    detail = ", ".join(f"{object_id}.{key}" for object_id, key in flattened)
    return f"attribute values flatten to ReqIF string cells: {detail}"