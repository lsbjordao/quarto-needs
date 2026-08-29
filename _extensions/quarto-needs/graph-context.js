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
      const container = args && args[0] && args[0].container;
      if (container && typeof container === "object") registry.set(container, cy);
      return cy;
    },
  });

  // Keep the adjustable layout aligned with graph.js's engineering hierarchy.
  // This map is presentation policy only; engineering relation semantics come
  // exclusively from the public projection emitted by the Python core.
  const TYPE_LEVEL_MAP = {
    "stakeholder-need": 0,
    stakeholder: 0,
    "system-requirement": 1,
    "functional-requirement": 2,
    "non-functional-requirement": 2,
    "architecture-decision": 3,
    component: 4,
    interface: 5,
    risk: 6,
    threat: 6,
    "test-case": 7,
    evidence: 8,
  };

  const DOUBLE_TAP_MS = 360;
  const DRAG_DISTANCE_PX = 6;
  const DEFAULT_SPACING = 90;
  const MIN_SPACING = 50;
  const MAX_SPACING = 240;
  const SPACING_STEP = 10;
  const isPt = () => String(document.documentElement.lang || "").toLowerCase().startsWith("pt");

  function projectionFor(container) {
    const script = container.querySelector("[data-need-graph-data]");
    if (!script) return {};
    try {
      return JSON.parse(script.textContent || "{}");
    } catch (_error) {
      return {};
    }
  }

  function directRelatives(cy, semantics, nodeId, kind) {
    const ids = new Set();
    cy.edges().forEach((edge) => {
      const relation = String(edge.data("relation") || "");
      const definition = semantics[relation] || {};
      const direction = String(definition.traversalDirection || "none");
      if (direction === "none") return;

      const source = edge.source().id();
      const target = edge.target().id();
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

  function recursiveRelatives(cy, semantics, nodeId, kind) {
    const visited = new Set([nodeId]);
    const result = new Set();
    let frontier = [nodeId];

    while (frontier.length) {
      const next = [];
      frontier.forEach((current) => {
        directRelatives(cy, semantics, current, kind).forEach((id) => {
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

  function makeToggle(kind, labelText, checked = true) {
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
    input.checked = checked;
    input.dataset.needGraphContext = kind;
    input.setAttribute("aria-label", labelText);

    const text = document.createElement("span");
    text.textContent = labelText;
    label.append(input, text);
    return { label, input };
  }

  function makeSpacingControl() {
    const wrapper = document.createElement("span");
    wrapper.className = "need-graph-spacing-control";
    wrapper.style.display = "inline-flex";
    wrapper.style.alignItems = "center";
    wrapper.style.gap = ".35rem";
    wrapper.style.whiteSpace = "nowrap";
    wrapper.style.fontSize = ".9rem";

    const toggle = makeToggle(
      "fixed-spacing",
      isPt() ? "Espaçamento fixo" : "Fixed spacing",
      false,
    );

    const range = document.createElement("input");
    range.type = "range";
    range.min = String(MIN_SPACING);
    range.max = String(MAX_SPACING);
    range.step = String(SPACING_STEP);
    range.value = String(DEFAULT_SPACING);
    range.disabled = true;
    range.className = "need-graph-spacing-range";
    range.dataset.needGraphSpacing = "true";
    range.setAttribute("aria-label", isPt() ? "Distância entre os nós" : "Distance between nodes");
    range.style.width = "8rem";

    const value = document.createElement("output");
    value.className = "need-graph-spacing-value";
    value.value = `${DEFAULT_SPACING} px`;
    value.textContent = `${DEFAULT_SPACING} px`;
    value.style.minWidth = "3.6rem";
    value.style.fontVariantNumeric = "tabular-nums";

    wrapper.append(toggle.label, range, value);
    return { wrapper, toggle: toggle.input, range, value };
  }

  function levelForType(type) {
    const normalized = String(type || "").toLowerCase().trim();
    return TYPE_LEVEL_MAP[normalized] != null ? TYPE_LEVEL_MAP[normalized] : 1000;
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

    const projection = projectionFor(container);
    const relationSemantics = projection.relationSemantics || {};

    container.dataset.needGraphContextReady = "true";
    const parents = makeToggle("parents", isPt() ? "Pais" : "Parents");
    const children = makeToggle("children", isPt() ? "Filhos" : "Children");
    const spacing = makeSpacingControl();
    const anchor = search.nextSibling;
    controls.insertBefore(parents.label, anchor);
    controls.insertBefore(children.label, anchor);
    controls.insertBefore(spacing.wrapper, anchor);

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
        recursiveRelatives(cy, relationSemantics, id, "children").forEach((child) => hidden.add(child));
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

    const applyFixedSpacing = () => {
      if (!spacing.toggle.checked) return;
      const distance = Number(spacing.range.value) || DEFAULT_SPACING;
      const visibleNodes = cy.nodes().filter((node) => node.visible());
      if (!visibleNodes.length) return;

      const levels = new Map();
      visibleNodes.forEach((node) => {
        const level = levelForType(node.data("type"));
        if (!levels.has(level)) levels.set(level, []);
        levels.get(level).push(node);
      });

      const ranked = [...levels.entries()].sort((a, b) => a[0] - b[0]);
      const positions = new Map();
      ranked.forEach(([, nodes], row) => {
        nodes.sort((a, b) => a.id().localeCompare(b.id()));
        const count = nodes.length;
        nodes.forEach((node, column) => {
          positions.set(node.id(), {
            x: (column - (count - 1) / 2) * distance,
            y: row * distance,
          });
        });
      });

      cy.layout({
        name: "preset",
        positions: (node) => positions.get(node.id()) || node.position(),
        fit: false,
        animate: false,
      }).run();
      fitVisible();
    };

    const refreshLayout = () => {
      if (spacing.toggle.checked) applyFixedSpacing();
      else fitVisible();
    };

    const showContext = () => {
      if (!selectedNodeId || !searchActive()) return;
      const selected = cy.getElementById(selectedNodeId);
      if (!selected || !selected.length) return;

      const visible = new Set([selectedNodeId]);
      if (parents.input.checked) {
        recursiveRelatives(cy, relationSemantics, selectedNodeId, "parents").forEach((id) => visible.add(id));
      }
      if (children.input.checked) {
        recursiveRelatives(cy, relationSemantics, selectedNodeId, "children").forEach((id) => visible.add(id));
      }
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
      refreshLayout();
    };

    const applyHierarchyView = () => {
      if (searchActive() && selectedNodeId) {
        showContext();
      } else if (!searchActive()) {
        setVisible(null);
        refreshLayout();
      }
    };

    const toggleCollapse = (nodeId) => {
      const descendants = recursiveRelatives(cy, relationSemantics, nodeId, "children");
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

    search.addEventListener("input", () => {
      selectedNodeId = null;
      lastTap = null;
      // graph.js performs the actual text filtering in the same input event.
      // Wait until it has hidden the non-matches before reapplying fixed spacing.
      requestAnimationFrame(refreshLayout);
    });

    parents.input.addEventListener("change", showContext);
    children.input.addEventListener("change", showContext);

    spacing.toggle.addEventListener("change", () => {
      spacing.range.disabled = !spacing.toggle.checked;
      if (spacing.toggle.checked) {
        applyFixedSpacing();
        announce(isPt() ? "Espaçamento fixo ativado" : "Fixed spacing enabled");
      } else {
        announce(isPt() ? "Espaçamento fixo desativado" : "Fixed spacing disabled");
      }
    });
    spacing.range.addEventListener("input", () => {
      const distance = Number(spacing.range.value) || DEFAULT_SPACING;
      spacing.value.value = `${distance} px`;
      spacing.value.textContent = `${distance} px`;
      applyFixedSpacing();
    });

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
        if (spacing.toggle.checked) requestAnimationFrame(applyFixedSpacing);
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
