"""The renderer-independent C4 intermediate representation.

Nothing here knows what Mermaid, Structurizr, PlantUML or D2 are. The types
in this module are the formal boundary between "Quarto-Needs understands
architecture" and "some library draws architecture" (Spec 6, 7).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class C4ElementRole(Enum):
    """What an element *is* in C4 terms, independent of any renderer."""

    PERSON = "person"
    SOFTWARE_SYSTEM = "software-system"
    EXTERNAL_SYSTEM = "external-system"
    CONTAINER = "container"
    COMPONENT = "component"
    CODE = "code"


# The one and only object-type to C4-role mapping. Explicit and canonical:
# never inferred from a title, tag, colour or naming convention (Spec 45).
# The four containment types mirror rules.py's _C4_LAYER_ORDER, which the
# ARC001 structural rule already enforces adjacency over.
C4_ROLE_BY_TYPE: Mapping[str, C4ElementRole] = {
    "actor": C4ElementRole.PERSON,
    "external-system": C4ElementRole.EXTERNAL_SYSTEM,
    "system": C4ElementRole.SOFTWARE_SYSTEM,
    "container": C4ElementRole.CONTAINER,
    "component": C4ElementRole.COMPONENT,
    "source-module": C4ElementRole.CODE,
}

# Roles that must sit inside a parent: _C4_LAYER_ORDER minus its root, which
# by definition has none. People and external systems live outside the
# containment hierarchy entirely (Spec 5).
CONTAINMENT_ROLES = (
    C4ElementRole.CONTAINER,
    C4ElementRole.COMPONENT,
    C4ElementRole.CODE,
)

LEVELS = ("system-context", "container", "component", "code")

# `context` was this project's own spelling before the spec settled on
# `system-context`; it stays accepted everywhere so existing documents and
# tests keep working (Spec 43). Public because the generated artifact
# manifest publishes it verbatim: that is what lets the Lua shortcode
# resolve an alias by lookup rather than by carrying a rule of its own.
LEVEL_ALIASES: Mapping[str, str] = {"context": "system-context"}


def normalize_level(level: str) -> str | None:
    """The canonical level name, or None when `level` is not a C4 level."""
    candidate = LEVEL_ALIASES.get(level, level)
    return candidate if candidate in LEVELS else None


class LayoutDirection(Enum):
    """A presentation hint, deliberately *not* part of the IR (Spec 32).

    Lives here so every renderer names the same four directions, but it is
    carried on `C4RenderOptions`, never on a `C4View`: layout orientation is
    not semantic edge direction (Spec 31), and keeping it out of the IR is
    what makes "renderer options cannot change the view fingerprint" true by
    construction rather than by discipline.
    """

    TOP_BOTTOM = "top-bottom"
    BOTTOM_TOP = "bottom-top"
    LEFT_RIGHT = "left-right"
    RIGHT_LEFT = "right-left"


@dataclass(frozen=True, slots=True)
class C4Element:
    id: str
    role: C4ElementRole
    name: str
    description: str | None = None
    technology: str | None = None
    parent_id: str | None = None
    external: bool = False
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "role": self.role.value,
            "name": self.name,
            "description": self.description,
            "technology": self.technology,
            "parentId": self.parent_id,
            "external": self.external,
            "tags": list(self.tags),
        }


@dataclass(frozen=True, slots=True)
class C4Relationship:
    id: str
    source_id: str
    target_id: str
    relation_type: str
    description: str | None = None
    technology: str | None = None
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "sourceId": self.source_id,
            "targetId": self.target_id,
            "relationType": self.relation_type,
            "description": self.description,
            "technology": self.technology,
            "tags": list(self.tags),
        }


def relationship_id(source_id: str, target_id: str, relation_type: str) -> str:
    """A deterministic relationship identity. Never a counter, never random."""
    return f"{relation_type}:{source_id}:{target_id}"


@dataclass(frozen=True, slots=True)
class C4View:
    id: str
    level: str
    scope_id: str | None
    elements: tuple[C4Element, ...]
    relationships: tuple[C4Relationship, ...]

    @property
    def scope(self) -> C4Element | None:
        return self.element(self.scope_id) if self.scope_id is not None else None

    def element(self, identifier: str | None) -> C4Element | None:
        if identifier is None:
            return None
        for element in self.elements:
            if element.id == identifier:
                return element
        return None

    def children_of(self, parent_id: str) -> tuple[C4Element, ...]:
        """Direct children, in the view's own (already deterministic) order."""
        return tuple(
            element for element in self.elements if element.parent_id == parent_id
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "level": self.level,
            "scopeId": self.scope_id,
            "elements": [element.to_dict() for element in self.elements],
            "relationships": [item.to_dict() for item in self.relationships],
        }


_UNSAFE_IDENTIFIER_CHARACTER = re.compile(r"[^A-Za-z0-9_]")


def sanitize_identifier(identifier: str) -> str:
    """A readable, syntactically safe token derived from a canonical ID.

    Deterministic by construction -- the same input always yields the same
    output, and no counter or random value is involved (Spec 28). The
    transform is lossy, so callers that need uniqueness must go through
    `identifier_map`, not this function directly.
    """
    cleaned = _UNSAFE_IDENTIFIER_CHARACTER.sub("_", identifier)
    if not cleaned or not (cleaned[0].isalpha() or cleaned[0] == "_"):
        cleaned = "c4_" + cleaned
    return cleaned


def identifier_map(view: C4View) -> dict[str, str]:
    """Canonical ID -> renderer-safe identifier for one view, collision-free.

    `A-B` and `A.B` both sanitize to `A_B`. Suffixing only the second one
    encountered would make the output depend on element order; every member
    of a colliding group is suffixed with a stable digest of its own ID
    instead, so the result is permutation-independent (Spec 27, 28).
    """
    grouped: dict[str, list[str]] = {}
    for element in view.elements:
        grouped.setdefault(sanitize_identifier(element.id), []).append(element.id)
    mapping: dict[str, str] = {}
    for safe, canonical_ids in grouped.items():
        if len(canonical_ids) == 1:
            mapping[canonical_ids[0]] = safe
            continue
        for canonical in canonical_ids:
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
            mapping[canonical] = f"{safe}_{digest}"
    return mapping
