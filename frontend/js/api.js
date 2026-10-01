// js/api.js
// The website and API share an origin in local and Render deployments.
const API_BASE_URL = "";

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
    const res = await fetch(`${API_BASE_URL}/api/ocr-url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_url: url })
    });
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
    const payload = await response.json();
    return payload.detail || fallback;
  } catch (_) {
    return fallback;
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
