import { state } from "./state.js";

const COLORS = {
  primary: "#2563eb",
  teal: "#0f766e",
  gray: "#94a3b8",
  grid: "#e2e8f0",
  text: "#0f172a",
  muted: "#64748b",
  good: "#16a34a",
  warning: "#f59e0b",
  danger: "#dc2626",
};

const CATEGORY_COLORS = {
  Free: "#0f766e",
  Low: "#2563eb",
  Medium: "#f59e0b",
  High: "#dc2626",
  "Very High": "#7c3aed",
  Unknown: "#94a3b8",
};

function getContainer(containerId) {
  return document.querySelector(`#${containerId}`);
}

function safeValue(value, fallback = "暂无") {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return value;
}

function formatRate(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "暂无";
  const rate = Number(value);
  return rate <= 1 ? `${(rate * 100).toFixed(1)}%` : `${rate.toFixed(1)}%`;
}

function baseGrid(extra = {}) {
  return { left: 56, right: 28, top: 52, bottom: 42, containLabel: true, ...extra };
}

function mountChart(containerId, option, hasData = true) {
  const container = getContainer(containerId);
  if (!container || !window.echarts) return null;

  if (state.chartInstances[containerId]) {
    state.chartInstances[containerId].dispose();
  }

  const chart = window.echarts.init(container);
  chart.setOption(hasData ? option : emptyOption("暂无可视化数据。"));
  state.chartInstances[containerId] = chart;
  return chart;
}

function emptyOption(message) {
  return {
    title: {
      text: message,
      left: "center",
      top: "center",
      textStyle: { color: COLORS.muted, fontSize: 14, fontWeight: 500 },
    },
  };
}

export function showEmptyState(containerId, message = "暂无可视化数据。") {
  return mountChart(containerId, emptyOption(message), false);
}

export function showChartError(containerId, errorMessage = "图表渲染失败。") {
  const container = getContainer(containerId);
  if (!container) return;
  container.innerHTML = `<div class="empty-state">${errorMessage}</div>`;
}

export function resizeCharts() {
  Object.values(state.chartInstances).forEach((chart) => chart?.resize());
}

export function renderEchartsOption(containerId, option) {
  return mountChart(containerId, option || {}, Boolean(option));
}

export function renderLineChart(containerId, title, rows, xKey, yKey, options = {}) {
  const sorted = Array.isArray(rows)
    ? [...rows].sort((a, b) => Number(a[xKey]) - Number(b[xKey]))
    : [];
  const hasData = sorted.length > 0;
  return mountChart(
    containerId,
    {
      title: { text: title, left: 12, top: 8, textStyle: { fontSize: 14, color: COLORS.text } },
      toolbox: { right: 12, top: 6, feature: { dataZoom: {}, restore: {}, saveAsImage: {} } },
      tooltip: { trigger: "axis" },
      grid: baseGrid(),
      xAxis: { type: "category", data: sorted.map((item) => item[xKey]), boundaryGap: false },
      yAxis: { type: "value", splitLine: { lineStyle: { color: COLORS.grid } } },
      series: [
        {
          type: "line",
          smooth: true,
          symbolSize: 7,
          areaStyle: options.area ? { color: "rgba(37, 99, 235, 0.08)" } : undefined,
          data: sorted.map((item) => item[yKey]),
          color: COLORS.primary,
        },
      ],
    },
    hasData,
  );
}

export function renderBarChart(containerId, title, rows, xKey, yKey, options = {}) {
  const sorted = Array.isArray(rows) ? [...rows].sort((a, b) => Number(b[yKey]) - Number(a[yKey])) : [];
  const hasData = sorted.length > 0;
  return mountChart(
    containerId,
    {
      title: { text: title, left: 12, top: 8, textStyle: { fontSize: 14, color: COLORS.text } },
      toolbox: { right: 12, top: 6, feature: { dataZoom: {}, restore: {}, saveAsImage: {} } },
      tooltip: { trigger: "axis" },
      grid: baseGrid({ bottom: 60 }),
      xAxis: {
        type: "category",
        data: sorted.map((item) => item[xKey]),
        axisLabel: { rotate: options.rotate ?? 0, color: COLORS.muted },
      },
      yAxis: { type: "value", splitLine: { lineStyle: { color: COLORS.grid } } },
      series: [
        {
          type: "bar",
          data: sorted.map((item) => item[yKey]),
          color: options.color || COLORS.primary,
          barMaxWidth: 34,
          label: { show: Boolean(options.label), position: "top" },
        },
      ],
    },
    hasData,
  );
}

