const result = document.getElementById("result");
const reanalyze = document.getElementById("reanalyze");

function show(payload) {
  const analysis = payload?.analysis?.credibility || {};
  const prediction = analysis.prediction || {};
  const clickbait = payload?.analysis?.clickbait || {};
  if (!payload?.success) {
    result.innerHTML = `<p class="error">${escapeHtml(payload?.error || "No analysis is available yet. Open a news article and retry.")}</p>`;
    return;
  }
  result.innerHTML = `<div class="card"><p class="label">CREDIBILITY MODEL</p><p class="value">${escapeHtml(prediction.label || "UNKNOWN")}</p><p class="muted">Model confidence: ${Number.isFinite(Number(prediction.confidence_percent)) ? Number(prediction.confidence_percent).toFixed(1) + "%" : "unavailable"}</p></div><div class="card"><p class="label">CLICKBAIT SIGNAL</p><p class="value">${escapeHtml(clickbait.level || "Unavailable")}</p><p class="muted">${Number.isFinite(Number(clickbait.score_percent)) ? Number(clickbait.score_percent).toFixed(1) + "%" : "No score"}</p></div>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function scan(force = false) {
  result.innerHTML = '<p class="muted">Analyzing article…</p>';
  chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
    if (!tab?.id || !/^https?:/.test(tab.url || "")) {
      show({ error: "Open a news article in a regular browser tab first." });
      return;
    }
    chrome.tabs.sendMessage(tab.id, { type: "NEWSCRED_GET_ARTICLE" }, article => {
      // The content script sends its automatic scan during page load; requesting here covers popup-first use.
      if (chrome.runtime.lastError || !article) {
        show({ error: "This page has no readable article text. Reload the page and try again." });
        return;
      }
      chrome.runtime.sendMessage({ type: "NEWSCRED_ANALYZE", article, force }, response => {
        if (chrome.runtime.lastError) show({ error: chrome.runtime.lastError.message });
        else if (response?.result) show(response.result);
        else show({ error: response?.error });
      });
    });
  });
}

// The popup requests current-page text directly. content.js handles the initial auto-scan.
chrome.runtime.onMessage.addListener(() => {});
reanalyze.addEventListener("click", () => scan(true));
scan();
