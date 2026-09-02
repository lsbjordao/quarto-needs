# Phase 6c — Structurizr, C4-PlantUML and D2 Backends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Prerequisite:** `docs/superpowers/plans/2026-09-02-phase-6b-c4-ir-and-renderer-boundary.md` must be complete and merged. This plan adds adapters behind the boundary that plan built; it changes no C4 semantics.

**Goal:** Add Structurizr DSL, C4-PlantUML and D2 as first-class C4 rendering backends, prove all four backends are generated from one identical IR fingerprint, and demonstrate the whole thing on Quarto-Needs' own truthful architecture.

**Architecture:** Each backend is one module under `src/quarto_needs/c4/renderers/`, registered in the existing registry, consuming only a `C4View`. Nothing outside `c4/renderers/` changes except the IR gaining scope ancestors (Task 1, needed because Structurizr and D2 require a grammatical parent for a nested element), the self-hosted example, and documentation. Golden files pin each backend's exact output; a parity test proves every backend's artifact records the same `viewFingerprint`.

**Tech Stack:** Python 3.10+ (stdlib only), Structurizr DSL, C4-PlantUML via PlantUML's bundled stdlib (`!include <C4/...>` — no network), D2, Quarto/Lua for the showcase page.

**Spec:** `docs/superpowers/specs/2026-09-02-multi-backend-c4-projections.md` (sections 11-13, 16, 22, 30, 35-42, 50; Tasks 6-8, 11, 12)

## Global Constraints

- **Source generation only.** No adapter runs a subprocess. `RendererCapabilities.svg` stays `False` for all three new backends. Spec §47's process trust boundary is not opened by this plan. (Owner decision 2.)
- **Offline (Spec §48).** No generated source may contain a remote include, a SaaS URL, or a hosted renderer reference. C4-PlantUML is emitted as `!include <C4/…>`, which resolves from PlantUML's own bundled standard library — never as `!includeurl https://…`.
- **No renderer may import the engineering graph.** `tests/test_c4_renderer_registry.py::test_no_renderer_module_may_import_the_engineering_graph` already enforces this; every new module is covered automatically.
- **Semantic edge direction is never reversed for layout convenience** (Spec §31). `A depends-on B` renders as an arrow from A to B in every backend; only orientation is configurable.
- **Renderer options remain presentation-only.** Changing `direction` or `layout` must not change any view's fingerprint. Task 5 pins this.
- **Every commit leaves the full `pytest` suite green.** Run `python -m pytest -q` before each commit. Do not rely on GitHub Actions — the project's Actions quota is exhausted.
- **TDD throughout**, same rhythm as Plan A: failing test, read the real failure, minimal implementation, green, commit.
- **Goldens are never auto-rewritten** (Spec §37). A mismatch fails. Regeneration is an explicit, reviewed manual step.

---

### Task 1: Scope ancestors in the IR

**Files:**
- Modify: `src/quarto_needs/c4/model.py` (add `ancestors` to `C4View`)
- Modify: `src/quarto_needs/c4/projection.py` (populate it)
- Modify: `src/quarto_needs/c4/serialize.py` (emit it)
- Modify: `schemas/c4-view-v1.schema.json` (declare it)
- Modify: `tests/test_c4_model.py`, `tests/test_c4_projection_ir.py`, `tests/test_c4_serialize.py`

