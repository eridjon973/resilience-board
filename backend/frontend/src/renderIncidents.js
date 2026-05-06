function qs(id) {
  return document.getElementById(id);
}

function fmtSeconds(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }

  return `${Number(value).toFixed(2)}s`;
}

function normalizeList(payload, keys) {
  if (Array.isArray(payload)) return payload;

  for (const key of keys) {
    if (Array.isArray(payload?.[key])) return payload[key];
  }

  return [];
}

function appendCell(row, value, className = "") {
  const cell = document.createElement("td");

  if (className) {
    cell.className = className;
  }

  cell.textContent = String(value ?? "--");
  row.appendChild(cell);
}

export function renderIncidents(data) {
  const root = qs("incidentTableWrap");
  if (!root) return;

  const items = normalizeList(data, ["items", "incidents", "most_recent_incidents"]);

  root.replaceChildren();

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No incidents detected yet.";
    root.appendChild(empty);
    return;
  }

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");

  const headerRow = document.createElement("tr");
  const headers = [
    "Namespace",
    "Workload",
    "Deleted Pod",
    "Replacement Pod",
    "Recovery",
    "Correlation"
  ];

  for (const header of headers) {
    const th = document.createElement("th");
    th.textContent = header;
    headerRow.appendChild(th);
  }

  thead.appendChild(headerRow);

  for (const item of items) {
    const row = document.createElement("tr");

    appendCell(row, item.namespace);
    appendCell(row, item.workload);
    appendCell(row, item.deleted_pod ?? item.deleted_pod_name ?? item.deleted, "mono");
    appendCell(row, item.replacement_pod ?? item.replacement_pod_name ?? item.replacement, "mono");

    const recovery =
      item.recovery_time_seconds ??
      item.recovery_time ??
      item.recovery_seconds;

    appendCell(row, fmtSeconds(recovery));
    appendCell(row, item.correlation_id ?? item.correlation, "mono");

    tbody.appendChild(row);
  }

  table.appendChild(thead);
  table.appendChild(tbody);
  root.appendChild(table);
}
