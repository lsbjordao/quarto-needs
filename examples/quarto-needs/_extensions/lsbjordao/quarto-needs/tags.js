// Tag index filtering: the ?tag=<slug> query parameter — what a clicked tag
// badge deep-links to — hides every need-tags table row whose badges do not
// carry that slug. Pure enhancement: without JS the page simply shows the
// full table. Rows are hidden with a class (not the `hidden` attribute) so
// need-table's search box, which owns `hidden` on the same rows, keeps
// composing with the tag filter instead of overwriting it.
(() => {
  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-need-tags]").forEach((root) => {
      const table = root.querySelector("table");
      if (!table) return;
      const status = root.querySelector(".need-tags-status");
      const clearChip = root.querySelector(".need-tag-chip-clear");
      const chips = root.querySelectorAll(".need-tag-chip[data-need-tag]");

      const rowTags = (row) => {
        const found = new Set();
        row.querySelectorAll(".need-tag").forEach((badge) => {
          badge.classList.forEach((cls) => {
            const match = cls.match(/^need-tag-(.+)$/);
            if (match) found.add(match[1]);
          });
        });
        return found;
      };

      const params = new URLSearchParams(window.location.search);
      const wanted = (params.get("tag") || "").trim().toLowerCase();
      if (wanted === "") {
        if (clearChip) clearChip.classList.add("need-tag-chip-active");
        return;
      }

      let shown = 0;
      let total = 0;
      Array.from(table.tBodies).forEach((body) => [...body.rows].forEach((row) => {
        total += 1;
        if (rowTags(row).has(wanted)) {
          shown += 1;
        } else {
          row.classList.add("need-tag-filtered");
        }
      }));

      chips.forEach((chip) => {
        const active = chip.dataset.needTag === wanted;
        chip.classList.toggle("need-tag-chip-active", active);
        if (active) chip.setAttribute("aria-current", "true");
      });

      if (status) {
        const template = shown === 0
          ? root.getAttribute("data-need-tags-zero") || ""
          : root.getAttribute("data-need-tags-filtered") || "";
        if (template !== "") {
          status.textContent = template
            .replace("{shown}", String(shown))
            .replace("{total}", String(total))
            .replace("{tag}", wanted);
        }
      }
    });
  });
})();
