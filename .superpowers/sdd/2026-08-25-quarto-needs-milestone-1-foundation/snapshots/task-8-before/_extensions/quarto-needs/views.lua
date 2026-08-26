-- Read-only presentation helpers for the graph emitted by quarto-needs.
local M = {}

local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local function text(value)
  if value == nil then return "" end
  return pandoc.utils.stringify(value)
end

function M.slug(value)
  return text(value):lower():gsub("[^%w]+", "-"):gsub("^-", ""):gsub("-$", "")
end

local assets_added = false
function M.ensure_assets()
  if assets_added or not quarto.doc.is_format("html:js") then return end
  assets_added = true
  quarto.doc.add_html_dependency({
    name = "quarto-needs",
    version = "0.1.0",
    stylesheets = {"needs.css"},
    scripts = {"needs.js"},
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

function M.load()
  local path = project_dir() .. "/.quarto-needs/needs.json"
  local file = io.open(path, "r")
  if not file then return nil, "Quarto Needs graph not found: " .. path end
  local contents = file:read("*a")
  file:close()
  local ok, graph = pcall(pandoc.json.decode, contents)
  if not ok or type(graph) ~= "table" or type(graph.objects) ~= "table" then
    return nil, "Quarto Needs graph is invalid: " .. path
  end
  return graph
end

local function option_values(kwargs, ...)
  local values = {}
  for i = 1, select("#", ...) do
    local key = select(i, ...)
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

-- Reserve a safe HTML identifier. Pass a requested ID for explicit views;
-- omit it to allocate the next ID for the prefix.
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

function M.next_id(prefix)
  return M.reserve_view_id(prefix)
end

function M.badge(kind, value)
  local raw = text(value)
  if raw == "" then return {} end
  return {pandoc.Span({pandoc.Str(raw)}, pandoc.Attr("", {"need-badge", "need-" .. kind, "need-" .. kind .. "-" .. M.slug(raw)}))}
end

function M.link(object, label)
  return pandoc.Link({pandoc.Str(label or text(object.id))}, text(object.href) ~= "" and object.href or "#" .. text(object.id), "")
end

function M.objects_by_id(objects)
  local result = {}
  for _, object in ipairs(objects or {}) do result[text(object.id)] = object end
  return result
end

function M.related(graph, source, relation_type)
  local result = {}
  for _, relation in ipairs(graph.relations or {}) do
    if text(relation.source) == source and (relation_type == nil or text(relation.type) == relation_type) then
      table.insert(result, relation.target)
    end
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
  return "need_" .. text(id):gsub(".", function(char)
    return string.format("%02X", string.byte(char))
  end)
end

function M.escape_mermaid(value)
  return text(value):gsub("[\"\\\n\r]", function(char)
    if char == "\"" then return "'" end
    if char == "\\" then return "/" end
    return " "
  end)
end

return M
