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

  document.addEventListener("DOMContentLoaded", () => document.querySelectorAll("[data-need-table]").forEach(enhance));
})();