**Why this is needed and why it is still v1.** Structurizr DSL and D2 both require a nested element to sit inside a declared parent: `container` is only grammatical inside `softwareSystem`. A component-level view's scope *is* a container, and its parent system is deliberately not one of the view's `elements` (Spec §30 — a component view shows the container's boundary and its components, not the system). Ancestors are therefore carried separately: they are context for a renderer that needs a grammatical parent, never content of the view. Mermaid ignores them; `validate_c4_view` ignores them; `children_of` ignores them.

`quarto-needs-c4-view-v1` gains a field rather than becoming v2 because Plan A and this plan are one milestone and the boundary has not shipped to users. **If Plan A has already been released independently, make this `quarto-needs-c4-view-v2` instead** and add the version to the schema `const`, the CLI output and the golden files.

**Interfaces:**
- Produces: `C4View.ancestors: tuple[C4Element, ...] = ()` — the scope's containment chain, outermost first, each with its real `parent_id`; `C4View.to_dict()` gains an `"ancestors"` key.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_c4_model.py`:

```python
def test_ancestors_are_context_not_content() -> None:
    system = _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM)
    container = _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1")
    component = _element("COMP-1", C4ElementRole.COMPONENT, parent_id="CONTAINER-A")
    view = C4View(
        id="component-CONTAINER-A",
        level="component",
        scope_id="CONTAINER-A",
        elements=(component, container),
        relationships=(),
        ancestors=(system,),
    )
    assert view.ancestors == (system,)
    # Ancestors are not elements: lookup, children and the payload's
    # element list all ignore them.
    assert view.element("SYS-1") is None
    assert view.children_of("SYS-1") == ()
    assert [item["id"] for item in view.to_dict()["elements"]] == ["COMP-1", "CONTAINER-A"]
    assert [item["id"] for item in view.to_dict()["ancestors"]] == ["SYS-1"]


def test_ancestors_default_to_empty() -> None:
    view = C4View(id="v", level="system-context", scope_id="SYS-1", elements=(), relationships=())
    assert view.ancestors == ()
    assert view.to_dict()["ancestors"] == []
```

Add to `tests/test_c4_projection_ir.py`:

```python
def test_the_scopes_containment_chain_is_carried_as_ancestors() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
        _obj("SRC-1", type="source-module", relations=[Relation("part-of", "SRC-1", "COMP-1")]),
    )
    code = project_c4(snapshot, level="code", scope_id="COMP-1")
    assert [element.id for element in code.ancestors] == ["SYS-1", "CONTAINER-1"]
    assert code.ancestors[1].parent_id == "SYS-1"
    # Still not in the view proper.
    assert _ids(code) == ["COMP-1", "SRC-1"]

    component = project_c4(snapshot, level="component", scope_id="CONTAINER-1")
    assert [element.id for element in component.ancestors] == ["SYS-1"]

    context = project_c4(snapshot, level="system-context", scope_id="SYS-1")
    assert context.ancestors == ()


def test_ancestors_resolve_from_decomposes_authoring_too() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system", relations=[Relation("decomposes", "SYS-1", "CONTAINER-1")]),
        _obj("CONTAINER-1", type="container", relations=[Relation("decomposes", "CONTAINER-1", "COMP-1")]),
        _obj("COMP-1", type="component"),
    )
    view = project_c4(snapshot, level="code", scope_id="COMP-1")
    assert [element.id for element in view.ancestors] == ["SYS-1", "CONTAINER-1"]


def test_an_ancestor_cycle_cannot_hang_the_projection() -> None:
    # ARC001 already rejects this as a graph error; the projection must not
    # spin on it regardless of the active profile.
    snapshot = _snapshot(
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "COMP-1")]),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
    )
    view = project_c4(snapshot, level="component", scope_id="CONTAINER-1")
    assert [element.id for element in view.ancestors] == ["COMP-1"]
```

Add to `tests/test_c4_serialize.py`:

```python
def test_ancestors_are_serialized_and_change_the_fingerprint() -> None:
    nested = analyze_objects([
        _obj("SYS-1", type="system"),
        _obj("CONTAINER-1", type="container", relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
    ])
    assert nested.snapshot is not None
    view = project_c4(nested.snapshot, level="component", scope_id="CONTAINER-1")
    document = c4_view_document(view)
    Draft202012Validator(SCHEMA).validate(document)
    assert [item["id"] for item in document["ancestors"]] == ["SYS-1"]

    orphaned = analyze_objects([
        _obj("CONTAINER-1", type="container"),
        _obj("COMP-1", type="component", relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
    ])
    assert orphaned.snapshot is not None
    assert c4_view_fingerprint(
        project_c4(orphaned.snapshot, level="component", scope_id="CONTAINER-1")
    ) != c4_view_fingerprint(view)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_model.py tests/test_c4_projection_ir.py tests/test_c4_serialize.py -q`
Expected: `TypeError: C4View.__init__() got an unexpected keyword argument 'ancestors'`.

- [ ] **Step 3: Implement**

In `src/quarto_needs/c4/model.py`, add the field to `C4View` (after `relationships`, so existing positional construction keeps working) and to `to_dict`:

```python
@dataclass(frozen=True, slots=True)
class C4View:
    id: str
    level: str
    scope_id: str | None
    elements: tuple[C4Element, ...]
    relationships: tuple[C4Relationship, ...]
    # The scope's containment chain, outermost first. Context for a renderer
    # whose target grammar requires a declared parent (Structurizr's
    # `container` is only valid inside a `softwareSystem`), never content of
    # the view: `element`, `children_of` and `elements` all ignore it.
    ancestors: tuple[C4Element, ...] = ()
```

and in `to_dict`, add after `"relationships"`:

```python
            "ancestors": [element.to_dict() for element in self.ancestors],
```

`identifier_map` must cover ancestors too — Structurizr and D2 both need a
reference for the enclosing system, and a separate map would risk handing
the same element two different identifiers. Change its first loop to walk
both sequences:

```python
    grouped: dict[str, list[str]] = {}
    for element in (*view.elements, *view.ancestors):
        if element.id in {item for ids in grouped.values() for item in ids}:
            continue
        grouped.setdefault(sanitize_identifier(element.id), []).append(element.id)
```

and add this to `tests/test_c4_model.py`:

```python
def test_identifier_map_covers_ancestors_without_duplicating_them() -> None:
    system = _element("SYS-1", C4ElementRole.SOFTWARE_SYSTEM)
    container = _element("CONTAINER-A", C4ElementRole.CONTAINER, parent_id="SYS-1")
    view = C4View(
        id="component-CONTAINER-A", level="component", scope_id="CONTAINER-A",
        elements=(container,), relationships=(), ancestors=(system,),
    )
    mapping = identifier_map(view)
    assert mapping == {"CONTAINER-A": "CONTAINER_A", "SYS-1": "SYS_1"}
```

In `src/quarto_needs/c4/projection.py`, add the resolver and pass it to the `C4View`:

```python
def _parent_id(snapshot: AnalysisSnapshot, child_id: str) -> str | None:
    """The child's declared parent, from either authored direction."""
    for relation in snapshot.relations:
        if relation.v1_name == "part-of" and relation.source == child_id:
            return relation.target
        if relation.v1_name == "decomposes" and relation.target == child_id:
            return relation.source
    return None


def _ancestors(snapshot: AnalysisSnapshot, scope_id: str) -> tuple[C4Element, ...]:
    """The scope's containment chain, outermost first.

    A visited set terminates a cycle. ARC001 already rejects one as a graph
    error, but the projection must not spin on it whatever profile is active.
    """
    chain: list[C4Element] = []
    seen = {scope_id}
    current = _parent_id(snapshot, scope_id)
    while current is not None and current not in seen:
        seen.add(current)
        record = snapshot.objects_by_id.get(current)
        if record is None or record.type not in C4_ROLE_BY_TYPE:
            break
        chain.append(_element(record, parent_id=_parent_id(snapshot, current)))
        current = _parent_id(snapshot, current)
    return tuple(reversed(chain))
```

and in `project_c4`'s return:

```python
    return C4View(
        id=f"{canonical}-{scope_id}",
        level=canonical,
        scope_id=scope_id,
        elements=elements,
        relationships=relationships,
        ancestors=_ancestors(snapshot, scope_id),
    )
```

In `schemas/c4-view-v1.schema.json`, add `"ancestors"` to the top-level `required` array and, in `properties`, give it the same definition as `elements`. To avoid duplicating the element schema, hoist the element object into `$defs` and reference it from both:

```json
  "$defs": {
    "element": { ...the existing elements/items object, verbatim... }
  },
```

with `"elements": {"type": "array", "items": {"$ref": "#/$defs/element"}}` and `"ancestors": {"type": "array", "items": {"$ref": "#/$defs/element"}}`.

`serialize.py` needs no change beyond adding the key, because `c4_view_document` should read it from the view:

```python
        "ancestors": [element.to_dict() for element in view.ancestors],
```

placed after `"relationships"`. `c4_view_fingerprint` already hashes `view.to_dict()`, so ancestors are covered automatically.

- [ ] **Step 4: Run the tests and the full suite**

Run: `python -m pytest tests/test_c4_model.py tests/test_c4_projection_ir.py tests/test_c4_serialize.py -q` — expected: all pass.
Run: `python -m pytest -q` — expected: all pass. If `tests/test_c4_artifacts.py` pins an exact `view.json` payload, update it for the new key.

- [ ] **Step 5: Commit**

```bash
git add src/quarto_needs/c4 schemas/c4-view-v1.schema.json tests/test_c4_model.py \
        tests/test_c4_projection_ir.py tests/test_c4_serialize.py
git commit -m "feat: carry the scope's containment chain as C4View ancestors

Context for a renderer whose grammar requires a declared parent, never
content of the view -- element lookup, children and validation ignore it."
```

---

### Task 2: The Structurizr DSL adapter

**Files:**
- Create: `src/quarto_needs/c4/renderers/structurizr.py`
- Modify: `src/quarto_needs/c4/renderers/__init__.py` (register it)
- Test: `tests/test_c4_renderer_structurizr.py`

**Interfaces:**
- Produces: `StructurizrRenderer` (`name = "structurizr"`, `capabilities = RendererCapabilities(source=True, svg=False, auto_layout="full")`), `source_format = "structurizr-dsl"`, `file_extension = ".dsl"`.

**Mapping decisions:**

| C4 IR | Structurizr DSL |
| --- | --- |
| `PERSON` | `person "<name>" "<description>"` |
| `SOFTWARE_SYSTEM` | `softwareSystem "<name>" "<description>"` |
| `EXTERNAL_SYSTEM` | `softwareSystem "<name>" "<description>" "External"` (a tag, not a different type — Structurizr models externality as a tag) |
| `CONTAINER` | `container "<name>" "<description>" "<technology>"` |
| `COMPONENT` | `component "<name>" "<description>" "<technology>"` |
| `CODE` | `component "<name>" "<description>" "<technology>"` (Structurizr has no code-level element type; code elements are rendered as the container's components, which is what its own docs recommend) |
| `C4Relationship` | `<source> -> <target> "<description>"` |
| ancestors | the enclosing `softwareSystem` / `container` blocks |
| level | the `views` block: `systemContext` / `container` / `component` / `component` |
| `options.direction` | `autoLayout tb` / `bt` / `lr` / `rl` |

Structurizr is never the source of architecture identity: this adapter only ever writes, never reads a workspace back.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_renderer_structurizr.py`:

```python
from __future__ import annotations

from quarto_needs.analysis import analyze_objects
from quarto_needs.c4.model import LayoutDirection
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


def _render(view, options=None):
    return get_c4_renderer("structurizr").render(view, options or C4RenderOptions())


def _nested():
    return _snapshot(
        _obj("SYS-1", type="system", title="Quarto-Needs"),
        _obj("ACTOR-1", type="actor", title="Requirements engineer",
             relations=[Relation("depends-on", "ACTOR-1", "SYS-1")]),
        _obj("EXT-1", type="external-system", title="GitHub",
             relations=[Relation("depends-on", "EXT-1", "SYS-1")]),
        _obj("CONTAINER-1", type="container", title="Python package",
             attributes={"technology": "Python 3.12"},
             relations=[Relation("part-of", "CONTAINER-1", "SYS-1")]),
        _obj("COMP-1", type="component", title="Parser",
             relations=[Relation("part-of", "COMP-1", "CONTAINER-1")]),
    )


def test_result_metadata() -> None:
    view = project_c4(_nested(), level="system-context", scope_id="SYS-1")
    result = _render(view)
    assert result.renderer == "structurizr"
    assert result.source_format == "structurizr-dsl"
    assert result.file_extension == ".dsl"
    assert result.view_fingerprint == c4_view_fingerprint(view)
    assert result.source.endswith("\n")


def test_system_context_declares_a_workspace_model_and_view() -> None:
    source = _render(project_c4(_nested(), level="system-context", scope_id="SYS-1")).source
    assert source.startswith("workspace {\n")
    assert "    model {" in source
    assert '        ACTOR_1 = person "Requirements engineer"' in source
    assert '        SYS_1 = softwareSystem "Quarto-Needs"' in source
    assert '        EXT_1 = softwareSystem "GitHub" "" "External"' in source
    assert '        ACTOR_1 -> SYS_1 "Depends on"' in source
    assert "    views {" in source
    assert "        systemContext SYS_1 {" in source
    assert "            include *" in source
    assert "            autoLayout tb" in source


def test_container_view_nests_containers_inside_the_system() -> None:
    source = _render(project_c4(_nested(), level="container", scope_id="SYS-1")).source
    assert '        SYS_1 = softwareSystem "Quarto-Needs" {' in source
    assert '            CONTAINER_1 = container "Python package" "" "Python 3.12"' in source
    assert "        container SYS_1 {" in source


def test_component_view_nests_through_the_scopes_ancestors() -> None:
    # The scope is a container; Structurizr's grammar only accepts a
    # container inside a softwareSystem, which is what ancestors supply.
    source = _render(project_c4(_nested(), level="component", scope_id="CONTAINER-1")).source
    assert '        SYS_1 = softwareSystem "Quarto-Needs" {' in source
    assert '            CONTAINER_1 = container "Python package" "" "Python 3.12" {' in source
    assert '                COMP_1 = component "Parser"' in source
    assert "        component CONTAINER_1 {" in source


def test_code_view_renders_code_elements_as_components() -> None:
    snapshot = _snapshot(
        _obj("COMP-1", type="component", title="Parser"),
        _obj("SRC-1", type="source-module", title="parser.py",
             attributes={"path": "src/p.py", "language": "Python"},
             relations=[Relation("part-of", "SRC-1", "COMP-1")]),
    )
    source = _render(project_c4(snapshot, level="code", scope_id="COMP-1")).source
    assert '"parser.py" "src/p.py" "Python"' in source


def test_direction_is_a_presentation_hint_only() -> None:
    view = project_c4(_nested(), level="system-context", scope_id="SYS-1")
    for direction, token in (
        (LayoutDirection.TOP_BOTTOM, "tb"),
        (LayoutDirection.BOTTOM_TOP, "bt"),
        (LayoutDirection.LEFT_RIGHT, "lr"),
        (LayoutDirection.RIGHT_LEFT, "rl"),
    ):
        result = _render(view, C4RenderOptions(direction=direction))
        assert f"autoLayout {token}" in result.source
        # Presentation only: the IR identity never moves.
        assert result.view_fingerprint == c4_view_fingerprint(view)


def test_semantic_direction_is_never_reversed() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "SYS-1", "EXT-1")]),
    )
    source = _render(project_c4(snapshot, level="system-context", scope_id="SYS-1")).source
    assert "SYS_1 -> EXT_1" in source
    assert "EXT_1 -> SYS_1" not in source


def test_quotes_and_newlines_in_labels_are_escaped() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system", title='A "quoted"\nname'))
    source = _render(project_c4(snapshot, level="system-context", scope_id="SYS-1")).source
    assert '"A \\"quoted\\" name"' in source
    assert len(source.splitlines()) == len([line for line in source.splitlines() if line])


def test_output_is_byte_identical_across_renders() -> None:
    view = project_c4(_nested(), level="container", scope_id="SYS-1")
    assert _render(view).source == _render(view).source


def test_no_remote_include_or_url_appears_in_the_source() -> None:
    source = _render(project_c4(_nested(), level="container", scope_id="SYS-1")).source
    assert "http://" not in source and "https://" not in source
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_renderer_structurizr.py -q`
Expected: `UnknownRendererError: Renderer 'structurizr' is not available for direct rendering`.

- [ ] **Step 3: Write the implementation**

Create `src/quarto_needs/c4/renderers/structurizr.py`:

```python
"""Structurizr DSL generation from the C4 IR.

Write-only, always: this adapter emits a workspace and never reads one back.
Structurizr is a rendering backend here, never the source of architecture
identity (Spec 11).
"""
from __future__ import annotations

from ..model import C4Element, C4ElementRole, C4View, LayoutDirection, identifier_map
from ..serialize import c4_view_fingerprint
from .base import C4RenderOptions, C4RenderResult, RendererCapabilities

_AUTO_LAYOUT = {
    LayoutDirection.TOP_BOTTOM: "tb",
    LayoutDirection.BOTTOM_TOP: "bt",
    LayoutDirection.LEFT_RIGHT: "lr",
    LayoutDirection.RIGHT_LEFT: "rl",
}
# Structurizr has no code-level element type; its own guidance is to model
# code-level detail as components, which is what this maps CODE onto.
_KEYWORD_BY_ROLE = {
    C4ElementRole.PERSON: "person",
    C4ElementRole.SOFTWARE_SYSTEM: "softwareSystem",
    C4ElementRole.EXTERNAL_SYSTEM: "softwareSystem",
    C4ElementRole.CONTAINER: "container",
    C4ElementRole.COMPONENT: "component",
    C4ElementRole.CODE: "component",
}
_VIEW_KEYWORD = {
    "system-context": "systemContext",
    "container": "container",
    "component": "component",
    "code": "component",
}


