-- The `need-graph` shortcode: deterministic static and progressive graph views.
local M = {}

local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local views = dofile(script_dir() .. "views.lua")

local function text(value)
  if value == nil then return "" end
  if type(value) == "string" then return value end
  -- A JSON `null` does not decode to nil here: it arrives as a userdata
  -- sentinel, which is truthy and whose tostring is a pointer. Without this
  -- branch an absent field renders as "userdata: 0x55f0..." in the output.
  if type(value) == "userdata" then return "" end
  if type(value) == "table" then return pandoc.utils.stringify(value) end
  return tostring(value)
end

local COPY_ASSET_FLAG = "__quarto_needs_graph_clipboard_added_v1"
local function ensure_clipboard_asset()
  if rawget(_G, COPY_ASSET_FLAG) or not quarto.doc.is_format("html:js") then return end
  rawset(_G, COPY_ASSET_FLAG, true)
  quarto.doc.add_html_dependency({
    name = "quarto-needs-graph-clipboard",
    version = "0.1.0",
    scripts = {"clipboard.js"},
  })
end

-- Mermaid node identifiers must be plain alphanumeric tokens. Encoding the
-- full id as two hex digits per character doubled a real view's source size
-- and pushed it past mermaid's fixed 50,000-character maxTextSize (which
-- Quarto's render pipeline cannot raise), so mermaid drew its error bubble
-- instead of the diagram. Aliases are memoized and assigned in the
-- projection's deterministic first-appearance order, keeping output
-- byte-stable for a fraction of the bytes.
local function mermaid_refs()
  return {count = 0, map = {}}
end

local function node_ref(refs, identifier)
  local alias = refs.map[identifier]
  if not alias then
    refs.count = refs.count + 1
    alias = "n" .. refs.count
    refs.map[identifier] = alias
  end
  return alias
end

local function escape_mermaid(value)
  return views.escape_mermaid(text(value)):gsub("|", "/"):gsub("%-%->", "→"):gsub("%-%-%-", "—")
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
  if node.change and text(node.change) ~= "unchanged" then table.insert(facets, "— " .. text(node.change)) end
  if line == "" then line = text(node.id) end
  return escape_mermaid(line) .. "<br/>" .. escape_mermaid(table.concat(facets, " · "))
end

local function edge_label(edge)
  local suffix = ""
  if edge.change and text(edge.change) ~= "unchanged" then suffix = suffix .. " (" .. text(edge.change) .. ")" end
  if edge.pathMember then suffix = suffix .. " (path)" end
  return escape_mermaid(text(edge.label) .. suffix)
end

