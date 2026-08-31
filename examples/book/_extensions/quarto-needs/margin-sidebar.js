(() => {
  const KEY = "quarto-needs:margin-sidebar-collapsed";
  const CLASS = "qn-margin-sidebar-collapsed";
  const FORCED = "qn-margin-sidebar-forced-fullcontent";

  function readState() {
    try { return localStorage.getItem(KEY) === "true"; } catch (_) { return false; }
  }

  function writeState(value) {
    try { localStorage.setItem(KEY, value ? "true" : "false"); } catch (_) {}
  }

  function init() {
    const body = document.body;
    const margin = document.getElementById("quarto-margin-sidebar");
    if (!body || !margin || document.querySelector(".qn-margin-sidebar-toggle")) return;
    if (!margin.querySelector("nav[role='doc-toc'], #TOC")) return;

    const pt = (document.documentElement.lang || "").toLowerCase().startsWith("pt");
    const collapseLabel = pt ? "Recolher índice desta página" : "Collapse page table of contents";
    const expandLabel = pt ? "Expandir índice desta página" : "Expand page table of contents";
    const originallyFull = body.classList.contains("fullcontent");

    const button = document.createElement("button");
    button.type = "button";
    button.className = "qn-margin-sidebar-toggle";
    button.setAttribute("aria-controls", "quarto-margin-sidebar");
    button.innerHTML = '<span class="qn-margin-sidebar-toggle-icon" aria-hidden="true"></span>';
    body.appendChild(button);

    function position(collapsed) {
      if (collapsed) {
        button.style.left = "auto";
        button.style.right = "0.75rem";
      } else {
        const rect = margin.getBoundingClientRect();
        const gap = 8;
        button.style.right = "auto";
        // Keep the control entirely outside the margin sidebar. The old
        // half-width offset put half the button over the TOC title/items.
        button.style.left = `${Math.max(8, Math.round(rect.left - button.offsetWidth - gap))}px`;
      }
    }

    function apply(collapsed, persist) {
      body.classList.toggle(CLASS, collapsed);
      margin.setAttribute("aria-hidden", collapsed ? "true" : "false");

      if (collapsed && !originallyFull) {
        body.classList.add("fullcontent", FORCED);
      } else if (!collapsed && body.classList.contains(FORCED)) {
        body.classList.remove("fullcontent", FORCED);
      }

      button.dataset.state = collapsed ? "collapsed" : "expanded";
      button.setAttribute("aria-expanded", collapsed ? "false" : "true");
      button.setAttribute("aria-label", collapsed ? expandLabel : collapseLabel);
      button.title = collapsed ? expandLabel : collapseLabel;
      position(collapsed);
      if (persist) writeState(collapsed);
      window.dispatchEvent(new Event("resize"));
    }

    apply(readState(), false);
    button.addEventListener("click", () => apply(!body.classList.contains(CLASS), true));
    window.addEventListener("resize", () => position(body.classList.contains(CLASS)));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