def _escape(value: str) -> str:
    collapsed = value.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return collapsed.replace("\\", "\\\\").replace('"', '\\"')


def _declaration(element: C4Element, reference: str) -> str:
    keyword = _KEYWORD_BY_ROLE[element.role]
    arguments = [f'"{_escape(element.name)}"']
    trailing: list[str] = []
    if element.role in (C4ElementRole.CONTAINER, C4ElementRole.COMPONENT, C4ElementRole.CODE):
        trailing = [f'"{_escape(element.description or "")}"',
                    f'"{_escape(element.technology or "")}"']
    elif element.external:
        # Structurizr models externality as a tag on a softwareSystem, not
        # as a distinct element type.
        trailing = [f'"{_escape(element.description or "")}"', '"External"']
    elif element.description:
        trailing = [f'"{_escape(element.description)}"']
    return f"{reference} = {keyword} {' '.join(arguments + trailing)}"


def _model_lines(view: C4View, references: dict[str, str]) -> list[str]:
    lines: list[str] = []
    indent = 2
    scope = view.scope

    def emit(text: str, level: int) -> None:
        lines.append("    " * level + text)

    # Ancestors nest outermost-first, each opening a block the scope closes.
    for ancestor in view.ancestors:
        emit(_declaration(ancestor, references[ancestor.id]) + " {", indent)
        indent += 1

    if scope is not None:
        children = view.children_of(scope.id)
        if children:
            emit(_declaration(scope, references[scope.id]) + " {", indent)
            for child in children:
                emit(_declaration(child, references[child.id]), indent + 1)
            emit("}", indent)
        else:
            emit(_declaration(scope, references[scope.id]), indent)

    for ancestor in reversed(view.ancestors):
        indent -= 1
        emit("}", indent)

    child_ids = {child.id for child in view.children_of(scope.id)} if scope else set()
    for element in view.elements:
        if scope is not None and element.id in (scope.id, *child_ids):
            continue
        emit(_declaration(element, references[element.id]), 2)

    for relationship in view.relationships:
        emit(
            f"{references[relationship.source_id]} -> "
            f"{references[relationship.target_id]} "
            f'"{_escape(relationship.description or relationship.relation_type)}"',
            2,
        )
    return lines


class StructurizrRenderer:
    name = "structurizr"
    capabilities = RendererCapabilities(
        source=True, svg=False, png=False, auto_layout="full", interactive=False
    )

    def render(self, view: C4View, options: C4RenderOptions) -> C4RenderResult:
        # identifier_map covers ancestors as well as elements, so an
        # enclosing system has exactly one reference across the whole file.
        references = identifier_map(view)
        lines = ["workspace {", "    model {"]
        lines.extend(_model_lines(view, references))
        lines.append("    }")
        lines.append("    views {")
        scope_reference = references[view.scope_id] if view.scope_id in references else "*"
        lines.append(f"        {_VIEW_KEYWORD[view.level]} {scope_reference} {{")
        lines.append("            include *")
        lines.append(f"            autoLayout {_AUTO_LAYOUT[options.direction]}")
        lines.append("        }")
        lines.append("    }")
        lines.append("}")
        return C4RenderResult(
            renderer=self.name,
            source_format="structurizr-dsl",
            file_extension=".dsl",
            source="\n".join(lines) + "\n",
            view_fingerprint=c4_view_fingerprint(view),
        )
```

- [ ] **Step 4: Register it**

In `src/quarto_needs/c4/renderers/__init__.py`, extend `_register_builtin_renderers`:

```python
def _register_builtin_renderers() -> None:
    """Importing this package registers every backend that ships with it."""
    from .mermaid import MermaidRenderer
    from .structurizr import StructurizrRenderer

    register_c4_renderer(MermaidRenderer())
    register_c4_renderer(StructurizrRenderer())
```

- [ ] **Step 5: Run the tests and the full suite**

Run: `python -m pytest tests/test_c4_renderer_structurizr.py -q` — expected: 10 passed.
Run: `python -m pytest -q` — expected: all pass. Note that `tests/test_c4_cli.py::test_renderers_lists_capabilities_as_text` and the registry test now see two renderers; if either pins an exact list, update it.

- [ ] **Step 6: Commit**

```bash
git add src/quarto_needs/c4/renderers/structurizr.py src/quarto_needs/c4/renderers/__init__.py \
        tests/test_c4_renderer_structurizr.py
git commit -m "feat: add the Structurizr DSL C4 renderer"
```

---

### Task 3: The C4-PlantUML adapter

**Files:**
- Create: `src/quarto_needs/c4/renderers/plantuml.py`
- Modify: `src/quarto_needs/c4/renderers/__init__.py` (register it)
- Test: `tests/test_c4_renderer_plantuml.py`

**Interfaces:**
- Produces: `PlantUMLRenderer` (`name = "plantuml"`, `capabilities = RendererCapabilities(source=True, svg=False, auto_layout="full")`), `source_format = "plantuml"`, `file_extension = ".puml"`.
- New diagnostic owned by this renderer: `C4012` (info) — the requested direction was approximated, because C4-PlantUML offers `LAYOUT_TOP_DOWN()` and `LAYOUT_LEFT_RIGHT()` but no reversed variants.

**Offline include (Spec §48).** The generated source uses `!include <C4/C4_Context>`, which resolves from PlantUML's own bundled standard library. It must never use `!includeurl https://raw.githubusercontent.com/…`, which is the form most C4-PlantUML examples show and which would make rendering require network access.

**This adapter demonstrates the boundary paying off.** Unlike Mermaid, C4-PlantUML draws a `Rel` into a boundary without complaint. Same IR, no dropped relationships, no `C4010` — the limitation lives in the adapter that has it, exactly as intended.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_renderer_plantuml.py`, reusing the same `_obj`/`_snapshot`/`_nested` helpers as `tests/test_c4_renderer_structurizr.py` (copy them verbatim — the test modules stay independent, matching how this repository's other renderer tests are written), and `_render` bound to `get_c4_renderer("plantuml")`:

```python
def test_result_metadata() -> None:
    view = project_c4(_nested(), level="system-context", scope_id="SYS-1")
    result = _render(view)
    assert result.renderer == "plantuml"
    assert result.source_format == "plantuml"
    assert result.file_extension == ".puml"
    assert result.view_fingerprint == c4_view_fingerprint(view)


def test_context_diagram_uses_the_bundled_offline_include() -> None:
    source = _render(project_c4(_nested(), level="system-context", scope_id="SYS-1")).source
    lines = source.splitlines()
    assert lines[0] == "@startuml"
    assert lines[1] == "!include <C4/C4_Context>"
    assert lines[-1] == "@enduml"
    # Offline: never the !includeurl form every C4-PlantUML example shows.
    assert "includeurl" not in source
    assert "http://" not in source and "https://" not in source


def test_context_macros_and_relationships() -> None:
    source = _render(project_c4(_nested(), level="system-context", scope_id="SYS-1")).source
    assert 'Person(ACTOR_1, "Requirements engineer")' in source
    assert 'System(SYS_1, "Quarto-Needs")' in source
    assert 'System_Ext(EXT_1, "GitHub")' in source
    assert 'Rel(ACTOR_1, SYS_1, "Depends on")' in source


def test_container_diagram_keeps_a_relationship_into_the_boundary() -> None:
    # The Mermaid adapter must drop this; PlantUML must not. Same IR --
    # this is the whole point of the renderer boundary.
    view = project_c4(_nested(), level="container", scope_id="SYS-1")
    result = _render(view)
    assert result.source.splitlines()[1] == "!include <C4/C4_Container>"
    assert 'System_Boundary(SYS_1, "Quarto-Needs") {' in result.source
    assert 'Container(CONTAINER_1, "Python package", "Python 3.12")' in result.source
    assert 'Rel(ACTOR_1, SYS_1, "Depends on")' in result.source
    assert result.diagnostics == ()


def test_component_diagram_uses_a_container_boundary() -> None:
    source = _render(project_c4(_nested(), level="component", scope_id="CONTAINER-1")).source
    assert source.splitlines()[1] == "!include <C4/C4_Component>"
    assert 'Container_Boundary(CONTAINER_1, "Python package") {' in source
    assert 'Component(COMP_1, "Parser")' in source


def test_code_diagram_draws_code_elements_inside_a_generic_boundary() -> None:
    snapshot = _snapshot(
        _obj("COMP-1", type="component", title="Parser"),
        _obj("SRC-1", type="source-module", title="parser.py",
             attributes={"path": "src/p.py", "language": "Python"},
             relations=[Relation("part-of", "SRC-1", "COMP-1")]),
    )
    source = _render(project_c4(snapshot, level="code", scope_id="COMP-1")).source
    assert 'Boundary(COMP_1, "Parser", "component") {' in source
    assert 'Component(SRC_1, "parser.py", "Python", "src/p.py")' in source


def test_direction_maps_to_a_layout_macro_and_reports_approximation() -> None:
    view = project_c4(_nested(), level="system-context", scope_id="SYS-1")
    assert "LAYOUT_TOP_DOWN()" in _render(view, C4RenderOptions(
        direction=LayoutDirection.TOP_BOTTOM)).source
    assert "LAYOUT_LEFT_RIGHT()" in _render(view, C4RenderOptions(
        direction=LayoutDirection.LEFT_RIGHT)).source

    approximated = _render(view, C4RenderOptions(direction=LayoutDirection.BOTTOM_TOP))
    assert "LAYOUT_TOP_DOWN()" in approximated.source
    assert [item.code for item in approximated.diagnostics] == ["C4012"]
    assert approximated.diagnostics[0].severity == "info"
    # Presentation only: the identity does not move.
    assert approximated.view_fingerprint == c4_view_fingerprint(view)


def test_semantic_direction_is_never_reversed() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "SYS-1", "EXT-1")]),
    )
    source = _render(project_c4(snapshot, level="system-context", scope_id="SYS-1")).source
    assert "Rel(SYS_1, EXT_1" in source
    assert "Rel(EXT_1, SYS_1" not in source


