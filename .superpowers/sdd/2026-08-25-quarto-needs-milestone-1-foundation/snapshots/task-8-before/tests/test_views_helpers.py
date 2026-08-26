from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEWS = ROOT / "_extensions" / "quarto-needs" / "views.lua"


LUA_ASSERTIONS = r'''
local views = dofile(__VIEWS_PATH__)

local objects = {
  {id = "REQ-ALPHA", type = "Functional-Requirement", status = "Approved", attributes = {priority = "High", tags = "Security; Authentication"}},
  {id = "REQ-BETA", type = "System-Requirement", status = "Draft", attributes = {priority = "Low", tags = {"authentication", "Lifecycle"}}},
  {id = "REQ-GAMMA", type = "Functional-Requirement", status = "In-Review", attributes = {priority = "Critical", tags = "security, audit"}},
}

local function ids(items)
  local result = {}
  for _, item in ipairs(items) do table.insert(result, item.id) end
  return table.concat(result, ",")
end

local function expect(name, kwargs, wanted)
  local actual = ids(views.filter(objects, kwargs))
  assert(actual == wanted, name .. ": expected " .. wanted .. ", got " .. actual)
end

function Pandoc(doc)
  expect("no filters", {}, "REQ-ALPHA,REQ-BETA,REQ-GAMMA")
  expect("ids", {ids = "req-alpha"}, "REQ-ALPHA")
  expect("types", {types = "functional-requirement"}, "REQ-ALPHA,REQ-GAMMA")
  expect("type alias", {type = "system-requirement"}, "REQ-BETA")
  expect("status", {status = "approved"}, "REQ-ALPHA")
  expect("priority", {priority = "critical"}, "REQ-GAMMA")
  expect("scalar tags", {tags = "authentication"}, "REQ-ALPHA,REQ-BETA")
  expect("list tags", {tags = "lifecycle"}, "REQ-BETA")
  expect("case insensitive", {status = "aPpRoVeD", priority = "hIgH", tags = "sEcUrItY"}, "REQ-ALPHA")
  expect("OR alternatives", {ids = "REQ-ALPHA;req-beta", status = "approved,draft"}, "REQ-ALPHA,REQ-BETA")

  local first = views.node_id("REQ-A")
  local second = views.node_id("REQ_A")
  local third = views.node_id("REQ/A")
  assert(first ~= second and first ~= third and second ~= third, "Mermaid IDs must not collide")
  assert(first == views.node_id("REQ-A"), "Mermaid IDs must be deterministic")
  assert(first:match("^[%a_][%w_]*$") ~= nil, "Mermaid ID must be a valid identifier")
  return doc
end
'''


LUA_VIEW_ID_ASSERTIONS = r'''
local views = dofile(__VIEWS_PATH__)

function Pandoc(doc)
  local first = views.reserve_view_id("need-table", "Release Notes")
  local repeated = views.reserve_view_id("need-table", "Release Notes")
  assert(first == "release-notes", "explicit IDs should be sanitized")
  assert(repeated == "release-notes-2", "repeated explicit IDs need a stable suffix")

  local malicious = views.reserve_view_id("need-table", 'bad" onmouseover="alert(1)')
  assert(malicious:match("^[a-z0-9]+%-?[a-z0-9%-]*$") ~= nil, "view IDs must be safe HTML identifiers")
  assert(not malicious:find('"', 1, true), "view IDs must not retain quotes")

  local explicit = views.reserve_view_id("need-table", "need-table-1")
  local automatic = views.next_id("need-table")
  local repeated_explicit = views.reserve_view_id("need-table", "need-table-1")
  assert(explicit == "need-table-1", "explicit ID should keep its safe spelling")
  assert(automatic == "need-table-1-2", "automatic ID must reserve around an explicit collision")
  assert(repeated_explicit == "need-table-1-3", "collision suffixes must be deterministic")
  return doc
end
'''


def run_lua_assertions(tmp_path: Path, assertions: str) -> None:
    assertion_filter = tmp_path / "views_assertions.lua"
    assertion_filter.write_text(assertions.replace("__VIEWS_PATH__", json.dumps(str(VIEWS))), encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("# View helper assertions\n", encoding="utf-8")
    subprocess.run(
        ["quarto", "pandoc", "--lua-filter", str(assertion_filter), "--to", "plain", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_view_filter_helpers_and_mermaid_ids(tmp_path: Path):
    """Filtering stays exact and Mermaid node IDs cannot collide after normalization."""
    run_lua_assertions(tmp_path, LUA_ASSERTIONS)


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_view_id_reservation_sanitizes_and_avoids_collisions(tmp_path: Path):
    """Explicit and automatic view IDs share one safe, deterministic registry."""
    run_lua_assertions(tmp_path, LUA_VIEW_ID_ASSERTIONS)
