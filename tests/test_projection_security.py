"""Release gate: authored content must never escape a published projection.

The interactive graph hands its projection to the browser inside
``<script type="application/json">`` elements. JSON escaping is not HTML
escaping: a title containing the literal ``</script>`` closes the element
early and everything after it is parsed as markup. These tests pin the
escaping at the embedding boundary and exercise it through a real render.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VIEWS_LUA = ROOT / "_extensions" / "quarto-needs" / "views.lua"
GRAPH_LUA = ROOT / "_extensions" / "quarto-needs" / "graph.lua"
FIXTURE = ROOT / "tests" / "fixtures" / "security"

LUA_SCRIPT_JSON_ASSERTIONS = r'''
local views = dofile(__VIEWS_PATH__)

function Pandoc(doc)
  local hostile = '</script><script>alert(1)</script> & <b>bold</b>'
  local payload = '{"title":"' .. hostile .. '"}'
  local safe = views.script_json(payload)

  assert(safe:find("</script>", 1, true) == nil, "a closing script tag must not survive")
  assert(safe:find("<", 1, true) == nil, "no raw less-than may survive")
  assert(safe:find(">", 1, true) == nil, "no raw greater-than may survive")
  assert(safe:find("&", 1, true) == nil, "no raw ampersand may survive")
  assert(safe:find("\\u003c", 1, true) ~= nil, "a less-than must survive as a JSON escape")

  local decoded = pandoc.json.decode(safe)
  assert(decoded.title == hostile, "escaping must round-trip through JSON decoding")

  local separator = string.char(226, 128, 168)
  local line = views.script_json('{"title":"a' .. separator .. 'b"}')
  assert(line:find("\\u2028", 1, true) ~= nil, "a line separator must survive as an escape")
  assert(pandoc.json.decode(line).title == "a" .. separator .. "b", "line separators must round-trip")
  return doc
end
'''


def _run_lua(tmp_path: Path, assertions: str) -> None:
    rendered = assertions.replace("__VIEWS_PATH__", json.dumps(str(VIEWS_LUA)))
    assertion_filter = tmp_path / "script_json_assertions.lua"
    assertion_filter.write_text(rendered, encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("# Projection security assertions\n", encoding="utf-8")
    subprocess.run(
        ["quarto", "pandoc", "--lua-filter", str(assertion_filter), "--to", "plain", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_views_lua_exposes_a_script_embedding_escape() -> None:
    """The embedding escape exists and maps HTML-significant characters."""
    source = VIEWS_LUA.read_text(encoding="utf-8")
    assert "function M.script_json(" in source
    start = source.index("function M.script_json(")
    body = source[start : source.index("\nend", start)]
    assert "\\u003c" in body
    assert "\\u003e" in body
    assert "\\u0026" in body


def test_graph_lua_escapes_both_inline_json_payloads() -> None:
    """Every JSON script element in the graph goes through the escape."""
    source = GRAPH_LUA.read_text(encoding="utf-8")
    assert "views.script_json(json_payload)" in source
    assert "views.script_json(overlays_contents)" in source
    assert "views.script_json(source)" not in source, "mermaid source must not be JSON-escaped"
    data_scripts = source.count("data-need-graph-data=")
    escaped_data_scripts = source.count("views.script_json(json_payload)")
    assert data_scripts == escaped_data_scripts


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_script_json_escaping_round_trips(tmp_path: Path) -> None:
    """The helper's output stays valid JSON while carrying no raw markup."""
    _run_lua(tmp_path, LUA_SCRIPT_JSON_ASSERTIONS)


def _install_fixture_extension(project: Path) -> None:
    extension = project / "_extensions" / "lsbjordao" / "quarto-needs"
    extension.parent.mkdir(parents=True)
    shutil.copytree(ROOT / "_extensions" / "quarto-needs", extension)


@pytest.mark.skipif(shutil.which("quarto") is None, reason="Quarto is not installed")
def test_authored_markup_cannot_break_out_of_the_rendered_graph(tmp_path: Path) -> None:
    """A real render keeps the hostile title inside the JSON payload."""
    project = tmp_path / "security"
    shutil.copytree(FIXTURE, project)
    _install_fixture_extension(project)
    subprocess.run(
        ["quarto", "render", str(project)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    html = (project / "index.html").read_text(encoding="utf-8")

    assert '<script>alert("breakout")</script>' not in html, "the payload broke out as markup"
    assert "</script><script>" not in html, "the closing tag was embedded raw"

    blocks = re.findall(
        r'<script type="application/json" data-need-graph-data="[^"]*">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert blocks, "the fixture must render the interactive graph data"

    titles: list[str] = []
    for block in blocks:
        assert "</script" not in block
        assert "\\u003c" in block, "each payload must escape HTML-significant characters"
        payload = json.loads(block)
        titles.extend(node["title"] for node in payload["nodes"])
    assert any("</script><script>alert" in title for title in titles), (
        "the title must round-trip through JSON decoding"
    )
