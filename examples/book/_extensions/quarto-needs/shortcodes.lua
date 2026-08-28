local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)" ) or ""
end

local views = dofile(script_dir() .. "views.lua")
local flow = dofile(script_dir() .. "flow.lua")
local relations = dofile(script_dir() .. "relations.lua")
local inspector = dofile(script_dir() .. "inspector.lua")
local dashboard = dofile(script_dir() .. "dashboard.lua")
local graph = dofile(script_dir() .. "graph.lua")

local function graph_or_warning()
  views.ensure_assets()
  local graph, message = views.load()
  if not graph then return nil, views.warning(message) end
  return graph
end

local function object_cell(graph, object, column)
  if column == "id" then return {views.link(object)} end
  if column == "title" then return {pandoc.Str(pandoc.utils.stringify(object.title))} end
  if column == "status" or column == "priority" then
    local value = column == "status" and object.status or (object.attributes or {}).priority
    return views.badge(column, value)
  end
  if column == "type" then return {pandoc.Str(pandoc.utils.stringify(object.type))} end
  local targets = views.related(graph, pandoc.utils.stringify(object.id), column)
  if #targets > 0 then
    local objects = views.objects_by_id(graph.objects)
    local inlines = {}
    for i, target in ipairs(targets) do
      if i > 1 then table.insert(inlines, pandoc.Str(", ")) end
      local related = objects[pandoc.utils.stringify(target)]
      if related then table.insert(inlines, views.link(related)) else table.insert(inlines, pandoc.Str(pandoc.utils.stringify(target))) end
    end
    return inlines
  end
  return {pandoc.Str(pandoc.utils.stringify((object.attributes or {})[column] or ""))}
end

local function select_objects(graph, kwargs)
  local objects, message = views.select(graph, graph.objects, kwargs)
  if message then
    quarto.log.warning(message)
    return nil, views.warning(message)
  end
  return views.sort(objects, kwargs), nil
end

local function render_need_table(args, kwargs)
  local graph, warning = graph_or_warning()
  if not graph then return warning end
  local objects, warning_message = select_objects(graph, kwargs)
  if warning_message then return warning_message end
  if #objects == 0 then return views.empty("No needs match this query.") end
  local columns, headers = {}, {}
  for column in views.kwarg(kwargs, "columns", "id;title;type;status;priority"):gmatch("[^,;]+") do
    column = column:match("^%s*(.-)%s*$")
    table.insert(columns, column)
    table.insert(headers, {pandoc.Str(column:gsub("%-", " "))})
  end
  local rows = {}
  for _, object in ipairs(objects) do
    local row = {}
    for _, column in ipairs(columns) do table.insert(row, object_cell(graph, object, column)) end
    table.insert(rows, row)
  end
  local table_id = views.reserve_view_id("need-table", views.kwarg(kwargs, "id"))
  local table_block = views.table(views.kwarg(kwargs, "caption"), headers, rows, pandoc.Attr(table_id, {"need-table"}))
  return pandoc.Div({table_block}, pandoc.Attr("", {"need-table-container"}, { ["data-need-table"] = "true" }))
end

