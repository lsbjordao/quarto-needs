# Task 1: Freeze the public projection and its privacy contract

> Extracted from `docs/superpowers/plans/2026-08-26-quarto-needs-milestone-5a-interactive-graph-execution.md`. This brief is your complete requirements.
> Use every value in it verbatim.

## Global Constraints (bind every task)

- Do not add a runtime Python dependency. Cytoscape.js is vendored into the extension with a pinned version, a recorded license, and a SHA-256 checksum; it is never fetched at render time.
- The browser receives only the public projection. Bodies, rationales, local filesystem paths, source locations, and undeclared attributes never reach it. Projection construction **fails closed**: a field a view requests but policy does not publish is an error, not an omission.
- Static output is not a fallback in the sense of "lesser". For every graph instance the renderer emits a deterministic diagram, an accessible table carrying source, relation, target, change state and impact explanation, and a summary with counts. "Equivalent" means the same nodes, relations, change classifications, and impact paths — not identical layout.
- Keyboard operation and a working non-JavaScript representation are acceptance criteria for this milestone, not later polish. There is no separate hardening milestone.
- Graph limits produce a visible narrowing prompt naming actual counts and configured limits. They never silently truncate.
- Layout is deterministic: a stored seed and explicit tie-breaking, so two renders of unchanged input produce the same asset bytes.
- Preserve every existing CLI command, shortcode, exit code, and schema. `needs.json` bytes do not change for a project that requests no graph.
- The interactive client initializes only after the static content is present and the projection validates, and hides the fallback only on success.
- The workspace may or may not have Git metadata. Tasks end with a conditional checkpoint that commits only inside a Git worktree.
- Do not stop or restart the preview server on `127.0.0.1:8777`.

## Task 1

Freeze the public projection and its privacy contract

This task is the security boundary of the whole milestone. Everything after it trusts that what reaches the browser was filtered here.

**Files:**
- Create: `src/quarto_needs/graph_projection.py`
- Create: `schemas/graph-public-v1.schema.json`
- Create: `tests/test_graph_projection.py`
- Create: `tests/fixtures/graph/adversarial.qmd`

**Interfaces:**
- Consumes: `AnalysisSnapshot` from `src/quarto_needs/snapshot.py`; `ObjectRecord.priority` and `.tags`.
- Produces:
  - `graph_projection.PublicNode`, `PublicEdge`, `GraphProjection` (frozen dataclasses)
  - `graph_projection.build_projection(snapshot, *, node_ids, view_id, mode="catalog", limits=None) -> GraphProjection`
  - `graph_projection.render_projection(projection) -> str` (canonical JSON)
  - `graph_projection.PUBLIC_NODE_FIELDS`, `PUBLIC_EDGE_FIELDS`

- [ ] **Step 1: Write the adversarial fixture**

Create `tests/fixtures/graph/adversarial.qmd`. Every denied value carries a unique token, so a test can search the serialized output for it rather than checking only the fields someone remembered to check:

```qmd
::: {.need #ADV-1 type=functional-requirement status=approved priority=high tags="public-tag" secret-attribute="LEAKCANARYATTR7f3a"}
## Publishable title

LEAKCANARYBODY91cd is body prose and must never reach the browser.

### Rationale
LEAKCANARYRATIONALE4e77 explains why and is equally private.
:::

::: {.need #ADV-2 type=test-case status=passed tags="public-tag"}
## Second publishable title

LEAKCANARYBODY2b80 is more private prose.
:::
```

- [ ] **Step 2: Write the failing privacy tests**

Create `tests/test_graph_projection.py`. The canary test is the load-bearing one: it does not enumerate fields, it asserts that no denied *value* appears anywhere in the serialized projection.

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quarto_needs import graph_projection
from quarto_needs.analysis import analyze_project

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "graph" / "adversarial.qmd"
SCHEMA = ROOT / "schemas" / "graph-public-v1.schema.json"

CANARIES = (
    "LEAKCANARYATTR7f3a",
    "LEAKCANARYBODY91cd",
    "LEAKCANARYRATIONALE4e77",
    "LEAKCANARYBODY2b80",
)


def projection_of(tmp_path: Path):
    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = analyze_project(tmp_path)
    assert result.snapshot is not None
    return graph_projection.build_projection(
        result.snapshot,
        node_ids=("ADV-1", "ADV-2"),
        view_id="need-graph-1",
    )


