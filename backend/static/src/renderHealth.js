import { CONFIG } from "./config.js";

function qs(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  const el = qs(id);
  if (el) el.textContent = value;
}

function setHealthVisual(score, status) {
  const scoreEl = qs("healthScore");
  const badge = qs("healthBadge");

  if (!scoreEl || !badge) return;

  scoreEl.classList.remove("good", "warn", "bad");

  const numeric = Number(score);

  if (!Number.isFinite(numeric)) {
    badge.className = "badge yellow";
    badge.textContent = status || "unknown";
    return;
  }

  if (numeric >= CONFIG.healthThresholdGood) {
    scoreEl.classList.add("good");
    badge.className = "badge green";
  } else if (numeric >= CONFIG.healthThresholdWarn) {
    scoreEl.classList.add("warn");
    badge.className = "badge yellow";
  } else {
    scoreEl.classList.add("bad");
    badge.className = "badge red";
  }

  badge.textContent = status || "unknown";
}

function renderWatcherStatus(watcher) {
  const badge = qs("watcherBadge");

  if (!badge) return;

  if (!watcher) {
    badge.className = "badge yellow";
    badge.textContent = "watcher: unknown";
    setText("watcherRestarts", "--");
    return;
  }

  if (watcher.running) {
    badge.className = "badge green";
    badge.textContent = "watcher: running";
  } else {
    badge.className = "badge red";
    badge.textContent = "watcher: stopped";
  }

  setText("watcherRestarts", watcher.restart_count ?? "--");
}

export function renderHealth(data) {
  const score = data?.score ?? data?.health_score ?? "--";
  const status = data?.status ?? "UNKNOWN";
  const reasons = Array.isArray(data?.reasons) ? data.reasons : [];

  setText("healthScore", score);
  setText("healthStatus", status);
  setHealthVisual(score, status);

  const list = qs("healthReasons");
  if (!list) return;

  list.innerHTML = "";

  if (reasons.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No health reasons returned.";
    list.appendChild(li);
  } else {
    for (const reason of reasons) {
      const li = document.createElement("li");
      li.textContent = reason;
      list.appendChild(li);
    }
  }

  renderWatcherStatus(data?.watcher ?? data?.watcher_status);
}
