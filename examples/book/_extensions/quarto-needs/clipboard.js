(() => {
  async function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(value);
        return true;
      } catch (_error) {}
    }
    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.setAttribute("aria-hidden", "true");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "0";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    const selection = document.getSelection();
    const previousRange = selection && selection.rangeCount ? selection.getRangeAt(0).cloneRange() : null;
    const active = document.activeElement;
    try { textarea.focus({ preventScroll: true }); } catch (_error) { textarea.focus(); }
    textarea.select();
    textarea.setSelectionRange(0, textarea.value.length);
    let copied = false;
    try { copied = document.execCommand("copy"); } catch (_error) { copied = false; }
    textarea.remove();
    if (active && typeof active.focus === "function") {
      try { active.focus({ preventScroll: true }); } catch (_error) { active.focus(); }
    }
    if (selection && previousRange) {
      selection.removeAllRanges();
      selection.addRange(previousRange);
    }
    return copied;
  }

  document.addEventListener("click", async (event) => {
    const target = event.target instanceof Element ? event.target : null;
    const button = target && target.closest(".need-graph-popup-copy");
    if (!button) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    const row = button.closest(".need-graph-popup-row");
    const valueNode = row && row.querySelector(".need-graph-popup-value");
    const value = valueNode && valueNode.textContent.trim();
    if (!value) return;
    const original = button.innerHTML;
    button.disabled = true;
    const copied = await copyText(value);
    if (copied) {
      button.classList.add("copied");
      button.innerHTML = "✓";
      button.title = `Copied ${value}`;
      button.setAttribute("aria-label", `Copied ${value}`);
    } else {
      button.classList.add("copy-failed");
      button.innerHTML = "!";
      button.title = `Could not copy ${value}`;
      button.setAttribute("aria-label", `Could not copy ${value}`);
    }
    window.setTimeout(() => {
      button.classList.remove("copied", "copy-failed");
      button.innerHTML = original;
      button.title = "Copy ID to clipboard";
      button.setAttribute("aria-label", "Copy ID to clipboard");
      button.disabled = false;
    }, 1200);
  }, true);
})();
