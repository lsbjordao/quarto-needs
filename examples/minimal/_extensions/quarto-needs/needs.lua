local function extension_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)" ) or ""
end

local views = dofile(extension_dir() .. "views.lua")
local relations = dofile(extension_dir() .. "relations.lua")
local tags = dofile(extension_dir() .. "tags.lua")

local function value(attrs, key, default)
  local v = attrs.attributes[key]
  if v == nil or v == "" then return default end
  return v
end

local slug = views.slug

function Div(el)
  if not el.classes:includes("need") then return nil end
  views.ensure_assets()
  local id = el.identifier
  local need_type = value(el, "type", "need")
  local status = value(el, "status", "draft")
  local priority = value(el, "priority", "")

  -- Load the semantic object before building the header. Most card fields are
  -- authored as fenced-div attributes, but structured metadata may also come
  -- from the parser preamble. Using the graph as a fallback keeps the rendered
  -- header aligned with the canonical engineering object.
  local graph, message = views.load()
  local graph_object = graph and views.get(graph, id) or nil
  local date = value(el, "date", "")
  if date == "" and graph_object and type(graph_object.attributes) == "table" then
    date = pandoc.utils.stringify(graph_object.attributes.date or "")
  end
  local tags_value = value(el, "tags", "")
  if tags_value == "" and graph_object and type(graph_object.attributes) == "table" then
    tags_value = graph_object.attributes.tags
  end
  local card_tags = tags.parse_tags(tags_value)

  local heading_index = nil
  local heading_level = 3
  local heading_content = {pandoc.Str(id)}
  for i, block in ipairs(el.content) do
    if block.t == "Header" then
      heading_level = block.level
      heading_content = block.content
      heading_index = i
      break
    end
  end

  local title_inlines = {
      pandoc.Span({pandoc.Str(id)}, pandoc.Attr("", {"need-id"})),
      pandoc.Str(" · "),
      pandoc.Span(heading_content, pandoc.Attr("", {"need-title"}))
  }
  local badge_inlines = {}
  local function append_badge(kind, raw)
    local badges = views.badge(kind, raw)
    if #badges == 0 then return end
    if #badge_inlines > 0 then table.insert(badge_inlines, pandoc.Space()) end
    for _, inline in ipairs(badges) do table.insert(badge_inlines, inline) end
  end
  append_badge("type", need_type)
  append_badge("status", status)
  append_badge("priority", priority)
  if need_type == "architecture-decision" then append_badge("date", date) end
  local badges = pandoc.Div({pandoc.Plain(badge_inlines)}, pandoc.Attr("", {"need-header-badges"}))
  local need_type_class = "need-type-" .. slug(need_type)
  local header = pandoc.Header(
    heading_level,
    title_inlines,
    pandoc.Attr(
      id,
      {"need-card-section", "need-heading", "unnumbered", need_type_class}
    )
  )

  local body = {}
  local function mark_unnumbered(block)
    if not block.classes:includes("unnumbered") then
      block.classes:insert("unnumbered")
    end
    return block
  end
  for i, block in ipairs(el.content) do
    if i ~= heading_index then
      if block.t == "Header" then
        local suffix = block.identifier
        if suffix == "" then suffix = slug(pandoc.utils.stringify(block.content)) end
        block.identifier = id .. "-" .. suffix
        block = mark_unnumbered(block)
      else
        block = block:walk({Header = mark_unnumbered})
      end
      table.insert(body, block)
    end
  end
  if graph then
    for _, block in ipairs(relations.render_for_card(graph, id)) do
      table.insert(body, block)
    end
  else
    table.insert(body, views.warning(message))
  end

  -- The card carries its own tag row directly below the description (the
  -- first paragraph), so authored subsections and the relation sections
  -- stack underneath it. A card without a paragraph shows the tags first.
  if #card_tags > 0 then
    local tags_block = pandoc.Div(
      {pandoc.Plain(tags.badge_line(card_tags))},
      pandoc.Attr("", {"need-card-tags"})
    )
    local insert_at = 1
    for i, block in ipairs(body) do
      if block.t == "Para" then insert_at = i + 1; break end
    end
    table.insert(body, insert_at, tags_block)
  end

  return {
    header,
    badges,
    pandoc.Div(
      body,
      pandoc.Attr("", {"need-card", need_type_class}, {["data-need-id"] = id})
    )
  }
end
