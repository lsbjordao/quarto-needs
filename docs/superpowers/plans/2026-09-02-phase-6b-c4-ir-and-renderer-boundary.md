# Phase 6b — C4 Renderer-Independent IR and Renderer Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert a formal, versioned, renderer-independent C4 intermediate representation (`quarto-needs-c4-view-v1`) between the canonical engineering graph and every diagram renderer, then re-found the existing Mermaid C4 output on top of it — so that adding Structurizr/PlantUML/D2 later (Plan B) is purely an adapter change with zero semantic consequence.

**Architecture:** A new `src/quarto_needs/c4/` package owns the whole C4 semantic layer. `projection.py` turns an `AnalysisSnapshot` into an immutable `C4View` (typed roles, resolved parent/child hierarchy, selected relationships) — this is the *only* place C4 semantics live. `validation.py` checks that view against the C4 structural contract and returns `C4Diagnostic` values. `serialize.py` emits the versioned JSON that is the formal renderer boundary, plus a sha256 fingerprint of it. `renderers/base.py` defines the `C4Renderer` protocol, `C4RenderOptions`, `C4RenderResult`, and `RendererCapabilities`; `renderers/__init__.py` is an extensible registry. `renderers/mermaid.py` is the first adapter and receives **only** a `C4View` — never a snapshot, never a `GraphProjection`. `artifacts.py` writes the deterministic `.quarto-needs/c4/<level>/<scope-id>/` tree. A new `c4_cli.py` exposes `c4 project` / `c4 render` / `c4 renderers` following the repository's established `<x>_cli.py` + `cli_entry._dispatch` interception pattern. The `need-c4` Lua shortcode stays a pure reader of pre-rendered text — Python remains the sole semantic authority.

**Tech Stack:** Python 3.10+ (stdlib only for all new code — `dataclasses`, `enum`, `hashlib`, `json`, `re`, `argparse`), `jsonschema>=4.23` (already a dependency) for schema tests, TOML project config (`.quarto-needs.toml`, read with `tomllib`), Lua (Quarto/Pandoc filter), Mermaid.js via Quarto's bundled renderer.

**Spec:** `docs/superpowers/specs/2026-09-02-multi-backend-c4-projections.md`

## Global Constraints

- **Python remains the sole semantic authority; Lua only presents.** `c4.lua` must never map a role to a macro, never decide what a boundary is, never interpret a projection. It reads a pre-rendered text artifact and hands it to the existing `views.mermaid_inline_svg` helper. (Spec §2.1, §18; this is the project's binding invariant, restated in `docs/phase-6-architecture-c4.md`.)
- **No second architecture database.** Every C4 concept is derived from the existing typed-object/relation graph. No new object type, no new relation, no new authored syntax is introduced by this plan. (Spec §1, §53.)
- **Renderer configuration is presentation-only and must never enter the canonical fingerprint.** `NeedsConfig.canonical_document()` is a field-by-field allowlist (`config.py:113`), so a new `architecture` field on `NeedsConfig` is excluded by construction — Task 7 pins that with a test. (Spec §17, §27.)
- **The renderer receives only the IR.** No function in `c4/renderers/` may import `snapshot`, `graph_projection`, or `analysis`. Task 5 pins this with an import test.
- **Source generation only.** No adapter runs a subprocess in this plan or in Plan B. `RendererCapabilities.svg` is `False` for every renderer except `mermaid` (whose SVG is produced by Quarto's own bundled Mermaid, not by us). Spec §47's process trust boundary is deliberately not opened here. (Owner decision 2, recorded in the spec.)
- **Determinism is a tested property, not an aspiration.** Every ordering is an explicit sort key. No `set` or `dict` iteration order may reach an output. Byte-identical output for an equivalent snapshot is asserted, not assumed. (Spec §27.)
- **Every commit leaves the full `pytest` suite green.** Run `python -m pytest -q` before each commit. **Do not rely on GitHub Actions** — the project's Actions quota is exhausted; verify everything locally.
- **TDD throughout**, in the project's established rhythm: write the failing test, run it and read the actual failure, write the minimal implementation, run it again, commit. Commit messages follow the repo's `feat:`/`test:`/`docs:`/`refactor:` style.
- **Back-compat, carried across two tasks deliberately.** Task 8 writes the new artifact tree *while still writing the legacy `.quarto-needs/graphs/c4-*.json` files*; Task 10 switches Lua to the new tree; Task 11 deletes the legacy writer and the legacy modules. This ordering is what keeps every intermediate commit green — never collapse Tasks 8/10/11 into one.

## Inherited limitations (carried forward, not regressions)

These are pre-existing and documented in `docs/phase-6-architecture-c4.md`. This plan does **not** fix them and must not silently appear to.

1. **No relation-attribute authoring syntax.** `parser.py` hardcodes `RelationToken(..., {}, ...)` — there is no grammar for `depends-on: TARGET technology="..."`. Therefore `C4Relationship.description` is always the relation catalog's fixed `direct_label` ("Depends on") and `C4Relationship.technology` is always `None`. The IR carries both fields (Spec §7) so a future parser slice fills them without changing the boundary.
2. **Interaction edges reach the scope element only, not its children.** A container-level view shows actors/external systems attached to the system as a whole, never to a specific container. Preserved exactly as-is.
3. **"Exactly one parent" is only half-enforced by config.** REQ010's `maximum-per-source = 1` catches duplicate parents; an object with *zero* parents is invisible to it. Task 2's `C4001` diagnostic closes that gap **at projection time** for elements that appear in a view.

## Deliberate deviations from the spec (decide once here, do not re-litigate per task)

- **§32 layout direction is NOT in the IR.** The spec says the IR "may" carry `preferred_layout_direction`. It does not, here: direction is a renderer option (`C4RenderOptions.direction`). Keeping it out is what makes "changing renderer options cannot change the IR fingerprint" (§17, §27) true by construction rather than by discipline.
- **§7's `include_external` / `max_depth` view metadata are omitted.** No consumer needs them; the level definitions already fix both. YAGNI.
- **`C4Element.description` comes from the object's `description` attribute, never from `body`.** A `.need` block's body is multi-paragraph prose and would wreck every diagram. When there is no `description` attribute the field is `None` — which is exactly today's Mermaid output (no descriptions), so this is not a visual regression.
- **§28's readable identifiers replace today's hex encoding, with explicit collision handling.** `SYS-QUARTO-NEEDS` becomes `SYS_QUARTO_NEEDS`, not `c4_5359532d...`. Because sanitization is lossy (`A-B` and `A.B` both sanitize to `A_B`), Task 1 groups by sanitized form and appends a stable hash suffix to *every* member of a colliding group — never to just the second one seen, which would depend on iteration order.
- **Element ordering is `(id.casefold(), id)`, not authoring order.** Today's Mermaid output follows `snapshot.objects` order. Sorting by id is renderer-independent and permutation-proof (§27). Visual ordering of boxes may therefore differ from the pre-refactor diagrams; that is presentation-only and expected.
- **Level names gain the spec's spelling with the current one as an alias.** Canonical: `system-context`, `container`, `component`, `code`. `context` is accepted everywhere `system-context` is (CLI, shortcode, config) and normalizes to it.
- **§26's `fallback-renderer` is deliberately not implemented, and its config key is deliberately not parsed.** Fallback needs a trigger — "the requested renderer is unavailable" — and in this milestone there is none: every registered backend generates source unconditionally, and `_parse_c4` already rejects an unregistered name at configuration-load time with the list of what is installed. A parsed key that can never fire is worse than an absent one, because it reads as a working feature. This becomes real in the slice that adds binary execution, where `C4004`/`C4005` acquire actual failure modes; Task 12 documents it as deferred rather than leaving it unmentioned.

---

### Task 1: The C4 semantic model — roles, elements, relationships, views, stable identifiers

**Files:**
- Create: `src/quarto_needs/c4/__init__.py`
- Create: `src/quarto_needs/c4/model.py`
- Test: `tests/test_c4_model.py`

**Interfaces:**
- Produces: `C4ElementRole` (enum: `PERSON`, `SOFTWARE_SYSTEM`, `EXTERNAL_SYSTEM`, `CONTAINER`, `COMPONENT`, `CODE`); `C4_ROLE_BY_TYPE: Mapping[str, C4ElementRole]`; `CONTAINMENT_ROLES: tuple[C4ElementRole, ...]`; `LEVELS: tuple[str, ...]`; `normalize_level(level: str) -> str | None`; `LayoutDirection` (enum); the frozen dataclasses `C4Element`, `C4Relationship`, `C4View` (each with `.to_dict() -> dict[str, object]`); `C4View.scope -> C4Element | None`, `C4View.element(identifier: str) -> C4Element | None`, `C4View.children_of(parent_id: str) -> tuple[C4Element, ...]`; `relationship_id(source_id: str, target_id: str, relation_type: str) -> str`; `sanitize_identifier(identifier: str) -> str`; `identifier_map(view: C4View) -> dict[str, str]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_model.py`:

```python
from __future__ import annotations

from quarto_needs.c4.model import (
    CONTAINMENT_ROLES,
    C4_ROLE_BY_TYPE,
    C4Element,
    C4ElementRole,
    C4Relationship,
    C4View,
    LEVEL_ALIASES,
    LEVELS,
    LayoutDirection,
    identifier_map,
    normalize_level,
    relationship_id,
    sanitize_identifier,
)


def _element(identifier: str, role: C4ElementRole, **kwargs) -> C4Element:
    return C4Element(id=identifier, role=role, name=identifier.title(), **kwargs)


def test_every_architecture_object_type_maps_to_exactly_one_role() -> None:
    # The mapping is explicit and canonical -- never inferred from titles,
    # tags or colours (Spec 45). These six types are the architecture types
    # the graph already has; nothing else is a C4 element.
    assert C4_ROLE_BY_TYPE == {
        "actor": C4ElementRole.PERSON,
        "external-system": C4ElementRole.EXTERNAL_SYSTEM,
        "system": C4ElementRole.SOFTWARE_SYSTEM,
        "container": C4ElementRole.CONTAINER,
        "component": C4ElementRole.COMPONENT,
        "source-module": C4ElementRole.CODE,
    }


def test_containment_roles_are_the_layers_below_the_root() -> None:
    assert CONTAINMENT_ROLES == (
        C4ElementRole.CONTAINER,
        C4ElementRole.COMPONENT,
        C4ElementRole.CODE,
    )
    assert C4ElementRole.SOFTWARE_SYSTEM not in CONTAINMENT_ROLES
    assert C4ElementRole.PERSON not in CONTAINMENT_ROLES


def test_levels_and_the_legacy_context_alias() -> None:
    assert LEVELS == ("system-context", "container", "component", "code")
    # Published, not private: the artifact manifest hands this table to Lua
    # so the shortcode resolves an alias by lookup instead of by a rule of
    # its own (Task 8's index.json, Task 10's reader).
    assert LEVEL_ALIASES == {"context": "system-context"}
    assert normalize_level("system-context") == "system-context"
    assert normalize_level("context") == "system-context"
    assert normalize_level("container") == "container"
    assert normalize_level("code") == "code"
    assert normalize_level("deployment") is None
    assert normalize_level("") is None


def test_layout_direction_is_renderer_neutral() -> None:
    assert {member.value for member in LayoutDirection} == {
        "top-bottom", "bottom-top", "left-right", "right-left",
    }


def test_element_to_dict_always_emits_every_declared_key() -> None:
    # Unlike PublicNode's conditional inclusion, the IR emits nulls: this
    # payload is a versioned boundary consumed by four adapters and pinned
    # by goldens, so a stable key set matters more than payload size.
    element = _element("CONTAINER-CORE", C4ElementRole.CONTAINER, technology="Python")
    assert element.to_dict() == {
        "id": "CONTAINER-CORE",
        "role": "container",
        "name": "Container-Core",
        "description": None,
        "technology": "Python",
        "parentId": None,
        "external": False,
        "tags": [],
    }


def test_relationship_to_dict_and_deterministic_id() -> None:
    assert relationship_id("A", "B", "depends-on") == "depends-on:A:B"
    relationship = C4Relationship(
        id=relationship_id("A", "B", "depends-on"),
        source_id="A",
        target_id="B",
        relation_type="depends-on",
        description="Depends on",
    )
    assert relationship.to_dict() == {
        "id": "depends-on:A:B",
        "sourceId": "A",
        "targetId": "B",
        "relationType": "depends-on",
        "description": "Depends on",
        "technology": None,
        "tags": [],
    }


def test_view_lookup_helpers() -> None:
    system = _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM)
    first = _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1")
    second = _element("CONTAINER-B", C4ElementRole.CONTAINER, parent_id="SYS-1")
    outside = _element("ACTOR-1", C4ElementRole.PERSON)
    view = C4View(
        id="container-SYS-1",
        level="container",
        scope_id="SYS-1",
        elements=(first, second, outside, system),
        relationships=(),
    )
    assert view.scope is system
    assert view.element("CONTAINER-B") is second
    assert view.element("NOPE") is None
    assert view.children_of("SYS-1") == (first, second)
    assert view.children_of("CONTAINER-A") == ()


def test_view_scope_is_none_when_the_scope_element_is_absent() -> None:
    view = C4View(id="v", level="container", scope_id="MISSING", elements=(), relationships=())
    assert view.scope is None


def test_sanitize_identifier_is_readable_and_syntactically_safe() -> None:
    assert sanitize_identifier("SYS-QUARTO-NEEDS") == "SYS_QUARTO_NEEDS"
    assert sanitize_identifier("COMP.parser") == "COMP_parser"
    assert sanitize_identifier("already_safe") == "already_safe"
    # A leading digit is invalid in every target DSL's identifier grammar.
    assert sanitize_identifier("1ST") == "c4_1ST"
    assert sanitize_identifier("") == "c4_"


def test_identifier_map_suffixes_every_member_of_a_collision_group() -> None:
    # "A-B" and "A.B" both sanitize to "A_B". Suffixing only the second one
    # seen would make the output depend on element order; both must be
    # suffixed, and the result must be permutation-independent.
    dashed = _element("A-B", C4ElementRole.COMPONENT)
    dotted = _element("A.B", C4ElementRole.COMPONENT)
    lonely = _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM)
    forward = C4View(
        id="v", level="component", scope_id="SYS-1",
        elements=(dashed, dotted, lonely), relationships=(),
    )
    backward = C4View(
        id="v", level="component", scope_id="SYS-1",
        elements=(lonely, dotted, dashed), relationships=(),
    )
    mapping = identifier_map(forward)
    assert identifier_map(backward) == mapping
    assert mapping["SYS-1"] == "SYS_1"
    assert mapping["A-B"].startswith("A_B_")
    assert mapping["A.B"].startswith("A_B_")
    assert mapping["A-B"] != mapping["A.B"]
    assert len(set(mapping.values())) == 3
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_model.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'quarto_needs.c4'`.

- [ ] **Step 3: Write the implementation**

Create `src/quarto_needs/c4/__init__.py`:

```python
"""The C4 architecture projection: semantics, validation, and renderer adapters.

This package is the single home of C4 meaning in Quarto-Needs. Renderers live
under `c4.renderers` and consume only the IR defined in `c4.model` -- they
never see an `AnalysisSnapshot` and never re-derive architecture semantics
of their own (Spec 1, 9).
"""
from __future__ import annotations
```

Create `src/quarto_needs/c4/model.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_c4_model.py -q`
Expected: 9 passed.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all pass — nothing imports the new package yet.

- [ ] **Step 6: Commit**

```bash
git add src/quarto_needs/c4/__init__.py src/quarto_needs/c4/model.py tests/test_c4_model.py
git commit -m "feat: add the renderer-independent C4 semantic model"
```

---

### Task 2: C4 structural validation

**Files:**
- Create: `src/quarto_needs/c4/validation.py`
- Test: `tests/test_c4_validation.py`

**Interfaces:**
- Consumes: `C4Element`, `C4ElementRole`, `C4Relationship`, `C4View`, `CONTAINMENT_ROLES` from Task 1.
- Produces: `C4Diagnostic` (frozen dataclass: `code: str`, `severity: str`, `message: str`, `object_id: str | None = None`, with `.to_dict()`); `validate_c4_view(view: C4View) -> tuple[C4Diagnostic, ...]`, returning diagnostics sorted by `(code, object_id or "")`.
- Diagnostic codes owned by this task: `C4001` (containment element with no parent), `C4002` (parent not present in the view), `C4003` (containment cycle), `C4006` (relationship references an unknown element), `C4007` (duplicate element ID), `C4009` (system-context view contains a nested element). `C4004`/`C4005` are renderer-availability codes owned by Task 5; `C4008` (invalid scope) is raised as an exception by Task 3.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_validation.py`:

```python
from __future__ import annotations

from quarto_needs.c4.model import C4Element, C4ElementRole, C4Relationship, C4View
from quarto_needs.c4.validation import C4Diagnostic, validate_c4_view


def _element(identifier: str, role: C4ElementRole, parent_id: str | None = None) -> C4Element:
    return C4Element(id=identifier, role=role, name=identifier.title(), parent_id=parent_id)


def _view(level: str, scope_id: str | None, elements, relationships=()) -> C4View:
    return C4View(
        id=f"{level}-{scope_id}",
        level=level,
        scope_id=scope_id,
        elements=tuple(elements),
        relationships=tuple(relationships),
    )


def _codes(view: C4View) -> list[str]:
    return [diagnostic.code for diagnostic in validate_c4_view(view)]


def test_a_well_formed_container_view_produces_no_diagnostics() -> None:
    view = _view(
        "container",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1"),
            _element("ACTOR-1", C4ElementRole.PERSON),
        ],
    )
    assert validate_c4_view(view) == ()


def test_c4001_flags_a_container_with_no_parent_system() -> None:
    view = _view(
        "container",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("CONTAINER-A", C4ElementRole.CONTAINER),
        ],
    )
    diagnostics = validate_c4_view(view)
    assert [item.code for item in diagnostics] == ["C4001"]
    assert diagnostics[0].object_id == "CONTAINER-A"
    assert "CONTAINER-A" in diagnostics[0].message
    assert diagnostics[0].severity == "error"


