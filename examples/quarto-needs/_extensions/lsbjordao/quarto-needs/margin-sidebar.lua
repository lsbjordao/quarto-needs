local STYLES_FLAG = "__quarto_needs_margin_sidebar_styles_v1"
local TOGGLE_FLAG = "__quarto_needs_margin_sidebar_toggle_v1"

local function text(value)
  if value == nil then return "" end
  local ok, rendered = pcall(pandoc.utils.stringify, value)
  if not ok then return "" end
  return rendered:lower()
end

local function enabled(value)
  local rendered = text(value)
  return rendered == "true" or rendered == "yes" or rendered == "1" or rendered == "on"
end

local function add_styles()
  if rawget(_G, STYLES_FLAG) or not quarto.doc.is_format("html:js") then return end
  rawset(_G, STYLES_FLAG, true)
  quarto.doc.add_html_dependency({
    name = "quarto-needs-margin-sidebar",
    version = "0.1.0",
    stylesheets = {"margin-sidebar.css"},
  })
end

local function add_toggle()
  if rawget(_G, TOGGLE_FLAG) or not quarto.doc.is_format("html:js") then return end
  rawset(_G, TOGGLE_FLAG, true)
  quarto.doc.add_html_dependency({
    name = "quarto-needs-margin-sidebar-toggle",
    version = "0.1.0",
    scripts = {"margin-sidebar.js"},
  })
end

function Meta(meta)
  add_styles()
  local options = meta["quarto-needs"]
  if type(options) == "table" and enabled(options["margin-sidebar-toggle"]) then
    add_toggle()
  end
  return nil
end
