(() => {
  if (window.__quartoNeedsGraphExploreInstalled) return;
  window.__quartoNeedsGraphExploreInstalled = true;

  const isPt = () => String(document.documentElement.lang || "").toLowerCase().startsWith("pt");
  const t = (en, pt) => isPt() ? pt : en;

  function projectionFor(container) {
    const script = container.querySelector("[data-need-graph-data]");
    if (!script) return {};
    try { return JSON.parse(script.textContent || "{}"); } catch (_error) { return {}; }
  }

  function unique(values) {
    return [...new Set(values.filter(Boolean).map(String))].sort((a, b) => a.localeCompare(b));
  }

  function makeSelect(kind, labelText, values, allLabel) {
    const label = document.createElement("label");
    label.className = `need-graph-explore-field need-graph-explore-${kind}`;
    Object.assign(label.style, {
      display: "inline-flex", alignItems: "center", gap: ".25rem",
      whiteSpace: "nowrap", fontSize: ".85rem",
    });
    const text = document.createElement("span");
    text.textContent = labelText;
    const select = document.createElement("select");
    select.dataset.needGraphExplore = kind;
    select.setAttribute("aria-label", labelText);
    const all = document.createElement("option");
    all.value = "";
    all.textContent = allLabel;
    select.appendChild(all);
    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    label.append(text, select);
    return { label, select };
  }

  function makeProfileSelect(profiles) {
    const names = Object.keys(profiles || {}).sort((a, b) => a.localeCompare(b));
    const field = makeSelect(
      "profile",
      t("Traversal", "Travessia"),
      names,
      t("all semantic", "toda semântica"),
    );
    if (names.includes("traceability")) field.select.value = "traceability";
    return field;
  }

  function familyFor(edge, semantics) {
    const definition = semantics[String(edge.data("relation") || "")] || {};
    return String(definition.family || "");
  }

  function directParents(cy, semantics, nodeId, allowedFamilies) {
    const result = [];
    cy.edges().forEach((edge) => {
      const relation = String(edge.data("relation") || "");
      const definition = semantics[relation] || {};
      const family = String(definition.family || "");
      if (allowedFamilies && !allowedFamilies.has(family)) return;
      const direction = String(definition.traversalDirection || "none");
      const source = edge.source().id();
      const target = edge.target().id();
      if ((direction === "source_to_target" || direction === "both") && target === nodeId) result.push(source);
      if ((direction === "target_to_source" || direction === "both") && source === nodeId) result.push(target);
    });
    return unique(result);
  }

  function edgeBetween(cy, semantics, childId, parentId, allowedFamilies) {
    let found = null;
    cy.edges().forEach((edge) => {
      if (found) return;
      const relation = String(edge.data("relation") || "");
      const definition = semantics[relation] || {};
      const family = String(definition.family || "");
      if (allowedFamilies && !allowedFamilies.has(family)) return;
      const direction = String(definition.traversalDirection || "none");
      const source = edge.source().id();
      const target = edge.target().id();
      if ((direction === "source_to_target" || direction === "both") && source === parentId && target === childId) found = edge;
      if ((direction === "target_to_source" || direction === "both") && target === parentId && source === childId) found = edge;
    });
    return found;
  }

  // Unlike directParents/edgeBetween, this ignores each relation's own
  // declared traversalDirection — a two-node connectivity question ("are
  // these connected at all") is answered over every edge in an allowed
  // family, traversable both ways, including "none"-direction relations
  // (e.g. references) that a parent-walk never follows.
  function neighbors(cy, semantics, nodeId, allowedFamilies) {
    const result = [];
    cy.edges().forEach((edge) => {
      const relation = String(edge.data("relation") || "");
      const definition = semantics[relation] || {};
      const family = String(definition.family || "");
      if (allowedFamilies && !allowedFamilies.has(family)) return;
      const source = edge.source().id();
      const target = edge.target().id();
      if (source === nodeId) result.push(target);
      else if (target === nodeId) result.push(source);
    });
    return result;
  }

  function undirectedEdgeBetween(cy, semantics, aId, bId, allowedFamilies) {
    let found = null;
    cy.edges().forEach((edge) => {
      if (found) return;
      const relation = String(edge.data("relation") || "");
      const definition = semantics[relation] || {};
      const family = String(definition.family || "");
      if (allowedFamilies && !allowedFamilies.has(family)) return;
      const source = edge.source().id();
      const target = edge.target().id();
      if ((source === aId && target === bId) || (source === bId && target === aId)) found = edge;
    });
    return found;
  }

  function shortestPath(cy, semantics, startId, endId, allowedFamilies) {
    if (startId === endId) return { nodes: [startId], edges: [] };
    const queue = [startId];
    const previous = new Map([[startId, null]]);
    let found = false;
    while (queue.length) {
      const current = queue.shift();
      if (current === endId) { found = true; break; }
      neighbors(cy, semantics, current, allowedFamilies).forEach((next) => {
        if (!previous.has(next)) {
          previous.set(next, current);
          queue.push(next);
        }
      });
    }
    if (!found) return null;
    const path = [endId];
    let cursor = endId;
    while (cursor !== startId) {
      cursor = previous.get(cursor);
      path.unshift(cursor);
    }
    const edgeIds = [];
    for (let i = 0; i < path.length - 1; i += 1) {
      const edge = undirectedEdgeBetween(cy, semantics, path[i], path[i + 1], allowedFamilies);
      if (edge) edgeIds.push(edge.id());
    }
    return { nodes: path, edges: edgeIds };
  }

  function pathToRoot(cy, semantics, startId, allowedFamilies) {
    const queue = [startId];
    const previous = new Map([[startId, null]]);
    let root = null;
    while (queue.length) {
      const current = queue.shift();
      const parents = directParents(cy, semantics, current, allowedFamilies);
      if (!parents.length) { root = current; break; }
      parents.forEach((parent) => {
        if (!previous.has(parent)) {
          previous.set(parent, current);
          queue.push(parent);
        }
      });
    }
    if (!root) return null;
    const rootToFocus = [root];
    let cursor = root;
    while (cursor !== startId) {
      const child = previous.get(cursor);
      if (!child) return null;
      rootToFocus.push(child);
      cursor = child;
    }
    const edgeIds = [];
    for (let i = 0; i < rootToFocus.length - 1; i += 1) {
      const parent = rootToFocus[i];
      const child = rootToFocus[i + 1];
      const edge = edgeBetween(cy, semantics, child, parent, allowedFamilies);
      if (edge) edgeIds.push(edge.id());
    }
    return { nodes: rootToFocus, edges: edgeIds, root };
  }

  function ensurePathStyle(cy) {
    cy.style()
      .selector("node.need-root-path-node")
      .style({ "border-width": 5, "border-color": "#7c3aed", "z-index": 20 })
      .selector("edge.need-root-path-edge")
      .style({ "line-color": "#7c3aed", "target-arrow-color": "#7c3aed", width: 4, "z-index": 20 })
      .update();
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function edgePopup(projection, edge, semantics, profileName, familyFilter) {
    const index = Number(String(edge.id()).replace(/^e/, ""));
    const raw = Number.isInteger(index) ? (projection.edges || [])[index] || {} : {};
    const relation = String(edge.data("relation") || raw.relation || "");
    const definition = semantics[relation] || {};
    const source = edge.source().id();
    const target = edge.target().id();
    const direction = String(definition.traversalDirection || "none");
    let semanticDirection = t("not traversed", "não percorrida");
    if (direction === "source_to_target") semanticDirection = `${source} → ${target}`;
    else if (direction === "target_to_source") semanticDirection = `${target} → ${source}`;
    else if (direction === "both") semanticDirection = `${source} ↔ ${target}`;

    const row = (label, value) => value == null || value === "" ? "" :
      `<div class="need-graph-popup-row"><span class="need-graph-popup-label">${escapeHtml(label)}</span>` +
      `<code class="need-graph-popup-value">${escapeHtml(value)}</code></div>`;
    const provenance = Array.isArray(raw.provenance) ? raw.provenance : [];
    const declared = provenance.map((item) => {
      const where = `${item.file || ""}:${item.line || ""}${item.anchor ? ` #${item.anchor}` : ""}`;
      return row(t("Declared at", "Declarada em"), where);
    }).join("");

    const popup = document.createElement("div");
    popup.className = "need-graph-popup need-graph-edge-popup";
    popup.setAttribute("role", "dialog");
    popup.innerHTML =
      `<div class="need-graph-popup-head"><div class="need-graph-popup-title">${escapeHtml(source)} → ${escapeHtml(target)}</div>` +
      `<button type="button" class="need-graph-popup-close" aria-label="${t("Close details", "Fechar detalhes")}">×</button></div>` +
      `<div class="need-graph-popup-body">` +
      row(t("Relation", "Relação"), relation) +
      row(t("Family", "Família"), definition.family || "") +
      row(t("Semantic direction", "Direção semântica"), semanticDirection) +
      row(t("Source role", "Papel da origem"), definition.sourceRole || "") +
      row(t("Target role", "Papel do destino"), definition.targetRole || "") +
      row(t("Impact", "Impacto"), definition.impactDirection || "") +
      row(t("Traversal profile", "Perfil de travessia"), profileName || t("all semantic", "toda semântica")) +
      row(t("Family filter", "Filtro de família"), familyFilter || t("all", "todas")) +
      declared + `</div>`;
    return popup;
  }

  function positionPopup(canvas, popup, event) {
    const at = event && event.renderedPosition ? event.renderedPosition : { x: 80, y: 80 };
    const padding = 8;
    const rect = canvas.getBoundingClientRect();
    const width = popup.offsetWidth || 260;
    const height = popup.offsetHeight || 220;
    popup.style.left = Math.max(padding, Math.min(at.x, rect.width - width - padding)) + "px";
    popup.style.top = Math.max(padding, Math.min(at.y, rect.height - height - padding)) + "px";
  }

  function enhance(container) {
    if (!container || container.dataset.needGraphExploreReady === "true") return true;
    const canvas = container.querySelector("[data-need-graph-canvas]");
    const controls = container.querySelector("[data-need-graph-controls]");
    const search = controls && controls.querySelector(".need-graph-search");
    const status = container.querySelector("[data-need-graph-status]");
    const contextApi = container.__needGraphContextApi;
    const cy = canvas && canvas.__quartoNeedsCy;
    if (!canvas || !controls || !search || !contextApi || !cy) return false;

    const projection = projectionFor(container);
    const semantics = projection.relationSemantics || {};
    const profiles = projection.traversalProfiles || {};
    const types = unique((projection.nodes || []).map((node) => node.type));
    const statuses = unique((projection.nodes || []).map((node) => node.status));
    const families = unique((projection.edges || []).map((edge) => {
      const definition = semantics[String(edge.relation || "")] || {};
      return definition.family || "";
    }));

    container.dataset.needGraphExploreReady = "true";
    ensurePathStyle(cy);

    const wrapper = document.createElement("span");
    wrapper.className = "need-graph-explore-controls";
    Object.assign(wrapper.style, {
      display: "inline-flex", flexWrap: "wrap", alignItems: "center",
      gap: ".4rem", width: "100%", marginTop: ".25rem",
    });
    const typeField = makeSelect("type", t("Type", "Tipo"), types, t("all", "todos"));
    const statusField = makeSelect("status", "Status", statuses, t("all", "todos"));
    const familyField = makeSelect("family", t("Family", "Família"), families, t("all", "todas"));
    const profileField = makeProfileSelect(profiles);
    const pathButton = document.createElement("button");
    pathButton.type = "button";
    pathButton.className = "need-graph-root-path";
    pathButton.textContent = t("Path to root", "Caminho até a raiz");
    pathButton.disabled = true;
    const betweenButton = document.createElement("button");
    betweenButton.type = "button";
    betweenButton.className = "need-graph-shortest-path";
    betweenButton.textContent = t("Path between…", "Caminho entre…");
    betweenButton.disabled = true;
    wrapper.append(typeField.label, statusField.label, familyField.label, profileField.label, pathButton, betweenButton);
    controls.appendChild(wrapper);

    const breadcrumbs = document.createElement("nav");
    breadcrumbs.className = "need-graph-breadcrumbs";
    breadcrumbs.setAttribute("aria-label", t("Path trail", "Trilha do caminho"));
    breadcrumbs.hidden = true;
    controls.appendChild(breadcrumbs);

    let pathNodes = new Set();
    let pathEdges = new Set();
    let pathActive = false;
    let activePathKind = null;
    let pickingSecondEndpoint = null;

    const announce = (message) => { if (status) status.textContent = message; };

    // Renders the exact result.nodes array already stored on
    // __needGraphActivePath as a clickable trail — never a second, separately
    // maintained copy of path data. Clicking an entry re-focuses that node
    // through the same shared event a canvas tap already dispatches.
    function renderBreadcrumbs(nodes) {
      breadcrumbs.innerHTML = "";
      if (!nodes || !nodes.length) { breadcrumbs.hidden = true; return; }
      nodes.forEach((id, index) => {
        if (index > 0) {
          const sep = document.createElement("span");
          sep.className = "need-graph-breadcrumb-sep";
          sep.setAttribute("aria-hidden", "true");
          sep.textContent = "→";
          breadcrumbs.appendChild(sep);
        }
        const item = document.createElement("button");
        item.type = "button";
        item.className = "need-graph-breadcrumb";
        item.textContent = id;
        item.addEventListener("click", () => {
          container.__needGraphFocusNode = id;
          container.dispatchEvent(new CustomEvent("quarto-needs-node-focus", { detail: { nodeId: id } }));
        });
        breadcrumbs.appendChild(item);
      });
      breadcrumbs.hidden = false;
    }
    const activeProfileFamilies = () => {
      const name = profileField.select.value;
      const raw = name ? profiles[name] : null;
      const set = raw ? new Set(raw.map(String)) : null;
      const family = familyField.select.value;
      if (family) {
        if (set) return new Set([...set].filter((value) => value === family));
        return new Set([family]);
      }
      return set;
    };
    const familyIncidentNodes = () => {
      const family = familyField.select.value;
      if (!family) return null;
      const ids = new Set();
      cy.edges().forEach((edge) => {
        if (familyFor(edge, semantics) === family) {
          ids.add(edge.source().id());
          ids.add(edge.target().id());
        }
      });
      return ids;
    };

    const installPredicates = () => {
      const type = typeField.select.value;
      const statusValue = statusField.select.value;
      const family = familyField.select.value;
      const incident = familyIncidentNodes();
      const overlayForced = container.__needGraphOverlayForcedNodes;
      const forced = overlayForced instanceof Set && overlayForced.size
        ? new Set([...pathNodes, ...overlayForced])
        : pathNodes;
      const affectedOnly = container.__needGraphAffectedOnly;
      container.__needGraphForcedNodes = forced;
      container.__needGraphTraversalFamilies = activeProfileFamilies();
      container.__needGraphNodeAllowed = (node) => {
        if (forced.has(node.id())) return true;
        if (affectedOnly && !affectedOnly.has(node.id())) return false;
        if (type && String(node.data("type") || "") !== type) return false;
        if (statusValue && String(node.data("status") || "") !== statusValue) return false;
        if (incident && !incident.has(node.id())) return false;
        return true;
      };
      container.__needGraphEdgeAllowed = (edge) => {
        if (pathEdges.has(edge.id())) return true;
        return !family || familyFor(edge, semantics) === family;
      };
    };

    // The modes client flips its slots and asks this module — the predicate
    // owner — to re-derive them, so forced/affected state can never diverge
    // from the filters composed here.
    container.__needGraphReapplyPredicates = () => { installPredicates(); };

    const refresh = () => {
      installPredicates();
      if (contextApi.selectedNode()) contextApi.refresh();
      else if (String(search.value || "").trim()) search.dispatchEvent(new Event("input", { bubbles: true }));
      else contextApi.refresh();
    };

    const clearPath = () => {
      pathNodes = new Set();
      pathEdges = new Set();
      pathActive = false;
      activePathKind = null;
      pickingSecondEndpoint = null;
      container.__needGraphActivePath = null;
      container.__needGraphForcedNodes = pathNodes;
      cy.elements().removeClass("need-root-path-node need-root-path-edge");
      pathButton.textContent = t("Path to root", "Caminho até a raiz");
      betweenButton.textContent = t("Path between…", "Caminho entre…");
      renderBreadcrumbs(null);
      installPredicates();
    };

    [typeField.select, statusField.select, familyField.select, profileField.select].forEach((select) => {
      select.addEventListener("change", () => {
        clearPath();
        refresh();
        announce(t("Graph filters updated", "Filtros do grafo atualizados"));
      });
    });

    container.addEventListener("quarto-needs-node-focus", (event) => {
      const nodeId = event.detail && event.detail.nodeId;
      // A focus change is normally the "clear any active path" signal — but
      // while picking the second endpoint for a between-path, this same
      // event IS the second pick, and must not be swallowed by that clear.
      if (pickingSecondEndpoint) {
        const startId = pickingSecondEndpoint;
        pickingSecondEndpoint = null;
        if (!nodeId) {
          betweenButton.textContent = t("Path between…", "Caminho entre…");
          pathButton.disabled = true;
          betweenButton.disabled = true;
          return;
        }
        const result = shortestPath(cy, semantics, startId, nodeId, activeProfileFamilies());
        if (!result) {
          betweenButton.textContent = t("Path between…", "Caminho entre…");
          announce(t("No semantic path was found between the two objects", "Nenhum caminho semântico foi encontrado entre os dois objetos"));
          pathButton.disabled = false;
          betweenButton.disabled = false;
          return;
        }
        pathNodes = new Set(result.nodes);
        pathEdges = new Set(result.edges);
        pathActive = true;
        activePathKind = "between";
        container.__needGraphActivePath = { kind: "between", nodes: result.nodes };
        renderBreadcrumbs(result.nodes);
        installPredicates();
        contextApi.refresh();
        result.nodes.forEach((id) => cy.getElementById(id).addClass("need-root-path-node"));
        result.edges.forEach((id) => cy.getElementById(id).addClass("need-root-path-edge"));
        betweenButton.textContent = t("Clear path", "Remover caminho");
        pathButton.disabled = false;
        betweenButton.disabled = false;
        announce(`${result.nodes.length - 1} ${t("hops", "saltos")}`);
        return;
      }
      // Re-focusing a node already on the shown trail (a breadcrumb click, or
      // re-tapping a highlighted node on canvas) is just moving attention
      // within the same path — it must not trigger the ordinary "any focus
      // change clears the active path" rule below.
      if (pathActive && nodeId && pathNodes.has(nodeId)) {
        pathButton.disabled = !nodeId;
        betweenButton.disabled = !nodeId;
        return;
      }
      clearPath();
      pathButton.disabled = !nodeId;
      betweenButton.disabled = !nodeId;
    });

    pathButton.addEventListener("click", () => {
      const focus = container.__needGraphFocusNode;
      if (!focus) return;
      if (activePathKind === "root") {
        clearPath();
        refresh();
        announce(t("Root path cleared", "Caminho até a raiz removido"));
        return;
      }
      clearPath();
      const result = pathToRoot(cy, semantics, focus, activeProfileFamilies());
      if (!result) {
        announce(t("No semantic path to a root was found", "Nenhum caminho semântico até uma raiz foi encontrado"));
        return;
      }
      pathNodes = new Set(result.nodes);
      pathEdges = new Set(result.edges);
      pathActive = true;
      activePathKind = "root";
      container.__needGraphActivePath = { kind: "root", nodes: result.nodes };
      renderBreadcrumbs(result.nodes);
      installPredicates();
      contextApi.refresh();
      result.nodes.forEach((id) => cy.getElementById(id).addClass("need-root-path-node"));
      result.edges.forEach((id) => cy.getElementById(id).addClass("need-root-path-edge"));
      pathButton.textContent = t("Clear root path", "Remover caminho");
      announce(`${t("Root", "Raiz")}: ${result.root} · ${result.nodes.length - 1} ${t("hops", "saltos")}`);
    });

    betweenButton.addEventListener("click", () => {
      if (pickingSecondEndpoint) {
        pickingSecondEndpoint = null;
        betweenButton.textContent = t("Path between…", "Caminho entre…");
        announce(t("Path selection cancelled", "Seleção de caminho cancelada"));
        return;
      }
      if (activePathKind === "between") {
        clearPath();
        refresh();
        announce(t("Path cleared", "Caminho removido"));
        return;
      }
      const focus = container.__needGraphFocusNode;
      if (!focus) return;
      clearPath();
      pickingSecondEndpoint = focus;
      betweenButton.textContent = t("Select the second object…", "Selecione o segundo objeto…");
      announce(t("Select the second object to find the path", "Selecione o segundo objeto para encontrar o caminho"));
    });

    cy.on("tap", "edge", (event) => {
      canvas.querySelectorAll(".need-graph-popup").forEach((popup) => popup.remove());
      const popup = edgePopup(
        projection,
        event.target,
        semantics,
        profileField.select.value,
        familyField.select.value,
      );
      canvas.appendChild(popup);
      positionPopup(canvas, popup, event);
      const close = popup.querySelector(".need-graph-popup-close");
      if (close) close.addEventListener("click", (e) => { e.stopPropagation(); popup.remove(); });
      announce(`${t("Selected relation", "Relação selecionada")} ${event.target.data("relation")}`);
    });

    container.addEventListener("quarto-needs-context-reset", () => {
      typeField.select.value = "";
      statusField.select.value = "";
      familyField.select.value = "";
      profileField.select.value = Object.prototype.hasOwnProperty.call(profiles, "traceability") ? "traceability" : "";
      pathButton.disabled = true;
      betweenButton.disabled = true;
      clearPath();
      requestAnimationFrame(refresh);
    });

    installPredicates();
    requestAnimationFrame(refresh);
    return true;
  }

  function enhanceAll() {
    document.querySelectorAll("[data-need-graph]").forEach(enhance);
  }
  function schedule() {
    requestAnimationFrame(enhanceAll);
    setTimeout(enhanceAll, 150);
    setTimeout(enhanceAll, 600);
    setTimeout(enhanceAll, 1200);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule);
  else schedule();
})();
