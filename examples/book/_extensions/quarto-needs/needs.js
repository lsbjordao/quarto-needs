(() => {
  const normalize = (value) => value.trim().toLocaleLowerCase();
  const codeToken = /^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+$/;

  function markAtomicCodes(table) {
    table.querySelectorAll("a").forEach((link) => {
      const value = link.textContent.trim();
      if (!codeToken.test(value)) return;
      link.classList.add("need-code");
      link.style.setProperty("display", "inline-block", "important");
      link.style.setProperty("white-space", "nowrap", "important");
      link.style.setProperty("overflow-wrap", "normal", "important");
      link.style.setProperty("word-break", "keep-all", "important");
      link.style.setProperty("hyphens", "none", "important");
    });

    table.querySelectorAll(".need-badge").forEach((badge) => {
      badge.style.setProperty("white-space", "nowrap", "important");
      badge.style.setProperty("overflow-wrap", "normal", "important");
      badge.style.setProperty("word-break", "keep-all", "important");
      badge.style.setProperty("hyphens", "none", "important");
    });
  }

  function filterRows(table, query) {
    const needle = normalize(query);
    Array.from(table.tBodies).forEach((body) => [...body.rows].forEach((row) => {
      row.hidden = needle !== "" && !normalize(row.textContent).includes(needle);
    }));
  }

  function sortRows(table, index, ascending) {
    Array.from(table.tBodies).forEach((body) => {
      const rows = [...body.rows].sort((left, right) =>
        left.cells[index].textContent.trim().localeCompare(
          right.cells[index].textContent.trim(), undefined, {numeric: true}
        )
      );
      if (!ascending) rows.reverse();
      rows.forEach((row) => body.appendChild(row));
    });
  }

  function enhance(container) {
    const table = container.querySelector("table");
    if (!table) return;
    markAtomicCodes(table);
    let input = container.querySelector(".need-table-search");
    if (!input) {
      const searchBase = (table.id || "need-table") + "-search";
      let searchId = searchBase;
      let suffix = 2;
      while (document.getElementById(searchId)) {
        searchId = `${searchBase}-${suffix}`;
        suffix += 1;
      }
      const label = document.createElement("label");
      label.className = "visually-hidden";
      label.htmlFor = searchId;
      label.textContent = "Search needs";
      input = document.createElement("input");
      input.id = searchId;
      input.className = "need-table-search";
      input.type = "search";
      input.placeholder = "Search this table";
      container.insertBefore(label, table);
      container.insertBefore(input, table);
    }
    input.addEventListener("input", () => filterRows(table, input.value));
    table.querySelectorAll("thead th").forEach((header, index) => {
      const label = header.textContent;
      header.textContent = "";
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      header.setAttribute("aria-sort", "none");
      let ascending = true;
      button.addEventListener("click", () => {
        sortRows(table, index, ascending);
        table.querySelectorAll("thead th").forEach((other) => other.setAttribute("aria-sort", "none"));
        header.setAttribute("aria-sort", ascending ? "ascending" : "descending");
        ascending = !ascending;
      });
      header.appendChild(button);
    });
  }

  function rgb(value) {
    const match = String(value || "").match(/rgba?\(\s*([\d.]+)[, ]+\s*([\d.]+)[, ]+\s*([\d.]+)/i);
    return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : null;
  }

  function graphSurfaceIsDark(canvas) {
    const sample = rgb(getComputedStyle(canvas).backgroundColor);
    if (!sample) return document.documentElement.getAttribute("data-bs-theme") === "dark";
    const linear = (value) => {
      const channel = value / 255;
      return channel <= 0.04045 ? channel / 12.92 : Math.pow((channel + 0.055) / 1.055, 2.4);
    };
    const luminance = 0.2126 * linear(sample[0]) + 0.7152 * linear(sample[1]) + 0.0722 * linear(sample[2]);
    return luminance < 0.35;
  }

  function applyGraphTheme(canvas) {
    const cy = canvas.__quartoNeedsCy;
    if (!cy || typeof cy.style !== "function") return false;
    const dark = graphSurfaceIsDark(canvas);
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

  function refreshGraphThemes(attempt = 0) {
    let pending = false;
    document.querySelectorAll("[data-need-graph-canvas]").forEach((canvas) => {
      if (!applyGraphTheme(canvas)) pending = true;
    });
    if (pending && attempt < 12) {
      setTimeout(() => refreshGraphThemes(attempt + 1), 50 * (attempt + 1));
    }
  }

  function scheduleGraphThemeRefresh() {
    requestAnimationFrame(() => requestAnimationFrame(() => refreshGraphThemes()));
  }

  function installGraphThemeSync() {
    refreshGraphThemes();
    const observer = new MutationObserver(scheduleGraphThemeRefresh);
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
        setTimeout(scheduleGraphThemeRefresh, 0);
        setTimeout(scheduleGraphThemeRefresh, 120);
      }
    }, true);
    document.addEventListener("quarto:themeChanged", scheduleGraphThemeRefresh);
    const media = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
    if (media && typeof media.addEventListener === "function") {
      media.addEventListener("change", scheduleGraphThemeRefresh);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-need-table]").forEach(enhance);
    installGraphThemeSync();
  });
})();
