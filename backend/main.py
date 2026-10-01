from __future__ import annotations

from typing import Any

import re
import requests
import langid

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from pydantic import BaseModel, HttpUrl

from backend.services.scraper import scrape_article
from backend.services.ocr import extract_text_from_image
from backend.services.fake_news_model import predict_fake_news
from backend.services.clickbait_model import predict_clickbait
from backend.services.translation import LanguagePairUnavailable, translate_article


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="NewsCred API",
    version="0.4.0",
    description=(
        "NewsCred - Article scraping, OCR and "
        "WELFake-based fake news analysis."
    ),
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
load_dotenv(PROJECT_ROOT / "backend" / ".env")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?|chrome-extension://[a-p]{32}",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ============================================================
# Request Models
# ============================================================

class ScrapeRequest(BaseModel):
    url: HttpUrl


class OCRURLRequest(BaseModel):
    image_url: HttpUrl


class ExtensionAnalyzeRequest(BaseModel):
    url: HttpUrl
    title: str = ""
    text: str
    domain: str = ""


class TranslateRequest(BaseModel):
    text: str
    target_language: str


# ============================================================
# Configuration
# ============================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
}

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_TRANSLATION_CHARACTERS = 5000
TRANSLATION_LANGUAGES = {
    "ar", "bn", "de", "en", "es", "fr", "hi", "it", "ja", "ko",
    "mr", "pa", "pt", "ru", "ta", "te", "ur", "zh-CN",
}


# ============================================================
# Root
# ============================================================

@app.get("/api/health")
def root():

    return {
        "name": "NewsCred",
        "status": "running",
        "model": "WELFake",
        "features": [
            "article_scraping",
            "local_ocr",
            "fake_news_analysis",
            "argos_translate",
        ],
    }


@app.post("/api/translate")
def translate_text(request: TranslateRequest):
    """Translate article text locally through the Argos Translate module."""
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text to translate is required.")
    if len(text) > MAX_TRANSLATION_CHARACTERS:
        raise HTTPException(
            status_code=413,
            detail=f"Translate up to {MAX_TRANSLATION_CHARACTERS:,} characters at a time.",
        )
    if request.target_language not in TRANSLATION_LANGUAGES:
        raise HTTPException(status_code=422, detail="Choose a supported target language.")

    try:
        translated_text, detected_source_language = translate_article(
            text, request.target_language
        )
    except LanguagePairUnavailable as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="The local translation model could not be installed or loaded. Try again after checking Render logs.",
        ) from exc

    return {
        "success": True,
        "translated_text": translated_text,
        "detected_source_language": detected_source_language,
        "target_language": request.target_language,
        "character_count": len(text),
    }


# ============================================================
# MODEL HELPER
# ============================================================

def analyze_text(
    text: str
) -> dict[str, Any]:

    text = text.strip()

    if not text:

        return {
            "status": "no_text",
            "prediction": None,
        }

    try:

        prediction = predict_fake_news(
            text
        )

        return prediction

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Fake-news model failed: {exc}"
            ),
        )


# ============================================================
# COMBINED CONTENT ANALYSIS
# ============================================================

def analyze_content(
    text: str,
    credibility_text: str | None = None,
    clickbait_text: str | None = None,
) -> dict[str, Any]:

    text = text.strip()

    if not text:

        return {
            "status": "no_text",
            "credibility": None,
            "clickbait": None,
        }

    # --------------------------------------------------------
    # WELFake / Fake-News Analysis
    # --------------------------------------------------------

    try:

        credibility = predict_fake_news(
            credibility_text or text
        )

    except Exception as exc:

        credibility = {
            "status": "error",
            "error": str(exc),
        }

    # --------------------------------------------------------
    # Clickbait Analysis
    # --------------------------------------------------------

    try:

        clickbait = predict_clickbait(
            clickbait_text or text
        )

    except Exception as exc:

        clickbait = {
            "status": "error",
            "error": str(exc),
        }

    # --------------------------------------------------------
    # Combined Result
    # --------------------------------------------------------

    return {

        "status": "completed",

        "credibility": credibility,

        "clickbait": clickbait,
    }


# ============================================================
# ARTICLE SCRAPING + AI ANALYSIS
# ============================================================

@app.post("/api/scrape")
def scrape(
    request: ScrapeRequest,
):

    # --------------------------------------------------------
    # Scrape article
    # --------------------------------------------------------

    try:

        article = scrape_article(
            str(request.url)
        )

    except requests.RequestException as e:

        raise HTTPException(
            status_code=502,
            detail=f"Website request failed: {e}",
        )

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Scraping failed: {e}",
        )

    # --------------------------------------------------------
    # Get article title
    # --------------------------------------------------------

    title = (
        article.get("title") or ""
    ).strip()

    # --------------------------------------------------------
    # Run WELFake + Clickbait4
    #
    # WELFake was trained on headline/title input,
    # so the title is currently used here.
    # --------------------------------------------------------

    analysis = analyze_content(
        title
    )

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {

        "success": True,

        "article": article,

        "analysis": {

            "input_type": "article_title",

            "input_text": title,

            **analysis,
        },
    }


