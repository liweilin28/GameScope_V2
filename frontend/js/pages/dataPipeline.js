import { getCleaningReport, getDataPreview, getDataStatus, uploadDataFile } from "../api.js";
import { escapeHtml, renderList, renderTable, showToast } from "../utils.js";

export function renderDataPipeline() {
  return `
    <section class="section">
      <div class="page-head">
        <div>
          <p class="eyebrow">数据流程</p>
          <h2>数据读取与清洗</h2>
          <p>展示默认数据状态、多格式数据上传、字段兼容、缺失值和清洗报告。</p>
        </div>
        <label class="upload-button">
          上传数据文件
          <input id="data-file-upload" type="file" accept=".csv,.tsv,.xlsx,.json,text/csv,text/tab-separated-values,application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" hidden />
        </label>
      </div>

      <div id="pipeline-alert"></div>
      <div class="grid-3" id="pipeline-summary"></div>

      <article class="card">
        <h3>上传说明</h3>
        <div class="stack">
          <p>本系统支持 CSV、TSV、XLSX、JSON 数据文件上传。</p>
          <p>后续分析主要面向 Steam 游戏数据字段，如果缺少 name、price、genres、tags、positive_reviews、negative_reviews 等字段，会在字段兼容性检查中提示。</p>
        </div>
      </article>

      <div class="card">
        <div class="card-title-row">
          <h3>字段名</h3>
          <span class="muted">清洗后字段</span>
        </div>
        <div id="pipeline-fields"></div>
      </div>

      <div class="grid-2">
        <article class="card">
          <h3>原始数据预览</h3>
          <div id="raw-preview"></div>
        </article>
        <article class="card">
          <h3>清洗后数据预览</h3>
          <div id="cleaned-preview"></div>
        </article>
      </div>

      <div class="grid-2">
        <article class="card">
          <h3>缺失值概览</h3>
          <div id="missing-report"></div>
        </article>
        <article class="card">
          <h3>字段兼容性检查</h3>
          <div id="field-report"></div>
        </article>
      </div>

      <article class="card">
        <h3>清洗报告</h3>
        <div id="cleaning-report"></div>
      </article>
    </section>
  `;
}

function summaryCard(label, value, note = "") {
  return `
    <article class="metric-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      ${note ? `<small>${escapeHtml(note)}</small>` : ""}
    </article>
  `;
}

function warningCard(message) {
  return `<div class="notice warning"><strong>提示</strong><span>${escapeHtml(message)}</span></div>`;
}

async function refreshPipeline() {
  const status = await getDataStatus();
  const statusData = status || null;
  const [preview, report] = await Promise.allSettled([getDataPreview(), getCleaningReport()]);
  const previewData = preview.status === "fulfilled" ? preview.value : null;
  const reportData = report.status === "fulfilled" ? report.value : null;

  document.querySelector("#pipeline-alert").innerHTML = statusData?.default_data_exists
    ? ""
    : warningCard("默认数据文件 data/sample/sample_steam_games.csv 暂不存在。你仍然可以上传 CSV、TSV、XLSX 或 JSON 进行演示。");

  document.querySelector("#pipeline-summary").innerHTML = [
    summaryCard("当前数据来源", statusData?.source_name || "未加载数据"),
    summaryCard("默认数据", statusData?.default_data_exists ? "已找到" : "未找到", statusData?.default_data_path || ""),
    summaryCard("当前数据量", `${statusData?.rows || 0} 行`, `${statusData?.columns?.length || 0} 列`),
  ].join("");

  const cleanedColumns = previewData?.cleaned?.columns || statusData?.columns || [];
  document.querySelector("#pipeline-fields").innerHTML = renderList(cleanedColumns);

  document.querySelector("#raw-preview").innerHTML = previewData
    ? `<p class="muted">${previewData.raw.rows} 行，${previewData.raw.columns.length} 列</p>${renderTable(previewData.raw.preview, { limit: 20, className: "wide-tags-table" })}`
    : `<div class="empty-state">暂无原始数据。</div>`;

  document.querySelector("#cleaned-preview").innerHTML = previewData
    ? `<p class="muted">${previewData.cleaned.rows} 行，${previewData.cleaned.columns.length} 列</p>${renderTable(previewData.cleaned.preview, { limit: 20 })}`
    : `<div class="empty-state">暂无清洗数据。</div>`;

  const missing = previewData?.missing_values || [];
  document.querySelector("#missing-report").innerHTML = renderTable(
    missing.filter((item) => item.missing_count > 0).slice(0, 20),
    {
      columns: ["field", "missing_count", "missing_ratio"],
      emptyText: "未发现明显缺失值。",
    },
  );

  const compatibility = previewData?.field_compatibility || reportData?.field_compatibility;
  document.querySelector("#field-report").innerHTML = compatibility
    ? `
      <div class="stack">
        <p><strong>可基础分析：</strong>${compatibility.can_basic_analyze ? "是" : "否"}</p>
        <p><strong>可价格分析：</strong>${compatibility.can_price_analyze ? "是" : "否"}</p>
        <p><strong>可评论分析：</strong>${compatibility.can_review_analyze ? "是" : "否"}</p>
        <p><strong>缺少核心字段：</strong>${escapeHtml((compatibility.missing_core_fields || []).join(", ") || "无")}</p>
        <p><strong>衍生字段：</strong>${escapeHtml((compatibility.available_derived_fields || []).join(", ") || "无")}</p>
      </div>
    `
    : `<div class="empty-state">暂无字段兼容报告。</div>`;

  const cleaning = reportData?.cleaning_report;
  document.querySelector("#cleaning-report").innerHTML = cleaning
    ? `
      <div class="grid-3">
        ${summaryCard("清洗前行数", cleaning.raw_rows ?? 0)}
        ${summaryCard("清洗后行数", cleaning.cleaned_rows ?? 0)}
        ${summaryCard("1000 行要求", reportData.meets_1000_rows ? "满足" : "未满足")}
      </div>
      <div class="report-grid">
        <div><strong>删除空名称</strong><span>${cleaning.dropped_missing_name ?? 0}</span></div>
        <div><strong>删除重复行</strong><span>${cleaning.dropped_duplicates ?? 0}</span></div>
        <div><strong>衍生字段</strong><span>${escapeHtml((cleaning.derived?.generated_fields || []).join(", ") || "无")}</span></div>
        <div><strong>提示信息</strong><span>${escapeHtml((cleaning.warnings || []).join("；") || "无")}</span></div>
      </div>
    `
    : `<div class="empty-state">暂无清洗报告。</div>`;

  if (preview.status === "rejected" || report.status === "rejected") {
    showToast("部分数据接口暂不可用，请确认已上传数据文件或放置默认数据。");
  }
}

export function initDataPipelinePage() {
  refreshPipeline();
  document.querySelector("#data-file-upload")?.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      await uploadDataFile(file);
      await refreshPipeline();
    } finally {
      event.target.value = "";
    }
  });
}
