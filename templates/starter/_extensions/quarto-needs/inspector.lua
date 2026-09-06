-- Inline inspector for a single need, localized without changing graph semantics.
local function script_dir()
  local source=debug.getinfo(1,"S").source; if source:sub(1,1)=="@" then source=source:sub(2) end; return source:match("(.*/)") or ""
end
local views=dofile(script_dir().."views.lua")
local relations=dofile(script_dir().."relations.lua")
local M={}
local function L(en,pt) return views.tr(en,pt) end
local function text(value) if value==nil then return "" end return pandoc.utils.stringify(value) end
local function words(value) local r={}; for token in text(value):gmatch("%S+") do if #r>0 then r[#r+1]=pandoc.Space() end; r[#r+1]=pandoc.Str(token) end; return r end
local function before(a,b) local al,bl=a:lower(),b:lower(); if al~=bl then return al<bl end; return a<b end
local function attribute_value(value) if type(value)~="table" then return text(value) end; local p={}; for _,item in ipairs(value) do p[#p+1]=text(item) end; if #p>0 then return table.concat(p,", ") end; return text(value) end
local function badge_inlines(object)
  local inlines={}; local function append(kind,raw) local badges=views.badge(kind,raw); if #badges==0 then return end; if #inlines>0 then inlines[#inlines+1]=pandoc.Space() end; for _,badge in ipairs(badges) do inlines[#inlines+1]=badge end end
  append("type",object.type); append("status",object.status); append("priority",(object.attributes or {}).priority); return inlines
end
local function provenance_block(object)
  local source=type(object.source)=="table" and object.source or nil; local file=source and text(source.file) or ""; if file=="" then return nil end
  local location=file; local line=source.line and math.floor(tonumber(source.line) or 0) or 0; if line>0 then location=location..":"..tostring(line) end
  local inlines=words(L("Declared in","Declarado em")); inlines[#inlines+1]=pandoc.Space(); inlines[#inlines+1]=pandoc.Str(location); return pandoc.Para(inlines)
end
local function attribute_blocks(object)
  local attributes=type(object.attributes)=="table" and object.attributes or {}; local keys={}; for key in pairs(attributes) do keys[#keys+1]=text(key) end; table.sort(keys,before); if #keys==0 then return {} end
  local items={}; for _,key in ipairs(keys) do items[#items+1]={words(key),{{pandoc.Plain({pandoc.Str(attribute_value(attributes[key]))})}}} end
  return {pandoc.Para({pandoc.Strong(words(L("Attributes","Atributos")))}),pandoc.Div({pandoc.DefinitionList(items)},pandoc.Attr("",{"need-inspector-attributes"}))}
end
local function finding_blocks(graph,object_id)
  local findings=type(graph.validation)=="table" and graph.validation or {}; local entries={}
  for _,finding in ipairs(findings) do if text(finding.object_id)==object_id then local inlines={pandoc.Strong({pandoc.Str(text(finding.code))}),pandoc.Str(" ("),pandoc.Str(text(finding.severity)),pandoc.Str("): ")}; for _,inline in ipairs(words(finding.message)) do inlines[#inlines+1]=inline end; entries[#entries+1]={pandoc.Plain(inlines)} end end
  if #entries==0 then return {} end; return {pandoc.Para({pandoc.Strong(words(L("Findings","Achados")))}),pandoc.BulletList(entries)}
end
function M.render(graph,id,kwargs)
  local object=views.get(graph,id); if not object then return nil end
  local region_id=views.reserve_view_id("need-inspector",views.kwarg(kwargs,"id")); local heading_id=views.reserve_view_id("need-inspector-title",region_id.."-title")
  local heading=words(L("Inspector:","Inspetor:")); heading[#heading+1]=pandoc.Space(); heading[#heading+1]=pandoc.Str(id); local title=text(object.title); if title~="" then heading[#heading+1]=pandoc.Space(); heading[#heading+1]=pandoc.Str("—"); heading[#heading+1]=pandoc.Space(); for _,inline in ipairs(words(title)) do heading[#heading+1]=inline end end
  local blocks={pandoc.Header(4,{pandoc.Span(heading,pandoc.Attr(heading_id))},pandoc.Attr("",{"need-inspector-title"}))}; local badges=badge_inlines(object); if #badges>0 then blocks[#blocks+1]=pandoc.Para(badges) end
  local provenance=provenance_block(object); if provenance then blocks[#blocks+1]=provenance end; for _,block in ipairs(attribute_blocks(object)) do blocks[#blocks+1]=block end; for _,block in ipairs(relations.render_for_card(graph,id)) do blocks[#blocks+1]=block end; for _,block in ipairs(finding_blocks(graph,id)) do blocks[#blocks+1]=block end
  return pandoc.Div(blocks,pandoc.Attr(region_id,{"need-inspector"},{role="region",["aria-labelledby"]=heading_id}))
end
return M
