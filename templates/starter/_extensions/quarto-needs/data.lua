-- Cached graph access and pure link resolution for quarto-needs.
-- Python owns relation semantics; this module only indexes the emitted graph.
local M = {}

local CACHE_KEY = "__quarto_needs_data_cache_v1"
local cache = rawget(_G, CACHE_KEY)
if type(cache) ~= "table" or type(cache.by_path) ~= "table" or type(cache.by_graph) ~= "table" then
  cache = {
    by_path = {},
    by_graph = setmetatable({}, {__mode = "k"}),
  }
  rawset(_G, CACHE_KEY, cache)
end

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

local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

-- The manifest is the single version source; a constant here would be a second
-- one, and Task 1's packaging test cannot see into Lua to catch the drift.
local function extension_version()
  local file = io.open(script_dir() .. "_extension.yml", "r")
  if not file then return nil end
  local contents = file:read("*a")
  file:close()
  return contents:match("\nversion:%s*(%S+)") or contents:match("^version:%s*(%S+)")
end

-- Pre-1.0 releases treat the minor component as the breaking axis, which is why
-- a patch difference stays readable and a minor difference does not.
local function compatibility_key(version)
  local major, minor = tostring(version):match("^(%d+)%.(%d+)")
  if not major then return nil end
  if major == "0" then return major .. "." .. minor end
  return major
end

local function version_mismatch(graph)
  local ours = extension_version()
  if not ours then return nil end
  local extensions = type(graph.extensions) == "table" and graph.extensions or {}
  local quarto_needs = type(extensions.quartoNeeds) == "table" and extensions.quartoNeeds or {}
  local generator = type(quarto_needs.generator) == "table" and quarto_needs.generator or {}
  local theirs = generator.version
  -- A graph without generator metadata predates this field; accept it rather
  -- than breaking projects whose engine simply never wrote one.
  if theirs == nil then return nil end
  local wanted, found = compatibility_key(ours), compatibility_key(theirs)
  if not wanted or not found or wanted == found then return nil end
  return "Quarto Needs extension " .. ours .. " cannot read a graph written by engine "
    .. tostring(theirs) .. "; install matching versions"
end

local function relation_key(item)
  return text(item.type) .. "\0" .. text(item.source) .. "\0" .. text(item.target)
end

local function build_entry(graph)
  local by_id, outgoing, incoming = {}, {}, {}
  for _, object in ipairs(graph.objects or {}) do
    by_id[text(object.id)] = object
  end
  for _, relation in ipairs(graph.relations or {}) do
    local source, target = text(relation.source), text(relation.target)
    outgoing[source] = outgoing[source] or {}
    incoming[target] = incoming[target] or {}
    table.insert(outgoing[source], relation)
    table.insert(incoming[target], relation)
  end
  for _, index in pairs({outgoing, incoming}) do
    for _, items in pairs(index) do
      table.sort(items, function(a, b) return relation_key(a) < relation_key(b) end)
    end
  end
  return {graph = graph, by_id = by_id, outgoing = outgoing, incoming = incoming}
end

-- Decode the graph at `path` at most once per process, caching failures too so a
-- missing or malformed file keeps explaining itself instead of degrading to {}.
function M.load(path)
  local key = pandoc.path.normalize(text(path))
  local entry = cache.by_path[key]
  if entry then
    if entry.error then return nil, entry.error end
    return entry.graph
  end

  local file = io.open(key, "r")
  if not file then
    local message = "Quarto Needs graph not found: " .. key
    cache.by_path[key] = {error = message}
    return nil, message
  end
  local contents = file:read("*a")
  file:close()

  local ok, graph = pcall(pandoc.json.decode, contents)
  if not ok or type(graph) ~= "table" or type(graph.objects) ~= "table" then
    local message = "Quarto Needs graph is invalid: " .. key
    cache.by_path[key] = {error = message}
    return nil, message
  end

  local mismatch = version_mismatch(graph)
  if mismatch then
    cache.by_path[key] = {error = mismatch}
    return nil, mismatch
  end

  entry = build_entry(graph)
  cache.by_path[key] = entry
  cache.by_graph[entry.graph] = entry
  return entry.graph
end

-- Graph tables built outside `load` (legacy callers, tests) still get an index.
local function entry_for(graph)
  if type(graph) ~= "table" then return nil end
  local entry = cache.by_graph[graph]
  if entry then return entry end
  return build_entry(graph)
end

function M.get(graph, id)
  local entry = entry_for(graph)
  if not entry then return nil end
  return entry.by_id[text(id)]
end

-- Copy so callers cannot reorder or truncate the cached adjacency tuples.
local function filtered(items, relation_type)
  local result = {}
  for _, relation in ipairs(items or {}) do
    if relation_type == nil or text(relation.type) == text(relation_type) then
      result[#result + 1] = relation
    end
  end
  return result
end

function M.outgoing(graph, id, relation_type)
  local entry = entry_for(graph)
  if not entry then return {} end
  return filtered(entry.outgoing[text(id)], relation_type)
end

function M.incoming(graph, id, relation_type)
  local entry = entry_for(graph)
  if not entry then return {} end
  return filtered(entry.incoming[text(id)], relation_type)
end

local function source_of(object)
  return type(object) == "table" and type(object.source) == "table" and object.source or nil
end

local function anchor_of(object)
  local source = source_of(object)
  local anchor = source and text(source.anchor) or ""
  if anchor == "" then anchor = text(object.id) end
  return anchor
end

local function segments(path)
  local parts = {}
  for part in text(path):gmatch("[^/\\]+") do parts[#parts + 1] = part end
  return parts
end

-- Resolve "." and ".." without touching the filesystem; nil rejects a path that
-- climbs above the project root.
local function normalize(parts)
  local result = {}
  for _, part in ipairs(parts) do
    if part == ".." then
      if #result == 0 then return nil end
      table.remove(result)
    elseif part ~= "." then
      result[#result + 1] = part
    end
  end
  return result
end

local function as_page(path)
  return text(path):gsub("%.qmd$", ".html")
end

-- Pure, string-only link resolution. HTML gets a page-relative path; every other
-- format stays anchor-only because the document is a single file.
function M.link_target(object, options)
  options = options or {}
  local fragment = "#" .. anchor_of(object)

  local format = text(options.format):lower()
  if format ~= "" and not format:match("^html") then return fragment end

  local source = source_of(object)
  local file = source and text(source.file) or ""
  if file == "" then
    local href = text(object.href)
    if href ~= "" then return href end
    return "#" .. text(object.id)
  end

  local target = normalize(segments(as_page(file)))
  if not target or #target == 0 then return fragment end
  local current = normalize(segments(as_page(options.current_input)))
  if not current then return fragment end

  if table.concat(target, "/") == table.concat(current, "/") then return fragment end

  local directory = {}
  for i = 1, #current - 1 do directory[i] = current[i] end

  local shared = 0
  while shared < #directory and shared < #target - 1 and directory[shared + 1] == target[shared + 1] do
    shared = shared + 1
  end

  local pieces = {}
  for _ = shared + 1, #directory do pieces[#pieces + 1] = ".." end
  for i = shared + 1, #target do pieces[#pieces + 1] = target[i] end
  return table.concat(pieces, "/") .. fragment
end

return M