# ============================================================
# DOWNLOAD IMAGE FROM URL
# ============================================================

def download_image_from_url(
    image_url: str,
) -> tuple[bytes, str]:

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(
        image_url,
        headers=headers,
        timeout=20,
        stream=True,
    )

    response.raise_for_status()

    content_type = (
        response.headers.get(
            "Content-Type",
            "",
        )
        .split(";")[0]
        .lower()
    )

    # --------------------------------------------------------
    # Validate image content type
    # --------------------------------------------------------

    if (
        content_type
        and content_type not in ALLOWED_IMAGE_TYPES
    ):

        raise ValueError(
            "URL does not appear to point to an image. "
            f"Content-Type: {content_type}"
        )

    chunks = []

    total_size = 0

    # --------------------------------------------------------
    # Download in chunks
    # --------------------------------------------------------

    for chunk in response.iter_content(
        chunk_size=64 * 1024
    ):

        if not chunk:
            continue

        total_size += len(chunk)

        # 10 MB maximum
        if total_size > MAX_IMAGE_SIZE:

            raise ValueError(
                "Image exceeds the 10 MB limit."
            )

        chunks.append(chunk)

    image_bytes = b"".join(
        chunks
    )

    if not image_bytes:

        raise ValueError(
            "Downloaded image is empty."
        )

    return (
        image_bytes,
        content_type or "unknown",
    )


# ============================================================
# OCR HELPER
# ============================================================

def run_ocr(
    image_bytes: bytes
) -> dict[str, Any]:

    try:

        return extract_text_from_image(
            image_bytes
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"OCR failed: {exc}",
        )


