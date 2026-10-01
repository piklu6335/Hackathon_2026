document.addEventListener("DOMContentLoaded", () => {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));
      
      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.target);
      if (target) target.classList.add("active");
    });
  });

  const loader = document.getElementById("loader");
  const loaderText = document.getElementById("loader-text");
  
  function showLoading(text = "Processing...") {
    if(loaderText) loaderText.textContent = text;
    if(loader) loader.classList.add("active");
  }
  
  function hideLoading() {
    if(loader) loader.classList.remove("active");
  }

  const resultContainer = document.getElementById("result-container");
  
  function resetAnalysis() {
    resultContainer.innerHTML = "";
    resultContainer.classList.remove("hidden");
  }

  function renderPrediction(data) {
    const analysis = data.analysis || data;
    const credibility = analysis.credibility || {};
    const clickbait = analysis.clickbait || {};
    const ocr = data.ocr || {};
    const predictionResult = credibility.prediction || {};
    const prediction = predictionResult.label || credibility.label || "UNCERTAIN";
    const confidenceValue = predictionResult.confidence ?? credibility.confidence;
    const conf = Number.isFinite(Number(confidenceValue)) ? Math.round(Number(confidenceValue) * 100) + "%" : "N/A";
    const score = Number.isFinite(Number(confidenceValue)) ? Math.round(Number(confidenceValue) * 100) : "--";
    
    let statusClass = "status-" + prediction.toUpperCase();
    
    let html = `
      <div class="glass-panel">
        <h2 class="mb-8">AI Content Analysis</h2>
        <div class="flex items-center gap-8 flex-wrap">
          <div class="score-circle" style="--score-pct: ${score}%">
            <div class="score-value">
              <div class="num">${score}</div>
              <div class="max">${data.score ? '/ 100' : 'Confidence'}</div>
            </div>
          </div>
          <div class="flex-col gap-2">
            <div class="status-badge ${statusClass}">${prediction.toUpperCase()}</div>
            <div style="color: var(--text-secondary); margin-top: 8px;">Model: WELFake</div>
            <div style="color: var(--text-secondary);">Confidence: ${conf}</div>
          </div>
        </div>
    `;

    const detectedText = ocr.text || data.detected_text;
    if (detectedText) {
      const ocrConfidence = ocr.average_confidence || data.ocr_confidence;
      let ocrConf = ocrConfidence ? Math.round(ocrConfidence * 100) + "%" : "";
      html += `
        <h3 style="margin-top: 32px; margin-bottom: 8px;">OCR Analysis ${ocrConf ? '('+ocrConf+')' : ''}</h3>
        <div class="ocr-result">${escapeHTML(detectedText)}</div>
      `;
    }

    if (clickbait.score_percent !== undefined) {
      html += `<h3 style="margin-top: 32px;">Clickbait assessment</h3><div class="factor-list"><div class="factor-item"><span>Score</span><span>${escapeHTML(String(clickbait.score_percent))}%</span></div><div class="factor-item"><span>Level</span><span>${escapeHTML(clickbait.level || "Unknown")}</span></div></div>`;
    }

    if (data.factors) {
      html += `<h3 style="margin-top: 32px;">Analysis Breakdown</h3><div class="factor-list">`;
      for (const [key, val] of Object.entries(data.factors)) {
         html += `<div class="factor-item"><span>${escapeHTML(key.replace(/_/g, ' '))}</span><span>${escapeHTML(String(val))}</span></div>`;
      }
      html += `</div>`;
    } else {
      // Placeholders
      html += `
        <h3 style="margin-top: 32px;">Analysis Breakdown</h3>
        <div class="factor-list">
          <div class="factor-item"><span>Source Reputation</span><span style="color:var(--text-secondary)">Pending pipeline</span></div>
          <div class="factor-item"><span>Linguistic Sensationalism</span><span style="color:var(--text-secondary)">Pending pipeline</span></div>
          <div class="factor-item"><span>Content Consistency</span><span style="color:var(--text-secondary)">Pending pipeline</span></div>
        </div>
      `;
    }

    html += `</div>`;
    return html;
  }

  function renderArticle(data) {
    let html = `<div class="glass-panel">`;
    if (data.image) {
      html += `<img src="${escapeHTML(data.image)}" style="width: 100%; max-height: 300px; object-fit: cover; border-radius: 8px; margin-bottom: 24px;">`;
    }
    html += `<h2>${escapeHTML(data.title || "Untitled Article")}</h2>`;
    
    html += `<div class="article-meta">`;
    if (data.domain) html += `<span>🌍 ${escapeHTML(data.domain)}</span>`;
    if (data.author) html += `<span>👤 ${escapeHTML(data.author)}</span>`;
    if (data.published_date) html += `<span>🕒 ${escapeHTML(data.published_date)}</span>`;
    if (data.word_count) html += `<span>📄 ${data.word_count} words</span>`;
    html += `</div>`;

    if (data.description) {
      html += `<div class="article-desc">${escapeHTML(data.description)}</div>`;
    }

    if (data.content) {
      html += `<h3>Article Content</h3><div class="article-content">${escapeHTML(data.content)}</div>`;
    }
    
    html += `</div>`;
    return html;
  }

  function escapeHTML(str) {
    if (!str) return "";
    return str.replace(/[&<>'"]/g, 
      tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag]));
  }

  function showError(msg) {
    hideLoading();
    resetAnalysis();
    resultContainer.innerHTML = `
      <div class="glass-panel" style="border-color: var(--color-red); background: rgba(239,68,68,0.1);">
        <h3 style="color: var(--color-red); margin-bottom: 8px;">Analysis Error</h3>
        <p>${escapeHTML(msg)}</p>
      </div>
    `;
  }

  const urlForm = document.getElementById("url-form");
  if (urlForm) {
    urlForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const url = document.getElementById("article-url").value;
      if (!url) return;
      
      showLoading("Extracting article...");
      try {
      const res = await window.api.scrapeArticle(url);
        hideLoading();
        resetAnalysis();
      resultContainer.innerHTML = renderArticle(res.article || {}) + renderPrediction(res);
      } catch (err) {
        showError(err.message);
      }
    });
  }

  const imgUrlForm = document.getElementById("img-url-form");
  if (imgUrlForm) {
    imgUrlForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const url = document.getElementById("image-url").value;
      if (!url) return;
      
      showLoading("Running AI analysis...");
      try {
        const res = await window.api.ocrImageFromUrl(url);
        hideLoading();
        resetAnalysis();
        resultContainer.innerHTML = renderPrediction(res);
      } catch (err) {
        showError(err.message);
      }
    });
  }

  const uploadZone = document.getElementById("upload-zone");
  const fileInput = document.getElementById("file-upload");
  
  if (uploadZone && fileInput) {
    uploadZone.addEventListener("click", () => fileInput.click());
    
    uploadZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadZone.classList.add("dragover");
    });
    
    uploadZone.addEventListener("dragleave", () => {
      uploadZone.classList.remove("dragover");
    });
    
    uploadZone.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadZone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFile(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFile(e.target.files[0]);
      }
    });
  }

  async function handleFile(file) {
    if (!file.type.startsWith("image/")) {
      return showError("Please upload a PNG, JPG or WEBP image.");
    }
    if (file.size > 10 * 1024 * 1024) {
      return showError("Image exceeds the 10 MB limit.");
    }

    showLoading("Uploading and analyzing...");
    try {
      const res = await window.api.analyzeImage(file);
      hideLoading();
      resetAnalysis();
      resultContainer.innerHTML = renderPrediction(res);
    } catch (err) {
      showError(err.message);
    }
  }
});
