local function script_dir()
  local source=debug.getinfo(1,"S").source; if source:sub(1,1)=="@" then source=source:sub(2) end; return source:match("(.*/)") or ""
end
local views=dofile(script_dir().."views.lua")
local flow=dofile(script_dir().."flow.lua")
local relations=dofile(script_dir().."relations.lua")
local inspector=dofile(script_dir().."inspector.lua")
local dashboard=dofile(script_dir().."dashboard.lua")
local graph=dofile(script_dir().."graph.lua")
local c4=dofile(script_dir().."c4.lua")
local tags=dofile(script_dir().."tags.lua")
local function L(en,pt) return views.tr(en,pt) end
local function graph_or_warning() views.ensure_assets(); local graph_data,message=views.load(); if not graph_data then return nil,views.warning(message) end; return graph_data end
local function project_dir() local ok,directory=pcall(function() return quarto.project.directory end); if ok and type(directory)=="string" and directory~="" then return directory end; local input=PANDOC_STATE.input_files and PANDOC_STATE.input_files[1]; return input and input:match("(.*/)") or "." end
local function graph_view_projection(name)
  if name=="" then return nil,nil end
  local path=pandoc.path.join({project_dir(),".quarto-needs","graphs","views.json"}); local file=io.open(path,"rb"); if not file then return nil,L("Graph view manifest not found: ","Manifesto de visões do grafo não encontrado: ")..path end
  local raw=file:read("*a"); file:close(); local ok,payload=pcall(pandoc.json.decode,raw); if not ok or type(payload)~="table" or type(payload.queries)~="table" then return nil,L("Graph view manifest is invalid.","O manifesto de visões do grafo é inválido.") end
  local projection=payload.queries[name]; if projection then return pandoc.utils.stringify(projection),nil end
  local unavailable=type(payload.unavailable)=="table" and payload.unavailable[name] or nil; if unavailable then return nil,L("Graph view unavailable: ","Visão de grafo indisponível: ")..pandoc.utils.stringify(unavailable) end
  return nil,L("Unknown graph view/query: ","Visão/consulta de grafo desconhecida: ")..name
end
local function render_need_graph(args,kwargs)
  local query=views.kwarg(kwargs,"query"); local named_view=views.kwarg(kwargs,"view"); if query~="" and named_view~="" and query~=named_view then return views.warning(L("need-graph query and view disagree.","query e view de need-graph são diferentes.")) end
  local requested=query~="" and query or named_view
  if requested=="" then return graph.render_shortcode(args,kwargs) end
  local projection,message=graph_view_projection(requested); if not projection then quarto.log.warning(message); return views.warning(message) end
  local effective={}; for key,value in pairs(kwargs or {}) do effective[key]=value end; effective.projection=projection; effective.query=nil; effective.view=nil
  return graph.render_shortcode(args,effective)
end
local function render_need_c4(args,kwargs) return c4.render_shortcode(args,kwargs) end
local function object_cell(graph_data,object,column)
  if column=="id" then return {views.link(object)} end
  if column=="title" then return {pandoc.Str(pandoc.utils.stringify(object.title))} end
  if column=="status" or column=="priority" then local value=column=="status" and object.status or (object.attributes or {}).priority; return views.badge(column,value) end
  if column=="type" then return views.badge("type", object.type) end
  local targets=views.related(graph_data,pandoc.utils.stringify(object.id),column)
  if #targets>0 then local objects=views.objects_by_id(graph_data.objects); local inlines={}; for i,target in ipairs(targets) do if i>1 then inlines[#inlines+1]=pandoc.Str(", ") end; local related=objects[pandoc.utils.stringify(target)]; if related then inlines[#inlines+1]=views.link(related) else inlines[#inlines+1]=pandoc.Str(pandoc.utils.stringify(target)) end end; return inlines end
  return {pandoc.Str(pandoc.utils.stringify((object.attributes or {})[column] or ""))}