def test_labels_are_escaped() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system", title='A "quoted"\nname'))
    source = _render(project_c4(snapshot, level="system-context", scope_id="SYS-1")).source
    assert "'quoted'" in source
    assert source.count("\n") == len(source.splitlines())


def test_output_is_byte_identical_across_renders() -> None:
    view = project_c4(_nested(), level="container", scope_id="SYS-1")
    assert _render(view).source == _render(view).source
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_renderer_plantuml.py -q`
Expected: `UnknownRendererError: Renderer 'plantuml' is not available for direct rendering`.

- [ ] **Step 3: Write the implementation**

Create `src/quarto_needs/c4/renderers/plantuml.py`:

```python
"""C4-PlantUML source generation from the C4 IR.

The include is PlantUML's bundled standard library (`!include <C4/...>`),
never the `!includeurl https://...` form C4-PlantUML's own examples use:
source generation must work offline (Spec 48).
"""
from __future__ import annotations

from ..model import C4Element, C4ElementRole, C4View, LayoutDirection, identifier_map
from ..serialize import c4_view_fingerprint
from ..validation import C4Diagnostic
from .base import C4RenderOptions, C4RenderResult, RendererCapabilities

_INCLUDE_BY_LEVEL = {
    "system-context": "<C4/C4_Context>",
    "container": "<C4/C4_Container>",
    "component": "<C4/C4_Component>",
    "code": "<C4/C4_Component>",
}
_MACRO_BY_ROLE = {
    C4ElementRole.PERSON: "Person",
    C4ElementRole.SOFTWARE_SYSTEM: "System",
    C4ElementRole.EXTERNAL_SYSTEM: "System_Ext",
    C4ElementRole.CONTAINER: "Container",
    C4ElementRole.COMPONENT: "Component",
    C4ElementRole.CODE: "Component",
}
_BOUNDARY_BY_LEVEL = {
    "container": "System_Boundary",
    "component": "Container_Boundary",
}
# C4-PlantUML offers only these two; the reversed directions have no macro.
_LAYOUT = {
    LayoutDirection.TOP_BOTTOM: "LAYOUT_TOP_DOWN()",
    LayoutDirection.BOTTOM_TOP: "LAYOUT_TOP_DOWN()",
    LayoutDirection.LEFT_RIGHT: "LAYOUT_LEFT_RIGHT()",
    LayoutDirection.RIGHT_LEFT: "LAYOUT_LEFT_RIGHT()",
}
_EXACT_DIRECTIONS = (LayoutDirection.TOP_BOTTOM, LayoutDirection.LEFT_RIGHT)


def _escape(value: str) -> str:
    replaced = value.replace("\\", "/").replace('"', "'")
    return replaced.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _macro_call(element: C4Element, reference: str) -> str:
    arguments = [reference, f'"{_escape(element.name)}"']
    if element.technology:
        arguments.append(f'"{_escape(element.technology)}"')
    if element.description:
        if not element.technology:
            arguments.append('""')
        arguments.append(f'"{_escape(element.description)}"')
    return f"{_MACRO_BY_ROLE[element.role]}({', '.join(arguments)})"


class PlantUMLRenderer:
    name = "plantuml"
    capabilities = RendererCapabilities(
        source=True, svg=False, png=False, auto_layout="full", interactive=False
    )

    def render(self, view: C4View, options: C4RenderOptions) -> C4RenderResult:
        references = identifier_map(view)
        scope = view.scope
        diagnostics: list[C4Diagnostic] = []
        if options.direction not in _EXACT_DIRECTIONS:
            diagnostics.append(
                C4Diagnostic(
                    "C4012",
                    "info",
                    f"C4-PlantUML has no macro for direction "
                    f"{options.direction.value!r}; {_LAYOUT[options.direction]} was used",
                    view.scope_id,
                )
            )

        lines = ["@startuml", f"!include {_INCLUDE_BY_LEVEL[view.level]}", _LAYOUT[options.direction], ""]

        children = view.children_of(scope.id) if scope is not None else ()
        if scope is not None and view.level != "system-context" and children:
            boundary = _BOUNDARY_BY_LEVEL.get(view.level)
            if boundary is not None:
                lines.append(f'{boundary}({references[scope.id]}, "{_escape(scope.name)}") {{')
            else:
                # Code level: the scope is a component, which has no
                # dedicated C4-PlantUML boundary macro. The generic
                # `Boundary` takes an explicit type instead.
                lines.append(
                    f'Boundary({references[scope.id]}, "{_escape(scope.name)}", "component") {{'
                )
            for child in children:
                lines.append(f"  {_macro_call(child, references[child.id])}")
            lines.append("}")
        elif scope is not None:
            lines.append(_macro_call(scope, references[scope.id]))

        child_ids = {child.id for child in children}
        for element in view.elements:
            if scope is not None and element.id in ({scope.id} | child_ids):
                continue
            lines.append(_macro_call(element, references[element.id]))

        if view.relationships:
            lines.append("")
        # Unlike Mermaid, C4-PlantUML draws a relationship into a boundary,
        # so nothing is dropped here.
        for relationship in view.relationships:
            lines.append(
                f"Rel({references[relationship.source_id]}, "
                f"{references[relationship.target_id]}, "
                f'"{_escape(relationship.description or relationship.relation_type)}")'
            )
        lines.append("@enduml")
        return C4RenderResult(
            renderer=self.name,
            source_format="plantuml",
            file_extension=".puml",
            source="\n".join(lines) + "\n",
            view_fingerprint=c4_view_fingerprint(view),
            diagnostics=tuple(diagnostics),
        )
```

- [ ] **Step 4: Register it**

Add to `_register_builtin_renderers` in `src/quarto_needs/c4/renderers/__init__.py`:

```python
    from .plantuml import PlantUMLRenderer

    register_c4_renderer(PlantUMLRenderer())
```

- [ ] **Step 5: Run the tests, the full suite, and commit**

Run: `python -m pytest tests/test_c4_renderer_plantuml.py -q` — expected: 10 passed.
Run: `python -m pytest -q` — expected: all pass.

```bash
git add src/quarto_needs/c4/renderers/plantuml.py src/quarto_needs/c4/renderers/__init__.py \
        tests/test_c4_renderer_plantuml.py
git commit -m "feat: add the C4-PlantUML renderer, using PlantUML's offline stdlib include"
```

---

### Task 4: The D2 adapter

**Files:**
- Create: `src/quarto_needs/c4/renderers/d2.py`
- Modify: `src/quarto_needs/c4/renderers/__init__.py` (register it)
- Test: `tests/test_c4_renderer_d2.py`

**Interfaces:**
- Produces: `D2Renderer` (`name = "d2"`, `capabilities = RendererCapabilities(source=True, svg=False, auto_layout="full")`), `source_format = "d2"`, `file_extension = ".d2"`.
- New diagnostic: `C4013` (info) — the configured layout engine is proprietary (`tala`), so it is recorded as a header comment but cannot be assumed available.

**D2 has no C4 vocabulary, and does not need one (Spec §13).** The adapter carries the C4 semantics itself: hierarchy becomes D2 nesting, roles become shapes and a bracketed role label (the convention C4 diagrams use), external systems get a dashed stroke, relationship labels come straight from the IR.

**Layout engine** comes from `options.setting("layout", "dagre")` and is emitted as a header comment, because D2 selects its layout engine on the command line (`d2 --layout=elk`), not in the source. Accepted values are `dagre`, `elk` and `tala`; anything else falls back to `dagre` with a `C4013` diagnostic.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_c4_renderer_d2.py` with the same helpers as Task 3's test module and `_render` bound to `get_c4_renderer("d2")`:

```python
def test_result_metadata() -> None:
    view = project_c4(_nested(), level="system-context", scope_id="SYS-1")
    result = _render(view)
    assert result.renderer == "d2"
    assert result.source_format == "d2"
    assert result.file_extension == ".d2"
    assert result.view_fingerprint == c4_view_fingerprint(view)


def test_context_declares_shapes_roles_and_relationships() -> None:
    source = _render(project_c4(_nested(), level="system-context", scope_id="SYS-1")).source
    assert source.splitlines()[0] == "# layout: dagre"
    assert "direction: down" in source
    assert 'ACTOR_1: "Requirements engineer\\n[Person]"' in source
    assert 'SYS_1: "Quarto-Needs\\n[Software System]"' in source
    assert 'EXT_1: "GitHub\\n[External System]"' in source
    assert 'ACTOR_1 -> SYS_1: "Depends on"' in source


def test_a_person_gets_the_person_shape_and_an_external_system_a_dashed_stroke() -> None:
    source = _render(project_c4(_nested(), level="system-context", scope_id="SYS-1")).source
    assert "ACTOR_1.shape: person" in source
    assert "EXT_1.style.stroke-dash: 3" in source


def test_container_view_nests_children_and_uses_dotted_paths_for_edges() -> None:
    source = _render(project_c4(_nested(), level="container", scope_id="SYS-1")).source
    assert 'SYS_1: "Quarto-Needs\\n[Software System]" {' in source
    assert '  CONTAINER_1: "Python package\\n[Container: Python 3.12]"' in source
    assert "}" in source
    # An edge into the boundary is drawn against the container node itself.
    assert 'ACTOR_1 -> SYS_1: "Depends on"' in source


def test_component_view_nests_through_the_scopes_ancestors() -> None:
    source = _render(project_c4(_nested(), level="component", scope_id="CONTAINER-1")).source
    assert 'SYS_1: "Quarto-Needs\\n[Software System]" {' in source
    assert '  CONTAINER_1: "Python package\\n[Container: Python 3.12]" {' in source
    assert '    COMP_1: "Parser\\n[Component]"' in source


def test_direction_maps_to_d2_directions() -> None:
    view = project_c4(_nested(), level="system-context", scope_id="SYS-1")
    for direction, token in (
        (LayoutDirection.TOP_BOTTOM, "down"),
        (LayoutDirection.BOTTOM_TOP, "up"),
        (LayoutDirection.LEFT_RIGHT, "right"),
        (LayoutDirection.RIGHT_LEFT, "left"),
    ):
        result = _render(view, C4RenderOptions(direction=direction))
        assert f"direction: {token}" in result.source
        assert result.view_fingerprint == c4_view_fingerprint(view)


def test_layout_engine_comes_from_the_renderers_settings() -> None:
    view = project_c4(_nested(), level="system-context", scope_id="SYS-1")
    assert _render(view, C4RenderOptions(settings={"layout": "elk"})).source.startswith(
        "# layout: elk"
    )
    proprietary = _render(view, C4RenderOptions(settings={"layout": "tala"}))
    assert proprietary.source.startswith("# layout: tala")
    assert [item.code for item in proprietary.diagnostics] == ["C4013"]
    unknown = _render(view, C4RenderOptions(settings={"layout": "graphviz"}))
    assert unknown.source.startswith("# layout: dagre")
    assert [item.code for item in unknown.diagnostics] == ["C4013"]


def test_semantic_direction_is_never_reversed() -> None:
    snapshot = _snapshot(
        _obj("SYS-1", type="system"),
        _obj("EXT-1", type="external-system", relations=[Relation("depends-on", "SYS-1", "EXT-1")]),
    )
    source = _render(project_c4(snapshot, level="system-context", scope_id="SYS-1")).source
    assert "SYS_1 -> EXT_1" in source
    assert "EXT_1 -> SYS_1" not in source


def test_labels_are_escaped() -> None:
    snapshot = _snapshot(_obj("SYS-1", type="system", title='A "quoted"\nname'))
    source = _render(project_c4(snapshot, level="system-context", scope_id="SYS-1")).source
    assert '\\"quoted\\"' in source


def test_output_is_byte_identical_across_renders() -> None:
    view = project_c4(_nested(), level="container", scope_id="SYS-1")
    assert _render(view).source == _render(view).source
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_c4_renderer_d2.py -q`
Expected: `UnknownRendererError: Renderer 'd2' is not available for direct rendering`.

