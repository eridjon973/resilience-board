import { safeFetch } from "./api.js";
import { CONFIG } from "./config.js";
import { state } from "./state.js";
import { setText, qs } from "./utils.js";

let renderHealth;
let renderSummary;
let renderTimeline;
let renderIncidents;
let showError;
let clearError;
let showWarning;

export function initPolling(deps) {
  renderHealth = deps.renderHealth;
  renderSummary = deps.renderSummary;
  renderTimeline = deps.renderTimeline;
  renderIncidents = deps.renderIncidents;
  showError = deps.showError;
  clearError = deps.clearError;
  showWarning = deps.showWarning;
}

function setPollingState(status) {
  const badge = qs("pollBadge");
  if (!badge) return;

  if (status === "updating") {
    badge.className = "badge blue";
    badge.textContent = "polling: updating";
    return;
  }

  if (status === "paused") {
    badge.className = "badge yellow";
    badge.textContent = "polling: paused";
    return;
  }

  badge.className = "badge green";
  badge.textContent = "polling: active";
}

export function startPolling() {
  stopPolling();
  state.pollTimer = setInterval(refreshDashboard, CONFIG.pollIntervalMs);
  setPollingState("active");
}

export function stopPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }

  setPollingState("paused");
}

export async function refreshDashboard() {
  if (state.refreshInFlight) {
    state.refreshPending = true;
    return;
  }

  state.refreshInFlight = true;
  state.refreshPending = false;
  setPollingState("updating");

  try {
    const results = await Promise.all([
      safeFetch("health", "/health/score"),
      safeFetch("summary", "/metrics/summary"),
      safeFetch("timeline", "/timeline"),
      safeFetch("incidents", "/metrics/incidents")
    ]);

    const failures = [];

    for (const result of results) {
      if (!result.ok) {
        failures.push({
          name: result.name,
          message: result.error.message
        });
        continue;
      }

      if (result.name === "health") renderHealth(result.data);
      if (result.name === "summary") renderSummary(result.data);
      if (result.name === "timeline") renderTimeline(result.data);
      if (result.name === "incidents") renderIncidents(result.data);
    }

    showWarning(failures);

    if (failures.length === results.length) {
      showError("Full dashboard refresh failed. Backend may be down or unreachable.");
    } else {
      clearError();
    }

    setText("updatedBadge", `updated: ${new Date().toLocaleTimeString()}`);
  } finally {
    state.refreshInFlight = false;
    setPollingState(state.pollTimer ? "active" : "paused");

    if (state.refreshPending) {
      state.refreshPending = false;
      setTimeout(refreshDashboard, 250);
    }
  }
}
