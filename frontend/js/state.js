export const state = {
  currentPage: "home",
  backendOnline: false,
  llmStatus: null,
  chartInstances: {},
  explorerFilters: {
    only_indie: true,
    year_range: null,
    price_range: null,
    genres: null,
    tags: null,
    min_reviews: 0,
  },
};

export const pages = [
  { key: "home", title: "首页" },
  { key: "dataPipeline", title: "数据读取与清洗" },
  { key: "dashboard", title: "市场总览" },
  { key: "explorer", title: "可视化探索" },
  { key: "qa", title: "智能问数" },
  { key: "ideaLab", title: "立项实验室" },
];
