"""Structural validation of a projected C4 view, before any renderer sees it.

These checks are about the *projection*, not about the authored graph: layer
adjacency is already a graph rule (`rules.py`'s ARC001), and this module
deliberately does not duplicate it. What it catches is a view that would send
a renderer something incoherent -- a boundary with no parent, a dangling
relationship, a nested element in a context diagram (Spec 29).

Every diagnostic names canonical Quarto-Needs object IDs, never renderer-side
sanitized identifiers, so a reader can find the `.need` block that caused it.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import CONTAINMENT_ROLES, C4View


@dataclass(frozen=True, slots=True)
class C4Diagnostic:
    code: str
    severity: str
    message: str
    object_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "objectId": self.object_id,
        }


def _containment_cycles(view: C4View) -> list[tuple[str, ...]]:
    parents = {
        element.id: element.parent_id
        for element in view.elements
        if element.parent_id is not None
    }
    cycles: list[tuple[str, ...]] = []
    seen: set[str] = set()
    for start in sorted(parents):
        if start in seen:
            continue
        path: list[str] = []
        node: str | None = start
        while node is not None and node not in path:
            path.append(node)
            node = parents.get(node)
        if node is not None:
            cycle = tuple(path[path.index(node):]) + (node,)
            if cycle not in cycles:
                cycles.append(cycle)
        seen.update(path)
    return cycles


def validate_c4_view(view: C4View) -> tuple[C4Diagnostic, ...]:
    """Every structural problem in `view`, sorted deterministically."""
    found: list[C4Diagnostic] = []
    known = {element.id for element in view.elements}

    counts: dict[str, int] = {}
    for element in view.elements:
        counts[element.id] = counts.get(element.id, 0) + 1
    for identifier in sorted(item for item, count in counts.items() if count > 1):
        found.append(
            C4Diagnostic(
                "C4007",
                "error",
                f"{identifier} appears more than once in C4 view {view.id}",
                identifier,
            )
        )

    for element in view.elements:
        if element.id == view.scope_id:
            # The scope is the view's root: its own parent is one level up
            # and deliberately outside this view.
            continue
        if element.role in CONTAINMENT_ROLES and element.parent_id is None:
            found.append(
                C4Diagnostic(
                    "C4001",
                    "error",
                    f"{element.id} ({element.role.value}) has no parent in C4 "
                    f"view {view.id}: every container, component and code "
                    "element must sit inside the layer above it",
                    element.id,
                )
            )
        elif element.parent_id is not None and element.parent_id not in known:
            found.append(
                C4Diagnostic(
                    "C4002",
                    "error",
                    f"{element.id} references unknown parent "
                    f"{element.parent_id} in C4 view {view.id}",
                    element.id,
                )
            )

    for cycle in _containment_cycles(view):
        found.append(
            C4Diagnostic(
                "C4003",
                "error",
                "Containment cycle detected: " + " -> ".join(cycle),
                cycle[0],
            )
        )

    for relationship in view.relationships:
        for endpoint in (relationship.source_id, relationship.target_id):
            if endpoint not in known:
                found.append(
                    C4Diagnostic(
                        "C4006",
                        "error",
                        f"Relationship {relationship.id} references unknown "
                        f"element {endpoint} in C4 view {view.id}",
                        endpoint,
                    )
                )

    if view.level == "system-context":
        for element in view.elements:
            if element.role in CONTAINMENT_ROLES:
                found.append(
                    C4Diagnostic(
                        "C4009",
                        "error",
                        f"{element.id} ({element.role.value}) may not appear in "
                        f"system-context view {view.id}: a context diagram shows "
                        "the system as an opaque box",
                        element.id,
                    )
                )

    return tuple(sorted(found, key=lambda item: (item.code, item.object_id or "")))
