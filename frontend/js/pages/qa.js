import { chatQa, getLlmStatus } from "../api.js?v=20260529cachefix1";
import { renderEchartsOption } from "../charts.js?v=20260529cachefix1";
import { state } from "../state.js?v=20260529cachefix1";
import { renderSupportDataToggle, setupSupportDataToggles } from "../supportData.js?v=20260529cachefix1";
import { escapeHtml, renderMarkdown, renderTableFromPayload } from "../utils.js?v=20260529cachefix1";

const examples = [
  "帮我找 Co-op Horror 的竞品",
  "这个方向有没有机会？",
  "适合定价多少？",
  "哪些标签最值得保留？",
  "Indie 游戏的价格主要集中在哪些区间？",
  "高好评率游戏通常有什么共同特征？",
];

const quickTemplates = [
  { key: "opportunity", label: "赛道机会分析", question: "这个方向有没有机会？" },
  { key: "competitors", label: "竞品查找", question: "帮我找这个方向的竞品" },
  { key: "pricing", label: "价格带分析", question: "适合定价多少？" },
  { key: "tags", label: "标签组合分析", question: "哪些标签最值得保留？" },
  { key: "similar", label: "相似游戏分析", question: "有哪些相似游戏？" },
  { key: "risk", label: "创意风险分析", question: "这个创意的主要风险是什么？" },
];

const qaState = {
  conversationId: null,
  history: [],
  currentFilters: {
    genres: [],
    tags: [],
    price_range: null,
    year_range: null,
    min_reviews: null,
    market_scope: "unknown",
  },
  chartIndex: 0,
};

