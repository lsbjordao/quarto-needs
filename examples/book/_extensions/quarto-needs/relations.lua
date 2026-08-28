-- Static, catalog-labeled relation sections shared by need cards and shortcodes.
local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local views = dofile(script_dir() .. "views.lua")
local M = {}

local function text(value)
  if value == nil then return "" end
  return pandoc.utils.stringify(value)
end

local function words(value)
  local inlines = {}
  for token in text(value):gmatch("%S+") do
    if #inlines > 0 then inlines[#inlines + 1] = pandoc.Space() end
    inlines[#inlines + 1] = pandoc.Str(token)
  end
  return inlines
end

local function catalog_entry(graph, relation_type)
  local extensions = type(graph.extensions) == "table" and graph.extensions or {}
  local quarto_needs = type(extensions.quartoNeeds) == "table" and extensions.quartoNeeds or {}
  local catalog = type(quarto_needs.relationCatalog) == "table" and quarto_needs.relationCatalog or {}
  local entry = catalog[relation_type]
  if type(entry) == "table" then return entry end
  return nil
end

local DIRECTIONS = {
  outgoing = {
    class = "need-relations",
    title = function() return views.tr("Need relations", "Relações") end,
    endpoint = function(relation) return text(relation.target) end,
    label = function(entry, relation_type)
      local label = entry and text(entry.directLabel) or relation_type
      return views.relation_label(relation_type, false, label)
    end,
  },
  incoming = {
    class = "need-backlinks",
    title = function() return views.tr("Need backlinks", "Referências inversas") end,
    endpoint = function(relation) return text(relation.source) end,
    label = function(entry, relation_type)
      local label = entry and text(entry.inverseLabel) or ("Referenced by: " .. relation_type)
      return views.relation_label(relation_type, true, label)
    end,
  },
}

local function before(a, b)
  local lowered_a, lowered_b = a:lower(), b:lower()
  if lowered_a ~= lowered_b then return lowered_a < lowered_b end
  return a < b
end

local function grouped(graph, relations, direction)
  local spec = DIRECTIONS[direction]
  local labels, groups = {}, {}
  for _, relation in ipairs(relations) do
    local relation_type = text(relation.type)
    local label = spec.label(catalog_entry(graph, relation_type), relation_type)
    if not groups[label] then groups[label] = {}; labels[#labels + 1] = label end
    table.insert(groups[label], spec.endpoint(relation))
  end
  table.sort(labels, before)
  for _, label in ipairs(labels) do table.sort(groups[label], before) end
  return labels, groups
end

local function endpoint_inlines(graph, id)
  local object = views.get(graph, id)
  if not object then
    return {pandoc.Span({pandoc.Str(id)}, pandoc.Attr("", {"need-relation-missing"}))}
  end
  local inlines = {views.link(object)}
  local title = text(object.title)
  if title ~= "" then
    inlines[#inlines + 1] = pandoc.Str(" — ")
    for _, inline in ipairs(words(title)) do inlines[#inlines + 1] = inline end
  end
  return inlines
end

local function direction_div(graph, object_id, relations, direction)
  local spec = DIRECTIONS[direction]
  local labels, groups = grouped(graph, relations, direction)
  local items = {}
  for _, label in ipairs(labels) do
    local definitions = {}
    for _, endpoint in ipairs(groups[label]) do
      definitions[#definitions + 1] = {pandoc.Plain(endpoint_inlines(graph, endpoint))}
    end
    items[#items + 1] = {words(label), definitions}
  end
  local title = pandoc.Div(
    {pandoc.Plain({pandoc.Strong(words(spec.title()))})},
    pandoc.Attr("", {spec.class .. "-title"})
  )
  local list = pandoc.Div({pandoc.DefinitionList(items)}, pandoc.Attr("", {"need-relation-groups"}))
  return pandoc.Div({title, list}, pandoc.Attr("", {spec.class}))
end

function M.render_for_card(graph, object_id)
  local blocks = {}
  local outgoing = views.outgoing(graph, object_id)
  if #outgoing > 0 then blocks[#blocks + 1] = direction_div(graph, object_id, outgoing, "outgoing") end
  local incoming = views.incoming(graph, object_id)
  if #incoming > 0 then blocks[#blocks + 1] = direction_div(graph, object_id, incoming, "incoming") end
  return blocks
end

function M.render_backlinks(graph, object_id)
  local incoming = views.incoming(graph, object_id)
  if #incoming == 0 then
    return views.empty(views.tr("No backlinks for ", "Nenhuma referência inversa para ") .. object_id .. ".")
  end
  return direction_div(graph, object_id, incoming, "incoming")
end

return M
