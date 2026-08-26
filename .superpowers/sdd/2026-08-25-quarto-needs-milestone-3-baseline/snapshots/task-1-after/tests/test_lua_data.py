from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "_extensions" / "quarto-needs" / "data.lua"
GRAPH = ROOT / "tests" / "fixtures" / "views" / ".quarto-needs" / "needs.json"


LUA_CACHE_ASSERTIONS = r'''
local data = dofile(__DATA_PATH__)

function Pandoc(doc)
  local original_open = io.open
  local opens = 0
  io.open = function(path, mode)
    if path == __GRAPH_PATH__ then opens = opens + 1 end
    return original_open(path, mode)
  end

  local first, first_error = data.load(__GRAPH_PATH__)
  local second, second_error = data.load(__GRAPH_PATH__)
  assert(first_error == nil and second_error == nil, "the fixture graph must load without an error")
  assert(first == second, "cache must return the same graph table")
  assert(opens == 1, "graph JSON must be opened once per process and path")
  assert(data.get(first, "REQ-APPROVED").title == "Authenticate administrators")
  assert(#data.outgoing(first, "REQ-APPROVED", "verified-by") == 1)
  assert(#data.incoming(first, "TC-LOGIN", "verified-by") == 1)

  assert(data.get(first, "MISSING") == nil, "unknown IDs must not resolve")
  assert(#data.outgoing(first, "REQ-APPROVED", "derives-from") == 0, "filters must be exact")
  assert(#data.outgoing(first, "REQ-APPROVED") == 1, "an omitted filter must keep every relation")
  assert(#data.incoming(first, "REQ-APPROVED") == 0, "backlinks must not invent edges")

  local borrowed = data.outgoing(first, "REQ-APPROVED", "verified-by")
  table.remove(borrowed)
  assert(#data.outgoing(first, "REQ-APPROVED", "verified-by") == 1, "callers must not mutate the cached adjacency")

  io.open = original_open
  return doc
end
'''


LUA_LOAD_ERROR_ASSERTIONS = r'''
local data = dofile(__DATA_PATH__)

function Pandoc(doc)
  local missing = __MISSING_PATH__
  local first_graph, first_error = data.load(missing)
  local second_graph, second_error = data.load(missing)
  assert(first_graph == nil and second_graph == nil, "a missing graph must never decode")
  assert(first_error == second_error, "the cached error must stay identical")
  assert(first_error:find("Quarto Needs graph not found", 1, true) == 1, "the error must stay meaningful")

  local invalid_graph, invalid_error = data.load(__INVALID_PATH__)
  assert(invalid_graph == nil, "malformed JSON must not produce an empty graph")
  assert(invalid_error:find("Quarto Needs graph is invalid", 1, true) == 1, "invalid graphs must say so")
  return doc
end
'''


LUA_LINK_ASSERTIONS = r'''
local data = dofile(__DATA_PATH__)

function Pandoc(doc)
  local target = {id = "TC-LOGIN", href = "nested/details.html#TC-LOGIN", source = {file = "nested/details.qmd", anchor = "TC-LOGIN"}}
  assert(data.link_target(target, {format = "html", current_input = "index.qmd"}) == "nested/details.html#TC-LOGIN")
  assert(data.link_target(target, {format = "html", current_input = "nested/details.qmd"}) == "#TC-LOGIN")
  assert(data.link_target(target, {format = "html", current_input = "chapters/trace.qmd"}) == "../nested/details.html#TC-LOGIN")
  assert(data.link_target(target, {format = "docx", current_input = "index.qmd"}) == "#TC-LOGIN")
  assert(data.link_target(target, {format = "pdf", current_input = "index.qmd"}) == "#TC-LOGIN")

  assert(data.link_target(target, {format = "latex", current_input = "index.qmd"}) == "#TC-LOGIN")
  assert(data.link_target(target, {format = "html", current_input = "nested/trace.qmd"}) == "details.html#TC-LOGIN",
    "siblings must resolve without a parent hop")
  assert(data.link_target(target, {format = "html", current_input = "./index.qmd"}) == "nested/details.html#TC-LOGIN",
    "dot segments must normalize")

  local anchored = {id = "TC-LOGIN", source = {file = "nested/details.qmd", anchor = "custom-anchor"}}
  assert(data.link_target(anchored, {format = "html", current_input = "index.qmd"}) == "nested/details.html#custom-anchor")
  assert(data.link_target(anchored, {format = "docx", current_input = "index.qmd"}) == "#custom-anchor")

  local escaping = {id = "TC-LOGIN", source = {file = "../outside/details.qmd", anchor = "TC-LOGIN"}}
  assert(data.link_target(escaping, {format = "html", current_input = "index.qmd"}) == "#TC-LOGIN",
    "traversal above the project root must be rejected")

  local legacy = {id = "REQ-LEGACY", href = "legacy.html#REQ-LEGACY"}
  assert(data.link_target(legacy, {format = "html", current_input = "index.qmd"}) == "legacy.html#REQ-LEGACY")
  local bare = {id = "REQ-BARE"}
  assert(data.link_target(bare, {format = "html", current_input = "index.qmd"}) == "#REQ-BARE")
  local blank = {id = "REQ-BLANK", href = ""}
  assert(data.link_target(blank, {format = "html", current_input = "index.qmd"}) == "#REQ-BLANK")
  return doc
end
'''


def run_lua_assertions(tmp_path: Path, assertions: str, substitutions: dict[str, Path]) -> None:
    """Execute Lua assertions through the Quarto-bundled Pandoc interpreter."""
    rendered = assertions.replace("__DATA_PATH__", json.dumps(str(DATA)))
    for placeholder, value in substitutions.items():
        rendered = rendered.replace(placeholder, json.dumps(str(value)))
    assertion_filter = tmp_path / "data_assertions.lua"
    assertion_filter.write_text(rendered, encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("# Data helper assertions\n", encoding="utf-8")
    subprocess.run(
        ["quarto", "pandoc", "--lua-filter", str(assertion_filter), "--to", "plain", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_graph_is_read_once_and_indexed_per_process(tmp_path: Path):
    """Repeated loads share one decoded graph, one open, and immutable adjacency."""
    run_lua_assertions(tmp_path, LUA_CACHE_ASSERTIONS, {"__GRAPH_PATH__": GRAPH})


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_unreadable_graphs_cache_a_meaningful_error(tmp_path: Path):
    """A missing or malformed graph keeps reporting why, never an empty graph."""
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{ not json", encoding="utf-8")
    run_lua_assertions(
        tmp_path,
        LUA_LOAD_ERROR_ASSERTIONS,
        {"__MISSING_PATH__": tmp_path / "absent.json", "__INVALID_PATH__": invalid},
    )


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_link_target_resolves_by_format_and_source_page(tmp_path: Path):
    """Only HTML gets relative page paths; every other format stays anchor-only."""
    run_lua_assertions(tmp_path, LUA_LINK_ASSERTIONS, {})
