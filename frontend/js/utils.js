export function showToast(message) {
  const root = document.querySelector("#toast-root");
  if (!root) return;
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = message;
  root.appendChild(node);
  window.setTimeout(() => node.remove(), 3600);
}

export function setLoading(isLoading) {
  const loading = document.querySelector("#loading");
  if (loading) loading.classList.toggle("hidden", !isLoading);
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function renderTable(records, options = {}) {
  const rows = Array.isArray(records) ? records : [];
  const limit = options.limit || rows.length;
  const visibleRows = rows.slice(0, limit);
  const columns = options.columns || Array.from(new Set(visibleRows.flatMap((row) => Object.keys(row || {}))));
  const className = options.className ? ` ${escapeHtml(options.className)}` : "";

  if (!visibleRows.length || !columns.length) {
    return `<div class="empty-state">${escapeHtml(options.emptyText || "暂无数据。")}</div>`;
  }

  const head = columns.map((column) => `<th class="col-${escapeHtml(column)}">${escapeHtml(column)}</th>`).join("");
  const body = visibleRows
    .map((row) => {
      const cells = columns
        .map((column) => {
          const raw = row?.[column];
          const value = Array.isArray(raw) ? raw.join(", ") : raw;
          return `<td class="col-${escapeHtml(column)}">${escapeHtml(value ?? "")}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  return `
    <div class="table-wrap${className}">
      <table class="data-table">
        <thead><tr>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

export function renderTableFromPayload(table, options = {}) {
  if (!table || !Array.isArray(table.rows)) {
    return `<div class="empty-state">暂无数据。</div>`;
  }
  return renderTable(table.rows, { ...options, columns: table.columns || options.columns });
}

export function renderList(items, keyName = null) {
  const values = Array.isArray(items) ? items : [];
  if (!values.length) return `<div class="empty-state">暂无数据。</div>`;
  return `
    <div class="tag-cloud">
      ${values
        .map((item) => {
          const text = keyName ? item[keyName] : item;
          return `<span class="tag">${escapeHtml(text)}</span>`;
        })
        .join("")}
    </div>
  `;
}

export function renderMarkdown(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const html = [];
  let inList = false;
  const closeList = () => {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      closeList();
      continue;
    }
    if (line.startsWith("### ")) {
      closeList();
      html.push(`<h4>${escapeHtml(line.slice(4))}</h4>`);
    } else if (line.startsWith("## ")) {
      closeList();
      html.push(`<h3>${escapeHtml(line.slice(3))}</h3>`);
    } else if (line.startsWith("# ")) {
      closeList();
      html.push(`<h2>${escapeHtml(line.slice(2))}</h2>`);
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${escapeHtml(line.slice(2))}</li>`);
    } else {
      closeList();
      html.push(`<p>${escapeHtml(line)}</p>`);
    }
  }
  closeList();
  return html.join("");
}

export function readCsvList(value) {
  const text = String(value || "").trim();
  if (!text) return null;
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}