end
local function select_objects(graph_data,kwargs) local objects,message=views.select(graph_data,graph_data.objects,kwargs); if message then quarto.log.warning(message); return nil,views.warning(message) end; return views.sort(objects,kwargs),nil end
local function render_need_table(args,kwargs)
  local graph_data,warning=graph_or_warning(); if not graph_data then return warning end; local objects,w=select_objects(graph_data,kwargs); if w then return w end; if #objects==0 then return views.empty(L("No needs match this query.","Nenhum objeto corresponde a esta consulta.")) end
  local columns,headers={},{}; for column in views.kwarg(kwargs,"columns","id;title;type;status;priority"):gmatch("[^,;]+") do column=column:match("^%s*(.-)%s*$"); columns[#columns+1]=column; local label=column:gsub("%-"," "); local common={id=L("ID","ID"),title=L("title","título"),type=L("type","tipo"),status=L("status","status"),priority=L("priority","prioridade")}; headers[#headers+1]={pandoc.Str(common[column] or label)} end
  local rows={}; for _,object in ipairs(objects) do local row={}; for _,column in ipairs(columns) do row[#row+1]=object_cell(graph_data,object,column) end; rows[#rows+1]=row end
  local table_id=views.reserve_view_id("need-table",views.kwarg(kwargs,"id")); local table_block=views.table(views.kwarg(kwargs,"caption"),headers,rows,pandoc.Attr(table_id,{"need-table"})); return pandoc.Div({table_block},pandoc.Attr("",{"need-table-container"},{["data-need-table"]="true"}))
end
local function render_need_list(args,kwargs)
  local graph_data,warning=graph_or_warning(); if not graph_data then return warning end; local objects,w=select_objects(graph_data,kwargs); if w then return w end; if #objects==0 then return views.empty(L("No needs match this query.","Nenhum objeto corresponde a esta consulta.")) end
  local show={}; for field in views.kwarg(kwargs,"show"):gmatch("[^,;]+") do show[#show+1]=field:match("^%s*(.-)%s*$") end; local entries={}
  for _,object in ipairs(objects) do local inlines={views.link(object),pandoc.Str(" — "),pandoc.Str(pandoc.utils.stringify(object.title))}; for _,field in ipairs(show) do inlines[#inlines+1]=pandoc.Space(); local value=field=="status" and object.status or (object.attributes or {})[field]; for _,badge in ipairs(views.badge(field,value)) do inlines[#inlines+1]=badge end end; entries[#entries+1]={pandoc.Plain(inlines)} end; return pandoc.BulletList(entries)
end
local function render_need_count(args,kwargs) local graph_data,warning=graph_or_warning(); if not graph_data then return warning end; local objects,w=select_objects(graph_data,kwargs); if w then return w end; local count=#objects; return pandoc.Span({pandoc.Str(tostring(count))},pandoc.Attr("",{"need-count"},{["data-need-count"]=tostring(count)})) end
local function render_need_matrix(args,kwargs)
  local graph_data,warning=graph_or_warning(); if not graph_data then return warning end; local pool,message=views.select(graph_data,graph_data.objects,{query=views.kwarg(kwargs,"query")}); if message then return views.warning(message) end
  local rows=views.sort(views.filter(pool,{types=views.kwarg(kwargs,"rows")}),{}); local columns=views.sort(views.filter(pool,{types=views.kwarg(kwargs,"columns")}),{}); if #rows==0 or #columns==0 then return views.empty(L("No needs match this matrix query.","Nenhum objeto corresponde a esta consulta de matriz.")) end
  local relation_type=views.kwarg(kwargs,"relation","verified-by"); local index={}; for _,relation in ipairs(graph_data.relations or {}) do if pandoc.utils.stringify(relation.type)==relation_type then index[pandoc.utils.stringify(relation.source).."\0"..pandoc.utils.stringify(relation.target)]=true end end
  local headers={{pandoc.Str(L("Need","Objeto"))}}; for _,object in ipairs(columns) do headers[#headers+1]={views.link(object)} end; local matrix_rows={}; for _,row_object in ipairs(rows) do local cells={{views.link(row_object)}}; for _,column_object in ipairs(columns) do local key=pandoc.utils.stringify(row_object.id).."\0"..pandoc.utils.stringify(column_object.id); if index[key] then cells[#cells+1]={views.link(column_object,"✓")} else cells[#cells+1]={pandoc.Str("—")} end end; matrix_rows[#matrix_rows+1]=cells end
  local matrix_id=views.reserve_view_id("need-matrix",views.kwarg(kwargs,"id")); return views.table(L("Traceability: ","Rastreabilidade: ")..relation_type,headers,matrix_rows,pandoc.Attr(matrix_id,{"need-matrix"}))
end
local function render_need_backlinks(args,kwargs) local id=pandoc.utils.stringify(args[1] or ""); if id=="" then return views.warning(L("Missing need ID for need-backlinks.","ID ausente para need-backlinks.")) end; local graph_data,warning=graph_or_warning(); if not graph_data then return warning end; if not views.get(graph_data,id) then return views.warning(L("Unknown need ID: ","ID desconhecido: ")..id) end; return relations.render_backlinks(graph_data,id) end
local function render_need_inspector(args,kwargs) local id=pandoc.utils.stringify(args[1] or ""); if id=="" then return views.warning(L("Missing need ID for need-inspector.","ID ausente para need-inspector.")) end; local graph_data,warning=graph_or_warning(); if not graph_data then return warning end; local block=inspector.render(graph_data,id,kwargs); if not block then return views.warning(L("Unknown need ID: ","ID desconhecido: ")..id) end; return block end
local function render_need_flow(args,kwargs)
  local graph_data,warning=graph_or_warning(); if not graph_data then return warning end; local plan,plan_error=flow.build(graph_data,kwargs,views); if not plan then return views.warning(plan_error) end; if plan.node_count==0 then return views.empty(L("No needs match this flow query.","Nenhum objeto corresponde a esta consulta de fluxo.")) end
  local blocks={}; for _,message in ipairs(plan.warnings) do blocks[#blocks+1]=pandoc.Div({pandoc.Para({pandoc.Str(message)})},pandoc.Attr("",{"need-view-warning"},{role="status"})) end
  local description=L("Traceability flow with ","Fluxo de rastreabilidade com ")..tostring(plan.node_count)..L(" needs"," objetos")
  if views.is_html_format() then local svg=views.mermaid_inline_svg(plan.source,description,"need-flow"); if svg then blocks[#blocks+1]=pandoc.Div({pandoc.RawBlock("html",svg)},pandoc.Attr("",{"need-flow-scroll"})); return pandoc.Div(blocks) end end
  local image_name,render_error=views.render_mermaid_asset(plan.source,"quarto-needs-flow"); if not image_name then quarto.log.warning(render_error or "flow render failed"); return views.warning(L("Could not render this need-flow diagram.","Não foi possível renderizar este diagrama de fluxo.")) end
  local image=pandoc.Image({pandoc.Str(description)},image_name,"",pandoc.Attr("",{"need-flow"},{role="img"})); blocks[#blocks+1]=pandoc.Div({pandoc.Para({image})},pandoc.Attr("",{"need-flow-scroll"})); return pandoc.Div(blocks)
end
local function render_need_dashboard(args,kwargs) local graph_data,warning=graph_or_warning(); if not graph_data then return warning end; local blocks,message=dashboard.render(graph_data,kwargs); if not blocks then if message then return views.warning(message) end; return views.empty(L("Dashboard report unavailable.","Relatório do painel indisponível.")) end; local id=views.reserve_view_id("need-dashboard",views.kwarg(kwargs,"id")); return pandoc.Div(blocks,pandoc.Attr(id,{"need-dashboard"},{role="region"})) end
-- Every handler first parks the document meta where this engine's views.lua
-- can reach it: that is how `quarto-needs: tags-page:` gets from _quarto.yml
-- to badge rendering at shortcode time. Filter-side rendering (the need
-- cards) resolves the same value lazily off PANDOC_DOCUMENT instead — pandoc
-- gives each filter its own Lua state and quarto walks filter bodies before
-- Meta handlers, so nothing parked from here could reach them in time.
local handlers={
  need=function(args,kwargs,meta) local id=pandoc.utils.stringify(args[1] or ""); if id=="" then return pandoc.Str(L("[missing need id]","[id ausente]")) end; local graph_data,message=views.load(); if not graph_data then return pandoc.Span({pandoc.Str(id)},pandoc.Attr("",{"need-ref","need-ref-missing"})) end; local object=views.get(graph_data,id); if not object then return pandoc.Span({pandoc.Str(id)},pandoc.Attr("",{"need-ref","need-ref-missing"})) end; local label=id; if kwargs and kwargs["title"] and pandoc.utils.stringify(kwargs["title"])=="true" then label=id.." — "..pandoc.utils.stringify(object.title) end; return views.link(object,label) end,
  ["need-table"]=render_need_table,["need-list"]=render_need_list,["need-count"]=render_need_count,["need-matrix"]=render_need_matrix,["need-backlinks"]=render_need_backlinks,["need-inspector"]=render_need_inspector,["need-flow"]=render_need_flow,["need-dashboard"]=render_need_dashboard,["need-graph"]=render_need_graph,["need-c4"]=render_need_c4,["need-tags"]=function(args,kwargs) return tags.render_shortcode(args,kwargs) end,
}
local M={}
for name,render in pairs(handlers) do
  M[name]=function(args,kwargs,meta) views.note_shortcode_meta(meta); return render(args,kwargs,meta) end
end
return M
