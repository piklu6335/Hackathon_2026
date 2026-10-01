const API_BASE = "http://localhost:8000"; // Set this to the deployed NewsCred origin before publishing.

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "NEWSCRED_ANALYZE") return;
  const url = message.article?.url || sender.tab?.url;
  if (!url) {
    sendResponse({ error: "No article URL is available." });
    return;
  }

  const cacheKey = `scan:${url}`;
  chrome.storage.local.get(cacheKey, async stored => {
    if (stored[cacheKey] && !message.force) {
      sendResponse({ result: stored[cacheKey], cached: true });
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/api/extension/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(message.article)
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `Analysis failed (${response.status})`);
      await chrome.storage.local.set({ [cacheKey]: payload });
      sendResponse({ result: payload, cached: false });
    } catch (error) {
      sendResponse({ error: error.message || "Could not reach NewsCred." });
    }
  });
  return true;
});