function M.mermaid_source(projection)
  local refs = mermaid_refs()
  local lines = {"flowchart LR"}
  local classes = {}
  for _, node in ipairs(projection.nodes) do
    local class_name = "need_type_" .. views.slug(node.type):gsub("-", "_")
    table.insert(lines, '  ' .. node_ref(refs, node.id) .. '["' .. node_label(node) .. '"]')
    table.insert(lines, '  class ' .. node_ref(refs, node.id) .. ' ' .. class_name)
    classes[class_name] = views.type_palette(node.type)
  end
  for _, edge in ipairs(projection.edges) do
    table.insert(lines, '  ' .. node_ref(refs, edge.source) .. ' -->|"' .. edge_label(edge) .. '"| ' .. node_ref(refs, edge.target))
  end
  local class_names = {}
  for class_name in pairs(classes) do class_names[#class_names + 1] = class_name end
  table.sort(class_names)
  for _, class_name in ipairs(class_names) do
    table.insert(lines, '  classDef ' .. class_name .. ' ' .. classes[class_name])
  end
  return table.concat(lines, "\n")
end

local function impact_explanations(projection)
  local explanations = {}
  for _, entry in ipairs(projection.impact or {}) do
    local hops = text(entry.distance) == "1" and "hop" or "hops"
    local classification = text(entry.classification) ~= "" and text(entry.classification) or "impact"
    local path_names = {}
    for _, segment in ipairs(entry.path or {}) do table.insert(path_names, text(segment)) end
    local explanation = table.concat({table.concat(path_names, " → "), " (", classification, ", ", tostring(entry.distance), " ", hops, ")"}, "")
    for i = 1, #entry.path - 1 do
      local left, right = text(entry.path[i]), text(entry.path[i + 1])
      local key = left .. "\0" .. right
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
    for _, key in ipairs({edge.source .. "\0" .. edge.target, edge.target .. "\0" .. edge.source}) do
      for _, value in ipairs(explanations[key] or {}) do table.insert(hit, value) end
    end
    -- id uses the raw relation key (edge.relation), not the translated
    -- display label (edge.label) below — it must match the same
    -- (source, relation, target) triple graph-modes.js's findEdge() already
    -- keys diff/impact overlay entries by.
    local id = text(edge.source) .. "|" .. text(edge.relation) .. "|" .. text(edge.target)
    table.insert(rows, {id=id, source=text(edge.source), relation=text(edge.label), target=text(edge.target), change=text(edge.change), impact=table.concat(hit, "; ")})
  end
  return rows
end

-- One row per node's own attributes and change state. The static table is
-- the primary operable representation for keyboard/screen-reader readers,
-- independent of whether the canvas's own JS ever loads; until this, that
-- table only ever listed edges, so a node's own type/status/priority/tags
-- were only visible on the canvas — which a non-visual reader, or one whose
-- JS failed, could not reach at all.
local function node_table_rows(projection)
  local rows = {}
  for _, node in ipairs(projection.nodes) do
    local tags = {}
    for _, tag in ipairs(node.tags or {}) do table.insert(tags, text(tag)) end
    table.insert(rows, {
      id = text(node.id), title = text(node.title), type = text(node.type),
      status = text(node.status), priority = text(node.priority),
      tags = tags, change = text(node.change),
    })
  end
  return rows
end

-- Each tag becomes its own badge span (views.badge's list-of-inlines shape,
-- which table_block wraps directly), separated by spaces; needs.css's
-- .need-tag rule keeps the badge outline on a transparent fill.
local function tag_cell(tags)
  local inlines = {}
  for _, tag in ipairs(tags or {}) do
    if #inlines > 0 then table.insert(inlines, pandoc.Space()) end
    for _, badge in ipairs(views.badge("tag", tag)) do table.insert(inlines, badge) end
  end
  return inlines
end

local function summary_entries(projection)
  local entries = {
    {views.tr("mode", "modo"), text(projection.view.mode)},
    {views.tr("nodes", "nós"), tostring(#projection.nodes) .. " / " .. tostring(projection.view.limits.nodes)},
    {views.tr("edges", "arestas"), tostring(#projection.edges) .. " / " .. tostring(projection.view.limits.edges)},
  }
  return entries
end

local function projected_copy(projection, nodes, edges)
  return {
    schemaVersion = projection.schemaVersion,
    relationCatalogVersion = projection.relationCatalogVersion,
    relationSemantics = projection.relationSemantics,
    typeRoles = projection.typeRoles,
    nodes = nodes,
    edges = edges,
    view = projection.view,
    impact = projection.impact,
  }
end

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
    if keep[text(edge.source)] and keep[text(edge.target)] then table.insert(edges, edge) end
  end
  return projected_copy(projection, nodes, edges)
end

local function traversal_direction(projection, relation)
  local semantics = projection.relationSemantics or {}
  local definition = semantics[text(relation)]
  if type(definition) ~= "table" then return "none" end
  local direction = text(definition.traversalDirection)
  if direction == "source_to_target" or direction == "target_to_source" or direction == "both" then
    return direction
  end
  return "none"
end

local function downstream_target(projection, edge, current)
  local source, target = text(edge.source), text(edge.target)
  local direction = traversal_direction(projection, edge.relation)
  if (direction == "source_to_target" or direction == "both") and source == current then return target end
  if (direction == "target_to_source" or direction == "both") and target == current then return source end
  return nil
end

-- Restrict an already-public projection to descendants reachable from one root.
-- Engineering direction is resolved by the Python relation catalog and carried
-- in relationSemantics; this presentation layer never redefines relation meaning.
local function root_projection(projection, root_id, raw_depth)
  if root_id == "" then return projection end

  local by_id = {}
  for _, node in ipairs(projection.nodes or {}) do by_id[text(node.id)] = node end
  if not by_id[root_id] then return nil, "Unknown need-graph root: " .. root_id end

  local requested_depth = tonumber(raw_depth) or 3
  requested_depth = math.max(0, math.floor(requested_depth))
  local depth = math.min(requested_depth, 10)
  local selected = {[root_id] = true}
  local frontier = {[root_id] = true}

  for _ = 1, depth do
    local candidates = {}
    for _, edge in ipairs(projection.edges or {}) do
      for current in pairs(frontier) do
        local next_id = downstream_target(projection, edge, current)
        if next_id and by_id[next_id] and not selected[next_id] then
          candidates[next_id] = true
        end
      end
    end
    if not next(candidates) then break end
    for id in pairs(candidates) do selected[id] = true end
    frontier = candidates
  end

  local nodes, edges = {}, {}
  for _, node in ipairs(projection.nodes or {}) do
    if selected[text(node.id)] then table.insert(nodes, node) end
  end
  for _, edge in ipairs(projection.edges or {}) do
    if selected[text(edge.source)] and selected[text(edge.target)] then table.insert(edges, edge) end
  end
  return projected_copy(projection, nodes, edges)
end

local function project_dir()
  local ok, directory = pcall(function() return quarto.project.directory end)
  if ok and type(directory) == "string" and directory ~= "" then return directory end
  local input = PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]
  return input and input:match("(.*/)") or "."
end

local function load_projection(root, view_id)
  local full = pandoc.path.join({root, ".quarto-needs", "graphs", view_id .. ".json"})
  local file = io.open(full, "rb")
  if not file then return nil, nil, "Graph projection not found: " .. full end
  local contents = file:read("*a"); file:close()
  local ok, decoded = pcall(pandoc.json.decode, contents)
  if not ok or type(decoded) ~= "table" then return nil, nil, "Graph projection is not valid JSON: " .. full end
  return decoded, contents
end

-- `row_ids`, when given, is a list parallel to `rows` naming each row's
-- stable id (a node id, or a "source|relation|target" triple for an edge —
-- the same key graph-modes.js's findEdge() already uses) as a
-- data-need-graph-row-id attribute, so the client can find and update a
-- specific row without fragile text-matching against a cell's contents.
-- `kind` ("node"/"edge") is stamped on the table itself so the client can
-- tell the two same-classed tables apart.
local function table_block(headers, rows, kind, row_ids)
  local function cells_block(cells)
    local result = {}
    -- A cell value that is already a list of Inlines (badge spans from
    -- views.badge for the status/priority columns) is wrapped directly;
    -- anything else stays the plain-text Str it always was.
    for _, value in ipairs(cells) do
      if type(value) == "table" then
        table.insert(result, pandoc.Plain(value))
      else
        table.insert(result, pandoc.Plain({pandoc.Str(value)}))
      end
    end
    return result
  end
  local aligns, widths = {}, {}
  for _ = 1, #headers do aligns[#aligns + 1] = "AlignDefault"; widths[#widths + 1] = 0 end
  local simple = pandoc.SimpleTable({pandoc.Str("")}, aligns, widths, cells_block(headers), rows)
  local t = pandoc.utils.from_simple_table(simple)
  t.classes = {"need-graph-table"}
  if kind then t.attributes = {["data-need-graph-role"] = kind} end
  -- Pandoc's from_simple_table omits bodies[1] entirely when there are zero
  -- data rows (an edge-less or node-less graph, or a narrow filter/named
  -- query) — nothing to attribute a row id to in that case.
  if row_ids and t.bodies[1] then
    local body = t.bodies[1]
    for i, row in ipairs(body.body) do
      if row_ids[i] then
        row.attr = pandoc.Attr("", {}, {["data-need-graph-row-id"] = row_ids[i]})
        body.body[i] = row
      end
    end
    t.bodies[1] = body
  end
  return t
end

function M.render_shortcode(args, kwargs)
  views.ensure_assets()
  ensure_clipboard_asset()
  local root = project_dir()
  local instance_id = views.kwarg(kwargs, "id", "need-graph-1")
  local projection_id = views.kwarg(kwargs, "projection", instance_id)
  local projection, raw_json, message = load_projection(root, projection_id)
  if not projection then quarto.log.warning(message); return views.warning(message) end
  if not projection.nodes or not projection.edges then return views.warning(views.tr("Graph projection is incomplete.", "A projeção do grafo está incompleta.")) end
  views.localize_projection(projection)

  local filter_cond = parse_filter(views.kwarg(kwargs, "filter", ""))
  if next(filter_cond) then projection = filter_projection(projection, filter_cond) end

  local root_id = views.kwarg(kwargs, "root", "")
  if root_id ~= "" then
    local rooted, root_error = root_projection(projection, root_id, views.kwarg(kwargs, "depth", "3"))
    if not rooted then return views.warning(root_error) end
    projection = rooted
  end

  local blocks = {}
  local source = M.mermaid_source(projection)
  local description = views.tr("Traceability graph for ", "Grafo de rastreabilidade para ") .. instance_id
  local rendered = false
  if views.is_html_format() then
    local svg = views.mermaid_inline_svg(source, description, "need-graph-figure")
    if svg then
      table.insert(blocks, pandoc.Div({pandoc.RawBlock("html", svg)}, pandoc.Attr("", {"need-graph-scroll"})))
      rendered = true
    end
  end
  if not rendered then
    local image_name = views.render_mermaid_asset(source, "quarto-needs-graph")
    if image_name then
      local image = pandoc.Image({pandoc.Str(description)}, image_name, "", pandoc.Attr("", {"need-graph-figure"}, {role="img"}))
      table.insert(blocks, pandoc.Div({pandoc.Para({image})}, pandoc.Attr("", {"need-graph-scroll"})))
    else
      table.insert(blocks, views.warning(views.tr("Could not render this graph diagram.", "Não foi possível renderizar este diagrama de grafo.")))
    end
  end

  local summary_text = {}
  for _, entry in ipairs(summary_entries(projection)) do table.insert(summary_text, entry[1] .. ": " .. entry[2]) end
  table.insert(blocks, pandoc.Para({pandoc.Str(table.concat(summary_text, " · "))}))

  local node_header = {
    views.tr("ID", "ID"), views.tr("Title", "Título"), views.tr("Type", "Tipo"),
    views.tr("Status", "Status"), views.tr("Priority", "Prioridade"),
    views.tr("Tags", "Tags"), views.tr("Change", "Mudança"),
  }
  -- IDs name needs: link them to the needs they identify, the same
  -- convention need-table's id column already follows. The link target
  -- comes from the projected node's public `href` (site-relative, same one
  -- the canvas tooltip's "Open need" uses); an id that survives as a bare
  -- string (outside the selected node set, e.g. ghost overlay entries)
  -- stays the plain text it always was.
  local nodes_by_id = {}
  for _, node in ipairs(projection.nodes) do nodes_by_id[text(node.id)] = node end
  local function linked_cell(identifier)
    local node = nodes_by_id[text(identifier)]
    local href = node and text(node.href) or ""
    if href == "" then return text(identifier) end
    return {pandoc.Link({pandoc.Str(text(identifier))}, href, "")}
  end
  local node_rows, node_row_ids = {}, {}
  -- Type/status/priority/tags go through the shared badge generator, the
  -- same convention need-table and dashboard cells already follow, so the
  -- values carry the predefined need-type-*/need-status-*/need-priority-*
  -- styles here too (tags stay on needs.css's transparent .need-tag rule).
  for _, row in ipairs(node_table_rows(projection)) do
    table.insert(node_rows, {linked_cell(row.id), row.title, views.badge("type", row.type), views.badge("status", row.status), views.badge("priority", row.priority), tag_cell(row.tags), row.change})
    table.insert(node_row_ids, row.id)
  end
  table.insert(blocks, table_block(node_header, node_rows, "node", node_row_ids))

  local header = {
    views.tr("Source", "Origem"), views.tr("Relation", "Relação"), views.tr("Target", "Destino"),
    views.tr("Change", "Mudança"), views.tr("Impact", "Impacto")
  }
  local rows, edge_row_ids = {}, {}
  for _, row in ipairs(edge_table_rows(projection)) do
    table.insert(rows, {linked_cell(row.source), row.relation, linked_cell(row.target), row.change, row.impact})
    table.insert(edge_row_ids, row.id)
  end
  table.insert(blocks, table_block(header, rows, "edge", edge_row_ids))

  local encoded_ok, encoded = pcall(pandoc.json.encode, projection)
  local projection_changed = views.language() ~= "en" or next(filter_cond) or root_id ~= ""
  local json_payload = projection_changed and encoded_ok and encoded or raw_json
  local search = views.tr("Search graph", "Buscar no grafo")
  local placeholder = views.tr("Search by ID or title", "Buscar por ID ou título")
  local color = views.tr("Color nodes by", "Colorir nós por")
  local controls = pandoc.RawBlock("html",
    '<div class="need-graph-controls" data-need-graph-controls="' .. instance_id .. '">' ..
    '<label class="visually-hidden" for="' .. instance_id .. '-search">' .. search .. '</label>' ..
    '<input id="' .. instance_id .. '-search" class="need-graph-search" type="search" placeholder="' .. placeholder .. '">' ..
    '<label class="visually-hidden" for="' .. instance_id .. '-color">' .. color .. '</label>' ..
    '<select id="' .. instance_id .. '-color" class="need-graph-color" data-need-graph-color>' ..
    '<option value="change" selected>' .. views.tr("Color: change", "Cor: mudança") .. '</option>' ..
    '<option value="type">' .. views.tr("Color: type", "Cor: tipo") .. '</option>' ..
    '<option value="status">' .. views.tr("Color: status", "Cor: status") .. '</option>' ..
    '<option value="priority">' .. views.tr("Color: priority", "Cor: prioridade") .. '</option>' ..
    '<option value="none">' .. views.tr("No color", "Sem cor") .. '</option></select>' ..
    '<button type="button" class="need-graph-fit">' .. views.tr("Fit", "Ajustar") .. '</button>' ..
    '<button type="button" class="need-graph-reset">' .. views.tr("Reset", "Redefinir") .. '</button>' ..
    '<button type="button" class="need-graph-fullscreen">' .. views.tr("Fullscreen", "Tela cheia") .. '</button>' ..
    '<button type="button" class="need-graph-export-png">' .. views.tr("Export PNG", "Exportar PNG") .. '</button></div>')
  local canvas = pandoc.RawBlock("html", '<div class="need-graph-canvas" data-need-graph-canvas="' .. instance_id .. '" role="img" aria-label="' .. views.tr("Interactive traceability graph", "Grafo de rastreabilidade interativo") .. '"><div class="need-graph-loading">' .. views.tr("Loading interactive graph…", "Carregando grafo interativo…") .. '</div><div id="' .. instance_id .. '-minimap" class="cytoscape-navigator" data-need-graph-minimap="' .. instance_id .. '" aria-hidden="true"></div></div>')
  local data_script = pandoc.RawBlock("html", '<script type="application/json" data-need-graph-data="' .. instance_id .. '">' .. views.script_json(json_payload) .. '</script>')
  -- The overlay annotation artifact (written by write_graph_overlays when the
  -- project has a comparison baseline) rides along when it exists; its script
  -- tag's presence is the browser-side availability signal.
  local overlays_script = nil
  local overlays_full = pandoc.path.join({root, ".quarto-needs", "graphs", projection_id .. "-overlays.json"})
  local overlays_file = io.open(overlays_full, "rb")
  if overlays_file then
    local overlays_contents = overlays_file:read("*a"); overlays_file:close()
    local overlays_ok, overlays_decoded = pcall(pandoc.json.decode, overlays_contents)
    if overlays_ok and type(overlays_decoded) == "table" and type(overlays_decoded.schemaVersion) == "string" then
      overlays_script = pandoc.RawBlock("html", '<script type="application/json" data-need-graph-overlays="' .. instance_id .. '">' .. views.script_json(overlays_contents) .. '</script>')
    end
  end
  local status = pandoc.RawBlock("html", '<div class="need-graph-status visually-hidden" role="status" data-need-graph-status="' .. instance_id .. '"></div>')
  table.insert(blocks, pandoc.RawBlock("html", '<div class="need-graph-container">'))
  table.insert(blocks, controls); table.insert(blocks, canvas); table.insert(blocks, status); table.insert(blocks, data_script)
  if overlays_script then table.insert(blocks, overlays_script) end
  table.insert(blocks, pandoc.RawBlock("html", "</div>"))
  return pandoc.Div(blocks, pandoc.Attr(instance_id, {"need-graph", "need-graph-progressive"}, {["data-need-graph"]=instance_id}))
end

return M