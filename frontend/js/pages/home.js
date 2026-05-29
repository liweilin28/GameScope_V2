import { getSubmissionReadiness } from "../api.js?v=20260529cachefix1";
import { escapeHtml } from "../utils.js?v=20260529cachefix1";

export function renderHome() {
  return `
    <section class="section">
      <div class="hero">
        <div>
          <p class="eyebrow">Steam 市场智能分析</p>
          <h2>GameScope</h2>
        </div>
        <p class="hero-subtitle">面向独立游戏创意的 Steam 市场分析平台</p>
        <p class="hero-copy">输入一个游戏创意，系统将基于 Steam 数据分析相似竞品、市场机会和差异化方向。V2 使用 FastAPI 后端保留 Python 数据分析能力，用 HTML/CSS/JavaScript 呈现更稳定的课堂演示。</p>
        <div>
          <button class="primary-button" data-action="start-scan">开始市场扫描</button>
        </div>
      </div>

      <div class="card">
        <div class="card-title-row">
          <div>
            <h3>课程验收面板</h3>
            <p class="muted">从后端真实接口读取数据规模、模块状态、文档和测试信息。</p>
          </div>
          <span class="pill" id="readiness-summary-pill">读取中</span>
        </div>
        <div id="submission-readiness-panel">
          <div class="empty-state">正在读取课程验收状态...</div>
        </div>
      </div>

      <div class="grid-4">
        <article class="card">
          <h3>竞品雷达</h3>
          <p>根据类型、标签、价格和关键词寻找相似竞品，并解释匹配原因。</p>
        </article>
        <article class="card">
          <h3>机会评分</h3>
          <p>从热度、口碑、趋势、竞争压力和差异化空间评估立项机会。</p>
        </article>
        <article class="card">
          <h3>差异化洞察</h3>
          <p>结合竞品高频标签和创意关键词生成差异化建议卡片。</p>
        </article>
        <article class="card">
          <h3>数据问答</h3>
          <p>用规则问答和可选 LLM 解释回答市场分析问题，避免凭空编造数据。</p>
        </article>
      </div>

      <div class="card">
        <h3>课程模块映射</h3>
        <div class="module-strip">
          <span class="module-chip">数据读取</span>
          <span class="module-chip">数据预处理</span>
          <span class="module-chip">数据分析</span>
          <span class="module-chip">数据可视化</span>
          <span class="module-chip">交互式问答</span>
          <span class="module-chip">PLUS 创新</span>
        </div>
      </div>
    </section>
  `;
}

function moduleItem(item) {
  return `
    <div class="readiness-item">
      <div class="readiness-item-head">
        <strong>${escapeHtml(item.label)}</strong>
        <span class="pill ${item.status ? "success" : "warning"}">${item.status ? "已就绪" : "受限"}</span>
      </div>
      <p>${escapeHtml(item.evidence || "暂无说明。")}</p>
    </div>
  `;
}

export async function initHomePage() {
  const root = document.querySelector("#submission-readiness-panel");
  const summaryPill = document.querySelector("#readiness-summary-pill");
  if (!root || !summaryPill) return;

  try {
    const readiness = await getSubmissionReadiness();
    const modules = Object.values(readiness.required_modules || {});
    const docItems = Object.entries(readiness.docs_status?.items || {});
    const allReady =
      readiness.meets_1000_rows &&
      readiness.meets_10_columns &&
      modules.every((item) => item.status) &&
      readiness.docs_status?.complete;

    summaryPill.textContent = allReady ? "可验收" : "待补充";
    summaryPill.className = `pill ${allReady ? "success" : "warning"}`;

    root.innerHTML = `
      <div class="readiness-grid">
        <article class="support-metric">
          <span>数据规模</span>
          <strong>${escapeHtml(`${readiness.rows} 行 / ${readiness.columns} 列`)}</strong>
        </article>
        <article class="support-metric">
          <span>1000+ 行要求</span>
          <strong>${readiness.meets_1000_rows ? "已满足" : "未满足"}</strong>
        </article>
        <article class="support-metric">
          <span>五大模块</span>
          <strong>${modules.filter((item) => item.status).length}/${modules.length} 已就绪</strong>
        </article>
        <article class="support-metric">
          <span>LLM 状态</span>
          <strong>${escapeHtml(readiness.llm_status?.enabled ? "已启用" : "规则 fallback")}</strong>
        </article>
      </div>

      <div class="grid-2">
        <div class="readiness-block">
          <h4>模块状态</h4>
          <div class="readiness-list">
            ${modules.map(moduleItem).join("")}
          </div>
        </div>
        <div class="readiness-block">
          <h4>文档与测试</h4>
          <div class="readiness-list">
            <div class="readiness-item">
              <div class="readiness-item-head">
                <strong>提交文档</strong>
                <span class="pill ${readiness.docs_status?.complete ? "success" : "warning"}">${readiness.docs_status?.complete ? "已齐" : "待补"}</span>
              </div>
              <p>${escapeHtml(docItems.filter(([, value]) => value.exists).length + "/" + docItems.length + " 份文档已存在。")}</p>
            </div>
            <div class="readiness-item">
              <div class="readiness-item-head">
                <strong>测试命令</strong>
                <span class="pill">自检</span>
              </div>
              <p>${escapeHtml(readiness.test_command || "python3 -m pytest -q")}</p>
            </div>
            <div class="readiness-item">
              <div class="readiness-item-head">
                <strong>PLUS 创新</strong>
                <span class="pill success">Idea Lab</span>
              </div>
              <p>Idea Lab 已作为 PLUS 创新功能纳入验收接口与首页面板。</p>
            </div>
          </div>
        </div>
      </div>
    `;
  } catch (error) {
    summaryPill.textContent = "读取失败";
    summaryPill.className = "pill warning";
    root.innerHTML = `<div class="empty-state">${escapeHtml(error.message || "课程验收状态读取失败。")}</div>`;
  }
}
