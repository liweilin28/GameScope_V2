import { getExplorerCharts } from "../api.js";
import {
  renderHorizontalBarChart,
  renderScatterChart,
  renderStackedBarChart,
  showEmptyState,
} from "../charts.js";
import { formatNumber, numberOrNull, readCsvList, renderTable } from "../utils.js";

export function renderExplorer() {
  return `
    <section class="section">
      <div class="page-head">
        <div>
          <p class="eyebrow">交互式可视化</p>
          <h2>可视化探索</h2>
          <p>通过筛选器观察细分市场表现。散点图支持滚轮缩放、拖动缩放和框选，便于查看拥挤区域。</p>
        </div>
      </div>

      <form id="explorer-form" class="filter-panel">
        <label class="check-row"><input id="only-indie" type="checkbox" checked />只看 Indie</label>
        <label>年份起始<input id="year-min" type="number" placeholder="如 2018" /></label>
        <label>年份结束<input id="year-max" type="number" placeholder="如 2024" /></label>
        <label>最低价格<input id="price-min" type="number" step="0.01" placeholder="0" /></label>
        <label>最高价格<input id="price-max" type="number" step="0.01" placeholder="20" /></label>
        <label>类型 genres<input id="genres-input" type="text" placeholder="Puzzle, RPG" /></label>
        <label>标签 tags<input id="tags-input" type="text" placeholder="Story Rich, Atmospheric" /></label>
        <label>最低评论数<input id="min-reviews" type="number" value="0" min="0" /></label>
        <button class="primary-button" type="submit">应用筛选</button>
      </form>

      <div id="explorer-alert"></div>
      <div class="metrics-grid" id="explorer-summary"></div>

      <div class="grid-2">
        ${chartPanel("价格 vs 评论数", "不同价格游戏的市场热度是否有差异？", "颜色表示价格层级；支持滚轮缩放、框选和滑块缩放，避免点全部糊在一起。", "price-reviews-chart")}
        ${chartPanel("热度 vs 好评率", "评论热度和口碑是否存在关系？", "横轴使用 log(total_reviews + 1)，适合观察头部集中市场。", "reviews-positive-chart")}
      </div>
      <div class="grid-2">
        ${chartPanel("Genre × Price Level", "不同类型游戏的定价结构是否不同？", "堆叠柱状图展示每个类型内部的价格层级构成。", "genre-price-stack-chart")}
        ${chartPanel("Top Games", "筛选条件下最有代表性的游戏有哪些？", "按评论数排序，旁边保留表格便于精确查看。", "top-games-chart")}
      </div>
      <article class="card">
        <h3>Top 游戏表格</h3>
        <div id="top-games"></div>
      </article>
      <article class="card">
        <h3>筛选后数据表</h3>
        <div id="explorer-table"></div>
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

function buildFilters() {
  const yearMin = numberOrNull(document.querySelector("#year-min").value);
  const yearMax = numberOrNull(document.querySelector("#year-max").value);
  const priceMin = numberOrNull(document.querySelector("#price-min").value);
  const priceMax = numberOrNull(document.querySelector("#price-max").value);
  return {
    only_indie: document.querySelector("#only-indie").checked,
    year_range: yearMin !== null && yearMax !== null ? [yearMin, yearMax] : null,
    price_range: priceMin !== null && priceMax !== null ? [priceMin, priceMax] : null,
    genres: readCsvList(document.querySelector("#genres-input").value),
    tags: readCsvList(document.querySelector("#tags-input").value),
    min_reviews: Number(document.querySelector("#min-reviews").value || 0),
  };
}

function summaryCard(label, value, description = "") {
  return `<article class="metric-card"><span>${label}</span><strong>${value}</strong><small>${description}</small></article>`;
}

async function applyFilters() {
  const chartIds = ["price-reviews-chart", "reviews-positive-chart", "genre-price-stack-chart", "top-games-chart"];
  try {
    const data = await getExplorerCharts(buildFilters());
    const empty = data.filtered_count === 0;
    document.querySelector("#explorer-alert").innerHTML = empty
      ? `<div class="notice warning"><strong>筛选结果为空</strong><span>当前条件下没有足够数据，请放宽类型、标签、年份或价格条件。</span></div>`
      : "";
    document.querySelector("#explorer-summary").innerHTML = [
      summaryCard("筛选后数量", formatNumber(data.filtered_count), "当前条件下的游戏数量"),
      summaryCard("全量数量", formatNumber(data.total_count), "当前加载数据集大小"),
      summaryCard("散点样本", formatNumber(data.price_reviews_scatter?.length || 0), "用于关系图的样本数"),
    ].join("");

    if (empty) {
      chartIds.forEach((id) => showEmptyState(id, "当前筛选条件下没有足够数据。"));
    } else {
      renderScatterChart("price-reviews-chart", "价格 vs 评论数", data.price_reviews_scatter || [], {
        xKey: "price",
        yKey: "total_reviews",
        xName: "价格",
        yName: "评论数",
        colorBy: "price_level",
        sizeByReviews: true,
        opacity: 0.64,
        dataZoom: true,
        brush: true,
      });
      renderScatterChart("reviews-positive-chart", "log(total_reviews + 1) vs 好评率", data.reviews_positive_scatter || [], {
        xKey: "log_total_reviews",
        yKey: "positive_rate",
        xName: "log(评论数 + 1)",
        yName: "好评率",
        colorBy: "review_level",
        opacity: 0.68,
        dataZoom: true,
      });
      renderStackedBarChart("genre-price-stack-chart", data.genre_price_stack, { title: "Genre × Price Level" });
      renderHorizontalBarChart("top-games-chart", "Top Games by Reviews", data.top_games || [], "name", "total_reviews", {
        left: 150,
      });
    }

    document.querySelector("#top-games").innerHTML = renderTable(data.top_games || [], {
      limit: 10,
      columns: ["name", "price", "positive_rate", "total_reviews", "release_year", "genres", "tags"],
    });
    document.querySelector("#explorer-table").innerHTML = renderTable(data.table || [], { limit: 50 });
  } catch (error) {
    document.querySelector("#explorer-alert").innerHTML =
      `<div class="notice warning"><strong>暂无可探索数据</strong><span>${error.message}</span></div>`;
    document.querySelector("#explorer-summary").innerHTML = "";
    chartIds.forEach((id) => showEmptyState(id, "请先在 Data Pipeline 页面加载默认数据或上传 CSV。"));
    document.querySelector("#top-games").innerHTML = `<div class="empty-state">暂无数据。</div>`;
    document.querySelector("#explorer-table").innerHTML = `<div class="empty-state">暂无数据。</div>`;
  }
}

export function initExplorerPage() {
  document.querySelector("#explorer-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    applyFilters();
  });
  applyFilters();
}
