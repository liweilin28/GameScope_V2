import { analyzeIdea, chatIdeaAdvisor, getLlmStatus, parseIdea } from "../api.js?v=20260529cachefix1";
import {
  renderHistogram,
  renderHorizontalBarChart,
  renderRadarChart,
  renderScatterChart,
  showEmptyState,
} from "../charts.js?v=20260529cachefix1";
import { renderSupportDataToggle, setupSupportDataToggles } from "../supportData.js?v=20260529cachefix1";
import { escapeHtml, formatNumber, renderMarkdown, renderTable, showToast } from "../utils.js?v=20260529cachefix1";

const defaultIdea = "我想做一款 2D 独立解谜叙事游戏，价格控制在 20 元以内，风格偏治愈和剧情向。";
const advisorSuggestions = [
  "我应该如何做出差异化？",
  "这个方向最大的风险是什么？",
  "小团队应该先做什么 Demo？",
  "商店页卖点怎么包装？",
  "这个项目应该避开什么竞品打法？",
];
const maxAdvisorHistory = 8;

let latestIdeaAnalysis = null;
let advisorHistory = [];
let advisorSending = false;

export function renderIdeaLab() {
  return `
    <section class="section">
      <div class="page-head">
        <div>
          <p class="eyebrow">PLUS 创新功能</p>
          <h2>立项实验室</h2>
          <p>输入游戏创意，系统会解析方向、寻找竞品、计算机会评分，并生成可解释的立项简报。</p>
        </div>
        <span class="pill warning" id="idea-llm-status">正在检查 LLM</span>
      </div>

      <article class="card">
        <label class="field-label">游戏创意</label>
        <textarea id="idea-text" class="textarea" rows="4">${defaultIdea}</textarea>
        <div class="actions-row">
          <button class="ghost-button" id="parse-idea">解析创意</button>
          <label class="check-row"><input id="idea-only-indie" type="checkbox" checked /> 只看 Indie</label>
          <label class="inline-label">竞品数量 <input id="idea-top-n" type="number" min="1" max="30" value="10" /></label>
        </div>
      </article>

      <article class="card">
        <h3>解析结果编辑区</h3>
        <div class="profile-grid" id="idea-profile-editor"></div>
        <div class="actions-row">
          <button class="primary-button" id="run-scan">运行市场扫描</button>
        </div>
      </article>

      <div id="idea-alert"></div>
      <div class="grid-3" id="score-summary"></div>

      <div class="grid-2">
        ${chartPanel("Opportunity Score 雷达图", "五维机会画像是否均衡？", "雷达图用于观察整体画像，条形图用于读取精确分数。", "score-radar-chart")}
        ${chartPanel("Opportunity Score 五维拆解", "每个维度具体得分是多少？", "状态颜色由总分卡体现，维度解释保留在下方卡片中。", "score-bar-chart")}
      </div>
      <div class="grid-2" id="score-dimensions"></div>
      <div id="score-support"></div>

      <div class="grid-2">
        <article class="card">
          <h3>相似竞品表格</h3>
          <p class="muted">表格保留 match_reason，说明共同类型、共同标签、价格接近或关键词接近。</p>
          <div id="competitor-table"></div>
          <div id="competitor-support"></div>
        </article>
        ${chartPanel("相似竞品 Top N", "哪些竞品与创意最接近？", "横向条形图按 similarity_score 排名。", "competitor-chart")}
      </div>

      <div class="grid-2">
        ${chartPanel("竞品价格分布", "相似竞品主要集中在哪些价格区间？", "直方图用于辅助定价参考。", "idea-price-chart")}
        ${chartPanel("竞品好评率分布", "同类竞品的玩家接受度如何？", "直方图展示竞品口碑分布。", "idea-reception-chart")}
      </div>
      <div class="grid-2">
        ${chartPanel("目标定位 vs 竞品位置", "价格、口碑和热度之间的位置关系如何？", "散点大小由评论数决定，普通竞品使用统一强调色。", "idea-position-chart")}
        ${chartPanel("细分市场类型结构", "该方向对应哪些常见类型？", "横向条形图展示细分市场 genre 结构。", "idea-genre-chart")}
      </div>

      <div class="grid-4" id="differentiation-cards"></div>
      <div id="differentiation-support"></div>

      <article class="card">
        <h3>Project Brief</h3>
        <div id="brief-support"></div>
        <div id="project-brief" class="brief-box markdown-body">运行市场扫描后生成报告。</div>
      </article>

      <article class="card advisor-chat" id="advisor-chat-card">
        <div class="card-title-row">
          <div>
            <h3>立项顾问追问</h3>
            <p class="muted">看完报告后，你可以继续询问差异化、风险、目标玩家、MVP 验证或商店页表达。回答会基于当前创意和市场扫描结果生成。</p>
          </div>
        </div>
        <div id="advisor-chat-gate" class="notice warning">
          <strong>请先运行市场扫描，生成报告后再追问。</strong>
        </div>
        <div id="advisor-messages" class="advisor-messages">
          <div class="advisor-message advisor-message-assistant">
            <div class="advisor-message-role">立项顾问</div>
            <div class="advisor-message-body markdown-body">
              <p>请先运行市场扫描，生成报告后再追问。</p>
            </div>
          </div>
        </div>
        <div class="advisor-suggestions">
          ${advisorSuggestions
            .map((question) => `<button type="button" class="ghost-button advisor-suggestion" data-question="${escapeHtml(question)}">${escapeHtml(question)}</button>`)
            .join("")}
        </div>
        <div class="advisor-input-row">
          <textarea id="advisor-question" class="textarea" rows="3" placeholder="例如：如果我只有 3 个月和 2 人团队，最该先验证什么？"></textarea>
          <div class="actions-row advisor-actions">
            <button class="primary-button" id="advisor-send" disabled>发送追问</button>
          </div>
        </div>
      </article>
    </section>
  `;
}

