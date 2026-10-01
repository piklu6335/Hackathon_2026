// js/api.js
// Render serves the frontend and API from one origin. VS Code Live Server
// serves the frontend on :5500, so point local browser requests at FastAPI :8000.
const API_BASE_URL = (() => {
  const localHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const separateLocalFrontend = localHost && window.location.port !== "8000";
  return separateLocalFrontend
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "";
})();

const api = {
  async checkBackend() {
    try {
      const controller = new AbortController();
      const id = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(`${API_BASE_URL}/api/health`, { signal: controller.signal });
      clearTimeout(id);
      return res.ok;
    } catch (e) {
      return false;
    }
  },

  async scrapeArticle(url) {
    const res = await fetch(`${API_BASE_URL}/api/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });
    if (!res.ok) throw new Error(await responseError(res, "Unable to fetch article"));
    return res.json();
  },

  async analyzeImage(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE_URL}/api/analyze-image`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) throw new Error(await responseError(res, "Image analysis failed"));
    return res.json();
  },

  async ocrImageFromUrl(url) {
    let res = await fetch(`${API_BASE_URL}/api/ocr-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_url: url })
    });
    // Older deployments may expose this endpoint as GET only. Retry using
    // the query-string form if the server rejects POST with 405.
    if (res.status === 405) {
      const query = new URLSearchParams({ image_url: url });
      res = await fetch(`${API_BASE_URL}/api/ocr-url?${query.toString()}`);
    }
    if (!res.ok) throw new Error(await responseError(res, "Failed to process image URL"));
    return res.json();
  },

  async translateText(text, targetLanguage) {
    const res = await fetch(`${API_BASE_URL}/api/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, target_language: targetLanguage })
    });
    if (!res.ok) throw new Error(await responseError(res, "Translation failed"));
    return res.json();
  }
};

async function responseError(response, fallback) {
  try {
    const body = await response.text();
    if (!body) return `${fallback} (HTTP ${response.status})`;
    try {
      const payload = JSON.parse(body);
      return payload.detail || `${fallback} (HTTP ${response.status})`;
    } catch (_) {
      // Render/proxy errors can be HTML instead of the API's JSON error body.
      const message = body.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
      return message
        ? `${fallback} (HTTP ${response.status}): ${message.slice(0, 240)}`
        : `${fallback} (HTTP ${response.status})`;
    }
  } catch (_) {
    return `${fallback} (HTTP ${response.status})`;
  }
}

window.api = api;

// Global UI Status Manager
document.addEventListener("DOMContentLoaded", () => {
  const statusEl = document.createElement("div");
  statusEl.className = "api-status status-checking";
  statusEl.innerHTML = `<div class="status-indicator"></div><span>Checking API...</span>`;
  document.body.appendChild(statusEl);

  api.checkBackend().then(isOnline => {
    if (isOnline) {
      statusEl.className = "api-status status-online";
      statusEl.querySelector("span").textContent = "API Connected";
      setTimeout(() => statusEl.style.opacity = '0', 3000);
    } else {
      statusEl.className = "api-status status-offline";
      statusEl.querySelector("span").textContent = "API Offline";
    }
  });
});