def test_c4001_does_not_flag_the_scope_element_itself() -> None:
    # A component view's scope container legitimately has no parent *in the
    # view* -- its system is one level up and deliberately out of scope.
    view = _view(
        "component",
        "CONTAINER-A",
        [
            _element("CONTAINER-A", C4ElementRole.CONTAINER),
            _element("COMP-1", C4ElementRole.COMPONENT, parent_id="CONTAINER-A"),
        ],
    )
    assert validate_c4_view(view) == ()


def test_c4002_flags_a_parent_that_is_not_in_the_view() -> None:
    view = _view(
        "component",
        "CONTAINER-A",
        [
            _element("CONTAINER-A", C4ElementRole.CONTAINER),
            _element("COMP-1", C4ElementRole.COMPONENT, parent_id="CONTAINER-GONE"),
        ],
    )
    diagnostics = validate_c4_view(view)
    assert [item.code for item in diagnostics] == ["C4002"]
    assert "CONTAINER-GONE" in diagnostics[0].message
    assert diagnostics[0].object_id == "COMP-1"


def test_c4003_flags_a_containment_cycle() -> None:
    view = _view(
        "container",
        "SYS-A",
        [
            _element("SYS-A", C4ElementRole.SOFTWARE_SYSTEM, parent_id="CONTAINER-B"),
            _element("CONTAINER-B", C4ElementRole.CONTAINER, parent_id="SYS-A"),
        ],
    )
    codes = _codes(view)
    assert "C4003" in codes
    cycle = next(item for item in validate_c4_view(view) if item.code == "C4003")
    assert "SYS-A" in cycle.message and "CONTAINER-B" in cycle.message


def test_c4006_flags_a_relationship_pointing_outside_the_view() -> None:
    view = _view(
        "system-context",
        "SYS-1",
        [_element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM)],
        [
            C4Relationship(
                id="depends-on:SYS-1:GONE",
                source_id="SYS-1",
                target_id="GONE",
                relation_type="depends-on",
            )
        ],
    )
    diagnostics = validate_c4_view(view)
    assert [item.code for item in diagnostics] == ["C4006"]
    assert "GONE" in diagnostics[0].message


def test_c4007_flags_a_duplicate_element_id() -> None:
    view = _view(
        "container",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1"),
            _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1"),
        ],
    )
    assert "C4007" in _codes(view)


def test_c4009_flags_a_container_leaking_into_a_system_context_view() -> None:
    view = _view(
        "system-context",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1"),
        ],
    )
    codes = _codes(view)
    assert "C4009" in codes


def test_diagnostics_are_sorted_and_serializable() -> None:
    view = _view(
        "container",
        "SYS-1",
        [
            _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM),
            _element("ZZZ-CONTAINER", C4ElementRole.CONTAINER),
            _element("AAA-CONTAINER", C4ElementRole.CONTAINER),
        ],
    )
    diagnostics = validate_c4_view(view)
    assert [item.object_id for item in diagnostics] == ["AAA-CONTAINER", "ZZZ-CONTAINER"]
    assert diagnostics[0].to_dict() == {
        "code": "C4001",
        "severity": "error",
        "message": diagnostics[0].message,
        "objectId": "AAA-CONTAINER",
    }


def test_diagnostic_without_an_object_id_serializes_a_null() -> None:
    assert C4Diagnostic("C4004", "warning", "no renderer").to_dict() == {
        "code": "C4004",
        "severity": "warning",
        "message": "no renderer",
        "objectId": None,
    }
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_validation.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'quarto_needs.c4.validation'`.

- [ ] **Step 3: Write the implementation**

Create `src/quarto_needs/c4/validation.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_c4_validation.py -q`
Expected: 10 passed.

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass.

```bash
git add src/quarto_needs/c4/validation.py tests/test_c4_validation.py
git commit -m "feat: validate projected C4 views before any renderer sees them"
```

---

### Task 3: The C4 projection engine — canonical graph to IR

**Files:**
- Create: `src/quarto_needs/c4/projection.py`
- Test: `tests/test_c4_projection_ir.py`

**Interfaces:**
- Consumes: `AnalysisSnapshot`, `ObjectRecord`, `RelationRecord` from `..snapshot`; `DEFAULT_RELATION_CATALOG` from `..relations`; every name from Task 1's `model`.
- Produces: `C4ProjectionError` (exception with a `.code == "C4008"` class attribute and a `.scope_id: str | None`); `project_c4(snapshot: AnalysisSnapshot, *, level: str, scope_id: str) -> C4View`; `available_scopes(snapshot: AnalysisSnapshot, level: str) -> tuple[str, ...]`; `SCOPE_TYPE_BY_LEVEL: Mapping[str, str]`.

**Semantics this task fixes (state it in the commit message, it is not a silent change):** today's `c4_projection.build_c4_view` selects every depth-1 neighbour over `depends-on`, whatever its type, and `c4_render._macro_call` then does `_MACRO_BY_TYPE[node.type]` — so a project that authors `depends-on` from, say, a `system-requirement` to a `system` crashes `quarto-needs scan` with an unhandled `KeyError` (`graph_output.write_c4_projections` catches only `C4ViewError`/`GraphLimitExceeded`). The new projection admits an object as an element only when its type is in `C4_ROLE_BY_TYPE`, which removes the crash. A regression test pins it.

**Semantics this task deliberately moves out of the renderer:** the current Mermaid code decides which `depends-on` edges are drawable and which "other" nodes then become disconnected floating boxes. Those are *Mermaid* limitations (mermaid 11.6.0 throws when a `Rel` targets a boundary alias), not C4 semantics. The IR therefore **includes** the people/external systems attached to the scope and their relationships at every level; Task 6's Mermaid adapter drops what it cannot draw. Mermaid's rendered output is unchanged; the difference is that the limitation now lives in the adapter that has it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_projection_ir.py`:

```python
from __future__ import annotations

import pytest

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4.model import C4ElementRole
from quarto_needs.c4.projection import (
    C4ProjectionError,
    available_scopes,
    project_c4,
)
from quarto_needs.model import EngineeringObject, Relation


def _obj(identifier, *, type, title=None, attributes=None, relations=None):
    return EngineeringObject(
        identifier,
        type,
        title or identifier.title(),
        status="draft",
        attributes=attributes or {},
        relations=relations or [],
    )


def _snapshot(*objects):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None
    return result.snapshot


def _ids(view):
    return [element.id for element in view.elements]


def test_system_context_shows_the_system_and_its_interacting_neighbours() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "EXT-1", "SYS-1")]),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    assert view.id == "system-context-SYS-1"
    assert view.level == "system-context"
    assert view.scope_id == "SYS-1"
    assert _ids(view) == ["ACTOR-1", "EXT-1", "SYS-1"]
    assert "CONTAINER-1" not in _ids(view)


def test_roles_and_the_external_flag_come_from_the_object_type() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "EXT-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    roles = {element.id: element.role for element in view.elements}
    assert roles == {
        "SYS-1": C4ElementRole.SOFTWARE_SYSTEM,
        "ACTOR-1": C4ElementRole.PERSON,
        "EXT-1": C4ElementRole.EXTERNAL_SYSTEM,
    }
    external = {element.id: element.external for element in view.elements}
    assert external == {"SYS-1": False, "ACTOR-1": False, "EXT-1": True}


def test_container_level_resolves_children_authored_as_part_of() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj(
            "CONTAINER-1",
            type="container",
            attributes={"technology": "Python 3.12"},
            relations=[Relation("part-of", "CONTAINER-1", "SYS-1")],
        ),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
    )
    view = project_c4(snapshot, level="container", scope_id="SYS-1")
    assert _ids(view) == ["CONTAINER-1", "SYS-1"]
    container = view.element("CONTAINER-1")
    assert container.parent_id == "SYS-1"
    assert container.technology == "Python 3.12"
    # The scope is the view's root: its own parent is out of scope.
    assert view.scope.parent_id is None
    # Grandchildren stop at one level.
    assert "COMP-1" not in _ids(view)


def test_container_level_resolves_children_authored_as_decomposes() -> None:
    # part-of runs child->parent; decomposes runs parent->child. A consumer
    # that checks only one direction silently drops every hierarchy authored
    # the other way -- the exact defect the previous slice had to fix.
    snapshot = _snapshot(
        _obj("SYS-1", type="system", relations=[Relation("decomposes", "SYS-1", "CONTAINER-1")]),
        _obj("CONTAINER-1", type="container"),
    )
    view = project_c4(snapshot, level="container", scope_id="SYS-1")
    assert _ids(view) == ["CONTAINER-1", "SYS-1"]
    assert view.element("CONTAINER-1").parent_id == "SYS-1"


def test_component_level_does_not_pull_in_the_scopes_own_parent() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
        _obj("SRC-1", type="source-module", relations=[Relation("part-of", "SRC-1", "COMP-1")]),
    )
    view = project_c4(snapshot, level="component", scope_id="CONTAINER-1")
    assert _ids(view) == ["COMP-1", "CONTAINER-1"]
    assert "SYS-1" not in _ids(view)
    assert "SRC-1" not in _ids(view)


def test_code_level_shows_a_components_source_modules() -> None:
    snapshot = _snapshot(
        _obj("COMP-1", type="component"),
        _obj(
            "SRC-1",
            type="source-module",
            attributes={"language": "Python"},
            relations=[Relation("part-of", "SRC-1", "COMP-1")],
        ),
    )
    view = project_c4(snapshot, level="code", scope_id="COMP-1")
    assert _ids(view) == ["COMP-1", "SRC-1"]
    assert view.element("SRC-1").role is C4ElementRole.CODE
    assert view.element("SRC-1").parent_id == "COMP-1"


def test_children_are_filtered_to_the_levels_expected_child_type() -> None:
    # ARC001 already rejects a layer skip as a graph error; the projection
    # additionally refuses to draw one, so a project running under an
    # advisory profile still gets a coherent diagram.
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="container", scope_id="SYS-1")
    assert _ids(view) == ["SYS-1"]


def test_a_non_architecture_neighbour_is_not_a_c4_element() -> None:
    # Before this projection existed, a depends-on edge from a requirement
    # reached the Mermaid renderer and raised KeyError inside
    # `quarto-needs scan`. Only types in C4_ROLE_BY_TYPE are elements.
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("REQ-1", type="system-requirement", relations=[Relation("depends-on", "REQ-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    assert _ids(view) == ["SYS-1"]
    assert view.relationships == ()


def test_relationships_keep_semantic_direction_and_carry_the_catalog_label() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    assert len(view.relationships) == 1
    relationship = view.relationships[0]
    assert relationship.source_id == "ACTOR-1"
    assert relationship.target_id == "SYS-1"
    assert relationship.relation_type == "depends-on"
    assert relationship.description == "Depends on"
    # Known limitation: the parser has no relation-attribute grammar.
    assert relationship.technology is None


def test_interaction_edges_survive_at_container_level() -> None:
    # The IR keeps them; whether a given renderer can draw an arrow into a
    # boundary is that renderer's problem, not the model's.
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="container", scope_id="SYS-1")
    assert _ids(view) == ["ACTOR-1", "CONTAINER-1", "SYS-1"]
    assert [item.id for item in view.relationships] == ["depends-on:ACTOR-1:SYS-1"]


def test_ordering_is_stable_regardless_of_authoring_order() -> None:
    objects = [
        _obj("SYS-1", type="system"),
        _obj("ZED", type="external-system", relations=[Relation("depends-on", "ZED", "SYS-1")]),
        _obj("ABLE", type="actor", relations=[Relation("depends-on", "ABLE", "SYS-1")]),
    ]
    forward = project_c4(_snapshot(*objects), level="system-context", scope_id="SYS-1")
    backward = project_c4(_snapshot(*reversed(objects)), level="system-context", scope_id="SYS-1")
    assert _ids(forward) == ["ABLE", "SYS-1", "ZED"]
    assert _ids(forward) == _ids(backward)
    assert forward.relationships == backward.relationships


def test_the_legacy_context_level_name_is_accepted() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"))
    view = project_c4(snapshot, level="context", scope_id="SYS-1")
    assert view.level == "system-context"
    assert view.id == "system-context-SYS-1"


def test_invalid_scope_and_level_raise_c4008() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system"), _obj("CONTAINER-1", type="container"))
    with pytest.raises(C4ProjectionError, match="unsupported C4 level") as unsupported:
        project_c4(snapshot, level="deployment", scope_id="SYS-1")
    assert unsupported.value.code == "C4008"
    with pytest.raises(C4ProjectionError, match="MISSING"):
        project_c4(snapshot, level="system-context", scope_id="MISSING")
    with pytest.raises(C4ProjectionError, match="requires a 'system' scope"):
        project_c4(snapshot, level="container", scope_id="CONTAINER-1")
    with pytest.raises(C4ProjectionError, match="requires a 'container' scope"):
        project_c4(snapshot, level="component", scope_id="SYS-1")
    with pytest.raises(C4ProjectionError, match="requires a 'component' scope"):
        project_c4(snapshot, level="code", scope_id="SYS-1")


def test_available_scopes_enumerates_the_levels_scope_type() -> None:
    snapshot = _snapshot(
        _obj("SYS-B", type="system"),
        _obj("SYS-A", type="system"),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-A")]),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
    )
    assert available_scopes(snapshot, "system-context") == ("SYS-A", "SYS-B")
    assert available_scopes(snapshot, "container") == ("SYS-A", "SYS-B")
    assert available_scopes(snapshot, "component") == ("CONTAINER-1",)
    assert available_scopes(snapshot, "code") == ("COMP-1",)
    assert available_scopes(snapshot, "deployment") == ()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_projection_ir.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'quarto_needs.c4.projection'`.

- [ ] **Step 3: Write the implementation**

Create `src/quarto_needs/c4/projection.py`:

```python
"""The canonical graph to C4 IR projection -- the only place C4 meaning lives.

This module reads an `AnalysisSnapshot` and produces an immutable `C4View`.
It does not render, does not position anything, does not know any diagram
syntax, and never emits Mermaid/Structurizr/PlantUML/D2 (Spec 8).

Containment is resolved from the canonical `part-of`/`decomposes` pair in
*both* authored directions: `part-of` runs child->parent, `decomposes` runs
parent->child. Consuming only one direction silently drops every hierarchy
authored the other way.
"""
from __future__ import annotations

from typing import Mapping

from ..relations import DEFAULT_RELATION_CATALOG
from ..snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord
from .model import (
    C4_ROLE_BY_TYPE,
    C4Element,
    C4ElementRole,
    C4Relationship,
    C4View,
    normalize_level,
    relationship_id,
)


class C4ProjectionError(Exception):
    """An unusable level/scope pair. Reported to users as C4008."""

    code = "C4008"

    def __init__(self, message: str, *, scope_id: str | None = None) -> None:
        super().__init__(message)
        self.scope_id = scope_id


SCOPE_TYPE_BY_LEVEL: Mapping[str, str] = {
    "system-context": "system",
    "container": "system",
    "component": "container",
    "code": "component",
}

# What a level draws *inside* its boundary. system-context draws nothing
# inside: a context diagram shows the system as an opaque box (Spec 30).
_CHILD_TYPE_BY_LEVEL: Mapping[str, str] = {
    "container": "container",
    "component": "component",
    "code": "source-module",
}

_INTERACTION_RELATION = "depends-on"
_CONTAINMENT_RELATIONS = ("part-of", "decomposes")


def _text_attribute(record: ObjectRecord, key: str) -> str | None:
    """A non-empty string attribute, or None.

    `description` deliberately comes from an attribute and never from the
    `.need` block body: a body is multi-paragraph prose and would wreck
    every diagram it reached.
    """
    value = record.attributes.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _child_id(relation: RelationRecord, *, parent_id: str) -> str | None:
    """The child's ID if `relation` declares it a direct child of `parent_id`.

    `v1_name` rather than `authored_name`: it collapses authoring aliases, so
    a future alias for either direction is handled without touching this.
    """
    if relation.v1_name == "part-of" and relation.target == parent_id:
        return relation.source
    if relation.v1_name == "decomposes" and relation.source == parent_id:
        return relation.target
    return None


def _label_for(relation: RelationRecord) -> str:
    try:
        return DEFAULT_RELATION_CATALOG.resolve(relation.authored_name).direct_label
    except ValueError:
        return relation.authored_name


def _element(record: ObjectRecord, *, parent_id: str | None) -> C4Element:
    role = C4_ROLE_BY_TYPE[record.type]
    return C4Element(
        id=record.id,
        role=role,
        name=record.title,
        description=_text_attribute(record, "description"),
        technology=_text_attribute(record, "technology"),
        parent_id=parent_id,
        external=role is C4ElementRole.EXTERNAL_SYSTEM,
        tags=record.tags,
    )


def _sort_key(identifier: str) -> tuple[str, str]:
    return (identifier.casefold(), identifier)


def available_scopes(snapshot: AnalysisSnapshot, level: str) -> tuple[str, ...]:
    """Every object that can scope a view at `level`, in deterministic order."""
    canonical = normalize_level(level)
    if canonical is None:
        return ()
    scope_type = SCOPE_TYPE_BY_LEVEL[canonical]
    return tuple(
        sorted(
            (record.id for record in snapshot.objects if record.type == scope_type),
            key=_sort_key,
        )
    )


def project_c4(
    snapshot: AnalysisSnapshot, *, level: str, scope_id: str
) -> C4View:
    canonical = normalize_level(level)
    if canonical is None:
        raise C4ProjectionError(
            f"unsupported C4 level: {level!r} (expected one of "
            f"{', '.join(SCOPE_TYPE_BY_LEVEL)})"
        )
    record = snapshot.objects_by_id.get(scope_id)
    if record is None:
        raise C4ProjectionError(
            f"{scope_id!r} is not a known object", scope_id=scope_id
        )
    expected_type = SCOPE_TYPE_BY_LEVEL[canonical]
    if record.type != expected_type:
        raise C4ProjectionError(
            f"level={canonical!r} requires a {expected_type!r} scope, "
            f"but {scope_id!r} is {record.type!r}",
            scope_id=scope_id,
        )

    # id -> parent id within this view. The scope is always the view's root.
    parents: dict[str, str | None] = {scope_id: None}

    child_type = _CHILD_TYPE_BY_LEVEL.get(canonical)
    if child_type is not None:
        for relation in snapshot.relations:
            child_id = _child_id(relation, parent_id=scope_id)
            if child_id is None or child_id in parents:
                continue
            child = snapshot.objects_by_id.get(child_id)
            # Filtering by the level's expected child type keeps a layer
            # skip (already an ARC001 graph error) from producing an
            # incoherent diagram under an advisory profile.
            if child is not None and child.type == child_type:
                parents[child_id] = scope_id

    for relation in snapshot.relations:
        if relation.v1_name != _INTERACTION_RELATION:
            continue
        if relation.source == scope_id:
            other = relation.target
        elif relation.target == scope_id:
            other = relation.source
        else:
            continue
        if other not in parents and other in snapshot.objects_by_id:
            parents[other] = None

    # Only architecture objects are C4 elements. A `depends-on` neighbour of
    # any other type (a requirement, say) is a perfectly valid graph edge
    # that simply has no C4 role, and is not drawn.
    elements = tuple(
        _element(snapshot.objects_by_id[identifier], parent_id=parents[identifier])
        for identifier in sorted(parents, key=_sort_key)
        if snapshot.objects_by_id[identifier].type in C4_ROLE_BY_TYPE
    )
    element_ids = {element.id for element in elements}

    relationships = tuple(
        sorted(
            (
                C4Relationship(
                    id=relationship_id(
                        relation.source, relation.target, relation.v1_name
                    ),
                    source_id=relation.source,
                    target_id=relation.target,
                    relation_type=relation.v1_name,
                    description=_label_for(relation),
                )
                for relation in snapshot.relations
                if relation.v1_name == _INTERACTION_RELATION
                and relation.source in element_ids
                and relation.target in element_ids
            ),
            key=lambda item: _sort_key(item.source_id)
            + _sort_key(item.target_id)
            + _sort_key(item.relation_type),
        )
    )

    return C4View(
        id=f"{canonical}-{scope_id}",
        level=canonical,
        scope_id=scope_id,
        elements=elements,
        relationships=relationships,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_c4_projection_ir.py -q`
