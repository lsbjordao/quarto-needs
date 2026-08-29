(() => {
  // Search-context and hierarchy interaction for the interactive Cytoscape
  // need graph. The base graph client owns rendering/search/popups; this module
  // augments it with semantic parent/child traversal, collapse/expand, and an
  // optional fixed-spacing layout for the currently visible nodes.
  if (!window.cytoscape || window.__quartoNeedsGraphContextInstalled) return;
  window.__quartoNeedsGraphContextInstalled = true;

  const registry = new WeakMap();
  const original = window.cytoscape;
  window.cytoscape = new Proxy(original, {
    apply(target, thisArg, args) {
      const cy = Reflect.apply(target, thisArg, args);
      const canvas = args && args[0] && args[0].container;
      if (canvas && typeof canvas === "object") registry.set(canvas, cy);
      return cy;
    },
  });

  const TYPE_LEVEL_MAP = {
    "stakeholder-need": 0, stakeholder: 0, "system-requirement": 1,
    "functional-requirement": 2, "non-functional-requirement": 2,
    "architecture-decision": 3, component: 4, interface: 5,
    risk: 6, threat: 6, "test-case": 7, evidence: 8,
  };
  const DOUBLE_TAP_MS = 360, DRAG_DISTANCE_PX = 6, DEFAULT_SPACING = 90;
  const MIN_SPACING = 50, MAX_SPACING = 240, SPACING_STEP = 10;
  const isPt = () => String(document.documentElement.lang || "").toLowerCase().startsWith("pt");

  function projectionFor(container) {
    const script = container.querySelector("[data-need-graph-data]");
    if (!script) return {};
    try { return JSON.parse(script.textContent || "{}"); } catch (_error) { return {}; }
  }
  function directRelatives(cy, semantics, nodeId, kind, allowedFamilies = null) {
    const ids = new Set();
    cy.edges().forEach((edge) => {
      const definition = semantics[String(edge.data("relation") || "")] || {};
      const family = String(definition.family || "");
      if (allowedFamilies && allowedFamilies.size && !allowedFamilies.has(family)) return;
      const direction = String(definition.traversalDirection || "none");
      if (direction === "none") return;
      const source = edge.source().id(), target = edge.target().id();
      if (direction === "source_to_target" || direction === "both") {
        if (kind === "parents" && target === nodeId) ids.add(source);
        if (kind === "children" && source === nodeId) ids.add(target);
      }
      if (direction === "target_to_source" || direction === "both") {
        if (kind === "parents" && source === nodeId) ids.add(target);
        if (kind === "children" && target === nodeId) ids.add(source);
      }
    });
    return ids;
  }
  function recursiveRelatives(cy, semantics, nodeId, kind, allowedFamilies = null) {
    const visited = new Set([nodeId]), result = new Set(); let frontier = [nodeId];
    while (frontier.length) {
      const next = [];
      frontier.forEach((current) => directRelatives(cy, semantics, current, kind, allowedFamilies).forEach((id) => {
        if (visited.has(id)) return; visited.add(id); result.add(id); next.push(id);
      }));
      frontier = next;
    }
    return result;
  }
  function makeToggle(kind, labelText, checked = true) {
    const label = document.createElement("label"); label.className = `need-graph-context-toggle need-graph-context-${kind}`;
    Object.assign(label.style, {display:"inline-flex",alignItems:"center",gap:".3rem",whiteSpace:"nowrap",fontSize:".9rem",cursor:"pointer"});
    const input = document.createElement("input"); input.type="checkbox"; input.checked=checked; input.dataset.needGraphContext=kind; input.setAttribute("aria-label",labelText);
    const text = document.createElement("span"); text.textContent=labelText; label.append(input,text); return {label,input};
  }
  function makeSpacingControl() {
    const wrapper=document.createElement("span"); wrapper.className="need-graph-spacing-control";
    Object.assign(wrapper.style,{display:"inline-flex",alignItems:"center",gap:".35rem",whiteSpace:"nowrap",fontSize:".9rem"});
    const toggle=makeToggle("fixed-spacing",isPt()?"Espaçamento fixo":"Fixed spacing",false);
    const range=document.createElement("input"); range.type="range"; range.min=String(MIN_SPACING); range.max=String(MAX_SPACING); range.step=String(SPACING_STEP); range.value=String(DEFAULT_SPACING); range.disabled=true; range.className="need-graph-spacing-range"; range.dataset.needGraphSpacing="true"; range.setAttribute("aria-label",isPt()?"Distância entre os nós":"Distance between nodes"); range.style.width="8rem";
    const value=document.createElement("output"); value.className="need-graph-spacing-value"; value.value=`${DEFAULT_SPACING} px`; value.textContent=`${DEFAULT_SPACING} px`; value.style.minWidth="3.6rem"; value.style.fontVariantNumeric="tabular-nums";
    wrapper.append(toggle.label,range,value); return {wrapper,toggle:toggle.input,range,value};
  }
  function levelForType(type){const n=String(type||"").toLowerCase().trim();return TYPE_LEVEL_MAP[n]!=null?TYPE_LEVEL_MAP[n]:1000;}

  function enhance(container) {
    if (!container || container.dataset.needGraphContextReady === "true") return true;
    const canvas=container.querySelector("[data-need-graph-canvas]"), controls=container.querySelector("[data-need-graph-controls]"), search=controls&&controls.querySelector(".need-graph-search"), status=container.querySelector("[data-need-graph-status]");
    if(!canvas||!controls||!search)return false; const cy=registry.get(canvas); if(!cy)return false; canvas.__quartoNeedsCy=cy;
    const projection=projectionFor(container), relationSemantics=projection.relationSemantics||{}; container.dataset.needGraphContextReady="true";
    const parents=makeToggle("parents",isPt()?"Pais":"Parents"), children=makeToggle("children",isPt()?"Filhos":"Children"), spacing=makeSpacingControl(), anchor=search.nextSibling;
    controls.insertBefore(parents.label,anchor); controls.insertBefore(children.label,anchor); controls.insertBefore(spacing.wrapper,anchor);
    let selectedNodeId=null,lastTap=null,dragGesture=null,suppressTapUntil=0; const collapsed=new Set();
    const announce=(m)=>{if(status)status.textContent=m;}, searchActive=()=>Boolean(String(search.value||"").trim());
    const traversalFamilies=()=>container.__needGraphTraversalFamilies instanceof Set?container.__needGraphTraversalFamilies:null;
    const nodeAllowed=(n)=>typeof container.__needGraphNodeAllowed!=="function"||container.__needGraphNodeAllowed(n);
    const edgeAllowed=(e)=>typeof container.__needGraphEdgeAllowed!=="function"||container.__needGraphEdgeAllowed(e);
    const collapseHiddenIds=()=>{const h=new Set();collapsed.forEach((id)=>recursiveRelatives(cy,relationSemantics,id,"children").forEach((x)=>h.add(x)));return h;};
    const applyEdges=()=>cy.edges().forEach((e)=>{const ok=e.source().style("display")!=="none"&&e.target().style("display")!=="none"&&edgeAllowed(e);e.style("display",ok?"element":"none");});
    const setVisible=(ids)=>{const h=collapseHiddenIds();cy.nodes().forEach((n)=>{const ok=(ids===null||ids.has(n.id()))&&nodeAllowed(n)&&!h.has(n.id());n.style("display",ok?"element":"none");});applyEdges();};
    const fitVisible=()=>{const shown=cy.elements().filter((e)=>e.visible());if(shown.length)cy.fit(shown,40);};
    const applyFixedSpacing=()=>{if(!spacing.toggle.checked)return;const distance=Number(spacing.range.value)||DEFAULT_SPACING,visible=cy.nodes().filter((n)=>n.visible());if(!visible.length)return;const levels=new Map();visible.forEach((n)=>{const l=levelForType(n.data("type"));if(!levels.has(l))levels.set(l,[]);levels.get(l).push(n);});const positions=new Map();[...levels.entries()].sort((a,b)=>a[0]-b[0]).forEach(([,nodes],row)=>{nodes.sort((a,b)=>a.id().localeCompare(b.id()));const count=nodes.length;nodes.forEach((n,col)=>positions.set(n.id(),{x:(col-(count-1)/2)*distance,y:row*distance}));});cy.layout({name:"preset",positions:(n)=>positions.get(n.id())||n.position(),fit:false,animate:false}).run();fitVisible();};
    const refreshLayout=()=>spacing.toggle.checked?applyFixedSpacing():fitVisible();
    const showContext=()=>{if(!selectedNodeId||!searchActive())return;const selected=cy.getElementById(selectedNodeId);if(!selected||!selected.length)return;const visible=new Set([selectedNodeId]),families=traversalFamilies();if(parents.input.checked)recursiveRelatives(cy,relationSemantics,selectedNodeId,"parents",families).forEach((id)=>visible.add(id));if(children.input.checked)recursiveRelatives(cy,relationSemantics,selectedNodeId,"children",families).forEach((id)=>visible.add(id));const hidden=collapseHiddenIds();hidden.delete(selectedNodeId);cy.nodes().forEach((n)=>n.style("display",visible.has(n.id())&&!hidden.has(n.id())&&nodeAllowed(n)?"element":"none"));applyEdges();refreshLayout();};
    const applyHierarchyView=()=>{if(searchActive()&&selectedNodeId)showContext();else if(!searchActive()){setVisible(null);refreshLayout();}else{cy.nodes().forEach((n)=>{if(n.style("display")!=="none"&&!nodeAllowed(n))n.style("display","none");});applyEdges();refreshLayout();}};
    container.__needGraphContextApi={refresh:applyHierarchyView,fit:refreshLayout,selectedNode:()=>selectedNodeId,recursiveRelatives:(id,kind)=>recursiveRelatives(cy,relationSemantics,id,kind,traversalFamilies())};
    const toggleCollapse=(id)=>{const d=recursiveRelatives(cy,relationSemantics,id,"children");if(!d.size)return;if(collapsed.has(id)){collapsed.delete(id);announce(isPt()?`Expandido ${id}`:`Expanded ${id}`);}else{collapsed.add(id);announce(isPt()?`Colapsado ${id}`:`Collapsed ${id}`);}applyHierarchyView();};
    search.addEventListener("input",()=>{selectedNodeId=null;lastTap=null;requestAnimationFrame(applyHierarchyView);});parents.input.addEventListener("change",showContext);children.input.addEventListener("change",showContext);
    spacing.toggle.addEventListener("change",()=>{spacing.range.disabled=!spacing.toggle.checked;if(spacing.toggle.checked){applyFixedSpacing();announce(isPt()?"Espaçamento fixo ativado":"Fixed spacing enabled");}else announce(isPt()?"Espaçamento fixo desativado":"Fixed spacing disabled");});
    spacing.range.addEventListener("input",()=>{const d=Number(spacing.range.value)||DEFAULT_SPACING;spacing.value.value=`${d} px`;spacing.value.textContent=`${d} px`;applyFixedSpacing();});
    cy.on("grab","node",(e)=>{const p=e.target.renderedPosition();dragGesture={id:e.target.id(),x:p.x,y:p.y,moved:false};});
    cy.on("drag","node",(e)=>{if(!dragGesture||dragGesture.id!==e.target.id())return;const p=e.target.renderedPosition();if(Math.hypot(p.x-dragGesture.x,p.y-dragGesture.y)>=DRAG_DISTANCE_PX)dragGesture.moved=true;});
    cy.on("free","node",(e)=>{if(dragGesture&&dragGesture.id===e.target.id()&&dragGesture.moved){suppressTapUntil=Date.now()+DOUBLE_TAP_MS;lastTap=null;}dragGesture=null;});
    cy.on("tap","node",(e)=>{const id=e.target.id(),now=Date.now();container.__needGraphFocusNode=id;container.dispatchEvent(new CustomEvent("quarto-needs-node-focus",{detail:{nodeId:id}}));if(searchActive()){selectedNodeId=id;showContext();}if(now<suppressTapUntil)return;if(lastTap&&lastTap.id===id&&now-lastTap.time<=DOUBLE_TAP_MS){lastTap=null;toggleCollapse(id);}else lastTap={id,time:now};});
    const reset=controls.querySelector(".need-graph-reset");if(reset)reset.addEventListener("click",()=>{selectedNodeId=null;container.__needGraphFocusNode=null;collapsed.clear();lastTap=null;parents.input.checked=true;children.input.checked=true;container.dispatchEvent(new CustomEvent("quarto-needs-context-reset"));if(spacing.toggle.checked)requestAnimationFrame(applyFixedSpacing);});
    return true;
  }
  function enhanceAll(){document.querySelectorAll("[data-need-graph]").forEach(enhance);}function schedule(){requestAnimationFrame(enhanceAll);setTimeout(enhanceAll,100);setTimeout(enhanceAll,500);}if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",schedule);else schedule();
})();