export function renderHorizontalBarChart(containerId, title, rows, yKey, xKey, options = {}) {
  const sorted = Array.isArray(rows) ? [...rows].sort((a, b) => Number(a[xKey]) - Number(b[xKey])) : [];
  const hasData = sorted.length > 0;
  return mountChart(
    containerId,
    {
      title: { text: title, left: 12, top: 8, textStyle: { fontSize: 14, color: COLORS.text } },
      toolbox: { right: 12, top: 6, feature: { dataZoom: {}, restore: {}, saveAsImage: {} } },
      tooltip: { trigger: "axis" },
      grid: baseGrid({ left: options.left ?? 132, right: 52, bottom: 24 }),
      xAxis: { type: "value", splitLine: { lineStyle: { color: COLORS.grid } } },
      yAxis: { type: "category", data: sorted.map((item) => item[yKey]), axisLabel: { color: COLORS.muted } },
      series: [
        {
          type: "bar",
          data: sorted.map((item) => item[xKey]),
          color: options.color || COLORS.teal,
          barMaxWidth: options.barMaxWidth || 18,
          label: { show: true, position: "right", color: COLORS.muted },
        },
      ],
    },
    hasData,
  );
}

export function renderHistogram(containerId, rows, options = {}) {
  return renderBarChart(
    containerId,
    options.title || "分布直方图",
    rows,
    options.xKey || "bin",
    options.yKey || "count",
    { color: options.color || COLORS.primary, rotate: options.rotate ?? 0 },
  );
}

export function renderScatterChart(containerId, title, rows, options = {}) {
  const dataRows = Array.isArray(rows) ? rows : [];
  const xKey = options.xKey || "price";
  const yKey = options.yKey || "positive_rate";
  const hasData = dataRows.length > 0;
  return mountChart(
    containerId,
    {
      title: { text: title, left: 12, top: 8, textStyle: { fontSize: 14, color: COLORS.text } },
      tooltip: {
        trigger: "item",
        formatter: (params) => {
          const item = params.data?.raw || {};
          return [
            `<strong>${safeValue(item.name, "Unknown")}</strong>`,
            `价格：${safeValue(item.price)}`,
            `好评率：${formatRate(item.positive_rate)}`,
            `评论数：${safeValue(item.total_reviews)}`,
            `类型：${safeValue(item.genres)}`,
            `标签：${safeValue(item.tags)}`,
          ].join("<br/>");
        },
      },
      grid: baseGrid({ left: 70, right: 36, bottom: options.dataZoom ? 78 : 52 }),
      dataZoom: options.dataZoom
        ? [
            { type: "inside", xAxisIndex: 0, yAxisIndex: 0 },
            { type: "slider", xAxisIndex: 0, height: 22, bottom: 18 },
            { type: "slider", yAxisIndex: 0, width: 20, right: 6 },
          ]
        : undefined,
      brush: options.brush ? { toolbox: ["rect", "polygon", "clear"], xAxisIndex: 0, yAxisIndex: 0 } : undefined,
      toolbox: { right: 18, top: 8, feature: { ...(options.brush ? { brush: {} } : {}), dataZoom: {}, restore: {}, saveAsImage: {} } },
      xAxis: {
        name: options.xName || xKey,
        nameLocation: "middle",
        nameGap: 32,
        type: "value",
        splitLine: { lineStyle: { color: COLORS.grid } },
      },
      yAxis: {
        name: options.yName || yKey,
        nameLocation: "middle",
        nameGap: 46,
        type: "value",
        splitLine: { lineStyle: { color: COLORS.grid } },
      },
      series: [
        {
          type: "scatter",
          symbolSize: (value, params) => {
            const reviews = Number(params.data?.raw?.total_reviews || 0);
            return options.sizeByReviews ? Math.max(8, Math.min(26, Math.log10(reviews + 1) * 5)) : 9;
          },
          itemStyle: {
            color: (params) => {
              if (!options.colorBy) return options.color || COLORS.primary;
              const key = params.data?.raw?.[options.colorBy] || "Unknown";
              return CATEGORY_COLORS[key] || COLORS.primary;
            },
            opacity: options.opacity ?? 0.72,
          },
          data: dataRows.map((item) => ({ value: [item[xKey], item[yKey]], raw: item })),
        },
      ],
    },
    hasData,
  );
}

