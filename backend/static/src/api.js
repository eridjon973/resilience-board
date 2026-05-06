import { CONFIG } from "./config.js";

function classifyHttpStatus(status) {
  if (status === 404) return "Endpoint not found";
  if (status >= 500) return "Backend server error";
  if (status >= 400) return "Bad request";
  return "Request failed";
}

export async function getJson(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), CONFIG.requestTimeoutMs);

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  try {
    const response = await fetch(CONFIG.apiBaseUrl + path, {
      ...options,
      headers,
      signal: controller.signal
    });

    if (!response.ok) {
      const text = await response.text();

      throw new Error(
        `${classifyHttpStatus(response.status)}: ${path} returned ${response.status}. ${text}`
      );
    }
   if (response.status === 204) return null;
    return await response.json();
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error(`Request timeout after ${CONFIG.requestTimeoutMs / 1000}s`);
    }

    if (error instanceof TypeError) {
      throw new Error(
        `Network failure while calling ${path}. Backend may be down, unreachable, or blocked by CORS.`
      );
    }

    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function safeFetch(name, path, options = {}) {
  try {
    const data = await getJson(path, options);
    return { name, ok: true, data };
  } catch (error) {
    return {
      name,
      ok: false,
      error: error instanceof Error ? error : new Error(String(error))
    };
  }
}