export function renderQa() {
  return `
    <section class="section qa-section">
      <div class="page-head">
        <div>
          <p class="eyebrow">数据分析 Agent</p>
          <h2>智能问数</h2>
          <p>先识别分析意图，再由后端基于当前数据集或立项实验室上下文执行查询、计算、图表和证据生成，最后再输出中文解释。</p>
        </div>
        <span class="pill warning" id="qa-llm-status">正在检查 LLM</span>
      </div>

      <article class="card">
        <h3>数据边界</h3>
        <p class="muted">可回答：当前数据集中存在或可计算的问题，例如竞品、价格带、标签组合、评论表现、相似游戏。</p>
        <p class="muted">不保证回答：未来爆款预测、真实收入、平台外数据、数据集缺失字段。</p>
        <div id="qa-idea-context-tip" class="notice" hidden></div>
      </article>

      <article class="card">
        <h3>快捷分析模板</h3>
        <div class="example-row">
          ${quickTemplates
            .map((item) => `<button class="ghost-button qa-template" data-question="${escapeHtml(item.question)}">${escapeHtml(item.label)}</button>`)
            .join("")}
        </div>
      </article>

      <article class="card">
        <h3>示例问题</h3>
        <div class="example-row">
          ${examples.map((item) => `<button class="ghost-button example-question" data-question="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join("")}
        </div>
      </article>

      <article class="qa-chat-card">
        <div id="qa-chat-log" class="qa-chat-log">
          <div class="chat-message assistant">
            <div class="chat-bubble">
              这里不是普通聊天框。只有在完成数据查询和计算后，我才会给出数据结论；如果问题模糊或超出范围，我会先澄清或说明限制。
            </div>
          </div>
        </div>
      </article>

      <article class="qa-input-card">
        <input id="qa-message" class="text-input" placeholder="输入你的市场数据问题，例如：帮我找 Co-op Horror 的竞品" />
        <button class="primary-button" id="qa-send">发送</button>
        <button class="ghost-button" id="qa-clear">清空对话</button>
      </article>
    </section>
  `;
}

function chatLog() {
  return document.querySelector("#qa-chat-log");
}

function currentIdeaContext() {
  return state.ideaLabContext || null;
}

function appendMessage(role, content) {
  const node = document.createElement("div");
  node.className = `chat-message ${role}`;
  if (role === "assistant") {
    node.innerHTML = `<div class="chat-bubble"><div class="markdown-body">${renderMarkdown(content)}</div></div>`;
  } else {
    node.innerHTML = `<div class="chat-bubble">${escapeHtml(content)}</div>`;
  }
  chatLog().appendChild(node);
  chatLog().scrollTop = chatLog().scrollHeight;
}

function appendClarification(data) {
  const clarification = data.clarification || {};
  const options = (clarification.options || []).map((item) => {
    if (typeof item === "string") {
      return { label: item, value: item };
    }
    return {
      label: item?.label ?? item?.value ?? "选项",
      value: item?.value ?? item?.label ?? "",
    };
  });
  const node = document.createElement("div");
  node.className = "chat-message assistant";
  node.innerHTML = `
    <div class="chat-bubble">
      <div class="markdown-body">${renderMarkdown(clarification.question || data.assistant_message)}</div>
      <div class="clarification-options">
        ${options
          .map(
            (item) =>
              `<button class="ghost-button clarification-option" data-value="${escapeHtml(item.value)}" data-field="${escapeHtml(item.field || "")}">${escapeHtml(item.label)}</button>`,
          )
          .join("")}
      </div>
    </div>
  `;
  chatLog().appendChild(node);
  chatLog().scrollTop = chatLog().scrollHeight;
}

function metricCards(metrics) {
  if (!Array.isArray(metrics) || !metrics.length) return "";
  return `
    <div class="qa-metric-grid">
      ${metrics
        .map(
          (item) => `
            <article class="metric-card">
              <span>${escapeHtml(item.label)}</span>
              <strong>${escapeHtml(item.value)}</strong>
              <small>${escapeHtml(item.description || "")}</small>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function evidenceBrief(evidence) {
  if (!evidence) return "";
  const representativeGames = Array.isArray(evidence.representative_games)
    ? evidence.representative_games.map((item) => item?.name).filter(Boolean).slice(0, 5)
    : [];
  const limitations = Array.isArray(evidence.limitations) ? evidence.limitations : [];
  return `
    <article class="card">
      <h3>证据摘要</h3>
      <p><strong>筛选条件：</strong>${escapeHtml(evidence.filters_text || "未额外筛选")}</p>
      <p><strong>样本量：</strong>${escapeHtml(String(evidence.sample_size ?? 0))}</p>
      <p><strong>代表性游戏：</strong>${escapeHtml(representativeGames.join("、") || "暂无")}</p>
      <p><strong>限制：</strong>${escapeHtml(limitations.join("；") || "结论仅基于当前数据集")}</p>
    </article>
  `;
}

function chartsMarkup(charts) {
  if (!Array.isArray(charts) || !charts.length) {
    return `<div class="empty-state">暂无可视化数据。</div>`;
  }
  return charts
    .map((chart, index) => {
      const chartId = `qa-agent-chart-${qaState.chartIndex++}-${index}`;
      chart.__chartId = chartId;
      return `<article class="chart-card qa-result-chart"><div id="${chartId}" class="chart"></div></article>`;
    })
    .join("");
}

function appendFinalAnswer(data) {
  const answer = data.answer || {};
  const charts = Array.isArray(answer.charts) && answer.charts.length ? answer.charts : answer.chart ? [answer.chart] : [];
  const node = document.createElement("div");
  node.className = "chat-message assistant";
  node.innerHTML = `
    <div class="chat-bubble result-bubble">
      <div class="markdown-body">${renderMarkdown(answer.summary || data.assistant_message)}</div>
      ${metricCards(answer.key_metrics)}
      ${evidenceBrief(answer.evidence_brief)}
      ${chartsMarkup(charts)}
      <article class="card qa-result-table">
        <h3>结构化结果</h3>
        ${renderTableFromPayload(answer.table, { limit: 20 })}
        ${renderSupportDataToggle(answer.support_data, { label: "查看支撑数据", closeLabel: "收起支撑数据" })}
      </article>
      <div class="follow-up-box">
        <span>你可以继续问：</span>
        ${(answer.follow_up_suggestions || [])
          .map((item) => `<button class="ghost-button follow-up-question" data-question="${escapeHtml(item)}">${escapeHtml(item)}</button>`)
          .join("")}
      </div>
    </div>
  `;
  chatLog().appendChild(node);
  charts.forEach((chart) => {
    if (chart?.echarts_option && chart.__chartId) {
      renderEchartsOption(chart.__chartId, chart.echarts_option);
    }
  });
  chatLog().scrollTop = chatLog().scrollHeight;
}

function updateStateFromResponse(data) {
  qaState.conversationId = data.conversation_id || qaState.conversationId;
  qaState.currentFilters = data.understood_intent?.filters || qaState.currentFilters;
}

async function sendMessage(message) {
  const text = String(message || "").trim();
  if (!text) return;

  appendMessage("user", text);
  qaState.history.push({ role: "user", content: text });
  document.querySelector("#qa-message").value = "";

  try {
    const data = await chatQa({
      conversation_id: qaState.conversationId,
      message: text,
      history: qaState.history,
      idea_context: currentIdeaContext(),
    });
    updateStateFromResponse(data);
    if (data.response_type === "clarification") {
      appendClarification(data);
    } else if (data.response_type === "final_answer") {
      appendFinalAnswer(data);
    } else {
      appendMessage("assistant", data.assistant_message || "问数分析失败，请换一种问法。");
    }
    qaState.history.push({ role: "assistant", content: data.assistant_message || "" });
  } catch (error) {
    appendMessage("assistant", error.message);
  }
}

function runTemplate(question) {
  const hasContext = Boolean(currentIdeaContext());
  if (!hasContext && ["这个方向有没有机会？", "帮我找这个方向的竞品", "适合定价多少？", "哪些标签最值得保留？", "有哪些相似游戏？", "这个创意的主要风险是什么？"].includes(question)) {
    appendMessage("assistant", "当前没有可用的立项实验室解析结果。你可以先去“立项实验室”运行一次市场扫描，或直接在这里补充类型、标签或关键词。");
    document.querySelector("#qa-message").focus();
    return;
  }
  document.querySelector("#qa-message").value = question;
  sendMessage(question);
}

function refreshIdeaContextTip() {
  const node = document.querySelector("#qa-idea-context-tip");
  if (!node) return;
  const context = currentIdeaContext();
  if (!context?.query_intent && !context?.idea_profile) {
    node.hidden = true;
    node.innerHTML = "";
    return;
  }
  const profile = context.query_intent || context.idea_profile || {};
  const genres = Array.isArray(profile.target_genres) ? profile.target_genres.join("/") : "";
  const tags = Array.isArray(profile.target_tags) ? profile.target_tags.join("/") : "";
  node.hidden = false;
  node.innerHTML = `<strong>已接入立项实验室上下文：</strong><span>默认使用 ${escapeHtml(genres || "未指定类型")}${tags ? ` + ${escapeHtml(tags)}` : ""} 作为分析起点。</span>`;
}

function resetConversation() {
  qaState.conversationId = null;
  qaState.history = [];
  qaState.currentFilters = {
    genres: [],
    tags: [],
    price_range: null,
    year_range: null,
    min_reviews: null,
    market_scope: "unknown",
  };
  qaState.chartIndex = 0;
  chatLog().innerHTML = `
    <div class="chat-message assistant">
      <div class="chat-bubble">对话已清空。请输入新的市场分析问题。</div>
    </div>
  `;
}

export async function initQaPage() {
  try {
    const status = await getLlmStatus();
    const node = document.querySelector("#qa-llm-status");
    node.textContent = status.enabled ? "LLM 已启用" : "规则模式";
    node.classList.toggle("success", status.enabled);
    node.classList.toggle("warning", !status.enabled);
  } catch {
    document.querySelector("#qa-llm-status").textContent = "规则模式";
  }

  refreshIdeaContextTip();

  document.querySelector("#qa-send")?.addEventListener("click", () => sendMessage(document.querySelector("#qa-message").value));
  document.querySelector("#qa-clear")?.addEventListener("click", resetConversation);
  document.querySelector("#qa-message")?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") sendMessage(event.target.value);
  });
  document.querySelectorAll(".example-question").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelector("#qa-message").value = button.dataset.question;
      document.querySelector("#qa-message").focus();
    });
  });
  document.querySelectorAll(".qa-template").forEach((button) => {
    button.addEventListener("click", () => runTemplate(button.dataset.question));
  });
  document.querySelector("#qa-chat-log")?.addEventListener("click", (event) => {
    if (event.target.matches(".clarification-option")) {
      const value = event.target.dataset.value;
      if (value === "free_text") {
        document.querySelector("#qa-message").focus();
        return;
      }
      const field = event.target.dataset.field;
      sendMessage(field ? `${field}:${value}` : value);
    }
    if (event.target.matches(".follow-up-question")) {
      sendMessage(event.target.dataset.question);
    }
  });
  setupSupportDataToggles(document.querySelector("#qa-chat-log"));
}
