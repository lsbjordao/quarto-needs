// The `need-graph` deep-linking and saved-exploration-state client.
//
// Reads and drives the SAME controls graph-explore.js/graph-modes.js
// already own — a select's `.value` + a dispatched "change" event, a
// checkbox's `.checked` + "change", the "quarto-needs-node-focus" custom
// event, and the path buttons' own click handlers — rather than exposing
// a second, parallel state API those modules would have to keep in sync.
// Restoring a path replays the same two-click, two-focus sequence a
// reader would perform by hand.
(() => {
  if (window.__quartoNeedsGraphStateInstalled) return;
  window.__quartoNeedsGraphStateInstalled = true;

  const DEBOUNCE_MS = 400;
  const STORAGE_PREFIX = "quarto-needs-graph-state:";

  function currentHashParams() {
    return new URLSearchParams(String(location.hash || "").replace(/^#/, ""));
  }

  function readHashState(instanceId) {
    const raw = currentHashParams().get(instanceId);
    if (!raw) return null;
    try {
      return JSON.parse(decodeURIComponent(raw));
    } catch (_error) {
      return null;
    }
  }

  function writeHashState(instanceId, state) {
    const params = currentHashParams();
    params.set(instanceId, encodeURIComponent(JSON.stringify(state)));
    history.replaceState(null, "", "#" + params.toString());
  }

  function clearHashState(instanceId) {
    const params = currentHashParams();
    if (!params.has(instanceId)) return;
    params.delete(instanceId);
    const rest = params.toString();
    history.replaceState(null, "", rest ? "#" + rest : location.pathname + location.search);
  }

  function readStoredState(instanceId) {
    try {
      const raw = localStorage.getItem(STORAGE_PREFIX + instanceId);
      return raw ? JSON.parse(raw) : null;
    } catch (_error) {
      return null;
    }
  }

  function writeStoredState(instanceId, state) {
    try {
      localStorage.setItem(STORAGE_PREFIX + instanceId, JSON.stringify(state));
    } catch (_error) {
      // Private browsing, quota, or a disabled store — persistence is a
      // convenience, never a hard requirement.
    }
  }

  function clearStoredState(instanceId) {
    try {
      localStorage.removeItem(STORAGE_PREFIX + instanceId);
    } catch (_error) {
      // See writeStoredState.
    }
  }

  function fieldValue(controls, selector) {
    const el = controls.querySelector(selector);
    return el ? el.value : "";
  }

  function readCurrentState(container, controls) {
    return {
      type: fieldValue(controls, '[data-need-graph-explore="type"]'),
      status: fieldValue(controls, '[data-need-graph-explore="status"]'),
      family: fieldValue(controls, '[data-need-graph-explore="family"]'),
      profile: fieldValue(controls, '[data-need-graph-explore="profile"]'),
      search: fieldValue(controls, ".need-graph-search"),
      mode: fieldValue(controls, '[data-need-graph-modes="mode"]'),
      affected: !!(controls.querySelector('[data-need-graph-modes="affected"]') || {}).checked,
      focus: container.__needGraphFocusNode || null,
      path: container.__needGraphActivePath || null,
    };
  }

  function setSelectValue(el, value) {
    if (!el || el.value === value) return;
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function setChecked(el, checked) {
    if (!el || el.checked === checked) return;
    el.checked = checked;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function setSearch(el, value) {
    if (!el || el.value === value) return;
    el.value = value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function focusNode(container, nodeId) {
    const contextApi = container.__needGraphContextApi;
    container.__needGraphFocusNode = nodeId;
    container.dispatchEvent(new CustomEvent("quarto-needs-node-focus", { detail: { nodeId } }));
    if (contextApi) contextApi.refresh();
  }

  // pathToRoot's own node list runs root-first, focus-last; shortestPath's
  // runs start-first, end-last — the two algorithms this state mirrors
  // already disagree on that order, so restoration must not assume one.
  function restorePath(container, controls, path) {
    if (!path || !path.kind || !path.nodes || !path.nodes.length) return;
    if (path.kind === "root") {
      const startId = path.nodes[path.nodes.length - 1];
      focusNode(container, startId);
      const pathButton = controls.querySelector(".need-graph-root-path");
      if (pathButton && !pathButton.disabled) pathButton.click();
      return;
    }
    if (path.kind === "between") {
      const startId = path.nodes[0];
      const endId = path.nodes[path.nodes.length - 1];
      focusNode(container, startId);
      const betweenButton = controls.querySelector(".need-graph-shortest-path");
      if (betweenButton && !betweenButton.disabled) betweenButton.click();
      focusNode(container, endId);
    }
  }

  function applyState(container, controls, state) {
    if (!state) return;
    setSelectValue(controls.querySelector('[data-need-graph-explore="profile"]'), state.profile || "");
    setSelectValue(controls.querySelector('[data-need-graph-explore="type"]'), state.type || "");
    setSelectValue(controls.querySelector('[data-need-graph-explore="status"]'), state.status || "");
    setSelectValue(controls.querySelector('[data-need-graph-explore="family"]'), state.family || "");
    setSearch(controls.querySelector(".need-graph-search"), state.search || "");
    setSelectValue(controls.querySelector('[data-need-graph-modes="mode"]'), state.mode || "");
    setChecked(controls.querySelector('[data-need-graph-modes="affected"]'), !!state.affected);
    if (state.focus) focusNode(container, state.focus);
    if (state.path) restorePath(container, controls, state.path);
  }

  function enhance(container) {
    if (!container || container.dataset.needGraphStateReady === "true") return false;
    const controls = container.querySelector("[data-need-graph-controls]");
    const contextApi = container.__needGraphContextApi;
    if (!controls || !contextApi) return false;
    container.dataset.needGraphStateReady = "true";

    const instanceId = container.id;
    if (!instanceId) return true;

    const hashState = readHashState(instanceId);
    const initial = hashState || readStoredState(instanceId);
    if (initial) applyState(container, controls, initial);

    let timer = null;
    const persist = () => {
      const state = readCurrentState(container, controls);
      writeHashState(instanceId, state);
      writeStoredState(instanceId, state);
    };
    const schedulePersist = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(persist, DEBOUNCE_MS);
    };

    ["type", "status", "family", "profile"].forEach((kind) => {
      const el = controls.querySelector(`[data-need-graph-explore="${kind}"]`);
      if (el) el.addEventListener("change", schedulePersist);
    });
    const search = controls.querySelector(".need-graph-search");
    if (search) search.addEventListener("input", schedulePersist);
    const modeEl = controls.querySelector('[data-need-graph-modes="mode"]');
    if (modeEl) modeEl.addEventListener("change", schedulePersist);
    const affectedEl = controls.querySelector('[data-need-graph-modes="affected"]');
    if (affectedEl) affectedEl.addEventListener("change", schedulePersist);
    container.addEventListener("quarto-needs-node-focus", schedulePersist);

    container.addEventListener("quarto-needs-context-reset", () => {
      clearHashState(instanceId);
      clearStoredState(instanceId);
    });

    return true;
  }

  function enhanceAll() {
    document.querySelectorAll("[data-need-graph]").forEach(enhance);
  }
  function schedule() {
    requestAnimationFrame(enhanceAll);
    setTimeout(enhanceAll, 150);
    setTimeout(enhanceAll, 600);
    setTimeout(enhanceAll, 1200);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule);
  else schedule();
})();