def analyze_ocr_content(ocr_result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
    """Translate non-English OCR to English before running English news models."""
    original_text = (ocr_result.get("text") or "").strip()
    average_ocr_confidence = float(ocr_result.get("average_confidence") or 0)
    confidence_threshold = 0.55 if str(ocr_result.get("engine", "")).startswith("EasyOCR") else 0.70
    if average_ocr_confidence < confidence_threshold:
        return (
            {
                "status": "low_ocr_confidence",
                "credibility": None,
                "clickbait": None,
                "analysis_language": None,
                "warning": (
                    f"OCR confidence is low ({average_ocr_confidence:.0%}), so AI scores were skipped. "
                    "Try a sharper image, crop closer to the text, or use a larger image."
                ),
            },
            None,
            "und",
        )

    detected_language, _confidence = langid.classify(original_text)
    analysis_text = original_text
    translation = None

    if detected_language != "en":
        try:
            analysis_text, detected_language = translate_article(
                original_text[:MAX_TRANSLATION_CHARACTERS], "en"
            )
            translation = {
                "translated_text": analysis_text,
                "detected_source_language": detected_language,
                "target_language": "en",
                "character_count": min(len(original_text), MAX_TRANSLATION_CHARACTERS),
            }
        except Exception as exc:
            return (
                {
                    "status": "translation_unavailable",
                    "credibility": None,
                    "clickbait": None,
                    "input_language": detected_language,
                    "analysis_language": None,
                    "warning": (
                        "This text appears to be non-English, but it could not be "
                        "translated to English. AI scores were skipped to avoid "
                        "misleading results. " + str(exc)
                    ),
                },
                None,
                detected_language,
            )

    # The credibility classifier was trained on short headlines, so use the
    # first high-confidence OCR lines for it. Clickbait analysis uses the
    # complete available English text instead.
    headline_lines = [
        str(line.get("text", "")).strip()
        for line in ocr_result.get("lines", [])
        if float(line.get("confidence", 0)) >= 0.45 and str(line.get("text", "")).strip()
    ]
    headline_candidate = " ".join(headline_lines[:4])[:300]
    if detected_language != "en" and translation:
        headline_candidate = analysis_text[:300]

    analysis = analyze_content(
        analysis_text,
        credibility_text=headline_candidate or analysis_text,
        clickbait_text=analysis_text,
    )
    warnings = [
        "AI scores are estimates, not verification. The credibility model was trained mainly on short English news headlines."
    ]
    if average_ocr_confidence < 0.60:
        warnings.append(
            f"OCR confidence is low ({average_ocr_confidence:.0%}); check the recognized text before relying on the scores."
        )
    analysis.update({
        "input_language": detected_language,
        "analysis_language": "en",
        "warning": " ".join(warnings),
    })
    return analysis, translation, detected_language

# ============================================================
# OCR USING IMAGE URL + AI ANALYSIS
# ============================================================

@app.api_route("/api/ocr-url", methods=["GET", "POST"])
def ocr_using_url(
    request: OCRURLRequest | None = None,
    image_url: HttpUrl | None = None,
):

    submitted_url = image_url or (request.image_url if request else None)
    if submitted_url is None:
        raise HTTPException(status_code=422, detail="Provide an image_url to analyze.")
    image_url = str(submitted_url)

    # --------------------------------------------------------
    # Download image
    # --------------------------------------------------------

    try:

        image_bytes, content_type = (
            download_image_from_url(
                image_url
            )
        )

    except requests.RequestException as exc:

        raise HTTPException(
            status_code=502,
            detail=f"Failed to download image: {exc}",
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    ocr_result = run_ocr(
        image_bytes
    )

    extracted_text = (
        ocr_result.get("text") or ""
    ).strip()

    # --------------------------------------------------------
    # No text detected
    # --------------------------------------------------------

    if not extracted_text:

        return {

            "success": True,

            "input": {

                "image_url": image_url,

                "content_type": content_type,

                "size_bytes": len(
                    image_bytes
                ),
            },

            "ocr": ocr_result,

            "analysis": {

                "status": "no_text_detected",

                "input_type": "image_url",

                "prediction": None,

            },
        }

    # --------------------------------------------------------
    # Run WELFake + Clickbait4
    # --------------------------------------------------------

    analysis, ocr_translation, detected_language = analyze_ocr_content(ocr_result)

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {

        "success": True,

        "input": {

            "image_url": image_url,

            "content_type": content_type,

            "size_bytes": len(
                image_bytes
            ),
        },

        "ocr": {

            "text": extracted_text,

            "engine": ocr_result.get("engine"),

            "lines": ocr_result.get(
                "lines",
                [],
            ),

            "average_confidence": (
                ocr_result.get(
                    "average_confidence"
                )
            ),
        },

        "ocr_detected_language": detected_language,

        "ocr_translation": ocr_translation,

        "analysis": {

            "status": "completed",

            "input_type": "image_url",

            "input_text": extracted_text,

            **analysis,
        },
    }


# ============================================================
# UPLOADED IMAGE + OCR + AI ANALYSIS
# ============================================================

@app.post("/api/analyze-image")
async def analyze_image(
    file: UploadFile = File(...)
):

    # --------------------------------------------------------
    # Validate image type
    # --------------------------------------------------------

    if file.content_type not in ALLOWED_IMAGE_TYPES:

        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported image type. "
                "Use JPG, PNG or WEBP."
            ),
        )

    # --------------------------------------------------------
    # Read image
    # --------------------------------------------------------

    image_bytes = await file.read()

    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="Empty image.",
        )

    if len(image_bytes) > MAX_IMAGE_SIZE:

        raise HTTPException(
            status_code=413,
            detail="Image exceeds the 10 MB limit.",
        )

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    ocr_result = run_ocr(
        image_bytes
    )

    extracted_text = (
        ocr_result.get("text") or ""
    ).strip()

    # --------------------------------------------------------
    # No text detected
    # --------------------------------------------------------

    if not extracted_text:

        return {

            "success": True,

            "input": {

                "filename": file.filename,

                "content_type": file.content_type,

                "size_bytes": len(
                    image_bytes
                ),
            },

            "ocr": ocr_result,

            "analysis": {

                "status": "no_text_detected",

                "input_type": "uploaded_image",

                "prediction": None,

            },
        }

    # --------------------------------------------------------
    # Run WELFake + Clickbait4
    # --------------------------------------------------------

    analysis, ocr_translation, detected_language = analyze_ocr_content(ocr_result)

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {

        "success": True,

        "input": {

            "filename": file.filename,

            "content_type": file.content_type,

            "size_bytes": len(
                image_bytes
            ),
        },

        "ocr": {

            "text": extracted_text,

            "engine": ocr_result.get("engine"),

            "lines": ocr_result.get(
                "lines",
                [],
            ),

            "average_confidence": (
                ocr_result.get(
                    "average_confidence"
                )
            ),
        },

        "ocr_detected_language": detected_language,

        "ocr_translation": ocr_translation,

        "analysis": {

            "status": "completed",

            "input_type": "uploaded_image",

            "input_text": extracted_text,

            **analysis,
        },
    }


@app.post("/api/extension/analyze")
def analyze_extension_article(request: ExtensionAnalyzeRequest):
    """Analyze article text extracted by the NewsCred browser extension."""
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="No article text was provided.")
    if len(text) > 100_000:
        raise HTTPException(status_code=413, detail="Article text exceeds the 100 KB limit.")

    # The WELFake model was trained on headlines. Use the article title when
    # available; retain the extracted body for the clickbait model and UI.
    credibility_input = request.title.strip() or text[:500]
    credibility = analyze_content(credibility_input)
    return {
        "success": True,
        "scan": {"source": "browser_extension", "url": str(request.url), "domain": request.domain},
        "article": {"title": request.title.strip(), "text": text},
        "analysis": {"input_type": "browser_extension", **credibility},
    }


# Serve the existing frontend from the same origin as the API.
@app.get("/", include_in_schema=False)
def home_page():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/signup", include_in_schema=False)
def signup_page():
    return FileResponse(FRONTEND_DIR / "signup.html")


@app.get("/analyze", include_in_schema=False)
def analyze_page():
    return FileResponse(FRONTEND_DIR / "analyze.html")


app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