export function renderStackedBarChart(containerId, payload, options = {}) {
  const categories = payload?.categories || [];
  const series = payload?.series || [];
  const hasData = categories.length > 0 && series.length > 0;
  return mountChart(
    containerId,
    {
      title: { text: options.title || "堆叠柱状图", left: 12, top: 8, textStyle: { fontSize: 14, color: COLORS.text } },
      toolbox: { right: 12, top: 6, feature: { dataZoom: {}, restore: {}, saveAsImage: {} } },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      legend: { top: 28, right: 16, type: "scroll" },
      grid: baseGrid({ top: 76, bottom: 56 }),
      xAxis: { type: "category", data: categories, axisLabel: { rotate: 0 } },
      yAxis: { type: "value", splitLine: { lineStyle: { color: COLORS.grid } } },
      series: series.map((item) => ({ name: item.name, type: "bar", stack: "total", data: item.data, barMaxWidth: 34 })),
    },
    hasData,
  );
}

export function renderRadarChart(containerId, rows, options = {}) {
  const dataRows = Array.isArray(rows) ? rows : [];
  const nameKey = options.nameKey || "name";
  const valueKey = options.valueKey || "score";
  const hasData = dataRows.length > 0;
  return mountChart(
    containerId,
    {
      title: { text: options.title || "五维评分雷达图", left: 12, top: 8, textStyle: { fontSize: 14, color: COLORS.text } },
      tooltip: {},
      radar: {
        radius: "62%",
        center: ["50%", "56%"],
        indicator: dataRows.map((item) => ({ name: item[nameKey], max: 100 })),
      },
      series: [
        {
          type: "radar",
          areaStyle: { color: "rgba(37, 99, 235, 0.12)" },
          lineStyle: { color: COLORS.primary },
          itemStyle: { color: COLORS.primary },
          data: [{ value: dataRows.map((item) => item[valueKey]), name: options.seriesName || "Score" }],
        },
      ],
    },
    hasData,
  );
}

export function renderBoxPlot(containerId, rows, options = {}) {
  const values = Array.isArray(rows) ? rows.map((item) => Number(item[options.valueKey || "value"])).filter(Number.isFinite) : [];
  if (!values.length) return showEmptyState(containerId);
  values.sort((a, b) => a - b);
  const quantile = (q) => values[Math.floor((values.length - 1) * q)];
  const data = [[values[0], quantile(0.25), quantile(0.5), quantile(0.75), values[values.length - 1]]];
  return mountChart(containerId, {
    title: { text: options.title || "箱线图", left: 12, top: 8, textStyle: { fontSize: 14, color: COLORS.text } },
    tooltip: { trigger: "item" },
    grid: baseGrid(),
    xAxis: { type: "category", data: [options.label || "样本"] },
    yAxis: { type: "value", splitLine: { lineStyle: { color: COLORS.grid } } },
    series: [{ type: "boxplot", data, itemStyle: { color: COLORS.primary, borderColor: COLORS.primary } }],
  });
}

export function renderSimpleChart(containerId, chart) {
  if (!chart) return showEmptyState(containerId);
  if (chart.echarts_option) return renderEchartsOption(containerId, chart.echarts_option);
  if (!chart.data || !Array.isArray(chart.data)) return showEmptyState(containerId);

  const type = chart.type || chart.chart_type;
  if (type === "line") return renderLineChart(containerId, chart.title || "分析结果", chart.data, chart.x, chart.y);
  if (type === "horizontal_bar") {
    return renderHorizontalBarChart(containerId, chart.title || "分析结果", chart.data, chart.y, chart.x);
  }
  if (type === "scatter") return renderScatterChart(containerId, chart.title || "分析结果", chart.data, chart);
  return renderBarChart(containerId, chart.title || "分析结果", chart.data, chart.x, chart.y);
}
