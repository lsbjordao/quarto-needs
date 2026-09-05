from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "_extensions" / "quarto-needs" / "graph.lua"
VIEWS = ROOT / "_extensions" / "quarto-needs" / "views.lua"


LUA_ASSERTIONS = r'''
local graph = dofile(__GRAPH_PATH__)
local views = dofile(__VIEWS_PATH__)

local function node(id, node_type)
  return {id = id, title = "Title " .. id, type = node_type or "functional-requirement"}
end

function Pandoc(doc)
  local projection = {
    nodes = {
      node("REQ-1", "functional-requirement"),
      node("SYS-1", "system"),
      node("ACTOR-1", "actor"),
    },
    edges = {
      {source = "REQ-1", target = "SYS-1", label = "depends-on"},
    },
  }
  local source = graph.mermaid_source(projection)

  -- Every node carries a type-scoped class, and there is one classDef per
  -- type used -- the same shared palette flow.lua draws from, so a node's
  -- color agrees with its card badge's color on the same page. Node refs
  -- are compact sequential aliases (mermaid's fixed maxTextSize cannot be
  -- raised through Quarto's render pipeline), assigned in the projection's
  -- deterministic first-appearance order.
  assert(source:find("class n1 need_type_functional_requirement", 1, true),
    "REQ-1 must carry its type class")
  assert(source:find('n1["REQ-1 · Title REQ-1', 1, true),
    "REQ-1's label must stay on its own alias")
  assert(source:find("class n2 need_type_system", 1, true),
    "SYS-1 must carry its type class")
  assert(source:find("classDef need_type_functional_requirement fill:#dbeafe,stroke:#2563eb,color:#1e3a8a", 1, true),
    "functional-requirement classDef must match the shared palette")
  assert(source:find("classDef need_type_system fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e", 1, true),
    "system classDef must be defined, not left to fall back to gray")
  assert(source:find("classDef need_type_actor fill:#fce7f3,stroke:#be185d,color:#831843", 1, true),
    "actor classDef must be defined, not left to fall back to gray")
  assert(source:find('n1 -->|"depends-on"| n2', 1, true),
    "edges must reference their endpoints by the same aliases")

  -- classDef lines must be deterministically ordered, independent of
  -- traversal order, the same guarantee flow.lua already gives edges.
  local actor_pos = assert(source:find("classDef need_type_actor", 1, true))
  local functional_pos = assert(source:find("classDef need_type_functional_requirement", 1, true))
  local system_pos = assert(source:find("classDef need_type_system", 1, true))
  assert(actor_pos < functional_pos and functional_pos < system_pos,
    "classDef lines must be sorted by class name")

  -- An undeclared type still gets a class and a classDef -- the shared
  -- fallback color, never bare, uncolored mermaid syntax.
  local unknown = graph.mermaid_source({nodes = {node("X-1", "not-a-real-type")}, edges = {}})
  assert(unknown:find("class n1 need_type_not_a_real_type", 1, true),
    "an undeclared type must still carry a class")
  assert(unknown:find("classDef need_type_not_a_real_type fill:#f8fafc,stroke:#64748b,color:#1e293b", 1, true),
    "an unrecognized type must still resolve to the shared fallback color")

  return doc
end
'''


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_graph_mermaid_source_colors_every_node_by_type(tmp_path: Path):
    """The static (no-JS) graph diagram must color nodes by type, the same
    way need-flow already does and the same way every card badge on the
    page does -- never bare black-and-white boxes, and never a type that
    silently falls through to no color at all.
    """
    assertion_filter = tmp_path / "graph_assertions.lua"
    assertion_filter.write_text(
        LUA_ASSERTIONS.replace("__GRAPH_PATH__", json.dumps(str(GRAPH))).replace(
            "__VIEWS_PATH__", json.dumps(str(VIEWS))
        ),
        encoding="utf-8",
    )
    source = tmp_path / "source.md"
    source.write_text("# Graph helper assertions\n", encoding="utf-8")

    subprocess.run(
        ["quarto", "pandoc", "--lua-filter", str(assertion_filter), "--to", "plain", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
