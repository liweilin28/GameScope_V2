import { getRawData } from "./api.js";
import { formatNumber, renderTable } from "./utils.js";

function metric(label, value) {
  return `<article class="metric-card"><span>${label}</span><strong>${value}</strong></article>`;
}

async function init() {
  try {
    const data = await getRawData(0);
    document.querySelector("#raw-summary").innerHTML = [
      metric("原始行数", formatNumber(data.rows)),
      metric("原始列数", formatNumber(data.columns?.length || 0)),
    ].join("");
    document.querySelector("#raw-table").innerHTML = renderTable(data.preview || [], {
      limit: data.preview?.length || 0,
      columns: data.columns,
      emptyText: "暂无原始 CSV 数据。",
    });
  } catch (error) {
    document.querySelector("#raw-table").innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

init();
