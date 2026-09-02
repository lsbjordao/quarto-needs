(() => {
  // The interactive Cytoscape client for quarto-needs need-graph.
  //
  // It initializes only after the static fallback is present and the embedded
  // projection decodes and validates. The fallback (edge table) is hidden only
  // after a successful render, so a script failure leaves the accessible table
  // visible. The canvas is hidden from assistive technology because the
  // synchronized semantic table already represents the same information.
  const VALID_MODES = new Set(["catalog", "diff", "impact"]);
  const CHANGE_COLORS = {
    added: "#166534",
    removed: "#991b1b",
    modified: "#92400e",
    relocated: "#1d4ed8",
    unchanged: "#64748b",
  };
  // Fill/border pairs used when coloring by an attribute such as change. The
  // `change` palette mirrors the static net style so the interactive graph
  // matches the default rendering when that option is selected.
  const CHANGE_STYLES = {
    added: { fill: "#dcfce7", border: "#166534" },
    removed: { fill: "#fee2e2", border: "#991b1b" },
    modified: { fill: "#ffedd5", border: "#92400e" },
    relocated: { fill: "#dbeafe", border: "#1d4ed8" },
    unchanged: { fill: "#e2e8f0", border: "#94a3b8" },
  };
  // General-purpose categorical palette, re-used in document order for each
  // distinct value of an arbitrary node facet (type, status, priority, …).
  const CATEGORY_PALETTE = [
    { fill: "#dbeafe", border: "#1d4ed8" },
    { fill: "#dcfce7", border: "#166534" },
    { fill: "#fee2e2", border: "#991b1b" },
    { fill: "#fef3c7", border: "#b45309" },
    { fill: "#ede9fe", border: "#7c3aed" },
    { fill: "#ccfbf1", border: "#0f766e" },
    { fill: "#ffedd5", border: "#c2410c" },
    { fill: "#f1f5f9", border: "#475569" },
  ];

  // Cytoscape creates internal canvases and requests 2d contexts without
  // preserveDrawingBuffer. On GPU-accelerated browsers the frame buffer is then
  // discarded between rAF ticks, so a fully-rendered graph can appear as a blank
  // canvas on screen (while toDataURL still shows the content). Force the flag
  // on every 2d context so the drawing stays visible.
  (function forcePreserveDrawingBuffer() {
    if (!window.HTMLCanvasElement) return;
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, attributes) {
      const attrs = Object.assign({}, attributes, { preserveDrawingBuffer: true });
      return original.call(this, type, attrs);
    };
  })();

  function validateProjection(payload) {
    if (!payload || typeof payload !== "object") return "missing projection";
    if (payload.schemaVersion !== "graph-public-v1") return "unsupported schemaVersion";
    if (!Array.isArray(payload.nodes) || !Array.isArray(payload.edges)) return "no nodes/edges";
    if (!payload.view || !VALID_MODES.has(payload.view.mode)) return "invalid view mode";
    return null;
  }

  function dataFor(container) {
    const root = container.querySelector("[data-need-graph-data]");
    if (!root) return null;
    try {
      return JSON.parse(root.textContent);
    } catch (_error) {
      return null;
    }
  }

  function announce(statusEl, message) {
    if (statusEl) statusEl.textContent = message;
  }

  // Remove the "Loading interactive graph…" placeholder. It is a child of the
  // canvas with height:100%, so if left in the DOM it stays on top of the
  // rendered graph and hides it. Removing only a class on the canvas root is not
  // enough — the placeholder child must be removed from the DOM.
  function clearLoading(canvasRoot) {
    if (!canvasRoot) return;
    const placeholder = canvasRoot.querySelector(".need-graph-loading");
    if (placeholder && placeholder.parentNode) placeholder.parentNode.removeChild(placeholder);
  }

  function buildElements(projection) {
    return {
      nodes: projection.nodes.map((node) => ({
        data: { id: node.id, title: node.title, type: node.type, status: node.status,
                priority: node.priority || "", tags: node.tags || [],
                href: node.href, change: node.change || "unchanged" },
      })),
      edges: projection.edges.map((edge, index) => ({
        data: { id: `e${index}`, source: edge.source, target: edge.target,
                label: edge.label, relation: edge.relation,
                change: edge.change || "unchanged", pathMember: !!edge.pathMember },
      })),
    };
  }

  // Logical engineering levels, top to bottom. Every type maps to a level so the
  // hierarchical layout can line the nodes up in rows (stakeholders/needs at the
  // top, then system → functional/non-functional requirements → components →
  // risks → tests → evidence at the bottom). Unknown types sink to the bottom.
  const TYPE_LEVEL_MAP = {
    "stakeholder-need": 0,
    stakeholder: 0,
    "system-requirement": 1,
    "functional-requirement": 2,
    "non-functional-requirement": 2,
    component: 3,
    interface: 4,
    risk: 5,
    threat: 5,
    "test-case": 6,
    evidence: 7,
  };
  function levelForType(type) {
    const normalized = String(type || "").toLowerCase().trim();
    return TYPE_LEVEL_MAP[normalized] != null ? TYPE_LEVEL_MAP[normalized] : NaN;
  }

  // Deterministic, hierarchical preset layout: rows of nodes ordered by logical
  // level with the topmost type at the top. Accepts either the raw projection
  // nodes ({id, type}) or a Cytoscape collection ({id(), data('type')}), so the
  // same helper drives both the initial render and the reset.
  function hierarchicalLayout(providedNodes) {
    const nodes = Array.from(providedNodes);
    return () => {
      const levels = new Map();
      const idOf = (node) => (typeof node.id === "function" ? node.id() : node.id);
      const typeOf = (node) => {
        const value = typeof node.data === "function" ? node.data("type") : node.type;
        return String(value == null ? "" : value).toLowerCase().trim();
      };
      nodes.forEach((node) => {
        let level = levelForType(typeOf(node));
        if (Number.isNaN(level)) level = 1000; // unknown types at the very bottom
        if (!levels.has(level)) levels.set(level, []);
        levels.get(level).push(idOf(node));
      });
      const ranked = [...levels.entries()].sort((a, b) => a[0] - b[0]);
      const positions = {};
      const nodeGap = 70;
      const levelGap = 150;
      ranked.forEach(([, ids], rankIndex) => {
        const count = ids.length;
        ids.forEach((id, column) => {
          const x = (column - (count - 1) / 2) * nodeGap;
          const y = rankIndex * levelGap;
          positions[id] = { x, y };
        });
      });
      return { name: "preset", positions, fit: true, padding: 40, animate: true };
    };
  }

  function applyNetStyle() {
    return [
      {
        selector: "node",
        style: {
          label: "data(id)",
          "font-size": 11,
          "text-valign": "top",
          "text-halign": "center",
          "border-width": 2,
          "border-color": "#94a3b8",
          "background-color": "#e2e8f0",
          width: 34,
          height: 34,
          "overlay-opacity": 0,
        },
      },
      {
        selector: "node[change = 'added']",
        style: { "background-color": "#dcfce7", "border-color": "#166534" },
      },
      {
        selector: "node[change = 'removed']",
        style: { "background-color": "#fee2e2", "border-color": "#991b1b" },
      },
      {
        selector: "node[change = 'modified']",
        style: { "background-color": "#ffedd5", "border-color": "#92400e" },
      },
      {
        selector: "node[change = 'relocated']",
        style: { "background-color": "#dbeafe", "border-color": "#1d4ed8" },
      },
      {
        selector: "edge",
        style: {
          "curve-style": "bezier",
          "target-arrow-shape": "triangle",
          "target-arrow-color": "#64748b",
          "line-color": "#64748b",
          width: 1.5,
          label: "data(label)",
          "font-size": 9,
          "text-rotation": "autorotate",
          "text-background-opacity": 0.6,
          "text-background-color": "#ffffff",
        },
      },
      {
        selector: "edge[pathMember = 'true']",
        style: { "line-color": "#b45309", "target-arrow-color": "#b45309", width: 3 },
      },
      {
        selector: ":selected",
        style: { "border-width": 4, "border-color": "#2563eb" },
      },
    ];
  }

  function highlightPath(cy, target, origin) {
    cy.elements().removeClass("path-vertex");
    cy.$("*").removeClass("path-edge");
    if (!origin) return;
    const sourceNode = cy.getElementById(origin);
    const targetNode = cy.getElementById(target);
    if (!sourceNode.length || !targetNode.length) return;
    const dijkstra = cy.elements().dijkstra({ root: sourceNode, directed: false });
    const path = dijkstra.pathTo(targetNode);
    if (!path) return;
    path.nodes().addClass("path-vertex");
    path.edges().addClass("path-edge");
  }

  function neighborsOf(cy, id) {
    const nbrs = cy.getElementById(id).closedNeighborhood();
    return nbrs.nodes().map((node) => node.id());
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  // Lowercase, dash-separated slug reused to build color classes like
  // `need-status-approved` or `need-priority-high`, mirroring views.badge.
  function slug(value) {
    return String(value == null ? "" : value)
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  // A real popup (not a hover overlay) listing the node's facets. Fields are
  // `user-select: text` so values (e.g. the ID) can be selected and copied, and a
  // dedicated copy-to-clipboard button copies the node ID. A close button and
  // Escape dismiss it; background tap also hides an already-open popup.
  const COPY_ICON = `<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true" focusable="false"><path fill="currentColor" d="M4 2h8a1 1 0 0 1 1 1v8h-1V3H4V2Zm-2 2h6a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Zm0 1v8h6V5H2Z"/></svg>`;

  function buildNodePopup(node) {
    const data = node.data();
    const body = [];
    // ID stays a plain, selectable code value (with its copy button). Type,
    // Status and Priority render as colored badges reusing the standard need
    // badge classes (need-status-*, need-priority-*, need-type-*).
    const plainField = (label, value) => {
      if (value === "" || value == null) return "";
      return `<div class="need-graph-popup-row"><span class="need-graph-popup-label">${label}</span>` +
        `<code class="need-graph-popup-value">${escapeHtml(String(value))}</code></div>`;
    };
    const badgeField = (label, kind, value) => {
      if (value === "" || value == null) return "";
      return `<div class="need-graph-popup-row"><span class="need-graph-popup-label">${label}</span>` +
        `<span class="need-badge need-${slug(kind)} need-${slug(kind)}-${slug(value)}">${escapeHtml(String(value))}</span></div>`;
    };
    body.push(plainField("ID", node.id()));
    body.push(badgeField("Type", "type", data.type));
    body.push(badgeField("Status", "status", data.status));
    body.push(badgeField("Priority", "priority", data.priority));
    if (data.change && data.change !== "unchanged") body.push(plainField("Change", data.change));
    const popup = document.createElement("div");
    popup.className = "need-graph-popup";
    popup.setAttribute("role", "dialog");
    popup.innerHTML =
      `<div class="need-graph-popup-head">` +
        (data.title ? `<div class="need-graph-popup-title">${escapeHtml(data.title)}</div>` : `<div></div>`) +
        `<button type="button" class="need-graph-popup-close" aria-label="Close details" title="Close">×</button>` +
      `</div>` +
      `<div class="need-graph-popup-body">${body.join("")}</div>` +
      (data.href
        ? `<div class="need-graph-popup-foot"><a href="${escapeHtml(data.href)}">Open need</a></div>`
        : "");
    // Copy-to-clipboard button next to the ID.
    const idRow = popup.querySelector(".need-graph-popup-row .need-graph-popup-value");
    const idLabel = popup.querySelector(".need-graph-popup-row .need-graph-popup-label");
    if (idRow && idLabel && idLabel.textContent === "ID") {
      const copy = document.createElement("button");
      copy.type = "button";
      copy.className = "need-graph-popup-copy";
      copy.title = "Copy ID to clipboard";
      copy.setAttribute("aria-label", "Copy ID to clipboard");
      copy.innerHTML = COPY_ICON;
      copy.addEventListener("click", async () => {
        const value = String(node.id());
        let ok = false;
        try {
          await navigator.clipboard.writeText(value);
          ok = true;
        } catch (_clipboardError) {
          const ta = document.createElement("textarea");
          ta.value = value;
          ta.setAttribute("readonly", "");
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          try { ok = document.execCommand("copy"); } catch (_copyError) { ok = false; }
          ta.remove();
        }
        if (ok) {
          const original = copy.innerHTML;
          copy.classList.add("copied");
          copy.innerHTML = "✓";
          setTimeout(() => { copy.classList.remove("copied"); copy.innerHTML = original; }, 1200);
        }
      });
      idRow.parentNode.insertBefore(copy, idRow.nextSibling);
    }
    return popup;
  }

  // Recolour every node based on the value of a chosen facet. `change` uses the
  // dedicated palette; any other facet (type, status, priority) is grouped by its
  // distinct values and assigned a colour from the categorical palette, visited in
  // document order so the result is deterministic. `none` restores the base style.
  function applyColorBy(cy, facet) {
    const styleNode = (node, fill, border) =>
      node.style({ "background-color": fill, "border-color": border });

    if (!facet || facet === "none") {
      cy.nodes().forEach((node) =>
        styleNode(node, "#e2e8f0", "#94a3b8"));
      return;
    }

    if (facet === "change") {
      cy.nodes().forEach((node) => {
        const change = node.data("change") || "unchanged";
        const palette = CHANGE_STYLES[change] || CHANGE_STYLES.unchanged;
        styleNode(node, palette.fill, palette.border);
      });
      return;
    }

    const groups = new Map();
    cy.nodes().forEach((node) => {
      const value = String(node.data(facet) == null ? "" : node.data(facet));
      const key = value === "" ? "—" : value;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(node);
    });
    let index = 0;
    groups.forEach((nodes) => {
      const palette = CATEGORY_PALETTE[index % CATEGORY_PALETTE.length];
      index += 1;
      nodes.forEach((node) => styleNode(node, palette.fill, palette.border));
    });
  }

  function buildGraph(container, projection) {
    const canvasRoot = container.querySelector("[data-need-graph-canvas]");
    const controls = container.querySelector("[data-need-graph-controls]");
    const status = container.querySelector("[data-need-graph-status]");
    const table = container.querySelector(".need-graph-table");
    // Reusable node popup rendered into the canvas root, hidden on reset, a
    // background tap, a close click, or Escape. `hidePopup` is declared first so
    // the reset handler can call it regardless of ordering.
    let lastPopupAt = 0;
    const hidePopup = () => {
      const popup = canvasRoot && canvasRoot.querySelector(".need-graph-popup");
      if (popup) popup.remove();
    };
    // A single node tap can be followed immediately by a spurious background tap
    // (seen in automated/headless input). Guard against that so the just-shown
    // popup isn't dismissed before the user has a chance to see it, while still
    // allowing a deliberate background tap to hide an already-open popup.
    const hidePopupOnBackground = () => {
      if (Date.now() - lastPopupAt < 250) return;
      hidePopup();
    };
    const cy = window.cytoscape({
      container: canvasRoot,
      elements: buildElements(projection),
      style: applyNetStyle(),
      layout: hierarchicalLayout(projection.nodes)(),
      wheelSensitivity: 0.2,
      minZoom: 0.1,
      maxZoom: 4,
      // Keep the drawing buffer so the rendered graph stays visible on screen.
      // Without this, GPU-accelerated browsers can show a blank canvas even
      // though the graph is drawn (toDataURL still captures the content).
      headless: false,
      textureOnViewport: false,
      motionBlur: false,
      pixelRatio: "auto",
    });

    // Expose for diagnostics/debugging only.
    window.__needGraph = cy;

    // Cytoscape captures the container size at init. If the page layout has not
    // settled yet, the container may report 0 width, so the graph renders into a
    // blank canvas. Re-query the real size on the next frame and redraw/fit.
    const stabilize = () => {
      cy.resize();
      cy.fit(undefined, 40);
    };
    requestAnimationFrame(stabilize);
    setTimeout(stabilize, 250);
    window.addEventListener("load", stabilize);

    // Filtering helpers -----------------------------------------------------
    const applyFacet = (kind, value) => {
      const nodes = cy.nodes();
      let visible;
      if (value === "") {
        visible = true;
      } else {
        visible = nodes.filter((node) => String(node.data(kind)).toLowerCase() === value.toLowerCase());
      }
      cy.nodes().forEach((node) => node.style("display", visible === true || visible.contains(node) ? "element" : "none"));
      cy.edges().forEach((edge) => {
        const showSource = edge.source().style("display") !== "none";
        const showTarget = edge.target().style("display") !== "none";
        edge.style("display", visible === true || (showSource && showTarget) ? "element" : "none");
      });
    };

    // Search ----------------------------------------------------------------
    const search = controls.querySelector(".need-graph-search");
    const searchMatches = () => {
      const needle = (search.value || "").trim().toLowerCase();
      if (!needle) return new Set(cy.nodes().map((n) => n.id()));
      const matches = new Set();
      cy.nodes().forEach((node) => {
        const id = String(node.id() || "").toLowerCase();
        const title = String(node.data("title") || "").toLowerCase();
        if (id.includes(needle) || title.includes(needle)) matches.add(node.id());
      });
      return matches;
    };
    const applySearch = () => {
      const matches = searchMatches();
      const total = matches.size;
      let first = null;
      cy.nodes().forEach((node) => {
        const match = matches.has(node.id());
        if (match && !first) first = node;
        node.style("display", match ? "element" : "none");
      });
      cy.edges().forEach((edge) => {
        const s = edge.source().style("display") !== "none";
        const t = edge.target().style("display") !== "none";
        edge.style("display", s && t ? "element" : "none");
      });
      announce(status, `${total} of ${cy.nodes().length} nodes match search`);
      if (first) {
        const neighbourhood = first.closedNeighborhood();
        neighbourhood.addClass("neighbour-highlight");
        neighbourhood.removeClass();
        first.addClass("search-target");
      }
    };
    search.addEventListener("input", applySearch);

    // Fit / reset / neighborhood -------------------------------------------
    const fitBtn = controls.querySelector(".need-graph-fit");
    const resetBtn = controls.querySelector(".need-graph-reset");
    fitBtn.addEventListener("click", () => cy.fit(undefined, 30));
    resetBtn.addEventListener("click", () => {
      cy.elements().removeClass("path-vertex path-edge");
      cy.nodes().forEach((n) => n.style("display", "element"));
      cy.edges().forEach((e) => e.style("display", "element"));
      if (search) search.value = "";
      hidePopup();
      cy.layout(hierarchicalLayout(cy.nodes())()).run();
      cy.fit(undefined, 30);
      announce(status, "Graph reset");
    });

    // Fullscreen -------------------------------------------------------------
    // requestFullscreen() doesn't reparent anything — it only changes how the
    // element is painted — so breadcrumbs, active-path highlighting, popups,
    // and every other module's state survive the transition untouched. The
    // only real effect is that the container's pixel size changes, which
    // Cytoscape must be told about explicitly.
    const fullscreenBtn = controls.querySelector(".need-graph-fullscreen");
    const fullscreenRoot = container.querySelector(".need-graph-container");
    if (fullscreenBtn && fullscreenRoot) {
      if (!fullscreenRoot.requestFullscreen) {
        fullscreenBtn.remove();
      } else {
        // The initial label is Lua's own views.tr() text (English or
        // pt-BR); only the transient "active" label is hardcoded English,
        // matching this file's existing dynamic status strings.
        const restLabel = fullscreenBtn.textContent;
        fullscreenBtn.addEventListener("click", () => {
          if (document.fullscreenElement === fullscreenRoot) {
            document.exitFullscreen();
          } else {
            fullscreenRoot.requestFullscreen().catch(() => {
              announce(status, "Fullscreen unavailable");
            });
          }
        });
        document.addEventListener("fullscreenchange", () => {
          const active = document.fullscreenElement === fullscreenRoot;
          fullscreenBtn.textContent = active ? "Exit fullscreen" : restLabel;
          stabilize();
        });
      }
    }

    // Export PNG --------------------------------------------------------------
    // cy.svg() does not exist on the vendored Cytoscape core — the only SVG
    // export plugin (cytoscape-svg) is GPLv3, which conflicts with this
    // project's MIT license for a vendored dependency, so PNG is all this
    // uses. Hidden (display:none) elements are already excluded by Cytoscape
    // itself, so the export naturally reflects whatever filters are active.
    const exportBtn = controls.querySelector(".need-graph-export-png");
    if (exportBtn) {
      exportBtn.addEventListener("click", () => {
        const dataUrl = cy.png({ full: true, scale: 2, bg: "#ffffff" });
        const link = document.createElement("a");
        link.href = dataUrl;
        link.download = (container.id || "graph") + ".png";
        document.body.appendChild(link);
        link.click();
        link.remove();
      });
    }

    // Color by attribute ----------------------------------------------------
    const colorSelect = controls.querySelector("[data-need-graph-color]");
    const preferred = colorSelect && colorSelect.value;
    const applyColorSel = () => applyColorBy(cy, preferred);
    if (colorSelect) {
      colorSelect.addEventListener("change", () => {
        applyColorBy(cy, colorSelect.value);
        announce(status, "Colored nodes by " + (colorSelect.value === "none" ? "no attribute" : colorSelect.value));
      });
    }
    applyColorSel();

    // Selection / path highlight + node popup --------------------------------
    const showPopup = (event, node) => {
      if (!canvasRoot) return;
      canvasRoot.querySelectorAll(".need-graph-popup").forEach((popup) => popup.remove());
      canvasRoot.appendChild(buildNodePopup(node));
      const popup = canvasRoot.querySelector(".need-graph-popup");
      // `renderedPosition` is not guaranteed on the tap event, so fall back to
      // the node's own rendered position within the canvas. Note: we deliberately
      // avoid `event.position` here — it is in model (abstract) coordinates, not
      // canvas pixels, so using it as a CSS offset would place the popup far
      // outside the visible canvas.
      const at =
        (event && event.renderedPosition) ||
        (typeof node.renderedPosition === "function" && node.renderedPosition()) ||
        { x: 60, y: 60 };
      // The canvas clips its contents (overflow hidden), so keep the popup fully
      // within the visible area by clamping to the canvas bounds.
      const padding = 8;
      const canvasRect = canvasRoot.getBoundingClientRect();
      const popupWidth = popup.offsetWidth || 220;
      const popupHeight = popup.offsetHeight || 160;
      const left = Math.max(padding, Math.min(at.x, canvasRect.width - popupWidth - padding));
      const top = Math.max(padding, Math.min(at.y, canvasRect.height - popupHeight - padding));
      popup.style.left = left + "px";
      popup.style.top = top + "px";
      const close = popup.querySelector(".need-graph-popup-close");
      if (close) {
        close.addEventListener("click", (e) => { e.stopPropagation(); hidePopup(); });
      }
      lastPopupAt = Date.now();
    };
    cy.on("tap", "node", (event) => {
      const node = event.target;
      cy.elements().removeClass("selected-highlight");
      node.closedNeighborhood().addClass("neighbour-highlight");
      announce(status, `Selected ${node.id()}`);
      highlightPath(cy, node.id(), projection.view.originId || node.id());
      showPopup(event, node);
    });
    cy.on("tap", "background", hidePopupOnBackground);
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") hidePopup();
    });

    // Keyboard-focus the canvas is handled by Cytoscape's own tabindex; keep
    // the semantic table as the primary operable representation.
    if (table) {
      table.setAttribute("aria-hidden", "false");
    }
    if (canvasRoot) {
      canvasRoot.setAttribute("aria-hidden", "true");
      clearLoading(canvasRoot);
      // Prevent wheel/trackpad/pinch gestures over the graph from scrolling the
      // page underneath while zooming. Cytoscape consumes the wheel for its own
      // zoom, but without preventDefault the event still bubbles and scrolls
      // the document.
      const blockPageScroll = (event) => event.preventDefault();
      canvasRoot.addEventListener("wheel", blockPageScroll, { passive: false });
      canvasRoot.addEventListener("touchmove", blockPageScroll, { passive: false });
    }

    announce(status, `Interactive graph ready (${projection.nodes.length} nodes, ${projection.edges.length} edges)`);
    return cy;
  }

  function enhance(container) {
    const statusEl = container.querySelector("[data-need-graph-status]");
    try {
      const projection = dataFor(container);
      const error = validateProjection(projection);
      if (error || !projection) {
        announce(statusEl, "Interactive graph unavailable: " + (error || "missing projection"));
        return;
      }
      if (!window.cytoscape) {
        announce(statusEl, "Interactive graph unavailable: Cytoscape failed to load");
        return;
      }
      const canvasRoot = container.querySelector("[data-need-graph-canvas]");
      if (!canvasRoot) {
        announce(statusEl, "Interactive graph unavailable: canvas missing");
        return;
      }
      buildGraph(container, projection);
    } catch (err) {
      const canvasRoot = container.querySelector("[data-need-graph-canvas]");
      clearLoading(canvasRoot);
      announce(statusEl, "Interactive graph unavailable: " + (err && err.message ? err.message : String(err)));
    }
  }

  function onReady() {
    document.querySelectorAll("[data-need-graph]").forEach(enhance);
  }

  // Bind once the DOM is complete. Handles both synchronous head scripts (which
  // finish before DOMContentLoaded) and late/injected scripts (which may run
  // after the event already fired).
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", onReady);
  } else {
    onReady();
  }
})();
