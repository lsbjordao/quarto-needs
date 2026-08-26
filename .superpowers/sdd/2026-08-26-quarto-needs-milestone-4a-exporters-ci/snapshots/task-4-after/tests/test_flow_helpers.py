from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "_extensions" / "quarto-needs" / "flow.lua"
VIEWS = ROOT / "_extensions" / "quarto-needs" / "views.lua"


LUA_ASSERTIONS = r'''
local flow = dofile(__FLOW_PATH__)
local views = dofile(__VIEWS_PATH__)

local function object(id, object_type)
  return {id = id, title = "Title " .. id, type = object_type or "functional-requirement", attributes = {}}
end

local function contains(items, fragment)
  for _, item in ipairs(items or {}) do
    if item:find(fragment, 1, true) then return true end
  end
  return false
end

function Pandoc(doc)
  local graph = {
    objects = {
      object("C", "risk"),
      object("A", "functional-requirement"),
      object("B", "test-case"),
    },
    relations = {
      {source = "C", target = "A", type = "zeta"},
      {source = "A", target = "B", type = "alpha"},
      {source = "B", target = "C", type = "beta"},
      {source = "A", target = "B", type = "alpha"},
    },
  }
  local plan = flow.build(graph, {root = "A", depth = "2"}, views)
  assert(plan.node_count == 3, "root traversal should include the two-hop subgraph")
  assert(plan.edge_count == 3, "duplicate edges must be removed")
  local alpha = assert(plan.source:find("|alpha|", 1, true))
  local beta = assert(plan.source:find("|beta|", 1, true))
  local zeta = assert(plan.source:find("|zeta|", 1, true))
  assert(alpha < beta and beta < zeta, "edges must have deterministic sort order")
  assert(plan.source:find("need_type_functional_requirement fill:#dbeafe,stroke:#2563eb,color:#1e3a8a", 1, true))
  assert(plan.source:find("need_type_test_case fill:#ccfbf1,stroke:#0f766e,color:#134e4a", 1, true))

  local many_objects = {}
  for index = 105, 1, -1 do many_objects[#many_objects + 1] = object(string.format("N%03d", index)) end
  local bounded = flow.build({objects = many_objects, relations = {}}, {}, views)
  assert(bounded.node_count == 100, "rootless flows must enforce the node budget")
  assert(bounded.source:find("N100<br/>", 1, true))
  assert(not bounded.source:find("N101<br/>", 1, true), "the sorted tail must be truncated")
  assert(contains(bounded.warnings, "first 100"), "node truncation must be visible")

  local many_edges = {}
  for index = 305, 1, -1 do
    many_edges[#many_edges + 1] = {source = "A", target = "B", type = string.format("rel-%03d", index)}
  end
  local edge_bounded = flow.build({objects = {object("A"), object("B")}, relations = many_edges}, {}, views)
  assert(edge_bounded.edge_count == 300, "flows must enforce the edge budget")
  assert(contains(edge_bounded.warnings, "first 300"), "edge truncation must be visible")

  local chain_objects, chain_relations = {}, {}
  for index = 1, 20 do
    chain_objects[#chain_objects + 1] = object(string.format("D%02d", index))
    if index > 1 then
      chain_relations[#chain_relations + 1] = {
        source = string.format("D%02d", index - 1),
        target = string.format("D%02d", index),
        type = "next",
      }
    end
  end
  local depth_bounded = flow.build(
    {objects = chain_objects, relations = chain_relations},
    {root = "D01", depth = "999"},
    views
  )
  assert(depth_bounded.node_count == 11, "depth must be clamped to ten hops")
  assert(contains(depth_bounded.warnings, "depth is limited to 10"), "depth truncation must be visible")
  return doc
end
'''


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_flow_source_is_deterministic_bounded_and_type_styled(tmp_path: Path):
    """Traversal order cannot change output, exceed budgets, or erase type meaning."""
    assertion_filter = tmp_path / "flow_assertions.lua"
    assertion_filter.write_text(
        LUA_ASSERTIONS.replace("__FLOW_PATH__", json.dumps(str(FLOW))).replace(
            "__VIEWS_PATH__", json.dumps(str(VIEWS))
        ),
        encoding="utf-8",
    )
    source = tmp_path / "source.md"
    source.write_text("# Flow helper assertions\n", encoding="utf-8")

    subprocess.run(
        ["quarto", "pandoc", "--lua-filter", str(assertion_filter), "--to", "plain", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
