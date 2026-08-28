-- The `need-graph` shortcode: render a deterministic static diagram, an
-- accessible edge table, a summary, and a progressive container carrying the
-- public projection for the interactive Cytoscape client.
--
-- The projection is written by the CLI at scan time (`.quarto-needs/graphs/`)
-- from the *same* `GraphProjection` the static text is derived from, so the
-- static and interactive views cannot disagree. This filter never evaluates a
-- query string; it only reads what Python already published.
local M = {}

local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local views = dofile(script_dir() .. "views.lua")

-- Stringify a decoded JSON value. `pandoc.json.decode` returns Pandoc values
-- (some userdata), so every string operation below goes through this, exactly
-- as data.lua requires for the needs graph.
local function text(value)
  if value == nil then return "" end
  if type(value) == "string" then return value end
  if type(value) == "table" then return pandoc.utils.stringify(value) end
  return tostring(value)
end

-- Mermaid node ref: hex of the public id, matching graph_render._ref.
local function node_ref(identifier)
  local hex = text(identifier):gsub(".", function(char)
    return string.format("%02X", char:byte())
  end)
  return "need_" .. hex
end

local function escape_mermaid(value)
  return views.escape_mermaid(text(value))
    :gsub("|", "/")
    :gsub("%-%->", "→")
    :gsub("%-%-%-", "—")
end

local function node_label(node)
  local heading = {}
  if text(node.id) ~= "" then table.insert(heading, text(node.id)) end
  if text(node.title) ~= "" then table.insert(heading, text(node.title)) end
  local line = table.concat(heading, " · ")
  local facets = {}
  if text(node.type) ~= "" then table.insert(facets, text(node.type)) end
  if text(node.status) ~= "" then table.insert(facets, text(node.status)) end
  if node.priority and text(node.priority) ~= "" then table.insert(facets, text(node.priority)) end
  if node.change and text(node.change) ~= "unchanged" then
    table.insert(facets, "— " .. text(node.change))
  end
  local facets_line = table.concat(facets, " · ")
  if line == "" then line = text(node.id) end
  return escape_mermaid(line) .. "<br/>" .. escape_mermaid(facets_line)
end

local function edge_label(edge)
  local suffix = ""
  if edge.change and text(edge.change) ~= "unchanged" then
    suffix = suffix .. " (" .. text(edge.change) .. ")"
  end
  if edge.pathMember then
    suffix = suffix .. " (path)"
  end
  return escape_mermaid(text(edge.label) .. suffix)
end

local function mermaid_source(projection)
  local lines = { "flowchart LR" }
  for _, node in ipairs(projection.nodes) do
    table.insert(lines, '  ' .. node_ref(node.id) .. '["' .. node_label(node) .. '"]')
  end
  for _, edge in ipairs(projection.edges) do
    table.insert(
      lines,
      '  ' .. node_ref(edge.source) .. ' -->|"' .. edge_label(edge) .. '"| ' .. node_ref(edge.target)
    )
  end
  return table.concat(lines, "\n")
end

-- Build the accessible edge table rows (source, relation, target, change,
-- impact). The impact explanation names the full path, classification, and
-- distance of each affected origin that travels through an edge.
local function impact_explanations(projection)
  local explanations = {}
  for _, entry in ipairs(projection.impact or {}) do
    local hops = text(entry.distance) == "1" and "hop" or "hops"
    local classification = text(entry.classification) ~= "" and text(entry.classification) or "impact"
    local path_names = {}
    for _, segment in ipairs(entry.path or {}) do
      table.insert(path_names, text(segment))
    end
    local explanation = table.concat(
      { table.concat(path_names, " → "), " (", classification, ", ", tostring(entry.distance), " ", hops, ")" },
      ""
    )
    for i = 1, #entry.path - 1 do
      local left, right = text(entry.path[i]), text(entry.path[i + 1])
      local key = left .. "\0" .. right
      local reverse = right .. "\0" .. left
      explanations[key] = explanations[key] or {}
      table.insert(explanations[key], explanation)
    end
  end
  return explanations
end

local function edge_table_rows(projection)
  local explanations = impact_explanations(projection)
  local rows = {}
  for _, edge in ipairs(projection.edges) do
    local hit = {}
    for _, key in ipairs({ edge.source .. "\0" .. edge.target, edge.target .. "\0" .. edge.source }) do
      for _, text in ipairs(explanations[key] or {}) do
        table.insert(hit, text)
      end
    end
    table.insert(rows, {
      source = text(edge.source),
      relation = text(edge.label),
      target = text(edge.target),
      change = text(edge.change),
      impact = table.concat(hit, "; "),
    })
  end
  return rows
end

