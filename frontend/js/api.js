import { setLoading, showToast } from "./utils.js";

const API_BASE = "";
let activeRequests = 0;

function beginRequest() {
  activeRequests += 1;
  setLoading(true);
}

function endRequest() {
  activeRequests = Math.max(0, activeRequests - 1);
  if (activeRequests === 0) setLoading(false);
}

async function handleResponse(response) {
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("后端返回内容不是有效 JSON。");
  }

  if (!response.ok || !payload.success) {
    throw new Error(payload.message || "请求失败。");
  }
  return payload.data;
}

export async function apiGet(url) {
  beginRequest();
  try {
    const response = await fetch(`${API_BASE}${url}`);
    return await handleResponse(response);
  } catch (error) {
    showToast(error.message);
    throw error;
  } finally {
    endRequest();
  }
}

export async function apiPost(url, body) {
  beginRequest();
  try {
    const response = await fetch(`${API_BASE}${url}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    return await handleResponse(response);
  } catch (error) {
    showToast(error.message);
    throw error;
  } finally {
    endRequest();
  }
}

export async function uploadDataFile(file) {
  beginRequest();
  try {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE}/api/data/upload`, {
      method: "POST",
      body: formData,
    });
    const data = await handleResponse(response);
    showToast("数据文件上传并清洗成功。");
    return data;
  } catch (error) {
    showToast(error.message);
    throw error;
  } finally {
    endRequest();
  }
}

export const getSystemHealth = () => apiGet("/api/system/health");
export const getLlmStatus = () => apiGet("/api/system/llm-status");
export const getSubmissionReadiness = () => apiGet("/api/system/submission-readiness");
export const getDataStatus = () => apiGet("/api/data/status");
export const getDataPreview = () => apiGet("/api/data/preview?limit=20");
export const getRawData = (limit = 0) => apiGet(`/api/data/raw?limit=${limit}`);
export const getCleaningReport = () => apiGet("/api/data/cleaning-report");
export const getDashboardMetrics = () => apiGet("/api/dashboard/metrics");
export const getDashboardInsights = () => apiGet("/api/dashboard/insights");
export const getReleaseTrend = () => apiGet("/api/dashboard/release-trend");
export const getGenreDistribution = () => apiGet("/api/dashboard/genre-distribution");
export const getTagFrequency = () => apiGet("/api/dashboard/tag-frequency");
export const getPriceDistribution = () => apiGet("/api/dashboard/price-distribution");
export const getReceptionDistribution = () => apiGet("/api/dashboard/reception-distribution");
export const getPriceHistogram = () => apiGet("/api/dashboard/price-histogram");
export const getPositiveRateHistogram = () => apiGet("/api/dashboard/positive-rate-histogram");
export const getReviewLogHistogram = () => apiGet("/api/dashboard/review-log-histogram");
export const filterExplorerData = (filters) => apiPost("/api/explorer/filter", filters);
export const getExplorerCharts = (filters) => apiPost("/api/explorer/charts", filters);
export const askQuestion = (question) => apiPost("/api/qa/ask", { question });
export const chatQa = (payload) => apiPost("/api/qa/chat", payload);
export const parseIdea = (idea_text) => apiPost("/api/idea/parse", { idea_text });
export const analyzeIdea = (payload) => apiPost("/api/idea/analyze", payload);
export const generateIdeaReport = (analysis_result) => apiPost("/api/idea/report", { analysis_result });
export const chatIdeaAdvisor = (payload) => apiPost("/api/idea/advisor-chat", payload);

export const api = {
  health: getSystemHealth,
  llmStatus: getLlmStatus,
  submissionReadiness: getSubmissionReadiness,
  dataStatus: getDataStatus,
};
