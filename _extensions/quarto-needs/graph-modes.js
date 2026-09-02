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

    // The static table stays the primary accessible path — Changes mode
    // must update it too, not just the canvas, or a reader relying on it
    // sees a stale catalog view regardless of the selected mode. Impact
    // mode's table columns are a separate, larger follow-on (it needs the
    // same path-explanation text formatting Lua's impact_explanations()
    // already does, which JS presenting-not-classifying shouldn't
    // duplicate) and stays announcement/popup-only for now.
    const nodeTable = container.querySelector('.need-graph-table[data-need-graph-role="node"]');
    const edgeTable = container.querySelector('.need-graph-table[data-need-graph-role="edge"]');
    // Snapshotted once, from the untouched catalog-rendered table, before
    // any mode ever applies — never re-derived lazily, or a second Changes
    // entry would snapshot the table's own prior modifications instead of
    // the true original.
    const tableSnapshot = new Map();
    function snapshotTable(table) {
      if (!table) return;
      table.querySelectorAll("tbody tr[data-need-graph-row-id]").forEach((row) => {
        const cells = row.querySelectorAll("td");
        const last = cells[cells.length - 1];
        if (last) tableSnapshot.set(row.dataset.needGraphRowId, last.textContent);
      });
    }
    snapshotTable(nodeTable);
    snapshotTable(edgeTable);

    function findRow(table, id) {
      if (!table) return null;
      return table.querySelector('tbody tr[data-need-graph-row-id="' + CSS.escape(String(id)) + '"]');
    }
    function setLastCellText(row, text) {
      if (!row) return;
      const cells = row.querySelectorAll("td");
      const last = cells[cells.length - 1];
      if (last) last.textContent = text;
    }
    function appendGhostRow(table, id, cellValues) {
      if (!table) return null;
      const tbody = table.querySelector("tbody");
      if (!tbody) return null;
      const row = document.createElement("tr");
      row.dataset.needGraphRowId = id;
      cellValues.forEach((value) => {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
      });
      tbody.appendChild(row);
      return row;
    }

    // Everything one mode application touches, so leaving a mode restores
    // exactly what it changed — no more, no less.
    const touched = {
      changes: new Set(), edges: [], pathEdges: [], impacts: [], ghosts: new Set(),
      tableRows: new Set(), tableGhostRows: [],
    };
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
      touched.tableRows.forEach((id) => {
        const row = findRow(nodeTable, id) || findRow(edgeTable, id);
        if (row && tableSnapshot.has(id)) setLastCellText(row, tableSnapshot.get(id));
      });
      touched.tableGhostRows.forEach((row) => row.remove());
      touched.changes.clear();
      touched.edges.length = 0;
      touched.pathEdges.length = 0;
      touched.impacts.length = 0;
      touched.ghosts.clear();
      touched.tableRows.clear();
      touched.tableGhostRows.length = 0;
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
          if (!edge) return;
          edge.data("change", String(entry[3]));
          touched.edges.push(edge.id());
        });
      });
      Object.entries(diff.nodes || {}).forEach(([id, change]) => {
        const row = findRow(nodeTable, id);
        if (!row) return;
        setLastCellText(row, String(change));
        touched.tableRows.add(id);
      });
      (diff.edges || []).forEach((entry) => {
        const id = entry[0] + "|" + entry[1] + "|" + entry[2];
        const row = findRow(edgeTable, id);
        if (!row) return;
        setLastCellText(row, String(entry[3]));
        touched.tableRows.add(id);
      });
      (diff.ghostNodes || []).forEach((ghost) => {
        const row = appendGhostRow(nodeTable, String(ghost.id), [
          ghost.id, ghost.title || ghost.id, ghost.type || "", ghost.status || "",
          ghost.priority || "", (ghost.tags || []).join(", "), "removed",
        ]);
        if (row) touched.tableGhostRows.push(row);
      });
      (diff.ghostEdges || []).forEach((edge) => {
        const id = edge.source + "|" + (edge.relation || "") + "|" + edge.target;
        const row = appendGhostRow(edgeTable, id, [
          edge.source, edge.label || edge.relation || "", edge.target, "removed", "",
        ]);
        if (row) touched.tableGhostRows.push(row);
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
          if (!edge) return;
          edge.data("pathMember", true);
          touched.pathEdges.push(edge.id());
        });
      });
      container.__needGraphOverlayForcedNodes = ghostIds;
      container.__needGraphImpactedNodes = impacted;
      if (affected.input && affected.input.checked && impacted.size) {
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
      const impactedNow = container.__needGraphImpactedNodes;
      const hasImpacted = impactedNow instanceof Set && impactedNow.size > 0;
      affected.input.disabled = mode !== "impact" || !hasImpacted;
      if (affected.input.disabled) affected.input.checked = false;
      syncSlots();
    });

    affected.input.addEventListener("change", () => {
      const impacted = container.__needGraphImpactedNodes;
      if (affected.input.checked && !(impacted instanceof Set && impacted.size)) {
        announce(t("No impacted objects to filter", "Nenhum objeto afetado para filtrar"));
        return;
      }
      container.__needGraphAffectedOnly = affected.input.checked && impacted instanceof Set && impacted.size
        ? new Set(impacted)
        : null;
      syncSlots();
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
