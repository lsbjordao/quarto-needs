-- The `need-c4` shortcode: Mermaid C4 diagrams and the Code-level table.
--
-- All C4-specific logic (which node is what shape, how a diagram's text is
-- built) lives in Python (c4_render.py and its sibling renderer modules
-- c4_structurizr.py/c4_plantuml.py/c4_d2.py) and is pre-rendered to
-- .quarto-needs/graphs/c4-<level>-<id>[.<backend>].json by
-- write_c4_projections. This module only reads that file and hands its text
-- to the existing Mermaid rendering helper, or invokes the selected local
-- renderer for the other backends before falling back to source text.
-- It never interprets a graph projection itself, unlike graph.lua's own
-- need-graph shortcode.
local M = {}

local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local views = dofile(script_dir() .. "views.lua")

local VALID_LEVELS = {context = true, container = true, component = true, code = true}
local MERMAID_BACKEND = "mermaid"

local function project_dir()
  local ok, directory = pcall(function() return quarto.project.directory end)
  if ok and type(directory) == "string" and directory ~= "" then return directory end
  local input = PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]
  return input and input:match("(.*/)") or "."
end

local function load_c4_view(root, view_id)
  local full = pandoc.path.join({root, ".quarto-needs", "graphs", view_id .. ".json"})
  local file = io.open(full, "rb")
  if not file then return nil, "C4 view not found: " .. full end
  local contents = file:read("*a"); file:close()
  local ok, decoded = pcall(pandoc.json.decode, contents)
  if not ok or type(decoded) ~= "table" or type(decoded.source) ~= "string" then
    return nil, "C4 view is not valid JSON: " .. full
  end
  return decoded
end

function M.render_shortcode(args, kwargs)
  views.ensure_assets()
  local root_id = views.kwarg(kwargs, "root", "")
  local level = views.kwarg(kwargs, "level", "")
  local backend = views.kwarg(kwargs, "backend", MERMAID_BACKEND)
  if root_id == "" or level == "" then
    return views.warning(views.tr(
      "need-c4 requires both root and level.",
      "need-c4 requer tanto root quanto level."
    ))
  end
  if not VALID_LEVELS[level] then
    return views.warning(views.tr(
      "need-c4 level must be one of context, container, component, code.",
      "need-c4 level deve ser context, container, component ou code."
    ))
  end

  local root = project_dir()
  local view_id = "c4-" .. level .. "-" .. root_id
  if backend ~= MERMAID_BACKEND then
    view_id = view_id .. "." .. backend
  end
  local decoded, message = load_c4_view(root, view_id)
  if not decoded then
    quarto.log.warning(message)
    return views.warning(message)
  end

  if decoded.kind == "table" then
    return pandoc.read(decoded.source, "markdown").blocks
  end

  if decoded.kind == "source" then
    local language = decoded.language or backend
    local description = views.tr("Architecture diagram", "Diagrama de arquitetura")
    if views.is_html_format() then
      local svg = views.diagram_inline_svg(backend, decoded.source, description, "need-c4-figure")
      if svg then
        return pandoc.Div({pandoc.RawBlock("html", svg)}, pandoc.Attr("", {"need-c4-scroll"}))
      end
    else
      local image_name = views.render_diagram_asset(backend, decoded.source, "quarto-needs-c4-" .. backend)
      if image_name then
        return pandoc.Div({pandoc.Para({
          pandoc.Image({pandoc.Str(description)}, image_name, "", pandoc.Attr("", {"need-c4-figure"}, {role="img"}))
        })}, pandoc.Attr("", {"need-c4-scroll"}))
      end
    end
    -- No local {backend} tool installed (or it failed): fall back to the
    -- pre-rendered source text, still useful on its own as a code sample.
    return pandoc.Div({pandoc.CodeBlock(decoded.source, pandoc.Attr("", {language}))})
  end

  local description = views.tr("Architecture diagram", "Diagrama de arquitetura")
  if views.is_html_format() then
    local svg = views.mermaid_inline_svg(decoded.source, description, "need-c4-figure")
    if svg then
      return pandoc.Div({pandoc.RawBlock("html", svg)}, pandoc.Attr("", {"need-c4-scroll"}))
    end
  end
  local image_name, render_error = views.render_mermaid_asset(decoded.source, "quarto-needs-c4")
  if image_name then
    return pandoc.Div({pandoc.Para({
      pandoc.Image({pandoc.Str(description)}, image_name, "", pandoc.Attr("", {"need-c4-figure"}, {role="img"}))
    })}, pandoc.Attr("", {"need-c4-scroll"}))
  end
  quarto.log.warning(render_error or "c4 render failed")
  return views.warning(views.tr(
    "need-c4 could not render the diagram.",
    "need-c4 não conseguiu renderizar o diagrama."
  ))
end

return M
