import {
  getDashboardInsights,
  getDashboardMetrics,
  getGenreDistribution,
  getPositiveRateHistogram,
  getPriceHistogram,
  getReleaseTrend,
  getReviewLogHistogram,
  getTagFrequency,
} from "../api.js";
import {
  renderHistogram,
  renderHorizontalBarChart,
  renderLineChart,
  showEmptyState,
} from "../charts.js";
import { escapeHtml, formatNumber, formatPercent, showToast } from "../utils.js";

export function renderDashboard() {
  return `
    <section class="section">
      <div class="page-head">
        <div>
          <p class="eyebrow">市场看板</p>
          <h2>市场总览</h2>
          <p>基于清洗后的 Steam 数据，观察发行趋势、类型结构、标签主题、价格分布、口碑分布和评论数头部集中现象。</p>
        </div>
      </div>

      <div id="dashboard-alert"></div>
      <div class="metrics-grid" id="dashboard-metrics"></div>

      <article class="card">
        <div class="card-title-row">
          <div>
            <h3>数据发现</h3>
            <p class="muted">以下结论由后端 pandas 统计结果生成，不使用 LLM 编造。</p>
          </div>
        </div>
        <div id="dashboard-insights"></div>
      </article>

      <div class="grid-2">
        ${chartPanel("年份发行趋势", "Steam 游戏发行数量是否随时间变化？", "折线图用于观察年份变化趋势。", "release-trend-chart")}
        ${chartPanel("Genre 分布 Top 10", "最常见的游戏类型是什么？", "横向条形图按数量降序展示，便于阅读较长类别名。", "genre-chart")}
      </div>
      <div class="grid-2">
        ${chartPanel("Tag 频率 Top 20", "玩家标签中哪些主题最常见？", "使用统一主色，避免大量标签随机着色。", "tag-chart", true)}
        ${chartPanel("价格分布直方图", "Steam 游戏价格主要集中在哪些区间？", "直方图展示连续价格字段的分布。", "price-chart")}
      </div>
      <div class="grid-2">
        ${chartPanel("好评率分布直方图", "游戏口碑整体分布如何？", "只统计有评论数据的样本，避免无评论游戏影响口碑判断。", "reception-chart")}
        ${chartPanel("评论数 log 分布", "游戏热度是否存在头部集中？", "使用 log(total_reviews + 1) 处理，避免头部游戏压扁图表。", "review-log-chart")}
      </div>
    </section>
  `;
}

function chartPanel(title, question, insight, id, tall = false) {
  return `
    <article class="chart-card ${tall ? "tall" : ""}">
      <div class="chart-copy">
        <h3>${title}</h3>
        <p><strong>问题：</strong>${question}</p>
        <p>${insight}</p>
      </div>
      <div id="${id}" class="chart"></div>
    </article>
  `;
}

function metric(label, value, description = "") {
  return `<article class="metric-card"><span>${label}</span><strong>${value}</strong><small>${description}</small></article>`;
}

function renderInsights(items) {
  const rows = Array.isArray(items) ? items : [];
  if (!rows.length) {
    return `<div class="empty-state">暂无可用结论。</div>`;
  }
  return `
    <div class="insight-list">
      ${rows
        .map(
          (item) => `
            <div class="insight-item">
              <span class="pill">${escapeHtml(item.type || "发现")}</span>
              <p>${escapeHtml(item.text || "")}</p>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

export async function initDashboardPage() {
  const chartIds = ["release-trend-chart", "genre-chart", "tag-chart", "price-chart", "reception-chart", "review-log-chart"];
  try {
    const [metrics, insights, trend, genres, tags, priceHistogram, rateHistogram, reviewLogHistogram] = await Promise.all([
      getDashboardMetrics(),
      getDashboardInsights(),
      getReleaseTrend(),
      getGenreDistribution(),
      getTagFrequency(),
      getPriceHistogram(),
      getPositiveRateHistogram(),
      getReviewLogHistogram(),
    ]);

    document.querySelector("#dashboard-alert").innerHTML = "";
    document.querySelector("#dashboard-metrics").innerHTML = [
      metric("游戏总数", formatNumber(metrics.game_count), "当前数据集中可分析游戏数量"),
      metric("平均价格", formatNumber(metrics.avg_price, 2), "价格字段的均值"),
      metric("中位数价格", formatNumber(metrics.median_price, 2), "比均值更不易受极端值影响"),
      metric("平均好评率", formatPercent(metrics.avg_positive_rate), "仅基于有评论样本"),
      metric("平均评论数", formatNumber(metrics.avg_total_reviews, 1), "用于粗略观察热度"),
      metric("免费游戏比例", formatPercent(metrics.free_game_ratio), "price = 0 的样本占比"),
      metric("独立游戏比例", formatPercent(metrics.indie_game_ratio), "genres 或 tags 含 Indie 的占比"),
    ].join("");
    document.querySelector("#dashboard-insights").innerHTML = renderInsights(insights);

    renderLineChart("release-trend-chart", "年份发行趋势", trend, "year", "count", { area: true });
    renderHorizontalBarChart("genre-chart", "Genre Top 10", genres, "genre", "count");
    renderHorizontalBarChart("tag-chart", "Tag Top 20", tags, "tag", "count", { left: 150 });
    renderHistogram("price-chart", priceHistogram, { title: "价格直方图" });
    renderHistogram("reception-chart", rateHistogram, { title: "好评率直方图" });
    renderHistogram("review-log-chart", reviewLogHistogram, { title: "log(total_reviews + 1) 分布" });
  } catch (error) {
    document.querySelector("#dashboard-alert").innerHTML =
      `<div class="notice warning"><strong>暂无可分析数据</strong><span>${error.message}</span></div>`;
    document.querySelector("#dashboard-metrics").innerHTML = "";
    document.querySelector("#dashboard-insights").innerHTML = `<div class="empty-state">暂无可用结论。</div>`;
    chartIds.forEach((id) => showEmptyState(id, "请先在 Data Pipeline 页面加载默认数据或上传 CSV。"));
    showToast("市场总览暂无数据。");
  }
}