- [ ] **Step 3: Write the implementation**

Create `src/quarto_needs/c4/renderers/d2.py`:

```python
"""D2 source generation from the C4 IR.

D2 has no C4 vocabulary and does not need one: the C4 semantics stay in the
IR, and this adapter expresses them in D2's own terms -- hierarchy as
nesting, role as a bracketed label and a shape, externality as a dashed
stroke (Spec 13).
"""
from __future__ import annotations

from ..model import C4Element, C4ElementRole, C4View, LayoutDirection, identifier_map
from ..serialize import c4_view_fingerprint
from ..validation import C4Diagnostic
from .base import C4RenderOptions, C4RenderResult, RendererCapabilities

_DIRECTION = {
    LayoutDirection.TOP_BOTTOM: "down",
    LayoutDirection.BOTTOM_TOP: "up",
    LayoutDirection.LEFT_RIGHT: "right",
    LayoutDirection.RIGHT_LEFT: "left",
}
_ROLE_LABEL = {
    C4ElementRole.PERSON: "Person",
    C4ElementRole.SOFTWARE_SYSTEM: "Software System",
    C4ElementRole.EXTERNAL_SYSTEM: "External System",
    C4ElementRole.CONTAINER: "Container",
    C4ElementRole.COMPONENT: "Component",
    C4ElementRole.CODE: "Code",
}
# `tala` is D2's proprietary layout engine. It is accepted because a user
# who has it should be able to ask for it, but never assumed available
# (Spec 13: do not require proprietary layout engines).
_OPEN_LAYOUTS = ("dagre", "elk")
_PROPRIETARY_LAYOUTS = ("tala",)


def _escape(value: str) -> str:
    collapsed = value.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return collapsed.replace("\\", "\\\\").replace('"', '\\"')


def _label(element: C4Element) -> str:
    role = _ROLE_LABEL[element.role]
    if element.technology:
        role = f"{role}: {_escape(element.technology)}"
    return f'"{_escape(element.name)}\\n[{role}]"'


def _style_lines(element: C4Element, path: str) -> list[str]:
    lines: list[str] = []
    if element.role is C4ElementRole.PERSON:
        lines.append(f"{path}.shape: person")
    if element.external:
        lines.append(f"{path}.style.stroke-dash: 3")
    return lines


class D2Renderer:
    name = "d2"
    capabilities = RendererCapabilities(
        source=True, svg=False, png=False, auto_layout="full", interactive=False
    )

    def render(self, view: C4View, options: C4RenderOptions) -> C4RenderResult:
        references = identifier_map(view)
        diagnostics: list[C4Diagnostic] = []
        requested = options.setting("layout", "dagre") or "dagre"
        if requested in _PROPRIETARY_LAYOUTS:
            layout = requested
            diagnostics.append(
                C4Diagnostic(
                    "C4013", "info",
                    f"D2 layout engine {requested!r} is proprietary and may not be "
                    "installed; the generated source records it as a comment only",
                    view.scope_id,
                )
            )
        elif requested in _OPEN_LAYOUTS:
            layout = requested
        else:
            layout = "dagre"
            diagnostics.append(
                C4Diagnostic(
                    "C4013", "info",
                    f"Unknown D2 layout engine {requested!r}; using 'dagre' "
                    f"(known: {', '.join(_OPEN_LAYOUTS + _PROPRIETARY_LAYOUTS)})",
                    view.scope_id,
                )
            )

        # D2 chooses its layout engine on the command line, not in the
        # source, so the choice is recorded as a header comment.
        lines = [f"# layout: {layout}", f"direction: {_DIRECTION[options.direction]}", ""]
        styles: list[str] = []
        # Canonical id -> D2 dotted path, because a nested node is only
        # addressable by its full path in a relationship.
        paths: dict[str, str] = {}

        def emit(element: C4Element, prefix: str) -> str:
            """Record an element's D2 dotted path and any style lines it needs."""
            reference = references[element.id]
            path = f"{prefix}.{reference}" if prefix else reference
            paths[element.id] = path
            styles.extend(_style_lines(element, path))
            return path

        scope = view.scope
        indent = 0
        prefix = ""
        for ancestor in view.ancestors:
            prefix = emit(ancestor, prefix)
            lines.append("  " * indent + f"{references[ancestor.id]}: {_label(ancestor)} {{")
            indent += 1

        if scope is not None:
            emit(scope, prefix)
            children = view.children_of(scope.id)
            if children:
                lines.append("  " * indent + f"{references[scope.id]}: {_label(scope)} {{")
                for child in children:
                    emit(child, paths[scope.id])
                    lines.append(
                        "  " * (indent + 1) + f"{references[child.id]}: {_label(child)}"
                    )
                lines.append("  " * indent + "}")
            else:
                lines.append("  " * indent + f"{references[scope.id]}: {_label(scope)}")

        for _ in view.ancestors:
            indent -= 1
            lines.append("  " * indent + "}")

        for element in view.elements:
            if element.id in paths:
                continue
            emit(element, "")
            lines.append(f"{references[element.id]}: {_label(element)}")

        if styles:
            lines.append("")
            lines.extend(styles)
        if view.relationships:
            lines.append("")
        for relationship in view.relationships:
            lines.append(
                f"{paths[relationship.source_id]} -> {paths[relationship.target_id]}: "
                f'"{_escape(relationship.description or relationship.relation_type)}"'
            )
        return C4RenderResult(
            renderer=self.name,
            source_format="d2",
            file_extension=".d2",
            source="\n".join(lines) + "\n",
            view_fingerprint=c4_view_fingerprint(view),
            diagnostics=tuple(diagnostics),
        )
```

- [ ] **Step 4: Register it**

Add to `_register_builtin_renderers` in `src/quarto_needs/c4/renderers/__init__.py`:

```python
    from .d2 import D2Renderer

    register_c4_renderer(D2Renderer())
```

- [ ] **Step 5: Run the tests, the full suite, and commit**

Run: `python -m pytest tests/test_c4_renderer_d2.py -q` — expected: 10 passed.
Run: `python -m pytest -q` — expected: all pass.

```bash
git add src/quarto_needs/c4/renderers/d2.py src/quarto_needs/c4/renderers/__init__.py \
        tests/test_c4_renderer_d2.py
git commit -m "feat: add the D2 C4 renderer with selectable open layout engines"
```

---

### Task 5: Golden outputs and the renderer-parity invariant

**Files:**
- Create: `tests/c4_reference_fixture.py`
- Create: `tools/regenerate_c4_goldens.py`
- Create: `tests/golden/c4/system-context.json`, `.mmd`, `.dsl`, `.puml`, `.d2`
- Create: `tests/golden/c4/container.json`, `.mmd`, `.dsl`, `.puml`, `.d2`
- Create: `tests/test_c4_goldens.py`
- Create: `tests/test_c4_renderer_parity.py`

**Interfaces:**
- Produces: `tests/c4_reference_fixture.py` exposing `reference_snapshot() -> AnalysisSnapshot` and `GOLDEN_VIEWS: tuple[tuple[str, str], ...]` (level, scope-id pairs); `tools/regenerate_c4_goldens.py` as a `python tools/regenerate_c4_goldens.py` entry point.

**The fixture is Spec §35's, exactly:** a person (Requirements engineer), one software system (Quarto-Needs), two external systems (GitHub, an OSLC-compatible RM tool), three containers (Python semantic core, Quarto extension, CLI) and four components of the semantic core (Parser, Analyzer, Rule engine, Graph projection).

**Goldens are never auto-rewritten (Spec §37).** `tools/regenerate_c4_goldens.py` is the only thing that writes them, it is run by hand, and its output is reviewed in the diff like any other change. There is no `--update` flag on the test.

- [ ] **Step 1: Write the shared fixture**

Create `tests/c4_reference_fixture.py`:

