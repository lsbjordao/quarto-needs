"""Editor/language features over the canonical Quarto-Needs analysis result.

This module intentionally contains no LSP transport code. It is the reusable
semantic layer for CLI/editor integrations and consumes the same parser,
configuration, relation catalog, findings, and snapshot as every other client.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .analysis import analyze_project
from .config import NeedsConfig, load_config
from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot, LocationRecord, ObjectRecord


class LanguageServiceError(ValueError):
    """The project cannot provide a valid language-service snapshot."""


@dataclass(frozen=True, slots=True)
class CompletionItem:
    label: str
    kind: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class HoverInfo:
    object_id: str
    title: str
    type: str
    status: str
    role: str | None
    priority: str | None
    derived: Mapping[str, object]
    outgoing: int
    incoming: int


@dataclass(frozen=True, slots=True)
class ReferenceInfo:
    object_id: str
    relation: str
    direction: str
    peer_id: str
    location: LocationRecord | None


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    object_id: str
    title: str
    type: str
    status: str
    location: LocationRecord | None


@dataclass(frozen=True, slots=True)
class DiagnosticInfo:
    code: str
    severity: str
    message: str
    object_id: str | None
    location: LocationRecord | None


class LanguageService:
    """Canonical semantic services for editors and future protocol adapters."""

    def __init__(self, root: Path, config: NeedsConfig, snapshot: AnalysisSnapshot):
        self.root = root.resolve()
        self.config = config
        self.snapshot = snapshot

    @classmethod
    def load(
        cls,
        root: Path,
        *,
        overlays: Mapping[str, str] | None = None,
    ) -> "LanguageService":
        resolved = Path(root).resolve()
        config = load_config(resolved)
        result = analyze_project(resolved, config=config, overlays=overlays)
        if result.snapshot is None:
            structural = "; ".join(
                f"{finding.code}: {finding.message}" for finding in result.findings
            )
            raise LanguageServiceError(
                structural or "project analysis is structurally invalid"
            )
        return cls(resolved, config, result.snapshot)

    def _role(self, record: ObjectRecord) -> str | None:
        configured = self.config.type_roles.get(record.type)
        if configured is not None:
            return configured
        if record.type.endswith("requirement"):
            return "requirement"
        return None

    def diagnostics(self, *, file: str | None = None) -> tuple[DiagnosticInfo, ...]:
        values: list[DiagnosticInfo] = []
        for finding in self.snapshot.findings:
            if file is not None and (
                finding.location is None or finding.location.file != file
            ):
                continue
            values.append(
                DiagnosticInfo(
                    finding.code,
                    finding.severity,
                    finding.message,
                    finding.object_id,
                    finding.location,
                )
            )
        return tuple(values)

    def completions(self, prefix: str = "") -> tuple[CompletionItem, ...]:
        folded = prefix.casefold()
        items: list[CompletionItem] = []
        for record in self.snapshot.objects:
            if not folded or record.id.casefold().startswith(folded):
                items.append(
                    CompletionItem(
                        record.id, "object", f"{record.type} · {record.title}"
                    )
                )
        for name in sorted(
            set(self.config.required_attributes)
            | set(self.config.type_roles)
            | set(self.config.allowed_statuses)
        ):
            if not folded or name.casefold().startswith(folded):
                items.append(
                    CompletionItem(name, "type", self.config.type_roles.get(name, ""))
                )
        for relation in DEFAULT_RELATION_CATALOG.names:
            if not folded or relation.casefold().startswith(folded):
                kind = DEFAULT_RELATION_CATALOG.resolve(relation)
                items.append(
                    CompletionItem(
                        relation,
                        "relation",
                        f"{kind.semantic_family}: {kind.source_role} → {kind.target_role}",
                    )
                )
        statuses = sorted(
            {status for values in self.config.allowed_statuses.values() for status in values}
        )
        for status in statuses:
            if not folded or status.casefold().startswith(folded):
                items.append(CompletionItem(status, "status"))
        items.sort(key=lambda item: (item.label.casefold(), item.label, item.kind))
        return tuple(items)

    def hover(self, object_id: str) -> HoverInfo | None:
        record = self.snapshot.objects_by_id.get(object_id)
        if record is None:
            return None
        return HoverInfo(
            object_id=record.id,
            title=record.title,
            type=record.type,
            status=record.status,
            role=self._role(record),
            priority=record.priority,
            derived=self.snapshot.derived.get(record.id, {}),
            outgoing=len(self.snapshot.outgoing.get(record.id, ())),
            incoming=len(self.snapshot.incoming.get(record.id, ())),
        )

    def definition(self, object_id: str) -> LocationRecord | None:
        record = self.snapshot.objects_by_id.get(object_id)
        if record is None or not record.locations:
            return None
        return record.locations[0]

    def references(self, object_id: str) -> tuple[ReferenceInfo, ...]:
        refs: list[ReferenceInfo] = []
        for edge in self.snapshot.outgoing.get(object_id, ()):
            refs.append(
                ReferenceInfo(
                    object_id,
                    edge.v1_name,
                    "outgoing",
                    edge.target,
                    edge.provenance[0] if edge.provenance else None,
                )
            )
        for edge in self.snapshot.incoming.get(object_id, ()):
            refs.append(
                ReferenceInfo(
                    object_id,
                    edge.v1_name,
                    "incoming",
                    edge.source,
                    edge.provenance[0] if edge.provenance else None,
                )
            )
        refs.sort(
            key=lambda ref: (
                ref.direction,
                ref.relation,
                ref.peer_id.casefold(),
                ref.peer_id,
            )
        )
        return tuple(refs)

    def symbols(self, *, file: str | None = None) -> tuple[SymbolInfo, ...]:
        symbols = []
        for record in self.snapshot.objects:
            location = record.locations[0] if record.locations else None
            if file is not None and (location is None or location.file != file):
                continue
            symbols.append(
                SymbolInfo(record.id, record.title, record.type, record.status, location)
            )
        return tuple(symbols)