def test_no_denied_value_reaches_the_projection(tmp_path: Path) -> None:
    """Search the serialized output for denied values, not for field names.

    Enumerating fields only catches leaks through paths someone anticipated. A
    canary search catches a leak through any path at all, including a future
    field added without thinking about publication policy.
    """
    serialized = graph_projection.render_projection(projection_of(tmp_path))

    for canary in CANARIES:
        assert canary not in serialized, f"{canary} reached the public projection"


def test_projection_validates_against_its_schema(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(json.loads(graph_projection.render_projection(projection_of(tmp_path))))


def test_only_allowlisted_fields_are_emitted(tmp_path: Path) -> None:
    payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))

    for node in payload["nodes"]:
        assert set(node) <= set(graph_projection.PUBLIC_NODE_FIELDS), f"unexpected keys: {set(node)}"
    for edge in payload["edges"]:
        assert set(edge) <= set(graph_projection.PUBLIC_EDGE_FIELDS)


def test_publishable_content_is_present(tmp_path: Path) -> None:
    """Deny-by-default must not degrade into deny-everything."""
    payload = json.loads(graph_projection.render_projection(projection_of(tmp_path)))

    node = next(item for item in payload["nodes"] if item["id"] == "ADV-1")
    assert node["title"] == "Publishable title"
    assert node["type"] == "functional-requirement"
    assert node["status"] == "approved"
    assert node["priority"] == "high"
    assert node["tags"] == ["public-tag"]


def test_render_is_byte_stable(tmp_path: Path) -> None:
    assert graph_projection.render_projection(projection_of(tmp_path)) == \
        graph_projection.render_projection(projection_of(tmp_path))


def test_node_order_is_deterministic_and_independent_of_request_order(tmp_path: Path) -> None:
    (tmp_path / "adversarial.qmd").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    result = analyze_project(tmp_path)
    assert result.snapshot is not None

    forward = graph_projection.build_projection(result.snapshot, node_ids=("ADV-1", "ADV-2"), view_id="v")
    reverse = graph_projection.build_projection(result.snapshot, node_ids=("ADV-2", "ADV-1"), view_id="v")

    assert graph_projection.render_projection(forward) == graph_projection.render_projection(reverse)
```

- [ ] **Step 3: Run them and verify they fail**

Run: `.venv/bin/python -m pytest tests/test_graph_projection.py -q`

Expected: FAIL with `ImportError` or `ModuleNotFoundError` naming `graph_projection`.

- [ ] **Step 4: Write the schema**

Create `schemas/graph-public-v1.schema.json`. `additionalProperties: false` on every object is what makes a leak fail loudly instead of passing through:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://quarto-needs.dev/schema/graph-public-v1.schema.json",
  "title": "Quarto-Needs public graph projection v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schemaVersion", "view", "nodes", "edges"],
  "properties": {
    "schemaVersion": {"const": "graph-public-v1"},
    "view": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "mode", "limits"],
      "properties": {
        "id": {"type": "string"},
        "layout": {"type": "string"},
        "mode": {"enum": ["catalog", "diff", "impact"]},
        "seed": {"type": "integer"},
        "limits": {
          "type": "object",
          "additionalProperties": false,
          "required": ["nodes", "edges"],
          "properties": {"nodes": {"type": "integer"}, "edges": {"type": "integer"}}
        }
      }
    },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "title", "type", "status"],
        "properties": {
          "id": {"type": "string"},
          "title": {"type": "string"},
          "type": {"type": "string"},
          "status": {"type": "string"},
          "priority": {"type": ["string", "null"]},
          "tags": {"type": "array", "items": {"type": "string"}},
          "href": {"type": "string"},
          "change": {"enum": ["added", "removed", "modified", "relocated", "unchanged"]}
        }
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["source", "target", "relation", "label"],
        "properties": {
          "source": {"type": "string"},
          "target": {"type": "string"},
          "relation": {"type": "string"},
          "label": {"type": "string"},
          "change": {"enum": ["added", "removed", "unchanged"]},
          "pathMember": {"type": "boolean"}
        }
      }
    },
    "impact": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["id", "origin", "distance", "path"],
        "properties": {
          "id": {"type": "string"},
          "origin": {"type": "string"},
          "classification": {"enum": ["direct", "transitive"]},
          "distance": {"type": "integer", "minimum": 1},
          "path": {"type": "array", "items": {"type": "string"}, "minItems": 2}
        }
      }
    }
  }
}
```

- [ ] **Step 5: Implement the projection**

Create `src/quarto_needs/graph_projection.py`. Build every node by naming the fields explicitly — never by copying a record and removing keys, because that inverts the default and a new private field would ship:

