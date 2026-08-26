-- Precomputed dashboard rendering. Python computes every number in the
-- report projection; this module only turns those numbers into Pandoc blocks.
local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local views = dofile(script_dir() .. "views.lua")

local M = {}

local STRENGTH_LABELS = {
  ["implementation-trace"] = "Implementation trace",
  ["implementation-effective"] = "Implementation effective",
  ["verification-trace"] = "Verification trace",
  ["verification-successful"] = "Verification successful",
  evidence = "Evidence",
}

local STRENGTH_ORDER = {
  "implementation-trace",
  "implementation-effective",
  "verification-trace",
  "verification-successful",
  "evidence",
}

local GAP_LABELS = {
  ["implementation-effective"] = "Implementation-effective gaps",
  ["verification-successful"] = "Verification-successful gaps",
  evidence = "Evidence gaps",
}

local BREAKDOWN_ORDER = {"type", "status", "priority"}

local BREAKDOWN_LABELS = {
  type = "Needs by type",
  status = "Needs by status",
  priority = "Needs by priority",
}

local SEVERITY_ORDER = {"error", "warning", "info"}

local SCOPE_LABELS = {
  catalog = "Whole catalog",
  ["approved-requirements"] = "Approved requirements",
}

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

-- JSON numbers decode as Lua floats, so counts must be formatted as integers
-- or every denominator would read "2.0 requirements".
local function count(value)
  return string.format("%d", math.floor(tonumber(value) or 0))
end

local function before(left, right)
  local left_lowered, right_lowered = left:lower(), right:lower()
  if left_lowered ~= right_lowered then return left_lowered < right_lowered end
  return left < right
end

local function report_of(graph)
  local extensions = type(graph.extensions) == "table" and graph.extensions or {}
  local quarto_needs = type(extensions.quartoNeeds) == "table" and extensions.quartoNeeds or {}
  return quarto_needs.report
end

local function endpoint_inlines(graph, id)
  local object = views.get(graph, id)
  if not object then
    return {pandoc.Span({pandoc.Str(id)}, pandoc.Attr("", {"need-relation-missing"}))}
  end
  return {views.link(object)}
end

local function findings_blocks(report)
  local findings = report.findings
  local counts = type(findings) == "table" and findings.counts or nil
  if type(counts) ~= "table" then return nil end
  local rows = {}
  for _, severity in ipairs(SEVERITY_ORDER) do
    rows[#rows + 1] = {{pandoc.Str(severity)}, {pandoc.Str(count(counts[severity]))}}
  end
  rows[#rows + 1] = {{pandoc.Str("total")}, {pandoc.Str(count(counts.total))}}
  return pandoc.Div({
    pandoc.Para({pandoc.Strong(words("Findings by severity"))}),
    views.table(nil, {{pandoc.Str("Severity")}, {pandoc.Str("Findings")}}, rows, nil),
  }, pandoc.Attr("", {"need-dashboard-findings"}))
end

local function scope_blocks(graph, name, data)
  local label = SCOPE_LABELS[name] or name
  local content = {}
  local heading = words(label)
  heading[#heading + 1] = pandoc.Space()
  heading[#heading + 1] = pandoc.Str("(" .. count(data.denominator) .. " requirements)")
  content[#content + 1] = pandoc.Para({pandoc.Strong(heading)})
  local rows = {}
  for _, strength in ipairs(STRENGTH_ORDER) do
    local measure = data.coverage and data.coverage[strength]
    if type(measure) == "table" then
      rows[#rows + 1] = {
        words(STRENGTH_LABELS[strength] or strength),
        {
          pandoc.Str(string.format(
            "%.1f%% (%d of %d)",
            tonumber(measure.percent) or 0.0,
            tonumber(measure.covered) or 0,
            tonumber(measure.total) or 0
          )),
        },
      }
    end
  end
  if #rows > 0 then
    content[#content + 1] = views.table(
      nil,
      {{pandoc.Str("Measure")}, {pandoc.Str("Coverage")}},
      rows,
      nil
    )
  end
  for _, dimension in ipairs(BREAKDOWN_ORDER) do
    local counts = data.breakdowns and data.breakdowns[dimension]
    if type(counts) == "table" then
      local keys = {}
      for key in pairs(counts) do keys[#keys + 1] = text(key) end
      table.sort(keys, before)
      local distribution = {}
      for _, key in ipairs(keys) do
        distribution[#distribution + 1] = {{pandoc.Str(key)}, {pandoc.Str(count(counts[key]))}}
      end
      if #distribution > 0 then
        content[#content + 1] = pandoc.Para({pandoc.Strong(words(BREAKDOWN_LABELS[dimension] or dimension))})
        content[#content + 1] = views.table(
          nil,
          {{pandoc.Str("Value")}, {pandoc.Str("Needs")}},
          distribution,
          nil
        )
      end
    end
  end

  local gap_names = {}
  for gap_name, ids in pairs(data.gaps or {}) do
    if type(ids) == "table" and #ids > 0 then gap_names[#gap_names + 1] = gap_name end
  end
  table.sort(gap_names, before)
  for _, gap_name in ipairs(gap_names) do
    local entries = {}
    for _, id in ipairs(data.gaps[gap_name]) do
      entries[#entries + 1] = {pandoc.Plain(endpoint_inlines(graph, text(id)))}
    end
    content[#content + 1] = pandoc.Para({pandoc.Strong(words(GAP_LABELS[gap_name] or gap_name))})
    content[#content + 1] = pandoc.BulletList(entries)
  end
  return pandoc.Div(content, pandoc.Attr("", {"need-dashboard-scope", "need-dashboard-" .. views.slug(name)}))
end

-- Returns blocks plus an optional unknown-query message; nil signals a missing
-- report so the caller can render the documented empty state.
function M.render(graph, kwargs)
  local report = report_of(graph)
  if type(report) ~= "table" or type(report.scopes) ~= "table" then
    return nil, nil
  end

  local names = {"catalog"}
  if type(report.scopes["approved-requirements"]) == "table" then
    names[#names + 1] = "approved-requirements"
  end
  local requested = views.kwarg(kwargs, "query")
  if requested ~= "" then
    if type(report.scopes[requested]) ~= "table" then
      return nil, "Unknown query: " .. requested
    end
    local already_listed = false
    for _, name in ipairs(names) do
      if name == requested then already_listed = true end
    end
    if not already_listed then names[#names + 1] = requested end
  end

  local blocks = {}
  blocks[#blocks + 1] = pandoc.Div(
    {pandoc.Plain({pandoc.Strong(words("Quality dashboard"))})},
    pandoc.Attr("", {"need-dashboard-title"})
  )
  for _, name in ipairs(names) do
    blocks[#blocks + 1] = scope_blocks(graph, name, report.scopes[name])
  end
  local findings = findings_blocks(report)
  if findings then blocks[#blocks + 1] = findings end
  return blocks, nil
end

return M
