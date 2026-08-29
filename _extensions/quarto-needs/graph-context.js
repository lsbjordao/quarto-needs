(() => {
  // Search-context controls for the interactive Cytoscape need graph.
  //
  // The base graph client owns rendering/search/popups. This module wraps the
  // Cytoscape constructor before graph.js initializes so each canvas can be
  // associated with its own graph instance, then adds two independent toggles:
  // direct semantic parents and direct semantic children of a selected search
  // result. The context expansion is intentionally one hop only.
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

  // Same downstream semantics used by the rooted graph view. A
  // source_to_target relation means source=parent and target=child; a
  // target_to_source relation means target=parent and source=child. Relations
  // without a meaningful hierarchy are intentionally omitted.
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

  const isPt = () => String(document.documentElement.lang || "").toLowerCase().startsWith("pt");

  function semanticRelatives(cy, nodeId, kind) {
    const ids = new Set();
    cy.edges().forEach((edge) => {
      const relation = String(edge.data("relation") || "");
      const direction = RELATION_DIRECTION[relation];
      if (!direction) return;

      const source = edge.source().id();
      const target = edge.target().id();
      if (direction === "source_to_target") {
        if (kind === "parents" && target === nodeId) ids.add(source);
        if (kind === "children" && source === nodeId) ids.add(target);
      } else if (direction === "target_to_source") {
        if (kind === "parents" && source === nodeId) ids.add(target);
        if (kind === "children" && target === nodeId) ids.add(source);
      }
    });
    return ids;
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

    const searchActive = () => Boolean(String(search.value || "").trim());

    const showContext = () => {
      if (!selectedNodeId || !searchActive()) return;
      const selected = cy.getElementById(selectedNodeId);
      if (!selected || !selected.length) return;

      const visible = new Set([selectedNodeId]);
      if (parents.input.checked) {
        semanticRelatives(cy, selectedNodeId, "parents").forEach((id) => visible.add(id));
      }
      if (children.input.checked) {
        semanticRelatives(cy, selectedNodeId, "children").forEach((id) => visible.add(id));
      }

      cy.nodes().forEach((node) => {
        node.style("display", visible.has(node.id()) ? "element" : "none");
      });
      cy.edges().forEach((edge) => {
        const show = visible.has(edge.source().id()) && visible.has(edge.target().id());
        edge.style("display", show ? "element" : "none");
      });

      const shown = cy.elements().filter((element) => element.visible());
      if (shown.length) cy.fit(shown, 40);
    };

    // graph.js handles text matching first. Changing the query returns to the
    // search result set; contextual expansion starts only after the user chooses
    // one of those visible nodes.
    search.addEventListener("input", () => {
      selectedNodeId = null;
    });

    cy.on("tap", "node", (event) => {
      if (!searchActive()) return;
      selectedNodeId = event.target.id();
      showContext();
    });

    parents.input.addEventListener("change", showContext);
    children.input.addEventListener("change", showContext);

    const reset = controls.querySelector(".need-graph-reset");
    if (reset) {
      reset.addEventListener("click", () => {
        selectedNodeId = null;
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
