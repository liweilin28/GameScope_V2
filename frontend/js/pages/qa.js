import { chatQa, getLlmStatus } from "../api.js";
import { renderEchartsOption } from "../charts.js";
import { renderSupportDataToggle, setupSupportDataToggles } from "../supportData.js";
import { escapeHtml, renderTableFromPayload } from "../utils.js";

const examples = [
  "Indie 游戏的价格主要集中在哪些区间？",
  "近几年 Steam 上哪些类型的游戏增长最快？",
  "高好评率游戏通常有什么共同特征？",
  "低价格游戏和高价格游戏的口碑有差异吗？",
  "免费游戏和付费游戏的评论数量差异大吗？",
  "我想看某个类型游戏的发行趋势",
  "帮我分析一个细分市场是否竞争激烈",
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
          <p class="eyebrow">交互式问数 Agent</p>
          <h2>智能问数</h2>
          <p>先澄清分析意图，再由 Python 后端基于当前清洗数据计算，最后返回文字、指标、表格和图表。</p>
        </div>
        <span class="pill warning" id="qa-llm-status">正在检查 LLM</span>
      </div>

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
              你可以直接问 Steam 市场数据问题。如果问题不够明确，我会先反问，再调用后端数据分析函数。
            </div>
          </div>
        </div>
      </article>

      <article class="qa-input-card">
        <input id="qa-message" class="text-input" placeholder="输入你的问题，例如：哪些游戏表现比较好？" />
        <button class="primary-button" id="qa-send">发送</button>
        <button class="ghost-button" id="qa-clear">清空对话</button>
      </article>
    </section>
  `;
}

function chatLog() {
  return document.querySelector("#qa-chat-log");
}

function appendMessage(role, content) {
  const node = document.createElement("div");
  node.className = `chat-message ${role}`;
  node.innerHTML = `<div class="chat-bubble">${escapeHtml(content)}</div>`;
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
      <p>${escapeHtml(clarification.question || data.assistant_message)}</p>
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

function appendFinalAnswer(data) {
  const answer = data.answer || {};
  const chartId = `qa-agent-chart-${qaState.chartIndex++}`;
  const hasChart = answer.chart?.echarts_option;
  const node = document.createElement("div");
  node.className = "chat-message assistant";
  node.innerHTML = `
    <div class="chat-bubble result-bubble">
      <p>${escapeHtml(answer.summary || data.assistant_message)}</p>
      ${metricCards(answer.key_metrics)}
      ${
        hasChart
          ? `<article class="chart-card qa-result-chart"><div id="${chartId}" class="chart"></div></article>`
          : `<div class="empty-state">暂无可视化数据。</div>`
      }
      <article class="card qa-result-table">
        <h3>结果表格</h3>
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
  if (hasChart) {
    renderEchartsOption(chartId, answer.chart.echarts_option);
  }
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
