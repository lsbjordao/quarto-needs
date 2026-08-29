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
    version = "0.1.3",
    stylesheets = {"needs.css", "graph.css"},
    scripts = {
      "needs.js",
      "vendor/cytoscape/cytoscape.min.js",
      "graph-context.js",
      "graph.js",
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
      elseif field:sub(1, 11) == "attributes." then
        local key = field:sub(12)
        av, bv = text(attributes(a)[key]):lower(), text(attributes(b)[key]):lower()
      else
        av, bv = text(a[field]):lower(), text(b[field]):lower()
      end
      if av ~= bv then return av < bv end
    end
    return text(a.id):lower() < text(b.id):lower()
  end)
  return objects
end

function M.limit(objects, kwargs, default_limit)
  local raw = M.kwarg(kwargs, "limit")
  local limit = tonumber(raw) or default_limit or #objects
  limit = math.max(0, math.floor(limit))
  if #objects <= limit then return objects end
  local result = {}
  for index = 1, limit do result[index] = objects[index] end
  return result
end

function M.output_format(kwargs)
  return M.kwarg(kwargs, "format", detect_format())
end

function M.table(headers, rows, classes)
  local aligns, widths = {}, {}
  for _ = 1, #headers do
    table.insert(aligns, "AlignDefault")
    table.insert(widths, 0)
  end
  local function cell_blocks(value)
    if type(value) == "table" and value.t then return {pandoc.Plain({value})} end
    if type(value) == "table" and value[1] and value[1].t then return {pandoc.Plain(value)} end
    return {pandoc.Plain({pandoc.Str(text(value))})}
  end
  local header_cells, body_rows = {}, {}
  for _, value in ipairs(headers) do table.insert(header_cells, cell_blocks(value)) end
  for _, row in ipairs(rows) do
    local cells = {}
    for _, value in ipairs(row) do table.insert(cells, cell_blocks(value)) end
    table.insert(body_rows, cells)
  end
  local simple = pandoc.SimpleTable({pandoc.Str("")}, aligns, widths, header_cells, body_rows)
  local table = pandoc.utils.from_simple_table(simple)
  table.classes = classes or {"need-table"}
  return table
end

function M.badge(kind, value)
  local label = text(value)
  if label == "" then return nil end
  local classes = {"need-badge", "need-" .. M.slug(kind), "need-" .. M.slug(kind) .. "-" .. M.slug(value)}
  return pandoc.Span({pandoc.Str(label)}, pandoc.Attr("", classes, {}))
end

function M.link(id, label, href)
  local target = href or ("#" .. text(id))
  return pandoc.Link({pandoc.Code(text(label or id))}, target, "", pandoc.Attr("", {"need-ref"}, {}))
end

function M.escape_mermaid(value)
  return text(value)
    :gsub("\\", "/")
    :gsub('"', "'")
    :gsub("[\r\n]+", " ")
    :gsub("%s+", " ")
end

return M