-- Read-only presentation helpers for the graph emitted by quarto-needs.
local M = {}

local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local data = dofile(script_dir() .. "data.lua")
local i18n = dofile(script_dir() .. "i18n.lua")

local function text(value)
  if value == nil then return "" end
  return pandoc.utils.stringify(value)
end

function M.language() return i18n.language() end
function M.tr(en, pt) return i18n.t(en, pt) end
function M.relation_label(relation_type, inverse, fallback)
  return i18n.relation_label(relation_type, inverse, fallback)
end

function M.slug(value)
  return text(value):lower():gsub("[^%w]+", "-"):gsub("^-", ""):gsub("-$", "")
end

local ASSETS_FLAG = "__quarto_needs_assets_added_v1"
function M.ensure_assets()
  if rawget(_G, ASSETS_FLAG) or not quarto.doc.is_format("html:js") then return end
  rawset(_G, ASSETS_FLAG, true)
  quarto.doc.add_html_dependency({
    name = "quarto-needs",
    version = "0.1.8",
    stylesheets = {"needs.css", "vendor/cytoscape-navigator/cytoscape.js-navigator.css", "graph.css"},
    scripts = {
      "needs.js",
      "vendor/cytoscape/cytoscape.min.js",
      "vendor/cytoscape-navigator/cytoscape-navigator.js",
      "graph-context.js",
      "graph.js",
      "graph-explore.js",
      "graph-modes.js",
      "graph-state.js",
    },
  })
end

function M.warning(message)
  return pandoc.Div({pandoc.Para({pandoc.Str(message)})}, pandoc.Attr("", {"need-view-warning"}, {role = "alert"}))
end

function M.empty(message)
  return pandoc.Div({pandoc.Para({pandoc.Str(message)})}, pandoc.Attr("", {"need-view-empty"}, {role = "status"}))
end

function M.kwarg(kwargs, key, default)
  local value = kwargs and kwargs[key]
  local result = text(value)
  if result == "" then return default or "" end
  return result
end

local function project_dir()
  local ok, directory = pcall(function() return quarto.project.directory end)
  if ok and type(directory) == "string" and directory ~= "" then return directory end
  local input = PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]
  return input and input:match("(.*/)") or "."
end

local localized_cache = {}
local function localized_titles()
  local locale = M.language()
  if locale == "en" then return {} end
  if localized_cache[locale] ~= nil then return localized_cache[locale] end
  local path = project_dir() .. "/.quarto-needs/i18n/" .. locale .. ".json"
  local file = io.open(path, "rb")
  if not file then localized_cache[locale] = {}; return localized_cache[locale] end
  local contents = file:read("*a")
  file:close()
  local ok, decoded = pcall(pandoc.json.decode, contents)
  local titles = ok and type(decoded) == "table" and decoded.titles or nil
  localized_cache[locale] = type(titles) == "table" and titles or {}
  return localized_cache[locale]
end

function M.localized_title(id, fallback)
  local title = localized_titles()[text(id)]
  if title == nil or text(title) == "" then return text(fallback) end
  return text(title)
end

function M.localize_graph(graph)
  if M.language() == "en" or type(graph) ~= "table" then return graph end
  for _, object in ipairs(graph.objects or {}) do
    object.title = M.localized_title(object.id, object.title)
  end
  return graph
end

function M.localize_projection(projection)
  if M.language() == "en" or type(projection) ~= "table" then return projection end
  for _, node in ipairs(projection.nodes or {}) do
    node.title = M.localized_title(node.id, node.title)
  end
  return projection
end

-- `path` is an explicit override used by tests; production callers pass nothing.
function M.load(path)
  local graph, message = data.load(path or (project_dir() .. "/.quarto-needs/needs.json"))
  if graph then M.localize_graph(graph) end
  return graph, message
end

function M.get(graph, id)
  return data.get(graph, id)
end

function M.outgoing(graph, id, relation_type)
  return data.outgoing(graph, id, relation_type)
end

function M.incoming(graph, id, relation_type)
  return data.incoming(graph, id, relation_type)
end

local function detect_format()
  local ok, detected = pcall(function()
    if quarto.doc.is_format("html:js") then return "html" end
    if quarto.doc.is_format("docx") then return "docx" end
    if quarto.doc.is_format("pdf") then return "pdf" end
    return nil
  end)
  if ok and detected then return detected end
  local writer = type(FORMAT) == "string" and FORMAT:lower() or ""
  if writer == "" then return "html" end
  return writer