Expected: 14 passed.

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass. The legacy `c4_projection.py` is untouched and still serves `graph_output.py`.

```bash
git add src/quarto_needs/c4/projection.py tests/test_c4_projection_ir.py
git commit -m "feat: project the canonical graph into a renderer-independent C4 view

Only objects with a canonical C4 role become elements, which also removes
an unhandled KeyError that reached 'quarto-needs scan' whenever a
non-architecture object had a depends-on edge to a system."
```

---

### Task 4: The versioned IR boundary — serialization, JSON schema, fingerprint

**Files:**
- Create: `src/quarto_needs/c4/serialize.py`
- Create: `schemas/c4-view-v1.schema.json`
- Test: `tests/test_c4_serialize.py`

**Interfaces:**
- Consumes: `C4View` (Task 1), `C4Diagnostic` (Task 2).
- Produces: `C4_VIEW_SCHEMA_VERSION = "quarto-needs-c4-view-v1"`; `c4_view_fingerprint(view: C4View) -> str` (64-character sha256 hex); `c4_view_document(view: C4View, *, diagnostics: Sequence[C4Diagnostic] = ()) -> dict[str, object]`; `render_c4_view(view: C4View, *, diagnostics: Sequence[C4Diagnostic] = ()) -> str` (JSON text, `indent=2`, `sort_keys=True`, trailing newline — matching `graph_projection.render_projection`).

**Why the document shape differs from the spec's sketch:** Spec §21 sketches a flat `{"schema": ..., "level": ...}`. This repository's existing published artifacts (`graph-public-v1`) use `schemaVersion` plus a nested `view` object, and `schemas/*.schema.json` files are the convention for pinning them. The plan follows the repository, not the sketch. The `fingerprint` field is added so Plan B's renderer-parity test (Spec §38) can read the IR identity straight out of a generated artifact.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_serialize.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4.projection import project_c4
from quarto_needs.c4.serialize import (
    C4_VIEW_SCHEMA_VERSION,
    c4_view_document,
    c4_view_fingerprint,
    render_c4_view,
)
from quarto_needs.c4.validation import validate_c4_view
from quarto_needs.model import EngineeringObject, Relation

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "c4-view-v1.schema.json").read_text(encoding="utf-8"))


def _obj(identifier, *, type, relations=None, attributes=None):
    return EngineeringObject(
        identifier, type, identifier.title(), status="draft",
        attributes=attributes or {}, relations=relations or [],
    )


def _fixture_snapshot():
    result = analyze_objects([
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "EXT-1", "SYS-1")]),
    ])
    assert result.snapshot is not None
    return result.snapshot


def _view():
    return project_c4(_fixture_snapshot(), level="system-context", scope_id="SYS-1")


def test_document_declares_the_versioned_schema_and_the_view_identity() -> None:
    document = c4_view_document(_view())
    assert document["schemaVersion"] == C4_VIEW_SCHEMA_VERSION == "quarto-needs-c4-view-v1"
    assert document["view"] == {
        "id": "system-context-SYS-1",
        "level": "system-context",
        "scopeId": "SYS-1",
    }
    assert [element["id"] for element in document["elements"]] == ["ACTOR-1", "EXT-1", "SYS-1"]
    assert [item["sourceId"] for item in document["relationships"]] == ["ACTOR-1", "EXT-1"]
    assert document["diagnostics"] == []
    assert document["fingerprint"] == c4_view_fingerprint(_view())


def test_document_validates_against_the_published_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    Draft202012Validator(SCHEMA).validate(c4_view_document(_view()))


def test_diagnostics_are_carried_in_the_document() -> None:
    view = _view()
    document = c4_view_document(view, diagnostics=validate_c4_view(view))
    assert document["diagnostics"] == []
    broken = project_c4(_fixture_snapshot(), level="container", scope_id="SYS-1")
    document = c4_view_document(broken, diagnostics=validate_c4_view(broken))
    Draft202012Validator(SCHEMA).validate(document)


def test_rendered_json_is_stable_text_with_a_trailing_newline() -> None:
    text = render_c4_view(_view())
    assert text.endswith("\n")
    assert json.loads(text)["schemaVersion"] == C4_VIEW_SCHEMA_VERSION
    assert render_c4_view(_view()) == text


def test_fingerprint_is_a_sha256_over_the_semantic_content_only() -> None:
    fingerprint = c4_view_fingerprint(_view())
    assert len(fingerprint) == 64
    assert set(fingerprint) <= set("0123456789abcdef")
    # Equivalent snapshots built in a different authoring order must agree.
    reordered = analyze_objects([
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "EXT-1", "SYS-1")]),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("SYS-1", type="system"),
    ])
    assert reordered.snapshot is not None
    assert (
        c4_view_fingerprint(
            project_c4(reordered.snapshot, level="system-context", scope_id="SYS-1")
        )
        == fingerprint
    )


def test_fingerprint_ignores_diagnostics_but_tracks_semantics() -> None:
    view = _view()
    assert c4_view_fingerprint(view) == c4_view_fingerprint(view)
    changed = analyze_objects([
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
    ])
    assert changed.snapshot is not None
    assert c4_view_fingerprint(
        project_c4(changed.snapshot, level="system-context", scope_id="SYS-1")
    ) != c4_view_fingerprint(view)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_serialize.py -q`
Expected: collection error — the schema file does not exist (`FileNotFoundError`) / `ModuleNotFoundError: No module named 'quarto_needs.c4.serialize'`.

- [ ] **Step 3: Write the schema**

Create `schemas/c4-view-v1.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schemas/c4-view-v1.schema.json",
  "title": "Quarto-Needs C4 view (v1)",
  "description": "The renderer-independent C4 intermediate representation. Every C4 renderer consumes this document and nothing else.",
  "type": "object",
  "required": ["schemaVersion", "view", "elements", "relationships", "diagnostics", "fingerprint"],
  "additionalProperties": false,
  "properties": {
    "schemaVersion": {"const": "quarto-needs-c4-view-v1"},
    "fingerprint": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "view": {
      "type": "object",
      "required": ["id", "level", "scopeId"],
      "additionalProperties": false,
      "properties": {
        "id": {"type": "string", "minLength": 1},
        "level": {"enum": ["system-context", "container", "component", "code"]},
        "scopeId": {"type": ["string", "null"]}
      }
    },
    "elements": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "role", "name", "description", "technology", "parentId", "external", "tags"],
        "additionalProperties": false,
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "role": {"enum": ["person", "software-system", "external-system", "container", "component", "code"]},
          "name": {"type": "string"},
          "description": {"type": ["string", "null"]},
          "technology": {"type": ["string", "null"]},
          "parentId": {"type": ["string", "null"]},
          "external": {"type": "boolean"},
          "tags": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "relationships": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "sourceId", "targetId", "relationType", "description", "technology", "tags"],
        "additionalProperties": false,
        "properties": {
          "id": {"type": "string", "minLength": 1},
          "sourceId": {"type": "string", "minLength": 1},
          "targetId": {"type": "string", "minLength": 1},
          "relationType": {"type": "string", "minLength": 1},
          "description": {"type": ["string", "null"]},
          "technology": {"type": ["string", "null"]},
          "tags": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "diagnostics": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["code", "severity", "message", "objectId"],
        "additionalProperties": false,
        "properties": {
          "code": {"type": "string", "pattern": "^C4[0-9]{3}$"},
          "severity": {"enum": ["error", "warning", "info"]},
          "message": {"type": "string"},
          "objectId": {"type": ["string", "null"]}
        }
      }
    }
  }
}
```

- [ ] **Step 4: Write the implementation**

Create `src/quarto_needs/c4/serialize.py`:

```python
"""The formal, versioned renderer boundary.

`quarto-needs-c4-view-v1` is the contract that separates "Quarto-Needs
understands architecture" from "some library draws architecture". Everything
downstream -- every renderer, every golden test, every parity check -- is
defined against this document and never against an `AnalysisSnapshot`.
"""
from __future__ import annotations

import hashlib
import json
from typing import Sequence

from .model import C4View
from .validation import C4Diagnostic

C4_VIEW_SCHEMA_VERSION = "quarto-needs-c4-view-v1"


