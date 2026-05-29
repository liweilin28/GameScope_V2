import { getRawCsvText, getRawData } from "./api.js?v=20260529cachefix1";
import { escapeHtml, formatNumber } from "./utils.js?v=20260529cachefix1";

function metric(label, value) {
  return `<article class="metric-card"><span>${label}</span><strong>${value}</strong></article>`;
}

async function init() {
  const summaryEl = document.querySelector("#raw-summary");
  const rawEl = document.querySelector("#raw-table");
  rawEl.innerHTML = `<div class="empty-state">正在加载原始 CSV 数据...</div>`;

  try {
    const data = await getRawData(1);
    summaryEl.innerHTML = [
      metric("原始行数", formatNumber(data.rows)),
      metric("原始列数", formatNumber(data.columns?.length || 0)),
    ].join("");

    const csvText = await getRawCsvText();
    if (!csvText.trim()) {
      rawEl.innerHTML = `<div class="empty-state">暂无原始 CSV 数据。</div>`;
      return;
    }

    rawEl.innerHTML = `
      <pre class="raw-csv-pre"><code id="raw-csv-code"></code></pre>
    `;
    document.querySelector("#raw-csv-code").textContent = csvText;
  } catch (error) {
    summaryEl.innerHTML = "";
    rawEl.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "原始 CSV 数据加载失败。")}</div>`;
  }
}

init();