```python
"""The reduced projection the browser is allowed to see.

Deny by default: nodes and edges are constructed field by field from an
allowlist. Nothing is copied wholesale and filtered afterwards, because that
inverts the default — a field added to `ObjectRecord` later would ship to the
browser until someone remembered to exclude it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from .relations import DEFAULT_RELATION_CATALOG
from .snapshot import AnalysisSnapshot, ObjectRecord, RelationRecord

SCHEMA_VERSION = "graph-public-v1"

PUBLIC_NODE_FIELDS = ("id", "title", "type", "status", "priority", "tags", "href", "change")
PUBLIC_EDGE_FIELDS = ("source", "target", "relation", "label", "change", "pathMember")

DEFAULT_LIMITS = {"nodes": 100, "edges": 300}


@dataclass(frozen=True, slots=True)
class PublicNode:
    id: str
    title: str
    type: str
    status: str
    priority: str | None
    tags: tuple[str, ...]
    href: str
    change: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "priority": self.priority,
            "tags": list(self.tags),
            "href": self.href,
        }
        if self.change is not None:
            payload["change"] = self.change
        return payload


@dataclass(frozen=True, slots=True)
class PublicEdge:
    source: str
    target: str
    relation: str
    label: str
    change: str | None = None
    path_member: bool | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "label": self.label,
        }
        if self.change is not None:
            payload["change"] = self.change
        if self.path_member is not None:
            payload["pathMember"] = self.path_member
        return payload


@dataclass(frozen=True, slots=True)
class GraphProjection:
    view_id: str
    mode: str
    limits: Mapping[str, int]
    nodes: tuple[PublicNode, ...]
    edges: tuple[PublicEdge, ...]
    impact: tuple[Mapping[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": SCHEMA_VERSION,
            "view": {
                "id": self.view_id,
                "mode": self.mode,
                "limits": dict(self.limits),
            },
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }
        if self.impact:
            payload["impact"] = [dict(item) for item in self.impact]
        return payload


def _public_href(record: ObjectRecord) -> str:
    """Anchor-only by default.

    A resolved cross-page href is safe to publish, but it is built by the Lua
    link resolver at render time, where the output format and current page are
    known. Emitting a filesystem-derived path here would leak project layout.
    """
    return "#" + record.id


def _label_for(relation: RelationRecord) -> str:
    try:
        return DEFAULT_RELATION_CATALOG.resolve(relation.authored_name).direct_label
    except ValueError:
        return relation.authored_name


def build_projection(
    snapshot: AnalysisSnapshot,
    *,
    node_ids: Iterable[str],
    view_id: str,
    mode: str = "catalog",
    limits: Mapping[str, int] | None = None,
) -> GraphProjection:
    selected = {str(item) for item in node_ids}
    nodes = tuple(
        PublicNode(
            id=record.id,
            title=record.title,
            type=record.type,
            status=record.status,
            priority=record.priority,
            tags=record.tags,
            href=_public_href(record),
        )
        for record in snapshot.objects
        if record.id in selected
    )
    edges = tuple(
        PublicEdge(
            source=relation.source,
            target=relation.target,
            relation=relation.v1_name,
            label=_label_for(relation),
        )
        for relation in snapshot.relations
        if relation.source in selected and relation.target in selected
    )
    return GraphProjection(
        view_id=view_id,
        mode=mode,
        limits=dict(limits or DEFAULT_LIMITS),
        nodes=nodes,
        edges=edges,
    )


def render_projection(projection: GraphProjection) -> str:
    return json.dumps(projection.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
```

Node and edge order follow `snapshot.objects` and `snapshot.relations`, which the analysis builder already sorts deterministically — that is what makes the request-order test pass without a second sort here.

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_graph_projection.py -q`

Expected: PASS, all six.

- [ ] **Step 7: Falsify every deny assertion**

A passing privacy test proves nothing until you have watched it fail. For each of the four canaries, temporarily add the corresponding private field to `PublicNode.to_dict()` — `"body": record.body` and so on — confirm `test_no_denied_value_reaches_the_projection` fails naming that canary, then restore and verify the restoration with `diff` rather than assuming it.

Report all four experiments. A canary that cannot be made to fail is testing nothing.

- [ ] **Step 8: Run the full suite**

Run: `.venv/bin/python -m pytest -q`

Expected: PASS with no new warnings. Nothing in this task touches an existing code path.

- [ ] **Step 9: Record the checkpoint conditionally**

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add src/quarto_needs/graph_projection.py schemas/graph-public-v1.schema.json tests/test_graph_projection.py tests/fixtures/graph/adversarial.qmd
  git commit -m "feat: add the deny-by-default public graph projection"
else
  echo "Checkpoint 1 verified; workspace has no Git metadata."
fi
```
