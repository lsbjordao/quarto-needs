local ASSETS_FLAG = "__quarto_needs_margin_sidebar_assets_v1"

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

local function add_assets()
  if rawget(_G, ASSETS_FLAG) or not quarto.doc.is_format("html:js") then return end
  rawset(_G, ASSETS_FLAG, true)
  quarto.doc.add_html_dependency({
    name = "quarto-needs-margin-sidebar",
    version = "0.1.0",
    stylesheets = {"margin-sidebar.css"},
    scripts = {"margin-sidebar.js"},
  })
end

function Meta(meta)
  local options = meta["quarto-needs"]
  if type(options) == "table" and enabled(options["margin-sidebar-toggle"]) then
    add_assets()
  end
  return nil
end