local function summary_entries(projection)
  local entries = {
    { "mode", text(projection.view.mode) },
    { "nodes", tostring(#projection.nodes) .. " / " .. tostring(projection.view.limits.nodes) },
    { "edges", tostring(#projection.edges) .. " / " .. tostring(projection.view.limits.edges) },
  }
  if text(projection.view.mode) == "diff" then
    local counts = {}
    for _, node in ipairs(projection.nodes) do
      if node.change and text(node.change) ~= "" then
        local change = text(node.change)
        counts[change] = (counts[change] or 0) + 1
      end
    end
    for _, change in ipairs({ "added", "removed", "modified", "relocated" }) do
      table.insert(entries, { "nodes " .. change, tostring(counts[change] or 0) })
    end
  end
  if text(projection.view.mode) == "impact" then
    local total = #(projection.impact or {})
    local direct = 0
    for _, entry in ipairs(projection.impact or {}) do
      if text(entry.classification) == "direct" then direct = direct + 1 end
    end
    table.insert(entries, { "impacted", tostring(total) })
    table.insert(entries, { "direct", tostring(direct) })
    table.insert(entries, { "transitive", tostring(total - direct) })
  end
  return entries
end

-- Parse a `filter="key=value,key=value"` argument into an ordered set of node
-- attribute conditions. Only nodes that satisfy every clause survive; edges are
-- kept when both endpoints survive. Supported keys are the node facets published
-- in the projection: type, status, priority and change.
local function parse_filter(raw)
  local conditions = {}
  local raw_text = text(raw)
  if raw_text == "" then return conditions end
  for clause in string.gmatch(raw_text, "[^,]+") do
    local key, value = clause:match("^%s*([%w_%-]+)%s*=%s*([%w_%/%-%.]+)%s*$")
    if key and value ~= "" then conditions[key] = value end
  end
  return conditions
end

local function filter_projection(projection, conditions)
  if not next(conditions) then return projection end
  local keep, nodes = {}, {}
  for _, node in ipairs(projection.nodes or {}) do
    local ok = true
    for key, value in pairs(conditions) do
      if text(node[key]) ~= value then ok = false break end
    end
    if ok then
      keep[text(node.id)] = true
      table.insert(nodes, node)
    end
  end
  local edges = {}
  for _, edge in ipairs(projection.edges or {}) do
    if keep[text(edge.source)] and keep[text(edge.target)] then
      table.insert(edges, edge)
    end
  end
  return {
    nodes = nodes,
    edges = edges,
    view = projection.view,
    impact = projection.impact,
  }
end

local function load_projection(root, view_id)
  local path = view_id .. ".json"
  local full = pandoc.path.join({ root, ".quarto-needs", "graphs", path })
  local file = io.open(full, "rb")
  if not file then return nil, nil, "Graph projection not found: " .. full end
  local contents = file:read("*a")
  file:close()
  local ok, decoded = pcall(pandoc.json.decode, contents)
  if not ok or type(decoded) ~= "table" then
    return nil, nil, "Graph projection is not valid JSON: " .. full
  end
  return decoded, contents
end

local function project_dir()
  local ok, directory = pcall(function() return quarto.project.directory end)
  if ok and type(directory) == "string" and directory ~= "" then return directory end
  local input = PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]
  return input and input:match("(.*/)") or "."
end

local function table_block(headers, rows)
  local function cells_block(cells)
    local result = {}
    for _, text in ipairs(cells) do
      table.insert(result, pandoc.Plain({ pandoc.Str(text) }))
    end
    return result
  end
  local aligns, widths = {}, {}
  for _ = 1, #headers do
    aligns[#aligns + 1] = "AlignDefault"
    widths[#widths + 1] = 0
  end
  local simple = pandoc.SimpleTable(
    { pandoc.Str("") }, aligns, widths, cells_block(headers), rows
  )
  local t = pandoc.utils.from_simple_table(simple)
  t.classes = { "need-graph-table" }
  return t
end

local rendered_digests = {}

local function render_mermaid_image(source, id)
  local digest = pandoc.utils.sha1(source)
  local image = "quarto-needs-graph-" .. digest .. ".png"
  if rendered_digests[digest] then
    pandoc.mediabag.insert(image, "image/png", rendered_digests[digest])
    return image
  end
  local ok, entry = pcall(pandoc.system.with_temporary_directory, "quarto-needs-graph", function(directory)
    local input = pandoc.path.join({ directory, "graph.qmd" })
    local output = io.open(input, "wb")
    output:write("---\nmermaid-format: png\nformat: html\n---\n\n```{mermaid}\n")
    output:write(source)
    output:write("\n```\n")
    output:close()
    local o, message = pandoc.system.with_working_directory(directory, function()
      return pcall(
        pandoc.pipe,
        quarto.config.cli_path(),
        { "render", "graph.qmd", "--to", "html", "--output", "graph.html" },
        ""
      )
    end)
    if not o then return { error = "render failed: " .. pandoc.utils.stringify(message) } end
    local img = pandoc.path.join({ directory, "graph_files", "figure-html", "mermaid-figure-1.png" })
    local f = io.open(img, "rb")
    if not f then return { error = "no mermaid png produced" } end
    local data = f:read("*a")
    f:close()
    return { data = data }
  end)
  if not ok or entry.error then return nil end
  pandoc.mediabag.insert(image, "image/png", entry.data)
  rendered_digests[digest] = entry.data
  return image
end

function M.render_shortcode(args, kwargs)
  views.ensure_assets()
  local root = project_dir()
  local view_id = views.kwarg(kwargs, "id", "need-graph-1")
  local projection, raw_json, message = load_projection(root, view_id)
  if not projection then
    quarto.log.warning(message)
    return views.warning(message)
  end
  if not projection.nodes or not projection.edges then
    quarto.log.warning("Graph projection is missing nodes or edges: " .. view_id)
    return views.warning("Graph projection is incomplete for view " .. view_id .. ".")
  end
  local filter_cond = parse_filter(views.kwarg(kwargs, "filter", ""))
  if next(filter_cond) then projection = filter_projection(projection, filter_cond) end

  local blocks = {}

  -- Static diagram (only in HTML where we can render Mermaid to PNG locally).
  local source = mermaid_source(projection)
  local image_name, render_error = render_mermaid_image(source, view_id)
  if image_name then
    local image = pandoc.Image(
      { pandoc.Str("Traceability graph for " .. view_id) },
      image_name,
      "",
      pandoc.Attr("", { "need-graph-figure" }, { role = "img" })
    )
    table.insert(blocks, pandoc.Para({ image }))
  else
    quarto.log.warning("Could not render graph diagram: " .. (render_error or "unknown"))
    table.insert(blocks, views.warning("Could not render this graph diagram."))
  end

  -- Summary with counts.
  local summary_text = {}
  for _, entry in ipairs(summary_entries(projection)) do
    table.insert(summary_text, entry[1] .. ": " .. entry[2])
  end
  table.insert(blocks, pandoc.Para({ pandoc.Str(table.concat(summary_text, " · ")) }))

  -- Accessible edge table.
  local header = { "Source", "Relation", "Target", "Change", "Impact" }
  local rows = {}
  for _, row in ipairs(edge_table_rows(projection)) do
    table.insert(rows, { row.source, row.relation, row.target, row.change, row.impact })
  end
  table.insert(blocks, table_block(header, rows))

  -- Progressive container carrying the projection as embedded JSON. When a
  -- filter was applied the original file no longer matches what is shown, so
  -- re-serialize the filtered projection; otherwise embed the source JSON
  -- verbatim to preserve the published bytes untouched.
  local json_payload = raw_json
  if next(filter_cond) then
    local ok, encoded = pcall(pandoc.json.encode, projection)
    json_payload = ok and encoded ~= nil and encoded or raw_json
  end
  local data_script = pandoc.RawBlock(
    "html",
    '<script type="application/json" data-need-graph-data="' .. view_id .. '">' .. json_payload .. "</script>"
  )
  local canvas = pandoc.RawBlock(
    "html",
    '<div class="need-graph-canvas" data-need-graph-canvas="' .. view_id
      .. '" role="img" aria-label="Interactive traceability graph"><div class="need-graph-loading">Loading interactive graph…</div></div>'
  )
  local controls = pandoc.RawBlock(
    "html",
    '<div class="need-graph-controls" data-need-graph-controls="' .. view_id .. '">'
      .. '<label class="visually-hidden" for="' .. view_id .. '-search">Search graph</label>'
      .. '<input id="' .. view_id .. '-search" class="need-graph-search" type="search" placeholder="Search by ID or title">'
      .. '<label class="visually-hidden" for="' .. view_id .. '-color">Color nodes by</label>'
      .. '<select id="' .. view_id .. '-color" class="need-graph-color" data-need-graph-color>'
      .. '<option value="change" selected>Color: change</option>'
      .. '<option value="type">Color: type</option>'
      .. '<option value="status">Color: status</option>'
      .. '<option value="priority">Color: priority</option>'
      .. '<option value="none">No color</option>'
      .. "</select>"
      .. '<button type="button" class="need-graph-fit">Fit</button>'
      .. '<button type="button" class="need-graph-reset">Reset</button>'
      .. "</div>"
  )
  local status = pandoc.RawBlock(
    "html",
    '<div class="need-graph-status visually-hidden" role="status" data-need-graph-status="' .. view_id .. '"></div>'
  )

  table.insert(blocks, pandoc.RawBlock("html", '<div class="need-graph-container">'))
  table.insert(blocks, controls)
  table.insert(blocks, canvas)
  table.insert(blocks, status)
  table.insert(blocks, data_script)
  table.insert(blocks, pandoc.RawBlock("html", "</div>"))

  return pandoc.Div(blocks, pandoc.Attr(view_id, { "need-graph", "need-graph-progressive" }, { ["data-need-graph"] = view_id }))
end

return M
