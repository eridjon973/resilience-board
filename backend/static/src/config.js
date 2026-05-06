const API_BASE_URL = (
  window.__API_BASE_URL__ ||
  window.location.origin
).replace(/\/$/, "");

export const CONFIG = {
  apiBaseUrl: API_BASE_URL,

  env: window.__APP_ENV__ || "dev",
  clusterName: "resilience-board",

  pollIntervalMs: 5000,
  chaosCooldownMs: 12000,
  requestTimeoutMs: 8000,

  healthThresholdGood: 85,
  healthThresholdWarn: 60
};

export function validateConfig(showWarning) {
  const warnings = [];

  if (!CONFIG.apiBaseUrl) {
    warnings.push({
      name: "config",
      message: "apiBaseUrl is not set. Backend requests will fail."
    });
  }

  if (location.protocol === "file:") {
    warnings.push({
      name: "config",
      message: "Running from file://. Use FastAPI or a local server."
    });
  }

  if (!["dev", "staging", "prod"].includes(CONFIG.env)) {
    warnings.push({
      name: "config",
      message: `Unknown environment "${CONFIG.env}". Expected dev, staging, or prod.`
    });
  }

  if (warnings.length > 0) {
    showWarning(warnings);
  }
}