function chartPanel(title, question, insight, id) {
  return `
    <article class="chart-card">
      <div class="chart-copy">
        <h3>${title}</h3>
        <p><strong>问题：</strong>${question}</p>
        <p>${insight}</p>
      </div>
      <div id="${id}" class="chart"></div>
    </article>
  `;
}

function defaultProfile() {
  return {
    target_genres: ["Indie"],
    target_tags: ["Puzzle", "Story Rich", "Atmospheric"],
    price_range: [0, 20],
    art_style_keywords: [],
    gameplay_keywords: [],
    narrative_keywords: [],
    target_players: [],
    reference_games: [],
  };
}

function csv(value) {
  return Array.isArray(value) ? value.join(", ") : "";
}

function renderProfileEditor(profile) {
  const p = { ...defaultProfile(), ...(profile || {}) };
  document.querySelector("#idea-profile-editor").innerHTML = `
    ${field("target_genres", "目标类型", csv(p.target_genres))}
    ${field("target_tags", "目标标签", csv(p.target_tags))}
    ${field("price_range", "价格区间", csv(p.price_range))}
    ${field("art_style_keywords", "美术关键词", csv(p.art_style_keywords))}
    ${field("gameplay_keywords", "玩法关键词", csv(p.gameplay_keywords))}
    ${field("narrative_keywords", "叙事关键词", csv(p.narrative_keywords))}
    ${field("target_players", "目标玩家", csv(p.target_players))}
    ${field("reference_games", "参考游戏", csv(p.reference_games))}
  `;
}

function field(key, label, value) {
  return `<label class="field-label">${label}<input class="text-input profile-field" data-key="${key}" value="${escapeHtml(value)}" /></label>`;
}

function readProfile() {
  const profile = {};
  document.querySelectorAll(".profile-field").forEach((input) => {
    const key = input.dataset.key;
    const parts = input.value.split(",").map((item) => item.trim()).filter(Boolean);
    profile[key] = key === "price_range" ? parts.map(Number).filter((item) => !Number.isNaN(item)).slice(0, 2) : parts;
  });
  if (!profile.price_range?.length) profile.price_range = [0, 20];
  return profile;
}

function scoreBand(score) {
  const value = Number(score || 0);
  if (value >= 80) return { label: "高机会", className: "success" };
  if (value >= 60) return { label: "可进入但需差异化", className: "warning" };
  if (value >= 40) return { label: "谨慎进入", className: "warning" };
  return { label: "不建议优先进入", className: "danger" };
}

function scoreCard(label, value, note = "", className = "") {
  return `<article class="metric-card ${className}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>`;
}

function dimensionRows(dimensions) {
  return Object.entries(dimensions || {}).map(([key, item]) => ({
    name: key,
    score: Number(item.score || 0),
    explanation: item.explanation || "",
  }));
}

async function parseCurrentIdea() {
  const text = document.querySelector("#idea-text").value.trim();
  if (!text) return;
  const profile = await parseIdea(text);
  renderProfileEditor(profile);
  showToast(profile.llm_used ? "LLM 解析完成。" : "规则解析完成。");
}

