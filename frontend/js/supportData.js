import { escapeHtml, renderTable } from "./utils.js";

let supportId = 0;

function cleanValue(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "";
  if (Array.isArray(value)) return value.filter((item) => item !== null && item !== undefined).join(", ");
  if (typeof value === "object") {
    return Object.entries(value)
      .filter(([, item]) => item !== null && item !== undefined && !Number.isNaN(item))
      .map(([key, item]) => `${key}: ${cleanValue(item)}`)
      .join("；");
  }
  return String(value);
}

function hasSupportData(supportData) {
  return supportData && typeof supportData === "object" && Object.keys(supportData).length > 0;
}

function summaryMetrics(summary = {}) {
  const entries = Object.entries(summary).filter(([, value]) => cleanValue(value));
  if (!entries.length) return "";
  return `
    <div class="support-summary-grid">
      ${entries
        .map(
          ([key, value]) => `
            <article class="support-metric">
              <span>${escapeHtml(key)}</span>
              <strong>${escapeHtml(cleanValue(value))}</strong>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function supportTables(tables = []) {
  if (!Array.isArray(tables) || !tables.length) return "";
  return tables
    .filter((table) => Array.isArray(table.rows) && table.rows.length)
    .map(
      (table) => `
        <article class="support-card">
          <h4>${escapeHtml(table.title || "Evidence table")}</h4>
          <div class="support-table-wrapper">
            ${renderTable(table.rows, { limit: 10, columns: table.columns || undefined })}
          </div>
        </article>
      `,
    )
    .join("");
}

function scoreEvidence(scoreBreakdown = []) {
  if (!Array.isArray(scoreBreakdown) || !scoreBreakdown.length) return "";
  return `
    <article class="support-card">
      <h4>评分维度依据</h4>
      <div class="support-score-list">
        ${scoreBreakdown
          .map(
            (item) => `
              <div class="support-score-row">
                <strong>${escapeHtml(cleanValue(item.dimension))}</strong>
                <span>${escapeHtml(cleanValue(item.score))}</span>
                <p>${escapeHtml(cleanValue(item.basis))}</p>
                ${cleanValue(item.evidence) ? `<small>${escapeHtml(cleanValue(item.evidence))}</small>` : ""}
              </div>
            `,
          )
          .join("")}
      </div>
    </article>
  `;
}

function notesBlock(notes = []) {
  const fixed = "本区域展示的是后端数据分析函数返回的支撑信息。LLM 仅负责将结构化结果组织成自然语言，不直接生成核心统计数值、竞品排序或机会评分。";
  const allNotes = Array.isArray(notes) ? [...notes, fixed] : [fixed];
  return `
    <div class="support-note">
      ${allNotes.filter(Boolean).map((note) => `<p>${escapeHtml(note)}</p>`).join("")}
    </div>
  `;
}

export function renderSupportDataPanel(supportData, options = {}) {
  if (!hasSupportData(supportData)) return "";
  if (supportData.raw_csv) {
    return `
      <div class="support-panel-inner">
        <div class="support-panel-head">
          <span>Analysis Evidence</span>
          <strong>${escapeHtml(options.title || supportData.title || "分析支撑数据")}</strong>
        </div>
        ${summaryMetrics({
          ...(supportData.summary || {}),
          raw_rows: supportData.raw_csv.rows,
          raw_columns: supportData.raw_csv.columns?.length || 0,
        })}
        ${supportTables(supportData.tables)}
        <article class="support-card">
          <h4>原始 CSV</h4>
          <div class="actions-row">
            <a class="support-open-link" href="${escapeHtml(supportData.raw_csv.view_url || "/raw-data.html")}" target="_blank" rel="noreferrer">查看全部原始 CSV</a>
          </div>
        </article>
        ${notesBlock(supportData.notes)}
      </div>
    `;
  }
  return `
    <div class="support-panel-inner">
      <div class="support-panel-head">
        <span>Analysis Evidence</span>
        <strong>${escapeHtml(options.title || supportData.title || "分析支撑数据")}</strong>
      </div>
      ${summaryMetrics(supportData.summary)}
      ${scoreEvidence(supportData.score_breakdown)}
      ${supportTables(supportData.tables)}
      ${
        Array.isArray(supportData.used_sources)
          ? `<article class="support-card"><h4>使用的数据来源</h4><p>${escapeHtml(supportData.used_sources.join("、"))}</p></article>`
          : ""
      }
      ${notesBlock(supportData.notes)}
    </div>
  `;
}

export function renderSupportDataToggle(supportData, options = {}) {
  if (!hasSupportData(supportData)) {
    return options.showDisabled ? `<button class="support-toggle" disabled>暂无支撑数据</button>` : "";
  }
  const id = `support-panel-${supportId++}`;
  const label = options.label || "查看支撑数据";
  const closeLabel = options.closeLabel || label.replace("查看", "收起");
  return `
    <div class="support-block">
      <button class="support-toggle" type="button" aria-expanded="false" aria-controls="${id}" data-open-label="${escapeHtml(closeLabel)}" data-close-label="${escapeHtml(label)}">
        <span class="support-toggle-icon">▦</span>
        <span class="support-toggle-text">${escapeHtml(label)}</span>
        <span class="support-toggle-chevron">⌄</span>
      </button>
      <div id="${id}" class="support-panel" hidden>
        ${renderSupportDataPanel(supportData, options)}
      </div>
    </div>
  `;
}

export function toggleSupportPanel(buttonEl, panelEl) {
  if (!buttonEl || !panelEl) return;
  const willOpen = !buttonEl.classList.contains("is-open");
  buttonEl.classList.toggle("is-open", willOpen);
  panelEl.classList.toggle("is-open", willOpen);
  panelEl.hidden = !willOpen;
  buttonEl.setAttribute("aria-expanded", String(willOpen));
  const text = buttonEl.querySelector(".support-toggle-text");
  if (text) text.textContent = willOpen ? buttonEl.dataset.openLabel : buttonEl.dataset.closeLabel;
}

export function setupSupportDataToggles(root = document) {
  if (!root || root.dataset?.supportToggleReady === "true") return;
  if (root.dataset) root.dataset.supportToggleReady = "true";
  root.addEventListener("click", (event) => {
    const button = event.target.closest?.(".support-toggle");
    if (!button || button.disabled) return;
    const panel = root.querySelector(`#${button.getAttribute("aria-controls")}`);
    toggleSupportPanel(button, panel);
  });
}
