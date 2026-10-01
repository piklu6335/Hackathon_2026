// Use IPv4 explicitly: on some Windows setups localhost resolves to ::1 while
// Uvicorn is listening on IPv4 (0.0.0.0), which makes extension fetch fail.
const API_BASE = "http://127.0.0.1:8000"; // Set this to the deployed NewsCred origin before publishing.

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
    let timeout;
    try {
      const controller = new AbortController();
      timeout = setTimeout(() => controller.abort(), 45000);
      const response = await fetch(`${API_BASE}/api/extension/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(message.article),
        signal: controller.signal
      });
      const payload = await response.json();
      clearTimeout(timeout);
      if (!response.ok) throw new Error(payload.detail || `Analysis failed (${response.status})`);
      await chrome.storage.local.set({ [cacheKey]: payload });
      sendResponse({ result: payload, cached: false });
    } catch (error) {
      clearTimeout(timeout);
      sendResponse({
        error: error.name === "AbortError"
          ? "Analysis timed out after 45 seconds. Check that the backend is running and responsive, then retry."
          : `Could not reach NewsCred at ${API_BASE}. Check that the backend is running and reload the extension. ${error.message || "Network request failed."}`
      });
    }
  });
  return true;
});