end

function M.is_html_format()
  return detect_format() == "html"
end

local function normalize_mermaid_svg(html)
  local start = html:find("<svg", 1, true)
  if not start then return nil end
  local finish, cursor = start, start
  repeat
    local next_close = html:find("</svg>", cursor + 1, true)
    if next_close then finish, cursor = next_close, next_close end
  until not next_close
  local document = html:sub(start, finish + 6)
  document = document:gsub("foreignobject", "foreignObject")
  document = document:gsub("<br>", "<br/>")
  document = document:gsub("data%-xmlns", "xmlns")
  document = document:gsub('%sxlink="http://www%.w3%.org/1999/xlink"', ' xmlns:xlink="http://www.w3.org/1999/xlink"')
  local open_end = document:find(">", 1, true)
  if not open_end then return nil end
  local open_tag = document:sub(1, open_end - 1)
  local body = document:sub(open_end + 1)
  open_tag = open_tag:gsub("%s*viewbox=", " viewBox=")
  local width, height = open_tag:match('viewBox%s*=%s*"[%d%.%-]+%s+[%d%.%-]+%s+([%d%.%-]+)%s+([%d%.%-]+)"')
  if not width then
    width, height = open_tag:match("viewBox%s*=%s*'[%d%.%-]+%s+[%d%.%-]+%s+([%d%.%-]+)%s+([%d%.%-]+)'")
  end
  if not width then return nil end
  open_tag = open_tag:gsub('%s*width%s*=%s*"[^"]*"', "")
  open_tag = open_tag:gsub("%s*width%s*=%s*'[^']*'", "")
  open_tag = open_tag:gsub('%s*height%s*=%s*"[^"]*"', "")
  open_tag = open_tag:gsub("%s*height%s*=%s*'[^']*'", "")
  open_tag = open_tag:gsub('%s*style%s*=%s*"[^"]*"', "")
  return open_tag .. string.format(' width="%s" height="%s">', width, height) .. body
end

local function with_temp_mermaid(source, temp_name, mermaid_format, collect)
  local labeled = "%%{init: {\"htmlLabels\": false}}%%\n" .. source
  local ok, result = pcall(pandoc.system.with_temporary_directory, temp_name, function(directory)
    local input = pandoc.path.join({directory, "diagram.qmd"})
    local output = io.open(input, "wb")
    if not output then return {error = "temporary source"} end
    output:write("---\nmermaid-format: ", mermaid_format, "\nformat: html\n---\n\n```{mermaid}\n", labeled, "\n```\n")
    output:close()
    local rendered = pandoc.system.with_working_directory(directory, function()
      return pcall(pandoc.pipe, quarto.config.cli_path(), {"render", "diagram.qmd", "--to", "html", "--output", "diagram.html"}, "")
    end)
    if not rendered then return {error = "render failed"} end
    return collect(directory)
  end)
  if not ok then return nil, pandoc.utils.stringify(result) end
  if type(result) ~= "table" or result.error then
    return nil, (type(result) == "table" and result.error) or "render failed"
  end
  return result.data
end

local function collect_temp_html(directory)
  local f = io.open(pandoc.path.join({directory, "diagram.html"}), "rb")
  if not f then return {error = "no html output"} end
  local html = f:read("*a"); f:close()
  return {data = html}
end

local function collect_temp_png(directory)
  local f = io.open(pandoc.path.join({directory, "diagram_files", "figure-html", "mermaid-figure-1.png"}), "rb")
  if not f then return {error = "no png"} end
  local contents = f:read("*a"); f:close()
  return {data = contents}
end

local function escape_html_attr(value)
  return (value:gsub("[&<\"]", {["&"] = "&amp;", ["<"] = "&lt;", ['"'] = "&quot;"}))
end

