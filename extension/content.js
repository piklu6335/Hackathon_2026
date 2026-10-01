(() => {
  if (!/^https?:$/.test(location.protocol)) return;
  const article = document.querySelector("article");
  const title = (article?.querySelector("h1") || document.querySelector("h1"))?.innerText?.trim() || document.title;
  const root = article || document.querySelector("main") || document.body;
  const text = (root.innerText || "").replace(/\s+/g, " ").trim().slice(0, 100000);
  const paragraphs = [...root.querySelectorAll("p")].filter(node => node.innerText.trim().length > 60).length;
  const looksLikeArticle = Boolean(article) || (Boolean(document.querySelector("main")) && paragraphs >= 3 && text.length >= 1000);
  if (!looksLikeArticle) return;

  const articleData = () => ({ url: location.href, title, text, domain: location.hostname });
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === "NEWSCRED_GET_ARTICLE") sendResponse(articleData());
  });

  // Extract the article only when the user opens the popup. Avoids an
  // unrequested background scan and duplicate model inference on popup open.
})();
