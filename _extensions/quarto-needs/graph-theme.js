(() => {
  if (window.__quartoNeedsGraphThemeInstalled) return;
  window.__quartoNeedsGraphThemeInstalled = true;

  const canvases = () => document.querySelectorAll("[data-need-graph-canvas]");

  function rgb(value) {
    const match = String(value || "").match(/rgba?\(\s*([\d.]+)[, ]+\s*([\d.]+)[, ]+\s*([\d.]+)/i);
    return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : null;
  }

  function isDark(canvas) {
    const sample = rgb(getComputedStyle(canvas).backgroundColor);
    if (!sample) {
      return document.documentElement.getAttribute("data-bs-theme") === "dark";
    }
    const [r, g, b] = sample.map((channel) => channel / 255);
    const linear = (channel) => channel <= 0.04045
      ? channel / 12.92
      : Math.pow((channel + 0.055) / 1.055, 2.4);
    const luminance = 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
    return luminance < 0.35;
  }

  function apply(canvas) {
    const cy = canvas.__quartoNeedsCy;
    if (!cy || typeof cy.style !== "function") return false;

    const dark = isDark(canvas);
    const edge = dark ? "#b8c2cc" : "#64748b";
    const label = dark ? "#f1f5f9" : "#1f2937";
    const labelBackground = dark ? "#212529" : "#ffffff";

    cy.style()
      .selector("node")
      .style({ color: label })
      .selector("edge")
      .style({
        "line-color": edge,
        "target-arrow-color": edge,
        color: label,
        "text-background-color": labelBackground,
        "text-background-opacity": dark ? 0.88 : 0.72,
      })
      .selector("edge[pathMember = 'true']")
      .style({
        "line-color": dark ? "#f59e0b" : "#b45309",
        "target-arrow-color": dark ? "#f59e0b" : "#b45309",
        width: 3,
      })
      .update();
    return true;
  }

  function refresh(attempt = 0) {
    let pending = false;
    canvases().forEach((canvas) => {
      if (!apply(canvas)) pending = true;
    });
    if (pending && attempt < 12) {
      setTimeout(() => refresh(attempt + 1), 50 * (attempt + 1));
    }
  }

  function scheduleRefresh() {
    requestAnimationFrame(() => requestAnimationFrame(() => refresh()));
  }

  function install() {
    refresh();

    const observer = new MutationObserver(scheduleRefresh);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "style", "data-bs-theme"],
    });
    if (document.body) {
      observer.observe(document.body, {
        attributes: true,
        attributeFilter: ["class", "style", "data-bs-theme"],
      });
    }

    document.addEventListener("click", (event) => {
      if (event.target && event.target.closest && event.target.closest(".quarto-color-scheme-toggle")) {
        setTimeout(scheduleRefresh, 0);
        setTimeout(scheduleRefresh, 120);
      }
    }, true);
    document.addEventListener("quarto:themeChanged", scheduleRefresh);

    const media = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
    if (media && typeof media.addEventListener === "function") {
      media.addEventListener("change", scheduleRefresh);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
