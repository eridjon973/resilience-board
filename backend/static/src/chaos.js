import { getJson } from "./api.js";
import { CONFIG } from "./config.js";
import { startPolling, stopPolling } from "./polling.js";
import { state } from "./state.js";
import { qs, setText } from "./utils.js";

function clearChaosTimers() {
  for (const timer of state.chaosTimers) {
    clearTimeout(timer);
  }

  state.chaosTimers = [];
}

function schedule(delayMs, fn) {
  const timer = setTimeout(async () => {
    state.chaosTimers = state.chaosTimers.filter((id) => id !== timer);

    try {
      await fn();
    } catch {
      // Refresh failures are already handled by refreshFn/showWarning.
      // Do not break the chaos recovery schedule.
    }
  }, delayMs);

  state.chaosTimers.push(timer);
}

export function hideConfirmPanel() {
  state.confirmArmed = false;

  const panel = qs("confirmPanel");
  if (panel) panel.classList.remove("active");

  const armBtn = qs("armChaosBtn");
  if (armBtn && !state.chaosInProgress) {
    armBtn.focus();
  }
}

export function showConfirmPanel() {
  const remaining = state.chaosCooldownUntil - Date.now();

  if (state.chaosInProgress || remaining > 0) return;

  state.confirmArmed = true;

  const panel = qs("confirmPanel");
  if (panel) panel.classList.add("active");

  const confirmBtn = qs("confirmKillBtn");
  if (confirmBtn) confirmBtn.focus();
}

function updateCooldownUI() {
  const remaining = Math.max(0, state.chaosCooldownUntil - Date.now());

  const armBtn = qs("armChaosBtn");
  const confirmBtn = qs("confirmKillBtn");

  if (remaining <= 0 && !state.chaosInProgress) {
    if (armBtn) armBtn.disabled = false;
    if (confirmBtn) confirmBtn.disabled = false;
    setText("chaosNote", "Chaos cooldown: idle");
    return;
  }

  if (armBtn) armBtn.disabled = true;
  if (confirmBtn) confirmBtn.disabled = true;

  setText("chaosNote", `Chaos cooldown: ${Math.ceil(remaining / 1000)}s`);

  setTimeout(updateCooldownUI, 250);
}

export async function executeChaosKill(refreshFn, showError, showWarning) {
  if (state.chaosInProgress) return;

  const remaining = state.chaosCooldownUntil - Date.now();

  if (remaining > 0) {
    showWarning([
      {
        name: "chaos",
        message: `Cooldown active (${Math.ceil(remaining / 1000)}s)`
      }
    ]);
    return;
  }

  try {
    state.chaosInProgress = true;
    state.chaosCooldownUntil = Date.now() + CONFIG.chaosCooldownMs;

    hideConfirmPanel();
    clearChaosTimers();
    stopPolling();

    const armBtn = qs("armChaosBtn");
    const refreshBtn = qs("refreshBtn");
    const confirmBtn = qs("confirmKillBtn");

    if (armBtn) {
      armBtn.disabled = true;
      armBtn.textContent = "Killing Pod...";
    }

    if (refreshBtn) refreshBtn.disabled = true;
    if (confirmBtn) confirmBtn.disabled = true;

    setText("chaosNote", "Chaos action running...");

    await getJson("/chaos/kill-pod", { method: "POST" });

    await refreshFn();

    schedule(2500, refreshFn);
    schedule(6000, refreshFn);
    schedule(10000, async () => {
      await refreshFn();
      startPolling();
    });
  } catch (error) {
    showError(error instanceof Error ? error.message : String(error));
    startPolling();
  } finally {
    state.chaosInProgress = false;

    const armBtn = qs("armChaosBtn");
    const refreshBtn = qs("refreshBtn");

    if (armBtn) {
      armBtn.textContent = "Kill Random Pod";
    }

    if (refreshBtn) {
      refreshBtn.disabled = false;
    }

    updateCooldownUI();
  }
}
