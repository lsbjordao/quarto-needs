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


LUA_FACADE_ASSERTIONS = r'''
local views = dofile(__VIEWS_PATH__)

function Pandoc(doc)
  local graph, message = views.load(__GRAPH_PATH__)
  assert(graph ~= nil, "the fixture graph must load through the facade: " .. tostring(message))

  assert(views.get(graph, "REQ-APPROVED").title == "Authenticate administrators", "views.get must delegate to the cache")
  assert(views.get(graph, "MISSING") == nil, "views.get must not invent objects")
  assert(#views.outgoing(graph, "REQ-APPROVED", "verified-by") == 1, "views.outgoing must delegate to the cache")
  assert(#views.incoming(graph, "TC-LOGIN", "verified-by") == 1, "views.incoming must expose backlinks")
  assert(#views.incoming(graph, "REQ-APPROVED", "verified-by") == 0, "backlinks must stay oriented")

  local related = views.related(graph, "REQ-APPROVED", "verified-by")
  assert(#related == 1 and pandoc.utils.stringify(related[1]) == "TC-LOGIN", "views.related must keep returning target IDs")
  assert(#views.related(graph, "REQ-APPROVED", "derives-from") == 0, "relation filters must stay exact")

  local target = views.get(graph, "TC-LOGIN")
  local from_index = views.link(target, "TC-LOGIN", {format = "html", current_input = "index.qmd"})
  assert(from_index.target == "nested/details.html#TC-LOGIN", "cross-page HTML links must be relative, got " .. from_index.target)
  local from_page = views.link(target, "TC-LOGIN", {format = "html", current_input = "nested/details.qmd"})
  assert(from_page.target == "#TC-LOGIN", "same-page links must stay anchors")
  local printed = views.link(target, "TC-LOGIN", {format = "pdf", current_input = "index.qmd"})
  assert(printed.target == "#TC-LOGIN", "print formats must stay anchor-only")
  assert(pandoc.utils.stringify(from_index.content) == "TC-LOGIN", "links must keep their label")
  return doc
end
'''

# PlantUML and D2 lead their SVG with an XML prolog; Structurizr and Mermaid
# do not. An inline HTML fragment has no place for that prolog -- an HTML
# parser turns `<?xml ...?>` into a bogus comment -- so the figure attributes
# must land on the <svg> root element, never on whatever comes before it.
LUA_DIAGRAM_SVG_ASSERTIONS = r"""
local views = dofile(__VIEWS_PATH__)

local sources = {
  {backend = "d2", source = 'a: "A"\nb: "B"\na -> b: "uses"\n'},
  {backend = "plantuml", source = "@startuml\nAlice -> Bob: hello\n@enduml\n"},
  {backend = "structurizr", source = table.concat({
    "workspace {",
    "  model {",
    '    u = person "User"',
    '    s = softwareSystem "System"',
    '    u -> s "Uses"',
    "  }",
    "  views {",
    "    systemContext s {",
    "      include *",
    "      autoLayout",
    "    }",
    "  }",
    "}",
  }, "\n")},
}

function Pandoc(doc)
  for _, case in ipairs(sources) do
    local backend = case.backend
    local svg = views.diagram_inline_svg(backend, case.source, "Architecture diagram", "need-c4-figure")
    assert(svg, backend .. ": renderer produced no SVG")
    assert(svg:sub(1, 4) == "<svg", backend .. ": inline SVG must start at the root element, got " .. svg:sub(1, 60))
    assert(not svg:find("<?xml", 1, true), backend .. ": XML prolog must not reach inline HTML")
    local open_tag = svg:sub(1, svg:find(">", 1, true))
    assert(open_tag:find('class="need%-c4%-figure"'), backend .. ": class must land on <svg>, got " .. open_tag)
    assert(open_tag:find('role="img"'), backend .. ": role must land on <svg>, got " .. open_tag)
    assert(open_tag:find('aria%-label="Architecture diagram"'), backend .. ": aria-label must land on <svg>, got " .. open_tag)
    assert(open_tag:find('width="100%%"'), backend .. ": responsive width must land on <svg>, got " .. open_tag)
  end
  return doc
end
"""


def run_lua_assertions(
    tmp_path: Path, assertions: str, graph: Path | None = None
) -> None:
    rendered = assertions.replace("__VIEWS_PATH__", json.dumps(str(VIEWS)))
    if graph is not None:
        rendered = rendered.replace("__GRAPH_PATH__", json.dumps(str(graph)))
    assertion_filter = tmp_path / "views_assertions.lua"
    assertion_filter.write_text(rendered, encoding="utf-8")
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


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_views_delegate_to_the_cached_graph_and_format_links(
    tmp_path: Path, views_fixture_graph: Path
):
    """The facade keeps its legacy API while every link flows through the resolver."""
    run_lua_assertions(tmp_path, LUA_FACADE_ASSERTIONS, graph=views_fixture_graph)


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
@pytest.mark.skipif(shutil.which("d2") is None, reason="d2 is not installed")
@pytest.mark.skipif(shutil.which("plantuml") is None, reason="PlantUML is not installed")
@pytest.mark.skipif(shutil.which("structurizr") is None, reason="Structurizr is not installed")
def test_optional_backend_svgs_carry_their_figure_attributes(tmp_path: Path):
    """Every optional backend must hand back one properly attributed inline SVG.

    PlantUML and D2 lead their output with an XML prolog, which used to absorb
    the figure attributes; Structurizr does not, and guards the CI wrapper.
    """
    run_lua_assertions(tmp_path, LUA_DIAGRAM_SVG_ASSERTIONS)
