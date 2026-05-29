import { api } from "./api.js";
import { state, pages } from "./state.js";
import { showToast, setLoading } from "./utils.js";
import { initHomePage, renderHome } from "./pages/home.js";
import { initDataPipelinePage, renderDataPipeline } from "./pages/dataPipeline.js";
import { initDashboardPage, renderDashboard } from "./pages/dashboard.js";
import { initExplorerPage, renderExplorer } from "./pages/explorer.js";
import { initQaPage, renderQa } from "./pages/qa.js";
import { initIdeaLabPage, renderIdeaLab } from "./pages/ideaLab.js";

const renderers = {
  home: renderHome,
  dataPipeline: renderDataPipeline,
  dashboard: renderDashboard,
  explorer: renderExplorer,
  qa: renderQa,
  ideaLab: renderIdeaLab,
};

const initializers = {
  home: initHomePage,
  dataPipeline: initDataPipelinePage,
  dashboard: initDashboardPage,
  explorer: initExplorerPage,
  qa: initQaPage,
  ideaLab: initIdeaLabPage,
};

function resetScrollPosition() {
  window.scrollTo(0, 0);
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
}

export function navigate(pageKey) {
  if (!renderers[pageKey]) return;
  state.currentPage = pageKey;

  resetScrollPosition();
  document.querySelector("#app").innerHTML = renderers[pageKey]();
  document.querySelector("#page-title").textContent =
    pages.find((page) => page.key === pageKey)?.title || "GameScope";

  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.page === pageKey);
  });

  initializers[pageKey]?.();
  requestAnimationFrame(resetScrollPosition);
  window.setTimeout(resetScrollPosition, 80);
}

async function refreshSystemStatus() {
  try {
    setLoading(true);
    const [health, llm] = await Promise.all([api.health(), api.llmStatus()]);
    state.backendOnline = true;
    state.llmStatus = llm;

    document.querySelector(".status-dot").classList.add("online");
    document.querySelector("#sidebar-status").textContent = health.status === "running" ? "后端已连接" : health.status;

    const llmNode = document.querySelector("#llm-status");
    llmNode.textContent = llm.enabled ? "LLM 已启用" : "规则模式";
    llmNode.classList.toggle("success", llm.enabled);
    llmNode.classList.toggle("warning", !llm.enabled);
  } catch (error) {
    state.backendOnline = false;
    document.querySelector(".status-dot").classList.remove("online");
    document.querySelector("#sidebar-status").textContent = "后端未连接";
    showToast(error.message);
  } finally {
    setLoading(false);
  }
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => navigate(item.dataset.page));
  });

  document.querySelector("#refresh-status").addEventListener("click", refreshSystemStatus);

  document.addEventListener("click", (event) => {
    if (event.target.matches("[data-action='start-scan']")) {
      navigate("ideaLab");
    }
  });
}

bindEvents();
navigate("home");
refreshSystemStatus();
