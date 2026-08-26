-- Deterministic, bounded Mermaid source generation for need-flow.
local M = {}

local MAX_NODES = 100
local MAX_EDGES = 300
local MAX_DEPTH = 10

local palettes = {
  ["stakeholder-need"] = "fill:#f1f5f9,stroke:#475569,color:#1e293b",
  ["system-requirement"] = "fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a",
  ["functional-requirement"] = "fill:#dbeafe,stroke:#2563eb,color:#1e3a8a",
  ["non-functional-requirement"] = "fill:#ede9fe,stroke:#7c3aed,color:#4c1d95",
  ["test-case"] = "fill:#ccfbf1,stroke:#0f766e,color:#134e4a",
  evidence = "fill:#dcfce7,stroke:#15803d,color:#14532d",
  risk = "fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d",
  threat = "fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d",
  component = "fill:#fef3c7,stroke:#b45309,color:#78350f",
  interface = "fill:#ffedd5,stroke:#c2410c,color:#7c2d12",
}

local fallback_palette = "fill:#f8fafc,stroke:#64748b,color:#1e293b"

local function text(value)
  if value == nil then return "" end
  return pandoc.utils.stringify(value)
end

local function sorted_objects(objects)
  local result = {}
  for _, object in ipairs(objects or {}) do result[#result + 1] = object end
  table.sort(result, function(left, right) return text(left.id) < text(right.id) end)
  return result
end

local function relation_options(kwargs, views)
  local result = {}
  for value in views.kwarg(kwargs, "relations"):gmatch("[^,;]+") do
    result[value:match("^%s*(.-)%s*$")] = true
  end
  return result
end

local function sorted_relations(relations, allowed)
  local result = {}
  for _, relation in ipairs(relations or {}) do
    if next(allowed) == nil or allowed[text(relation.type)] then
      result[#result + 1] = relation
    end
  end
  table.sort(result, function(left, right)
    local left_source, right_source = text(left.source), text(right.source)
    if left_source ~= right_source then return left_source < right_source end
    local left_type, right_type = text(left.type), text(right.type)
    if left_type ~= right_type then return left_type < right_type end
    return text(left.target) < text(right.target)
  end)
  return result
end

local function palette_for(object_type, views)
  local slug = views.slug(object_type)
  return palettes[slug] or fallback_palette
end

local function add_warning(warnings, message)
  for _, existing in ipairs(warnings) do if existing == message then return end end
  warnings[#warnings + 1] = message
end

function M.build(graph, kwargs, views)
  local warnings = {}
  local objects = sorted_objects(graph.objects)
  local by_id = views.objects_by_id(objects)
  local root = views.kwarg(kwargs, "root")
  if root ~= "" and not by_id[root] then return nil, "Unknown need-flow root: " .. root end

  local relations = sorted_relations(graph.relations, relation_options(kwargs, views))
  local selected = {}
  local selected_count = 0

  if root == "" then
    local pool = objects
    local query_name = views.kwarg(kwargs, "query")
    if query_name ~= "" then
      local wanted = views.named_query_ids(graph, query_name)
      if wanted == nil then
        add_warning(warnings, "Unknown query: " .. query_name)
        return {source = "", node_count = 0, edge_count = 0, warnings = warnings}
      end
      pool = {}
      for _, object in ipairs(objects) do
        if wanted[text(object.id)] then pool[#pool + 1] = object end
      end
    end
    local matching = views.sort(views.filter(pool, kwargs), {})
    if #matching == 0 then
      return {source = "", node_count = 0, edge_count = 0, warnings = warnings}
    end
    for index, object in ipairs(matching) do
      if index > MAX_NODES then
        add_warning(warnings, "Flow is limited to the first 100 matching needs.")
        break
      end
      selected[text(object.id)] = true
      selected_count = selected_count + 1
    end
  else
    selected[root] = true
    selected_count = 1
    local frontier = {[root] = true}
    local requested_depth = tonumber(views.kwarg(kwargs, "depth", "3")) or 3
    requested_depth = math.max(0, math.floor(requested_depth))
    local depth = math.min(requested_depth, MAX_DEPTH)
    if requested_depth > MAX_DEPTH then add_warning(warnings, "Flow depth is limited to 10.") end

    for _ = 1, depth do
      local candidates = {}
      for _, relation in ipairs(relations) do
        local source, target = text(relation.source), text(relation.target)
        if frontier[source] and by_id[target] and not selected[target] then candidates[target] = true end
        if frontier[target] and by_id[source] and not selected[source] then candidates[source] = true end
      end
      local candidate_ids = {}
      for id in pairs(candidates) do candidate_ids[#candidate_ids + 1] = id end
      table.sort(candidate_ids)
      if #candidate_ids == 0 then break end
      local next_frontier = {}
      for _, id in ipairs(candidate_ids) do
        if selected_count >= MAX_NODES then
          add_warning(warnings, "Flow is limited to the first 100 reachable needs.")
          break
        end
        selected[id] = true
        selected_count = selected_count + 1
        next_frontier[id] = true
      end
      frontier = next_frontier
      if selected_count >= MAX_NODES then break end
    end
  end

  local selected_objects, classes = {}, {}
  for _, object in ipairs(objects) do
    if selected[text(object.id)] then
      selected_objects[#selected_objects + 1] = object
      classes["need_type_" .. views.slug(object.type):gsub("-", "_")] = palette_for(object.type, views)
    end
  end

  local selected_relations, seen_edges = {}, {}
  for _, relation in ipairs(relations) do
    local source, target, relation_type = text(relation.source), text(relation.target), text(relation.type)
    if selected[source] and selected[target] then
      local key = source .. "\0" .. relation_type .. "\0" .. target
      if not seen_edges[key] then
        seen_edges[key] = true
        selected_relations[#selected_relations + 1] = relation
      end
    end
  end
  if #selected_relations > MAX_EDGES then
    add_warning(warnings, "Flow is limited to the first 300 matching relations.")
    while #selected_relations > MAX_EDGES do table.remove(selected_relations) end
  end

  local directions = {TD = true, TB = true, BT = true, LR = true, RL = true}
  local direction = views.kwarg(kwargs, "direction", "TD"):upper()
  if not directions[direction] then direction = "TD" end
  local lines = {"flowchart " .. direction}

  for _, object in ipairs(selected_objects) do
    local id = text(object.id)
    local class_name = "need_type_" .. views.slug(object.type):gsub("-", "_")
    lines[#lines + 1] = views.node_id(id) .. '["' .. views.escape_mermaid(id .. "<br/>" .. text(object.title)) .. '"]'
    lines[#lines + 1] = "class " .. views.node_id(id) .. " " .. class_name
  end

  local class_names = {}
  for class_name in pairs(classes) do class_names[#class_names + 1] = class_name end
  table.sort(class_names)
  for _, class_name in ipairs(class_names) do
    lines[#lines + 1] = "classDef " .. class_name .. " " .. classes[class_name]
  end

  for _, relation in ipairs(selected_relations) do
    lines[#lines + 1] = views.node_id(relation.source) .. " -->|" .. views.escape_mermaid(relation.type) .. "| " .. views.node_id(relation.target)
  end

  return {
    source = table.concat(lines, "\n"),
    node_count = #selected_objects,
    edge_count = #selected_relations,
    warnings = warnings,
  }
end

return M