local function render_need_list(args, kwargs)
  local graph, warning = graph_or_warning()
  if not graph then return warning end
  local objects, warning_message = select_objects(graph, kwargs)
  if warning_message then return warning_message end
  if #objects == 0 then return views.empty("No needs match this query.") end
  local show = {}
  for field in views.kwarg(kwargs, "show"):gmatch("[^,;]+") do show[#show + 1] = field:match("^%s*(.-)%s*$") end
  local entries = {}
  for _, object in ipairs(objects) do
    local inlines = {views.link(object), pandoc.Str(" — "), pandoc.Str(pandoc.utils.stringify(object.title))}
    for _, field in ipairs(show) do
      table.insert(inlines, pandoc.Space())
      local value = field == "status" and object.status or (object.attributes or {})[field]
      for _, badge in ipairs(views.badge(field, value)) do table.insert(inlines, badge) end
    end
    table.insert(entries, {pandoc.Plain(inlines)})
  end
  return pandoc.BulletList(entries)
end

local function render_need_count(args, kwargs)
  local graph, warning = graph_or_warning()
  if not graph then return warning end
  local objects, warning_message = select_objects(graph, kwargs)
  if warning_message then return warning_message end
  local count = #objects
  return pandoc.Span({pandoc.Str(tostring(count))}, pandoc.Attr("", {"need-count"}, {["data-need-count"] = tostring(count)}))
end

local function render_need_matrix(args, kwargs)
  local graph, warning = graph_or_warning()
  if not graph then return warning end
  -- A named query narrows the pool both axes are drawn from; the row and
  -- column type filters then apply inside that materialized set.
  local pool, query_message = views.select(graph, graph.objects, {query = views.kwarg(kwargs, "query")})
  if query_message then
    quarto.log.warning(query_message)
    return views.warning(query_message)
  end
  local row_args = {types = views.kwarg(kwargs, "rows")}
  local column_args = {types = views.kwarg(kwargs, "columns")}
  local rows = views.sort(views.filter(pool, row_args), {})
  local columns = views.sort(views.filter(pool, column_args), {})
  if #rows == 0 or #columns == 0 then return views.empty("No needs match this matrix query.") end
  local relation_type = views.kwarg(kwargs, "relation", "verified-by")
  local index = {}
  for _, relation in ipairs(graph.relations or {}) do
    if pandoc.utils.stringify(relation.type) == relation_type then index[pandoc.utils.stringify(relation.source) .. "\0" .. pandoc.utils.stringify(relation.target)] = true end
  end
  local headers = {{pandoc.Str("Need")}}
  for _, object in ipairs(columns) do table.insert(headers, {views.link(object)}) end
  local matrix_rows = {}
  for _, row_object in ipairs(rows) do
    local cells = {{views.link(row_object)}}
    for _, column_object in ipairs(columns) do
      local key = pandoc.utils.stringify(row_object.id) .. "\0" .. pandoc.utils.stringify(column_object.id)
      if index[key] then table.insert(cells, {views.link(column_object, "✓")}) else table.insert(cells, {pandoc.Str("—")}) end
    end
    table.insert(matrix_rows, cells)
  end
  local matrix_id = views.reserve_view_id("need-matrix", views.kwarg(kwargs, "id"))
  return views.table("Traceability: " .. relation_type, headers, matrix_rows, pandoc.Attr(matrix_id, {"need-matrix"}))
end

local function render_need_backlinks(args, kwargs)
  local id = pandoc.utils.stringify(args[1] or "")
  if id == "" then return views.warning("Missing need ID for need-backlinks.") end
  local graph, warning = graph_or_warning()
  if not graph then return warning end
  if not views.get(graph, id) then
    local message = "Unknown need ID: " .. id
    quarto.log.warning(message)
    return views.warning(message)
  end
  return relations.render_backlinks(graph, id)
end

local function render_need_inspector(args, kwargs)
  local id = pandoc.utils.stringify(args[1] or "")
  if id == "" then return views.warning("Missing need ID for need-inspector.") end
  local graph, warning = graph_or_warning()
  if not graph then return warning end
  local block = inspector.render(graph, id, kwargs)
  if not block then
    local message = "Unknown need ID: " .. id
    quarto.log.warning(message)
    return views.warning(message)
  end
  return block
end

local rendered_flow_images = {}

local function render_mermaid_png(source)
  local digest = pandoc.utils.sha1(source)
  local image_name = "quarto-needs-flow-" .. digest .. ".png"
  if rendered_flow_images[digest] then
    pandoc.mediabag.insert(image_name, "image/png", rendered_flow_images[digest])
    return image_name
  end

  local ok, result = pcall(pandoc.system.with_temporary_directory, "quarto-needs-flow", function(directory)
    local input = pandoc.path.join({directory, "flow.qmd"})
    local output = io.open(input, "wb")
    if not output then return {error = "could not create the temporary Mermaid source"} end
    output:write("---\nmermaid-format: png\nformat: html\n---\n\n```{mermaid}\n")
    output:write(source)
    output:write("\n```\n")
    output:close()

    local ok, message = pandoc.system.with_working_directory(directory, function()
      return pcall(
        pandoc.pipe,
        quarto.config.cli_path(),
        {"render", "flow.qmd", "--to", "html", "--output", "flow.html"},
        ""
      )
    end)
    if not ok then return {error = pandoc.utils.stringify(message)} end

    local image_path = pandoc.path.join({directory, "flow_files", "figure-html", "mermaid-figure-1.png"})
    local image = io.open(image_path, "rb")
    if not image then return {error = "Quarto did not produce the expected Mermaid PNG"} end
    local contents = image:read("*a")
    image:close()
    return {contents = contents}
  end)

  if not ok then return nil, pandoc.utils.stringify(result) end
  if result.error then return nil, result.error end
  pandoc.mediabag.insert(image_name, "image/png", result.contents)
  rendered_flow_images[digest] = result.contents
  return image_name
end

local function render_need_flow(args, kwargs)
  local graph, warning = graph_or_warning()
  if not graph then return warning end
  local plan, plan_error = flow.build(graph, kwargs, views)
  if not plan then return views.warning(plan_error) end
  if plan.node_count == 0 then return views.empty("No needs match this flow query.") end
  local blocks = {}
  for _, message in ipairs(plan.warnings) do
    table.insert(blocks, pandoc.Div({pandoc.Para({pandoc.Str(message)})}, pandoc.Attr("", {"need-view-warning"}, {role = "status"})))
  end
  local image_name, render_error = render_mermaid_png(plan.source)
  if not image_name then
    quarto.log.warning("Could not render need-flow Mermaid diagram: " .. render_error)
    table.insert(blocks, views.warning("Could not render this need-flow diagram."))
    return pandoc.Div(blocks)
  end
  local description = "Traceability flow with " .. tostring(plan.node_count) .. " needs"
  local image = pandoc.Image(
    {pandoc.Str(description)},
    image_name,
    "",
    pandoc.Attr("", {"need-flow"}, {role = "img"})
  )
  table.insert(blocks, pandoc.Div({pandoc.Para({image})}, pandoc.Attr("", {"need-flow-scroll"})))
  return pandoc.Div(blocks)
end

local function render_need_dashboard(args, kwargs)
  local graph, warning = graph_or_warning()
  if not graph then return warning end
  local blocks, message = dashboard.render(graph, kwargs)
  if not blocks then
    if message then
      quarto.log.warning(message)
      return views.warning(message)
    end
    return views.empty("Dashboard report unavailable.")
  end
  local dashboard_id = views.reserve_view_id("need-dashboard", views.kwarg(kwargs, "id"))
  return pandoc.Div(blocks, pandoc.Attr(dashboard_id, {"need-dashboard"}, {role = "region"}))
end

return {
  need = function(args, kwargs, meta)
    local id = pandoc.utils.stringify(args[1] or "")
    if id == "" then return pandoc.Str("[missing need id]") end
    local graph, message = views.load()
    if not graph then
      quarto.log.warning(message)
      return pandoc.Span({pandoc.Str(id)}, pandoc.Attr("", {"need-ref", "need-ref-missing"}))
    end
    local object = views.get(graph, id)
    if not object then
      quarto.log.warning("Unknown need ID: " .. id)
      return pandoc.Span({pandoc.Str(id)}, pandoc.Attr("", {"need-ref", "need-ref-missing"}))
    end
    local label = id
    if kwargs and kwargs["title"] then
      local show_title = pandoc.utils.stringify(kwargs["title"])
      if show_title == "true" then label = id .. " — " .. pandoc.utils.stringify(object.title) end
    end
    return views.link(object, label)
  end,
  ["need-table"] = render_need_table,
  ["need-list"] = render_need_list,
  ["need-count"] = render_need_count,
  ["need-matrix"] = render_need_matrix,
  ["need-backlinks"] = render_need_backlinks,
  ["need-inspector"] = render_need_inspector,
  ["need-flow"] = render_need_flow,
  ["need-dashboard"] = render_need_dashboard,
  ["need-graph"] = graph.render_shortcode,
}
