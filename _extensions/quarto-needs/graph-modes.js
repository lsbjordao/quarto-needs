(() => {
  if (window.__quartoNeedsGraphModesInstalled) return;
  window.__quartoNeedsGraphModesInstalled = true;

  const isPt = () => String(document.documentElement.lang || "").toLowerCase().startsWith("pt");
  const t = (en, pt) => isPt() ? pt : en;

  function overlaysFor(container) {
    const script = container.querySelector("[data-need-graph-overlays]");
    if (!script) return null;
    try {
      const decoded = JSON.parse(script.textContent || "null");
      if (!decoded || decoded.schemaVersion !== "need-graph-overlays-v1") return null;
      return decoded;
    } catch (_error) {
      return null;
    }
  }

  // A ghost's cy id is its published id whenever that is free — a removed
  // object cannot collide with a live node — so labels and edge endpoints
  // stay readable. Only an unexpected collision falls back to a prefix.
  function ghostNodeId(cy, id, taken) {
    const original = String(id);
    if (!cy.getElementById(original).length && !taken.has(original)) return original;
    return "overlay-n-" + original;
  }

  function makeModeSelect() {
    const label = document.createElement("label");
    label.className = "need-graph-modes-field";
    Object.assign(label.style, {
      display: "inline-flex", alignItems: "center", gap: ".25rem",
      whiteSpace: "nowrap", fontSize: ".85rem",
    });
    const text = document.createElement("span");
    text.textContent = t("Mode", "Modo");
    const select = document.createElement("select");
    select.dataset.needGraphModes = "mode";
    select.setAttribute("aria-label", text.textContent);
    [["", t("Catalog", "Catálogo")], ["changes", t("Changes", "Mudanças")], ["impact", "Impact"]]
      .forEach(([value, textContent]) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = textContent;
        select.appendChild(option);
      });
    label.append(text, select);
    return { label, select };
  }

  function makeAffectedToggle() {
    const label = document.createElement("label");
    label.className = "need-graph-affected-field";
    Object.assign(label.style, {
      display: "inline-flex", alignItems: "center", gap: ".25rem",
      whiteSpace: "nowrap", fontSize: ".85rem",
    });
    const input = document.createElement("input");
    input.type = "checkbox";
    input.dataset.needGraphModes = "affected";
    input.disabled = true;
    const text = document.createElement("span");
    text.textContent = t("Affected only", "Somente afetados");
    label.append(input, text);
    return { label, input };
  }

  function enhance(container) {
    if (!container || container.dataset.needGraphModesReady === "true") return true;
    const canvas = container.querySelector("[data-need-graph-canvas]");
    const controls = container.querySelector("[data-need-graph-controls]");
    const status = container.querySelector("[data-need-graph-status]");
    const contextApi = container.__needGraphContextApi;
    const reapplyPredicates = container.__needGraphReapplyPredicates;
    const cy = canvas && canvas.__quartoNeedsCy;
    const overlays = overlaysFor(container);
    if (!canvas || !controls || !status || !contextApi || !reapplyPredicates || !cy || !overlays) return false;

    container.dataset.needGraphModesReady = "true";

    const colorSelect = controls.querySelector(".need-graph-color");
    const diff = overlays.diff || {};
    const impact = overlays.impact || {};

    const recolour = () => {
      if (colorSelect) colorSelect.dispatchEvent(new Event("change"));
    };
    const syncSlots = () => { reapplyPredicates(); contextApi.refresh(); };
    const announce = (message) => { if (status) status.textContent = message; };

    // Everything one mode application touches, so leaving a mode restores
    // exactly what it changed — no more, no less.
    const touched = { changes: new Set(), edges: [], pathEdges: [], impacts: [], ghosts: new Set(), ghostEdgeIds: new Set() };
    let ghostEdgeSequence = 0;

    function resetChangeData() {
      cy.batch(() => {
        touched.changes.forEach((id) => {
          const node = cy.getElementById(id);
          if (node.length) node.data("change", "unchanged");
        });
        touched.edges.forEach((id) => {
          const edge = cy.getElementById(id);
          if (edge.length) edge.data("change", "unchanged");
        });
        touched.pathEdges.forEach((id) => {
          const edge = cy.getElementById(id);
          if (edge.length) edge.data("pathMember", false);
        });
        touched.impacts.forEach((id) => {
          const node = cy.getElementById(id);
          if (!node.length) return;
          node.removeData("impactDistance");
          node.removeData("impactOrigin");
          node.removeClass("need-impact-origin");
        });
        touched.ghosts.forEach((id) => {
          const element = cy.getElementById(id);
          if (element.length) element.remove();
        });
      });
      touched.changes.clear();
      touched.edges.length = 0;
      touched.pathEdges.length = 0;
      touched.impacts.length = 0;
      touched.ghosts.clear();
      touched.ghostEdgeIds.clear();
      container.__needGraphOverlayForcedNodes = null;
      container.__needGraphAffectedOnly = null;
      if (affected.input) affected.input.checked = false;
      recolour();
    }

    function addGhosts(ghostNodes, ghostEdges) {
      const taken = new Set();
      const ghostIds = new Set();
      const idFor = (original) => {
        const actual = ghostNodeId(cy, original, taken);
        taken.add(actual);
        return actual;
      };
      cy.batch(() => {
        (ghostNodes || []).forEach((ghost) => {
          const id = idFor(ghost.id);
          if (cy.getElementById(id).length) return;
          cy.add({
            group: "nodes",
            data: {
              id, title: ghost.title || ghost.id, type: ghost.type || "",
              status: ghost.status || "", priority: ghost.priority || "",
              tags: ghost.tags || [], href: ghost.href || "#" + String(ghost.id),
              change: "removed",
            },
          });
          touched.ghosts.add(id);
          ghostIds.add(id);
        });
        (ghostEdges || []).forEach((edge) => {
          const source = idFor(edge.source);
          const target = idFor(edge.target);
          const id = "overlay-edge-" + String(ghostEdgeSequence++);
          if (cy.getElementById(id).length) return;
          if (!cy.getElementById(source).length || !cy.getElementById(target).length) return;
          cy.add({
            group: "edges",
            data: {
              id, source, target, label: edge.label || edge.relation || "",
              relation: edge.relation || "", change: "removed", pathMember: false,
            },
          });
          touched.ghosts.add(id);
          ghostIds.add(id);
        });
      });
      return ghostIds;
    }

    function findEdge(source, relation, target) {
      let found = null;
      cy.edges().forEach((edge) => {
        if (found) return;
        if (edge.data("relation") !== relation) return;
        if (edge.source().id() === source && edge.target().id() === target) found = edge;
        else if (edge.source().id() === target && edge.target().id() === source) found = edge;
      });
      return found;
    }

    function applyChanges() {
      const ghostIds = addGhosts(diff.ghostNodes, diff.ghostEdges);
      cy.batch(() => {
        Object.entries(diff.nodes || {}).forEach(([id, change]) => {
          const node = cy.getElementById(id);
          if (!node.length) return;
          node.data("change", String(change));
          touched.changes.add(id);
        });
        (diff.edges || []).forEach((entry) => {
          const edge = findEdge(entry[0], entry[1], entry[2]);
          if (!edge.length) return;
          edge.data("change", String(entry[3]));
          touched.edges.push(edge.id());
        });
      });
      container.__needGraphOverlayForcedNodes = new Set([...ghostIds, ...touched.changes]);
      reapplyPredicates();
      recolour();
      const changed = touched.changes.size;
      const removed = (diff.ghostNodes || []).length;
      announce(t("Changes mode", "Modo mudanças") + ": " + changed + " " + t("changed", "alterados") + ", " + removed + " " + t("removed", "removidos"));
    }

    function applyImpact() {
      const ghostIds = addGhosts(impact.ghostNodes, impact.ghostEdges);
      const impacted = new Set(ghostIds);
      cy.batch(() => {
        (impact.entries || []).forEach((entry) => {
          const node = cy.getElementById(String(entry.id));
          if (!node.length) return;
          node.data("impactDistance", Number(entry.distance) || 0);
          node.data("impactOrigin", String(entry.origin || ""));
          if (entry.origin && String(entry.origin) === String(entry.id)) node.addClass("need-impact-origin");
          impacted.add(String(entry.id));
          touched.impacts.push(String(entry.id));
        });
        (impact.pathEdges || []).forEach((entry) => {
          const edge = findEdge(entry[0], entry[1], entry[2]);
          if (!edge.length) return;
          edge.data("pathMember", true);
          touched.pathEdges.push(edge.id());
        });
      });
      container.__needGraphOverlayForcedNodes = ghostIds;
      container.__needGraphImpactedNodes = impacted;
      if (affected.input && affected.input.checked) {
        container.__needGraphAffectedOnly = impacted;
      }
      reapplyPredicates();
      recolour();
      announce(t("Impact mode", "Modo impacto") + ": " + impacted.size + " " + t("impacted objects", "objetos afetados"));
    }

    const modeField = makeModeSelect();
    const affected = makeAffectedToggle();
    const anchor = controls.querySelector(".need-graph-fit");
    if (anchor) controls.insertBefore(modeField.label, anchor);
    else controls.appendChild(modeField.label);
    controls.insertBefore(affected.label, modeField.label);

    modeField.select.addEventListener("change", () => {
      resetChangeData();
      const mode = modeField.select.value;
      if (mode === "changes") applyChanges();
      else if (mode === "impact") applyImpact();
      else announce(t("Catalog mode", "Modo catálogo"));
      affected.input.disabled = mode !== "impact";
      syncSlots();
    });

    affected.input.addEventListener("change", () => {
      const impacted = container.__needGraphImpactedNodes;
      container.__needGraphAffectedOnly = affected.input.checked && impacted instanceof Set
        ? new Set(impacted)
        : null;
      reapplyPredicates();
      announce(affected.input.checked
        ? t("Showing affected objects only", "Exibindo somente os afetados")
        : t("Showing the whole graph", "Exibindo o grafo inteiro"));
    });

    container.addEventListener("quarto-needs-context-reset", () => {
      modeField.select.value = "";
      resetChangeData();
      affected.input.disabled = true;
      syncSlots();
    });

    syncSlots();
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