```python
"""The one semantic fixture every C4 renderer is measured against.

Spec 35: every backend renders *this* graph, so a golden diff between two
backends is a difference in rendering, never a difference in what was
modelled.
"""
from __future__ import annotations

from quarto_needs.analysis import analyze_objects
from quarto_needs.model import EngineeringObject, Relation
from quarto_needs.snapshot import AnalysisSnapshot

GOLDEN_VIEWS: tuple[tuple[str, str], ...] = (
    ("system-context", "SYS-QUARTO-NEEDS"),
    ("container", "SYS-QUARTO-NEEDS"),
)


def _obj(identifier, *, type, title, attributes=None, relations=None):
    return EngineeringObject(
        identifier, type, title, status="approved",
        attributes=attributes or {}, relations=relations or [],
    )


def reference_snapshot() -> AnalysisSnapshot:
    result = analyze_objects([
        _obj("ACTOR-ENGINEER", type="actor", title="Requirements engineer",
             relations=[Relation("depends-on", "ACTOR-ENGINEER", "SYS-QUARTO-NEEDS")]),
        _obj("SYS-QUARTO-NEEDS", type="system", title="Quarto-Needs"),
        _obj("EXT-GITHUB", type="external-system", title="GitHub",
             relations=[Relation("depends-on", "SYS-QUARTO-NEEDS", "EXT-GITHUB")]),
        _obj("EXT-OSLC", type="external-system", title="OSLC-compatible RM tool",
             relations=[Relation("depends-on", "SYS-QUARTO-NEEDS", "EXT-OSLC")]),
        _obj("CONTAINER-CORE", type="container", title="Python semantic core",
             attributes={"technology": "Python 3.12"},
             relations=[Relation("part-of", "CONTAINER-CORE", "SYS-QUARTO-NEEDS")]),
        _obj("CONTAINER-QUARTO", type="container", title="Quarto extension",
             attributes={"technology": "Lua"},
             relations=[Relation("part-of", "CONTAINER-QUARTO", "SYS-QUARTO-NEEDS")]),
        _obj("CONTAINER-CLI", type="container", title="CLI",
             attributes={"technology": "Python 3.12"},
             relations=[Relation("part-of", "CONTAINER-CLI", "SYS-QUARTO-NEEDS")]),
        _obj("COMP-PARSER", type="component", title="Parser",
             relations=[Relation("part-of", "COMP-PARSER", "CONTAINER-CORE")]),
        _obj("COMP-ANALYZER", type="component", title="Analyzer",
             relations=[Relation("part-of", "COMP-ANALYZER", "CONTAINER-CORE")]),
        _obj("COMP-RULES", type="component", title="Rule engine",
             relations=[Relation("part-of", "COMP-RULES", "CONTAINER-CORE")]),
        _obj("COMP-GRAPH", type="component", title="Graph projection",
             relations=[Relation("part-of", "COMP-GRAPH", "CONTAINER-CORE")]),
    ])
    assert result.snapshot is not None
    return result.snapshot
```

- [ ] **Step 2: Write the golden regenerator**

Create `tools/regenerate_c4_goldens.py`:

```python
"""Regenerate tests/golden/c4/. Run by hand; review the diff.

Never called from a test: a golden that rewrites itself when it disagrees
with the code proves nothing (Spec 37).

    python tools/regenerate_c4_goldens.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from c4_reference_fixture import GOLDEN_VIEWS, reference_snapshot  # noqa: E402

from quarto_needs.c4.projection import project_c4  # noqa: E402
from quarto_needs.c4.renderers import c4_renderers  # noqa: E402
from quarto_needs.c4.renderers.base import C4RenderOptions  # noqa: E402
from quarto_needs.c4.serialize import render_c4_view  # noqa: E402
from quarto_needs.c4.validation import validate_c4_view  # noqa: E402

EXTENSION_BY_RENDERER = {
    "mermaid": ".mmd",
    "structurizr": ".dsl",
    "plantuml": ".puml",
    "d2": ".d2",
}


def main() -> int:
    directory = ROOT / "tests" / "golden" / "c4"
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = reference_snapshot()
    for level, scope_id in GOLDEN_VIEWS:
        view = project_c4(snapshot, level=level, scope_id=scope_id)
        (directory / f"{level}.json").write_text(
            render_c4_view(view, diagnostics=validate_c4_view(view)), encoding="utf-8"
        )
        for renderer in c4_renderers():
            extension = EXTENSION_BY_RENDERER[renderer.name]
            result = renderer.render(view, C4RenderOptions())
            (directory / f"{level}{extension}").write_text(result.source, encoding="utf-8")
        print(f"wrote {level}.*")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Write the golden test**

Create `tests/test_c4_goldens.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from c4_reference_fixture import GOLDEN_VIEWS, reference_snapshot

from quarto_needs.c4.projection import project_c4
from quarto_needs.c4.renderers import c4_renderers
from quarto_needs.c4.renderers.base import C4RenderOptions
from quarto_needs.c4.serialize import render_c4_view
from quarto_needs.c4.validation import validate_c4_view

GOLDEN = Path(__file__).resolve().parent / "golden" / "c4"
EXTENSION_BY_RENDERER = {
    "mermaid": ".mmd", "structurizr": ".dsl", "plantuml": ".puml", "d2": ".d2",
}


@pytest.mark.parametrize("level,scope_id", GOLDEN_VIEWS)
def test_the_ir_matches_its_golden(level: str, scope_id: str) -> None:
    view = project_c4(reference_snapshot(), level=level, scope_id=scope_id)
    actual = render_c4_view(view, diagnostics=validate_c4_view(view))
    expected = (GOLDEN / f"{level}.json").read_text(encoding="utf-8")
    assert actual == expected, (
        "The C4 IR changed. If that is intended, run "
        "`python tools/regenerate_c4_goldens.py` and review the diff."
    )


@pytest.mark.parametrize("level,scope_id", GOLDEN_VIEWS)
def test_every_renderer_matches_its_golden(level: str, scope_id: str) -> None:
    view = project_c4(reference_snapshot(), level=level, scope_id=scope_id)
    for renderer in c4_renderers():
        extension = EXTENSION_BY_RENDERER[renderer.name]
        actual = renderer.render(view, C4RenderOptions()).source
        expected = (GOLDEN / f"{level}{extension}").read_text(encoding="utf-8")
        assert actual == expected, (
            f"{renderer.name} output changed for the {level} view. If that is "
            "intended, run `python tools/regenerate_c4_goldens.py` and review."
        )


def test_a_golden_exists_for_every_registered_renderer() -> None:
    # A new backend without a golden would otherwise pass silently.
    for renderer in c4_renderers():
        assert renderer.name in EXTENSION_BY_RENDERER, (
            f"{renderer.name} has no golden extension mapping; add one and "
            "regenerate the goldens."
        )
        for level, _ in GOLDEN_VIEWS:
            assert (GOLDEN / f"{level}{EXTENSION_BY_RENDERER[renderer.name]}").is_file()
```

`tests/` is already on `sys.path` for pytest (`pythonpath = ["src"]` plus pytest's rootdir insertion of the test file's directory), so `from c4_reference_fixture import ...` resolves. If it does not in this environment, add `"tests"` to `pythonpath` in `pyproject.toml`'s `[tool.pytest.ini_options]`.

- [ ] **Step 4: Generate the goldens and read them**

```bash
python tools/regenerate_c4_goldens.py
cat tests/golden/c4/container.mmd tests/golden/c4/container.dsl \
    tests/golden/c4/container.puml tests/golden/c4/container.d2
```

Read every generated file before committing it. A golden is a reviewed artifact: check that the Structurizr DSL nests containers inside the software system, that the PlantUML keeps the `Rel` the Mermaid version drops, that the D2 nesting and dotted edge paths are right, and that no file contains a URL.

- [ ] **Step 5: Write the parity test**

Create `tests/test_c4_renderer_parity.py`:

```python
from __future__ import annotations

import json

from c4_reference_fixture import reference_snapshot

from quarto_needs.c4.model import identifier_map
from quarto_needs.c4.projection import project_c4
from quarto_needs.c4.renderers import c4_renderer_names, c4_renderers
from quarto_needs.c4.renderers.base import C4RenderOptions
from quarto_needs.c4.serialize import c4_view_fingerprint
from quarto_needs.config import embedded_defaults


def _view(level="container"):
    return project_c4(reference_snapshot(), level=level, scope_id="SYS-QUARTO-NEEDS")


def test_all_four_backends_ship() -> None:
    assert set(c4_renderer_names()) == {"mermaid", "structurizr", "plantuml", "d2"}


def test_every_backend_records_the_same_ir_fingerprint() -> None:
    # Spec 38/55: the branch point is *after* the semantic projection, so
    # every backend's output is traceable to one identical IR identity.
    view = _view()
    fingerprint = c4_view_fingerprint(view)
    for renderer in c4_renderers():
        result = renderer.render(view, C4RenderOptions())
        assert result.view_fingerprint == fingerprint, renderer.name


def test_every_backend_names_every_element_and_relationship() -> None:
    view = _view()
    references = identifier_map(view)
    for renderer in c4_renderers():
        source = renderer.render(view, C4RenderOptions()).source
        for element in view.elements:
            assert references[element.id] in source, f"{renderer.name}: {element.id}"
        for relationship in view.relationships:
            # Mermaid documents the one case it cannot draw; every other
            # backend must draw all of them.
            if renderer.name == "mermaid" and view.scope_id in (
                relationship.source_id, relationship.target_id
            ):
                continue
            assert references[relationship.source_id] in source
            assert references[relationship.target_id] in source


def test_no_backend_reverses_a_relationship() -> None:
    view = _view("system-context")
    references = identifier_map(view)
    for renderer in c4_renderers():
        source = renderer.render(view, C4RenderOptions()).source
        for relationship in view.relationships:
            forward = f"{references[relationship.source_id]}"
            backward = f"{references[relationship.target_id]}"
            arrow_forward = f"{forward} -> {backward}"
            arrow_backward = f"{backward} -> {forward}"
            macro_forward = f"({forward}, {backward},"
            macro_backward = f"({backward}, {forward},"
            assert arrow_forward in source or macro_forward in source, renderer.name
            assert arrow_backward not in source and macro_backward not in source, renderer.name


def test_renderer_options_cannot_move_any_fingerprint() -> None:
    from quarto_needs.c4.model import LayoutDirection

    view = _view()
    fingerprint = c4_view_fingerprint(view)
    for renderer in c4_renderers():
        for direction in LayoutDirection:
            result = renderer.render(
                view, C4RenderOptions(direction=direction, settings={"layout": "elk"})
            )
            assert result.view_fingerprint == fingerprint, renderer.name


def test_render_all_writes_one_artifact_set_per_backend(tmp_path) -> None:
    # Spec 39: `--all` is an architectural invariant check, not a
    # convenience. If every backend can consume the same IR, renderer
    # semantics have not leaked into the model.
    from dataclasses import replace

    from quarto_needs.c4.artifacts import write_c4_artifacts

    config = replace(
        embedded_defaults(),
        architecture=replace(
            embedded_defaults().architecture,
            c4=replace(
                embedded_defaults().architecture.c4,
                enabled_renderers=("d2", "mermaid", "plantuml", "structurizr"),
            ),
        ),
    )
    write_c4_artifacts(tmp_path, reference_snapshot(), config)
    directory = tmp_path / ".quarto-needs" / "c4" / "container" / "SYS_QUARTO_NEEDS"
    fingerprints = set()
    for name, extension in (
        ("mermaid", ".mmd"), ("structurizr", ".dsl"),
        ("plantuml", ".puml"), ("d2", ".d2"),
    ):
        payload = json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        assert payload["renderer"] == name
        assert (directory / f"{name}{extension}").is_file()
        fingerprints.add(payload["viewFingerprint"])
    assert len(fingerprints) == 1
    view_document = json.loads((directory / "view.json").read_text(encoding="utf-8"))
    assert fingerprints == {view_document["fingerprint"]}
