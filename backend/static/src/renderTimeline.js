import { fmtTime, normalizeList, qs } from "./utils.js";

function appendDiv(parent, className, value) {
  const div = document.createElement("div");
  div.className = className;
  div.textContent = String(value ?? "");
  parent.appendChild(div);
}

export function renderTimeline(data) {
  const root = qs("timeline");
  if (!root) return;

  const items = normalizeList(data, ["items", "events", "timeline"]);

  root.replaceChildren();

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No timeline events yet.";
    root.appendChild(empty);
    return;
  }

  for (const item of items) {
    const rawType = String(item.type ?? item.event_type ?? "").toLowerCase();
    const isChaos = rawType.includes("chaos");
    const isIncident = rawType.includes("incident") || rawType.includes("self");

    const title =
      item.title ??
      item.type ??
      item.event_type ??
      (isChaos ? "Chaos Event" : "Incident");

    const timestamp =
      item.timestamp ??
      item.created_at ??
      item.detected_at ??
      item.time;

    const detailParts = [];

    if (item.namespace) detailParts.push(`namespace=${item.namespace}`);
    if (item.workload) detailParts.push(`workload=${item.workload}`);
    if (item.pod_name) detailParts.push(`pod=${item.pod_name}`);
    if (item.deleted_pod) detailParts.push(`deleted=${item.deleted_pod}`);
    if (item.replacement_pod) detailParts.push(`replacement=${item.replacement_pod}`);
    if (item.status) detailParts.push(`status=${item.status}`);

    const row = document.createElement("div");
    row.className = `timeline-item ${isChaos ? "chaos" : isIncident ? "incident" : ""}`;

    appendDiv(row, "timeline-title", title);
    appendDiv(row, "timeline-meta", fmtTime(timestamp));
    appendDiv(row, "timeline-meta mono", detailParts.join(" | ") || "no details");

    root.appendChild(row);
  }
}