async function runScan() {
  const emptyChartIds = ["score-radar-chart", "score-bar-chart", "competitor-chart", "idea-price-chart", "idea-reception-chart", "idea-position-chart", "idea-genre-chart"];
  try {
    const payload = {
      idea_text: document.querySelector("#idea-text").value.trim(),
      idea_profile: readProfile(),
      top_n: Number(document.querySelector("#idea-top-n").value || 10),
      only_indie: document.querySelector("#idea-only-indie").checked,
    };
    const result = await analyzeIdea(payload);
    latestIdeaAnalysis = result;
    advisorHistory = [];
    const score = result.opportunity_score || {};
    const band = scoreBand(score.total_score);
    const dims = dimensionRows(score.dimensions);

    document.querySelector("#idea-alert").innerHTML = "";
    document.querySelector("#score-summary").innerHTML = [
      scoreCard("机会总分", formatNumber(score.total_score, 1), band.label, band.className),
      scoreCard("候选池数量", formatNumber(result.candidate_pool_size ?? result.support_data?.competitor_evidence?.summary?.candidate_pool_size, 0), `展示 Top ${result.returned_competitor_count ?? result.competitors?.length ?? 0} 相似竞品`),
      scoreCard("分析模式", result.llm_used ? "使用 LLM 辅助" : "规则 fallback", "评分和图表仍由 Python 后端计算"),
    ].join("");

    document.querySelector("#score-dimensions").innerHTML = dims
      .map((item) => `<article class="card"><h3>${escapeHtml(item.name)}</h3><p><strong>${item.score}</strong></p><p>${escapeHtml(item.explanation)}</p></article>`)
      .join("");
    document.querySelector("#score-support").innerHTML = renderSupportDataToggle(result.support_data?.score_evidence, {
      label: "查看评分依据",
      closeLabel: "收起评分依据",
      title: "机会评分支撑数据",
    });

    renderRadarChart("score-radar-chart", dims, { title: "Opportunity Score 雷达图" });
    renderHorizontalBarChart("score-bar-chart", "五维评分", dims, "name", "score", { left: 180 });

    document.querySelector("#competitor-table").innerHTML = renderTable(result.competitors || [], {
      limit: 20,
      columns: ["name", "price", "positive_rate", "total_reviews", "genres", "tags", "similarity_score", "match_reason"],
      className: "wide-tags-table",
    });
    document.querySelector("#competitor-support").innerHTML = renderSupportDataToggle(result.support_data?.competitor_evidence, {
      label: "查看竞品支撑数据",
      closeLabel: "收起竞品支撑数据",
      title: "竞品雷达支撑数据",
    });
    renderHorizontalBarChart("competitor-chart", "竞品相似度排行", result.charts?.competitor_scores || [], "name", "similarity_score", {
      left: 160,
    });
    renderHistogram("idea-price-chart", result.charts?.competitor_price_histogram || [], { title: "竞品价格分布" });
    renderHistogram("idea-reception-chart", result.charts?.competitor_reception_histogram || [], { title: "竞品好评率分布" });
    renderScatterChart("idea-position-chart", "竞品市场位置", result.charts?.competitor_position || [], {
      xKey: "price",
      yKey: "positive_rate",
      xName: "price",
      yName: "positive_rate",
      sizeByReviews: true,
      opacity: 0.72,
    });
    renderHorizontalBarChart("idea-genre-chart", "细分市场 Genre", result.charts?.genre_distribution || [], "genre", "count", {
      left: 140,
    });

    document.querySelector("#differentiation-cards").innerHTML = (result.differentiation_cards || [])
      .map((card) => `<article class="card"><h3>${escapeHtml(card.title)}</h3><p>${escapeHtml(card.content)}</p></article>`)
      .join("");
    document.querySelector("#differentiation-support").innerHTML = renderSupportDataToggle(result.support_data?.differentiation_evidence, {
      label: "查看建议依据",
      closeLabel: "收起建议依据",
      title: "差异化建议依据",
    });
    document.querySelector("#brief-support").innerHTML = renderSupportDataToggle(result.support_data?.brief_evidence, {
      label: "查看报告依据",
      closeLabel: "收起报告依据",
      title: "Project Brief 报告依据",
    });
    document.querySelector("#project-brief").innerHTML = renderMarkdown(result.brief || "暂无报告。");
    resetAdvisorChat();
    syncAdvisorComposerState();
  } catch (error) {
    document.querySelector("#idea-alert").innerHTML =
      `<div class="notice warning"><strong>分析失败</strong><span>${escapeHtml(error.message)}</span></div>`;
    emptyChartIds.forEach((id) => showEmptyState(id, "请检查数据是否已加载，或放宽创意筛选条件。"));
    latestIdeaAnalysis = null;
    advisorHistory = [];
    resetAdvisorChat();
    syncAdvisorComposerState();
  }
}

function hasAdvisorContext() {
  return Boolean(latestIdeaAnalysis?.brief);
}