def c4_view_fingerprint(view: C4View) -> str:
    """A sha256 over the view's semantic content.

    Diagnostics are excluded: they are derived from the view, so including
    them would let a validation change move an identity that nothing
    semantic touched. Renderer options are excluded by construction -- they
    are not part of a `C4View` at all.
    """
    payload = json.dumps(
        view.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def c4_view_document(
    view: C4View, *, diagnostics: Sequence[C4Diagnostic] = ()
) -> dict[str, object]:
    return {
        "schemaVersion": C4_VIEW_SCHEMA_VERSION,
        "fingerprint": c4_view_fingerprint(view),
        "view": {"id": view.id, "level": view.level, "scopeId": view.scope_id},
        "elements": [element.to_dict() for element in view.elements],
        "relationships": [item.to_dict() for item in view.relationships],
        "diagnostics": [item.to_dict() for item in diagnostics],
    }


def render_c4_view(view: C4View, *, diagnostics: Sequence[C4Diagnostic] = ()) -> str:
    """The artifact text, matching `graph_projection.render_projection`'s shape."""
    document = c4_view_document(view, diagnostics=diagnostics)
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_c4_serialize.py -q`
Expected: 6 passed.

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass.

```bash
git add src/quarto_needs/c4/serialize.py schemas/c4-view-v1.schema.json tests/test_c4_serialize.py
git commit -m "feat: publish quarto-needs-c4-view-v1 as the formal renderer boundary"
```

---

### Task 5: Renderer protocol, capabilities, and the extensible registry

**Files:**
- Create: `src/quarto_needs/c4/renderers/__init__.py`
- Create: `src/quarto_needs/c4/renderers/base.py`
- Test: `tests/test_c4_renderer_registry.py`

**Interfaces:**
- Consumes: `C4View`, `LayoutDirection` (Task 1); `C4Diagnostic` (Task 2).
- Produces, from `base`: `RendererCapabilities` (frozen dataclass: `source: bool = True`, `svg: bool = False`, `png: bool = False`, `auto_layout: str = "none"`, `interactive: bool = False`, with `.to_dict()`); `C4RenderOptions` (frozen: `direction: LayoutDirection = LayoutDirection.TOP_BOTTOM`, `settings: Mapping[str, str] = MappingProxyType({})`, plus `.setting(name, default=None) -> str | None`); `C4RenderResult` (frozen: `renderer`, `source_format`, `file_extension`, `source`, `view_fingerprint`, `diagnostics: tuple[C4Diagnostic, ...] = ()`, `artifact_path: Path | None = None`, with `.to_dict()`); the `C4Renderer` Protocol (`name: str`, `capabilities: RendererCapabilities`, `render(view, options) -> C4RenderResult`); `C4_RENDER_SCHEMA_VERSION = "quarto-needs-c4-render-v1"`.
- Produces, from `renderers/__init__`: `UnknownRendererError(ValueError)` with `.code == "C4004"`; `register_c4_renderer(renderer: C4Renderer) -> None`; `get_c4_renderer(name: str) -> C4Renderer`; `c4_renderer_names() -> tuple[str, ...]` (sorted); `c4_renderers() -> tuple[C4Renderer, ...]` (sorted by name).

**Deviation from Spec §25:** `auto_layout` is a string (`"none"` / `"limited"` / `"full"`), not a boolean. The spec's own §25 CLI mock-up prints `limited` for Mermaid, which a boolean cannot express.

**Note on `artifact_path`:** the renderer never sets it — a renderer produces text, it does not choose where text lives. Task 8's artifact writer fills it in with `dataclasses.replace`. It is deliberately excluded from `to_dict()`: that payload is read by Lua and must never carry a local filesystem path, matching the reasoning behind `graph_projection._public_href`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_renderer_registry.py`:

```python
from __future__ import annotations

import ast
import pathlib

import pytest

from quarto_needs.c4 import renderers as registry
from quarto_needs.c4.model import C4View, LayoutDirection
from quarto_needs.c4.renderers.base import (
    C4_RENDER_SCHEMA_VERSION,
    C4RenderOptions,
    C4RenderResult,
    RendererCapabilities,
)
from quarto_needs.c4.validation import C4Diagnostic


class _Fake:
    name = "fake"
    capabilities = RendererCapabilities(source=True, svg=False, auto_layout="full")

    def render(self, view: C4View, options: C4RenderOptions) -> C4RenderResult:
        return C4RenderResult(
            renderer=self.name,
            source_format="fake",
            file_extension=".fake",
            source=f"{view.id}:{options.direction.value}\n",
            view_fingerprint="0" * 64,
        )


@pytest.fixture
def clean_registry():
    saved = dict(registry._REGISTRY)
    try:
        yield
    finally:
        registry._REGISTRY.clear()
        registry._REGISTRY.update(saved)


def test_register_and_look_up_a_renderer(clean_registry) -> None:
    renderer = _Fake()
    registry.register_c4_renderer(renderer)
    assert registry.get_c4_renderer("fake") is renderer
    assert "fake" in registry.c4_renderer_names()


def test_renderer_names_and_objects_are_sorted(clean_registry) -> None:
    registry._REGISTRY.clear()
    for name in ("zulu", "alpha", "mike"):
        renderer = _Fake()
        renderer.name = name
        registry.register_c4_renderer(renderer)
    assert registry.c4_renderer_names() == ("alpha", "mike", "zulu")
    assert [item.name for item in registry.c4_renderers()] == ["alpha", "mike", "zulu"]


def test_unknown_renderer_reports_c4004_and_names_what_is_available(clean_registry) -> None:
    registry._REGISTRY.clear()
    registry.register_c4_renderer(_Fake())
    with pytest.raises(registry.UnknownRendererError) as error:
        registry.get_c4_renderer("structurizr")
    assert error.value.code == "C4004"
    assert "structurizr" in str(error.value)
    assert "fake" in str(error.value)


def test_mermaid_is_registered_by_importing_the_package() -> None:
    # Registration happens on import of `quarto_needs.c4.renderers`, so no
    # caller ever has to remember to wire the built-in adapters up.
    assert "mermaid" in registry.c4_renderer_names()


def test_render_options_expose_namespaced_settings() -> None:
    options = C4RenderOptions(
        direction=LayoutDirection.LEFT_RIGHT, settings={"layout": "elk"}
    )
    assert options.direction is LayoutDirection.LEFT_RIGHT
    assert options.setting("layout") == "elk"
    assert options.setting("missing") is None
    assert options.setting("missing", "dagre") == "dagre"
    assert C4RenderOptions().direction is LayoutDirection.TOP_BOTTOM
    assert C4RenderOptions().setting("anything") is None


def test_capabilities_serialize() -> None:
    assert RendererCapabilities().to_dict() == {
        "source": True,
        "svg": False,
        "png": False,
        "autoLayout": "none",
        "interactive": False,
    }


def test_render_result_payload_omits_the_local_artifact_path() -> None:
    result = C4RenderResult(
        renderer="fake",
        source_format="fake",
        file_extension=".fake",
        source="x\n",
        view_fingerprint="a" * 64,
        diagnostics=(C4Diagnostic("C4010", "info", "dropped one", "SYS-1"),),
        artifact_path=pathlib.Path("/tmp/somewhere/fake.fake"),
    )
    payload = result.to_dict()
    assert payload == {
        "schemaVersion": C4_RENDER_SCHEMA_VERSION,
        "renderer": "fake",
        "sourceFormat": "fake",
        "fileExtension": ".fake",
        "source": "x\n",
        "viewFingerprint": "a" * 64,
        "diagnostics": [
            {"code": "C4010", "severity": "info", "message": "dropped one", "objectId": "SYS-1"}
        ],
    }
    assert "artifactPath" not in payload
    assert "/tmp/somewhere" not in repr(payload)


def test_no_renderer_module_may_import_the_engineering_graph() -> None:
    # The architectural invariant this whole plan exists to create: a
    # renderer consumes the IR and nothing else. If this test fails, some
    # adapter has started re-deriving architecture semantics of its own.
    forbidden = {
        "snapshot", "analysis", "graph_projection", "graph_render",
        "relations", "config", "model",
    }
    directory = pathlib.Path(registry.__file__).parent
    offenders: list[str] = []
    for path in sorted(directory.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                head = node.module.split(".")[0]
                # `from ..model import ...` is the IR itself and is allowed;
                # `from ...model import ...` would be the *engineering* model.
                if head == "model" and node.level == 2:
                    continue
                if head in forbidden:
                    offenders.append(f"{path.name}: from {'.' * node.level}{node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[-1] in forbidden:
                        offenders.append(f"{path.name}: import {alias.name}")
    assert offenders == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_renderer_registry.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'quarto_needs.c4.renderers'`.

- [ ] **Step 3: Write `base.py`**

Create `src/quarto_needs/c4/renderers/base.py`:

```python
"""What every C4 renderer is, and nothing about what any of them draws.

A renderer receives a `C4View` and returns text. It never sees an
`AnalysisSnapshot`, never re-derives a role, never decides what a boundary
means -- all of that was settled by `c4.projection` before it was called
(Spec 9). `tests/test_c4_renderer_registry.py` enforces that mechanically.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Protocol

from ..model import C4View, LayoutDirection
from ..validation import C4Diagnostic

C4_RENDER_SCHEMA_VERSION = "quarto-needs-c4-render-v1"


@dataclass(frozen=True, slots=True)
class RendererCapabilities:
    """What a backend can actually do in this installation.

    `auto_layout` is a string rather than the spec's boolean because the
    spec's own capability table needs to say `limited` for Mermaid.
    `svg`/`png` stay False for every backend in this milestone: no adapter
    executes an external binary yet.
    """

    source: bool = True
    svg: bool = False
    png: bool = False
    auto_layout: str = "none"
    interactive: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "svg": self.svg,
            "png": self.png,
            "autoLayout": self.auto_layout,
            "interactive": self.interactive,
        }


@dataclass(frozen=True, slots=True)
class C4RenderOptions:
    """Presentation-only input. Changing any of it cannot change the IR."""

    direction: LayoutDirection = LayoutDirection.TOP_BOTTOM
    settings: Mapping[str, str] = MappingProxyType({})

    def setting(self, name: str, default: str | None = None) -> str | None:
        value = self.settings.get(name)
        return value if isinstance(value, str) and value else default


@dataclass(frozen=True, slots=True)
class C4RenderResult:
    renderer: str
    source_format: str
    file_extension: str
    source: str
    view_fingerprint: str
    diagnostics: tuple[C4Diagnostic, ...] = ()
    # Filled in by the artifact writer, never by a renderer: producing text
    # and choosing where text lives are different jobs.
    artifact_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        """The payload Lua reads. Deliberately carries no filesystem path."""
        return {
            "schemaVersion": C4_RENDER_SCHEMA_VERSION,
            "renderer": self.renderer,
            "sourceFormat": self.source_format,
            "fileExtension": self.file_extension,
            "source": self.source,
            "viewFingerprint": self.view_fingerprint,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


class C4Renderer(Protocol):
    name: str
    capabilities: RendererCapabilities

    def render(self, view: C4View, options: C4RenderOptions) -> C4RenderResult:
        ...
```

- [ ] **Step 4: Write the registry**

Create `src/quarto_needs/c4/renderers/__init__.py`:

```python
"""The C4 renderer registry -- the extension point for new backends.

Adding a backend is `register_c4_renderer(MyRenderer())`, never a new branch
in a conditional somewhere else (Spec 14).
"""
from __future__ import annotations

from .base import (
    C4_RENDER_SCHEMA_VERSION,
    C4Renderer,
    C4RenderOptions,
    C4RenderResult,
    RendererCapabilities,
)

__all__ = [
    "C4_RENDER_SCHEMA_VERSION",
    "C4Renderer",
    "C4RenderOptions",
    "C4RenderResult",
    "RendererCapabilities",
    "UnknownRendererError",
    "c4_renderer_names",
    "c4_renderers",
    "get_c4_renderer",
    "register_c4_renderer",
]


class UnknownRendererError(ValueError):
    """A renderer was requested that is not registered. Reported as C4004."""

    code = "C4004"


_REGISTRY: dict[str, C4Renderer] = {}


def register_c4_renderer(renderer: C4Renderer) -> None:
    _REGISTRY[renderer.name] = renderer


def get_c4_renderer(name: str) -> C4Renderer:
    try:
        return _REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY)) or "none"
        raise UnknownRendererError(
            f"Renderer {name!r} is not available for direct rendering "
            f"(registered renderers: {available})"
        ) from None


def c4_renderer_names() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def c4_renderers() -> tuple[C4Renderer, ...]:
    return tuple(_REGISTRY[name] for name in sorted(_REGISTRY))


def _register_builtin_renderers() -> None:
    """Importing this package registers every backend that ships with it."""
    from .mermaid import MermaidRenderer

    register_c4_renderer(MermaidRenderer())


_register_builtin_renderers()
```

- [ ] **Step 5: Run the tests to verify they fail for the right reason**

Run: `python -m pytest tests/test_c4_renderer_registry.py -q`
Expected: every test errors with `ModuleNotFoundError: No module named 'quarto_needs.c4.renderers.mermaid'` — raised from `_register_builtin_renderers`. That is the correct failure: Task 6 supplies the module. Do **not** stub it out here; go straight to Task 6 and run both test files together.

- [ ] **Step 6: Commit the protocol and registry**

```bash
git add src/quarto_needs/c4/renderers/__init__.py src/quarto_needs/c4/renderers/base.py tests/test_c4_renderer_registry.py
git commit -m "feat: add the C4 renderer protocol, capability model, and registry"
```

(The suite is red between this commit and Task 6's — the two tasks are one deliverable split for review. If the executing workflow requires every commit green, squash Tasks 5 and 6 into a single commit at the end of Task 6 instead.)

---

### Task 6: The Mermaid adapter, rebuilt on the IR

**Files:**
- Create: `src/quarto_needs/c4/renderers/mermaid.py`
- Test: `tests/test_c4_renderer_mermaid.py`

**Interfaces:**
- Consumes: `C4Element`, `C4ElementRole`, `C4View`, `identifier_map` (Task 1); `C4Diagnostic` (Task 2); `c4_view_fingerprint` (Task 4); `C4RenderOptions`, `C4RenderResult`, `RendererCapabilities` (Task 5).
- Produces: `MermaidRenderer` (`name = "mermaid"`, `capabilities = RendererCapabilities(source=True, svg=True, auto_layout="limited")`), rendering `source_format` `"mermaid"` / extension `.mmd` at the three diagram levels and `"markdown"` / `.md` at code level.
- New diagnostic code owned by this renderer: `C4010` (info) — Mermaid cannot draw a relationship into a boundary alias, so those relationships and any element left with nothing to connect to are omitted from container/component diagrams.

**Two user-visible changes to state in the commit message:**
1. **Identifiers become readable.** `c4_5359532d...` becomes `SYS_QUARTO_NEEDS` (Spec §28). Generated artifact only; no authored content changes.
2. **The code-level table's columns change** from `ID | Path | Language | Implements` to `ID | Name | Description | Technology`. `path` reaches the IR as a code element's `description` and `language` as its `technology`. The `Implements` column is dropped: `implements` edges point at requirements, which are not C4 elements, so carrying them would put non-C4 semantics into the C4 IR. Requirement traceability for a source module is what the existing `need-table`/`need-backlinks` shortcodes already render, and Plan B's self-hosted example task places one beside the code view.

- [ ] **Step 1: Extend the projection so a code element's path survives**

The `description` fallback for code elements is projection work, not renderer work. Add this test to `tests/test_c4_projection_ir.py`:

```python
def test_a_code_elements_description_falls_back_to_its_path() -> None:
    snapshot = _snapshot(
        _obj("COMP-1", type="component", attributes={"path": "ignored/for/components"}),
        _obj(
            "SRC-1",
            type="source-module",
            attributes={"path": "src/quarto_needs/parser.py", "language": "Python"},
            relations=[Relation("part-of", "SRC-1", "COMP-1")],
        ),
    )
    view = project_c4(snapshot, level="code", scope_id="COMP-1")
    assert view.element("SRC-1").description == "src/quarto_needs/parser.py"
    assert view.element("SRC-1").technology == "Python"
    # The fallback is code-specific: a component's `path` is not a description.
    assert view.element("COMP-1").description is None


def test_an_explicit_description_attribute_wins_over_the_path_fallback() -> None:
    snapshot = _snapshot(
        _obj("COMP-1", type="component"),
        _obj(
            "SRC-1",
            type="source-module",
            attributes={"description": "The .need block parser", "path": "src/p.py"},
            relations=[Relation("part-of", "SRC-1", "COMP-1")],
        ),
    )
    view = project_c4(snapshot, level="code", scope_id="COMP-1")
    assert view.element("SRC-1").description == "The .need block parser"
```

Then change `_element` in `src/quarto_needs/c4/projection.py`:

```python
def _element(record: ObjectRecord, *, parent_id: str | None) -> C4Element:
    role = C4_ROLE_BY_TYPE[record.type]
    description = _text_attribute(record, "description")
    if description is None and role is C4ElementRole.CODE:
        # A source module's identity is its path; C4 code elements carry a
        # description string in every target format. Deliberately scoped to
        # the CODE role -- a component's `path` attribute, if any, means
        # something else.
        description = _text_attribute(record, "path")
    return C4Element(
        id=record.id,
        role=role,
        name=record.title,
        description=description,
        technology=_text_attribute(record, "technology") or _code_language(record, role),
        parent_id=parent_id,
        external=role is C4ElementRole.EXTERNAL_SYSTEM,
        tags=record.tags,
    )


def _code_language(record: ObjectRecord, role: C4ElementRole) -> str | None:
    """A code element's `language` is its technology in C4 terms."""
    return _text_attribute(record, "language") if role is C4ElementRole.CODE else None
```

Run: `python -m pytest tests/test_c4_projection_ir.py -q` — expected: 16 passed (the 14 from Task 3 plus these two).

- [ ] **Step 2: Write the failing renderer tests**

Create `tests/test_c4_renderer_mermaid.py`:

```python
from __future__ import annotations

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4.projection import project_c4
from quarto_needs.c4.renderers import get_c4_renderer
from quarto_needs.c4.renderers.base import C4RenderOptions
from quarto_needs.c4.serialize import c4_view_fingerprint
from quarto_needs.model import EngineeringObject, Relation


def _obj(identifier, *, type, title=None, attributes=None, relations=None):
    return EngineeringObject(
        identifier, type, title or identifier.title(), status="draft",
        attributes=attributes or {}, relations=relations or [],
    )


def _snapshot(*objects):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None
    return result.snapshot


def _render(view):
    return get_c4_renderer("mermaid").render(view, C4RenderOptions())


def test_context_diagram_draws_the_system_as_an_opaque_box() -> None:
    snapshot = _snapshot(
        _obj("SYS-QUARTO-NEEDS", type="system", title="Quarto-Needs"),
        _obj("ACTOR-1", type="actor", title="Requirements engineer",
             relations=[Relation("depends-on", "ACTOR-1", "SYS-QUARTO-NEEDS")]),
        _obj("EXT-GITHUB", type="external-system", title="GitHub",
             relations=[Relation("depends-on", "EXT-GITHUB", "SYS-QUARTO-NEEDS")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-QUARTO-NEEDS")
    result = _render(view)
    assert result.renderer == "mermaid"
    assert result.source_format == "mermaid"
    assert result.file_extension == ".mmd"
    assert result.view_fingerprint == c4_view_fingerprint(view)
    lines = result.source.splitlines()
    assert lines[0] == "C4Context"
    assert '  Person(ACTOR_1, "Requirements engineer")' in lines
    assert '  System_Ext(EXT_GITHUB, "GitHub")' in lines
    assert '  System(SYS_QUARTO_NEEDS, "Quarto-Needs")' in lines
    assert '  Rel(ACTOR_1, SYS_QUARTO_NEEDS, "Depends on")' in lines
    assert result.source.endswith("\n")


def test_identifiers_are_readable_and_derived_from_canonical_ids() -> None:
    snapshot = _snapshot(_obj("SYS-QUARTO-NEEDS", type="system", title="Quarto-Needs"))
    result = _render(project_c4(snapshot, level="system-context", scope_id="SYS-QUARTO-NEEDS"))
    assert "SYS_QUARTO_NEEDS" in result.source
    assert "c4_53595" not in result.source


def test_container_diagram_wraps_children_in_a_system_boundary() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj("CONTAINER-1", type="container", title="Python package",
             attributes={"technology": "Python 3.12"},
             relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
    )
    source = _render(project_c4(snapshot, level="container", scope_id="SYS-1")).source
    lines = source.splitlines()
    assert lines[0] == "C4Container"
    assert '  System_Boundary(SYS_1, "Quarto-Needs") {' in lines
    assert '    Container(CONTAINER_1, "Python package", "Python 3.12")' in lines
    assert "  }" in lines


def test_component_diagram_wraps_children_in_a_container_boundary() -> None:
    snapshot = _snapshot(
        _obj("CONTAINER-1", type="container", title="Python package"),
        _obj("COMP-1", type="component", title="Parser",
             relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
    )
    source = _render(project_c4(snapshot, level="component", scope_id="CONTAINER-1")).source
    assert source.splitlines()[0] == "C4Component"
    assert '  Container_Boundary(CONTAINER_1, "Python package") {' in source
    assert '    Component(COMP_1, "Parser")' in source


def test_relationships_into_a_boundary_are_dropped_with_an_info_diagnostic() -> None:
    # mermaid 11.6.0 throws mid-render when a Rel targets a boundary alias.
    # That is a Mermaid limitation, so the Mermaid adapter owns it -- the IR
    # still carries the relationship, and the omission is reported, not hidden.
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="container", scope_id="SYS-1")
    assert len(view.relationships) == 1
    result = _render(view)
    assert "Rel(" not in result.source
    # An element left with nothing to connect to is a floating box with no
    # explanation; omit it entirely, as standard C4 practice does.
    assert "ACTOR_1" not in result.source
    assert [item.code for item in result.diagnostics] == ["C4010"]
    assert result.diagnostics[0].severity == "info"


def test_a_context_diagram_never_drops_relationships() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
    )
    result = _render(project_c4(snapshot, level="system-context", scope_id="SYS-1"))
    assert "Rel(ACTOR_1, SYS_1" in result.source
    assert result.diagnostics == ()


def test_code_level_renders_a_markdown_table_and_never_mermaid() -> None:
    snapshot = _snapshot(
        _obj("COMP-1", type="component", title="Parser"),
        _obj("SRC-B", type="source-module", title="rules.py",
             attributes={"path": "src/quarto_needs/rules.py", "language": "Python"},
             relations=[Relation("part-of", "SRC-B", "COMP-1")]),
        _obj("SRC-A", type="source-module", title="parser.py",
             attributes={"path": "src/quarto_needs/parser.py", "language": "Python"},
             relations=[Relation("part-of", "SRC-A", "COMP-1")]),
    )
    result = _render(project_c4(snapshot, level="code", scope_id="COMP-1"))
    assert result.source_format == "markdown"
    assert result.file_extension == ".md"
    assert "C4" not in result.source
    lines = result.source.splitlines()
    assert lines[0] == "| ID | Name | Description | Technology |"
    assert lines[1] == "| --- | --- | --- | --- |"
    assert lines[2] == "| SRC-A | parser.py | src/quarto_needs/parser.py | Python |"
    assert lines[3] == "| SRC-B | rules.py | src/quarto_needs/rules.py | Python |"
    # The scope component is the table's subject, not one of its rows.
    assert "COMP-1" not in result.source


def test_code_level_table_for_a_component_with_no_modules_is_just_a_header() -> None:
    snapshot = _snapshot(_obj("COMP-1", type="component"))
    result = _render(project_c4(snapshot, level="code", scope_id="COMP-1"))
    assert result.source.splitlines() == [
        "| ID | Name | Description | Technology |",
        "| --- | --- | --- | --- |",
    ]


def test_labels_are_escaped_against_mermaid_syntax() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", title='A "quoted" \\ name\nwith a newline'),
    )
    source = _render(project_c4(snapshot, level="system-context", scope_id="SYS-1")).source
    assert '"A \'quoted\' / name with a newline"' in source
    assert "\\" not in source
    assert len(source.splitlines()) == 2


def test_output_is_byte_identical_across_renders() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
    )
    view = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    assert _render(view).source == _render(view).source
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_renderer_mermaid.py tests/test_c4_renderer_registry.py -q`
Expected: `ModuleNotFoundError: No module named 'quarto_needs.c4.renderers.mermaid'`.

- [ ] **Step 4: Write the implementation**

Create `src/quarto_needs/c4/renderers/mermaid.py`:

```python
"""Mermaid C4 source generation from the C4 IR.

Mermaid is the zero-configuration default: no extra toolchain, and Quarto
already bundles the renderer. Its C4 layout is less sophisticated than the
alternatives -- a layout limitation, not a semantic one (Spec 50).

This module translates `C4View -> Mermaid text` and does nothing else. Every
decision about *what* is in the view was made by `c4.projection`.
"""
from __future__ import annotations

from ..model import (
    C4Element,
    C4ElementRole,
    C4View,
    identifier_map,
)
from ..serialize import c4_view_fingerprint
from ..validation import C4Diagnostic
from .base import C4RenderOptions, C4RenderResult, RendererCapabilities

_MACRO_BY_ROLE = {
    C4ElementRole.PERSON: "Person",
    C4ElementRole.EXTERNAL_SYSTEM: "System_Ext",
    C4ElementRole.SOFTWARE_SYSTEM: "System",
    C4ElementRole.CONTAINER: "Container",
    C4ElementRole.COMPONENT: "Component",
    # Mermaid has no C4 code macro; code level renders as a table instead,
    # so this entry exists only so the mapping is total.
    C4ElementRole.CODE: "Component",
}
_DIAGRAM_BY_LEVEL = {
    "system-context": "C4Context",
    "container": "C4Container",
    "component": "C4Component",
}
_BOUNDARY_BY_LEVEL = {"container": "System_Boundary", "component": "Container_Boundary"}


def _escape(value: str) -> str:
    replaced = value.replace("\\", "/").replace('"', "'")
    return replaced.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _macro_call(element: C4Element, reference: str) -> str:
    macro = _MACRO_BY_ROLE[element.role]
    arguments = [reference, f'"{_escape(element.name)}"']
    if element.technology:
        arguments.append(f'"{_escape(element.technology)}"')
    return f"{macro}({', '.join(arguments)})"


def _table(view: C4View) -> str:
    """Code level as a plain Markdown table.

    Mermaid has no C4Code diagram type, and code elements carry no
    inter-module arrows, so forcing diagram syntax onto non-diagram content
    would produce a worse artifact than a table.
    """
    lines = [
        "| ID | Name | Description | Technology |",
        "| --- | --- | --- | --- |",
    ]
    for element in view.children_of(view.scope_id or ""):
        lines.append(
            f"| {element.id} | {element.name} | "
            f"{element.description or ''} | {element.technology or ''} |"
        )
    return "\n".join(lines) + "\n"


def _diagram(view: C4View) -> tuple[str, tuple[C4Diagnostic, ...]]:
    references = identifier_map(view)
    scope = view.scope
    diagram_type = _DIAGRAM_BY_LEVEL[view.level]
    diagnostics: list[C4Diagnostic] = []

    if view.level == "system-context" or scope is None:
        drawn = view.relationships
        children: tuple[C4Element, ...] = ()
        outside = tuple(
            element for element in view.elements if scope is None or element.id != scope.id
        )
    else:
        children = view.children_of(scope.id)
        # A Rel that targets a boundary's own alias makes mermaid 11.6.0
        # throw mid-render (verified against Quarto's bundled mermaid.js in
        # a real browser). The relationship is not lost from the model --
        # the context diagram one level up shows it against the system as a
        # whole -- and the omission is reported rather than hidden.
        drawn = tuple(
            item
            for item in view.relationships
            if scope.id not in (item.source_id, item.target_id)
        )
        connected = {item.source_id for item in drawn} | {item.target_id for item in drawn}
        child_ids = {element.id for element in children}
        # An element left with no remaining edge renders as a floating box
        # with no indication of why it is on the diagram -- worse than the
        # crash it replaces. Omit it, as standard C4 practice does.
        outside = tuple(
            element
            for element in view.elements
            if element.id != scope.id
            and element.id not in child_ids
            and element.id in connected
        )
        omitted = len(view.relationships) - len(drawn)
        if omitted:
            diagnostics.append(
                C4Diagnostic(
                    "C4010",
                    "info",
                    f"Mermaid cannot draw a relationship into a boundary: "
                    f"{omitted} relationship(s) touching {scope.id} are omitted "
                    f"from the {view.level} diagram; the system-context view shows them",
                    scope.id,
                )
            )

    lines = [diagram_type]
    if view.level == "system-context" or scope is None:
        if scope is not None:
            lines.append(f"  {_macro_call(scope, references[scope.id])}")
        for element in outside:
            lines.append(f"  {_macro_call(element, references[element.id])}")
    else:
        boundary = _BOUNDARY_BY_LEVEL[view.level]
        lines.append(
            f'  {boundary}({references[scope.id]}, "{_escape(scope.name)}") {{'
        )
        for element in children:
            lines.append(f"    {_macro_call(element, references[element.id])}")
        lines.append("  }")
        for element in outside:
            lines.append(f"  {_macro_call(element, references[element.id])}")

    for item in drawn:
        lines.append(
            f"  Rel({references[item.source_id]}, {references[item.target_id]}, "
            f'"{_escape(item.description or item.relation_type)}")'
        )
    return "\n".join(lines) + "\n", tuple(diagnostics)


class MermaidRenderer:
    name = "mermaid"
    capabilities = RendererCapabilities(
        source=True,
        # Quarto's own bundled Mermaid produces the SVG; we generate text.
        svg=True,
        png=False,
        auto_layout="limited",
        interactive=False,
    )

    def render(self, view: C4View, options: C4RenderOptions) -> C4RenderResult:
        # Mermaid's C4 renderer offers no direction directive, so
        # `options.direction` is accepted and deliberately unused here --
        # hence `auto_layout="limited"`.
        if view.level == "code":
            return C4RenderResult(
                renderer=self.name,
                source_format="markdown",
                file_extension=".md",
                source=_table(view),
                view_fingerprint=c4_view_fingerprint(view),
            )
        source, diagnostics = _diagram(view)
        return C4RenderResult(
            renderer=self.name,
            source_format="mermaid",
            file_extension=".mmd",
            source=source,
            view_fingerprint=c4_view_fingerprint(view),
            diagnostics=diagnostics,
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_c4_renderer_mermaid.py tests/test_c4_renderer_registry.py -q`
Expected: 10 + 8 = 18 passed.

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass. The legacy `c4_render.py` still serves `graph_output.py`; nothing has switched over yet.

```bash
git add src/quarto_needs/c4/renderers/mermaid.py src/quarto_needs/c4/projection.py \
        tests/test_c4_renderer_mermaid.py tests/test_c4_projection_ir.py
git commit -m "feat: rebuild the Mermaid C4 adapter on the renderer-independent IR

Diagram identifiers become readable (SYS_QUARTO_NEEDS, not a hex blob) and
the code-level table's columns become ID/Name/Description/Technology -- a
source module's path and language reach the IR as its description and
technology. The Implements column is dropped: implements edges point at
requirements, which are not C4 elements."
```

---

### Task 7: `[architecture.c4]` configuration and renderer-selection precedence

**Files:**
- Modify: `src/quarto_needs/config.py` (add `KNOWN_TOP_LEVEL_KEYS` entry, three dataclasses, `_parse_architecture`, one `load_config` line, one `embedded_defaults` line)
- Test: `tests/test_c4_config.py`

**Interfaces:**
- Produces: `C4RendererSettings` (frozen: `direction: str = "top-bottom"`, `settings: Mapping[str, str] = MappingProxyType({})`); `C4Settings` (frozen: `renderer: str = "mermaid"`, `enabled_renderers: tuple[str, ...] = ("mermaid",)`, `view_renderers: Mapping[str, str] = MappingProxyType({})`, `renderer_settings: Mapping[str, C4RendererSettings] = MappingProxyType({})`, plus `renderer_for(level: str, requested: str | None = None) -> str` and `options_for(name: str) -> C4RendererSettings`); `ArchitectureSettings` (frozen: `c4: C4Settings = C4Settings()`); `NeedsConfig.architecture: ArchitectureSettings = ArchitectureSettings()`.

**The TOML shape, and why it differs from Spec §16/§17.** Those two sections together are not expressible in TOML: `renderers = [...]` (an array) and `[architecture.c4.renderers.mermaid]` (a table) cannot both live under the key `renderers`. The list key is therefore `enabled-renderers`. Keys are kebab-case throughout, matching every existing section (`max-nodes`, `overlay-queries`, `id-prefix`).

```toml
[architecture.c4]
renderer = "mermaid"            # the default renderer (Spec 15, 19)
enabled-renderers = ["mermaid"] # every renderer whose artifacts get written (Spec 16)

[architecture.c4.views.container]
renderer = "mermaid"            # per-view override, precedence step 2 (Spec 19)

[architecture.c4.renderers.mermaid]
direction = "top-bottom"        # everything else here is a free-form string setting
```

**Precedence (Spec §19), implemented in `C4Settings.renderer_for`:** explicit request (shortcode `renderer=` / CLI `--renderer`) → `[architecture.c4.views.<level>] renderer` → `[architecture.c4] renderer` → `"mermaid"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_config.py`:

```python
from __future__ import annotations

import pytest

from quarto_needs.config import ConfigurationError, load_config


def _config(tmp_path, body: str):
    (tmp_path / ".quarto-needs.toml").write_text(body, encoding="utf-8")
    return load_config(tmp_path)


def test_defaults_when_no_architecture_section_is_present(tmp_path) -> None:
    config = _config(tmp_path, 'profile = "default"\n')
    c4 = config.architecture.c4
    assert c4.renderer == "mermaid"
    assert c4.enabled_renderers == ("mermaid",)
    assert c4.view_renderers == {}
    assert c4.options_for("mermaid").direction == "top-bottom"
    assert c4.options_for("mermaid").settings == {}


def test_a_full_architecture_section_parses(tmp_path) -> None:
    config = _config(
        tmp_path,
        """
profile = "default"

[architecture.c4]
renderer = "mermaid"
enabled-renderers = ["mermaid"]

[architecture.c4.views.container]
renderer = "mermaid"

[architecture.c4.renderers.mermaid]
direction = "left-right"
layout = "elk"
""",
    )
    c4 = config.architecture.c4
    assert c4.renderer == "mermaid"
    assert c4.enabled_renderers == ("mermaid",)
    assert c4.view_renderers == {"container": "mermaid"}
    assert c4.options_for("mermaid").direction == "left-right"
    assert c4.options_for("mermaid").settings == {"layout": "elk"}


def test_renderer_selection_precedence(tmp_path) -> None:
    config = _config(
        tmp_path,
        """
profile = "default"

[architecture.c4]
renderer = "mermaid"

[architecture.c4.views.container]
renderer = "mermaid"
""",
    )
    c4 = config.architecture.c4
    # An explicit request always wins.
    assert c4.renderer_for("container", "someone-else") == "someone-else"
    # Then the per-view setting.
    assert c4.renderer_for("container") == "mermaid"
    # Then the section default.
    assert c4.renderer_for("system-context") == "mermaid"
    # And with nothing configured at all, mermaid.
    from quarto_needs.config import C4Settings

    assert C4Settings().renderer_for("code") == "mermaid"


def test_the_legacy_context_level_name_resolves_a_view_override(tmp_path) -> None:
    config = _config(
        tmp_path,
        """
profile = "default"

[architecture.c4.views.system-context]
renderer = "mermaid"
""",
    )
    assert config.architecture.c4.renderer_for("context") == "mermaid"


def test_unknown_keys_and_values_are_rejected(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="unknown keys"):
        _config(tmp_path, 'profile = "default"\n\n[architecture.c4]\nrendrer = "mermaid"\n')
    with pytest.raises(ConfigurationError, match="not a registered C4 renderer"):
        _config(tmp_path, 'profile = "default"\n\n[architecture.c4]\nrenderer = "graphviz"\n')
    with pytest.raises(ConfigurationError, match="direction must be one of"):
        _config(
            tmp_path,
            'profile = "default"\n\n[architecture.c4.renderers.mermaid]\ndirection = "diagonal"\n',
        )
    with pytest.raises(ConfigurationError, match="unknown C4 level"):
        _config(
            tmp_path,
            'profile = "default"\n\n[architecture.c4.views.deployment]\nrenderer = "mermaid"\n',
        )
    with pytest.raises(ConfigurationError, match="must be a table"):
        _config(tmp_path, 'profile = "default"\n\narchitecture = "yes"\n')


def test_renderer_settings_values_must_be_strings(tmp_path) -> None:
    with pytest.raises(ConfigurationError, match="must be a string"):
        _config(
            tmp_path,
            'profile = "default"\n\n[architecture.c4.renderers.mermaid]\nlayout = 3\n',
        )


def test_renderer_configuration_never_enters_the_canonical_fingerprint(tmp_path, monkeypatch) -> None:
    # Presentation-only, by construction: canonical_document() is a
    # field-by-field allowlist, so a new NeedsConfig field cannot leak into
    # it. This test is what stops a later refactor from making it leak.
    plain = _config(tmp_path, 'profile = "default"\n')
    baseline = plain.canonical_document()
    styled = _config(
        tmp_path,
        """
profile = "default"

[architecture.c4]
renderer = "mermaid"
enabled-renderers = ["mermaid"]

[architecture.c4.renderers.mermaid]
direction = "right-left"
""",
    )
    assert styled.canonical_document() == baseline
    assert styled.architecture.c4.options_for("mermaid").direction == "right-left"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_config.py -q`
Expected: `AttributeError: 'NeedsConfig' object has no attribute 'architecture'` (and, for the rejection tests, `ConfigurationError` about an unknown top-level key `architecture` — which is the *wrong* message, so those fail too).

- [ ] **Step 3: Add the dataclasses**

In `src/quarto_needs/config.py`, add `"architecture"` to `KNOWN_TOP_LEVEL_KEYS` (after `"graph"`), and add these dataclasses immediately after `GraphSettings`:

```python
@dataclass(frozen=True, slots=True)
class C4RendererSettings:
    """Presentation-only options for one C4 renderer. Never semantic."""

    direction: str = "top-bottom"
    settings: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class C4Settings:
    renderer: str = "mermaid"
    enabled_renderers: tuple[str, ...] = ("mermaid",)
    view_renderers: Mapping[str, str] = MappingProxyType({})
    renderer_settings: Mapping[str, C4RendererSettings] = MappingProxyType({})

    def renderer_for(self, level: str, requested: str | None = None) -> str:
        """The renderer to use, by the documented precedence (Spec 19).

        explicit request -> per-view configuration -> section default ->
        mermaid.
        """
        if requested:
            return requested
        from .c4.model import normalize_level

        canonical = normalize_level(level)
        if canonical is not None and canonical in self.view_renderers:
            return self.view_renderers[canonical]
        return self.renderer or "mermaid"

    def options_for(self, name: str) -> C4RendererSettings:
        return self.renderer_settings.get(name, C4RendererSettings())


@dataclass(frozen=True, slots=True)
class ArchitectureSettings:
    c4: C4Settings = C4Settings()
```

Add the field to `NeedsConfig`, immediately after `graph`:

```python
    architecture: ArchitectureSettings = ArchitectureSettings()
```

`canonical_document()` needs no change — it builds its payload key by key, so the new field is excluded by construction. That is the point, and Step 1's last test pins it.

- [ ] **Step 4: Add the parser**

Add `_parse_architecture` to `src/quarto_needs/config.py`, next to `_parse_graph`:

```python
def _parse_architecture(raw: object) -> ArchitectureSettings:
    """Parse `[architecture]`. Presentation-only: never fingerprinted.

    Renderer names are checked against the live registry so a typo fails at
    configuration-load time with the list of what is actually installed,
    rather than silently producing no diagram later.
    """
    if raw is None:
        return ArchitectureSettings()
    if not isinstance(raw, dict):
        raise _fail("[architecture] must be a table")
    unknown = set(raw) - {"c4"}
    if unknown:
        raise _fail(
            f"[architecture] has unknown keys: {', '.join(sorted(unknown))}"
        )
    return ArchitectureSettings(c4=_parse_c4(raw.get("c4")))


def _parse_c4(raw: object) -> C4Settings:
    from .c4.model import LEVELS, LayoutDirection, normalize_level
    from .c4.renderers import c4_renderer_names

    if raw is None:
        return C4Settings()
    if not isinstance(raw, dict):
        raise _fail("[architecture.c4] must be a table")
    unknown = set(raw) - {"renderer", "enabled-renderers", "views", "renderers"}
    if unknown:
        raise _fail(
            f"[architecture.c4] has unknown keys: {', '.join(sorted(unknown))}"
        )
    known_renderers = c4_renderer_names()

    def renderer_name(value: object, where: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise _fail(f"{where} must be a non-empty string")
        if value not in known_renderers:
            raise _fail(
                f"{where}: {value!r} is not a registered C4 renderer "
                f"(available: {', '.join(known_renderers)})"
            )
        return value

    renderer = (
        renderer_name(raw["renderer"], "[architecture.c4] renderer")
        if "renderer" in raw
        else "mermaid"
    )
    if "enabled-renderers" in raw:
        names = _string_list(raw["enabled-renderers"], "[architecture.c4] enabled-renderers")
        if not names:
            raise _fail(
                "[architecture.c4] enabled-renderers must not be empty; omit the "
                "key to write only the default renderer's artifacts"
            )
        enabled = tuple(
            dict.fromkeys(
                renderer_name(name, "[architecture.c4] enabled-renderers") for name in names
            )
        )
    else:
        enabled = (renderer,)

    views_raw = raw.get("views")
    view_renderers: dict[str, str] = {}
    if views_raw is not None:
        if not isinstance(views_raw, dict):
            raise _fail("[architecture.c4.views] must be a table")
        for level, section in views_raw.items():
            canonical = normalize_level(level)
            if canonical is None:
                raise _fail(
                    f"[architecture.c4.views.{level}]: unknown C4 level "
                    f"(known: {', '.join(LEVELS)})"
                )
            if not isinstance(section, dict):
                raise _fail(f"[architecture.c4.views.{level}] must be a table")
            extra = set(section) - {"renderer"}
            if extra:
                raise _fail(
                    f"[architecture.c4.views.{level}] has unknown keys: "
                    f"{', '.join(sorted(extra))}"
                )
            if "renderer" in section:
                view_renderers[canonical] = renderer_name(
                    section["renderer"], f"[architecture.c4.views.{level}] renderer"
                )

    renderers_raw = raw.get("renderers")
    renderer_settings: dict[str, C4RendererSettings] = {}
    directions = {member.value for member in LayoutDirection}
    if renderers_raw is not None:
        if not isinstance(renderers_raw, dict):
            raise _fail("[architecture.c4.renderers] must be a table")
        for name, section in renderers_raw.items():
            where = f"[architecture.c4.renderers.{name}]"
            renderer_name(name, where)
            if not isinstance(section, dict):
                raise _fail(f"{where} must be a table")
            direction = section.get("direction", "top-bottom")
            if not isinstance(direction, str) or direction not in directions:
                raise _fail(
                    f"{where} direction must be one of: {', '.join(sorted(directions))}"
                )
            settings: dict[str, str] = {}
            for key, value in section.items():
                if key == "direction":
                    continue
                if not isinstance(value, str):
                    raise _fail(f"{where} {key} must be a string")
                settings[key] = value
            renderer_settings[name] = C4RendererSettings(
                direction=direction, settings=MappingProxyType(settings)
            )

    return C4Settings(
        renderer=renderer,
        enabled_renderers=enabled,
        view_renderers=MappingProxyType(view_renderers),
        renderer_settings=MappingProxyType(renderer_settings),
    )
```

Wire it into `load_config`'s returned `NeedsConfig`, next to `graph=_parse_graph(...)`:

```python
        architecture=_parse_architecture(document.get("architecture")),
```

And add `architecture=ArchitectureSettings(),` to `embedded_defaults()`'s `NeedsConfig(...)` call, alongside its existing `graph=GraphSettings(),`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_c4_config.py -q`
Expected: 7 passed.

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass. Pay attention to `tests/test_config.py`: if it pins `KNOWN_TOP_LEVEL_KEYS` as an exact set, add `"architecture"` there too.

```bash
git add src/quarto_needs/config.py tests/test_c4_config.py
git commit -m "feat: configure C4 renderer selection under [architecture.c4]

Presentation-only: canonical_document() builds its payload key by key, so
renderer settings cannot reach the configuration fingerprint."
```

---

### Task 8: The deterministic C4 artifact tree

**Files:**
- Create: `src/quarto_needs/c4/artifacts.py`
- Modify: `src/quarto_needs/cli.py` (the `build` function, around line 103)
- Test: `tests/test_c4_artifacts.py`

**Interfaces:**
- Consumes: `AnalysisSnapshot`; `NeedsConfig`; `project_c4`, `available_scopes`, `C4ProjectionError` (Task 3); `validate_c4_view` (Task 2); `render_c4_view`, `c4_view_fingerprint` (Task 4); `get_c4_renderer`, `UnknownRendererError` (Task 5); `LayoutDirection` (Task 1).
- Produces: `C4_INDEX_SCHEMA_VERSION = "quarto-needs-c4-index-v1"`; `write_c4_artifacts(root: Path, snapshot: AnalysisSnapshot, config: NeedsConfig) -> tuple[Path, ...]` (every path written, sorted); `render_options_for(config: NeedsConfig, renderer: str) -> C4RenderOptions`.

**Layout written under `<root>/.quarto-needs/c4/`:**

```text
.quarto-needs/c4/
├── index.json                          <- the manifest Lua reads first
├── system-context/
│   └── SYS-QUARTO-NEEDS/
│       ├── view.json                   <- quarto-needs-c4-view-v1 (the IR)
│       ├── mermaid.json                <- quarto-needs-c4-render-v1 (what Lua reads)
│       └── mermaid.mmd                 <- the raw source, for external tooling
├── container/…
├── component/…
└── code/…
```

**Why a manifest, when the previous slice deliberately had none.** The old scheme let Lua build `c4-<level>-<id>.json` itself because the id was a filename fragment. A directory *path* segment built from an arbitrary object ID is a path-traversal question, and making Lua sanitize IDs would put an id-transformation rule on the presentation side — exactly what this project's invariant forbids. `index.json` maps a `(level, scopeId)` pair to a relative directory that Python chose, so Lua does a lookup and no transformation at all. It also carries `defaultScopeByLevel`, which is what makes `{{< need-c4 view="system-context" >}}` (no `scope=`) resolvable without Lua deciding anything.

**Directory naming:** `sanitize_identifier(scope_id)`, plus `-<8 hex of sha256(scope_id)>` when the sanitized form differs from the ID. Deterministic, path-safe, and collision-free — but no consumer ever has to reproduce it, because the manifest records it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_artifacts.py`:

```python
from __future__ import annotations

import json

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4.artifacts import (
    C4_INDEX_SCHEMA_VERSION,
    render_options_for,
    write_c4_artifacts,
)
from quarto_needs.c4.model import LayoutDirection
from quarto_needs.config import embedded_defaults, load_config
from quarto_needs.model import EngineeringObject, Relation


def _obj(identifier, *, type, attributes=None, relations=None):
    return EngineeringObject(
        identifier, type, identifier.title(), status="draft",
        attributes=attributes or {}, relations=relations or [],
    )


def _snapshot(*objects):
    result = analyze_objects(list(objects))
    assert result.snapshot is not None
    return result.snapshot


def _fixture():
    return _snapshot(
        _obj("SYS-1", type="system"),
        _obj("ACTOR-1", type="actor", relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
        _obj("SRC-1", type="source-module",
             attributes={"path": "src/p.py", "language": "Python"},
             relations=[Relation("part-of", "SRC-1", "COMP-1")]),
    )


def test_every_level_gets_a_view_and_a_rendered_artifact(tmp_path) -> None:
    write_c4_artifacts(tmp_path, _fixture(), embedded_defaults())
    root = tmp_path / ".quarto-needs" / "c4"
    for relative in (
        "system-context/SYS_1",
        "container/SYS_1",
        "component/CONTAINER_1",
        "code/COMP_1",
    ):
        assert (root / relative / "view.json").is_file(), relative
        assert (root / relative / "mermaid.json").is_file(), relative
    assert (root / "system-context/SYS_1/mermaid.mmd").is_file()
    assert (root / "code/COMP_1/mermaid.md").is_file()


def test_view_json_is_the_versioned_ir_and_render_json_the_render_payload(tmp_path) -> None:
    write_c4_artifacts(tmp_path, _fixture(), embedded_defaults())
    directory = tmp_path / ".quarto-needs" / "c4" / "system-context" / "SYS_1"
    view = json.loads((directory / "view.json").read_text(encoding="utf-8"))
    assert view["schemaVersion"] == "quarto-needs-c4-view-v1"
    assert view["view"]["level"] == "system-context"
    render = json.loads((directory / "mermaid.json").read_text(encoding="utf-8"))
    assert render["schemaVersion"] == "quarto-needs-c4-render-v1"
    assert render["renderer"] == "mermaid"
    assert render["sourceFormat"] == "mermaid"
    # The parity anchor: the render records which IR it came from.
    assert render["viewFingerprint"] == view["fingerprint"]
    assert (directory / "mermaid.mmd").read_text(encoding="utf-8") == render["source"]


def test_the_manifest_maps_levels_and_scopes_to_directories(tmp_path) -> None:
    write_c4_artifacts(tmp_path, _fixture(), embedded_defaults())
    index = json.loads(
        (tmp_path / ".quarto-needs" / "c4" / "index.json").read_text(encoding="utf-8")
    )
    assert index["schemaVersion"] == C4_INDEX_SCHEMA_VERSION
    assert index["defaultRenderer"] == "mermaid"
    # Published so the Lua reader resolves `level="context"` by lookup and
    # never carries an alias rule that could drift from the engine's.
    assert index["levelAliases"] == {"context": "system-context"}
    assert index["defaultScopeByLevel"] == {
        "system-context": "SYS-1",
        "container": "SYS-1",
        "component": "CONTAINER-1",
        "code": "COMP-1",
    }
    entry = next(
        item for item in index["views"]
        if item["level"] == "system-context" and item["scopeId"] == "SYS-1"
    )
    assert entry["directory"] == "system-context/SYS_1"
    assert entry["renderers"] == ["mermaid"]
    assert len(entry["fingerprint"]) == 64
    # Deterministic ordering, never dict insertion order.
    assert index["views"] == sorted(
        index["views"], key=lambda item: (item["level"], item["scopeId"])
    )


def test_default_scope_is_null_when_a_level_has_more_than_one(tmp_path) -> None:
    snapshot = _snapshot(_obj("SYS-A", type="system"), _obj("SYS-B", type="system"))
    write_c4_artifacts(tmp_path, snapshot, embedded_defaults())
    index = json.loads(
        (tmp_path / ".quarto-needs" / "c4" / "index.json").read_text(encoding="utf-8")
    )
    assert index["defaultScopeByLevel"]["system-context"] is None
    assert index["defaultScopeByLevel"]["code"] is None


def test_a_path_dangerous_scope_id_gets_a_safe_stable_directory(tmp_path) -> None:
    snapshot = _snapshot(_obj("SYS/ODD", type="system"))
    write_c4_artifacts(tmp_path, snapshot, embedded_defaults())
    index = json.loads(
        (tmp_path / ".quarto-needs" / "c4" / "index.json").read_text(encoding="utf-8")
    )
    directory = index["views"][0]["directory"]
    # The separator must not survive into the path, and the segment must
    # stay inside the tree.
    assert directory.startswith("system-context/SYS_ODD")
    assert directory.count("/") == 1
    assert ".." not in directory and not directory.startswith("/")
    assert (tmp_path / ".quarto-needs" / "c4" / directory / "view.json").is_file()
    # Deterministic across runs.
    write_c4_artifacts(tmp_path, snapshot, embedded_defaults())
    again = json.loads(
        (tmp_path / ".quarto-needs" / "c4" / "index.json").read_text(encoding="utf-8")
    )
    assert again["views"][0]["directory"] == directory


def test_two_scope_ids_that_sanitize_alike_get_distinct_directories(tmp_path) -> None:
    # "SYS-1" and "SYS.1" both sanitize to "SYS_1"; neither may win the
    # directory and silently overwrite the other's artifacts.
    snapshot = _snapshot(_obj("SYS-1", type="system"), _obj("SYS.1", type="system"))
    write_c4_artifacts(tmp_path, snapshot, embedded_defaults())
    index = json.loads(
        (tmp_path / ".quarto-needs" / "c4" / "index.json").read_text(encoding="utf-8")
    )
    directories = {
        entry["scopeId"]: entry["directory"]
        for entry in index["views"] if entry["level"] == "system-context"
    }
    assert len(set(directories.values())) == 2
    assert all(value.startswith("system-context/SYS_1-") for value in directories.values())


def test_writing_twice_is_byte_identical_and_removes_stale_views(tmp_path) -> None:
    write_c4_artifacts(tmp_path, _fixture(), embedded_defaults())
    root = tmp_path / ".quarto-needs" / "c4"
    first = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*")) if path.is_file()
    }
    write_c4_artifacts(tmp_path, _fixture(), embedded_defaults())
    second = {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*")) if path.is_file()
    }
    assert first == second

    write_c4_artifacts(tmp_path, _snapshot(_obj("SYS-9", type="system")), embedded_defaults())
    assert not (root / "system-context" / "SYS_1").exists()
    assert (root / "system-context" / "SYS_9" / "view.json").is_file()


def test_no_architecture_objects_writes_an_empty_manifest(tmp_path) -> None:
    write_c4_artifacts(tmp_path, _snapshot(_obj("REQ-1", type="system-requirement")), embedded_defaults())
    index = json.loads(
        (tmp_path / ".quarto-needs" / "c4" / "index.json").read_text(encoding="utf-8")
    )
    assert index["views"] == []
    assert index["defaultScopeByLevel"] == {
        "system-context": None, "container": None, "component": None, "code": None,
    }


def test_returned_paths_are_every_file_written_sorted(tmp_path) -> None:
    written = write_c4_artifacts(tmp_path, _fixture(), embedded_defaults())
    assert list(written) == sorted(written)
    assert all(path.is_file() for path in written)
    assert tmp_path / ".quarto-needs" / "c4" / "index.json" in written


def test_render_options_come_from_the_renderers_own_configuration(tmp_path) -> None:
    (tmp_path / ".quarto-needs.toml").write_text(
        'profile = "default"\n\n'
        "[architecture.c4.renderers.mermaid]\n"
        'direction = "left-right"\n'
        'layout = "elk"\n',
        encoding="utf-8",
    )
    options = render_options_for(load_config(tmp_path), "mermaid")
    assert options.direction is LayoutDirection.LEFT_RIGHT
    assert options.setting("layout") == "elk"
    assert render_options_for(embedded_defaults(), "mermaid").direction is LayoutDirection.TOP_BOTTOM


def test_a_projection_that_cannot_be_built_is_skipped_not_fatal(tmp_path) -> None:
    # An optional visualization must never take the whole analysis down.
    snapshot = _snapshot(_obj("SYS-1", type="system"))
    written = write_c4_artifacts(tmp_path, snapshot, embedded_defaults())
    assert any(path.name == "index.json" for path in written)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_artifacts.py -q`
Expected: `ModuleNotFoundError: No module named 'quarto_needs.c4.artifacts'`.

- [ ] **Step 3: Write the implementation**

Create `src/quarto_needs/c4/artifacts.py`:

```python
"""Deterministic on-disk C4 artifacts.

Generated data, never authored data: the whole tree is rebuilt from the
canonical graph on every scan, and nothing in it is a source of engineering
truth (Spec 22).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from typing import Iterable

from ..config import NeedsConfig
from ..snapshot import AnalysisSnapshot
from .model import LEVEL_ALIASES, LEVELS, LayoutDirection, sanitize_identifier
from .projection import C4ProjectionError, available_scopes, project_c4
from .renderers import UnknownRendererError, get_c4_renderer
from .renderers.base import C4RenderOptions
from .serialize import c4_view_fingerprint, render_c4_view
from .validation import validate_c4_view

C4_INDEX_SCHEMA_VERSION = "quarto-needs-c4-index-v1"


def _atomic_text(path: Path, contents: str) -> None:
    """Write via a temporary file in the same directory, then rename.

    Mirrors `graph_output._atomic_text`: a half-written artifact must never
    be observable by a concurrent Quarto render.
    """
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _directory_slugs(scope_ids: Iterable[str]) -> dict[str, str]:
    """Path-safe directory names for one level's scopes, collision-free.

    Path safety is free: `sanitize_identifier` emits only `[A-Za-z0-9_]`, so
    no separator, dot-segment or leading dash can survive into a path
    component whatever the object ID looked like. What is *not* free is
    uniqueness -- sanitization is lossy, and `SYS-1` and `SYS.1` both give
    `SYS_1`. So, exactly as `identifier_map` does, every member of a
    colliding group gets a stable digest of its own ID rather than only the
    second one seen, which would make the layout depend on iteration order.

    No consumer reproduces this: `index.json` records the mapping, which is
    what keeps the Lua reader a pure lookup with no ID rule of its own.
    """
    grouped: dict[str, list[str]] = {}
    for scope_id in scope_ids:
        grouped.setdefault(sanitize_identifier(scope_id), []).append(scope_id)
    slugs: dict[str, str] = {}
    for safe, ids in grouped.items():
        if len(ids) == 1:
            slugs[ids[0]] = safe
            continue
        for scope_id in ids:
            digest = hashlib.sha256(scope_id.encode("utf-8")).hexdigest()[:8]
            slugs[scope_id] = f"{safe}-{digest}"
    return slugs


def render_options_for(config: NeedsConfig, renderer: str) -> C4RenderOptions:
    settings = config.architecture.c4.options_for(renderer)
    return C4RenderOptions(
        direction=LayoutDirection(settings.direction), settings=settings.settings
    )


def write_c4_artifacts(
    root: Path, snapshot: AnalysisSnapshot, config: NeedsConfig
) -> tuple[Path, ...]:
    """Rebuild `<root>/.quarto-needs/c4/` from the canonical graph."""
    base = Path(root) / ".quarto-needs" / "c4"
    # The tree is fully derived, so it is rebuilt rather than patched: a
    # renamed or deleted system must not leave a stale diagram behind.
    shutil.rmtree(base, ignore_errors=True)

    c4 = config.architecture.c4
    written: list[Path] = []
    entries: list[dict[str, object]] = []
    default_scopes: dict[str, str | None] = {}

    for level in LEVELS:
        scopes = available_scopes(snapshot, level)
        default_scopes[level] = scopes[0] if len(scopes) == 1 else None
        slugs = _directory_slugs(scopes)
        for scope_id in scopes:
            try:
                view = project_c4(snapshot, level=level, scope_id=scope_id)
            except C4ProjectionError:
                # A view that cannot be projected is simply not published.
                # An optional visualization never fails the analysis.
                continue
            diagnostics = validate_c4_view(view)
            slug = slugs[scope_id]
            directory = base / level / slug
            view_path = directory / "view.json"
            _atomic_text(view_path, render_c4_view(view, diagnostics=diagnostics))
            written.append(view_path)

            rendered: list[str] = []
            for name in c4.enabled_renderers:
                try:
                    renderer = get_c4_renderer(name)
                except UnknownRendererError:
                    continue
                result = renderer.render(view, render_options_for(config, name))
                payload_path = directory / f"{name}.json"
                _atomic_text(
                    payload_path,
                    json.dumps(
                        result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
                    )
                    + "\n",
                )
                source_path = directory / f"{name}{result.file_extension}"
                _atomic_text(source_path, result.source)
                written.extend((payload_path, source_path))
                rendered.append(name)

            entries.append(
                {
                    "id": view.id,
                    "level": level,
                    "scopeId": scope_id,
                    "directory": f"{level}/{slug}",
                    "fingerprint": c4_view_fingerprint(view),
                    "renderers": rendered,
                }
            )

    index_path = base / "index.json"
    _atomic_text(
        index_path,
        json.dumps(
            {
                "schemaVersion": C4_INDEX_SCHEMA_VERSION,
                "defaultRenderer": c4.renderer,
                # Published so the presentation layer resolves an alias by
                # lookup instead of carrying its own copy of the rule.
                "levelAliases": dict(LEVEL_ALIASES),
                "defaultScopeByLevel": default_scopes,
                "views": sorted(
                    entries, key=lambda item: (item["level"], item["scopeId"])
                ),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    written.append(index_path)
    return tuple(sorted(written))
```

- [ ] **Step 4: Call it from the build**

In `src/quarto_needs/cli.py`'s `build`, immediately after the existing `write_c4_projections(root, result.snapshot)` call (around line 105), add:

```python
        from .c4.artifacts import write_c4_artifacts

        write_c4_artifacts(root, result.snapshot, config)
```

Both writers run for now. Task 11 removes the legacy one — keeping both here is what lets Task 10's Lua switch land as its own reviewable commit without a red intermediate state.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_c4_artifacts.py -q`
Expected: 10 passed.

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass.

```bash
git add src/quarto_needs/c4/artifacts.py src/quarto_needs/cli.py tests/test_c4_artifacts.py
git commit -m "feat: write the deterministic .quarto-needs/c4 artifact tree"
```

---

### Task 9: The `c4` CLI surface

**Files:**
- Create: `src/quarto_needs/c4_cli.py`
- Modify: `src/quarto_needs/cli_entry.py` (one import, one dispatch branch)
- Test: `tests/test_c4_cli.py`

**Interfaces:**
- Consumes: `analyze_project`, `load_config`, `ConfigurationError`; `project_c4`, `available_scopes`, `C4ProjectionError`; `validate_c4_view`; `render_c4_view`; `c4_renderers`, `get_c4_renderer`, `UnknownRendererError`; `write_c4_artifacts`, `render_options_for`.
- Produces: `c4_action(argv: Sequence[str]) -> str | None` (returns `"project"`, `"render"`, or `"renderers"` when `argv`'s top-level command is `c4` and its sub-action is one of those, else `None`); `run_c4_action(root: Path, argv: Sequence[str], action: str) -> int`.

**Command surface (Spec §20, §21, §25):**

```text
quarto-needs c4 renderers [--format text|json]
quarto-needs c4 project --view LEVEL [--scope ID] [--format json|text]
quarto-needs c4 render                                  # rebuild the whole artifact tree
quarto-needs c4 render --view LEVEL [--scope ID] [--renderer NAME]... [--all]
```

`c4 render` with no narrowing flags rebuilds `.quarto-needs/c4/` and prints a summary. With `--view` it prints the rendered source to stdout instead of writing — a narrowed write would have to either wipe the tree (losing the views it did not render) or patch it (losing the guarantee that the tree is a pure function of the graph), and neither is worth it for a debugging aid. `--all` and repeated `--renderer` print each renderer's source under a `# --- renderer: <name>` separator line; this is Spec §39's architectural invariant check, since every backend must consume the identical view.

**Exit codes**, matching the repository's existing CLI conventions: `0` success; `1` the project could not be analyzed (findings printed to stderr, as `variant_cli` does); `2` a usage problem — unknown level, unknown/ambiguous scope, unknown renderer, bad `--format`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_cli.py`:

```python
from __future__ import annotations

import json

import pytest

from quarto_needs.c4_cli import c4_action, run_c4_action

PROJECT = """---
title: "C4 CLI fixture"
---

::: {.need #SYS-1 type="system" status="draft"}
## Fixture system
:::

::: {.need #ACTOR-1 type="actor" status="draft" depends-on="SYS-1"}
## Fixture actor
:::

::: {.need #CONTAINER-1 type="container" status="draft" part-of="SYS-1"}
## Fixture container
:::
"""


@pytest.fixture
def project(tmp_path):
    (tmp_path / "index.qmd").write_text(PROJECT, encoding="utf-8")
    (tmp_path / ".quarto-needs.toml").write_text('profile = "default"\n', encoding="utf-8")
    return tmp_path


def test_c4_action_recognizes_only_its_own_subcommands() -> None:
    assert c4_action(["c4", "project", "--view", "system-context"]) == "project"
    assert c4_action(["c4", "render"]) == "render"
    assert c4_action(["c4", "renderers"]) == "renderers"
    assert c4_action(["--root", "/tmp", "c4", "render"]) == "render"
    assert c4_action(["c4"]) is None
    assert c4_action(["c4", "deploy"]) is None
    assert c4_action(["check"]) is None
    assert c4_action([]) is None


def test_renderers_lists_capabilities_as_text(project, capsys) -> None:
    assert run_c4_action(project, ["c4", "renderers"], "renderers") == 0
    out = capsys.readouterr().out
    assert "renderer" in out and "source" in out and "auto-layout" in out
    assert "mermaid" in out
    assert "limited" in out


def test_renderers_lists_capabilities_as_json(project, capsys) -> None:
    assert (
        run_c4_action(project, ["c4", "renderers", "--format", "json"], "renderers") == 0
    )
    payload = json.loads(capsys.readouterr().out)
    mermaid = next(item for item in payload["renderers"] if item["name"] == "mermaid")
    assert mermaid["capabilities"]["source"] is True
    assert mermaid["capabilities"]["autoLayout"] == "limited"
    assert payload["renderers"] == sorted(payload["renderers"], key=lambda item: item["name"])


def test_project_prints_the_versioned_ir(project, capsys) -> None:
    exit_code = run_c4_action(
        project,
        ["c4", "project", "--view", "system-context", "--scope", "SYS-1", "--format", "json"],
        "project",
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schemaVersion"] == "quarto-needs-c4-view-v1"
    assert payload["view"]["level"] == "system-context"
    assert [element["id"] for element in payload["elements"]] == ["ACTOR-1", "SYS-1"]


def test_project_defaults_to_the_only_scope_at_that_level(project, capsys) -> None:
    assert run_c4_action(project, ["c4", "project", "--view", "container"], "project") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["view"]["scopeId"] == "SYS-1"


def test_project_accepts_the_legacy_context_spelling(project, capsys) -> None:
    assert run_c4_action(project, ["c4", "project", "--view", "context"], "project") == 0
    assert json.loads(capsys.readouterr().out)["view"]["level"] == "system-context"


def test_project_text_format_summarizes_the_view(project, capsys) -> None:
    assert (
        run_c4_action(
            project, ["c4", "project", "--view", "container", "--format", "text"], "project"
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "container" in out and "SYS-1" in out and "CONTAINER-1" in out


def test_an_ambiguous_scope_is_a_usage_error_that_lists_the_candidates(tmp_path, capsys) -> None:
    (tmp_path / "index.qmd").write_text(
        '::: {.need #SYS-A type="system" status="draft"}\n## A\n:::\n\n'
        '::: {.need #SYS-B type="system" status="draft"}\n## B\n:::\n',
        encoding="utf-8",
    )
    assert run_c4_action(tmp_path, ["c4", "project", "--view", "container"], "project") == 2
    error = capsys.readouterr().err
    assert "SYS-A" in error and "SYS-B" in error


def test_unknown_level_scope_and_renderer_are_usage_errors(project, capsys) -> None:
    assert run_c4_action(project, ["c4", "project", "--view", "deployment"], "project") == 2
    assert "deployment" in capsys.readouterr().err
    assert (
        run_c4_action(
            project, ["c4", "project", "--view", "container", "--scope", "NOPE"], "project"
        )
        == 2
    )
    assert "NOPE" in capsys.readouterr().err
    assert (
        run_c4_action(
            project,
            ["c4", "render", "--view", "container", "--renderer", "graphviz"],
            "render",
        )
        == 2
    )
    error = capsys.readouterr().err
    assert "graphviz" in error and "mermaid" in error


def test_render_with_no_narrowing_rebuilds_the_artifact_tree(project, capsys) -> None:
    assert run_c4_action(project, ["c4", "render"], "render") == 0
    assert (project / ".quarto-needs" / "c4" / "index.json").is_file()
    assert (project / ".quarto-needs" / "c4" / "system-context" / "SYS_1" / "mermaid.mmd").is_file()
    assert "index.json" in capsys.readouterr().out


def test_render_with_a_view_prints_the_source_without_writing(project, capsys) -> None:
    assert (
        run_c4_action(
            project, ["c4", "render", "--view", "system-context", "--scope", "SYS-1"], "render"
        )
        == 0
    )
    assert capsys.readouterr().out.startswith("C4Context")
    assert not (project / ".quarto-needs" / "c4").exists()


def test_render_all_prints_every_renderer_from_the_same_view(project, capsys) -> None:
    assert (
        run_c4_action(project, ["c4", "render", "--view", "system-context", "--all"], "render")
        == 0
    )
    out = capsys.readouterr().out
    assert "# --- renderer: mermaid" in out
    assert "C4Context" in out


def test_a_project_that_cannot_be_analyzed_exits_one(tmp_path, capsys) -> None:
    (tmp_path / "index.qmd").write_text(
        '::: {.need #SYS-1 type="system" status="draft" part-of="GHOST"}\n## A\n:::\n',
        encoding="utf-8",
    )
    exit_code = run_c4_action(tmp_path, ["c4", "project", "--view", "container"], "project")
    assert exit_code in (1, 2)
    assert capsys.readouterr().err != ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_cli.py -q`
Expected: `ModuleNotFoundError: No module named 'quarto_needs.c4_cli'`.

- [ ] **Step 3: Write the implementation**

Create `src/quarto_needs/c4_cli.py`:

```python
"""The `quarto-needs c4` command family.

Follows the repository's established shape for a new command family: a
narrow `<x>_action` detector plus a `run_<x>_action` runner, intercepted in
`cli_entry._dispatch` before the legacy argparse CLI ever sees the argument
vector -- the same pattern `oslc_cli`, `variant_cli`, `migration_cli` and
`interchange_cli` already use.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .analysis import analyze_project
from .c4.artifacts import render_options_for, write_c4_artifacts
from .c4.projection import C4ProjectionError, available_scopes, project_c4
from .c4.renderers import UnknownRendererError, c4_renderer_names, c4_renderers, get_c4_renderer
from .c4.serialize import c4_view_document, render_c4_view
from .c4.validation import validate_c4_view
from .config import ConfigurationError, load_config

_ACTIONS = ("project", "render", "renderers")


def _top_level_command(argv: Sequence[str]) -> tuple[str, int] | None:
    """The first positional token and its index, skipping global flags."""
    values = list(argv)
    index = 0
    while index < len(values):
        value = values[index]
        if value == "--root":
            index += 2
            continue
        if value.startswith("--root="):
            index += 1
            continue
        if value.startswith("-"):
            index += 1
            continue
        return value, index
    return None


def c4_action(argv: Sequence[str]) -> str | None:
    found = _top_level_command(argv)
    if found is None or found[0] != "c4":
        return None
    values = list(argv)
    for candidate in values[found[1] + 1:]:
        if candidate.startswith("-"):
            continue
        return candidate if candidate in _ACTIONS else None
    return None


def _parser(action: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"quarto-needs c4 {action}", add_help=False)
    parser.add_argument("--root")
    if action == "renderers":
        parser.add_argument("--format", choices=("text", "json"), default="text")
        return parser
    parser.add_argument("--view")
    parser.add_argument("--scope")
    if action == "project":
        parser.add_argument("--format", choices=("text", "json"), default="json")
    else:
        parser.add_argument("--renderer", action="append", default=[])
        parser.add_argument("--all", action="store_true")
    return parser


def _parse(action: str, argv: Sequence[str]) -> argparse.Namespace | None:
    values = [
        value
        for value in list(argv)
        if value not in ("c4", action)
    ]
    try:
        namespace, unknown = _parser(action).parse_known_args(values)
    except SystemExit:
        return None
    if unknown:
        print(f"c4 {action}: unexpected argument(s): {', '.join(unknown)}", file=sys.stderr)
        return None
    return namespace


def _resolve_scope(snapshot, level: str, requested: str | None) -> str | None:
    scopes = available_scopes(snapshot, level)
    if requested is not None:
        if requested not in scopes:
            print(
                f"c4: {requested!r} cannot scope a {level!r} view "
                f"(candidates: {', '.join(scopes) or 'none'})",
                file=sys.stderr,
            )
            return None
        return requested
    if len(scopes) == 1:
        return scopes[0]
    print(
        f"c4: --scope is required for a {level!r} view "
        f"(candidates: {', '.join(scopes) or 'none'})",
        file=sys.stderr,
    )
    return None


def _renderers_command(argv: Sequence[str]) -> int:
    args = _parse("renderers", argv)
    if args is None:
        return 2
    entries = [
        {"name": renderer.name, "capabilities": renderer.capabilities.to_dict()}
        for renderer in c4_renderers()
    ]
    if args.format == "json":
        print(json.dumps({"renderers": entries}, indent=2, sort_keys=True))
        return 0
    print(f"{'renderer':<14} {'source':<8} {'svg':<8} {'auto-layout'}")
    print("-" * 46)
    for entry in entries:
        capabilities = entry["capabilities"]
        print(
            f"{entry['name']:<14} "
            f"{'yes' if capabilities['source'] else 'no':<8} "
            f"{'yes' if capabilities['svg'] else 'no':<8} "
            f"{capabilities['autoLayout']}"
        )
    return 0


def run_c4_action(root: Path, argv: Sequence[str], action: str) -> int:
    if action == "renderers":
        # Capability reporting is about the installation, not the project,
        # so it deliberately does not analyze anything.
        return _renderers_command(argv)

    args = _parse(action, argv)
    if args is None:
        return 2
    try:
        config = load_config(root)
        result = analyze_project(root, config=config)
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    if result.snapshot is None:
        from .cli import print_findings

        print_findings(result.findings, stream=sys.stderr)
        return 1
    snapshot = result.snapshot

    if action == "render" and not args.view:
        written = write_c4_artifacts(root, snapshot, config)
        for path in written:
            print(path.relative_to(root).as_posix())
        return 0

    if not args.view:
        print("c4 project: --view is required", file=sys.stderr)
        return 2

    scope_id = _resolve_scope(snapshot, args.view, args.scope)
    if scope_id is None:
        return 2
    try:
        view = project_c4(snapshot, level=args.view, scope_id=scope_id)
    except C4ProjectionError as error:
        print(f"c4: {error} [{error.code}]", file=sys.stderr)
        return 2
    diagnostics = validate_c4_view(view)

    if action == "project":
        if args.format == "json":
            print(render_c4_view(view, diagnostics=diagnostics), end="")
            return 0
        document = c4_view_document(view, diagnostics=diagnostics)
        print(f"{document['view']['level']} view of {document['view']['scopeId']}")
        for element in document["elements"]:
            parent = f" in {element['parentId']}" if element["parentId"] else ""
            print(f"  {element['id']} ({element['role']}){parent}")
        for relationship in document["relationships"]:
            print(
                f"  {relationship['sourceId']} -> {relationship['targetId']} "
                f"({relationship['relationType']})"
            )
        for item in document["diagnostics"]:
            print(f"  {item['code']} {item['severity']}: {item['message']}")
        return 0

    names = list(args.renderer)
    if args.all:
        names = list(c4_renderer_names())
    if not names:
        names = [config.architecture.c4.renderer_for(args.view)]
    try:
        selected = [get_c4_renderer(name) for name in names]
    except UnknownRendererError as error:
        print(f"c4: {error} [{error.code}]", file=sys.stderr)
        return 2
    for renderer in selected:
        rendered = renderer.render(view, render_options_for(config, renderer.name))
        if len(selected) > 1:
            print(f"# --- renderer: {renderer.name}")
        print(rendered.source, end="")
        for item in rendered.diagnostics:
            if item.severity != "info":
                print(f"{item.code} {item.severity}: {item.message}", file=sys.stderr)
    return 0
```

- [ ] **Step 4: Wire it into the entry point**

In `src/quarto_needs/cli_entry.py`, add the import beside the other `*_cli` imports:

```python
from .c4_cli import c4_action, run_c4_action
```

and add the branch inside `_dispatch`, immediately before the `lsp` branch:

```python
    c4 = c4_action(values)
    if c4 is not None:
        return run_c4_action(_root(values), values, c4)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_c4_cli.py -q`
Expected: 13 passed.

- [ ] **Step 6: Verify the installed entry point end to end**

```bash
python -m quarto_needs.cli_entry c4 renderers
python -m quarto_needs.cli_entry --root examples/quarto-needs c4 project --view system-context --scope SYS-QUARTO-NEEDS | head -20
```

Expected: a capability table, then a `quarto-needs-c4-view-v1` document naming `SYS-QUARTO-NEEDS`, `ACTOR-ENGINEER`, `EXT-GITHUB`, `EXT-OSLC`.

- [ ] **Step 7: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass.

```bash
git add src/quarto_needs/c4_cli.py src/quarto_needs/cli_entry.py tests/test_c4_cli.py
git commit -m "feat: add the quarto-needs c4 project/render/renderers CLI"
```

---

### Task 10: `need-c4` reads the new artifact tree

**Files:**
- Modify: `_extensions/quarto-needs/c4.lua` (rewritten)
- Modify: `tests/fixtures/c4/index.qmd`, `tests/fixtures/c4/missing.qmd`
- Modify: `tests/test_quarto_views.py` (the two `need-c4` tests, around lines 534-570)
- Test: `tests/test_quarto_views.py` (extended with a renderer-override and an alias test)

**Interfaces:**
- Consumes: `.quarto-needs/c4/index.json` (`quarto-needs-c4-index-v1`) and `<directory>/<renderer>.json` (`quarto-needs-c4-render-v1`), both written by Task 8.
- Produces: the `need-c4` shortcode accepting `view=`/`scope=`/`renderer=` with `level=`/`root=` as accepted aliases.

**Lua stays a pure reader.** It resolves nothing it could get wrong: the level alias table, the default scope for a level, and the default renderer all come out of `index.json`, which Python wrote. Lua does a lookup, reads a file, and hands text to an existing helper. It never maps a role to a macro and never decides what a boundary is.

- [ ] **Step 1: Rewrite the shortcode**

Replace the whole of `_extensions/quarto-needs/c4.lua` with:

```lua
-- The `need-c4` shortcode: a pure reader of pre-rendered C4 artifacts.
--
-- Every C4 decision -- which elements are in a view, what role each one
-- has, which macro draws it, what a boundary means -- was made in Python
-- (src/quarto_needs/c4/) and written to .quarto-needs/c4/ by
-- write_c4_artifacts. This module resolves nothing on its own: the level
-- aliases, the default scope for a level and the default renderer all come
-- out of index.json, so there is no rule here that can drift from the
-- engine's.
local M = {}

local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local views = dofile(script_dir() .. "views.lua")

local function project_dir()
  local ok, directory = pcall(function() return quarto.project.directory end)
  if ok and type(directory) == "string" and directory ~= "" then return directory end
  local input = PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]
  return input and input:match("(.*/)") or "."
end

local function read_json(path)
  local file = io.open(path, "rb")
  if not file then return nil, "C4 artifact not found: " .. path end
  local contents = file:read("*a"); file:close()
  local ok, decoded = pcall(pandoc.json.decode, contents)
  if not ok or type(decoded) ~= "table" then
    return nil, "C4 artifact is not valid JSON: " .. path
  end
  return decoded
end

local function load_index(root)
  return read_json(pandoc.path.join({root, ".quarto-needs", "c4", "index.json"}))
end

local function resolve_entry(index, level, scope)
  local canonical = level
  if type(index.levelAliases) == "table" and index.levelAliases[level] then
    canonical = index.levelAliases[level]
  end
  if scope == "" then
    local defaults = index.defaultScopeByLevel
    if type(defaults) ~= "table" or type(defaults[canonical]) ~= "string" then
      return nil, canonical
    end
    scope = defaults[canonical]
  end
  for _, entry in ipairs(index.views or {}) do
    if entry.level == canonical and entry.scopeId == scope then return entry, canonical end
  end
  return nil, canonical
end

function M.render_shortcode(args, kwargs)
  views.ensure_assets()
  -- `view=`/`scope=` are the documented spelling; `level=`/`root=` are the
  -- spelling this shortcode shipped with and stay accepted.
  local level = views.kwarg(kwargs, "view", "")
  if level == "" then level = views.kwarg(kwargs, "level", "") end
  local scope = views.kwarg(kwargs, "scope", "")
  if scope == "" then scope = views.kwarg(kwargs, "root", "") end
  local renderer = views.kwarg(kwargs, "renderer", "")

  if level == "" then
    return views.warning(views.tr(
      "need-c4 requires a view (system-context, container, component or code).",
      "need-c4 requer um view (system-context, container, component ou code)."
    ))
  end

  local root = project_dir()
  local index, index_error = load_index(root)
  if not index then
    quarto.log.warning(index_error)
    return views.warning(index_error)
  end

  local entry, canonical = resolve_entry(index, level, scope)
  if not entry then
    local message = "C4 view not found: " .. canonical ..
      (scope ~= "" and (" scoped to " .. scope) or " (no unique scope; add scope=)")
    quarto.log.warning(message)
    return views.warning(message)
  end

  if renderer == "" then renderer = index.defaultRenderer or "mermaid" end
  local payload_path = pandoc.path.join({
    root, ".quarto-needs", "c4", entry.directory, renderer .. ".json",
  })
  local payload, payload_error = read_json(payload_path)
  if not payload or type(payload.source) ~= "string" then
    local message = payload_error or ("C4 render not found: " .. payload_path)
    quarto.log.warning(message)
    return views.warning(message)
  end

  if payload.sourceFormat == "markdown" then
    return pandoc.read(payload.source, "markdown").blocks
  end

  local description = views.tr("Architecture diagram", "Diagrama de arquitetura")
  if payload.sourceFormat == "mermaid" then
    if views.is_html_format() then
      local svg = views.mermaid_inline_svg(payload.source, description, "need-c4-figure")
      if svg then return pandoc.RawBlock("html", svg) end
    end
    local image_name, render_error = views.render_mermaid_asset(payload.source, "quarto-needs-c4")
    if image_name then
      return pandoc.Para({
        pandoc.Image({pandoc.Str(description)}, image_name, "",
          pandoc.Attr("", {"need-c4-figure"}, {role = "img"}))
      })
    end
    quarto.log.warning(render_error or "c4 render failed")
    return views.warning(views.tr(
      "need-c4 could not render the diagram.",
      "need-c4 não conseguiu renderizar o diagrama."
    ))
  end

  -- A backend whose source this document cannot draw inline is still worth
  -- publishing as reviewable source. Plan B's renderers land here without
  -- another Lua change.
  return pandoc.CodeBlock(payload.source, pandoc.Attr("", {payload.sourceFormat or "text"}, {}))
end

return M
```

- [ ] **Step 2: Update the fixtures so both spellings are exercised**

`tests/fixtures/c4/index.qmd` — switch the shortcode line to the documented spelling:

```qmd
{{< need-c4 view="system-context" scope="SYS-1" >}}
```

`tests/fixtures/c4/missing.qmd` — deliberately keep the legacy spelling, so the alias path is covered by a real render:

```qmd
{{< need-c4 root="MISSING" level="context" >}}
```

- [ ] **Step 3: Update and extend the Quarto render tests**

In `tests/test_quarto_views.py`, change the artifact assertion in `test_need_c4_renders_a_context_diagram` from

```python
    assert (
        project / ".quarto-needs" / "graphs" / "c4-context-SYS-1.json"
    ).is_file()
```

to

```python
    assert (project / ".quarto-needs" / "c4" / "index.json").is_file()
    assert (
        project / ".quarto-needs" / "c4" / "system-context" / "SYS_1" / "mermaid.json"
    ).is_file()
```

and add two tests beside it:

```python
@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_need_c4_accepts_the_legacy_root_and_level_spelling(tmp_path: Path):
    """`root=`/`level=` keep working; only the documented spelling changed."""
    project = build_c4_fixture_project(tmp_path)
    (project / "legacy.qmd").write_text(
        '---\ntitle: "Legacy spelling"\n---\n\n'
        '{{< need-c4 root="SYS-1" level="context" >}}\n',
        encoding="utf-8",
    )
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    html = (project / "_site" / "legacy.html").read_text(encoding="utf-8")
    assert "need-c4-figure" in html
    assert "<svg" in html.lower()


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_need_c4_resolves_the_only_scope_when_none_is_given(tmp_path: Path):
    """`view=` alone works when the level has exactly one scope."""
    project = build_c4_fixture_project(tmp_path)
    (project / "implicit.qmd").write_text(
        '---\ntitle: "Implicit scope"\n---\n\n'
        '{{< need-c4 view="system-context" >}}\n',
        encoding="utf-8",
    )
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    html = (project / "_site" / "implicit.html").read_text(encoding="utf-8")
    assert "need-c4-figure" in html
    assert "Fixture system" in html
```

- [ ] **Step 4: Run the Quarto view tests**

Run: `python -m pytest tests/test_quarto_views.py -q -k c4`
Expected: 4 passed (or skipped, if `quarto` is not on PATH — check with `which quarto` first; if it is missing, say so explicitly rather than reporting a pass).

- [ ] **Step 5: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass.

```bash
git add _extensions/quarto-needs/c4.lua tests/fixtures/c4 tests/test_quarto_views.py
git commit -m "feat: read the c4 artifact tree from need-c4, with view=/scope= spelling

level=/root= stay accepted, and Lua resolves nothing itself: the level
aliases, per-level default scope and default renderer all come from
index.json."
```

---

### Task 11: Retire the pre-IR C4 modules

**Files:**
- Delete: `src/quarto_needs/c4_projection.py`, `src/quarto_needs/c4_render.py`
- Delete: `tests/test_c4_projection.py`, `tests/test_c4_render.py`
- Modify: `src/quarto_needs/graph_output.py` (remove `write_c4_projections`, lines 478-525)
- Modify: `src/quarto_needs/cli.py` (remove the legacy call)
- Modify: `src/quarto_needs/c4/artifacts.py` (clean up legacy artifacts on upgrade)
- Modify: `tests/test_graph_assets.py` (remove the three `write_c4_projections` tests, lines ~356-422)
- Modify: `tests/test_c4_artifacts.py` (one added test)

**Where the deleted tests' coverage now lives** — check each off before deleting, so nothing is lost silently:

| Deleted assertion | Replacement |
| --- | --- |
| `test_c4_projection.py` — per-level focus type, neighborhood bounds, `C4ViewError` cases | `tests/test_c4_projection_ir.py` (Task 3), all levels plus `code` |
| `test_c4_render.py` — macro shapes, both boundary types, technology labels | `tests/test_c4_renderer_mermaid.py` (Task 6) |
| `test_c4_render.py` — Mermaid escaping (falsified) | `test_labels_are_escaped_against_mermaid_syntax` (Task 6) |
| `test_c4_render.py` — Code-level table, never Mermaid | `test_code_level_renders_a_markdown_table_and_never_mermaid` (Task 6) |
| `test_c4_render.py` — children authored via `decomposes` | `test_container_level_resolves_children_authored_as_decomposes` (Task 3) |
| `test_graph_assets.py` — per-type file matrix, payload shape, no-op case | `tests/test_c4_artifacts.py` (Task 8) |

- [ ] **Step 1: Add the legacy-cleanup test**

Add to `tests/test_c4_artifacts.py`:

```python
def test_stale_pre_ir_artifacts_are_removed_on_upgrade(tmp_path) -> None:
    # A project built by an older version keeps c4-*.json files in the
    # graphs directory. Nothing reads them any more, so leave none behind.
    graphs = tmp_path / ".quarto-needs" / "graphs"
    graphs.mkdir(parents=True)
    (graphs / "c4-context-SYS-1.json").write_text("{}", encoding="utf-8")
    (graphs / "default.json").write_text("{}", encoding="utf-8")
    write_c4_artifacts(tmp_path, _fixture(), embedded_defaults())
    assert not (graphs / "c4-context-SYS-1.json").exists()
    # Only the C4 files go; the general graph projections are not ours.
    assert (graphs / "default.json").is_file()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_c4_artifacts.py::test_stale_pre_ir_artifacts_are_removed_on_upgrade -q`
Expected: FAIL — the stale file still exists.

- [ ] **Step 3: Add the cleanup**

In `src/quarto_needs/c4/artifacts.py`'s `write_c4_artifacts`, immediately after the `shutil.rmtree(base, ignore_errors=True)` line:

```python
    # Artifacts written by the pre-IR implementation, which put one flat
    # file per view in the graphs directory. Nothing reads them now.
    legacy = Path(root) / ".quarto-needs" / "graphs"
    if legacy.is_dir():
        for stale in sorted(legacy.glob("c4-*.json")):
            stale.unlink()
```

Run: `python -m pytest tests/test_c4_artifacts.py -q` — expected: 11 passed.

- [ ] **Step 4: Delete the legacy writer and its call**

Delete `write_c4_projections` from `src/quarto_needs/graph_output.py` (the whole function, lines 478-525).

In `src/quarto_needs/cli.py`'s `build`, delete these three lines:

```python
        from .graph_output import write_c4_projections

        write_c4_projections(root, result.snapshot)
```

leaving the `write_c4_artifacts(root, result.snapshot, config)` call Task 8 added.

- [ ] **Step 5: Delete the superseded modules and tests**

```bash
git rm src/quarto_needs/c4_projection.py src/quarto_needs/c4_render.py \
       tests/test_c4_projection.py tests/test_c4_render.py
```

Remove the three `write_c4_projections` tests from `tests/test_graph_assets.py` (`test_write_c4_projections_writes_one_file_per_system_and_container_level`, `test_write_c4_projections_writes_a_code_table_for_every_component`, `test_write_c4_projections_is_a_no_op_when_there_are_no_systems_or_containers`, around lines 356-422).

- [ ] **Step 6: Prove nothing still references the old names**

```bash
grep -rn "c4_projection\|c4_render\|write_c4_projections\|C4ViewError\|c4_mermaid_source\|c4_code_table_markdown" \
  src tests _extensions examples docs --include='*.py' --include='*.lua' --include='*.qmd' --include='*.md' \
  | grep -v "docs/superpowers" | grep -v "docs/phase-6-architecture-c4.md"
```

Expected: no output. (`docs/superpowers/` holds historical plans and `docs/phase-6-architecture-c4.md` is rewritten in Task 12; both are excluded deliberately.)

- [ ] **Step 7: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass.

Also rebuild the self-hosted example end to end, because it is the only place with real content at every level:

```bash
python -m quarto_needs.cli_entry --root examples/quarto-needs scan
ls examples/quarto-needs/.quarto-needs/c4
```

Expected: `index.json`, `system-context/`, `container/`, `component/`, `code/`; and no `c4-*.json` left in `examples/quarto-needs/.quarto-needs/graphs/`.

```bash
git add -A src/quarto_needs tests
git commit -m "refactor: retire the pre-IR C4 projection and Mermaid modules

Every assertion they carried now lives against the IR: projection contracts
in test_c4_projection_ir.py, Mermaid output in test_c4_renderer_mermaid.py,
artifact layout in test_c4_artifacts.py."
```

---

### Task 12: Documentation

**Files:**
- Rewrite: `docs/phase-6-architecture-c4.md`
- Create: `docs/manual/c4-architecture-views.qmd`, `docs/manual/c4-architecture-views.pt-BR.qmd`
- Modify: `docs/manual/_quarto.yml`, `docs/manual/_quarto-pt-BR.yml` (add the new page to the book)
- Modify: `ARCHITECTURE.md` (the canonical-pipeline block)
- Modify: `docs/ROADMAP.md` (the Phase 6 entry)

- [ ] **Step 1: Rewrite the phase document**

Rewrite `docs/phase-6-architecture-c4.md` in the shape the existing phase documents use — Status, why this reuses existing machinery, what is implemented, what was learned, known limitations, what is intentionally not implemented, regression coverage. It must state, at minimum:

- the flow `canonical graph -> C4 IR (quarto-needs-c4-view-v1) -> renderer adapter -> source`, and that the branch point is *after* the projection;
- that renderer configuration is presentation-only and cannot reach the configuration fingerprint;
- the renderer-selection precedence: shortcode `renderer=` → `[architecture.c4.views.<level>]` → `[architecture.c4] renderer` → `mermaid`;
- the three inherited limitations from this plan's "Inherited limitations" section, unchanged;
- the two user-visible changes from Task 6 (readable identifiers, changed code-table columns);
- that Mermaid is the zero-configuration default and that its C4 *layout* is less sophisticated than the alternatives — a rendering limitation, not a semantic one (Spec §50);
- the difference between `need-graph` and `need-c4` (Spec §44): `need-graph` shows some portion of the engineering graph, while `need-c4` interprets architecture-role nodes through the formal C4 projection rules — not every generic graph is a C4 graph, and both continue to work unchanged;
- that `fallback-renderer` (Spec §26) is deliberately absent because nothing in this milestone can make a registered renderer unavailable, and that it arrives with binary execution;
- that the `C4Renderer` protocol takes a `C4View` and returns text, which is all a future native ELK/SVG backend would need (Spec §33) — the interfaces do not prevent it, and this milestone deliberately does not build it;
- that Structurizr, PlantUML and D2 are Plan B, and that no adapter executes an external binary in this milestone.

- [ ] **Step 2: Write the manual page**

Create `docs/manual/c4-architecture-views.qmd` covering, in the manual's existing voice: the C4 semantic model and the type→role mapping; the four view levels and what each includes; authoring (nothing new — `part-of` on the child, `technology`/`description`/`path`/`language` attributes); the `need-c4` shortcode with both spellings; renderer selection and precedence; `[architecture.c4]` configuration with a full worked example; the CLI (`c4 project`, `c4 render`, `c4 renderers`); the generated artifact tree; and the diagnostic codes `C4001`-`C4010` with one sentence each.

State explicitly, as Spec §49 requires: *different renderers may produce different geometry and styling while representing the same architecture semantics.*

Mirror it to `docs/manual/c4-architecture-views.pt-BR.qmd` — translated prose, identical structure and identical code samples. Add both to their respective `_quarto*.yml` chapter lists.

- [ ] **Step 3: Update ARCHITECTURE.md**

In the canonical-pipeline block, add the C4 branch after the existing graph lines:

```text
AnalysisSnapshot -> C4View (quarto-needs-c4-view-v1)
                          |
                          +--> MermaidRenderer  -> .mmd / Markdown table
                          +--> (Plan B: Structurizr / PlantUML / D2)
```

with one sentence: the branch point is after the semantic projection, so a renderer never re-derives architecture meaning.

- [ ] **Step 4: Update the roadmap**

In `docs/ROADMAP.md`, extend the Phase 6 heading's parenthetical to name the second slice: the renderer-independent IR, the versioned `quarto-needs-c4-view-v1` boundary, the renderer registry, and the `c4` CLI.

- [ ] **Step 5: Verify the manual still builds**

```bash
quarto render docs/manual --to html
```

Expected: a clean build including the new chapter. If `quarto` is not installed, say so rather than claiming the build passed.

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass (`tests/test_localization.py` and any docs-parity test will check the pt-BR mirror).

```bash
git add docs ARCHITECTURE.md
git commit -m "docs: document the C4 IR, renderer selection, CLI, and artifact tree"
```

---
