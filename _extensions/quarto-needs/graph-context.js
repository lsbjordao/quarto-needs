(() => {
  // Search-context and hierarchy interaction for the interactive Cytoscape
  // need graph. The base graph client owns rendering/search/popups; this module
  // augments it with semantic parent/child traversal and collapse/expand.
  if (!window.cytoscape || window.__quartoNeedsGraphContextInstalled) return;
  window.__quartoNeedsGraphContextInstalled = true;

  const registry = new WeakMap();
  const original = window.cytoscape;
  window.cytoscape = new Proxy(original, {
    apply(target, thisArg, args) {
      const cy = Reflect.apply(target, thisArg, args);
      const container = args && args[0] && args[0].container;
      if (container && typeof container === "object") registry.set(container, cy);
      return cy;
    },
  });

  // Hierarchy semantics. source_to_target means source=parent,target=child;
  // target_to_source means target=parent,source=child. Symmetric/non-lineage
  // relations are omitted deliberately.
  const RELATION_DIRECTION = {
    "derives-from": "target_to_source",
    refines: "target_to_source",
    "depends-on": "target_to_source",
    implements: "target_to_source",
    "implemented-by": "source_to_target",
    verifies: "target_to_source",
    "verified-by": "source_to_target",
    "validated-by": "source_to_target",
    mitigates: "target_to_source",
    evidences: "target_to_source",
    "evidenced-by": "source_to_target",
    addresses: "target_to_source",
    "addressed-by": "source_to_target",
    "applies-to": "source_to_target",
    supersedes: "target_to_source",
    "superseded-by": "source_to_target",
    "confirmed-by": "source_to_target",
    confirms: "target_to_source",
  };

  const DOUBLE_TAP_MS = 360;
  const DRAG_DISTANCE_PX = 6;
  const isPt = () => String(document.documentElement.lang || "").toLowerCase().startsWith("pt");

  function directRelatives(cy, nodeId, kind) {
    const ids = new Set();
    cy.edges().forEach((edge) => {
      const direction = RELATION_DIRECTION[String(edge.data("relation") || "")];
      if (!direction) return;
      const source = edge.source().id();
      const target = edge.target().id();

      if (direction === "source_to_target") {
        if (kind === "parents" && target === nodeId) ids.add(source);
        if (kind === "children" && source === nodeId) ids.add(target);
      } else {
        if (kind === "parents" && source === nodeId) ids.add(target);
        if (kind === "children" && target === nodeId) ids.add(source);
      }
    });
    return ids;
  }

  function recursiveRelatives(cy, nodeId, kind) {
    const visited = new Set([nodeId]);
    const result = new Set();
    let frontier = [nodeId];

    while (frontier.length) {
      const next = [];
      frontier.forEach((current) => {
        directRelatives(cy, current, kind).forEach((id) => {
          if (visited.has(id)) return;
          visited.add(id);
          result.add(id);
          next.push(id);
        });
      });
      frontier = next;
    }
    return result;
  }

  function makeToggle(kind, labelText) {
    const label = document.createElement("label");
    label.className = `need-graph-context-toggle need-graph-context-${kind}`;
    label.style.display = "inline-flex";
    label.style.alignItems = "center";
    label.style.gap = ".3rem";
    label.style.whiteSpace = "nowrap";
    label.style.fontSize = ".9rem";
    label.style.cursor = "pointer";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = true;
    input.dataset.needGraphContext = kind;
    input.setAttribute("aria-label", labelText);

    const text = document.createElement("span");
    text.textContent = labelText;
    label.append(input, text);
    return { label, input };
  }

  function enhance(container) {
    if (!container || container.dataset.needGraphContextReady === "true") return true;
    const canvas = container.querySelector("[data-need-graph-canvas]");
    const controls = container.querySelector("[data-need-graph-controls]");
    const search = controls && controls.querySelector(".need-graph-search");
    const status = container.querySelector("[data-need-graph-status]");
    if (!canvas || !controls || !search) return false;

    const cy = registry.get(canvas);
    if (!cy) return false;

    container.dataset.needGraphContextReady = "true";
    const parents = makeToggle("parents", isPt() ? "Pais" : "Parents");
    const children = makeToggle("children", isPt() ? "Filhos" : "Children");
    const anchor = search.nextSibling;
    controls.insertBefore(parents.label, anchor);
    controls.insertBefore(children.label, anchor);

    let selectedNodeId = null;
    const collapsed = new Set();
    let lastTap = null;
    let dragGesture = null;
    let suppressTapUntil = 0;

    const announce = (message) => {
      if (status) status.textContent = message;
    };
    const searchActive = () => Boolean(String(search.value || "").trim());

    const collapseHiddenIds = () => {
      const hidden = new Set();
      collapsed.forEach((id) => {
        recursiveRelatives(cy, id, "children").forEach((child) => hidden.add(child));
      });
      return hidden;
    };

    const setVisible = (visibleIds) => {
      const hidden = collapseHiddenIds();
      cy.nodes().forEach((node) => {
        const permitted = visibleIds === null || visibleIds.has(node.id());
        node.style("display", permitted && !hidden.has(node.id()) ? "element" : "none");
      });
      cy.edges().forEach((edge) => {
        const show = edge.source().style("display") !== "none" &&
          edge.target().style("display") !== "none";
        edge.style("display", show ? "element" : "none");
      });
    };

    const fitVisible = () => {
      const shown = cy.elements().filter((element) => element.visible());
      if (shown.length) cy.fit(shown, 40);
    };

    const showContext = () => {
      if (!selectedNodeId || !searchActive()) return;
      const selected = cy.getElementById(selectedNodeId);
      if (!selected || !selected.length) return;

      const visible = new Set([selectedNodeId]);
      if (parents.input.checked) {
        recursiveRelatives(cy, selectedNodeId, "parents").forEach((id) => visible.add(id));
      }
      if (children.input.checked) {
        recursiveRelatives(cy, selectedNodeId, "children").forEach((id) => visible.add(id));
      }
      // The explicitly selected node remains visible even if an ancestor was
      // previously collapsed; collapse affects its descendants, not the focus.
      const hidden = collapseHiddenIds();
      hidden.delete(selectedNodeId);
      cy.nodes().forEach((node) => {
        node.style("display", visible.has(node.id()) && !hidden.has(node.id()) ? "element" : "none");
      });
      cy.edges().forEach((edge) => {
        const show = edge.source().style("display") !== "none" &&
          edge.target().style("display") !== "none";
        edge.style("display", show ? "element" : "none");
      });
      fitVisible();
    };

    const applyHierarchyView = () => {
      if (searchActive() && selectedNodeId) {
        showContext();
      } else if (!searchActive()) {
        setVisible(null);
        fitVisible();
      }
    };

    const toggleCollapse = (nodeId) => {
      const descendants = recursiveRelatives(cy, nodeId, "children");
      if (!descendants.size) return;
      if (collapsed.has(nodeId)) {
        collapsed.delete(nodeId);
        announce(isPt() ? `Expandido ${nodeId}` : `Expanded ${nodeId}`);
      } else {
        collapsed.add(nodeId);
        announce(isPt() ? `Colapsado ${nodeId}` : `Collapsed ${nodeId}`);
      }
      applyHierarchyView();
    };

    // graph.js applies text matching first. A changed query returns to the set of
    // text matches; recursive context starts only after the user chooses one.
    search.addEventListener("input", () => {
      selectedNodeId = null;
      lastTap = null;
    });

    parents.input.addEventListener("change", showContext);
    children.input.addEventListener("change", showContext);

    // Distinguish a true two-click gesture from dragging. Any movement beyond a
    // small threshold during grab/drag suppresses double-click collapse, leaving
    // Cytoscape's native node dragging untouched.
    cy.on("grab", "node", (event) => {
      const p = event.target.renderedPosition();
      dragGesture = { id: event.target.id(), x: p.x, y: p.y, moved: false };
    });
    cy.on("drag", "node", (event) => {
      if (!dragGesture || dragGesture.id !== event.target.id()) return;
      const p = event.target.renderedPosition();
      const dx = p.x - dragGesture.x;
      const dy = p.y - dragGesture.y;
      if (Math.hypot(dx, dy) >= DRAG_DISTANCE_PX) dragGesture.moved = true;
    });
    cy.on("free", "node", (event) => {
      if (dragGesture && dragGesture.id === event.target.id() && dragGesture.moved) {
        suppressTapUntil = Date.now() + DOUBLE_TAP_MS;
        lastTap = null;
      }
      dragGesture = null;
    });

    cy.on("tap", "node", (event) => {
      const nodeId = event.target.id();
      const now = Date.now();

      if (searchActive()) {
        selectedNodeId = nodeId;
        showContext();
      }

      if (now < suppressTapUntil) return;
      if (lastTap && lastTap.id === nodeId && now - lastTap.time <= DOUBLE_TAP_MS) {
        lastTap = null;
        toggleCollapse(nodeId);
      } else {
        lastTap = { id: nodeId, time: now };
      }
    });

    const reset = controls.querySelector(".need-graph-reset");
    if (reset) {
      reset.addEventListener("click", () => {
        selectedNodeId = null;
        collapsed.clear();
        lastTap = null;
        parents.input.checked = true;
        children.input.checked = true;
      });
    }
    return true;
  }

  function enhanceAll() {
    document.querySelectorAll("[data-need-graph]").forEach(enhance);
  }

  function schedule() {
    requestAnimationFrame(enhanceAll);
    setTimeout(enhanceAll, 100);
    setTimeout(enhanceAll, 500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", schedule);
  } else {
    schedule();
  }
})();