```

`NeedsConfig`, `ArchitectureSettings` and `C4Settings` are all frozen dataclasses, so `dataclasses.replace` is the right way to build the variant config above.

- [ ] **Step 6: Run everything and commit**

Run: `python -m pytest tests/test_c4_goldens.py tests/test_c4_renderer_parity.py -q`
Expected: 5 + 6 = 11 passed.
Run: `python -m pytest -q` — expected: all pass.

```bash
git add tests/c4_reference_fixture.py tests/golden/c4 tests/test_c4_goldens.py \
        tests/test_c4_renderer_parity.py tools/regenerate_c4_goldens.py
git commit -m "test: pin C4 goldens and prove renderer parity over one IR fingerprint"
```

---

### Task 6: Optional validation against the real target tools

**Files:**
- Create: `tests/test_c4_renderer_toolchain.py`

**Interfaces:**
- Consumes: `reference_snapshot`, `GOLDEN_VIEWS` (Task 5).

Spec §36 asks for real-tool validation where practical, skippable only when the executable is genuinely missing. Mermaid already has real-tool coverage through `tests/test_quarto_views.py`, which renders through the actual `quarto` binary; this module covers the other three.

Every invocation follows Spec §47: `shell=False`, an argument list (never a constructed string), a bounded timeout, and a temporary working directory.

- [ ] **Step 1: Write the tests**

Create `tests/test_c4_renderer_toolchain.py`:

```python
"""Validate generated source with the real target tools, when installed.

Skipped -- never silently passed -- when a tool is absent. The
source-generation unit tests always run; these are the extra confirmation
that what we generate is syntactically real (Spec 36).
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from c4_reference_fixture import reference_snapshot

from quarto_needs.c4.projection import project_c4
from quarto_needs.c4.renderers import get_c4_renderer
from quarto_needs.c4.renderers.base import C4RenderOptions

TIMEOUT_SECONDS = 60


def _source(renderer: str, level: str = "container") -> str:
    view = project_c4(reference_snapshot(), level=level, scope_id="SYS-QUARTO-NEEDS")
    return get_c4_renderer(renderer).render(view, C4RenderOptions()).source


def _run(command: list[str], cwd) -> subprocess.CompletedProcess[str]:
    # shell=False, an argument list, a bounded timeout and a bounded working
    # directory: generated source is data, never a command (Spec 47).
    return subprocess.run(
        command, cwd=str(cwd), shell=False, check=False,
        text=True, capture_output=True, timeout=TIMEOUT_SECONDS,
    )


@pytest.mark.skipif(shutil.which("plantuml") is None, reason="plantuml is not installed")
@pytest.mark.parametrize("level", ("system-context", "container"))
def test_plantuml_parses_the_generated_source(tmp_path, level: str) -> None:
    path = tmp_path / "diagram.puml"
    path.write_text(_source("plantuml", level), encoding="utf-8")
    completed = _run(["plantuml", "-failfast2", "-tsvg", path.name], tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "diagram.svg").is_file()


@pytest.mark.skipif(shutil.which("d2") is None, reason="d2 is not installed")
@pytest.mark.parametrize("level", ("system-context", "container"))
def test_d2_parses_the_generated_source(tmp_path, level: str) -> None:
    path = tmp_path / "diagram.d2"
    path.write_text(_source("d2", level), encoding="utf-8")
    completed = _run(["d2", "--dry-run", path.name], tmp_path)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(
    shutil.which("structurizr-cli") is None and shutil.which("structurizr.sh") is None,
    reason="structurizr-cli is not installed",
)
@pytest.mark.parametrize("level", ("system-context", "container", "component"))
def test_structurizr_validates_the_generated_workspace(tmp_path, level: str) -> None:
    scope = "CONTAINER-CORE" if level == "component" else "SYS-QUARTO-NEEDS"
    view = project_c4(reference_snapshot(), level=level, scope_id=scope)
    path = tmp_path / "workspace.dsl"
    path.write_text(
        get_c4_renderer("structurizr").render(view, C4RenderOptions()).source,
        encoding="utf-8",
    )
    executable = shutil.which("structurizr-cli") or shutil.which("structurizr.sh")
    completed = _run([executable, "validate", "-workspace", path.name], tmp_path)
    assert completed.returncode == 0, completed.stdout + completed.stderr
```

- [ ] **Step 2: Run them**

Run: `python -m pytest tests/test_c4_renderer_toolchain.py -q -rs`

Expected: passed where a tool is installed, **skipped with a printed reason** where it is not. Record in the task report exactly which of the three actually ran — a suite of three skips is not evidence that the source is valid, and reporting it as a pass would be false.

If none is installed and you want real evidence before merging, install one:

```bash
# any one of these is enough to exercise the path
sudo apt-get install -y plantuml
# or
curl -fsSL https://d2lang.com/install.sh | sh -s --
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_c4_renderer_toolchain.py
git commit -m "test: validate generated PlantUML/D2/Structurizr with the real tools when present"
```

---

### Task 7: The self-hosted architecture, extended truthfully

**Files:**
- Modify: `examples/quarto-needs/architecture.qmd`, `examples/quarto-needs/architecture.pt-BR.qmd`
- Modify: `examples/quarto-needs/implementation.qmd`, `examples/quarto-needs/implementation.pt-BR.qmd`
- Modify: `examples/quarto-needs/.quarto-needs.toml`
- Modify: `tests/test_self_hosted_example.py` (the exact-ownership assertion)

**What gets added, and why each is truthful.** Spec §40 asks for the LSP server and the VS Code client. Neither is modelled today, and both genuinely exist in this repository — but they are not both containers:

| Object | Type | Parent | Why this is the truthful shape |
| --- | --- | --- | --- |
| `CONTAINER-VSCODE-EXT` | `container` (technology `TypeScript / VS Code extension API`) | `SYS-QUARTO-NEEDS` | `editors/vscode/` is a genuinely separate deployable unit: it is installed from the VS Code marketplace, not from the Python package. |
| `COMP-LSP` | `component` | `CONTAINER-PYTHON-PKG` | `lsp_server.py` and `language_service.py` are modules **inside** the `quarto_needs` package (`quarto-needs lsp` is a subcommand). The language server is not separately deployable, so it is a component, not a container. Spec §40 lists it as a container; that would be untruthful here, and §40 also says "use truthful architecture only" — the second instruction wins. |
| `COMP-VSCODE-CLIENT` | `component` | `CONTAINER-VSCODE-EXT` | The extension's client code. |
| `SRC-LSP-SERVER` | `source-module` (`src/quarto_needs/lsp_server.py`) | `COMP-LSP` | |
| `SRC-LANGUAGE-SERVICE` | `source-module` (`src/quarto_needs/language_service.py`) | `COMP-LSP` | |

Before writing any of it, confirm each claim against the tree — `ls editors/vscode`, `ls src/quarto_needs/lsp_server.py src/quarto_needs/language_service.py`, and `grep -n '"lsp"' src/quarto_needs/cli_entry.py`. If something is not there, do not model it, and say so in the task report.

- [ ] **Step 1: Extend the exact-ownership test first**

`tests/test_self_hosted_example.py::test_self_hosted_c4_part_of_ownership_is_complete_and_exact` pins all 23 ownership tuples exactly, so it is the right place to start. Add the five new tuples to its expected set:

```python
        ("COMP-LSP", "CONTAINER-PYTHON-PKG"),
        ("COMP-VSCODE-CLIENT", "CONTAINER-VSCODE-EXT"),
        ("CONTAINER-VSCODE-EXT", "SYS-QUARTO-NEEDS"),
        ("SRC-LANGUAGE-SERVICE", "COMP-LSP"),
        ("SRC-LSP-SERVER", "COMP-LSP"),
```

Run: `python -m pytest tests/test_self_hosted_example.py -q`
Expected: FAIL — the expected set now has 28 tuples and the example still declares 23.

- [ ] **Step 2: Add the objects to the English example**

In `examples/quarto-needs/architecture.qmd`, after `CONTAINER-QUARTO-EXT` (line 39):

```markdown
::: {.need #CONTAINER-VSCODE-EXT type="container" status="approved" tags="architecture;c4;editor" technology="TypeScript / VS Code extension API" part-of="SYS-QUARTO-NEEDS"}
## VS Code extension

The editor client published to the VS Code marketplace (`editors/vscode/`): it launches `quarto-needs lsp` and surfaces diagnostics, completion and navigation inside the editor. Deployed separately from the Python package, which is why it is its own container.
:::
```

and, after `COMP-I18N` (line 89):

```markdown
::: {.need #COMP-LSP type="component" status="implemented" tags="python;lsp;editor" part-of="CONTAINER-PYTHON-PKG"}
## Language server

The Language Server Protocol implementation behind `quarto-needs lsp`. It ships inside the Python package rather than as its own deployable unit, so it is a component of that container, not a container of its own.
:::

::: {.need #COMP-VSCODE-CLIENT type="component" status="implemented" tags="typescript;editor" part-of="CONTAINER-VSCODE-EXT"}
## VS Code client

Starts and supervises the language server process and registers the extension's editor contributions.
:::
```

In `examples/quarto-needs/implementation.qmd`, add the two source modules alongside the existing 15, matching their exact block style:

```markdown
::: {.need #SRC-LSP-SERVER type="source-module" status="implemented" tags="python;lsp" path="src/quarto_needs/lsp_server.py" language="Python" part-of="COMP-LSP"}
## `lsp_server.py`

The stdio Language Server Protocol loop.
:::

::: {.need #SRC-LANGUAGE-SERVICE type="source-module" status="implemented" tags="python;lsp" path="src/quarto_needs/language_service.py" language="Python" part-of="COMP-LSP"}
## `language_service.py`

The editor-facing query surface the language server answers from.
:::
```

Match the surrounding blocks' attribute set exactly — open `implementation.qmd` and copy the shape of an existing `source-module` block rather than trusting the sketch above; if the existing blocks carry `implements=` relations, decide truthfully whether these two do and add them only if so.

- [ ] **Step 3: Mirror to pt-BR**

Add the same five objects to `architecture.pt-BR.qmd` and `implementation.pt-BR.qmd` with translated prose and **identical** IDs, types, statuses, tags, attributes and relations. `tests/test_self_hosted_example.py`'s EN/pt-BR parity gate checks exactly this.

- [ ] **Step 4: Add the generated C4 section**

Replace the three existing `need-c4` shortcodes in `architecture.qmd` (lines 325-329) with the documented spelling plus the two new views:

```markdown
## Generated C4 views

### System context

{{< need-c4 view="system-context" scope="SYS-QUARTO-NEEDS" >}}

### Containers

{{< need-c4 view="container" scope="SYS-QUARTO-NEEDS" >}}

### Components of the Python package

{{< need-c4 view="component" scope="CONTAINER-PYTHON-PKG" >}}

### Components of the VS Code extension

{{< need-c4 view="component" scope="CONTAINER-VSCODE-EXT" >}}

### Code: the language server

{{< need-c4 view="code" scope="COMP-LSP" >}}

The code view lists the component's source modules. Requirement traceability
for those modules is a separate question, answered by the engineering graph
directly:

{{< need-table type="source-module" tags="lsp" >}}
```

The closing `need-table` restores the requirement-traceability column the code view dropped when the C4 IR stopped carrying `implements` edges (they point at requirements, which are not C4 elements). Verify the `need-table` filter syntax against `docs/manual/reference.qmd` before writing it, and adjust the filter to whatever actually selects those two modules.

Mirror the whole section to `architecture.pt-BR.qmd` with translated headings.

- [ ] **Step 5: Register the new container type requirements**

`examples/quarto-needs/.quarto-needs.toml` already requires `technology` on `container`. Confirm the new objects satisfy every configured `required-attributes` for their type, and that the `part-of` policy's `allowed-source-types`/`allowed-target-types` admit `component -> container` for the VS Code pair. Extend those lists only if they genuinely exclude the new edges.

- [ ] **Step 6: Rebuild and verify end to end**

```bash
python -m quarto_needs.cli_entry --root examples/quarto-needs scan
python -m quarto_needs.cli_entry --root examples/quarto-needs check
ls examples/quarto-needs/.quarto-needs/c4/component
quarto render examples/quarto-needs
```

Expected: a clean `check` (the example runs under `profile = "strict"`, so ARC001 and every policy must pass), a `component/` directory containing both containers, and a rendered site. Confirm the new diagrams actually appear:

```bash
grep -c "need-c4-figure" examples/quarto-needs/_book/architecture.html
```

Expected: at least 4 (the four diagram views; the code view renders as a table, not a figure).

- [ ] **Step 7: Run the full suite and commit**

Run: `python -m pytest -q` — expected: all pass, including the updated exact-ownership assertion and the EN/pt-BR parity gate.

```bash
git add examples/quarto-needs tests/test_self_hosted_example.py
git commit -m "feat: model the language server and VS Code extension in the self-hosted example"
```

---

### Task 8: The renderer comparison showcase, and documentation

**Files:**
- Create: `examples/quarto-needs/architecture-renderers.qmd`, `examples/quarto-needs/architecture-renderers.pt-BR.qmd`
- Modify: `examples/quarto-needs/_quarto.yml` (add the page to the book)
- Modify: `examples/quarto-needs/.quarto-needs.toml` (enable all four renderers)
- Modify: `docs/manual/c4-architecture-views.qmd`, `docs/manual/c4-architecture-views.pt-BR.qmd`
- Modify: `docs/phase-6-architecture-c4.md`, `docs/ROADMAP.md`

- [ ] **Step 1: Enable every backend in the example**

In `examples/quarto-needs/.quarto-needs.toml`:

```toml
[architecture.c4]
renderer = "mermaid"
enabled-renderers = ["mermaid", "structurizr", "plantuml", "d2"]

[architecture.c4.renderers.d2]
layout = "elk"

[architecture.c4.renderers.plantuml]
direction = "left-right"
```

`mermaid` stays the default so every existing view renders as a diagram; the other three write side artifacts that the showcase page displays as source.

- [ ] **Step 2: Write the showcase page**

Create `examples/quarto-needs/architecture-renderers.qmd`:

```markdown
---
title: "One model, four renderers"
---

Every diagram below is generated from **the same** C4 view — the same
elements, the same roles, the same relationships, the same
`quarto-needs-c4-view-v1` fingerprint. Only the backend changes. No `.qmd`
engineering object, no relation and no C4 semantic differs between them.

Mermaid renders inline because Quarto bundles it. The other three are shown
as generated source: Quarto-Needs writes valid input for each toolchain but
does not execute an external renderer, so nothing here requires a binary you
have not installed yourself.

## Mermaid

{{< need-c4 view="system-context" scope="SYS-QUARTO-NEEDS" renderer="mermaid" >}}

## Structurizr

{{< need-c4 view="system-context" scope="SYS-QUARTO-NEEDS" renderer="structurizr" >}}

## C4-PlantUML

{{< need-c4 view="system-context" scope="SYS-QUARTO-NEEDS" renderer="plantuml" >}}

## D2

{{< need-c4 view="system-context" scope="SYS-QUARTO-NEEDS" renderer="d2" >}}

## Why this page is also a test

If all four blocks above are present, every backend consumed one identical
intermediate representation — which is evidence that no renderer-specific
concept has leaked back into the engineering model. The same property is
asserted mechanically in `tests/test_c4_renderer_parity.py`.
```

Mirror it to `architecture-renderers.pt-BR.qmd` with translated prose and identical shortcodes, and add both to `_quarto.yml` (and the pt-BR book configuration, following how the existing pages are listed there).

- [ ] **Step 3: Add a render test for the showcase**

Add to `tests/test_quarto_views.py`:

```python
@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_need_c4_renderer_override_emits_each_backends_source(tmp_path: Path):
    """`renderer=` overrides the default; unknown-to-Quarto formats become code."""
    project = build_c4_fixture_project(tmp_path)
    (project / ".quarto-needs.toml").write_text(
        'profile = "default"\n\n'
        "[architecture.c4]\n"
        'renderer = "mermaid"\n'
        'enabled-renderers = ["mermaid", "structurizr", "plantuml", "d2"]\n',
        encoding="utf-8",
    )
    (project / "backends.qmd").write_text(
        '---\ntitle: "Backends"\n---\n\n'
        '{{< need-c4 view="system-context" scope="SYS-1" renderer="structurizr" >}}\n\n'
        '{{< need-c4 view="system-context" scope="SYS-1" renderer="plantuml" >}}\n\n'
        '{{< need-c4 view="system-context" scope="SYS-1" renderer="d2" >}}\n',
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, "-m", "quarto_needs.cli_entry", "--root", str(project), "scan"],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    html = (project / "_site" / "backends.html").read_text(encoding="utf-8")
    assert "workspace {" in html
    assert "@startuml" in html
    assert "direction:" in html
```

Check how `build_c4_fixture_project` currently runs the scan and reuse that mechanism rather than the `subprocess` call sketched above if it differs; the point is that the artifacts must be regenerated after the configuration changes.

- [ ] **Step 4: Extend the manual page**

Add to `docs/manual/c4-architecture-views.qmd` (and its pt-BR mirror):

- a backend table: name, source format, file extension, auto-layout, whether it renders inline in Quarto;
- installation notes for PlantUML, Structurizr CLI and D2, stated as *optional* — Quarto-Needs generates their source without them, and an absent binary never fails an analysis (Spec §24);
- the D2 layout-engine setting and the note that `tala` is proprietary;
- the diagnostic codes this plan adds: `C4012` (PlantUML approximated a direction), `C4013` (D2 layout engine unknown or proprietary);
- the sentence Spec §49 requires, verbatim in substance: *different renderers may produce different geometry and styling while representing the same architecture semantics*;
- Spec §50's Mermaid note: the zero-configuration default, whose C4 *layout* is less sophisticated than the alternatives — a rendering limitation, not a semantic one;
- the honest statement that no adapter executes an external binary in this milestone: Structurizr, PlantUML and D2 produce source, and turning that source into an image is the reader's own toolchain step.

- [ ] **Step 5: Update the phase document and roadmap**

In `docs/phase-6-architecture-c4.md`, add a section for this slice: the three new backends, the ancestors addition and why it was needed, the golden and parity coverage, and the two renderer-owned diagnostics. Keep the existing "known limitations" section and add one: **no adapter executes an external renderer**, so `capabilities.svg` is `False` for Structurizr, PlantUML and D2, and `C4004`/`C4005` remain the documented codes for the day that changes.

In `docs/ROADMAP.md`, extend Phase 6's parenthetical to name the four backends and the parity invariant.

- [ ] **Step 6: Verify and commit**

```bash
python -m quarto_needs.cli_entry --root examples/quarto-needs scan
ls examples/quarto-needs/.quarto-needs/c4/system-context/SYS_QUARTO_NEEDS
quarto render examples/quarto-needs
quarto render docs/manual --to html
python -m pytest -q
```

Expected: the view directory contains `view.json`, `mermaid.json/.mmd`, `structurizr.json/.dsl`, `plantuml.json/.puml`, `d2.json/.d2`; both sites build; the suite is green. Report which of these actually ran — if `quarto` is not installed, say so rather than implying the renders passed.

```bash
git add examples/quarto-needs docs tests/test_quarto_views.py
git commit -m "docs: add the four-backend showcase and document renderer selection"
```

---

## Acceptance check (Spec §51)

Run this at the end of Plan B and record the result. Every line maps to a spec acceptance criterion.

```bash
python -m pytest -q
python -m quarto_needs.cli_entry c4 renderers
python -m quarto_needs.cli_entry --root examples/quarto-needs c4 project --view system-context --format json | head -5
python -m quarto_needs.cli_entry --root examples/quarto-needs c4 render --view system-context --all | grep '^# --- renderer:'
python -m quarto_needs.cli_entry --root examples/quarto-needs c4 render
grep -rn "http" tests/golden/c4/ || echo "goldens are offline-clean"
```

Expected: a green suite; four renderers listed with capabilities; a `quarto-needs-c4-view-v1` document; four `# --- renderer:` separators; a full artifact tree; and no URL in any golden.

Then walk Spec §51's checklist and mark each box, noting explicitly the two that this milestone deliberately does not satisfy in full:

- *"Structurizr adapter works" / "PlantUML adapter works" / "D2 adapter works"* — they generate valid source; they do not produce images, by the owner's recorded decision.
- *"optional real-parser integration tests exist"* — they exist and are skipped unless the tool is installed; say which ones actually ran on this machine.
