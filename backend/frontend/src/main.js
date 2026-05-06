import { validateConfig } from "./config.js";
import { escapeHtml, fmtSeconds, qs, setText } from "./utils.js";

import { renderHealth } from "./renderHealth.js";
import { renderTimeline } from "./renderTimeline.js";
import { renderIncidents } from "./renderIncidents.js";

import { executeChaosKill, hideConfirmPanel, showConfirmPanel } from "./chaos.js";
import { initPolling, refreshDashboard, startPolling } from "./polling.js";

/* ---------- Error / Warning UI ---------- */

function showError(message) {
  const box = qs("errorBox");
  if (!box) return;

  box.textContent = message;
  box.style.display = "block";
}

function clearError() {
  const box = qs("errorBox");
  if (!box) return;

  box.textContent = "";
  box.style.display = "none";
}

function showWarning(failures) {
  const box = qs("warningBox");
  if (!box) return;

  if (!failures.length) {
    box.replaceChildren();
    box.style.display = "none";
    return;
  }

  const wrapper = document.createElement("div");
  wrapper.textContent = "Partial failure:";

  const list = document.createElement("ul");

  for (const failure of failures) {
    const item = document.createElement("li");

    const name = document.createElement("strong");
    name.textContent = String(failure.name ?? "unknown");

    item.appendChild(name);
    item.appendChild(
      document.createTextNode(` stale: ${String(failure.message ?? "unknown error")}`)
    );

    list.appendChild(item);
  }

  box.replaceChildren(wrapper, list);
  box.style.display = "block";
}

/* ---------- Summary Renderer ---------- */

function renderSummary(data) {
  setText("incidentCount", data?.incidents_total ?? data?.total_incidents ?? "--");
  setText("chaosCount", data?.chaos_total ?? data?.total_chaos ?? data?.total_chaos_experiments ?? "--");

  const avg =
    data?.average_recovery_time ??
    data?.avg_recovery_time ??
    data?.average_recovery_seconds ??
    data?.avg_recovery_seconds;

  setText("avgRecovery", avg !== undefined ? fmtSeconds(avg) : "--");

  if (data?.watcher || data?.watcher_status) {
    setText("watcherRestarts", data?.watcher?.restart_count ?? data?.watcher_status?.restart_count ?? "--");
  }
}

/* ---------- Events ---------- */

function bindEvents() {
  qs("armChaosBtn")?.addEventListener("click", showConfirmPanel);
  qs("cancelKillBtn")?.addEventListener("click", hideConfirmPanel);

  qs("confirmKillBtn")?.addEventListener("click", () => {
    executeChaosKill(refreshDashboard, showError, showWarning);
  });

  qs("refreshBtn")?.addEventListener("click", () => {
    hideConfirmPanel();
    refreshDashboard();
  });
}

/* ---------- Init ---------- */

function init() {
  validateConfig(showWarning);

  initPolling({
    renderHealth,
    renderSummary,
    renderTimeline,
    renderIncidents,
    showError,
    clearError,
    showWarning
  });

  bindEvents();

  refreshDashboard();
  startPolling();
}

init();
