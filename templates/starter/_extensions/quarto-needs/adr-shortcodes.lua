local function extension_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local views = dofile(extension_dir() .. "views.lua")

local function text(value)
  if value == nil then return "" end
  return pandoc.utils.stringify(value)
end

local function split(value)
  local out = {}
  for item in text(value):gmatch("[^,;]+") do
    item = item:match("^%s*(.-)%s*$")
    if item ~= "" then out[#out + 1] = item:lower() end
  end
  return out
end

local function overlaps(value, wanted)
  if #wanted == 0 then return true end
  for _, actual in ipairs(split(value)) do
    for _, expected in ipairs(wanted) do
      if actual == expected then return true end
    end
  end
  return false
end

local function matches(object, kwargs)
  if text(object.type) ~= "architecture-decision" then return false end
  local attrs = type(object.attributes) == "table" and object.attributes or {}
  if not overlaps(object.status, split(views.kwarg(kwargs, "status"))) then return false end
  if not overlaps(attrs.tags, split(views.kwarg(kwargs, "tags"))) then return false end
  if not overlaps(attrs["decision-makers"], split(views.kwarg(kwargs, "decision-makers"))) then return false end
  local date = text(attrs.date)
  local from = views.kwarg(kwargs, "date-from")
  local to = views.kwarg(kwargs, "date-to")
  if from ~= "" and (date == "" or date < from) then return false end
  if to ~= "" and (date == "" or date > to) then return false end
  return true
end

local function select_adrs(graph, kwargs)
  local pool, message = views.select(graph, graph.objects or {}, {query = views.kwarg(kwargs, "query")})
  if message then return nil, message end
  local out = {}
  for _, object in ipairs(pool) do
    if matches(object, kwargs) then out[#out + 1] = object end
  end
  local direction = views.kwarg(kwargs, "date-sort", "desc"):lower()
  table.sort(out, function(a, b)
    local ad = text((a.attributes or {}).date)
    local bd = text((b.attributes or {}).date)
    if ad ~= bd then return direction == "asc" and ad < bd or direction ~= "asc" and ad > bd end
    return text(a.id) < text(b.id)
  end)
  return out
end

local function cell(object, column)
  local attrs = object.attributes or {}
  if column == "id" then return {views.link(object)} end
  if column == "title" then return {pandoc.Str(text(object.title))} end
  if column == "status" then return views.badge("status", object.status) end
  if column == "date" then return views.badge("date", attrs.date) end
  return {pandoc.Str(text(attrs[column]))}
end

local function render_table(args, kwargs)
  views.ensure_assets()
  local graph, message = views.load()
  if not graph then return views.warning(message) end
  local objects, selection_error = select_adrs(graph, kwargs)
  if not objects then return views.warning(selection_error) end
  if #objects == 0 then
    return views.empty(views.tr("No architecture decisions match these filters.", "Nenhuma decisão arquitetural corresponde a estes filtros."))
  end

  local labels = {
    id = views.tr("ID", "ID"), title = views.tr("title", "título"),
    status = views.tr("status", "status"), date = views.tr("date", "data"),
    ["decision-makers"] = views.tr("decision makers", "decisores"), tags = views.tr("tags", "tags")
  }
  local columns, headers = {}, {}
  for column in views.kwarg(kwargs, "columns", "id;title;status;date;decision-makers;tags"):gmatch("[^,;]+") do
    column = column:match("^%s*(.-)%s*$")
    columns[#columns + 1] = column
    headers[#headers + 1] = {pandoc.Str(labels[column] or column:gsub("%-", " "))}
  end
  local rows = {}
  for _, object in ipairs(objects) do
    local row = {}
    for _, column in ipairs(columns) do row[#row + 1] = cell(object, column) end
    rows[#rows + 1] = row
  end
  local id = views.reserve_view_id("adr-table", views.kwarg(kwargs, "id"))
  local caption = views.kwarg(kwargs, "caption", views.tr("Architecture decisions", "Decisões arquiteturais"))
  local table_block = views.table(caption, headers, rows, pandoc.Attr(id, {"need-table", "adr-table"}))
  return pandoc.Div({table_block}, pandoc.Attr("", {"need-table-container", "adr-table-container"}, {["data-need-table"] = "true"}))
end

local function render_count(args, kwargs)
  local graph, message = views.load()
  if not graph then return views.warning(message) end
  local objects, selection_error = select_adrs(graph, kwargs)
  if not objects then return views.warning(selection_error) end
  return pandoc.Span({pandoc.Str(tostring(#objects))}, pandoc.Attr("", {"need-count", "adr-count"}))
end

return { ["adr-table"] = render_table, ["adr-count"] = render_count }
