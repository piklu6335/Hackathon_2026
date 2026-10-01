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
  const signals = Array.isArray(clickbait.headline_signals) ? clickbait.headline_signals : [];
  const signalText = signals.length ? `Headline cues: ${signals.map(escapeHtml).join(", ")}.` : "No strong wording cues detected.";
  result.innerHTML = `<div class="card"><p class="label">CREDIBILITY MODEL</p><p class="value">${escapeHtml(prediction.label || "UNKNOWN")}</p><p class="muted">Model confidence: ${Number.isFinite(Number(prediction.confidence_percent)) ? Number(prediction.confidence_percent).toFixed(1) + "%" : "unavailable"}</p></div><div class="card"><p class="label">CLICKBAIT SIGNAL</p><p class="value">${escapeHtml(clickbait.level || "Unavailable")}</p><p class="muted">Combined estimate: ${Number.isFinite(Number(clickbait.score_percent)) ? Number(clickbait.score_percent).toFixed(1) + "%" : "No score"}</p><p class="muted">Model estimate: ${Number.isFinite(Number(clickbait.model_score_percent)) ? Number(clickbait.model_score_percent).toFixed(1) + "%" : "unavailable"}</p><p class="muted">${signalText}</p></div><p class="muted">These are automated text-pattern estimates, not proof that a story is true or false. Check reliable sources.</p>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function scan(force = false) {
  reanalyze.disabled = true;
  reanalyze.textContent = "Analyzing…";
  result.innerHTML = '<p class="muted">Analyzing article…</p>';
  const slowMessage = setTimeout(() => {
    result.innerHTML = '<p class="muted">Still analyzing. The local AI models may be loading; please keep this popup open.</p>';
  }, 12000);
  const finish = () => {
    clearTimeout(slowMessage);
    reanalyze.disabled = false;
    reanalyze.textContent = "Re-analyze this page";
  };
  chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
    if (!tab?.id || !/^https?:/.test(tab.url || "")) {
      show({ error: "Open a news article in a regular browser tab first." });
      finish();
      return;
    }
    chrome.tabs.sendMessage(tab.id, { type: "NEWSCRED_GET_ARTICLE" }, article => {
      // The content script sends its automatic scan during page load; requesting here covers popup-first use.
      if (chrome.runtime.lastError || !article) {
        show({ error: "This page has no readable article text. Reload the page and try again." });
        finish();
        return;
      }
      chrome.runtime.sendMessage({ type: "NEWSCRED_ANALYZE", article, force }, response => {
        if (chrome.runtime.lastError) show({ error: chrome.runtime.lastError.message });
        else if (response?.result) show(response.result);
        else show({ error: response?.error });
        finish();
      });
    });
  });
}

// The popup requests current-page text directly. content.js handles the initial auto-scan.
chrome.runtime.onMessage.addListener(() => {});
reanalyze.addEventListener("click", () => scan(true));
scan();
