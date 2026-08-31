from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Literal, Mapping

from .oslc_reconcile import (
    ExternalRequirementObservation,
    ReconciliationPlan,
)
from .snapshot import AnalysisSnapshot, freeze_json, thaw_json

ImportDirectiveAction = Literal["ignore", "update", "create"]
ImportDisposition = Literal[
    "ignored",
    "review-required",
    "ready-create",
    "ready-update",
    "no-change",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class ImportDirective:
    """Explicit reviewer intent for one external resource.

    Nothing in reconciliation implicitly creates or updates authored content.
    A create directive therefore carries all minimum canonical identity and
    authored-file placement information rather than deriving it from a remote
    identifier or provider-specific display fields.
    """

    action: ImportDirectiveAction
    canonical_id: str | None = None
    canonical_type: str | None = None
    canonical_status: str | None = None
    target_path: str | None = None

    def __post_init__(self) -> None:
        if self.action not in {"ignore", "update", "create"}:
            raise ValueError(f"unsupported import directive action: {self.action}")
        if self.action == "ignore":
            if any(
                value is not None
                for value in (
                    self.canonical_id,
                    self.canonical_type,
                    self.canonical_status,
                    self.target_path,
                )
            ):
                raise ValueError("ignore directives must not carry target metadata")
            return
        if self.action == "update":
            if any(
                value is not None
                for value in (self.canonical_id, self.canonical_type, self.canonical_status)
            ):
                raise ValueError(
                    "update identity/type/status comes from the reconciled canonical object"
                )
            _validate_target_path(self.target_path)
            return

        for value, field in (
            (self.canonical_id, "canonical_id"),
            (self.canonical_type, "canonical_type"),
            (self.canonical_status, "canonical_status"),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"create directive {field} must be a non-empty string")
        _validate_target_path(self.target_path)


@dataclass(frozen=True, slots=True)
class ImportPlanItem:
    external_uri: str
    disposition: ImportDisposition
    canonical_id: str | None
    canonical_type: str | None
    canonical_status: str | None
    target_path: str | None
    source_digest: str
    fetched_at: str
    changes: Mapping[str, Mapping[str, object]] = MappingProxyType({})
    message: str = ""

    def __post_init__(self) -> None:
        frozen = freeze_json(
            {
                key: dict(value)
                for key, value in sorted(self.changes.items())
            }
        )
        if not isinstance(frozen, Mapping):
            raise TypeError("changes must be a JSON object")
        object.__setattr__(self, "changes", frozen)

    def to_dict(self) -> dict[str, object]:
        return {
            "externalUri": self.external_uri,
            "disposition": self.disposition,
            "canonicalId": self.canonical_id,
            "canonicalType": self.canonical_type,
            "canonicalStatus": self.canonical_status,
            "targetPath": self.target_path,
            "sourceDigest": self.source_digest,
            "fetchedAt": self.fetched_at,
            "changes": thaw_json(self.changes),
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class OslcImportPlan:
    semantic_graph_fingerprint: str
    items: tuple[ImportPlanItem, ...]

    @property
    def has_blocked(self) -> bool:
        return any(item.disposition == "blocked" for item in self.items)

    @property
    def requires_review(self) -> bool:
        return any(item.disposition == "review-required" for item in self.items)

    @property
    def ready_count(self) -> int:
        return sum(
            item.disposition in {"ready-create", "ready-update"}
            for item in self.items
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "oslc-import-plan-v1",
            "semanticGraphFingerprint": self.semantic_graph_fingerprint,
            "hasBlocked": self.has_blocked,
            "requiresReview": self.requires_review,
            "readyCount": self.ready_count,
            "items": [item.to_dict() for item in self.items],
        }


def _validate_target_path(value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("target_path must be a non-empty project-relative path")
    normalized = value.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or normalized.startswith("./"):
        raise ValueError("target_path must be a normalized project-relative path")
    if path.suffix not in {".qmd", ".md"}:
        raise ValueError("target_path must identify an authored .qmd or .md file")
    return normalized


def _observation_index(
    observations: tuple[ExternalRequirementObservation, ...],
) -> dict[str, ExternalRequirementObservation]:
    index: dict[str, ExternalRequirementObservation] = {}
    for observation in observations:
        uri = observation.identity.resource_uri
        if uri in index:
            raise ValueError(f"duplicate external requirement URI: {uri}")
        index[uri] = observation
    return index


def _create_changes(
    observation: ExternalRequirementObservation,
    directive: ImportDirective,
) -> Mapping[str, Mapping[str, object]]:
    assert directive.canonical_id is not None
    assert directive.canonical_type is not None
    assert directive.canonical_status is not None
    return {
        "id": {"from": None, "to": directive.canonical_id},
        "type": {"from": None, "to": directive.canonical_type},
        "status": {"from": None, "to": directive.canonical_status},
        "title": {"from": None, "to": observation.title},
        "body": {"from": None, "to": observation.description},
    }


def _update_changes(item) -> Mapping[str, Mapping[str, object]]:  # type: ignore[no-untyped-def]
    changes: dict[str, Mapping[str, object]] = {}
    for field in ("title", "body"):
        difference = item.differences.get(field)
        if difference is None:
            continue
        changes[field] = {
            "from": difference.get("local"),
            "to": difference.get("external"),
        }
    return changes


def build_oslc_import_plan(
    snapshot: AnalysisSnapshot,
    observations: tuple[ExternalRequirementObservation, ...],
    reconciliation: ReconciliationPlan,
    *,
    directives: Mapping[str, ImportDirective],
) -> OslcImportPlan:
    """Build a review artifact without writing files or mutating the snapshot.

    Reconciliation supplies identity/conflict facts; directives supply reviewer
    intent. An unbound observation remains review-required unless an explicit
    create directive supplies a new canonical identity, type, status, and target
    authored file. A matched observation is never updated unless an explicit
    update directive supplies its authored-file placement.
    """
    by_uri = _observation_index(observations)
    reconciliation_by_uri = {item.external_uri: item for item in reconciliation.items}
    if set(reconciliation_by_uri) != set(by_uri):
        raise ValueError(
            "reconciliation items must correspond exactly to supplied observations"
        )
    unknown_directives = sorted(set(directives) - set(by_uri))
    if unknown_directives:
        raise ValueError(
            "directives reference unobserved external URIs: "
            + ", ".join(unknown_directives)
        )

    planned: list[ImportPlanItem] = []
    for uri in sorted(by_uri):
        observation = by_uri[uri]
        reconciled = reconciliation_by_uri[uri]
        directive = directives.get(uri)
        identity = observation.identity
        common = {
            "external_uri": uri,
            "source_digest": identity.digest,
            "fetched_at": identity.fetched_at,
        }

        if reconciled.status in {
            "missing-local",
            "duplicate-local-binding",
            "rejected-external",
            "stale-external",
        }:
            planned.append(
                ImportPlanItem(
                    **common,
                    disposition="blocked",
                    canonical_id=reconciled.canonical_id,
                    canonical_type=None,
                    canonical_status=None,
                    target_path=None,
                    message=(
                        "reconciliation conflict/trust state blocks import planning: "
                        + reconciled.status
                    ),
                )
            )
            continue

        if directive is None:
            planned.append(
                ImportPlanItem(
                    **common,
                    disposition="review-required",
                    canonical_id=reconciled.canonical_id,
                    canonical_type=None,
                    canonical_status=None,
                    target_path=None,
                    message="no explicit reviewer import directive exists",
                )
            )
            continue

        if directive.action == "ignore":
            planned.append(
                ImportPlanItem(
                    **common,
                    disposition="ignored",
                    canonical_id=reconciled.canonical_id,
                    canonical_type=None,
                    canonical_status=None,
                    target_path=None,
                    message="reviewer explicitly ignored this external observation",
                )
            )
            continue

        if directive.action == "create":
            if reconciled.status != "unbound":
                planned.append(
                    ImportPlanItem(
                        **common,
                        disposition="blocked",
                        canonical_id=directive.canonical_id,
                        canonical_type=directive.canonical_type,
                        canonical_status=directive.canonical_status,
                        target_path=directive.target_path,
                        message="create is allowed only for an explicitly unbound observation",
                    )
                )
                continue
            assert directive.canonical_id is not None
            if directive.canonical_id in snapshot.objects_by_id:
                planned.append(
                    ImportPlanItem(
                        **common,
                        disposition="blocked",
                        canonical_id=directive.canonical_id,
                        canonical_type=directive.canonical_type,
                        canonical_status=directive.canonical_status,
                        target_path=directive.target_path,
                        message="create target canonical ID already exists",
                    )
                )
                continue
            planned.append(
                ImportPlanItem(
                    **common,
                    disposition="ready-create",
                    canonical_id=directive.canonical_id,
                    canonical_type=directive.canonical_type,
                    canonical_status=directive.canonical_status,
                    target_path=directive.target_path,
                    changes=_create_changes(observation, directive),
                    message="explicit reviewer directive is ready for a future apply step",
                )
            )
            continue

        # update
        if reconciled.status != "matched" or reconciled.canonical_id is None:
            planned.append(
                ImportPlanItem(
                    **common,
                    disposition="blocked",
                    canonical_id=reconciled.canonical_id,
                    canonical_type=None,
                    canonical_status=None,
                    target_path=directive.target_path,
                    message="update requires an explicitly matched reconciliation item",
                )
            )
            continue
        local = snapshot.objects_by_id.get(reconciled.canonical_id)
        if local is None:
            raise ValueError(
                "matched reconciliation item references a missing canonical object"
            )
        changes = _update_changes(reconciled)
        planned.append(
            ImportPlanItem(
                **common,
                disposition="ready-update" if changes else "no-change",
                canonical_id=local.id,
                canonical_type=local.type,
                canonical_status=local.status,
                target_path=directive.target_path,
                changes=changes,
                message=(
                    "explicit reviewer directive is ready for a future apply step"
                    if changes
                    else "external title/body already match the canonical object"
                ),
            )
        )

    return OslcImportPlan(
        semantic_graph_fingerprint=snapshot.semantic_graph_fingerprint,
        items=tuple(planned),
    )