local function namespace_svg_ids(svg, prefix)
  local ids = {}
  for id in svg:gmatch('%sid="([^"]+)"') do ids[#ids + 1] = id end
  table.sort(ids, function(a, b) return #a > #b end)
  for _, id in ipairs(ids) do
    local escaped = id:gsub("%W", "%%%0")
    svg = svg:gsub('id="' .. escaped .. '"', 'id="' .. prefix .. id .. '"')
    svg = svg:gsub("#" .. escaped, "#" .. prefix .. id)
  end
  return svg
end

local inline_svg_cache = {}

function M.mermaid_inline_svg(source, description, class_name)
  local digest = pandoc.utils.sha1(source)
  local svg = inline_svg_cache[digest]
  if not svg then
    local html = with_temp_mermaid(source, "quarto-needs-svg", "svg", collect_temp_html)
    svg = html and normalize_mermaid_svg(html)
    if not svg then return nil end
    inline_svg_cache[digest] = svg
  end
  svg = namespace_svg_ids(svg, M.reserve_view_id("need-svg") .. "-")
  local open_end = svg:find(">", 1, true)
  if not open_end then return nil end
  local open_tag = svg:sub(1, open_end - 1)
  local body = svg:sub(open_end + 1)
  if class_name and class_name ~= "" then
    if open_tag:find('class="') then
      open_tag = open_tag:gsub('class="', 'class="' .. class_name .. " ", 1)
    else
      open_tag = open_tag .. ' class="' .. class_name .. '"'
    end
  end
  open_tag = open_tag:gsub('%s*role="[^"]*"', "")
  local extras = ' role="img"'
  if description and description ~= "" then
    extras = extras .. ' aria-label="' .. escape_html_attr(description) .. '"'
  end
  return open_tag .. extras .. ' style="max-width:100%;height:auto">' .. body
end

local mermaid_assets = {}

function M.render_mermaid_asset(source, prefix)
  local digest = pandoc.utils.sha1(source)
  local cached = mermaid_assets[digest]
  if cached then
    pandoc.mediabag.insert(cached.name, "image/png", cached.data)
    return cached.name
  end
  local data = with_temp_mermaid(source, prefix, "png", collect_temp_png)
  if not data then return nil, "mermaid render failed" end
  local name = prefix .. "-" .. digest .. ".png"
  pandoc.mediabag.insert(name, "image/png", data)
  mermaid_assets[digest] = {name = name, data = data}
  return name
end

local function current_input()
  local input
  local ok, declared = pcall(function() return quarto.doc.input_file end)
  if ok and type(declared) == "string" and declared ~= "" then
    input = declared
  else
    input = PANDOC_STATE and PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]
  end
  if type(input) ~= "string" or input == "" then return "" end
  local normalized = pandoc.path.normalize(input)
  local ok_root, directory = pcall(function() return quarto.project.directory end)
  if ok_root and type(directory) == "string" and directory ~= "" then
    local root = pandoc.path.normalize(directory)
    if root:sub(-1) ~= "/" then root = root .. "/" end
    if normalized:sub(1, #root) == root then normalized = normalized:sub(#root + 1) end
  end
  if normalized:sub(1, 1) == "/" then return "" end
  return normalized
end

local function option_values(kwargs, ...)
  local values = {}
  for n = 1, select("#", ...) do
    local key = select(n, ...)
    local raw = M.kwarg(kwargs, key)
    for value in raw:gmatch("[^,;]+") do
      value = value:match("^%s*(.-)%s*$")
      if value ~= "" then values[value:lower()] = true end
    end
  end
  return values
end

local function attributes(object)
  return type(object.attributes) == "table" and object.attributes or {}
end

local function matches(value, options)
  if next(options) == nil then return true end
  return options[text(value):lower()] == true
end

local function matches_tags(value, options)
  if next(options) == nil then return true end
  if type(value) == "table" then
    for _, tag in ipairs(value) do if matches(tag, options) then return true end end
    return false
  end
  for tag in text(value):gmatch("[^,;]+") do
    if matches(tag:match("^%s*(.-)%s*$"), options) then return true end
  end
  return false
end

function M.filter(objects, kwargs)
  local ids = option_values(kwargs, "ids")
  local types = option_values(kwargs, "types", "type")
  local statuses = option_values(kwargs, "status")
  local priorities = option_values(kwargs, "priority")
  local tags = option_values(kwargs, "tags")
  local result = {}
  for _, object in ipairs(objects or {}) do
    local attrs = attributes(object)
    if matches(object.id, ids) and matches(object.type, types) and matches(object.status, statuses)
      and matches(attrs.priority, priorities) and matches_tags(attrs.tags, tags) then
      table.insert(result, object)
    end
  end
  return result
end

function M.named_query_ids(graph, name)
  local extensions = type(graph.extensions) == "table" and graph.extensions or {}
  local quarto_needs = type(extensions.quartoNeeds) == "table" and extensions.quartoNeeds or {}
  local queries = quarto_needs.queries
  if type(queries) ~= "table" then return nil end
  local ids = queries[name]
  if type(ids) ~= "table" then return nil end
  local wanted = {}
  for _, id in ipairs(ids) do wanted[text(id)] = true end
  return wanted
end

function M.select(graph, objects, kwargs)
  local query_name = M.kwarg(kwargs, "query")
  local pool = objects
  if query_name ~= "" then
    local wanted = M.named_query_ids(graph, query_name)
    if wanted == nil then return {}, "Unknown query: " .. query_name end
    pool = {}
    for _, object in ipairs(objects or {}) do
      if wanted[text(object.id)] then pool[#pool + 1] = object end
    end
  end
  return M.filter(pool, kwargs), nil
end

local priority_order = {critical = 1, high = 2, medium = 3, low = 4}
function M.sort(objects, kwargs)
  local fields = {}
  for value in M.kwarg(kwargs, "sort"):gmatch("[^,;]+") do
    table.insert(fields, value:match("^%s*(.-)%s*$"):lower())
  end
  table.sort(objects, function(a, b)
    for _, field in ipairs(fields) do
      local av, bv
      if field == "priority" then
        av = priority_order[text(attributes(a).priority):lower()] or 5
        bv = priority_order[text(attributes(b).priority):lower()] or 5
      else
        av = text(a[field] or attributes(a)[field]):lower()
        bv = text(b[field] or attributes(b)[field]):lower()
      end
      if av ~= bv then return av < bv end
    end
    return text(a.id) < text(b.id)
  end)
  return objects
end

local generated_ids = {}
local reserved_view_ids = {}
local function safe_view_id(value, fallback)
  local normalized = M.slug(value)
  if normalized == "" then normalized = M.slug(fallback) end
  if normalized == "" then normalized = "need-view" end
  return normalized
end

function M.reserve_view_id(prefix, requested)
  local safe_prefix = safe_view_id(prefix, "need-view")
  local base
  if text(requested) == "" then
    generated_ids[safe_prefix] = (generated_ids[safe_prefix] or 0) + 1
    base = safe_prefix .. "-" .. tostring(generated_ids[safe_prefix])
  else
    base = safe_view_id(requested, safe_prefix)
  end
  local candidate = base
  local suffix = 2
  while reserved_view_ids[candidate] do
    candidate = base .. "-" .. tostring(suffix)
    suffix = suffix + 1
  end
  reserved_view_ids[candidate] = true
  return candidate
end

function M.next_id(prefix) return M.reserve_view_id(prefix) end

function M.badge(kind, value)
  local raw = text(value)
  if raw == "" then return {} end
  return {pandoc.Span({pandoc.Str(raw)}, pandoc.Attr("", {"need-badge", "need-" .. kind, "need-" .. kind .. "-" .. M.slug(raw)}))}
end

function M.link(object, label, options)
  local resolved = {
    format = options and options.format or detect_format(),
    current_input = options and options.current_input or current_input(),
  }
  return pandoc.Link({pandoc.Str(label or text(object.id))}, data.link_target(object, resolved), "")
end

function M.objects_by_id(objects)
  local result = {}
  for _, object in ipairs(objects or {}) do result[text(object.id)] = object end
  return result
end

function M.related(graph, source, relation_type)
  local result = {}
  for _, relation in ipairs(data.outgoing(graph, source, relation_type)) do
    table.insert(result, relation.target)
  end
  return result
end

function M.table(caption, headers, rows, attr)
  local function blocks(cells)
    local result = {}
    for _, cell in ipairs(cells) do result[#result + 1] = pandoc.Plain(cell) end
    return result
  end
  local normalized_rows = {}
  for _, row in ipairs(rows) do normalized_rows[#normalized_rows + 1] = blocks(row) end
  local aligns, widths = {}, {}
  for _ = 1, #headers do
    aligns[#aligns + 1] = "AlignDefault"
    widths[#widths + 1] = 0
  end
  local simple = pandoc.SimpleTable({pandoc.Str(caption or "")}, aligns, widths, blocks(headers), normalized_rows)
  local table_block = pandoc.utils.from_simple_table(simple)
  table_block.attr = attr or pandoc.Attr()
  return table_block
end

function M.node_id(id)
  return "need_" .. text(id):gsub(".", function(char) return string.format("%02X", string.byte(char)) end)
end

function M.escape_mermaid(value)
  return text(value):gsub("[\"\\\n\r]", function(char)
    if char == "\"" then return "'" end
    if char == "\\" then return "/" end
    return " "
  end)
end

return M
