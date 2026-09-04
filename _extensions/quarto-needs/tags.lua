-- Tag index view: one table listing every object with its tags, filterable
-- client-side. The chapter itself is authored by the project (usually a
-- "Tags" entry in _quarto.yml) containing `{{< need-tags >}}`; tags.js reads
-- the ?tag= query parameter — what a clicked tag badge deep-links to, once
-- the project configures `quarto-needs: tags-page:` — and hides every row
-- whose tag badges do not carry it. Without JS the page degrades to the
-- full, unfiltered table.
local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)" ) or ""
end

local views = dofile(script_dir() .. "views.lua")
local M = {}

-- JSON null arrives from pandoc.json.decode as a userdata sentinel; stringify
-- would render it as a pointer, so it collapses to "" like data.lua's text().
local function text(value)
  if value == nil then return "" end
  if type(value) == "userdata" then return "" end
  if type(value) == "table" then return pandoc.utils.stringify(value) end
  return tostring(value)
end

-- Raw `tags` attributes may be "a;b", "a,b" or a real list, matching the
-- normalization the Python engine applies to projections. Values are deduped
-- by slug, since the slug is what both the badge class and the ?tag= param
-- carry.
local function object_tags(object)
  local attributes = type(object.attributes) == "table" and object.attributes or {}
  local raw = attributes.tags
  local tags, seen = {}, {}
  local function add(value)
    local tag = text(value):gsub("^%s+", ""):gsub("%s+$", "")
    local slug = views.slug(tag)
    if tag == "" or slug == "" or seen[slug] then return end
    seen[slug] = true
    tags[#tags + 1] = {tag = tag, slug = slug}
  end
  if type(raw) == "table" and raw[1] ~= nil then
    for _, item in ipairs(raw) do add(item) end
  else
    for piece in text(raw):gmatch("[^;,]+") do add(piece) end
  end
  return tags
end

local function tag_badges(tags)
  local inlines = {}
  for _, entry in ipairs(tags) do
    if #inlines > 0 then table.insert(inlines, pandoc.Space()) end
    for _, badge in ipairs(views.badge("tag", entry.tag)) do table.insert(inlines, badge) end
  end
  return inlines
end

function M.render_shortcode(args, kwargs)
  views.ensure_assets()
  local graph, message = views.load()
  if not graph then return views.warning(message) end
  local objects, selection_error = views.select(graph, graph.objects, kwargs)
  if selection_error then
    quarto.log.warning(selection_error)
    return views.warning(selection_error)
  end
  objects = views.sort(objects, kwargs)
  if #objects == 0 then
    return views.empty(views.tr("No needs match this query.", "Nenhum objeto corresponde a esta consulta."))
  end

  local chips, seen = {}, {}
  for _, object in ipairs(objects) do
    for _, entry in ipairs(object_tags(object)) do
      if not seen[entry.slug] then
        seen[entry.slug] = true
        chips[#chips + 1] = entry
      end
    end
  end
  table.sort(chips, function(a, b) return a.slug < b.slug end)

  local blocks = {}
  if views.is_html_format() then
    -- The "All" chip is the clear-filter affordance: same URL, no ?tag=.
    local chip_inlines = {
      pandoc.Link(
        {pandoc.Str(views.tr("All", "Todas"))}, "?", "",
        pandoc.Attr("", {"need-badge", "need-tag", "need-tag-chip", "need-tag-chip-clear"})
      ),
    }
    for _, entry in ipairs(chips) do
      chip_inlines[#chip_inlines + 1] = pandoc.Str(" ")
      chip_inlines[#chip_inlines + 1] = pandoc.Link(
        {pandoc.Str(entry.tag)}, "?tag=" .. entry.slug, "",
        pandoc.Attr("", {"need-badge", "need-tag", "need-tag-chip"}, {["data-need-tag"] = entry.slug})
      )
    end
    table.insert(blocks, pandoc.Div(
      {pandoc.Plain(chip_inlines)},
      pandoc.Attr("", {"need-tags-chips"}, {role = "group", ["aria-label"] = views.tr("Filter by tag", "Filtrar por tag")})
    ))
    table.insert(blocks, pandoc.Div(
      {pandoc.Plain({pandoc.Str(tostring(#objects) .. " " .. views.tr("elements", "elementos"))})},
      pandoc.Attr("", {"need-tags-status"}, {role = "status"})
    ))
  end

  local headers = {
    views.tr("ID", "ID"), views.tr("Title", "Título"), views.tr("Type", "Tipo"),
    views.tr("Status", "Status"), views.tr("Tags", "Tags"),
  }
  local rows = {}
  for _, object in ipairs(objects) do
    rows[#rows + 1] = {
      {views.link(object)},
      {pandoc.Str(text(object.title))},
      views.badge("type", object.type),
      views.badge("status", object.status),
      tag_badges(object_tags(object)),
    }
  end
  local table_id = views.reserve_view_id("need-tags", views.kwarg(kwargs, "id"))
  local table_block = views.table(nil, headers, rows, pandoc.Attr(table_id, {"need-table"}))
  -- data-need-table hands the table to needs.js, so the tags page inherits
  -- the same search box and sortable columns as need-table for free.
  table.insert(blocks, pandoc.Div(
    {table_block},
    pandoc.Attr("", {"need-table-container"}, {["data-need-table"] = "true"})
  ))

  local attributes = {}
  if views.is_html_format() then
    attributes = {
      ["data-need-tags"] = "true",
      ["data-need-tags-filtered"] = views.tr(
        "Showing {shown} of {total} elements tagged “{tag}”.",
        "Mostrando {shown} de {total} elementos com a tag “{tag}”."
      ),
      ["data-need-tags-zero"] = views.tr(
        "No elements tagged “{tag}”.",
        "Nenhum elemento com a tag “{tag}”."
      ),
    }
  end
  return pandoc.Div(blocks, pandoc.Attr("", {"need-tags"}, attributes))
end

return M