function syncAdvisorComposerState() {
  const sendButton = document.querySelector("#advisor-send");
  const textarea = document.querySelector("#advisor-question");
  const gate = document.querySelector("#advisor-chat-gate");
  const enabled = hasAdvisorContext();
  if (sendButton) {
    sendButton.disabled = !enabled || advisorSending;
    sendButton.textContent = advisorSending ? "发送中..." : "发送追问";
  }
  if (textarea) {
    textarea.disabled = !enabled || advisorSending;
  }
  if (gate) {
    gate.hidden = enabled;
  }
  document.querySelectorAll(".advisor-suggestion").forEach((button) => {
    button.disabled = !enabled || advisorSending;
  });
}

function renderAdvisorMessages(messages = []) {
  const container = document.querySelector("#advisor-messages");
  if (!container) return;
  const rows = messages.length
    ? messages
    : [
        {
          role: "assistant",
          content: "请先运行市场扫描，生成报告后再追问。",
        },
      ];

  container.innerHTML = rows
    .map(
      (message) => `
        <div class="advisor-message advisor-message-${message.role === "user" ? "user" : "assistant"}">
          <div class="advisor-message-role">${message.role === "user" ? "你" : "立项顾问"}</div>
          <div class="advisor-message-body markdown-body">${renderMarkdown(message.content || "")}</div>
        </div>
      `
    )
    .join("");
  container.scrollTop = container.scrollHeight;
}

function resetAdvisorChat() {
  if (hasAdvisorContext()) {
    renderAdvisorMessages([
      {
        role: "assistant",
        content: "市场扫描已完成。你可以继续追问差异化、风险、Demo 范围、目标玩家或商店页表达，我会基于当前报告继续给建议。",
      },
    ]);
  } else {
    renderAdvisorMessages([]);
  }
}

function getAdvisorRequestHistory() {
  return advisorHistory.slice(-maxAdvisorHistory);
}

async function sendAdvisorQuestion(questionText = "") {
  const questionInput = document.querySelector("#advisor-question");
  const question = String(questionText || questionInput?.value || "").trim();
  if (!hasAdvisorContext()) {
    showToast("请先运行市场扫描，生成报告后再追问。");
    return;
  }
  if (!question || advisorSending) {
    return;
  }

  advisorHistory.push({ role: "user", content: question });
  renderAdvisorMessages(advisorHistory);
  if (questionInput) questionInput.value = "";
  advisorSending = true;
  syncAdvisorComposerState();

  try {
    const response = await chatIdeaAdvisor({
      question,
      idea_text: document.querySelector("#idea-text")?.value.trim() || "",
      analysis_result: latestIdeaAnalysis,
      history: getAdvisorRequestHistory(),
    });
    advisorHistory.push({ role: "assistant", content: response.answer || "暂无回答。" });
    advisorHistory = advisorHistory.slice(-maxAdvisorHistory);
    renderAdvisorMessages(advisorHistory);
    if (response.fallback_used) {
      showToast("当前使用规则 fallback 回答。");
    }
  } catch (error) {
    advisorHistory.push({
      role: "assistant",
      content: "当前无法生成追问回答。你仍可以参考报告中的差异化建议、机会评分和竞品表格。",
    });
    advisorHistory = advisorHistory.slice(-maxAdvisorHistory);
    renderAdvisorMessages(advisorHistory);
  } finally {
    advisorSending = false;
    syncAdvisorComposerState();
  }
}

export async function initIdeaLabPage() {
  latestIdeaAnalysis = null;
  advisorHistory = [];
  advisorSending = false;
  renderProfileEditor(defaultProfile());
  resetAdvisorChat();
  syncAdvisorComposerState();
  try {
    const status = await getLlmStatus();
    const node = document.querySelector("#idea-llm-status");
    node.textContent = status.enabled ? "LLM 已启用" : "规则 fallback";
    node.classList.toggle("success", status.enabled);
    node.classList.toggle("warning", !status.enabled);
  } catch {
    document.querySelector("#idea-llm-status").textContent = "规则 fallback";
  }
  document.querySelector("#parse-idea")?.addEventListener("click", parseCurrentIdea);
  document.querySelector("#run-scan")?.addEventListener("click", runScan);
  document.querySelector("#advisor-send")?.addEventListener("click", () => sendAdvisorQuestion());
  document.querySelector("#advisor-question")?.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      sendAdvisorQuestion();
    }
  });
  document.querySelectorAll(".advisor-suggestion").forEach((button) => {
    button.addEventListener("click", () => {
      const question = button.dataset.question || "";
      const textarea = document.querySelector("#advisor-question");
      if (textarea) textarea.value = question;
      sendAdvisorQuestion(question);
    });
  });
  setupSupportDataToggles(document.querySelector(".section"));
}
