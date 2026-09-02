-- Precomputed dashboard rendering. Python computes every number; Lua localizes presentation.
local function script_dir()
  local source = debug.getinfo(1, "S").source
  if source:sub(1, 1) == "@" then source = source:sub(2) end
  return source:match("(.*/)") or ""
end

local views = dofile(script_dir() .. "views.lua")
local M = {}

local function L(en, pt) return views.tr(en, pt) end
local function strength_label(key)
  local labels = {
    ["implementation-trace"] = {"Implementation trace", "Rastreabilidade de implementação"},
    ["implementation-effective"] = {"Implementation effective", "Implementação efetiva"},
    ["verification-trace"] = {"Verification trace", "Rastreabilidade de verificação"},
    ["verification-successful"] = {"Verification successful", "Verificação bem-sucedida"},
    evidence = {"Evidence", "Evidência"},
  }
  local pair = labels[key]; return pair and L(pair[1], pair[2]) or key
end
local STRENGTH_ORDER = {"implementation-trace", "implementation-effective", "verification-trace", "verification-successful", "evidence"}
local function gap_label(key)
  local labels = {
    ["implementation-effective"] = {"Implementation-effective gaps", "Lacunas de implementação efetiva"},
    ["verification-successful"] = {"Verification-successful gaps", "Lacunas de verificação bem-sucedida"},
    evidence = {"Evidence gaps", "Lacunas de evidência"},
  }
  local pair = labels[key]; return pair and L(pair[1], pair[2]) or key
end
local BREAKDOWN_ORDER = {"type", "status", "priority"}
local function breakdown_label(key)
  local labels = {
    type = {"Needs by type", "Objetos por tipo"},
    status = {"Needs by status", "Objetos por status"},
    priority = {"Needs by priority", "Objetos por prioridade"},
  }
  local pair = labels[key]; return pair and L(pair[1], pair[2]) or key
end
local SEVERITY_ORDER = {"error", "warning", "info"}
local function scope_label(key)
  if key == "catalog" then return L("Whole catalog", "Catálogo completo") end
  if key == "approved-requirements" then return L("Approved requirements", "Requisitos aprovados") end
  return key
end
local function text(value) if value == nil then return "" end return pandoc.utils.stringify(value) end
local function words(value)
  local inlines = {}
  for token in text(value):gmatch("%S+") do if #inlines > 0 then inlines[#inlines+1]=pandoc.Space() end; inlines[#inlines+1]=pandoc.Str(token) end
  return inlines
end
local function count(value) return string.format("%d", math.floor(tonumber(value) or 0)) end
local function before(left,right)
  local a,b=left:lower(),right:lower(); if a~=b then return a<b end; return left<right
end
local function report_of(graph)
  local extensions=type(graph.extensions)=="table" and graph.extensions or {}
  local qn=type(extensions.quartoNeeds)=="table" and extensions.quartoNeeds or {}
  return qn.report
end
local function endpoint_inlines(graph,id)
  local object=views.get(graph,id); if not object then return {pandoc.Span({pandoc.Str(id)}, pandoc.Attr("",{"need-relation-missing"}))} end
  return {views.link(object)}
end
local function findings_blocks(report)
  local findings=report.findings; local counts=type(findings)=="table" and findings.counts or nil
  if type(counts)~="table" then return nil end
  local rows={}
  for _,severity in ipairs(SEVERITY_ORDER) do rows[#rows+1]={{pandoc.Str(severity)},{pandoc.Str(count(counts[severity]))}} end
  rows[#rows+1]={{pandoc.Str(L("total","total"))},{pandoc.Str(count(counts.total))}}
  return pandoc.Div({pandoc.Para({pandoc.Strong(words(L("Findings by severity","Achados por severidade")))}), views.table(nil,{{pandoc.Str(L("Severity","Severidade"))},{pandoc.Str(L("Findings","Achados"))}},rows,nil)},pandoc.Attr("",{"need-dashboard-findings"}))
end
local function scope_blocks(graph,name,data)
  local content={}; local heading=words(scope_label(name)); heading[#heading+1]=pandoc.Space(); heading[#heading+1]=pandoc.Str("("..count(data.denominator).." "..L("requirements","requisitos")..")")
  content[#content+1]=pandoc.Para({pandoc.Strong(heading)})
  local rows={}
  for _,strength in ipairs(STRENGTH_ORDER) do
    local measure=data.coverage and data.coverage[strength]
    if type(measure)=="table" then rows[#rows+1]={words(strength_label(strength)),{pandoc.Str(string.format("%.1f%% (%d %s %d)",tonumber(measure.percent) or 0,tonumber(measure.covered) or 0,L("of","de"),tonumber(measure.total) or 0))}} end
  end
  if #rows>0 then content[#content+1]=views.table(nil,{{pandoc.Str(L("Measure","Medida"))},{pandoc.Str(L("Coverage","Cobertura"))}},rows,nil) end
  for _,dimension in ipairs(BREAKDOWN_ORDER) do
    local counts=data.breakdowns and data.breakdowns[dimension]
    if type(counts)=="table" then
      local keys={}; for key in pairs(counts) do keys[#keys+1]=text(key) end; table.sort(keys,before)
      local distribution={}; for _,key in ipairs(keys) do distribution[#distribution+1]={{pandoc.Str(key)},{pandoc.Str(count(counts[key]))}} end
      if #distribution>0 then content[#content+1]=pandoc.Para({pandoc.Strong(words(breakdown_label(dimension)))}); content[#content+1]=views.table(nil,{{pandoc.Str(L("Value","Valor"))},{pandoc.Str(L("Needs","Objetos"))}},distribution,nil) end
    end
  end
  local gap_names={}; for gap_name,ids in pairs(data.gaps or {}) do if type(ids)=="table" and #ids>0 then gap_names[#gap_names+1]=gap_name end end; table.sort(gap_names,before)
  for _,gap_name in ipairs(gap_names) do
    local entries={}; for _,id in ipairs(data.gaps[gap_name]) do entries[#entries+1]={pandoc.Plain(endpoint_inlines(graph,text(id)))} end
    content[#content+1]=pandoc.Para({pandoc.Strong(words(gap_label(gap_name)))}); content[#content+1]=pandoc.BulletList(entries)
  end
  return pandoc.Div(content,pandoc.Attr("",{"need-dashboard-scope","need-dashboard-"..views.slug(name)}))
end
function M.render(graph,kwargs)
  local report=report_of(graph); if type(report)~="table" or type(report.scopes)~="table" then return nil,nil end
  local names={"catalog"}; if type(report.scopes["approved-requirements"])=="table" then names[#names+1]="approved-requirements" end
  local requested=views.kwarg(kwargs,"query")
  if requested~="" then if type(report.scopes[requested])~="table" then return nil,L("Unknown query: ","Consulta desconhecida: ")..requested end; local listed=false; for _,name in ipairs(names) do if name==requested then listed=true end end; if not listed then names[#names+1]=requested end end
  local blocks={pandoc.Div({pandoc.Plain({pandoc.Strong(words(L("Quality dashboard","Painel de qualidade")))})},pandoc.Attr("",{"need-dashboard-title"}))}
  for _,name in ipairs(names) do blocks[#blocks+1]=scope_blocks(graph,name,report.scopes[name]) end
  local findings=findings_blocks(report); if findings then blocks[#blocks+1]=findings end
  return blocks,nil
end
return M
